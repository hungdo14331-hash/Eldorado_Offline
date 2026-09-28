#!/usr/bin/env python3
"""Round 3B PvP 2025 backend acceptance tests on an isolated SQLite DB."""

import http.client
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
RANK = "/ELDORADO_WEB/PVP_2025/get_pvp_ranking.php"
ENTER = "/ELDORADO_WEB/PVP_2025/enter_pvp_game.php"
UPDATE = "/ELDORADO_WEB/PVP_2025/update_pvp_result.php"
TEAM_A = "1:1:20:0:0:1,2:1:20:0:0:2,3:1:20:0:0:3"
TEAM_B = "4:1:20:0:0:4,25:1:20:0:0:25,46:1:60:0:0:46"
ITEM_A = "1001:1:1-0:0"
RANK_FIELDS = {
    "STATE", "ranking_list", "my_ranking", "TOT_SCORE",
    "entry_fee_rubies", "TICKET", "MAX_SCORE", "SCORE_REWARD",
    "season_num", "last_season_num", "season_period",
    "last_season_period", "weekly_reward_ruby", "weekly_reward_point",
    "season_reward", "TOT_POINT", "S_RANKING", "fame_ranking_list",
    "season_ranking_list",
}


def form(**values):
    return "&".join(f"{key}={value}" for key, value in values.items())


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, root, use_db=True):
        self.root = Path(root)
        self.db = self.root / "pvp.db"
        self.save = self.root / "pvp_save.json"
        self.log = self.root / "serve.log"
        self.use_db = use_db
        self.port = None
        self.proc = None

    def start(self):
        self.port = free_port()
        command = [
            sys.executable, "-u", str(BASE / "serve.py"),
            "--mode", "offline", "--host", "127.0.0.1",
            "--port", str(self.port), "--log", str(self.log),
        ]
        if self.use_db:
            command.extend(["--db", str(self.db)])
        else:
            command.extend(["--save-file", str(self.save), "--uniq-id", "json-a"])
        self.proc = subprocess.Popen(
            command,
            cwd=str(BASE),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"test server exited; see {self.log}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("test server did not listen")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.proc = None

    def restart(self):
        self.stop()
        self.start()

    def post(self, path, body):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request(
                "POST", path, body=body.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = connection.getresponse()
            text = response.read().decode("utf-8", "replace")
            return response.status, json.loads(text), text
        finally:
            connection.close()


class PvP2025Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="busidol_pvp_2025_")
        self.server = Server(self.temp.name)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        for attempt in range(20):
            try:
                self.temp.cleanup()
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)

    def seed(self, uid, ruby=100, extra=None):
        payload = {
            "USER_NAME": uid,
            "DATA1": f"{uid},100000,{ruby},2,KR,1,2,1,20,0,0,20260924,0,0,1:2:3",
        }
        payload.update(extra or {})
        with closing(sqlite3.connect(self.server.db)) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                (uid, json.dumps(payload, ensure_ascii=False)),
            )
            connection.commit()

    def rank(self, uid, name=None, team=TEAM_A, item=ITEM_A):
        return self.server.post(RANK, form(
            HOST_ID=uid, LANG=2, NAME=name or uid, LEVEL=20,
            TEAM=team, ITEM=item, TOWER_HP=1200, TOWER_LEVEL=5,
            MISSILE_AP=77, MISSILE_LEVEL=3, MISSILE_TICK=600,
            VER_DATE=20260908, ETC="",
        ))

    def enter(self, uid, mode="ENTRY_TICKET", team=TEAM_A, item=ITEM_A):
        return self.server.post(ENTER, form(
            HOST_ID=uid, LANG=2, NAME=uid, LEVEL=20,
            TEAM=team, ITEM=item, TOWER_HP=1200, TOWER_LEVEL=5,
            MISSILE_AP=77, MISSILE_LEVEL=3, MISSILE_TICK=600,
            MODE=mode, VER_DATE=20260908, ETC="",
        ))

    def update(self, uid, nonce, score="20", result="승", team=TEAM_A):
        return self.server.post(UPDATE, form(
            HOST_ID=uid, LANG=2, TEAM=team, SCORE=score,
            RESULT=result, MATCH_NONCE=nonce, VER_DATE=20260908, ETC="",
        ))

    def db_one(self, sql, values=()):
        with closing(sqlite3.connect(self.server.db, timeout=10)) as connection:
            return connection.execute(sql, values).fetchone()

    def test_a_ranking_response_is_client_compatible(self):
        self.seed("rank-a")
        status, payload, _ = self.rank("rank-a")
        self.assertEqual(status, 200)
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertTrue(RANK_FIELDS.issubset(payload))
        self.assertIsInstance(payload["ranking_list"], list)
        self.assertIsInstance(payload["fame_ranking_list"], list)
        self.assertIsInstance(payload["season_ranking_list"], list)
        self.assertEqual(len(payload["weekly_reward_ruby"]), 6)
        self.assertEqual(len(payload["weekly_reward_point"]), 10)
        self.assertEqual(len(payload["season_reward"]), 7)

    def test_b_enter_creates_active_nonce_and_parseable_nonself_opponent(self):
        self.seed("enter-a")
        self.seed("enter-b")
        self.rank("enter-a", team=TEAM_A)
        self.rank("enter-b", team=TEAM_B)
        status, payload, _ = self.enter("enter-a")
        self.assertEqual(status, 200)
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertTrue(payload["MATCH_NONCE"])
        opponent = payload["matched_user"]
        self.assertEqual(opponent["ID"], "enter-b")
        self.assertNotEqual(opponent["ID"], "enter-a")
        self.assertEqual(opponent["TEAM"], TEAM_B)
        for field in (
            "ID", "NAME", "LEVEL", "TOWER_HP", "TOWER_LEVEL",
            "MISSILE_AP", "MISSILE_LEVEL", "MISSILE_TICK", "TEAM",
            "ITEM", "PLATFORM", "PROFILE",
        ):
            self.assertIn(field, opponent)
        row = self.db_one(
            "SELECT user_id,status,opponent_id FROM pvp_sessions WHERE nonce=?",
            (payload["MATCH_NONCE"],),
        )
        self.assertEqual(row, ("enter-a", "ACTIVE", "enter-b"))

    def test_b2_ai_fallback_derives_a_valid_owner_snapshot(self):
        self.seed("solo")
        self.rank("solo", team=TEAM_A, item=ITEM_A)
        _, payload, _ = self.enter("solo")
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertNotEqual(payload["matched_user"]["ID"], "solo")
        self.assertEqual(payload["matched_user"]["TEAM"], TEAM_A)
        self.assertEqual(payload["matched_user"]["ITEM"], ITEM_A)

    def test_b3_fee_and_active_enter_retry_charge_once(self):
        self.seed("fee-ticket")
        self.rank("fee-ticket")
        _, first, _ = self.enter("fee-ticket")
        _, retry, _ = self.enter("fee-ticket")
        self.assertEqual(first["MATCH_NONCE"], retry["MATCH_NONCE"])
        self.assertEqual(first["add_ticket"], "9")
        self.assertEqual(retry["add_ticket"], "9")
        self.assertNotIn("s_add_ruby", first)

        today = time.strftime("%Y%m%d")
        self.seed("fee-ruby", ruby=100, extra={
            "pvp_ticket_day": today, "pvp_ticket_left": "0",
        })
        self.rank("fee-ruby")
        _, paid, _ = self.enter("fee-ruby", mode="ENTRY_RUBY")
        self.assertEqual(paid["STATE"], "SUCCESS")
        self.assertEqual(paid["s_add_ruby"], "90")

    def test_c_result_consumes_nonce_and_mutates_ranking_once(self):
        self.seed("result-a")
        self.rank("result-a")
        _, entered, _ = self.enter("result-a")
        _, result, _ = self.update("result-a", entered["MATCH_NONCE"])
        self.assertEqual(result["STATE"], "SUCCESS")
        self.assertEqual(result["tot_score"], "20")
        self.assertEqual(result["TOT_SCORE"], "20")
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("result-a",))[0],
            20,
        )
        self.assertEqual(
            self.db_one("SELECT status FROM pvp_sessions WHERE nonce=?", (entered["MATCH_NONCE"],))[0],
            "CONSUMED",
        )

    def test_d_same_nonce_replays_exact_response_without_double_mutation(self):
        self.seed("retry-a")
        self.rank("retry-a")
        _, entered, _ = self.enter("retry-a")
        _, first, first_text = self.update("retry-a", entered["MATCH_NONCE"])
        _, second, second_text = self.update("retry-a", entered["MATCH_NONCE"])
        self.assertEqual(second_text, first_text)
        self.assertEqual(second, first)
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("retry-a",))[0],
            20,
        )

    def test_e_old_consumed_nonce_replays_without_touching_new_active_match(self):
        self.seed("old-a")
        self.rank("old-a")
        _, match_a, _ = self.enter("old-a")
        _, response_a, text_a = self.update("old-a", match_a["MATCH_NONCE"])
        _, match_b, _ = self.enter("old-a")
        _, replay_a, replay_text = self.update("old-a", match_a["MATCH_NONCE"])
        self.assertEqual(replay_text, text_a)
        self.assertEqual(replay_a, response_a)
        self.assertEqual(
            self.db_one("SELECT status FROM pvp_sessions WHERE nonce=?", (match_b["MATCH_NONCE"],))[0],
            "ACTIVE",
        )

    def test_f_unknown_or_wrong_owner_nonce_cannot_mutate(self):
        self.seed("owner-a")
        self.seed("owner-b")
        self.rank("owner-a")
        self.rank("owner-b", team=TEAM_B)
        _, entered, _ = self.enter("owner-a")
        _, unknown, _ = self.update("owner-a", "not-a-server-nonce")
        _, wrong_owner, _ = self.update("owner-b", entered["MATCH_NONCE"], team=TEAM_B)
        self.assertEqual(unknown["STATE"], "ERROR")
        self.assertEqual(wrong_owner["STATE"], "ERROR")
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("owner-a",))[0],
            0,
        )
        self.assertEqual(
            self.db_one("SELECT status FROM pvp_sessions WHERE nonce=?", (entered["MATCH_NONCE"],))[0],
            "ACTIVE",
        )

    def test_g_expired_nonce_cannot_mutate(self):
        self.seed("expired-a")
        self.rank("expired-a")
        _, entered, _ = self.enter("expired-a")
        with closing(sqlite3.connect(self.server.db)) as connection:
            connection.execute(
                "UPDATE pvp_sessions SET expires_at=? WHERE nonce=?",
                (int(time.time()) - 1, entered["MATCH_NONCE"]),
            )
            connection.commit()
        _, payload, _ = self.update("expired-a", entered["MATCH_NONCE"])
        self.assertEqual(payload["STATE"], "ERROR")
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("expired-a",))[0],
            0,
        )
        self.assertEqual(
            self.db_one("SELECT status FROM pvp_sessions WHERE nonce=?", (entered["MATCH_NONCE"],))[0],
            "EXPIRED",
        )

    def test_h_concurrent_duplicate_update_mutates_at_most_once(self):
        self.seed("race-a")
        self.rank("race-a")
        _, entered, _ = self.enter("race-a")
        nonce = entered["MATCH_NONCE"]
        barrier = threading.Barrier(3)
        outputs = []

        def send():
            barrier.wait()
            outputs.append(self.update("race-a", nonce))

        threads = [threading.Thread(target=send) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(20)
        self.assertEqual(len(outputs), 2)
        self.assertTrue(all(payload[1]["STATE"] == "SUCCESS" for payload in outputs))
        self.assertEqual(outputs[0][2], outputs[1][2])
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("race-a",))[0],
            20,
        )

    def test_i_consumed_retry_survives_server_restart(self):
        self.seed("restart-a")
        self.rank("restart-a")
        _, entered, _ = self.enter("restart-a")
        _, _, expected_text = self.update("restart-a", entered["MATCH_NONCE"])
        self.server.restart()
        _, payload, replay_text = self.update("restart-a", entered["MATCH_NONCE"])
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertEqual(replay_text, expected_text)
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("restart-a",))[0],
            20,
        )

    def test_j_malformed_or_out_of_bounds_result_is_rejected_without_mutation(self):
        self.seed("bad-a")
        self.rank("bad-a")
        _, entered, _ = self.enter("bad-a")
        nonce = entered["MATCH_NONCE"]
        bad_payloads = [
            ("nan", "승"), ("-1", "승"), ("1001", "승"),
            ("20", "BAD"), ("5", "패"),
        ]
        for score, result in bad_payloads:
            with self.subTest(score=score, result=result):
                _, payload, _ = self.update("bad-a", nonce, score=score, result=result)
                self.assertEqual(payload["STATE"], "ERROR")
        self.assertEqual(
            self.db_one("SELECT total_score FROM pvp_leaderboard WHERE user_id=?", ("bad-a",))[0],
            0,
        )
        self.assertEqual(
            self.db_one("SELECT status FROM pvp_sessions WHERE nonce=?", (nonce,))[0],
            "ACTIVE",
        )

    def test_k_literal_client_result_token_is_normalized(self):
        self.seed("wire-a")
        self.rank("wire-a")
        _, entered, _ = self.enter("wire-a")
        literal_wire_win = "\u00ec\u008a\u00b9"
        _, payload, _ = self.update(
            "wire-a", entered["MATCH_NONCE"], result=literal_wire_win,
        )
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertEqual(payload["tot_score"], "20")

    def test_l_json_mode_uses_only_an_isolated_save_and_replays(self):
        self.server.stop()
        self.server = Server(self.temp.name, use_db=False)
        self.server.save.write_text(json.dumps({
            "USER_NAME": "json-a",
            "DATA1": "json-a,100000,100,2,KR,1,2,1,20,0,0,20260924,0,0,1:2:3",
        }), encoding="utf-8")
        self.server.start()
        _, ranked, _ = self.rank("json-a")
        _, entered, _ = self.enter("json-a")
        _, result, first_text = self.update("json-a", entered["MATCH_NONCE"])
        _, replay, replay_text = self.update("json-a", entered["MATCH_NONCE"])
        self.assertEqual(ranked["STATE"], "SUCCESS")
        self.assertEqual(entered["STATE"], "SUCCESS")
        self.assertEqual(result["STATE"], "SUCCESS")
        self.assertEqual(replay, result)
        self.assertEqual(replay_text, first_text)
        saved = json.loads(self.server.save.read_text(encoding="utf-8"))
        self.assertEqual(saved["pvp_leaderboard"]["json-a"]["total_score"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)

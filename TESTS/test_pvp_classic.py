#!/usr/bin/env python3
"""Acceptance tests for the legacy PVP_CLS_2026 HTTP contract."""

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

RANK = "/ELDORADO_WEB/PVP_CLS_2026/get_pvp_cls_ranking.php"
ENTER = "/ELDORADO_WEB/PVP_CLS_2026/enter_pvp_cls_game.php"
UPDATE = "/ELDORADO_WEB/PVP_CLS_2026/update_pvp_cls_result.php"
TEAM_A = "1:1:20:0:0:1,2:1:20:0:0:2,3:1:20:0:0:3"
TEAM_B = "4:1:20:0:0:4,25:1:20:0:0:25,46:1:60:0:0:46"
ITEM_A = "1001:1:1-0:0"


def form(**values):
    return "&".join(f"{key}={value}" for key, value in values.items())


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    def __init__(self, root, use_db=True):
        self.root = Path(root)
        self.db = self.root / "classic.db"
        self.save = self.root / "classic_save.json"
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
        self.proc = subprocess.Popen(command, cwd=str(BASE),
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.STDOUT)
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

    def post(self, path, body):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request("POST", path, body=body.encode("utf-8"),
                               headers={"Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            text = response.read().decode("utf-8", "replace")
            return response.status, json.loads(text), text
        finally:
            connection.close()


class PvPClassicTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="busidol_pvp_classic_")
        self.server = Server(self.temp.name)
        self.server.start()

    def tearDown(self):
        self.server.stop()
        self.temp.cleanup()

    def seed(self, uid, gold=100000, extra=None):
        payload = {
            "USER_NAME": uid,
            "DATA1": f"{uid},{gold},0,2,KR,1,2,1,20,0,0,20260924,0,0,1:2:3",
        }
        payload.update(extra or {})
        with closing(sqlite3.connect(self.server.db)) as connection:
            connection.execute("INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                               (uid, json.dumps(payload, ensure_ascii=False)))
            connection.commit()

    def rank(self, uid, team=TEAM_A, item=ITEM_A):
        return self.server.post(RANK, form(
            HOST_ID=uid, LANG=2, NAME=uid, LEVEL=20, TEAM=team, ITEM=item,
            TOWER_HP=1200, TOWER_LEVEL=5, MISSILE_AP=77, MISSILE_LEVEL=3,
            MISSILE_TICK=600, VER_DATE=20260908, ETC=""))

    def enter(self, uid, mode="ENTRY_TICKET", team=TEAM_A, item=ITEM_A):
        return self.server.post(ENTER, form(
            HOST_ID=uid, LANG=2, NAME=uid, LEVEL=20, TEAM=team, ITEM=item,
            TOWER_HP=1200, TOWER_LEVEL=5, MISSILE_AP=77, MISSILE_LEVEL=3,
            MISSILE_TICK=600, MODE=mode, VER_DATE=20260908, ETC=""))

    def update(self, uid, score="20", result="승", team=TEAM_A, item=ITEM_A):
        return self.server.post(UPDATE, form(
            HOST_ID=uid, LANG=2, TEAM=team, ITEM=item, SCORE=score,
            RESULT=result, VER_DATE=20260908, ETC=""))

    def db_one(self, sql, values=()):
        with closing(sqlite3.connect(self.server.db, timeout=10)) as connection:
            return connection.execute(sql, values).fetchone()

    def test_a_ranking_has_classic_contract_and_isolated_board(self):
        self.seed("rank-a")
        status, payload, _ = self.rank("rank-a")
        self.assertEqual(status, 200)
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertIsInstance(payload["ranking_list"], list)
        for field in ("my_ranking", "TOT_SCORE", "TICKET", "entry_fee_gold",
                      "PLATFORM_NAME_COM"):
            self.assertIn(field, payload)
        self.assertEqual(payload["TICKET"], "10")
        self.assertEqual(self.db_one(
            "SELECT total_score FROM pvp_classic_leaderboard WHERE user_id=?",
            ("rank-a",))[0], 0)

    def test_b_ticket_entry_replays_and_matches_classic_snapshot(self):
        self.seed("enter-a")
        self.seed("enter-b")
        self.rank("enter-a", team=TEAM_A)
        self.rank("enter-b", team=TEAM_B)
        _, first, _ = self.enter("enter-a")
        _, retry, _ = self.enter("enter-a")
        self.assertEqual(first["STATE"], "SUCCESS")
        self.assertEqual(first, retry)
        self.assertEqual(first["add_ticket"], "9")
        self.assertEqual(first["matched_user"]["ID"], "enter-b")
        self.assertEqual(first["matched_user"]["TEAM"], TEAM_B)
        self.assertEqual(self.db_one(
            "SELECT status FROM pvp_classic_sessions WHERE user_id=?",
            ("enter-a",))[0], "ACTIVE")

    def test_c_gold_entry_charges_fee_once_and_returns_new_gold(self):
        self.seed("gold-a", gold=50000, extra={
            "pvp_cls_ticket_day": time.strftime("%Y%m%d"),
            "pvp_cls_ticket_left": "0",
        })
        self.rank("gold-a")
        _, payload, _ = self.enter("gold-a", mode="ENTRY_GOLD")
        self.assertEqual(payload["STATE"], "SUCCESS")
        self.assertEqual(payload["s_add_gold"], "40000")
        _, retry, _ = self.enter("gold-a", mode="ENTRY_GOLD")
        self.assertEqual(retry, payload)
        saved = json.loads(self.db_one("SELECT payload FROM saves WHERE id=?",
                                       ("gold-a",))[0])
        self.assertEqual(saved["DATA1"].split(",")[1], "40000")

    def test_d_result_updates_classic_score_and_replays_without_double_score(self):
        self.seed("result-a")
        self.rank("result-a")
        self.enter("result-a")
        _, first, first_text = self.update("result-a")
        _, second, second_text = self.update("result-a")
        self.assertEqual(first["STATE"], "SUCCESS")
        self.assertEqual(first["TOT_SCORE"], "20")
        self.assertEqual(first["TICKET"], "9")
        self.assertEqual(second_text, first_text)
        self.assertEqual(self.db_one(
            "SELECT total_score FROM pvp_classic_leaderboard WHERE user_id=?",
            ("result-a",))[0], 20)
        self.assertEqual(self.db_one(
            "SELECT status FROM pvp_classic_sessions WHERE user_id=?",
            ("result-a",))[0], "CONSUMED")

    def test_e_errors_do_not_charge_or_mutate(self):
        self.seed("error-a", gold=5, extra={
            "pvp_cls_ticket_day": time.strftime("%Y%m%d"),
            "pvp_cls_ticket_left": "0",
        })
        self.rank("error-a")
        _, no_gold, _ = self.enter("error-a", mode="ENTRY_GOLD")
        self.assertEqual(no_gold["STATE"], "ERROR")
        self.assertEqual(no_gold["CODE"], "-103")
        _, bad_mode, _ = self.enter("error-a", mode="BAD")
        self.assertEqual(bad_mode["STATE"], "ERROR")
        self.assertEqual(bad_mode["CODE"], "-101")
        self.assertIsNone(self.db_one(
            "SELECT session_id FROM pvp_classic_sessions WHERE user_id=?",
            ("error-a",)))

    def test_f_invalid_result_keeps_active_session(self):
        self.seed("bad-a")
        self.rank("bad-a")
        self.enter("bad-a")
        for score, result in (("nan", "승"), ("-1", "승"), ("5", "패"),
                               ("20", "BAD"), ("20", "승")):
            if score == "20" and result == "승":
                continue
            _, payload, _ = self.update("bad-a", score=score, result=result)
            self.assertEqual(payload["STATE"], "ERROR")
        self.assertEqual(self.db_one(
            "SELECT status,total_score FROM pvp_classic_sessions s JOIN pvp_classic_leaderboard l ON l.user_id=s.user_id WHERE s.user_id=?",
            ("bad-a",)), ("ACTIVE", 0))

    def test_h_abandoned_ticket_match_keeps_ticket_spent(self):
        self.seed("abandon-a")
        self.rank("abandon-a")
        _, entered, _ = self.enter("abandon-a")
        self.assertEqual(entered["add_ticket"], "9")
        # No result is posted: the player has left the battle. Entry already
        # consumed the free ticket, so a later ranking read must stay at 9.
        _, ranking, _ = self.rank("abandon-a")
        self.assertEqual(ranking["TICKET"], "9")
        self.assertEqual(self.db_one(
            "SELECT status FROM pvp_classic_sessions WHERE user_id=?",
            ("abandon-a",))[0], "ACTIVE")

    def test_g_concurrent_result_consumes_once(self):
        self.seed("race-a")
        self.rank("race-a")
        self.enter("race-a")
        barrier = threading.Barrier(3)
        outputs = []

        def send():
            barrier.wait()
            outputs.append(self.update("race-a"))

        threads = [threading.Thread(target=send) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(20)
        self.assertEqual(len(outputs), 2)
        self.assertTrue(all(payload[1]["STATE"] == "SUCCESS" for payload in outputs))
        self.assertEqual(outputs[0][2], outputs[1][2])
        self.assertEqual(self.db_one(
            "SELECT total_score FROM pvp_classic_leaderboard WHERE user_id=?",
            ("race-a",))[0], 20)


class PvPClassicJsonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="busidol_pvp_classic_json_")
        self.server = Server(self.temp.name, use_db=False)
        self.server.start()
        self.server.save.write_text(json.dumps({
            "USER_NAME": "json-a",
            "DATA1": "json-a,50000,0,2,KR,1,2,1,20,0,0,20260924,0,0,1:2:3",
        }), encoding="utf-8")

    def tearDown(self):
        self.server.stop()
        self.temp.cleanup()

    def post(self, path, body):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.port, timeout=20)
        try:
            connection.request("POST", path, body=body.encode("utf-8"),
                               headers={"Content-Type": "application/x-www-form-urlencoded"})
            response = connection.getresponse()
            text = response.read().decode("utf-8", "replace")
            return response.status, json.loads(text), text
        finally:
            connection.close()

    def test_json_save_round_trip(self):
        common = dict(HOST_ID="ignored", LANG=2, NAME="json-a", LEVEL=20,
                      TEAM=TEAM_A, ITEM=ITEM_A, TOWER_HP=1200, TOWER_LEVEL=5,
                      MISSILE_AP=77, MISSILE_LEVEL=3, MISSILE_TICK=600,
                      VER_DATE=20260908, ETC="")
        _, rank, _ = self.post(RANK, form(**common))
        self.assertEqual(rank["STATE"], "SUCCESS")
        _, entered, _ = self.post(ENTER, form(**common, MODE="ENTRY_TICKET"))
        self.assertEqual(entered["STATE"], "SUCCESS")
        _, result, first_text = self.post(UPDATE, form(
            HOST_ID="ignored", LANG=2, TEAM=TEAM_A, ITEM=ITEM_A, SCORE=20,
            RESULT="승", VER_DATE=20260908, ETC=""))
        self.assertEqual(result["TOT_SCORE"], "20")
        _, replay, second_text = self.post(UPDATE, form(
            HOST_ID="ignored", LANG=2, TEAM=TEAM_A, ITEM=ITEM_A, SCORE=20,
            RESULT="승", VER_DATE=20260908, ETC=""))
        self.assertEqual(second_text, first_text)
        self.assertEqual(replay["TOT_SCORE"], "20")
        saved = json.loads(self.server.save.read_text(encoding="utf-8"))
        self.assertEqual(saved["pvp_cls_ticket_left"], "9")


if __name__ == "__main__":
    unittest.main()

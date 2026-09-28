"""Guild War (`update_guild_battle.php`) + Guild Boss (`update_guild_boss.php`).

Chay qua HTTP that cua serve.py nen bat duoc route sai trong serve.py va
NameError trong handler. Test kiem tra phan client that su doc:
`defeated_num` cho ca 3 tab xep hang, `deck30` la object khoa "1".."30",
`update_guild_battle_result` tra response long.
"""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

import guild_backend
import serve


def save_for(account, gold=0, cloud=1000):
    d1 = ["0"] * 21
    d1[1] = str(gold)
    d1[2] = "50000"
    return {"USER_NAME": account, "DATA1": ",".join(d1), "cloud_piece": str(cloud)}


class GuildBattleBossTests(unittest.TestCase):
    ACCOUNTS = ("g_bt_a", "g_bt_b", "g_bt_c", "g_bt_d")
    # Deck/HP gia de test - khong can so voi client that, chi can co gia tri.
    DECK = "1,2,3,4,5"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_guild_bt_")
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        serve.init_db(Path(cls.tmp.name) / "guild.db")
        for account in cls.ACCOUNTS:
            serve.add_account(account, "test-only-password")
        cls.server = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        serve.SRV_PORT = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if serve.DB_CONN is not None:
            serve.DB_CONN.close()
            serve.DB_CONN = None
        serve.DB_FILE = None
        serve.REQUIRE_LOGIN = False
        serve.AUTH_SESSIONS.clear()
        cls.tmp.cleanup()

    def setUp(self):
        serve.AUTH_SESSIONS.clear()
        with serve.SAVE_LOCK:
            for account in self.ACCOUNTS:
                serve.db_store_save(account, save_for(account, gold=0))
                for table in ("guild_members", "guild_applies", "guild_chat", "guilds",
                              "guild_bt_guild", "guild_bt_slot", "guild_bt_record",
                              "guild_boss_stage", "guild_boss_damage", "guild_boss_token"):
                    serve.DB_CONN.execute("DELETE FROM %s" % table)
            serve.DB_CONN.commit()

    # --- helpers -----------------------------------------------------------
    def post(self, group, act, account=None, **fields):
        fields["act"] = act
        fields.setdefault("user_level", 40)
        fields.setdefault("profile_num", 101)
        fields.setdefault("HOST_ID", account or "")
        fields.setdefault("language", "EN")
        form = urlencode({"crypt": 0, "url": "/Guild/update_guild_%s.php" % group,
                          "json_obj": json.dumps(fields, ensure_ascii=False)})
        cookie = ("dol_session=" + serve.issue_auth_session(account)) if account else None
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=10)
        try:
            conn.request("POST", "/ELDORADO_WEB/Guild/update_guild_%s.php" % group,
                         body=form,
                         headers={"Content-Type": "application/x-www-form-urlencoded",
                                  **({"Cookie": cookie} if cookie else {})})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"__raw__": raw}
        finally:
            conn.close()

    def create(self, account, name):
        st, r = self.post("inter", "insert_new_guild", account, USER_NAME=account,
                          guild_name=name, guild_type="free",
                          guild_flag=json.dumps({"flagImg": "flag_green3.png",
                                                 "symbolImg": "flagsymbol7.png"}))
        self.assertEqual("ok", r.get("result"), (st, r))

    def two_guilds(self):
        """Guild 'A' co g_bt_a (master) + g_bt_b; guild 'B' co g_bt_c + g_bt_d."""
        self.create("g_bt_a", "A")
        self.create("g_bt_c", "B")
        for acc, guild in (("g_bt_b", "A"), ("g_bt_d", "B")):
            st, r = self.post("inter", "join_open_guild", acc, USER_NAME=acc, guild_name=guild)
            self.assertEqual("ok", r.get("result"), (st, r))

    def set_defence(self, account):
        st, r = self.post("battle", "update_deck_defence", account, USER_NAME=account,
                          user_info="10,10,10,10,10,10", defence_deck=self.DECK)
        self.assertEqual(200, st, r)
        self.assertEqual("ok", r.get("result"), r)
        return r

    def rows(self, sql, args=()):
        cur = serve.DB_CONN.cursor()
        cur.row_factory = __import__("sqlite3").Row
        try:
            return [dict(x) for x in cur.execute(sql, args).fetchall()]
        finally:
            cur.close()

    # --- route -------------------------------------------------------------
    def test_both_new_endpoints_reach_backend(self):
        self.create("g_bt_a", "RouteGuild")
        st, r = self.post("battle", "get_battle_normal", "g_bt_a")
        self.assertEqual(200, st, r)
        self.assertEqual("ok", r["result"], r)
        st, r = self.post("boss", "get_lobby", "g_bt_a")
        self.assertEqual(200, st, r)
        self.assertEqual("ok", r["result"], r)

    def test_unregistered_act_is_rejected_not_silent_ok(self):
        self.create("g_bt_a", "RouteGuild")
        st, r = self.post("battle", "get_battle_bogus", "g_bt_a")
        self.assertEqual("no", r["result"], r)

    # --- Guild War ---------------------------------------------------------
    def test_battle_normal_has_every_field_client_reads(self):
        self.create("g_bt_a", "A")
        st, r = self.post("battle", "get_battle_normal", "g_bt_a")
        # Client: json_secure.set("guild_battle_normal", n) — tra thang, khong boc.
        for key in ("period", "remain_seconds", "rank_info", "other_guild_name",
                    "other_guild_flag", "other_guild_deck_tot", "other_guild_deck_clear",
                    "my_guild_defence_deck_num", "deck_defence", "deck_attack1",
                    "deck_attack2", "deck_attack3", "other_guild_name",
                    "clear_guild_num_this_week", "clear_guild_list", "season_data"):
            self.assertIn(key, r, sorted(r))
        self.assertEqual("A", guild_backend._member(serve.DB_CONN, "g_bt_a")["guild_name"])
        # other_guild_flag la JSON string hoac rong, khong phai object.
        self.assertIn(r["other_guild_flag"], ("", "{}"), r["other_guild_flag"])
        # clear_guild_list 1-based (client for tu 1).
        self.assertIsNone(r["clear_guild_list"][0], r["clear_guild_list"])

    def test_defence_deck_saved_then_readable_by_matched_guild(self):
        self.two_guilds()
        self.set_defence("g_bt_a")
        st, r = self.post("battle", "next_guild_matching", "g_bt_c", USER_NAME="g_bt_c")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("A", r["guild_name"], r)
        st, r = self.post("battle", "get_defence_deck30", "g_bt_c", USER_NAME="g_bt_c",
                          other_guild_name="A")
        self.assertEqual("ok", r["result"], r)
        # Client doc deck30["1"] - object khoa chuoi, khong phai mang.
        self.assertIsNone(r["deck30"].get("0"), r["deck30"])
        self.assertEqual(self.DECK, r["deck30"]["1"]["DECK_DEFENCE"], r["deck30"])
        self.assertEqual("g_bt_a", r["deck30"]["1"]["HOST_ID"], r["deck30"])

    def test_cannot_read_decks_of_guild_never_matched(self):
        self.two_guilds()
        self.set_defence("g_bt_a")
        st, r = self.post("battle", "get_defence_deck30", "g_bt_c", USER_NAME="g_bt_c",
                          other_guild_name="A")
        self.assertEqual("no", r["result"], r)
        self.assertEqual({}, r["deck30"])

    def test_matching_never_returns_own_guild(self):
        self.two_guilds()
        st, r = self.post("battle", "next_guild_matching", "g_bt_a", USER_NAME="g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertNotEqual("A", r["guild_name"], r)
        # Chi co 1 guild doi phuong -> lan 2 phai bao het, khong tra ten rong.
        st, r = self.post("battle", "next_guild_matching", "g_bt_b", USER_NAME="g_bt_b")
        self.assertEqual(guild_backend.GUILD_BT_NO_MATCH, r["guild_name"], r)

    def test_cloud30_costs_cloud_piece_once_and_persists(self):
        self.two_guilds()
        self.set_defence("g_bt_a")
        st, r = self.post("battle", "next_guild_matching_cloud30", "g_bt_c",
                          USER_NAME="g_bt_c")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("A", r["guild_name"], r)
        st, r = self.post("battle", "next_guild_matching_cloud30", "g_bt_c",
                          USER_NAME="g_bt_c")
        self.assertEqual("ok", r["result"], r)
        saved = serve.db_load_save("g_bt_c")
        self.assertEqual(1000 - 2 * guild_backend.GUILD_BT_CLOUD30_PRICE,
                         int(saved["cloud_piece"]), saved)

    def test_result_retry_does_not_double_score(self):
        self.two_guilds()
        self.set_defence("g_bt_a")
        self.post("battle", "next_guild_matching", "g_bt_c", USER_NAME="g_bt_c")
        st, r = self.post("battle", "insert_guild_battle_start", "g_bt_c", USER_NAME="g_bt_c",
                          other_guild_name="A", other_guild_slot_no=1,
                          other_host_id="g_bt_a", other_username="g_bt_a")
        self.assertEqual("ok", r["result"], r)
        for _ in range(2):
            st, r = self.post("battle", "update_guild_battle_result", "g_bt_c",
                              USER_NAME="g_bt_c", other_guild_name="A",
                              other_guild_slot_no=1, other_host_id="g_bt_a",
                              attack_deck_index=1, battle_result=guild_backend.GUILD_BT_WIN)
            # Client switch tren result.result -> phai long.
            self.assertEqual("ok", r["result"]["result"], r)
        score = self.rows("SELECT score FROM guild_bt_guild "
                          "WHERE guild_name='B'")[0]["score"]
        self.assertEqual(guild_backend.GUILD_BT_WIN_SCORE, score, score)

    def test_cannot_attack_slot_that_has_no_defence_deck(self):
        self.two_guilds()
        self.post("battle", "next_guild_matching", "g_bt_c", USER_NAME="g_bt_c")
        st, r = self.post("battle", "insert_guild_battle_start", "g_bt_c", USER_NAME="g_bt_c",
                          other_guild_name="A", other_guild_slot_no=7,
                          other_host_id="", other_username="")
        self.assertEqual("no", r["result"], r)
        self.assertEqual([], self.rows("SELECT * FROM guild_bt_slot WHERE slot=7"))

    def test_defence_deck_locked_once_slot_was_cleared(self):
        self.two_guilds()
        self.set_defence("g_bt_a")
        self.post("battle", "next_guild_matching", "g_bt_c", USER_NAME="g_bt_c")
        self.post("battle", "insert_guild_battle_start", "g_bt_c", USER_NAME="g_bt_c",
                  other_guild_name="A", other_guild_slot_no=1, other_host_id="g_bt_a",
                  other_username="g_bt_a")
        self.post("battle", "update_guild_battle_result", "g_bt_c", USER_NAME="g_bt_c",
                  other_guild_name="A", other_guild_slot_no=1, other_host_id="g_bt_a",
                  attack_deck_index=1, battle_result=guild_backend.GUILD_BT_LOSE)
        st, r = self.post("battle", "update_deck_defence", "g_bt_a", USER_NAME="g_bt_a",
                          user_info="10,10,10,10,10,10", defence_deck="9,9,9")
        self.assertEqual("no", r["result"], r)
        self.assertEqual(self.DECK, self.rows("SELECT deck FROM guild_bt_slot "
                                              "WHERE guild_name='A' AND slot=1")[0]["deck"])

    def test_rank_all_tabs_are_1_based_and_use_defeated_num(self):
        # Guild A co 2 o phong thu (g_bt_a master = slot 1, g_bt_b = slot 2).
        self.two_guilds()
        self.set_defence("g_bt_a")
        self.set_defence("g_bt_b")
        self.post("battle", "next_guild_matching", "g_bt_c", USER_NAME="g_bt_c")
        # g_bt_c thang o slot 1 -> attack_success cho B 1 diem.
        self.post("battle", "insert_guild_battle_start", "g_bt_c", USER_NAME="g_bt_c",
                  other_guild_name="A", other_guild_slot_no=1, other_host_id="g_bt_a",
                  other_username="g_bt_a")
        self.post("battle", "update_guild_battle_result", "g_bt_c", USER_NAME="g_bt_c",
                  other_guild_name="A", other_guild_slot_no=1, other_host_id="g_bt_a",
                  attack_deck_index=1, battle_result=guild_backend.GUILD_BT_WIN)
        # g_bt_d thua o slot 2 -> defence_fail cho A 1 diem.
        self.post("battle", "next_guild_matching", "g_bt_d", USER_NAME="g_bt_d")
        self.post("battle", "insert_guild_battle_start", "g_bt_d", USER_NAME="g_bt_d",
                  other_guild_name="A", other_guild_slot_no=2, other_host_id="g_bt_b",
                  other_username="g_bt_b")
        self.post("battle", "update_guild_battle_result", "g_bt_d", USER_NAME="g_bt_d",
                  other_guild_name="A", other_guild_slot_no=2, other_host_id="g_bt_b",
                  attack_deck_index=1, battle_result=guild_backend.GUILD_BT_LOSE)
        st, r = self.post("battle", "get_guild_battle_rank_all", "g_bt_a", USER_NAME="g_bt_a")
        self.assertEqual("ok", r["result"], r)
        data = r["data"]
        for tab in ("week_rank", "attack_success", "defence_fail"):
            rows = data[tab]
            self.assertIsNone(rows[0], tab)          # client for tu 1
            self.assertEqual(1, rows[1]["order"], tab)
            for row in rows[1:]:
                for key in ("order", "guild_name", "score", "defeated_num", "flag_info"):
                    self.assertIn(key, row, (tab, row))
                self.assertIn("symbolImg", row["flag_info"], (tab, row))
        # attack_success dem theo MY guild (dung ra danh) -> B 1 thang.
        self.assertEqual("B", data["attack_success"][1]["guild_name"], data["attack_success"])
        self.assertEqual(1, data["attack_success"][1]["defeated_num"], data["attack_success"])
        # defence_fail dem o phong thu bi that -> A 1 o thua.
        self.assertEqual("A", data["defence_fail"][1]["guild_name"], data["defence_fail"])
        self.assertEqual(1, data["defence_fail"][1]["defeated_num"], data["defence_fail"])
        # week_rank xep theo diem tuan.
        self.assertEqual("B", data["week_rank"][1]["guild_name"], data["week_rank"])

    def test_member_history_is_1_based(self):
        self.two_guilds()
        st, r = self.post("battle", "get_guild_battle_member_history", "g_bt_a",
                          USER_NAME="g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertIsNone(r["data"][0], r["data"])

    # --- Guild Boss --------------------------------------------------------
    def test_boss_lobby_lists_all_stages(self):
        self.create("g_bt_a", "A")
        st, r = self.post("boss", "get_lobby", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(guild_backend.GUILD_BOSS_STAGE_NUM, len(r["stages"]), r["stages"])
        self.assertEqual(1, r["active_stage"])
        self.assertEqual(guild_backend.GUILD_BOSS_STAGE_HP[0], r["stages"][0]["max_hp"])
        self.assertEqual(guild_backend.GUILD_BOSS_FREE_PER_DAY, r["free_remain"])

    def test_boss_help_is_0_based(self):
        self.create("g_bt_a", "A")
        st, r = self.post("boss", "get_help", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(guild_backend.GUILD_BOSS_STAGE_NUM, len(r["data"]), r["data"])
        self.assertEqual(1, r["data"][0]["stage"], r["data"][0])

    def test_boss_free_entry_once_then_requires_gold(self):
        self.create("g_bt_a", "A")
        st, r = self.post("boss", "check_can_enter", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("free", r["used_type"], r)
        self.assertTrue(r["battle_token"], r)
        # Het luot mien phi, account test co 0 vang -> phai bao khong du.
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        self.assertEqual("gb-not-enough-gold", r["result"], r)
        # Nap vang ma GIU nguyen bo dem gb_free_* (replace ca save se xoa no).
        with serve.SAVE_LOCK:
            saved = dict(serve.db_load_save("g_bt_a"))
            d1 = saved["DATA1"].split(",")
            d1[1] = str(guild_backend.GUILD_BOSS_PAID_GOLD)
            saved["DATA1"] = ",".join(d1)
            serve.db_store_save("g_bt_a", saved)
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("paid", r["used_type"], r)
        self.assertEqual(0, int(serve.db_load_save("g_bt_a")["DATA1"].split(",")[1]))

    def test_boss_damage_scaled_capped_and_token_single_use(self):
        self.create("g_bt_a", "A")
        st, r = self.post("inter", "join_open_guild", "g_bt_b", USER_NAME="g_bt_b",
                          guild_name="A")
        self.assertEqual("ok", r.get("result"), (st, r))
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        token = r["battle_token"]
        # damage_mult 0.001 (ban release) -> 5000 * 0.001 = 5.
        st, r = self.post("boss", "report_damage", "g_bt_a", damage_raw=5000,
                          damage_mult=0.001, user_chars="u1", battle_token=token)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(5, r["applied_raw"], r)
        self.assertEqual(5, r["lobby"]["my_total_damage"], r)
        self.assertEqual(5, r["lobby"]["ranking"][0]["total_damage"], r)
        # Retry cung token -> khong cong them.
        st, r = self.post("boss", "report_damage", "g_bt_a", damage_raw=5000,
                          damage_mult=0.001, user_chars="u1", battle_token=token)
        self.assertEqual("gb-already-cleared", r["result"], r)
        self.assertEqual(0, r["applied_raw"], r)
        # Token cua nguoi khac trong cung guild khong dung duoc.
        st, r = self.post("boss", "report_damage", "g_bt_b", damage_raw=5000,
                          damage_mult=0.001, battle_token=token)
        self.assertEqual("gb-bad-token", r["result"], r)

    def test_boss_damage_never_exceeds_stage_cap(self):
        self.create("g_bt_a", "A")
        cap = guild_backend.GUILD_BOSS_STAGE_HP[0] * guild_backend.GUILD_BOSS_STAGE_CAP[0] // 100
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        self.assertEqual("ok", r["result"], r)
        st, r = self.post("boss", "report_damage", "g_bt_a", damage_raw=10 ** 9,
                          damage_mult=1.0, battle_token=r["battle_token"])
        self.assertEqual(cap, r["applied_raw"], r)
        total = self.rows("SELECT total_damage FROM guild_boss_damage "
                          "WHERE guild_name='A'")[0]["total_damage"]
        self.assertEqual(cap, total, total)

    def test_boss_stage_advances_when_hp_cleared(self):
        self.create("g_bt_a", "A")
        st, r = self.post("boss", "enter_battle", "g_bt_a")
        st, r = self.post("boss", "report_damage", "g_bt_a", damage_raw=10 ** 9,
                          damage_mult=1.0, battle_token=r["battle_token"])
        self.assertEqual(2, r["lobby"]["active_stage"], r["lobby"]["active_stage"])
        st, r = self.post("boss", "check_can_enter", "g_bt_a")
        self.assertEqual("ok", r["result"], r)

    def test_non_member_cannot_read_boss(self):
        st, r = self.post("boss", "get_lobby", "g_bt_b")
        self.assertEqual("no", r["result"], r)

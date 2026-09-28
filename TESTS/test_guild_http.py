import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import serve


def save_for(account, ruby=50000):
    d1 = ["0"] * 21
    d1[2] = str(ruby)
    return {"USER_NAME": account, "DATA1": ",".join(d1),
            "cloud_piece": "1000"}


class GuildHTTPTests(unittest.TestCase):
    """Kiem tra phan gui HTTP that cua serve.py: route, phan quyen theo session,
    ghi duoc xuong DB, va chay dung khi nhieu request dung luc.

    Test_guild.py goi guild_dispatch truc tiep nen bo qua duong dan handler
    (route sai bien, hay bien mat khi Handler bat NameError) — bo suyet can
    chay qua HTTP that."""

    ACCOUNTS = ("g_http_a", "g_http_b", "g_http_c", "g_http_d")

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_guild_http_")
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        # serve.init_db goi init_guild_db(DB_CONN, SAVE_LOCK) ben trong.
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
                serve.db_store_save(account, save_for(account))
                for table in ("guild_members", "guild_applies", "guild_chat",
                              "guilds"):
                    serve.DB_CONN.execute("DELETE FROM %s" % table)
            serve.DB_CONN.commit()

    def post(self, group, act, account=None, **fields):
        """POST đúng wire format của client: PHPAjax gửi
        {crypt, url, send_data:{json_obj}}, json_obj là object (ENABLE_CRYPT)
        hoặc chuỗi JSON. `account` -> tạo cookie session; để trống để test
        request không đăng nhập."""
        fields["act"] = act
        # client luon kem 4 truong nay (xem ServerConnection.update_guild)
        fields.setdefault("user_level", 40)
        fields.setdefault("profile_num", 101)
        fields.setdefault("HOST_ID", account or "")
        fields.setdefault("language", "EN")
        payload = json.dumps(fields, ensure_ascii=False)
        form = urlencode({"crypt": 0, "url": "/Guild/update_guild_%s.php" % group,
                         "json_obj": payload})
        cookie = ("dol_session=" + serve.issue_auth_session(account)) if account else None
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=10)
        try:
            conn.request(
                "POST", "/ELDORADO_WEB/Guild/update_guild_%s.php" % group,
                body=form,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         **({"Cookie": cookie} if cookie else {})})
            response = conn.getresponse()
            raw = response.read().decode("utf-8")
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, {"__raw__": raw}
        finally:
            conn.close()

    def create(self, account, name, gtype="free"):
        return self.post("inter", "insert_new_guild", account, USER_NAME=account,
                         guild_name=name, guild_type=gtype,
                         guild_flag=json.dumps({"flagImg": "flag_green3.png",
                                                "symbolImg": "flagsymbol7.png"}))

    def rows(self, sql, args=()):
        cur = serve.DB_CONN.cursor()
        cur.row_factory = __import__("sqlite3").Row
        try:
            return [dict(r) for r in cur.execute(sql, args).fetchall()]
        finally:
            cur.close()

    # --- route -------------------------------------------------------------
    def test_both_routes_reach_guild_backend(self):
        st, r = self.create("g_http_a", "RouteGuild")
        self.assertEqual(200, st, r)
        self.assertNotIn("__raw__", r, "route tra ve text khong phai JSON: %r" % r)
        self.assertEqual("ok", r["result"], r)
        st, r = self.post("main", "get_guild_normal", "g_http_a")
        self.assertEqual(200, st)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("RouteGuild", r["data"]["guild_name"])

    def test_route_uses_session_uid_not_body_user_name(self):
        st, r = self.post("inter", "insert_new_guild", "g_http_a",
                          USER_NAME="g_http_b", guild_name="SpoofGuild",
                          guild_type="free")
        self.assertEqual("ok", r["result"], r)
        got = self.rows("SELECT master_id FROM guilds WHERE guild_name='SpoofGuild'")
        self.assertEqual([{"master_id": "g_http_a"}], got,
                         "server phai lay uid tu session, khong tin USER_NAME body")

    def test_creator_gets_master_on_every_path_client_reads(self):
        """Client quyet dinh quyen chu bang `guild_data.guild_position` doc tu
        json_secure. moi response ghi de guild_data phai tra MASTER cho nguoi
        tao, neu khong thi man hinh guild mo ra nhung khong co nut chu."""
        st, r = self.create("g_http_a", "MasterGuild")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("MASTER", r["data"]["guild_position"], r)

        st, r = self.post("main", "get_guild_normal", "g_http_a")
        self.assertEqual("MASTER", r["data"]["guild_position"], r)

        st, r = self.post("inter", "check_guild_member", "g_http_a")
        self.assertEqual("has_guild", r["result"], r)
        self.assertEqual("MASTER", r["data"]["guild_position"], r)

        st, r = self.post("main", "update_guild_mission", "g_http_a",
                          guild_mission_index=0, guild_mission_act="attendance")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("MASTER", r["data"]["guild_data"]["guild_position"], r)

    def test_non_member_never_sees_master_position(self):
        self.create("g_http_a", "MasterGuild2")
        st, r = self.post("inter", "join_open_guild", "g_http_b",
                          USER_NAME="g_http_b", guild_name="MasterGuild2")
        self.assertEqual("ok", r["result"], r)
        self.assertNotEqual("MASTER", r["data"]["guild_position"], r)

    def test_wire_identity_splits_two_windows_sharing_one_cookie(self):
        """Mot profile trinh duyet chi co mot cookie, nen hai cua so game da
        dang nhp hai tai khoan se tranh session. --wire-identity cho phep moi
        cua so chay bang tai khoan trong HOST_ID cua no."""
        try:
            serve.WIRE_IDENTITY = True
            # Ca hai cua so gui cung mot cookie (session cua g_http_a) nhung
            # HOST_ID khac nhau, dung tinh huong browser that.
            st, r = self.create("g_http_a", "WindowGuild")
            self.assertEqual("ok", r["result"], r)
            self.assertEqual("MASTER", r["data"]["guild_position"], r)
            st, r = self.post("inter", "join_approve_guild", "g_http_a",
                              USER_NAME="g_http_b", HOST_ID="g_http_b",
                              guild_name="WindowGuild")
            self.assertEqual("ok", r["result"], r)
            got = self.rows("SELECT user_id FROM guild_applies "
                            "WHERE guild_name='WindowGuild'")
            self.assertEqual([{"user_id": "g_http_b"}], got,
                             "ho so xin gia nhap phai mang ten tai khoan cua "
                             "cua so gui, khong phai tai khoan trong cookie")
        finally:
            serve.WIRE_IDENTITY = False

    def test_wire_identity_falls_back_to_session_for_unknown_wire_id(self):
        """get_cur_run_count gui HOST_ID=ELDORADO_OFFLINE_0001, khong phai tai
        khoan -> phai lui ve session chu khong duoc truc tiep."""
        try:
            serve.WIRE_IDENTITY = True
            st, r = self.create("g_http_a", "FbGuild")
            self.assertEqual("ok", r["result"], r)
            st, r = self.post("main", "get_guild_normal", "g_http_a",
                              HOST_ID="ELDORADO_OFFLINE_0001")
            self.assertEqual("FbGuild", r["data"]["guild_name"], r)
        finally:
            serve.WIRE_IDENTITY = False

    def test_anonymous_request_does_not_leak_guild_data(self):
        st, r = self.post("inter", "get_guild_normal")
        self.assertEqual(401, st, r)
        self.assertNotIn("ok", r)

    # --- ghi xuong DB ------------------------------------------------------
    def test_create_survives_new_request(self):
        self.create("g_http_a", "PersistGuild")
        st, r = self.post("inter", "get_guild_normal", "g_http_b")
        self.assertEqual("ok", r["result"], r)
        self.assertEqual("no_guild", r["data"])
        st, r = self.post("inter", "get_guild_list", "g_http_b")
        self.assertEqual("ok", r["result"], r)
        # client: json_secure.set("guild_list", n.data) roi lap t.length ->
        # `data` la mang truc tiep, khong phai object boc.
        self.assertEqual(["PersistGuild"], [g["guild_name"] for g in r["data"]])

    def test_member_slot_survives_new_request(self):
        self.create("g_http_a", "SlotGuild")
        self.assertEqual("ok", self.post("main", "update_guild_member", "g_http_a",
                                        USER_NAME="g_http_a", guild_name="SlotGuild",
                                        act_detail="guild_add_max_member")[1]["result"])
        st, r = self.post("inter", "get_guild_normal", "g_http_a")
        self.assertEqual(21, r["data"]["guild_max_member"], r)
        self.assertEqual(21, self.rows(
            "SELECT max_member FROM guilds WHERE guild_name='SlotGuild'")[0]["max_member"])

    # --- chay dong thoi ---------------------------------------------------
    def test_concurrent_join_respects_cap(self):
        self.create("g_http_a", "CapGuild")
        with serve.SAVE_LOCK:
            serve.DB_CONN.execute("UPDATE guilds SET max_member=2 WHERE guild_name='CapGuild'")
            serve.DB_CONN.commit()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(self.post, "inter", "join_open_guild", acc,
                                   USER_NAME=acc, guild_name="CapGuild")
                       for acc in ("g_http_b", "g_http_c", "g_http_d")]
            results = [fut.result()[1].get("result") for fut in futures]
        self.assertEqual(1, results.count("ok"), results)
        self.assertEqual(2, results.count("full"), results)
        self.assertEqual(2, self.rows(
            "SELECT user_id FROM guild_members WHERE guild_name='CapGuild'").__len__())

    def test_concurrent_create_same_name_only_one_wins(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.create, acc, "RaceName")
                       for acc in self.ACCOUNTS]
            results = [fut.result()[1].get("result") for fut in futures]
        self.assertEqual(1, results.count("ok"), results)
        self.assertEqual(3, results.count("duplication"), results)
        self.assertEqual(1, len(self.rows(
            "SELECT guild_name FROM guilds WHERE guild_name='RaceName'")))

    def test_concurrent_double_join_same_player(self):
        # Client gioi han 500ms/act nen that ra khong xay ra, nhung request trung
        # lap la do loi mang. Phai idempotent: chi tao duy nhat 1 dong thanh vien.
        self.create("g_http_a", "DblGuild")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.post, "inter", "join_open_guild", "g_http_b",
                                   USER_NAME="g_http_b", guild_name="DblGuild")
                       for _ in range(4)]
            results = [fut.result()[1].get("result") for fut in futures]
        self.assertEqual(1, results.count("ok"), results)
        self.assertEqual(3, results.count("duplication"), results)
        self.assertEqual(1, len(self.rows(
            "SELECT user_id FROM guild_members WHERE guild_name='DblGuild' "
            "AND user_id='g_http_b'")))


if __name__ == "__main__":
    unittest.main()

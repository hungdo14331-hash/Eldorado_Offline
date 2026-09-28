import http.client
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import farm_core
import serve


class FarmHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_farm_http_")
        cls.db_path = Path(cls.tmp.name) / "farm.db"
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        serve.init_db(cls.db_path)
        for account in ("farm_a", "farm_b"):
            serve.add_account(account, "test-only-password")
            serve.db_store_save(account, {"USER_NAME": account, "mails": []})
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
        for account in ("farm_a", "farm_b"):
            serve.db_store_save(account, {"USER_NAME": account, "mails": []})
        self.cookie_a = "dol_session=" + serve.issue_auth_session("farm_a")
        self.cookie_b = "dol_session=" + serve.issue_auth_session("farm_b")

    def request_path(self, path, fields=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        conn.request("POST", path, body=urlencode(fields or {}),
                     headers={"Content-Type": "application/x-www-form-urlencoded",
                              **({"Cookie": cookie} if cookie else {})})
        response = conn.getresponse()
        result = response.status, json.loads(response.read().decode("utf-8"))
        conn.close()
        return result

    def request(self, endpoint, fields=None, cookie=None):
        return self.request_path("/ELDORADO_WEB/garden/" + endpoint + ".php",
                                 fields, cookie)

    def saved(self, account):
        return serve.db_load_save(account)

    def test_state_buy_retry_and_account_isolation(self):
        status, initial = self.request("state", cookie=self.cookie_a)
        self.assertEqual(200, status)
        self.assertIn("farm", initial, "farm state endpoint is missing")
        self.assertEqual(250, initial["farm"]["coins"])

        fields = {"ACTION_ID": "buy-seed-0001", "ACTION": "buy_seed", "CROP": "carrot",
                  "QUANTITY": "2", "PRICE": "0", "HOST_ID": "farm_b"}
        status, result = self.request("action", fields, self.cookie_a)
        self.assertEqual(200, status)
        self.assertEqual("SUCCESS", result["STATE"])
        self.assertEqual(230, result["farm"]["coins"])
        self.assertEqual(5, result["farm"]["seeds"]["carrot"])
        self.assertEqual((status, result), self.request("action", fields, self.cookie_a))
        altered = dict(fields, QUANTITY="3")
        self.assertEqual("ERROR", self.request("action", altered, self.cookie_a)[1]["STATE"])
        self.assertEqual(250, self.request("state", cookie=self.cookie_b)[1]["farm"]["coins"])
        self.assertEqual(3, self.saved("farm_b")["ruby_garden_v1"]["seeds"]["carrot"])
        self.assertEqual(401, self.request("state")[0])

        with serve.SAVE_LOCK:
            serve.DB_CONN.close()
            serve.DB_CONN = None
            serve.DB_FILE = None
            serve.init_db(self.db_path)
        self.assertEqual(230, self.request("state", cookie=self.cookie_a)[1]["farm"]["coins"])

    def test_legacy_farm_receives_the_starter_pack_once(self):
        legacy = farm_core.new_farm(day="20260925")
        legacy.pop("starter_pack_version", None)
        legacy["coins"] = 100
        legacy["gems"] = {"diamond": 0, "emerald": 0}
        legacy["items"] = {"fertilizer": 0, "speed_boost": 0}
        legacy["seeds"] = {crop: 0 for crop in farm_core.CROPS}
        save = self.saved("farm_a")
        save["ruby_garden_v1"] = legacy
        serve.db_store_save("farm_a", save)

        first = self.request("state", cookie=self.cookie_a)[1]["farm"]
        second = self.request("state", cookie=self.cookie_a)[1]["farm"]
        self.assertEqual(250, first["coins"])
        self.assertEqual({"diamond": 2, "emerald": 3}, first["gems"])
        self.assertEqual(3, first["seeds"]["carrot"])
        self.assertEqual(first, second)
        self.assertEqual(1, self.saved("farm_a")["ruby_garden_v1"]["starter_pack_version"])

    def test_character_purchase_mail_and_same_id_concurrent_retry(self):
        save = self.saved("farm_a")
        save["ruby_garden_v1"] = farm_core.new_farm(day="20260925")
        save["ruby_garden_v1"]["coins"] = 500
        serve.db_store_save("farm_a", save)
        fields = {"ACTION_ID": "char-buy-0001", "ACTION": "buy_character", "CHARACTER_ID": "1"}
        with patch("serve.time.strftime", return_value="20260925"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: self.request("action", fields, self.cookie_a), range(2)))
        self.assertEqual(replies[0], replies[1])
        self.assertIn("STATE", replies[0][1], "farm action endpoint is missing")
        self.assertEqual("SUCCESS", replies[0][1]["STATE"])
        saved = self.saved("farm_a")
        self.assertEqual(150, saved["ruby_garden_v1"]["coins"])
        self.assertEqual(1, len(saved["mails"]))
        self.assertEqual("CHAR", saved["mails"][0]["what"])
        self.assertEqual("1", saved["mails"][0]["what_value"])
        self.assertEqual([], self.saved("farm_b")["mails"])

    def test_failed_persist_leaves_coins_and_mail_unchanged(self):
        save = self.saved("farm_a")
        save["ruby_garden_v1"] = farm_core.new_farm(day="20260925")
        save["ruby_garden_v1"]["coins"] = 500
        serve.db_store_save("farm_a", save)
        with patch("serve._farm_persist", side_effect=OSError("simulated write failure"), create=True):
            status, body = self.request("action", {"ACTION_ID": "char-fail-0001",
                "ACTION": "buy_character", "CHARACTER_ID": "1"}, self.cookie_a)
        self.assertEqual(500, status)
        self.assertEqual("ERROR", body["STATE"])
        after = self.saved("farm_a")
        self.assertEqual(500, after["ruby_garden_v1"]["coins"])
        self.assertEqual([], after["mails"])


    # Ngay co ruby trong CHECKIN_REWARDS va so ruby tra ve.
    # Khoa bang gia tri de bang quay lui khong the bi sua xoang.
    CHECKIN_RUBY = {4: 100, 9: 150, 15: 150, 20: 250,
                    27: 150, 30: 400, 31: 400}
    # Tong vang phai dung 3.000.000/thang.
    CHECKIN_GOLD = {1: 150000, 6: 300000, 13: 500000,
                    21: 750000, 29: 1300000}

    def test_checkin_ruby_schedule(self):
        for day, amt in sorted(self.CHECKIN_RUBY.items()):
            self.assertEqual(("RUBY", amt), serve.CHECKIN_REWARDS[day - 1],
                             "ngay %d phai tra ruby %d" % (day, amt))
        self.assertEqual(1600, sum(self.CHECKIN_RUBY.values()))
        # Nhung ngay con lai khong duoc tra ruby.
        for day, reward in enumerate(serve.CHECKIN_REWARDS, 1):
            if day in self.CHECKIN_RUBY:
                continue
            self.assertNotEqual("RUBY", reward[0],
                                "ngay %d khong nen co ruby" % day)

    def test_checkin_gold_schedule(self):
        for day, amt in sorted(self.CHECKIN_GOLD.items()):
            self.assertEqual(("GOLD", amt), serve.CHECKIN_REWARDS[day - 1],
                             "ngay %d phai tra gold %d" % (day, amt))
        # Tong tinh tu chinh bang chuoi, khong phai tu dict: bat bien "3 trieu".
        self.assertEqual(3000000,
                         sum(a for t, a in serve.CHECKIN_REWARDS if t == "GOLD"),
                         "tong vang/thang phai dung 3.000.000")
        for day, reward in enumerate(serve.CHECKIN_REWARDS, 1):
            if day in self.CHECKIN_GOLD:
                continue
            self.assertNotEqual("GOLD", reward[0],
                                "ngay %d khong nen co vang" % day)

    def test_checkin_info_serves_the_same_table_the_client_draws(self):
        status, info = self.request_path("/wallet/checkin.php",
                                         {"ACTION": "info"}, self.cookie_a)
        self.assertEqual(200, status)
        self.assertEqual("SUCCESS", info["STATE"])
        # Bang gui len phai dung bang server cap: het bang "xem lich qua" se
        # hien sai so so voi thu nhan thuc te.
        self.assertEqual([list(r) for r in serve.CHECKIN_REWARDS], info["rewards"])

    def test_checkin_claim_credits_exact_ruby_once_per_day(self):
        fixed = time.struct_time((2026, 9, 4, 12, 0, 0, 4, 247, -1))
        with patch("serve.time.localtime", return_value=fixed):
            status, first = self.request_path("/wallet/checkin.php",
                                              {"ACTION": "claim"}, self.cookie_a)
        self.assertEqual(200, status)
        self.assertEqual("SUCCESS", first["STATE"])
        self.assertEqual("RUBY", first["claimed"])
        self.assertEqual(100, first["amount"])
        self.assertEqual(100, int(self.saved("farm_a")["DATA1"].split(",")[2]))

        # Bam lai trong cung ngay: khong duoc cong them lan nua.
        with patch("serve.time.localtime", return_value=fixed):
            status, again = self.request_path("/wallet/checkin.php",
                                              {"ACTION": "claim"}, self.cookie_a)
        self.assertEqual(200, status)
        self.assertEqual("ERROR", again["STATE"])
        self.assertEqual(100, int(self.saved("farm_a")["DATA1"].split(",")[2]))


if __name__ == "__main__":
    unittest.main()

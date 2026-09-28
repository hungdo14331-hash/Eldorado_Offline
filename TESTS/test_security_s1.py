import http.client
import io
import json
import logging
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class SecurityS1HTTPTests(unittest.TestCase):
    ACCOUNT_A = "S1_ACCOUNT_A"
    ACCOUNT_B = "S1_ACCOUNT_B"
    PASSWORD_A = "S1-password-A"
    PASSWORD_B = "S1-password-B"
    ADMIN_KEY = "S1-test-admin-key-not-production"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_security_s1_")
        root = Path(cls.tmp.name)
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.UNIQ_ID = "S1_DEFAULT"
        serve.SAVE_FILE = root / "unused_save.json"
        serve.CAP_DIR = root / "capture"
        serve.CAP_DIR.mkdir()
        serve.ADMIN_KEY = cls.ADMIN_KEY
        serve.init_db(root / "security_s1.db")
        serve.add_account(cls.ACCOUNT_A, cls.PASSWORD_A)
        serve.add_account(cls.ACCOUNT_B, cls.PASSWORD_B)

        cls.log_output = io.StringIO()
        cls.log_handler = logging.StreamHandler(cls.log_output)
        serve.LOG.handlers.clear()
        serve.LOG.addHandler(cls.log_handler)
        serve.LOG.setLevel(logging.INFO)

        cls.server = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        serve.SRV_PORT = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        serve.LOG.removeHandler(cls.log_handler)
        if serve.DB_CONN is not None:
            serve.DB_CONN.close()
        serve.DB_CONN = None
        serve.DB_FILE = None
        serve.REQUIRE_LOGIN = False
        cls.tmp.cleanup()

    def setUp(self):
        sessions = getattr(serve, "AUTH_SESSIONS", None)
        if sessions is not None:
            sessions.clear()
        self.log_output.seek(0)
        self.log_output.truncate(0)
        self._store_fixture(self.ACCOUNT_A, "A_MARKER", gold=1000, ruby=111, bp=10, cloud=100)
        self._store_fixture(self.ACCOUNT_B, "B_MARKER", gold=2000, ruby=222, bp=20, cloud=200)

    def _store_fixture(self, account, marker, *, gold, ruby, bp, cloud):
        data1 = [marker, str(gold), str(ruby)] + ["0"] * 18
        payload = {
            "USER_NAME": marker,
            "DATA1": ",".join(data1),
            "DATA2": "",
            "DATA3": "",
            "ETC": "",
            "bp": str(bp),
            "cloud_piece": str(cloud),
            "celestial_essence": "0",
        }
        with serve.SAVE_LOCK:
            serve.DB_CONN.execute(
                "INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                (account, json.dumps(payload)),
            )
            serve.DB_CONN.commit()

    def _load_fixture(self, account):
        with serve.SAVE_LOCK:
            row = serve.DB_CONN.execute(
                "SELECT payload FROM saves WHERE id=?", (account,)
            ).fetchone()
        return json.loads(row[0])

    def _request(self, path, fields=None, *, cookie=None, method="POST", host=None):
        body = urlencode(fields or {}) if fields is not None else ""
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if cookie:
            headers["Cookie"] = cookie
        if host:
            headers["Host"] = host
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read().decode("utf-8", "replace")
        result = response.status, dict(response.getheaders()), raw
        conn.close()
        return result

    def _login(self, account=None, password=None):
        account = account or self.ACCOUNT_A
        password = password or self.PASSWORD_A
        status, headers, body = self._request(
            "/ELDORADO_WEB/login_auth.php",
            {"acc": account, "pw": password},
        )
        self.assertEqual(200, status)
        self.assertEqual(1, json.loads(body)["ok"])
        cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
        self.assertTrue(cookie)
        return cookie, headers

    def test_login_issues_opaque_httponly_session_and_does_not_log_secrets(self):
        cookie, headers = self._login()
        self.assertTrue(cookie.startswith("dol_session="), cookie)
        self.assertNotIn(self.ACCOUNT_A, cookie)
        self.assertIn("HttpOnly", headers.get("Set-Cookie", ""))
        logs = self.log_output.getvalue()
        self.assertNotIn(self.PASSWORD_A, logs)
        self.assertNotIn(cookie.split("=", 1)[1], logs)

    def test_wrong_login_does_not_issue_session(self):
        status, headers, body = self._request(
            "/ELDORADO_WEB/login_auth.php",
            {"acc": self.ACCOUNT_A, "pw": "wrong-password"},
        )
        self.assertEqual(200, status)
        self.assertEqual(0, json.loads(body)["ok"])
        self.assertNotIn("Set-Cookie", headers)

    def test_account_endpoint_without_session_is_rejected(self):
        status, _, body = self._request(
            "/ELDORADO_WEB/cnm_exist_host_in_server.php",
            {"HOST_ID": self.ACCOUNT_A},
        )
        self.assertEqual(401, status)
        self.assertNotIn("A_MARKER", body)

    def test_check_black_list_without_session_returns_graceful_login_required(self):
        status, headers, body = self._request(
            "/ELDORADO_WEB/check_black_list_db.php",
            {},
            method="GET",
        )
        self.assertEqual(200, status)
        self.assertNotIn("A_MARKER", body)
        data = json.loads(body)
        self.assertEqual("BLACK_LIST", data["result"])
        self.assertNotEqual("OK", data.get("STATE", ""))

    def test_session_a_reads_a_even_when_all_wire_ids_claim_b(self):
        cookie, _ = self._login()
        status, _, body = self._request(
            "/ELDORADO_WEB/cnm_exist_host_in_server.php",
            {"HOST_ID": self.ACCOUNT_B, "UNIQ_ID": self.ACCOUNT_B, "ID": self.ACCOUNT_B},
            cookie=cookie,
        )
        data = json.loads(body)
        self.assertEqual(200, status)
        self.assertEqual("A_MARKER", data["USER_NAME"])
        self.assertNotIn("B_MARKER", body)

    def test_session_a_save_mutation_cannot_write_b(self):
        cookie, _ = self._login()
        new_data1 = ",".join(["A_AFTER", "1234", "333"] + ["0"] * 18)
        status, _, _ = self._request(
            "/ELDORADO_WEB/cnm_update_user_to_server_cry.php",
            {
                "HOST_ID": self.ACCOUNT_B,
                "UNIQ_ID": self.ACCOUNT_B,
                "ID": self.ACCOUNT_B,
                "USER_NAME": "A_AFTER",
                "DATA1": new_data1,
            },
            cookie=cookie,
        )
        self.assertEqual(200, status)
        self.assertEqual("A_AFTER", self._load_fixture(self.ACCOUNT_A)["USER_NAME"])
        self.assertEqual("B_MARKER", self._load_fixture(self.ACCOUNT_B)["USER_NAME"])

    def test_session_a_wallet_and_economy_mutation_cannot_touch_b(self):
        cookie, _ = self._login()
        status, _, body = self._request(
            "/ELDORADO_WEB/toolshop/get_balances.php",
            {"HOST_ID": self.ACCOUNT_B, "UNIQ_ID": self.ACCOUNT_B, "ID": self.ACCOUNT_B},
            cookie=cookie,
        )
        self.assertEqual("10", json.loads(body)["bp"])
        status, _, _ = self._request(
            "/ELDORADO_WEB/bonuspoint/add_bonus_point.php",
            {"HOST_ID": self.ACCOUNT_B, "UNIQ_ID": self.ACCOUNT_B, "ID": self.ACCOUNT_B, "ADD_POINT": "5"},
            cookie=cookie,
        )
        self.assertEqual(200, status)
        self.assertEqual("15", self._load_fixture(self.ACCOUNT_A)["bp"])
        self.assertEqual("20", self._load_fixture(self.ACCOUNT_B)["bp"])

    def test_session_a_game_state_mutation_cannot_touch_b(self):
        cookie, _ = self._login()
        status, _, body = self._request(
            "/ELDORADO_WEB/temple/update_dragon_info.php",
            {"HOST_ID": self.ACCOUNT_B, "UNIQ_ID": self.ACCOUNT_B, "ID": self.ACCOUNT_B, "MODE": "UPDATE", "TYPE": "95"},
            cookie=cookie,
        )
        self.assertEqual(200, status)
        self.assertEqual("FAIL", json.loads(body)["STATE"])
        self.assertEqual("80", self._load_fixture(self.ACCOUNT_A)["cloud_piece"])
        self.assertEqual("200", self._load_fixture(self.ACCOUNT_B)["cloud_piece"])

    def test_legacy_admin_is_hidden_on_game_listener(self):
        for path in ("/admin", "/admin?key=wrong", "/admin?key=" + self.ADMIN_KEY):
            status, _, body = self._request(path, None, method="GET")
            self.assertEqual(404, status)
            self.assertEqual("Not Found", body)
            self.assertNotIn(self.ADMIN_KEY, body)

    def test_legacy_admin_stays_hidden_with_fake_host(self):
        status, _, body = self._request(
            "/admin?key=" + self.ADMIN_KEY,
            None,
            method="GET",
            host="evil.example",
        )
        self.assertEqual(404, status)
        self.assertEqual("Not Found", body)
        self.assertNotIn(self.ADMIN_KEY, body)
        self.assertNotIn("evil.example", body)
        self.assertNotIn(self.ADMIN_KEY, self.log_output.getvalue())

    def test_authenticated_game_contract_smoke(self):
        cookie, _ = self._login()
        checks = [
            ("/ELDORADO_WEB/get_app_file.php", {}, None),
            ("/ELDORADO_WEB/get_reward2_mailbox.php", {}, "STATE"),
            ("/ELDORADO_WEB/PVP_2025/get_pvp_ranking.php", {"TEAM": "1:2:3:4:5"}, "STATE"),
            ("/ELDORADO_WEB/BOSS_2026/get_boss_ranking.php", {}, "STATE"),
            ("/ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php", {"MODE": "RANKING_GET"}, "STATE"),
        ]
        for path, fields, required in checks:
            with self.subTest(path=path):
                status, _, body = self._request(path, fields, cookie=cookie)
                self.assertEqual(200, status)
                if required:
                    self.assertIn(required, json.loads(body))


if __name__ == "__main__":
    unittest.main(verbosity=2)

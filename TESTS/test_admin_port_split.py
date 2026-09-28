import http.client
import os
import secrets
import sys
import tempfile
import threading
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class AdminPortSplitHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admin_handler = serve.AdminHandler
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_admin_port_split_")
        cls.root = Path(cls.tmp.name)
        cls.password = secrets.token_urlsafe(24)
        cls.old_password = os.environ.get("BUSIDOL_ADMIN_PASSWORD")
        os.environ["BUSIDOL_ADMIN_PASSWORD"] = cls.password

        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.CAP_DIR = cls.root / "capture"
        serve.CAP_DIR.mkdir()
        serve.SAVE_FILE = cls.root / "unused.json"
        serve.init_db(cls.root / "split.db")
        serve.add_account("SPLIT_TEST", secrets.token_urlsafe(16))

        cls.game_server = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        cls.admin_server = serve.ThreadingHTTPServer(
            ("127.0.0.1", 0), admin_handler
        )
        serve.SRV_PORT = cls.game_server.server_port
        cls.threads = [
            threading.Thread(target=cls.game_server.serve_forever, daemon=True),
            threading.Thread(target=cls.admin_server.serve_forever, daemon=True),
        ]
        for thread in cls.threads:
            thread.start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.game_server, cls.admin_server):
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=5)
        if serve.DB_CONN is not None:
            serve.DB_CONN.close()
        serve.DB_CONN = None
        serve.DB_FILE = None
        serve.REQUIRE_LOGIN = False
        if cls.old_password is None:
            os.environ.pop("BUSIDOL_ADMIN_PASSWORD", None)
        else:
            os.environ["BUSIDOL_ADMIN_PASSWORD"] = cls.old_password
        cls.tmp.cleanup()

    @staticmethod
    def _get(port, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_game_listener_hides_all_admin_routes_even_with_spoofed_headers(self):
        spoofed = {
            "Host": "localhost",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
            "CF-Connecting-IP": "127.0.0.1",
        }
        for path in (
            "/admin-control",
            "/admin-control/",
            "/admin-control/login",
            "/admin-control/anything",
            "/admin",
            "/admin?key=random",
        ):
            with self.subTest(path=path):
                status, headers, body = self._get(
                    self.game_server.server_port, path, spoofed
                )
                self.assertEqual(404, status)
                disclosed = (str(headers) + body.decode("utf-8", "replace")).lower()
                self.assertNotIn("admin-control", disclosed)
                self.assertNotIn("8030", disclosed)

    def test_game_listener_still_serves_game_login(self):
        status, _, body = self._get(
            self.game_server.server_port, "/ELDORADO_WEB/login_page.php"
        )
        self.assertEqual(200, status)
        self.assertIn(b"password", body.lower())

    def test_admin_listener_serves_admin_control_only(self):
        status, _, body = self._get(
            self.admin_server.server_port, "/admin-control/login"
        )
        self.assertEqual(200, status)
        self.assertIn(b"password", body.lower())

        status, _, _ = self._get(
            self.admin_server.server_port, "/ELDORADO_WEB/login_page.php"
        )
        self.assertEqual(404, status)

        status, _, _ = self._get(self.admin_server.server_port, "/admin")
        self.assertEqual(404, status)

    def test_rejected_post_body_does_not_poison_keep_alive_connection(self):
        body = b"password=must-not-become-the-next-method"

        game_connection = http.client.HTTPConnection(
            "127.0.0.1", self.game_server.server_port, timeout=5
        )
        try:
            game_connection.request(
                "POST",
                "/admin-control/login",
                body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = game_connection.getresponse()
            self.assertEqual(404, response.status)
            response.read()
            game_connection.request("GET", "/ELDORADO_WEB/login_page.php")
            response = game_connection.getresponse()
            self.assertEqual(200, response.status)
            response.read()
        finally:
            game_connection.close()

        admin_connection = http.client.HTTPConnection(
            "127.0.0.1", self.admin_server.server_port, timeout=5
        )
        try:
            admin_connection.request(
                "POST",
                "/ELDORADO_WEB/login_auth.php",
                body=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = admin_connection.getresponse()
            self.assertEqual(404, response.status)
            response.read()
            admin_connection.request("GET", "/admin-control/login")
            response = admin_connection.getresponse()
            self.assertEqual(200, response.status)
            response.read()
        finally:
            admin_connection.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

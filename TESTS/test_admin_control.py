import http.client
import io
import json
import logging
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import serve


class AdminControlHTTPTests(unittest.TestCase):
    ACCOUNT_A = "ADMIN_TEST_A"
    ACCOUNT_B = "ADMIN_TEST_B"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_admin_control_")
        cls.root = Path(cls.tmp.name)
        cls.password = secrets.token_urlsafe(24)
        cls.old_password = os.environ.get("BUSIDOL_ADMIN_PASSWORD")
        os.environ["BUSIDOL_ADMIN_PASSWORD"] = cls.password

        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = False
        serve.MODE = "offline"
        serve.CAP_DIR = cls.root / "capture"
        serve.CAP_DIR.mkdir()
        serve.SAVE_FILE = cls.root / "unused.json"
        serve.init_db(cls.root / "admin-control.db")
        serve.add_account(cls.ACCOUNT_A, secrets.token_urlsafe(16))
        serve.add_account(cls.ACCOUNT_B, secrets.token_urlsafe(16))

        cls.old_handlers = list(serve.LOG.handlers)
        cls.log_output = io.StringIO()
        serve.LOG.handlers.clear()
        serve.LOG.addHandler(logging.StreamHandler(cls.log_output))
        serve.LOG.setLevel(logging.INFO)

        cls.server = serve.ThreadingHTTPServer(
            ("127.0.0.1", 0), serve.AdminHandler
        )
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
        serve.LOG.handlers.clear()
        for handler in cls.old_handlers:
            serve.LOG.addHandler(handler)
        if cls.old_password is None:
            os.environ.pop("BUSIDOL_ADMIN_PASSWORD", None)
        else:
            os.environ["BUSIDOL_ADMIN_PASSWORD"] = cls.old_password
        cls.tmp.cleanup()

    def setUp(self):
        self.log_output.seek(0)
        self.log_output.truncate(0)
        self._store(self.ACCOUNT_A, "A", gold=1000, ruby=200, bp=30, cloud=40, essence=50)
        self._store(self.ACCOUNT_B, "B", gold=9000, ruby=800, bp=70, cloud=60, essence=55)
        with serve.SAVE_LOCK:
            try:
                serve.DB_CONN.execute("DELETE FROM admin_audit")
                serve.DB_CONN.commit()
            except Exception:
                serve.DB_CONN.rollback()
        try:
            import admin_control_backend
            admin_control_backend._SESSIONS.clear()
        except ImportError:
            pass

    def _store(self, account, marker, *, gold, ruby, bp, cloud, essence):
        payload = {
            "DATA1": ",".join([marker, str(gold), str(ruby)] + ["0"] * 18),
            "DATA2": "114:56:70:2250:0:29",
            "DATA3": "",
            "bp": str(bp),
            "cloud_piece": str(cloud),
            "celestial_essence": str(essence),
            "mails": [],
        }
        with serve.SAVE_LOCK:
            serve.DB_CONN.execute(
                "INSERT OR REPLACE INTO saves(id,payload) VALUES(?,?)",
                (account, json.dumps(payload)),
            )
            serve.DB_CONN.commit()

    def _load(self, account):
        with serve.SAVE_LOCK:
            row = serve.DB_CONN.execute(
                "SELECT payload FROM saves WHERE id=?", (account,)
            ).fetchone()
        return json.loads(row[0])

    def _request(self, method, path, payload=None, *, cookie=None, headers=None):
        request_headers = dict(headers or {})
        body = b""
        if payload is not None:
            if request_headers.get("Content-Type") == "application/x-www-form-urlencoded":
                body = urlencode(payload).encode()
            else:
                request_headers["Content-Type"] = "application/json"
                body = json.dumps(payload).encode()
        if cookie:
            request_headers["Cookie"] = cookie
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        conn.request(method, path, body=body, headers=request_headers)
        response = conn.getresponse()
        raw = response.read()
        result = response.status, dict(response.getheaders()), raw
        conn.close()
        return result

    def _json(self, method, path, payload=None, **kwargs):
        status, headers, raw = self._request(method, path, payload, **kwargs)
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {"STATE": "INVALID_RESPONSE"}
        return status, headers, data

    def _request_on_connection(self, connection, method, path, payload=None, *,
                               cookie=None, form=False):
        headers = {}
        body = None
        if payload is not None:
            if form:
                body = urlencode(payload).encode()
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            else:
                body = json.dumps(payload).encode()
                headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        return response.status, dict(response.getheaders()), raw

    def _login(self, password=None, **kwargs):
        status, headers, raw = self._request(
            "POST",
            "/admin-control/login",
            {"password": self.password if password is None else password},
            headers={"Content-Type": "application/x-www-form-urlencoded", **kwargs.pop("headers", {})},
            **kwargs,
        )
        cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
        return status, headers, raw.decode("utf-8", "replace"), cookie

    def test_login_requires_configured_password_and_issues_strict_opaque_cookie(self):
        os.environ.pop("BUSIDOL_ADMIN_PASSWORD", None)
        try:
            status, _, _ = self._request("GET", "/admin-control/login")
            self.assertEqual(503, status)
        finally:
            os.environ["BUSIDOL_ADMIN_PASSWORD"] = self.password

        status, headers, body, cookie = self._login(password="wrong")
        self.assertEqual(401, status)
        self.assertFalse(cookie)
        self.assertNotIn(self.password, body)

        status, headers, _, cookie = self._login()
        self.assertEqual(303, status)
        self.assertTrue(cookie.startswith("busidol_admin_session="))
        self.assertNotIn(self.password, cookie)
        set_cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Strict", set_cookie)
        self.assertIn("Path=/admin-control", set_cookie)
        logs = self.log_output.getvalue()
        self.assertNotIn(self.password, logs)
        self.assertNotIn(cookie.split("=", 1)[1], logs)

    def test_login_post_keeps_one_http_connection_in_sync(self):
        connection = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        try:
            status, _, _ = self._request_on_connection(
                connection, "GET", "/admin-control/login"
            )
            self.assertEqual(200, status)
            socket_object = connection.sock
            self.assertIsNotNone(socket_object)

            status, headers, _ = self._request_on_connection(
                connection, "POST", "/admin-control/login",
                {"password": self.password}, form=True,
            )
            self.assertEqual(303, status)
            self.assertIs(socket_object, connection.sock)
            cookie = headers["Set-Cookie"].split(";", 1)[0]

            status, _, raw = self._request_on_connection(
                connection, "GET", "/admin-control/", cookie=cookie
            )
            self.assertEqual(200, status, raw.decode("utf-8", "replace"))
            self.assertIs(socket_object, connection.sock)
        finally:
            connection.close()

    def test_unconfigured_login_post_consumes_body_before_next_request(self):
        os.environ.pop("BUSIDOL_ADMIN_PASSWORD", None)
        connection = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        try:
            status, _, _ = self._request_on_connection(
                connection, "POST", "/admin-control/login",
                {"password": "not-configured"}, form=True,
            )
            self.assertEqual(503, status)
            socket_object = connection.sock
            self.assertIsNotNone(socket_object)

            status, _, raw = self._request_on_connection(
                connection, "GET", "/admin-control/login"
            )
            self.assertEqual(503, status, raw.decode("utf-8", "replace"))
            self.assertIs(socket_object, connection.sock)
        finally:
            connection.close()
            os.environ["BUSIDOL_ADMIN_PASSWORD"] = self.password

    def test_unauthorized_post_consumes_body_before_next_keep_alive_request(self):
        connection = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        try:
            status, _, raw = self._request_on_connection(
                connection, "POST", "/admin-control/grant-currency",
                {"target": self.ACCOUNT_A, "type": "RUBY", "amount": 1},
            )
            self.assertEqual(401, status)
            self.assertEqual("ADMIN_AUTH_REQUIRED", json.loads(raw)["message"])
            socket_object = connection.sock
            self.assertIsNotNone(socket_object)

            status, _, raw = self._request_on_connection(
                connection, "GET", "/admin-control/login"
            )
            self.assertEqual(200, status, raw.decode("utf-8", "replace"))
            self.assertIs(socket_object, connection.sock)
        finally:
            connection.close()

    def test_unauthenticated_routes_are_denied_and_sqlite_is_required(self):
        status, headers, _ = self._request("GET", "/admin-control")
        self.assertEqual(302, status)
        self.assertEqual("/admin-control/login", headers["Location"])
        status, _, data = self._json("GET", f"/admin-control/account?id={self.ACCOUNT_A}")
        self.assertEqual(401, status)
        self.assertEqual("ADMIN_AUTH_REQUIRED", data["message"])

        _, _, _, cookie = self._login()
        db = serve.DB_CONN
        serve.DB_CONN = None
        try:
            status, _, data = self._json(
                "GET", f"/admin-control/account?id={self.ACCOUNT_A}", cookie=cookie
            )
        finally:
            serve.DB_CONN = db
        self.assertEqual(503, status)
        self.assertEqual("SQLITE_DB_REQUIRED", data["message"])

    def test_local_peer_is_authoritative_not_host_or_forwarding_headers(self):
        try:
            import admin_control_backend
        except ModuleNotFoundError:
            self.fail("admin_control_backend is not installed")

        self.assertTrue(admin_control_backend._client_is_loopback(
            SimpleNamespace(client_address=("127.0.0.42", 1234))
        ))
        self.assertTrue(admin_control_backend._client_is_loopback(
            SimpleNamespace(client_address=("::1", 1234))
        ))
        self.assertFalse(admin_control_backend._client_is_loopback(
            SimpleNamespace(client_address=("192.0.2.10", 1234))
        ))

        _, _, _, cookie = self._login(headers={"Host": "evil.example"})
        status, _, data = self._json(
            "GET",
            f"/admin-control/account?id={self.ACCOUNT_A}",
            cookie=cookie,
            headers={"Host": "evil.example", "X-Forwarded-For": "192.0.2.10"},
        )
        self.assertEqual(200, status)
        self.assertEqual(self.ACCOUNT_A, data["id"])

    def test_frontend_and_account_lookup_contract(self):
        _, _, _, cookie = self._login()
        status, headers, _ = self._request("GET", "/admin-control", cookie=cookie)
        self.assertEqual(302, status)
        self.assertEqual("/admin-control/", headers["Location"])
        for path, content_type in (
            ("/admin-control/", "text/html"),
            ("/admin-control/admin.css", "text/css"),
            ("/admin-control/admin.js", "application/javascript"),
        ):
            with self.subTest(path=path):
                status, headers, raw = self._request("GET", path, cookie=cookie)
                self.assertEqual(200, status)
                self.assertTrue(headers["Content-Type"].startswith(content_type))
                self.assertTrue(raw)

        status, _, data = self._json(
            "GET", f"/admin-control/account?id={self.ACCOUNT_A}", cookie=cookie
        )
        self.assertEqual(200, status)
        self.assertEqual({
            "STATE": "SUCCESS", "id": self.ACCOUNT_A,
            "gold": 1000, "ruby": 200, "bp": 30, "cloud": 40, "essence": 50,
        }, data)
        status, _, data = self._json(
            "GET", "/admin-control/account?id=DOES_NOT_EXIST", cookie=cookie
        )
        self.assertEqual(404, status)
        self.assertEqual("ACCOUNT_NOT_FOUND", data["message"])

    def test_each_currency_grant_is_server_calculated_persistent_and_isolated(self):
        _, _, _, cookie = self._login()
        cases = {
            "GOLD": (1000, 11), "RUBY": (200, 12), "BP": (30, 13),
            "CLOUD": (40, 14), "ESSENCE": (50, 15),
        }
        expected_after = {}
        for typ, (before, amount) in cases.items():
            with self.subTest(currency=typ):
                status, _, data = self._json(
                    "POST", "/admin-control/grant-currency",
                    {"target": self.ACCOUNT_A, "type": typ, "amount": amount},
                    cookie=cookie,
                )
                self.assertEqual(200, status)
                if status != 200:
                    continue
                self.assertEqual(before, data["before"])
                self.assertEqual(before + amount, data["after"])
                expected_after[typ] = before + amount

        if len(expected_after) != len(cases):
            self.fail("one or more currency grants did not return the API contract")
        reloaded = self._load(self.ACCOUNT_A)
        d1 = reloaded["DATA1"].split(",")
        self.assertEqual(str(expected_after["GOLD"]), d1[1])
        self.assertEqual(str(expected_after["RUBY"]), d1[2])
        self.assertEqual(str(expected_after["BP"]), reloaded["bp"])
        self.assertEqual(str(expected_after["CLOUD"]), reloaded["cloud_piece"])
        self.assertEqual(str(expected_after["ESSENCE"]), reloaded["celestial_essence"])
        self.assertEqual("B", self._load(self.ACCOUNT_B)["DATA1"].split(",")[0])

    def test_currency_and_account_isolation_persist_after_real_server_restart(self):
        with tempfile.TemporaryDirectory(prefix="busidol_admin_restart_") as temp_dir:
            root = Path(temp_dir)
            db_path = root / "restart.db"
            admin_password = secrets.token_urlsafe(24)
            payload_a = {
                "DATA1": ",".join(["A", "1000", "200"] + ["0"] * 18),
                "DATA2": "114:56:70:2250:0:29",
                "DATA3": "",
                "bp": "30",
                "cloud_piece": "40",
                "celestial_essence": "50",
                "mails": [],
            }
            payload_b = {
                "DATA1": ",".join(["B", "9000", "800"] + ["0"] * 18),
                "DATA2": "114:56:70:2250:0:29",
                "DATA3": "",
                "bp": "70",
                "cloud_piece": "60",
                "celestial_essence": "55",
                "mails": [],
            }
            db = sqlite3.connect(db_path)
            try:
                db.execute("CREATE TABLE saves(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                db.executemany(
                    "INSERT INTO saves(id,payload) VALUES(?,?)",
                    (
                        ("ADMIN_TEST_RESTART", json.dumps(payload_a)),
                        ("ADMIN_TEST_RESTART_B", json.dumps(payload_b)),
                    ),
                )
                db.commit()
            finally:
                db.close()

            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                game_port = sock.getsockname()[1]
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                admin_port = sock.getsockname()[1]

            command = [
                sys.executable,
                str(PROJECT_ROOT / "serve.py"),
                "--mode", "offline",
                "--host", "127.0.0.1",
                "--port", str(game_port),
                "--admin-port", str(admin_port),
                "--db", str(db_path),
                "--require-login",
                "--capture", str(root / "capture"),
                "--save-file", str(root / "unused.json"),
                "--log", str(root / "serve.log"),
            ]
            environment = os.environ.copy()
            environment["BUSIDOL_ADMIN_PASSWORD"] = admin_password

            def start_server():
                process = subprocess.Popen(
                    command,
                    cwd=PROJECT_ROOT,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(f"isolated server exited with code {process.returncode}")
                    try:
                        with socket.create_connection(("127.0.0.1", admin_port), timeout=0.2):
                            return process
                    except OSError:
                        time.sleep(0.05)
                process.terminate()
                process.wait(timeout=5)
                self.fail("isolated server did not become ready")

            def stop_server(process):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

            def request(method, path, payload=None, cookie=None, form=False):
                headers = {}
                body = None
                if payload is not None:
                    if form:
                        body = urlencode(payload).encode()
                        headers["Content-Type"] = "application/x-www-form-urlencoded"
                    else:
                        body = json.dumps(payload).encode()
                        headers["Content-Type"] = "application/json"
                if cookie:
                    headers["Cookie"] = cookie
                connection = http.client.HTTPConnection(
                    "127.0.0.1", admin_port, timeout=5
                )
                connection.request(method, path, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                result = response.status, dict(response.getheaders()), raw
                connection.close()
                return result

            def login():
                status, headers, _ = request(
                    "POST", "/admin-control/login",
                    {"password": admin_password}, form=True,
                )
                self.assertEqual(303, status)
                return headers["Set-Cookie"].split(";", 1)[0]

            process = start_server()
            try:
                cookie = login()
                status, _, raw = request(
                    "POST", "/admin-control/grant-currency",
                    {"target": "ADMIN_TEST_RESTART", "type": "BP", "amount": 9},
                    cookie,
                )
                self.assertEqual(200, status, raw.decode("utf-8", "replace"))
                self.assertEqual(39, json.loads(raw)["after"])
            finally:
                stop_server(process)

            process = start_server()
            try:
                cookie = login()
                status, _, raw = request(
                    "GET", "/admin-control/account?id=ADMIN_TEST_RESTART",
                    cookie=cookie,
                )
                self.assertEqual(200, status)
                self.assertEqual(39, json.loads(raw)["bp"])
                status, _, raw = request(
                    "GET", "/admin-control/account?id=ADMIN_TEST_RESTART_B",
                    cookie=cookie,
                )
                self.assertEqual(200, status)
                account_b = json.loads(raw)
                self.assertEqual(70, account_b["bp"])
                self.assertEqual(9000, account_b["gold"])
                status, _, raw = request("GET", "/admin-control/audit", cookie=cookie)
                self.assertEqual(200, status)
                self.assertTrue(any(
                    row["target"] == "ADMIN_TEST_RESTART"
                    and row["action"] == "GRANT_BP"
                    for row in json.loads(raw)["logs"]
                ))
            finally:
                stop_server(process)

    def test_invalid_currency_amounts_and_overflow_are_rejected_without_mutation(self):
        _, _, _, cookie = self._login()
        invalid = [
            {"type": "GOLD", "amount": 0},
            {"type": "GOLD", "amount": -1},
            {"type": "GOLD", "amount": 1.5},
            {"type": "GOLD", "amount": 10**12 + 1},
            {"type": "NOT_A_CURRENCY", "amount": 1},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                status, _, data = self._json(
                    "POST", "/admin-control/grant-currency",
                    {"target": self.ACCOUNT_A, **payload}, cookie=cookie,
                )
                self.assertEqual(400, status)
                if status != 400:
                    continue
                self.assertEqual("ERROR", data["STATE"])
        self.assertEqual("1000", self._load(self.ACCOUNT_A)["DATA1"].split(",")[1])

        nearly_full = self._load(self.ACCOUNT_A)
        d1 = nearly_full["DATA1"].split(",")
        d1[1] = str(2**63 - 10)
        nearly_full["DATA1"] = ",".join(d1)
        with serve.SAVE_LOCK:
            serve.DB_CONN.execute(
                "UPDATE saves SET payload=? WHERE id=?",
                (json.dumps(nearly_full), self.ACCOUNT_A),
            )
            serve.DB_CONN.commit()
        status, _, data = self._json(
            "POST", "/admin-control/grant-currency",
            {"target": self.ACCOUNT_A, "type": "GOLD", "amount": 20}, cookie=cookie,
        )
        self.assertEqual(400, status)
        self.assertEqual("BALANCE_OVERFLOW", data["message"])
        self.assertEqual(str(2**63 - 10), self._load(self.ACCOUNT_A)["DATA1"].split(",")[1])

    def test_character_grant_uses_mailbox_without_touching_data2(self):
        _, _, _, cookie = self._login()
        before_data2 = self._load(self.ACCOUNT_A)["DATA2"]
        status, _, data = self._json(
            "POST", "/admin-control/grant-character",
            {"target": self.ACCOUNT_A, "character_id": 114, "reason": "ADMIN GIFT"},
            cookie=cookie,
        )
        self.assertEqual(200, status)
        saved = self._load(self.ACCOUNT_A)
        self.assertEqual(before_data2, saved["DATA2"])
        self.assertEqual("CHAR", saved["mails"][-1]["what"])
        self.assertEqual("114", saved["mails"][-1]["what_value"])
        self.assertEqual([], self._load(self.ACCOUNT_B)["mails"])
        for char_id, expected in ((0, "INVALID_CHARACTER"),
                                  (999, "INVALID_CHARACTER"),
                                  (1.5, "INVALID_REQUEST")):
            status, _, data = self._json(
                "POST", "/admin-control/grant-character",
                {"target": self.ACCOUNT_A, "character_id": char_id}, cookie=cookie,
            )
            self.assertEqual(400, status)
            self.assertEqual(expected, data["message"])

    def test_item_grant_validates_catalog_and_quantity_creates_separate_mails(self):
        _, _, _, cookie = self._login()
        status, _, data = self._json(
            "POST", "/admin-control/grant-item",
            {"target": self.ACCOUNT_A, "item_id": 111, "quantity": 3},
            cookie=cookie,
        )
        self.assertEqual(200, status)
        self.assertEqual(3, len(data["mail_sns"]))
        mails = self._load(self.ACCOUNT_A)["mails"]
        self.assertEqual(3, len(mails))
        self.assertTrue(all(m["what"] == "ITEM" and m["what_value"] == "111" for m in mails))
        status, _, data = self._json(
            "POST", "/admin-control/grant-item",
            {"target": self.ACCOUNT_A, "item_id": 999999, "quantity": 1},
            cookie=cookie,
        )
        self.assertEqual(400, status)
        self.assertEqual("INVALID_ITEM", data["message"])
        for payload in (
            {"target": self.ACCOUNT_A, "item_id": 111.5, "quantity": 1},
            {"target": self.ACCOUNT_A, "item_id": 111, "quantity": 1.5},
        ):
            status, _, data = self._json(
                "POST", "/admin-control/grant-item", payload, cookie=cookie,
            )
            self.assertEqual(400, status)
            self.assertEqual("INVALID_REQUEST", data["message"])

    def test_audit_contains_successful_actions_without_secrets(self):
        _, _, _, cookie = self._login()
        requests = [
            ("/admin-control/grant-currency", {"target": self.ACCOUNT_A, "type": "RUBY", "amount": 5}),
            ("/admin-control/grant-character", {"target": self.ACCOUNT_A, "character_id": 114}),
            ("/admin-control/grant-item", {"target": self.ACCOUNT_A, "item_id": 111, "quantity": 1}),
        ]
        for path, payload in requests:
            status, _, _ = self._json("POST", path, payload, cookie=cookie)
            self.assertEqual(200, status)
        status, _, data = self._json("GET", "/admin-control/audit", cookie=cookie)
        self.assertEqual(200, status)
        actions = {row["action"] for row in data["logs"]}
        self.assertTrue({"GRANT_RUBY", "GRANT_CHARACTER", "GRANT_ITEM"}.issubset(actions))
        serialized = json.dumps(data)
        self.assertNotIn(self.password, serialized)
        self.assertNotIn(cookie.split("=", 1)[1], serialized)

    def test_currency_grants_are_serialized_without_lost_updates(self):
        _, _, _, cookie = self._login()
        barrier = threading.Barrier(3)
        results = []

        def grant():
            barrier.wait()
            try:
                results.append(self._json(
                    "POST", "/admin-control/grant-currency",
                    {"target": self.ACCOUNT_A, "type": "BP", "amount": 7}, cookie=cookie,
                )[0])
            except Exception as exc:
                results.append(type(exc).__name__)

        threads = [threading.Thread(target=grant) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual([200, 200], sorted(results))
        self.assertEqual("44", self._load(self.ACCOUNT_A)["bp"])

    def test_audit_failure_rolls_back_the_save_mutation(self):
        _, _, _, cookie = self._login()
        with serve.SAVE_LOCK:
            try:
                serve.DB_CONN.execute("""
                    CREATE TRIGGER fail_admin_audit BEFORE INSERT ON admin_audit
                    WHEN NEW.target='ADMIN_TEST_A'
                    BEGIN SELECT RAISE(ABORT, 'forced audit failure'); END
                """)
            except Exception:
                self.fail("admin_audit table was not initialized")
            serve.DB_CONN.commit()
        try:
            status, _, data = self._json(
                "POST", "/admin-control/grant-currency",
                {"target": self.ACCOUNT_A, "type": "BP", "amount": 9}, cookie=cookie,
            )
            self.assertEqual(500, status)
            self.assertEqual("30", self._load(self.ACCOUNT_A)["bp"])
            with serve.SAVE_LOCK:
                count = serve.DB_CONN.execute(
                    "SELECT COUNT(*) FROM admin_audit WHERE target=?", (self.ACCOUNT_A,)
                ).fetchone()[0]
            self.assertEqual(0, count)
        finally:
            with serve.SAVE_LOCK:
                serve.DB_CONN.execute("DROP TRIGGER IF EXISTS fail_admin_audit")
                serve.DB_CONN.commit()


if __name__ == "__main__":
    unittest.main(verbosity=2)

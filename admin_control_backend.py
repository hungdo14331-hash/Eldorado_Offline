"""
BUSIDOL Admin Control backend
=============================

Drop-in helper for the existing stdlib ThreadingHTTPServer in serve.py.

Security model:
- localhost/loopback only (127.0.0.0/8 or ::1)
- separate admin password from environment variable BUSIDOL_ADMIN_PASSWORD
- server-generated HttpOnly SameSite=Strict session cookie
- target account is looked up server-side in SQLite `saves(id,payload)`
- browser never supplies current balances
- mutations are serialized under the existing SAVE_LOCK
- audit log is stored in SQLite table admin_audit

Expected project files:
    admin_control/admin_control.html
    admin_control/admin.css
    admin_control/admin.js

Integration into serve.py:
    from admin_control_backend import try_handle_admin_control

At the VERY START of both HTTP handler methods do_GET() and do_POST(),
before normal static/PHP dispatch:

    if try_handle_admin_control(self, DB_CONN, SAVE_LOCK, BASE_DIR):
        return

This module intentionally refuses arbitrary-account administration when
SQLite DB mode is not active.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

COOKIE_NAME = "busidol_admin_session"
SESSION_TTL = 8 * 60 * 60
MAX_GRANT = 10**12
VALID_CURRENCIES = {"GOLD", "RUBY", "BP", "CLOUD", "ESSENCE"}

def _custom_character_ids() -> set[int]:
    config_dir = Path(__file__).resolve().parent / "character_workshop" / "characters"
    result = set()
    for path in config_dir.glob("*.json"):
        try:
            char_id = int(json.loads(path.read_text(encoding="utf-8"))["id"])
            if char_id > 114:
                result.add(char_id)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
    return result


# Legacy catalog plus validated custom-character IDs.
VALID_CHARACTER_IDS = set(range(1, 115)) | _custom_character_ids()

_SESSIONS: dict[str, float] = {}
_SESSION_LOCK = threading.RLock()


def _json_bytes(data) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _reply(handler, status: int, body=b"", content_type="text/plain; charset=utf-8",
           headers: dict[str, str] | None = None):
    if isinstance(body, str):
        body = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Security-Policy",
                        "default-src 'self'; script-src 'self'; style-src 'self'; "
                        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
    if headers:
        for k, v in headers.items():
            handler.send_header(k, v)
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def _json_reply(handler, status: int, data):
    _reply(handler, status, _json_bytes(data), "application/json; charset=utf-8")


def _client_is_loopback(handler) -> bool:
    try:
        # IMPORTANT: use the actual TCP peer address, not Host/X-Forwarded-For.
        return ipaddress.ip_address(handler.client_address[0]).is_loopback
    except Exception:
        return False


def _cookies(handler) -> dict[str, str]:
    raw = handler.headers.get("Cookie", "")
    out = {}
    for part in raw.split(";"):
        if "=" not in part:
            continue
        k, v = part.strip().split("=", 1)
        out[k] = v
    return out


def _session_ok(handler) -> bool:
    token = _cookies(handler).get(COOKIE_NAME, "")
    if not token:
        return False
    now = time.time()
    with _SESSION_LOCK:
        expiry = _SESSIONS.get(token, 0)
        if expiry <= now:
            _SESSIONS.pop(token, None)
            return False
        # Sliding expiry while actively using the local admin page.
        _SESSIONS[token] = now + SESSION_TTL
        return True


def _new_session() -> str:
    token = secrets.token_urlsafe(32)
    with _SESSION_LOCK:
        _SESSIONS[token] = time.time() + SESSION_TTL
    return token


def _password_configured() -> str | None:
    value = os.environ.get("BUSIDOL_ADMIN_PASSWORD", "")
    return value if value else None


def _read_body(handler, max_bytes=64 * 1024) -> bytes:
    cached = getattr(handler, "_admin_control_request_body", None)
    if cached is not None:
        return cached
    try:
        length = int(handler.headers.get("Content-Length", "0") or 0)
    except ValueError as exc:
        raise ValueError("invalid content length") from exc
    if length < 0 or length > max_bytes:
        raise ValueError("request too large")
    body = handler.rfile.read(length) if length else b""
    handler._admin_control_request_body = body
    return body


def _parse_payload(handler) -> dict:
    raw = _read_body(handler)
    ctype = (handler.headers.get("Content-Type", "") or "").split(";", 1)[0].lower()
    if ctype == "application/json":
        try:
            value = json.loads(raw.decode("utf-8") or "{}")
        except Exception as exc:
            raise ValueError("invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value
    try:
        qs = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    except Exception as exc:
        raise ValueError("invalid form body") from exc
    return {k: (v[-1] if v else "") for k, v in qs.items()}


def _require_db(db_conn):
    if db_conn is None:
        raise RuntimeError("Admin Control requires --db SQLite mode")


def _ensure_schema(db_conn):
    _require_db(db_conn)
    db_conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL
        )
    """)
    db_conn.commit()


def _audit(db_conn, target: str, action: str, detail: str, result: str):
    # Never place passwords, admin session tokens or secrets in detail.
    db_conn.execute(
        "INSERT INTO admin_audit(ts,target,action,detail,result) VALUES(?,?,?,?,?)",
        (int(time.time()), str(target)[:128], str(action)[:64],
         str(detail)[:1000], str(result)[:64]),
    )


def _load_target_save(db_conn, target: str) -> dict | None:
    row = db_conn.execute("SELECT payload FROM saves WHERE id=?", (target,)).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except Exception:
        raise ValueError("target save payload is not valid JSON")
    if not isinstance(data, dict):
        raise ValueError("target save payload is not a JSON object")
    return data


def _store_target_save(db_conn, target: str, data: dict):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    cur = db_conn.execute("UPDATE saves SET payload=? WHERE id=?", (payload, target))
    if cur.rowcount != 1:
        raise ValueError("target account disappeared during update")


def _as_int(v, default=0):
    try:
        return int(float(str(v if v is not None else default)))
    except (TypeError, ValueError):
        return int(default)


def _request_int(value) -> int:
    """Parse an integer request field without truncating floats or booleans."""
    if isinstance(value, bool):
        raise ValueError("integer required")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        return int(value)
    raise ValueError("integer required")


def _balances(save: dict) -> dict[str, int]:
    d1 = str(save.get("DATA1") or "").split(",")
    gold = _as_int(d1[1], 0) if len(d1) > 1 else 0
    ruby = _as_int(d1[2], 0) if len(d1) > 2 else 0
    return {
        "gold": gold,
        "ruby": ruby,
        "bp": _as_int(save.get("bp"), 0),
        "cloud": _as_int(save.get("cloud_piece"), 0),
        "essence": _as_int(save.get("celestial_essence"), 0),
    }


def _set_currency(save: dict, typ: str, value: int):
    if typ in ("GOLD", "RUBY"):
        d1 = str(save.get("DATA1") or "").split(",")
        while len(d1) < 3:
            d1.append("0")
        d1[1 if typ == "GOLD" else 2] = str(value)
        save["DATA1"] = ",".join(d1)
    elif typ == "BP":
        save["bp"] = str(value)
    elif typ == "CLOUD":
        save["cloud_piece"] = str(value)
    elif typ == "ESSENCE":
        save["celestial_essence"] = str(value)
    else:
        raise ValueError("invalid currency")


def _next_mail_sn(mails) -> str:
    greatest = 0
    for m in mails:
        try:
            greatest = max(greatest, int(str((m or {}).get("sn", "0"))))
        except Exception:
            pass
    # Keep it numeric like the existing mailbox implementation.
    return str(max(greatest + 1, int(time.time() * 1000)))


def _append_mail(save: dict, what: str, what_value: str, reason: str) -> str:
    mails = save.get("mails")
    if not isinstance(mails, list):
        mails = []
    sn = _next_mail_sn(mails)
    mails.append({
        "sn": sn,
        "why": reason[:80] or "ADMIN GIFT",
        "what": what,
        "what_value": str(what_value),
        "start_date": time.strftime("%Y-%m-%d"),
        "end_date": "20991231",
    })
    save["mails"] = mails
    return sn


def _load_valid_item_ids(base_dir: Path) -> set[int] | None:
    """
    Try project catalogs rather than inventing item IDs.
    Returns None if no catalog can be confidently parsed.
    """
    candidates = [
        base_dir / "ITEMS.csv",
        base_dir / "wiki" / "data" / "ITEMS.csv",
        base_dir / "wiki" / "data" / "items.csv",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        ids = set()
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
            if not rows:
                continue
            # Determine ID column from header when possible.
            header = [c.strip().lower() for c in rows[0]]
            id_col = None
            for name in ("id", "item_id", "itemid", "num", "item_num"):
                if name in header:
                    id_col = header.index(name)
                    break
            start = 1 if id_col is not None else 0
            if id_col is None:
                id_col = 0
            for row in rows[start:]:
                if len(row) <= id_col:
                    continue
                try:
                    ids.add(int(row[id_col].strip()))
                except Exception:
                    continue
            if ids:
                return ids
        except Exception:
            continue

    # Markdown fallback: only accept explicit "ID <number>" patterns.
    md = base_dir / "ITEMS.md"
    if md.is_file():
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
            ids = {int(x) for x in re.findall(r"\bID\s*[:#]?\s*(\d+)\b", text, re.I)}
            if ids:
                return ids
        except Exception:
            pass
    return None


def _login_html(message="") -> bytes:
    msg = f"<p class='err'>{html.escape(message)}</p>" if message else ""
    page = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BUSIDOL Admin Login</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#090d16;color:#f5f7fb;font-family:system-ui,sans-serif}}
form{{width:min(360px,calc(100vw - 36px));padding:28px;background:#111827;border:1px solid #263047;border-radius:18px}}
h1{{font-size:20px;margin:0 0 6px}}p{{color:#91a0b8;font-size:13px}}label{{display:block;margin:18px 0 7px;color:#91a0b8;font-size:12px}}
input{{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid #263047;background:#090d16;color:white}}
button{{width:100%;margin-top:14px;padding:12px;border:0;border-radius:10px;background:#3b82f6;color:white;font-weight:800}}
.err{{color:#fb7185}}
</style></head><body>
<form method="post" action="/admin-control/login">
<h1>BUSIDOL Admin</h1>
<p>Local owner authentication</p>
{msg}
<label>Admin password</label>
<input type="password" name="password" autofocus required autocomplete="current-password">
<button type="submit">Đăng nhập</button>
</form></body></html>"""
    return page.encode("utf-8")


def _authorized_or_login(handler, path: str) -> bool:
    if _session_ok(handler):
        return True
    if path.startswith("/admin-control/api/") or path in {
        "/admin-control/account",
        "/admin-control/grant-currency",
        "/admin-control/grant-character",
        "/admin-control/grant-item",
        "/admin-control/audit",
    }:
        _json_reply(handler, 401, {"STATE": "ERROR", "message": "ADMIN_AUTH_REQUIRED"})
    else:
        _reply(handler, 302, b"", headers={"Location": "/admin-control/login"})
    return False


def _serve_frontend(handler, base_dir: Path, name: str):
    root = base_dir / "admin_control"
    path = root / name
    if not path.is_file():
        _reply(handler, 404, "Admin frontend file not found")
        return
    ext = path.suffix.lower()
    ctype = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }.get(ext, "application/octet-stream")
    _reply(handler, 200, path.read_bytes(), ctype)


def _handle_login(handler, method: str):
    configured = _password_configured()
    if not configured:
        _reply(handler, 503, _login_html(
            "Chưa cấu hình BUSIDOL_ADMIN_PASSWORD trên server."
        ), "text/html; charset=utf-8")
        return

    if method == "GET":
        _reply(handler, 200, _login_html(), "text/html; charset=utf-8")
        return

    try:
        body = _parse_payload(handler)
    except ValueError:
        _reply(handler, 400, _login_html("Request không hợp lệ."), "text/html; charset=utf-8")
        return

    supplied = str(body.get("password", ""))
    if not hmac.compare_digest(
        hashlib.sha256(supplied.encode()).digest(),
        hashlib.sha256(configured.encode()).digest(),
    ):
        # Generic error; never echo the configured password.
        _reply(handler, 401, _login_html("Sai mật khẩu."), "text/html; charset=utf-8")
        return

    token = _new_session()
    _reply(
        handler, 303, b"",
        headers={
            "Location": "/admin-control",
            "Set-Cookie": (
                f"{COOKIE_NAME}={token}; Path=/admin-control; HttpOnly; "
                "SameSite=Strict; Max-Age=" + str(SESSION_TTL)
            ),
        },
    )


def _api_account(handler, db_conn, save_lock, query):
    target = (query.get("id") or [""])[-1].strip()
    if not target or len(target) > 128:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_TARGET"})
        return
    with save_lock:
        save = _load_target_save(db_conn, target)
    if save is None:
        _json_reply(handler, 404, {"STATE": "ERROR", "message": "ACCOUNT_NOT_FOUND"})
        return
    b = _balances(save)
    _json_reply(handler, 200, {"STATE": "SUCCESS", "id": target, **b})


def _api_currency(handler, db_conn, save_lock):
    try:
        p = _parse_payload(handler)
        target = str(p.get("target", "")).strip()
        typ = str(p.get("type", "")).strip().upper()
        amount = _request_int(p.get("amount", 0))
    except Exception:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_REQUEST"})
        return

    if not target or len(target) > 128 or typ not in VALID_CURRENCIES:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_REQUEST"})
        return
    if amount <= 0 or amount > MAX_GRANT:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_AMOUNT"})
        return

    try:
        with save_lock:
            db_conn.execute("BEGIN IMMEDIATE")
            save = _load_target_save(db_conn, target)
            if save is None:
                db_conn.rollback()
                _json_reply(handler, 404, {"STATE": "ERROR", "message": "ACCOUNT_NOT_FOUND"})
                return

            key = {
                "GOLD": "gold", "RUBY": "ruby", "BP": "bp",
                "CLOUD": "cloud", "ESSENCE": "essence",
            }[typ]
            before = _balances(save)[key]
            after = before + amount
            if after > 2**63 - 1:
                db_conn.rollback()
                _json_reply(handler, 400, {"STATE": "ERROR", "message": "BALANCE_OVERFLOW"})
                return

            _set_currency(save, typ, after)
            _store_target_save(db_conn, target, save)
            _audit(db_conn, target, "GRANT_" + typ,
                   f"amount={amount} before={before} after={after}", "SUCCESS")
            db_conn.commit()

        _json_reply(handler, 200, {
            "STATE": "SUCCESS", "target": target, "type": typ,
            "amount": amount, "before": before, "after": after,
        })
    except Exception as exc:
        try:
            db_conn.rollback()
        except Exception:
            pass
        _json_reply(handler, 500, {"STATE": "ERROR", "message": "GRANT_FAILED"})


def _api_character(handler, db_conn, save_lock):
    try:
        p = _parse_payload(handler)
        target = str(p.get("target", "")).strip()
        char_id = _request_int(p.get("character_id", 0))
        reason = str(p.get("reason", "ADMIN GIFT")).strip()[:80] or "ADMIN GIFT"
    except Exception:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_REQUEST"})
        return

    if not target or len(target) > 128:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_TARGET"})
        return
    if char_id not in VALID_CHARACTER_IDS:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_CHARACTER"})
        return

    try:
        with save_lock:
            db_conn.execute("BEGIN IMMEDIATE")
            save = _load_target_save(db_conn, target)
            if save is None:
                db_conn.rollback()
                _json_reply(handler, 404, {"STATE": "ERROR", "message": "ACCOUNT_NOT_FOUND"})
                return

            # Use the game's existing mailbox contract:
            # WHAT="CHAR", WHAT_VALUE=<character id>.
            sn = _append_mail(save, "CHAR", str(char_id), reason)
            _store_target_save(db_conn, target, save)
            _audit(db_conn, target, "GRANT_CHARACTER",
                   f"character_id={char_id} mail_sn={sn}", "SUCCESS")
            db_conn.commit()

        _json_reply(handler, 200, {
            "STATE": "SUCCESS", "target": target,
            "character_id": char_id, "mail_sn": sn,
        })
    except Exception:
        try:
            db_conn.rollback()
        except Exception:
            pass
        _json_reply(handler, 500, {"STATE": "ERROR", "message": "GRANT_FAILED"})


def _api_item(handler, db_conn, save_lock, base_dir: Path):
    try:
        p = _parse_payload(handler)
        target = str(p.get("target", "")).strip()
        item_id = _request_int(p.get("item_id", 0))
        quantity = _request_int(p.get("quantity", 1))
        reason = str(p.get("reason", "ADMIN GIFT")).strip()[:80] or "ADMIN GIFT"
    except Exception:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_REQUEST"})
        return

    if not target or len(target) > 128 or quantity < 1 or quantity > 99:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_REQUEST"})
        return

    valid_items = _load_valid_item_ids(base_dir)
    if valid_items is None:
        # Deliberately fail closed rather than inventing item IDs.
        _json_reply(handler, 503, {
            "STATE": "ERROR",
            "message": "ITEM_CATALOG_UNAVAILABLE",
        })
        return
    if item_id not in valid_items:
        _json_reply(handler, 400, {"STATE": "ERROR", "message": "INVALID_ITEM"})
        return

    try:
        with save_lock:
            db_conn.execute("BEGIN IMMEDIATE")
            save = _load_target_save(db_conn, target)
            if save is None:
                db_conn.rollback()
                _json_reply(handler, 404, {"STATE": "ERROR", "message": "ACCOUNT_NOT_FOUND"})
                return

            # Existing gacha-overflow path mails ITEM with WHAT_VALUE=item id.
            # Quantity is represented as multiple mails, matching that proven flow.
            sns = [_append_mail(save, "ITEM", str(item_id), reason) for _ in range(quantity)]
            _store_target_save(db_conn, target, save)
            _audit(db_conn, target, "GRANT_ITEM",
                   f"item_id={item_id} quantity={quantity} mail_count={len(sns)}",
                   "SUCCESS")
            db_conn.commit()

        _json_reply(handler, 200, {
            "STATE": "SUCCESS", "target": target,
            "item_id": item_id, "quantity": quantity,
            "mail_sn": sns[0] if sns else "",
            "mail_sns": sns,
        })
    except Exception:
        try:
            db_conn.rollback()
        except Exception:
            pass
        _json_reply(handler, 500, {"STATE": "ERROR", "message": "GRANT_FAILED"})


def _api_audit(handler, db_conn, save_lock):
    with save_lock:
        rows = db_conn.execute(
            "SELECT ts,target,action,detail,result FROM admin_audit "
            "ORDER BY id DESC LIMIT 200"
        ).fetchall()
    logs = [{
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[0])),
        "target": r[1], "action": r[2], "detail": r[3], "result": r[4],
    } for r in rows]
    _json_reply(handler, 200, {"STATE": "SUCCESS", "logs": logs})


def try_handle_admin_control(handler, db_conn, save_lock, base_dir) -> bool:
    """
    Returns True iff this request belonged to /admin-control and was handled.
    """
    parts = urlsplit(handler.path)
    path = parts.path.rstrip("/") or "/"
    if not (path == "/admin-control" or path.startswith("/admin-control/")):
        return False

    method = handler.command.upper()
    if hasattr(handler, "_admin_control_request_body"):
        del handler._admin_control_request_body
    if method == "POST":
        try:
            _read_body(handler)
        except ValueError:
            handler.close_connection = True
            _json_reply(handler, 400, {
                "STATE": "ERROR",
                "message": "INVALID_REQUEST",
            })
            return True

    # Hard boundary: never trust Host or forwarding headers for this.
    if not _client_is_loopback(handler):
        _json_reply(handler, 403, {"STATE": "ERROR", "message": "LOCALHOST_ONLY"})
        return True

    base_dir = Path(base_dir)

    if path == "/admin-control/login":
        if method not in {"GET", "POST"}:
            _json_reply(handler, 405, {"STATE": "ERROR", "message": "METHOD_NOT_ALLOWED"})
            return True
        _handle_login(handler, method)
        return True

    if not _authorized_or_login(handler, path):
        return True

    try:
        with save_lock:
            _ensure_schema(db_conn)
    except Exception:
        _json_reply(handler, 503, {
            "STATE": "ERROR",
            "message": "SQLITE_DB_REQUIRED",
        })
        return True

    if method == "GET" and parts.path == "/admin-control":
        _reply(handler, 302, b"", headers={"Location": "/admin-control/"})
        return True
    if method == "GET" and path == "/admin-control":
        _serve_frontend(handler, base_dir, "admin_control.html")
        return True
    if method == "GET" and path == "/admin-control/admin.css":
        _serve_frontend(handler, base_dir, "admin.css")
        return True
    if method == "GET" and path == "/admin-control/admin.js":
        _serve_frontend(handler, base_dir, "admin.js")
        return True

    query = parse_qs(parts.query, keep_blank_values=True)

    if method == "GET" and path == "/admin-control/account":
        _api_account(handler, db_conn, save_lock, query)
        return True
    if method == "POST" and path == "/admin-control/grant-currency":
        _api_currency(handler, db_conn, save_lock)
        return True
    if method == "POST" and path == "/admin-control/grant-character":
        _api_character(handler, db_conn, save_lock)
        return True
    if method == "POST" and path == "/admin-control/grant-item":
        _api_item(handler, db_conn, save_lock, base_dir)
        return True
    if method == "GET" and path == "/admin-control/audit":
        _api_audit(handler, db_conn, save_lock)
        return True

    _json_reply(handler, 404, {"STATE": "ERROR", "message": "NOT_FOUND"})
    return True

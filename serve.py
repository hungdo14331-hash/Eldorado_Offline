#!/usr/bin/env python3
"""ELDORADO offline / proxy-capture server.
Usage:  python serve.py [--mode offline|proxy] [--port 8029] [--capture DIR]
"""
import argparse, base64, io, ipaddress, json, logging, math, os, re, secrets, sqlite3, sys, threading, time, traceback, hashlib, datetime
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, parse_qs, quote as urlquote, unquote
from pathlib import Path

from admin_control_backend import try_handle_admin_control
import farm_core
from farm_backend import farm_dispatch
from guild_backend import (guild_dispatch, init_db as init_guild_db,
                           roll_lunar_lucky_rewards)

BASE_DIR  = Path(__file__).resolve().parent
WEB_ROOT  = BASE_DIR / "ELDORADO_WEB"
CAP_DIR   = BASE_DIR / "capture"
LIVE_HOST = "https://game.busidol.com"
SRV_PORT = 8029  # set from --port in main(); kept dynamic so HTML/handler
                # rewrites point at the SAME port this server actually binds.
UNIQ_ID = "ELDORADO_OFFLINE_0001"  # account id returned by check_black_list_db
                                    # stub; override per instance via --uniq-id

# Multi-account / multi-user mode (--db busidol.db):
#   DB_FILE != None -> saves are stored in SQLite by account id. With
#                      REQUIRE_LOGIN, routing comes only from the opaque
#                      server-side session issued by the login page; legacy
#                      HOST_ID / UNIQ_ID fields remain wire data only.
#   WIRE_IDENTITY (--wire-identity): one browser profile = one cookie, so two
#                      game windows logged in as different accounts fight over
#                      the same session. When on, a request whose wire
#                      HOST_ID/UNIQ_ID names an EXISTING account runs as that
#                      account instead; otherwise falls back to the session.
#                      Only for a local single-player server: any client that
#                      can reach the port can then name any account.
DB_FILE = None
DB_CONN = None
REQUIRE_LOGIN = False
WIRE_IDENTITY = False
ADMIN_KEY = secrets.token_hex(32)  # legacy only; listener dispatch hides /admin
AUTH_SESSION_TTL = 7 * 86400
AUTH_SESSIONS = {}  # opaque token -> (account id, expires_at); reset on restart
# ThreadingHTTPServer gives every request its OWN thread, so thread-local is a
# safe per-request scratchpad for "which authenticated account is talking"
# and the request Host used only for legacy base-url rewriting.
_tl = threading.local()

TODAY = time.strftime("%Y-%m-%d")
NOW_EPOCH = str(int(time.time() * 1000))

STATIC_EXT = {".js",".css",".png",".jpg",".jpeg",".gif",".svg",".ico",
              ".woff",".woff2",".ttf",".otf",".eot",
              ".mp3",".wav",".ogg",".m4a",
              ".webp",".bmp",".fnt",".xml",".plist",".atlas",".bin"}

IMAGE_EXT = {".png",".jpg",".jpeg",".gif",".webp",".bmp",".svg",".ico"}

# Art the original game never published, redirected to sibling art that does
# exist. Keyed by path tail so both the ELDORADO_WEB/image and the
# ELDORADO_WEB/source_20240722/image roots match, and the alias is served from
# the same root the client asked for. boss_img1.png (the World Boss, stage 1)
# 404s on game.busidol.com and is absent from every local project copy, so the
# boss ranking screen used to draw a blank spot for it.
ASSET_ALIAS = {
    "/image/ui/21_boss/boss_img1.png": "/image/ui/21_boss/boss_img2.png",
}

# 1x1 RGBA PNG (valid CRCs) served for missing images instead of a 404.
# The client counts battle art via img.onload only; a 404 fires onerror, so
# cur never reaches tot, interval_test_our re-arms every 100ms forever and the
# match hangs before it starts. A decodable PNG makes onload fire so the game
# continues and just draws nothing for that one frame.
# ponytail: missing art renders invisible rather than as a visible error tile;
# add a logged placeholder tile if missing assets ever need to be spotted in UI.
BLANK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNg"
    "YGBgAAAABQABeqhXUAAAAABJRU5ErkJggg==")

LOG = logging.getLogger("serve")
fh  = logging.FileHandler(BASE_DIR / "serve.log", encoding="utf-8", delay=True)
fh.setFormatter(logging.Formatter("%(message)s"))
LOG.addHandler(fh)
LOG.setLevel(logging.INFO)

MODE = "offline"
CAP_DIR.mkdir(parents=True, exist_ok=True)

# ---------- persistent save (offline progress) ----------

SAVE_FILE = BASE_DIR / "offline_save.json"

# ThreadingHTTPServer handles PHP requests concurrently; the save file used
# to be read/written with no locks, so a torn read (json.loads of a file a
# sibling thread was mid-write) returned {} and the next handler OVERWROTE the
# whole save with just its own fields -- silently wiping hard_mode/quest/
# mails/bp/item. RLock + read-retry makes every access atomic.
SAVE_LOCK = threading.RLock()
DAYDUNGEON_FREE_TICKET_DAY = 30
FOUR_GODS_PERSUASION_COST = 20

# The client blocks Cloud Garden while the current timestamp is between
# RANKING_SHOW_TIMESTAMP and RANKING_PLAY_TIMESTAMP.  The live schedule is
# every Monday 01:00–07:00 in GMT+9; keep the most recent window in the past
# outside that interval so normal Match clicks are not mistaken for reset.
CLOUD_RANKING_TZ = datetime.timezone(datetime.timedelta(hours=9))


def cloud_ranking_reset_window(now_epoch: float | None = None) -> tuple[int, int, str, str]:
    """Return the active/latest weekly reset window for the Cloud client.

    The tuple is ``(start_epoch, end_epoch, start_datetime, end_datetime)``.
    During Monday 01:00–07:00 (GMT+9) the returned window contains *now*;
    otherwise it is the most recent completed window, so the client permits
    entry.
    """
    if now_epoch is None:
        now_epoch = time.time()
    current = datetime.datetime.fromtimestamp(float(now_epoch), CLOUD_RANKING_TZ)
    monday = (current - datetime.timedelta(days=current.weekday())).replace(
        hour=1, minute=0, second=0, microsecond=0
    )
    start = monday
    end = start + datetime.timedelta(hours=6)
    if current < start:
        start -= datetime.timedelta(days=7)
        end -= datetime.timedelta(days=7)
    start_epoch = int(start.timestamp())
    end_epoch = int(end.timestamp())
    return start_epoch, end_epoch, start.strftime("%Y%m%d%H%M%S"), end.strftime("%Y%m%d%H%M%S")


def issue_auth_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    with SAVE_LOCK:
        for old, (_, expires_at) in list(AUTH_SESSIONS.items()):
            if expires_at <= now:
                AUTH_SESSIONS.pop(old, None)
        AUTH_SESSIONS[token] = (str(user_id), now + AUTH_SESSION_TTL)
    return token


def authenticated_user(cookie_header: str) -> str:
    m = re.search(r"(?:^|;\s*)dol_session=([^;]+)", cookie_header or "")
    if not m:
        return ""
    token = m.group(1)
    now = int(time.time())
    with SAVE_LOCK:
        session = AUTH_SESSIONS.get(token)
        if not session or session[1] <= now:
            AUTH_SESSIONS.pop(token, None)
            return ""
        return session[0]

def _norm_save(s: dict) -> dict:
    """repair legacy saves whose DATA1/2/3 (and ETC) were stored
    percent-encoded (client encodeURIComponent). Hand them back to the
    client / the engine's STORAGE.load_n_parse_cnm in plain CSV form."""
    for k in ("DATA1", "DATA2", "DATA3", "ETC"):
        v = s.get(k)
        if isinstance(v, str) and "%" in v:
            try:
                s[k] = unquote(v)
            except Exception:
                pass
    return s

def load_save() -> dict:
    if DB_FILE:
        s = db_load_save(_uid())
        return s if s is not None else {}
    with SAVE_LOCK:
        for _ in range(10):
            try:
                if SAVE_FILE.exists():
                    return _norm_save(json.loads(SAVE_FILE.read_text(encoding="utf-8")))
            except Exception:
                time.sleep(0.02)
        LOG.info("save read failed")
    return {}

def store_save(payload: dict):
    if DB_FILE:
        db_store_save(_uid(), payload)
        return
    tmp = SAVE_FILE.with_name(SAVE_FILE.name + ".tmp")
    with SAVE_LOCK:
        try:
            data = json.dumps(payload, ensure_ascii=False)
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
            os.replace(tmp, SAVE_FILE)
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            LOG.info("save write failed")

def mutate_save(fn) -> dict:
    """Atomically read-modify-write the save: fn(s) edits the loaded dict,
    then the whole thing is written back under one lock."""
    with SAVE_LOCK:
        s = load_save()
        fn(s)
        store_save(s)
        return s

# ---------- base URL (Host-header aware) ----------

def base_url() -> str:
    """The origin the current request was REALLY addressed to (Host header),
    so JS/CSS/HTML we rewrite point at the machine/tunnel the friend used,
    not hardcoded localhost. Defaults to localhost:port (single-machine play).
    HTTPS is detected via the X-Forwarded-Proto header (set by the
    cloudflared tunnel) so rewritten URLs keep https:// under the tunnel
    -- otherwise Safari blocks the http:// calls as mixed content."""
    host = getattr(_tl, "host", None)
    if host:
        scheme = getattr(_tl, "scheme", "http")
        return f"{scheme}://{host}"
    return f"http://localhost:{SRV_PORT}"

# ---------- multi-account SQLite store (--db) ----------

def init_db(path):
    """Create/open the multi-account SQLite database:
        accounts(id TEXT PK, pw_hash TEXT)   - login credentials
        saves   (id TEXT PK, payload TEXT)   - one full save JSON per account
    """
    global DB_FILE, DB_CONN
    DB_FILE = Path(path)
    DB_CONN = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    with SAVE_LOCK:
        DB_CONN.execute("PRAGMA busy_timeout=5000")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, pw_hash TEXT)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS saves (id TEXT PRIMARY KEY, payload TEXT)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS moss_moon_wallet_ops (user_id TEXT NOT NULL, action_id TEXT NOT NULL, request_fingerprint TEXT NOT NULL, response_json TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY (user_id, action_id))")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS item_gacha_bp_ops (user_id TEXT NOT NULL, request_id TEXT NOT NULL, type_num INTEGER NOT NULL, response_json TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY (user_id, request_id))")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS sky_sessions (nonce TEXT PRIMARY KEY, user_id TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS sky_leaderboard (user_id TEXT PRIMARY KEY, clear_wave INTEGER NOT NULL DEFAULT 0, achieved_at INTEGER NOT NULL)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS cloud_leaderboard (user_id TEXT PRIMARY KEY, best_score INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, user_name TEXT NOT NULL DEFAULT '', team TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT 'WEB')")
        # World Boss 2026: one shared boss row per BOSS_DESIGN index, the damage
        # board, and the match sessions that make enter/update retry-safe. All
        # three live in this same file as `saves`, so a battle update and the
        # ticket/gold charge commit together (see _boss_persist).
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS boss_state (boss_num INTEGER PRIMARY KEY, cur_hp INTEGER NOT NULL DEFAULT 0, max_hp INTEGER NOT NULL DEFAULT 0, season_start INTEGER NOT NULL DEFAULT 0, season_end INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS boss_damage (boss_num INTEGER NOT NULL, user_id TEXT NOT NULL, total_damage INTEGER NOT NULL DEFAULT 0, user_name TEXT NOT NULL DEFAULT '', team TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (boss_num, user_id))")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS boss_sessions (kind TEXT NOT NULL, user_id TEXT NOT NULL, session_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', opened_at INTEGER NOT NULL DEFAULT 0, consumed_at INTEGER, expires_at INTEGER NOT NULL DEFAULT 0, request_fingerprint TEXT NOT NULL DEFAULT '', result_fingerprint TEXT NOT NULL DEFAULT '', meta_json TEXT NOT NULL DEFAULT '', response_json TEXT NOT NULL DEFAULT '', PRIMARY KEY (kind, user_id, session_id))")
        # PvP 2025 uses a server-issued nonce (unlike the legacy Boss wire
        # format), so every match has an independently replayable durable row.
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS pvp_leaderboard (user_id TEXT PRIMARY KEY, total_score INTEGER NOT NULL DEFAULT 0, best_score INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, user_name TEXT NOT NULL DEFAULT '', team TEXT NOT NULL DEFAULT '', item TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT 'WEB', level INTEGER NOT NULL DEFAULT 1, tower_hp INTEGER NOT NULL DEFAULT 0, tower_level INTEGER NOT NULL DEFAULT 0, missile_ap INTEGER NOT NULL DEFAULT 0, missile_level INTEGER NOT NULL DEFAULT 0, missile_tick INTEGER NOT NULL DEFAULT 0)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS pvp_sessions (nonce TEXT PRIMARY KEY, user_id TEXT NOT NULL, opponent_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL DEFAULT 0, consumed_at INTEGER, player_team TEXT NOT NULL DEFAULT '', opponent_json TEXT NOT NULL DEFAULT '', enter_response_json TEXT NOT NULL DEFAULT '', response_json TEXT NOT NULL DEFAULT '')")
        # PvP Classic keeps its legacy wire protocol (no MATCH_NONCE), so it
        # has a separate board/session store and an internal session id.  The
        # id is never sent to the old client, but lets us consume one active
        # match at a time and replay a completed response safely.
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS pvp_classic_leaderboard (user_id TEXT PRIMARY KEY, total_score INTEGER NOT NULL DEFAULT 0, best_score INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, user_name TEXT NOT NULL DEFAULT '', team TEXT NOT NULL DEFAULT '', item TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT 'WEB', level INTEGER NOT NULL DEFAULT 1, tower_hp INTEGER NOT NULL DEFAULT 0, tower_level INTEGER NOT NULL DEFAULT 0, missile_ap INTEGER NOT NULL DEFAULT 0, missile_level INTEGER NOT NULL DEFAULT 0, missile_tick INTEGER NOT NULL DEFAULT 0)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS pvp_classic_sessions (session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, opponent_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL DEFAULT 0, consumed_at INTEGER, player_team TEXT NOT NULL DEFAULT '', opponent_json TEXT NOT NULL DEFAULT '', enter_response_json TEXT NOT NULL DEFAULT '', response_json TEXT NOT NULL DEFAULT '', result_fingerprint TEXT NOT NULL DEFAULT '')")
        # Safety net for the one-open-match-per-player rule: the code already
        # keeps a single ACTIVE row, the index makes a bug fail loudly instead
        # of silently charging twice.
        DB_CONN.execute("CREATE UNIQUE INDEX IF NOT EXISTS boss_sessions_one_active ON boss_sessions (kind, user_id) WHERE status='ACTIVE'")
        DB_CONN.execute("CREATE INDEX IF NOT EXISTS boss_sessions_recent ON boss_sessions (kind, user_id, status, consumed_at)")
        DB_CONN.execute("CREATE UNIQUE INDEX IF NOT EXISTS pvp_sessions_one_active ON pvp_sessions (user_id) WHERE status='ACTIVE'")
        DB_CONN.execute("CREATE INDEX IF NOT EXISTS pvp_sessions_owner_status ON pvp_sessions (user_id, status, created_at)")
        DB_CONN.execute("CREATE UNIQUE INDEX IF NOT EXISTS pvp_classic_sessions_one_active ON pvp_classic_sessions (user_id) WHERE status='ACTIVE'")
        DB_CONN.execute("CREATE INDEX IF NOT EXISTS pvp_classic_sessions_owner_status ON pvp_classic_sessions (user_id, status, created_at)")
        # Guild thường (không phải Guild Boss): bảng guild, thành viên, hồ sơ
        # xin vào, và chat. "Mỗi người tối đa 1 guild" và "tên guild là duy
        # nhất" chặn bằng PRIMARY KEY nên bug sẽ nổ lên chứ không im lặng.
        init_guild_db(DB_CONN, SAVE_LOCK)
        DB_CONN.commit()


def sky_record_start(user_id, nonce):
    """Issue one active Sky run; an older run for the same account expires."""
    if not DB_CONN or not user_id or not nonce:
        return
    with SAVE_LOCK:
        DB_CONN.execute("UPDATE sky_sessions SET consumed=1 WHERE user_id=? AND consumed=0", (user_id,))
        DB_CONN.execute("INSERT OR REPLACE INTO sky_sessions (nonce,user_id,consumed,created_at) VALUES (?,?,0,?)",
                        (nonce, user_id, int(time.time())))
        DB_CONN.commit()


def sky_record_result(user_id, nonce, wave, result):
    """Consume a run once and persist a best clear wave."""
    if not DB_CONN or not user_id or not nonce:
        return False
    with SAVE_LOCK:
        row = DB_CONN.execute("SELECT user_id, consumed FROM sky_sessions WHERE nonce=?", (nonce,)).fetchone()
        if not row or row[0] != user_id or row[1]:
            return False
        DB_CONN.execute("UPDATE sky_sessions SET consumed=1 WHERE nonce=?", (nonce,))
        if str(result).upper() == "W":
            now = int(time.time())
            DB_CONN.execute("INSERT INTO sky_leaderboard (user_id,clear_wave,achieved_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET clear_wave=MAX(clear_wave, excluded.clear_wave), achieved_at=CASE WHEN excluded.clear_wave > clear_wave THEN excluded.achieved_at ELSE achieved_at END",
                            (user_id, max(0, int(wave)), now))
        DB_CONN.commit()
        return True


def sky_ranking(limit=50):
    if not DB_CONN:
        return []
    with SAVE_LOCK:
        rows = DB_CONN.execute("SELECT user_id, clear_wave, achieved_at FROM sky_leaderboard ORDER BY clear_wave DESC, achieved_at ASC, user_id ASC LIMIT ?", (limit,)).fetchall()
    return [{"user_id": row[0], "clear_wave": row[1], "achieved_at": row[2]} for row in rows]


def _cloud_ranking_rows(uid, save_obj, user_name, team, limit=50):
    """Persist the current best score and return the shared Cloud board rows."""
    score = max(0, int(float(str(save_obj.get("cloud_score", "0") or 0))))
    now = int(time.time())
    if DB_CONN:
        if score > 0:
            DB_CONN.execute(
                """INSERT INTO cloud_leaderboard
                   (user_id,best_score,updated_at,user_name,team,platform)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     best_score=MAX(cloud_leaderboard.best_score, excluded.best_score),
                     updated_at=CASE WHEN excluded.best_score > cloud_leaderboard.best_score
                                     THEN excluded.updated_at ELSE cloud_leaderboard.updated_at END,
                     user_name=excluded.user_name, team=excluded.team,
                     platform=excluded.platform""",
                (uid, score, now, user_name or uid, team or "", "WEB"),
            )
            DB_CONN.commit()
        return DB_CONN.execute(
            "SELECT user_id,best_score,updated_at,user_name,team,platform "
            "FROM cloud_leaderboard ORDER BY best_score DESC,updated_at ASC,user_id ASC LIMIT ?",
            (limit,),
        ).fetchall()

    board = save_obj.setdefault("cloud_leaderboard", {})
    current = board.get(uid) or {}
    if score > 0 and score >= int(float(str(current.get("best_score", 0) or 0))):
        board[uid] = {
            "user_id": uid,
            "best_score": max(score, int(float(str(current.get("best_score", 0) or 0)))),
            "updated_at": now if score > int(float(str(current.get("best_score", 0) or 0))) else int(current.get("updated_at", now)),
            "user_name": user_name or uid,
            "team": team or "",
            "platform": "WEB",
        }
        store_save(save_obj)
    rows = []
    for entry in board.values():
        rows.append((
            str(entry.get("user_id", "")),
            max(0, int(float(str(entry.get("best_score", 0) or 0)))),
            int(float(str(entry.get("updated_at", 0) or 0))),
            str(entry.get("user_name", "") or entry.get("user_id", "")),
            str(entry.get("team", "") or ""),
            str(entry.get("platform", "WEB") or "WEB"),
        ))
    rows.sort(key=lambda row: (-row[1], row[2], row[0]))
    return rows[:limit]


def _cloud_ranking_payload(uid, save_obj, rows):
    # The legacy client reserves index 0 and draws rows from index 1 onward.
    # Without this placeholder, a one-row board produces e=0 in drawRanks()
    # and the visible table stays empty even though the response is valid.
    ranking = [{"RANKING": 0, "NAME": "", "PLATFORM": "", "SCORE": 0, "TEAM": ""}]
    mine = None
    for pos, row in enumerate(rows, 1):
        ranking.append({
            "RANKING": pos,
            "NAME": row[3] or row[0],
            "PLATFORM": row[5] or "WEB",
            "SCORE": str(row[1]),
            "TEAM": row[4] or "",
        })
        if row[0] == uid:
            mine = (pos, row)
    score = mine[1][1] if mine else max(0, int(float(str(save_obj.get("cloud_score", "0") or 0))))
    rank = mine[0] if mine else 0
    return ranking, score, rank

# ---------- WORLD BOSS 2026 (BOSS_2026/*.php) ----------
# One shared boss per instance: every account drains the same HP pool and the
# board ranks total damage. Nothing the client posts (SCORE / RESULT / ETC) is
# server-authoritative -- see _boss_handle_update for the checks.
#
# OFFLINE POLICY (our own rules, NOT a claim about the original Eldorado server)
# and LEGACY-INFORMED DEFAULTs:
#  * BOSS_MAX_HP        hp of the active boss. Default = the value the client
#                       itself carries (BOSS_DESIGN[1].max_hp = 2e12); we did
#                       NOT invent a balance number. env BOSS_MAX_HP overrides.
#  * BOSS_SEASON_DAYS   a season is 7 days from the moment the state row is
#                       created/reset. When it runs out the boss refills and its
#                       damage board is cleared (lifecycle, not a client hack).
#  * BOSS_DAILY_TICKETS 10/day. Evidence: S_ATTENDANCE.init (the daily
#                       first-entry scene) does S_RANKING_BOSS.tiket=10 and
#                       pushes it with Boss/update_boss_tiket_to_server.php
#                       ("first access today, 10 charged"). The bundle never
#                       states the 2026 event reuses that number -> default.
#  * gold entry ladder  S_RANKING_BOSS.get_fee_gold() verbatim: 0 for enters
#                       0-10, then 3000 / 5000 / 7000 / 10000. The client burns
#                       its free tickets first, so the ladder is the "paid
#                       entries after the daily 10" price list.
#  * BOSS_SESSION_TTL   30 min. A battle is a canvas fight of a minute or two;
#                       the session only has to outlive one round-trip plus
#                       retries. No bundle evidence for the exact battle length.
BOSS_ACTIVE_NUM = 1                      # BOSS_DESIGN index the board fights
# Verbatim from the client's own table (BOSS_DESIGN[i].max_hp; slot 4 is the
# empty {} in the bundle). Kept as a table rather than one number so a state
# row for another index can never pick a made-up HP.
BOSS_DESIGN_MAX_HP = {1: 2_000_000_000_000, 2: 35_000_000_000,
                      3: 50_000_000_000, 5: 8_000_000_000,
                      6: 8_000_000_000, 7: 8_000_000_000}
BOSS_MAX_HP = 0                          # 0 = keep BOSS_DESIGN_MAX_HP
BOSS_SEASON_DAYS = 7
BOSS_DAILY_TICKETS = 10
BOSS_SESSION_TTL = 1800
BOSS_RETRY_SECS = 300                    # §9 stale-retry window, see _boss_retry_secs
BOSS_GOLD_LADDER = ((10, 0), (30, 3000), (50, 5000), (70, 7000), (10 ** 9, 10000))
BOSS_RANK_LIMIT = 50                     # MAX_GLOBAL_RANK_BOSS in the bundle
BOSS_RESULTS = ("승", "패")              # canonical win / lose tokens

def _boss_result_token(v: str) -> str:
    """Repair the client's double-encoded result token, or pass it through.

    The shipped bundle stores its Korean literals as the UTF-8 encoding of the
    latin-1 misreading of the original bytes, so a real win goes on the wire as
    "ìŠ¹" (U+00EC U+008A U+00B9) and a real loss as "íŒ¨" (U+00ED U+008C U+00A8)
    -- verified live: the UI posted RESULT=<mojibake> and the request was
    rejected as "bad RESULT" until this normalisation was added. Undoing one
    latin-1 round-trip maps both the shipped literal and a hypothetical
    corrected bundle onto the same canonical token."""
    try:
        fixed = v.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return v
    return fixed or v
BOSS_KIND = "BOSS_2026"                  # match-session kind (PvP will differ)
BOSS_DOC_SUFFIX = ".boss.json"           # JSON-mode sidecar, next to the save

def _int(v, default=0) -> int:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default

def _boss_env_int(name, default) -> int:
    """Ops/test override hook: the env wins over the module default."""
    try:
        v = os.environ.get(name)
        return int(v) if v not in (None, "") else int(default)
    except Exception:
        return int(default)

def _boss_now() -> int:
    """Epoch seconds. A separate seam so the season-expiry test can fast
    forward time without touching the system clock."""
    return int(time.time())

def _boss_max_hp(boss_num) -> int:
    override = _boss_env_int("BOSS_MAX_HP", 0) or BOSS_MAX_HP
    if override > 0:
        return override
    return BOSS_DESIGN_MAX_HP.get(int(boss_num), BOSS_DESIGN_MAX_HP[BOSS_ACTIVE_NUM])

def _boss_season_secs() -> int:
    return max(1, _boss_env_int("BOSS_SEASON_DAYS", BOSS_SEASON_DAYS)) * 86400

def _boss_tickets_per_day() -> int:
    return max(0, _boss_env_int("BOSS_DAILY_TICKETS", BOSS_DAILY_TICKETS))

def _boss_session_ttl() -> int:
    return max(60, _boss_env_int("BOSS_SESSION_TTL", BOSS_SESSION_TTL))

def _boss_retry_secs() -> int:
    """§9: how long a stale result retry stays recognizable while a NEWER match
    is already open. The wire carries no nonce, so the only usable signal is
    "this exact result was consumed moments ago"; too long a window would
    swallow a genuine repeat (a loss posts the same SCORE every time)."""
    return max(30, _boss_env_int("BOSS_RETRY_SECS", BOSS_RETRY_SECS))

def _boss_gold_fee(enter_count) -> int:
    n = max(0, _int(enter_count, 0))
    for hi, fee in BOSS_GOLD_LADDER:
        if n <= hi:
            return fee
    return BOSS_GOLD_LADDER[-1][1]

def _boss_kind(boss_num) -> str:
    """Session kind = match type + boss, so the one-ACTIVE-session-per-user
    rule stays per boss as well."""
    return f"{BOSS_KIND}:{int(boss_num)}"

def _boss_key(boss_num, user_id) -> str:
    return f"{int(boss_num)}|{user_id}"

def _boss_err(code, msg, extra=None):
    d = {"STATE": "ERROR", "CODE": str(code), "ERROR_MESSAGE": str(msg)}
    if extra:
        d.update(extra)
    return 200, json.dumps(d, ensure_ascii=False)

def _boss_doc_path() -> Path:
    """JSON mode keeps the shared boss document beside the instance save
    (save_anh.json -> save_anh.boss.json) so two instances reading different
    saves do not share one boss."""
    return SAVE_FILE.with_name(SAVE_FILE.stem + BOSS_DOC_SUFFIX)

def _boss_session_row(r) -> dict:
    try:
        meta = json.loads(r[9]) if r[9] else {}
    except Exception:
        meta = {}
    try:
        resp = json.loads(r[10]) if r[10] else None
    except Exception:
        resp = None
    return {"kind": r[0], "user_id": r[1], "session_id": r[2], "status": r[3],
            "opened_at": _int(r[4], 0), "consumed_at": _int(r[5], 0),
            "expires_at": _int(r[6], 0), "request_fingerprint": r[7] or "",
            "result_fingerprint": r[8] or "", "meta": meta, "response": resp}

def _boss_doc_load() -> dict:
    """The whole shared boss document: {"state":{}, "damage":{}, "sessions":[]}.

    --db mode reads the three boss_* tables (same SQLite file as the saves, so
    a caller inside BEGIN IMMEDIATE sees one consistent snapshot); JSON mode
    reads the sidecar file. Both are normalized so callers never trip over a
    missing key."""
    if DB_FILE:
        st = {}
        for r in DB_CONN.execute("SELECT boss_num,cur_hp,max_hp,season_start,season_end,updated_at FROM boss_state"):
            st[str(int(r[0]))] = {"boss_num": int(r[0]), "cur_hp": _int(r[1], 0),
                                  "max_hp": _int(r[2], 0), "season_start": _int(r[3], 0),
                                  "season_end": _int(r[4], 0), "updated_at": _int(r[5], 0)}
        dm = {}
        for r in DB_CONN.execute("SELECT boss_num,user_id,total_damage,user_name,team,platform,updated_at FROM boss_damage"):
            dm[_boss_key(r[0], r[1])] = {"boss_num": int(r[0]), "user_id": r[1] or "",
                                         "total_damage": _int(r[2], 0), "user_name": r[3] or "",
                                         "team": r[4] or "", "platform": r[5] or "",
                                         "updated_at": _int(r[6], 0)}
        ss = [_boss_session_row(r) for r in DB_CONN.execute(
            "SELECT kind,user_id,session_id,status,opened_at,consumed_at,expires_at,"
            "request_fingerprint,result_fingerprint,meta_json,response_json FROM boss_sessions")]
        return {"state": st, "damage": dm, "sessions": ss}
    try:
        doc = json.loads(_boss_doc_path().read_text(encoding="utf-8"))
    except Exception:
        doc = {}
    if not isinstance(doc, dict):
        doc = {}
    st = doc.get("state") if isinstance(doc.get("state"), dict) else {}
    dm = doc.get("damage") if isinstance(doc.get("damage"), dict) else {}
    ss = doc.get("sessions") if isinstance(doc.get("sessions"), list) else []
    return {"state": st, "damage": dm, "sessions": ss}

def _boss_doc_store(doc):
    """Persist the whole document. --db mode runs inside the caller's
    transaction (no commit here); JSON mode replaces the sidecar atomically."""
    if DB_FILE:
        DB_CONN.execute("DELETE FROM boss_state")
        for k, st in (doc.get("state") or {}).items():
            DB_CONN.execute("INSERT INTO boss_state (boss_num,cur_hp,max_hp,season_start,season_end,updated_at) VALUES (?,?,?,?,?,?)",
                            (int(st.get("boss_num", k) or 0), _int(st.get("cur_hp"), 0),
                             _int(st.get("max_hp"), 0), _int(st.get("season_start"), 0),
                             _int(st.get("season_end"), 0), _int(st.get("updated_at"), 0)))
        DB_CONN.execute("DELETE FROM boss_damage")
        for d in (doc.get("damage") or {}).values():
            DB_CONN.execute("INSERT OR REPLACE INTO boss_damage (boss_num,user_id,total_damage,user_name,team,platform,updated_at) VALUES (?,?,?,?,?,?,?)",
                            (int(d.get("boss_num", 0) or 0), str(d.get("user_id") or ""),
                             _int(d.get("total_damage"), 0), str(d.get("user_name") or ""),
                             str(d.get("team") or ""), str(d.get("platform") or ""),
                             _int(d.get("updated_at"), 0)))
        DB_CONN.execute("DELETE FROM boss_sessions")
        for s in (doc.get("sessions") or []):
            DB_CONN.execute("INSERT OR REPLACE INTO boss_sessions (kind,user_id,session_id,status,opened_at,consumed_at,expires_at,request_fingerprint,result_fingerprint,meta_json,response_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (str(s.get("kind") or ""), str(s.get("user_id") or ""),
                             str(s.get("session_id") or ""), str(s.get("status") or ""),
                             _int(s.get("opened_at"), 0), _int(s.get("consumed_at"), 0) or None,
                             _int(s.get("expires_at"), 0), str(s.get("request_fingerprint") or ""),
                             str(s.get("result_fingerprint") or ""),
                             json.dumps(s.get("meta") or {}, ensure_ascii=False),
                             json.dumps(s.get("response"), ensure_ascii=False) if s.get("response") is not None else ""))
        return
    p = _boss_doc_path()
    tmp = p.with_name(p.name + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        LOG.info("boss doc write failed")

def _boss_tx_begin():
    """Take the SQLite write lock (--db mode). sqlite3 opens a deferred
    transaction before DML, so an implicit one has to be closed first or
    BEGIN IMMEDIATE raises 'cannot start a transaction within a transaction'."""
    if DB_FILE:
        if DB_CONN.in_transaction:
            DB_CONN.commit()
        DB_CONN.execute("BEGIN IMMEDIATE")

def _boss_persist(doc, save_obj=None, uid=None):
    """Commit the boss document, and optionally the player's save row, as one
    unit.

    --db: boss state + sessions + damage + the saves row all live in the SAME
    SQLite file, so one BEGIN IMMEDIATE .. COMMIT makes a battle update atomic.
    JSON: the boss sidecar and the save file are two different files -- there is
    no cross-file transaction, so the caller orders the writes so a retry heals
    the gap (see _boss_handle_enter) and the crash window is documented."""
    if DB_FILE:
        _boss_tx_begin()
        try:
            _boss_doc_store(doc)
            if save_obj is not None:
                DB_CONN.execute("INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                                (uid or _uid(), json.dumps(save_obj, ensure_ascii=False)))
            DB_CONN.commit()
        except Exception:
            DB_CONN.rollback()
            raise
        return
    if save_obj is not None:
        _boss_doc_store(doc)      # session/state first: a crash here leaves a
        store_save(save_obj)      # replayable entry, never a double charge
        return
    _boss_doc_store(doc)

def _boss_state_for(doc, boss_num, now):
    """The current state row for `boss_num`, reset when its season ran out.
    Returns (state, created). Expiring also clears that boss' damage board and
    retires its open sessions, so a new season never inherits old numbers."""
    key = str(int(boss_num))
    st = (doc.get("state") or {}).get(key)
    if st is not None and now < _int(st.get("season_end"), 0):
        return st, False
    mx = _boss_max_hp(boss_num)
    st = {"boss_num": int(boss_num), "cur_hp": mx, "max_hp": mx,
          "season_start": now, "season_end": now + _boss_season_secs(),
          "updated_at": now}
    doc.setdefault("state", {})[key] = st
    for k in [k for k, d in (doc.get("damage") or {}).items()
              if _int(d.get("boss_num"), 0) == int(boss_num)]:
        doc["damage"].pop(k, None)
    for s in (doc.get("sessions") or []):
        if s.get("status") == "ACTIVE" and _int((s.get("meta") or {}).get("boss_num"), 0) == int(boss_num):
            s["status"] = "EXPIRED"
    return st, True

def _boss_expire_sessions(doc, now) -> int:
    n = 0
    for s in (doc.get("sessions") or []):
        if s.get("status") == "ACTIVE" and now >= _int(s.get("expires_at"), 0):
            s["status"] = "EXPIRED"
            n += 1
    return n

def _boss_prune_sessions(doc, now):
    keep = [s for s in (doc.get("sessions") or [])
            if _int(s.get("opened_at"), 0) >= now - 86400]
    doc["sessions"] = keep[-400:]

def _boss_active_session(doc, boss_num, user_id):
    kind = _boss_kind(boss_num)
    for s in (doc.get("sessions") or []):
        if s.get("kind") == kind and s.get("user_id") == user_id and s.get("status") == "ACTIVE":
            return s
    return None

def _boss_recent_consumed(doc, boss_num, user_id, fp, now, max_age=0):
    """Most recent CONSUMED session for this user whose result fingerprint is
    `fp` -- the late-retry guard.

    A retried POST for match A can arrive after the player already opened match
    B; the wire carries no nonce (RUN_COUNT/USER_KEY/IS_SYNC/VERSION are
    per-request transport metadata, not match identity), so the only usable
    signal is "this exact result was already consumed a moment ago".
    `max_age` > 0 narrows the window for the §9 case where a newer session is
    already open; 0 keeps the long window used when no match is open."""
    if not fp:
        return None
    kind = _boss_kind(boss_num)
    window = max_age if max_age > 0 else max(_boss_session_ttl(), 21600)
    best = None
    for s in (doc.get("sessions") or []):
        if (s.get("kind") == kind and s.get("user_id") == user_id
                and s.get("status") == "CONSUMED" and s.get("result_fingerprint") == fp
                and now - _int(s.get("consumed_at"), 0) <= window):
            if best is None or _int(s.get("consumed_at"), 0) > _int(best.get("consumed_at"), 0):
                best = s
    return best

def _boss_fingerprint(body) -> str:
    """Canonical hash of the RESULT-bearing fields only.

    IS_SYNC / USER_KEY / RUN_COUNT / VERSION are appended by the PHPAjax
    wrapper to EVERY request (RUN_COUNT is a per-day counter that does not move
    between the enter, the update and a retry), so they must never enter a
    fingerprint -- a genuine HTTP retry would otherwise look like a new match.

    RESULT is normalised to the canonical token before hashing, so the shipped
    double-encoded literal and a corrected bundle hash identically; invalid
    tokens pass through unchanged and are still rejected by validation."""
    parts = ["RESULT=" + _boss_result_token(str(body.get("RESULT", "") or "").strip())]
    parts += [f"{k}={str(body.get(k, '') or '').strip()}"
              for k in ("SCORE", "TEAM", "ITEM", "ETC")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

def _boss_enter_fingerprint(body) -> str:
    parts = [f"{k}={str(body.get(k, '') or '').strip()}"
             for k in ("MODE", "TEAM", "ITEM")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

def _boss_name(body, save_obj=None, fallback="") -> str:
    n = str(body.get("NAME") or "").strip()
    if n:
        return n[:40]
    if save_obj:
        d1 = (save_obj.get("DATA1") or "").split(",")
        for cand in ((d1[0] if d1 else ""), str(save_obj.get("USER_NAME") or "")):
            cand = str(cand or "").strip()
            if cand:
                return cand[:40]
    return (str(fallback or "").strip() or _uid())[:40]

def _boss_save_team(save_obj) -> str:
    try:
        d1 = (save_obj.get("DATA1") or "").split(",")
        if len(d1) > 14:
            return str(d1[14] or "").strip()
    except Exception:
        pass
    return ""

def _boss_team(body, save_obj=None, fallback="") -> str:
    """The client posts glo.char.get_decks() (comma separated char ids) and the
    board runs extract_character_numbers() over it, which splits on ','. The
    save's DATA1[14] uses ':' separators, so translate before falling back."""
    for cand in (body.get("TEAM"), _boss_save_team(save_obj or {}), fallback):
        t = str(cand or "").strip()
        if not t:
            continue
        if ":" in t and "," not in t:
            t = t.replace(":", ",")
        t = re.sub(r"[^0-9,]", "", t).strip(",")
        if t:
            return t[:120]
    return ""

def _boss_ticket_read(s, today):
    """Ticket + enter counters without writing anything (board reads)."""
    if str(s.get("boss_ticket_day") or "") != today:
        return _boss_tickets_per_day(), 0
    t = max(0, _int(s.get("boss_ticket_left"), 0))
    c = 0 if str(s.get("boss_enter_day") or "") != today else max(0, _int(s.get("boss_enter_count"), 0))
    return t, c

def _boss_ticket_take(s, today):
    """Lazily refill the daily tickets, then report the counters. The enter
    path writes these back with the charge."""
    if str(s.get("boss_ticket_day") or "") != today:
        s["boss_ticket_day"] = today
        s["boss_ticket_left"] = str(_boss_tickets_per_day())
        s["boss_enter_day"] = today
        s["boss_enter_count"] = "0"
    if str(s.get("boss_enter_day") or "") != today:
        s["boss_enter_day"] = today
        s["boss_enter_count"] = "0"
    return max(0, _int(s.get("boss_ticket_left"), 0)), max(0, _int(s.get("boss_enter_count"), 0))

def _boss_rank_rows(doc, boss_num):
    """Deterministic board: total damage desc, then whoever reached their total
    first, then user id. Only users who actually damaged the boss appear."""
    rows = []
    for d in (doc.get("damage") or {}).values():
        if _int(d.get("boss_num"), 0) != int(boss_num):
            continue
        tot = _int(d.get("total_damage"), 0)
        if tot <= 0:
            continue
        rows.append((tot, _int(d.get("updated_at"), 0), str(d.get("user_id") or ""),
                     str(d.get("user_name") or ""), str(d.get("team") or ""),
                     str(d.get("platform") or "")))
    rows.sort(key=lambda r: (-r[0], r[1], r[2]))
    listed = [{"ranking": str(i), "user_name": r[3], "team": r[4],
               "tot_score": str(r[0]), "platform": r[5] or "WEB"}
              for i, r in enumerate(rows[:BOSS_RANK_LIMIT], 1)]
    return listed, rows

def _boss_payload(doc, boss_num, st, user_id, extra=None) -> dict:
    """Everything parse_ranking_info()/the board actually read. ranking_list is
    always an array, every field is always present, and BOSS_NUM is always a
    real BOSS_DESIGN index (else BOSS_DESIGN[NaN].cur_hp throws client-side)."""
    listed, allrows = _boss_rank_rows(doc, boss_num)
    my_rank, my_score = 0, 0
    for i, r in enumerate(allrows, 1):
        if r[2] == user_id:
            my_rank, my_score = i, r[0]
            break
    hp = max(0, _int(st.get("cur_hp"), 0))
    payload = {
        "STATE": "SUCCESS",
        "ranking_list": listed,
        "my_ranking": str(my_rank),
        "TOT_SCORE": str(my_score),
        "BOSS_NUM": str(int(boss_num)),
        "BOSS_HP": str(hp),
        "boss_cur_hp": str(hp),
        "BC_BOSS_2_HP": "0",          # <=0 keeps the client's own max_hp
        "BC_BOSS_3_HP": "0",
        "run_out_time": str(_int(st.get("season_end"), 0)),
        "SERVER_TIME": str(_boss_now()),
    }
    if extra:
        payload.update(extra)
    return payload

def boss_ranking_text() -> str:
    """Board read. The offline instance runs one boss, so the answer (and the
    BOSS_NUM inside it) is always the active index -- the client copies that
    field into S_BOSS.stage, so echoing a requested-but-unknown index would
    make BOSS_DESIGN[stage] undefined and break the screen."""
    bn = BOSS_ACTIVE_NUM
    uid = _uid()
    today = time.strftime("%Y%m%d")
    now = _boss_now()
    with SAVE_LOCK:
        doc = _boss_doc_load()
        st, rolled = _boss_state_for(doc, bn, now)
        expired = _boss_expire_sessions(doc, now)
        s = load_save()
        ticket, count = _boss_ticket_read(s, today)
        payload = _boss_payload(doc, bn, st, uid, {"TICKET": str(ticket),
                                                   "ENTER_COUNT": str(count)})
        if rolled or expired:
            _boss_persist(doc)
    return json.dumps(payload, ensure_ascii=False)

def boss_enter_text(body, uid=None) -> str:
    """Entry: charge once, then remember the answer so a retry cannot charge
    again (§7). HP is never faked back to life: a dead boss refuses entry."""
    uid = uid or _uid()
    mode = str(body.get("MODE", "") or "").strip().upper()
    today = time.strftime("%Y%m%d")
    now = _boss_now()
    with SAVE_LOCK:
        doc = _boss_doc_load()
        bn = BOSS_ACTIVE_NUM
        st, rolled = _boss_state_for(doc, bn, now)
        if rolled:
            _boss_persist(doc)
            LOG.info("  boss season rolled boss_num=%d max_hp=%d", bn, st["max_hp"])
        _boss_expire_sessions(doc, now)

        act = _boss_active_session(doc, bn, uid)
        if act is not None:
            resp = act.get("response")
            if not isinstance(resp, dict) or not resp:
                resp = _boss_payload(doc, bn, st, uid,
                                     {"MODE": str((act.get("meta") or {}).get("mode") or mode),
                                      "MODE_IDLE": "1"})
            LOG.info("  boss enter REPLAY (active session) uid=%s", uid)
            return json.dumps(resp, ensure_ascii=False)

        cur_hp = max(0, _int(st.get("cur_hp"), 0))
        if cur_hp <= 0:
            return json.dumps({"STATE": "ERROR", "CODE": "-104",
                               "ERROR_MESSAGE": "world boss is already defeated",
                               "BOSS_NUM": str(bn), "BOSS_HP": "0",
                               "boss_cur_hp": "0"}, ensure_ascii=False)

        if mode not in ("ENTRY_TICKET", "ENTRY_GOLD"):
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "unknown boss entry mode"},
                              ensure_ascii=False)

        s = load_save()
        d1 = (s.get("DATA1") or "").split(",")
        while len(d1) < 21:
            d1.append("0")
        gold = max(0, _int(d1[1], 0))
        ticket, enter_count = _boss_ticket_take(s, today)
        if mode == "ENTRY_TICKET":
            if ticket < 1:
                return json.dumps({"STATE": "ERROR", "CODE": "-102",
                                   "ERROR_MESSAGE": "no world boss ticket left",
                                   "cur_ticket": "0"}, ensure_ascii=False)
            fee = 0
            ticket -= 1
        else:
            fee = _boss_gold_fee(enter_count)
            if gold < fee:
                return json.dumps({"STATE": "ERROR", "CODE": "-103",
                                   "ERROR_MESSAGE": "not enough gold",
                                   "need_gold": str(fee)}, ensure_ascii=False)
            gold -= fee
            d1[1] = str(gold)
            s["DATA1"] = ",".join(d1)
        enter_count += 1
        s["boss_ticket_day"] = today
        s["boss_ticket_left"] = str(ticket)
        s["boss_enter_day"] = today
        s["boss_enter_count"] = str(enter_count)

        name = _boss_name(body, s)
        team = _boss_team(body, s)
        resp = _boss_payload(doc, bn, st, uid, {
            "MODE": mode, "ENTER_COUNT": str(enter_count),
            "TICKET": str(ticket), "cur_ticket": str(ticket),
            "s_add_gold": str(gold),
            "gold": str(gold),
            "need_gold": str(fee),
        })
        doc.setdefault("sessions", []).append({
            "kind": _boss_kind(bn), "user_id": uid,
            "session_id": secrets.token_hex(8), "status": "ACTIVE",
            "opened_at": now, "consumed_at": 0,
            "expires_at": now + _boss_session_ttl(),
            "request_fingerprint": _boss_enter_fingerprint(body),
            "result_fingerprint": "",
            "meta": {"boss_num": bn, "mode": mode, "fee": fee,
                     "hp_at_open": cur_hp,
                     "season_start": _int(st.get("season_start"), 0),
                     "user_name": name, "team": team},
            "response": resp,
        })
        _boss_prune_sessions(doc, now)
        _boss_persist(doc, s, uid)
        LOG.info("  boss enter %s uid=%s fee=%d ticket=%d enter_count=%d hp=%d",
                 mode, uid, fee, ticket, enter_count, cur_hp)
    return json.dumps(resp, ensure_ascii=False)

def boss_result_text(body, uid=None) -> str:
    """Battle result: validated, clamped, applied exactly once, and replayed
    from the stored answer on any retry (§8) -- including a late retry that
    arrives after a newer match was opened (§9)."""
    uid = uid or _uid()
    today = time.strftime("%Y%m%d")
    now = _boss_now()
    fp = _boss_fingerprint(body)
    with SAVE_LOCK:
        doc = _boss_doc_load()
        bn = BOSS_ACTIVE_NUM
        st, rolled = _boss_state_for(doc, bn, now)
        if rolled:
            _boss_persist(doc)
        _boss_expire_sessions(doc, now)

        act = _boss_active_session(doc, bn, uid)
        if act is not None and act.get("result_fingerprint") and act["result_fingerprint"] == fp:
            resp = act.get("response")
            if isinstance(resp, dict) and resp:
                LOG.info("  boss result REPLAY (same result) uid=%s", uid)
                return json.dumps(resp, ensure_ascii=False)
        # §9: match A was consumed, the player then opened match B, and A's old
        # update arrives late. It must replay A's stored answer instead of being
        # applied to B -- and B must stay open. The window is short only while a
        # new session is open, so a genuine repeat is not mistaken for a retry.
        prev = _boss_recent_consumed(doc, bn, uid, fp, now,
                                     max_age=_boss_retry_secs() if act is not None else 0)
        if prev is not None:
            resp = prev.get("response")
            if isinstance(resp, dict) and resp:
                LOG.info("  boss result REPLAY (%s) uid=%s",
                         "late retry" if act is not None else "retry", uid)
                return json.dumps(resp, ensure_ascii=False)
        if act is None:
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "no active boss match session"},
                              ensure_ascii=False)

        meta = act.get("meta") or {}
        bnum = _int(meta.get("boss_num"), bn)
        st_use = st if bnum == bn else _boss_state_for(doc, bnum, now)[0]

        score = _int(body.get("SCORE"), -1)
        res = _boss_result_token(str(body.get("RESULT", "") or ""))
        hp_open = max(0, _int(meta.get("hp_at_open"), 0))
        if score < 0:
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "bad SCORE"}, ensure_ascii=False)
        if res not in BOSS_RESULTS:
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "bad RESULT"}, ensure_ascii=False)
        if score > hp_open:
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "SCORE exceeds boss HP at match start"},
                              ensure_ascii=False)
        if _int(meta.get("season_start"), 0) != _int(st_use.get("season_start"), 0):
            act["status"] = "EXPIRED"
            _boss_persist(doc)
            return json.dumps({"STATE": "ERROR", "CODE": "-101",
                               "ERROR_MESSAGE": "match session is from a previous season"},
                              ensure_ascii=False)

        cur = max(0, _int(st_use.get("cur_hp"), 0))
        damage = min(score, cur)
        st_use["cur_hp"] = max(0, cur - damage)
        st_use["updated_at"] = now
        if damage > 0:
            key = _boss_key(bnum, uid)
            d = (doc.setdefault("damage", {})).get(key) or {}
            d.update({"boss_num": int(bnum), "user_id": uid,
                      "total_damage": _int(d.get("total_damage"), 0) + damage,
                      "user_name": _boss_name(body, None, meta.get("user_name") or d.get("user_name")),
                      "team": _boss_team(body, None, meta.get("team") or d.get("team")),
                      "platform": str(d.get("platform") or "WEB"),
                      "updated_at": now})
            doc["damage"][key] = d

        s = load_save()
        ticket, count = _boss_ticket_read(s, today)
        resp = _boss_payload(doc, bnum, st_use, uid,
                             {"TICKET": str(ticket), "ENTER_COUNT": str(count)})
        act["status"] = "CONSUMED"
        act["consumed_at"] = now
        act["result_fingerprint"] = fp
        act["response"] = resp
        _boss_prune_sessions(doc, now)
        _boss_persist(doc)
        LOG.info("  boss result uid=%s res=%s score=%d dmg=%d hp=%d->%d",
                 uid, res, score, damage, cur, st_use["cur_hp"])
    return json.dumps(resp, ensure_ascii=False)

def _uid() -> str:
    """Account id of the CURRENT request (thread-local), set in _handle from
    an authenticated session when login is required. Wire ids are compatibility
    data only in that mode."""
    uid = getattr(_tl, "uid", None)
    if DB_FILE and REQUIRE_LOGIN:
        return uid or ""
    return uid if uid else UNIQ_ID

def add_account(acc, pw):
    salt = secrets.token_hex(8)
    pw_hash = salt + ":" + hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()
    with SAVE_LOCK:
        DB_CONN.execute("INSERT OR REPLACE INTO accounts (id, pw_hash) VALUES (?,?)",
                        (acc, pw_hash))
        DB_CONN.commit()

def account_exists(acc) -> bool:
    if not DB_CONN:
        return False
    with SAVE_LOCK:
        try:
            return DB_CONN.execute("SELECT 1 FROM accounts WHERE id=?", (acc,)).fetchone() is not None
        except Exception:
            return False

def verify_account(acc, pw) -> bool:
    if not DB_CONN:
        return False
    with SAVE_LOCK:
        row = DB_CONN.execute("SELECT pw_hash FROM accounts WHERE id=?", (acc,)).fetchone()
    if not row:
        return False
    try:
        salt, digest = row[0].split(":", 1)
        return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest() == digest
    except Exception:
        return False

def db_load_save(uid) -> dict | None:
    if not DB_CONN:
        return None
    with SAVE_LOCK:
        row = DB_CONN.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
    if not row:
        return None
    try:
        return _norm_save(json.loads(row[0]))
    except Exception:
        return None

def db_store_save(uid, payload):
    if not DB_CONN:
        return
    with SAVE_LOCK:
        DB_CONN.execute("INSERT OR REPLACE INTO saves (id, payload) VALUES (?,?)",
                        (uid, json.dumps(payload, ensure_ascii=False)))
        DB_CONN.commit()

def parse_body(body_str: str) -> dict:
    """Client posts application/x-www-form-urlencoded WITHOUT url-encoding
    (get_string_by_obj just joins key=value&). JSON used by some endpoints."""
    body_str = body_str or ""
    try:
        return json.loads(body_str)
    except Exception:
        pass
    d = {}
    for kv in body_str.split("&"):
        if not kv:
            continue
        if "=" in kv:
            k, v = kv.split("=", 1)
        else:
            k, v = kv, ""
        # The client builds its forms with encodeURIComponent, so payload
        # fields (DATA1/2/3 hold whole CSV strings) arrive percent-encoded
        # ("%2C" for ",", "%3A" for ":"). Without decoding, DATA1 is saved
        # as one giant "field" (0 commas) and the next boot hands it to
        # STORAGE.load_n_parse_cnm, whose t[14]=b ends up undefined -> the
        # game crashes at the logo screen (S_LOGO). unquote, not
        # unquote_plus, keeps literal "+" untouched.
        try:
            v = unquote(v)
        except Exception:
            pass
        d[k] = v
    return d

# ---------- PvP 2025 (PVP_2025/*.php) ----------
# Offline policy: ten tickets reset each local day, a paid entry costs ten
# rubies, and match results grant no economy rewards. Scores only affect this
# PvP ladder. MATCH_NONCE is authoritative and survives process restarts.
PVP_DAILY_TICKETS = 10
PVP_ENTRY_RUBIES = 10
PVP_SESSION_TTL = 1800
PVP_SCORE_MAX = 1000


def _pvp_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _pvp_error(code, message) -> str:
    return _pvp_json({"STATE": "ERROR", "CODE": str(code),
                      "ERROR_MESSAGE": str(message)})


def _pvp_valid_team(team) -> bool:
    entries = [part for part in str(team or "").split(",") if part]
    return bool(entries) and all(len(part.split(":")) >= 6 for part in entries)


def _pvp_snapshot(body, uid) -> dict | None:
    team = str(body.get("TEAM", "") or "")
    if not uid or not _pvp_valid_team(team):
        return None
    return {
        "user_id": str(uid),
        "user_name": str(body.get("NAME", "") or uid),
        "team": team,
        "item": str(body.get("ITEM", "") or ""),
        "platform": "WEB",
        "level": max(1, _int(body.get("LEVEL"), 1)),
        "tower_hp": max(0, _int(body.get("TOWER_HP"), 0)),
        "tower_level": max(0, _int(body.get("TOWER_LEVEL"), 0)),
        "missile_ap": max(0, _int(body.get("MISSILE_AP"), 0)),
        "missile_level": max(0, _int(body.get("MISSILE_LEVEL"), 0)),
        "missile_tick": max(0, _int(body.get("MISSILE_TICK"), 0)),
    }


def _pvp_ticket_read(save_obj, today=None) -> tuple[int, str]:
    today = today or time.strftime("%Y%m%d")
    if str(save_obj.get("pvp_ticket_day", "")) != today:
        return PVP_DAILY_TICKETS, today
    return max(0, _int(save_obj.get("pvp_ticket_left"), PVP_DAILY_TICKETS)), today


def _pvp_ruby_read(save_obj) -> tuple[list, int]:
    d1 = str(save_obj.get("DATA1", "") or "").split(",")
    while len(d1) < 3:
        d1.append("0")
    return d1, max(0, _int(d1[2], 0))


def _pvp_matched_user(snapshot, ai=False) -> dict:
    uid = str(snapshot.get("user_id", ""))
    return {
        "ID": ("AI_" + uid) if ai else uid,
        "NAME": ("AI " + str(snapshot.get("user_name", uid))) if ai else str(snapshot.get("user_name", uid)),
        "LEVEL": str(snapshot.get("level", 1)),
        "TOWER_HP": str(snapshot.get("tower_hp", 0)),
        "TOWER_LEVEL": str(snapshot.get("tower_level", 0)),
        "MISSILE_AP": str(snapshot.get("missile_ap", 0)),
        "MISSILE_LEVEL": str(snapshot.get("missile_level", 0)),
        "MISSILE_TICK": str(snapshot.get("missile_tick", 0)),
        "TEAM": str(snapshot.get("team", "")),
        "ITEM": str(snapshot.get("item", "")),
        "PLATFORM": str(snapshot.get("platform", "WEB") or "WEB"),
        "PROFILE": "0",
    }


def _pvp_db_save(uid) -> dict:
    row = DB_CONN.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
    if not row:
        return {}
    try:
        return _norm_save(json.loads(row[0]))
    except Exception:
        return {}


def _pvp_db_store_save(uid, save_obj):
    DB_CONN.execute("INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                    (uid, json.dumps(save_obj, ensure_ascii=False)))


def _pvp_db_upsert_snapshot(snapshot, now):
    DB_CONN.execute(
        "INSERT INTO pvp_leaderboard (user_id,total_score,best_score,updated_at,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick) VALUES (?,0,0,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET updated_at=excluded.updated_at,user_name=excluded.user_name,team=excluded.team,item=excluded.item,platform=excluded.platform,level=excluded.level,tower_hp=excluded.tower_hp,tower_level=excluded.tower_level,missile_ap=excluded.missile_ap,missile_level=excluded.missile_level,missile_tick=excluded.missile_tick",
        (snapshot["user_id"], now, snapshot["user_name"], snapshot["team"],
         snapshot["item"], snapshot["platform"], snapshot["level"],
         snapshot["tower_hp"], snapshot["tower_level"], snapshot["missile_ap"],
         snapshot["missile_level"], snapshot["missile_tick"]),
    )


def _pvp_db_rows():
    return DB_CONN.execute(
        "SELECT user_id,total_score,best_score,updated_at,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick FROM pvp_leaderboard ORDER BY total_score DESC,updated_at ASC,user_id ASC LIMIT 50"
    ).fetchall()


def _pvp_ranking_payload(uid, save_obj, rows) -> dict:
    ranking = []
    mine = None
    for pos, row in enumerate(rows, 1):
        entry = {
            "ranking": pos, "user_name": row[4] or row[0],
            "platform": row[7] or "WEB", "team": row[5],
            "tot_score": str(row[1]),
        }
        ranking.append(entry)
        if row[0] == uid:
            mine = (pos, row)
    ticket, _ = _pvp_ticket_read(save_obj)
    total = mine[1][1] if mine else 0
    best = mine[1][2] if mine else 0
    rank = mine[0] if mine else 0
    today = time.strftime("%Y%m%d")
    return {
        "STATE": "SUCCESS", "ranking_list": ranking,
        "my_ranking": str(rank), "TOT_SCORE": str(total),
        "entry_fee_rubies": str(PVP_ENTRY_RUBIES), "TICKET": str(ticket),
        "MAX_SCORE": str(best), "SCORE_REWARD": "0,0,0,0,0",
        "season_num": "1", "last_season_num": "0",
        "season_period": today, "last_season_period": "",
        "weekly_reward_ruby": [0] * 6, "weekly_reward_point": [0] * 10,
        "season_reward": [0] * 7, "TOT_POINT": "0",
        "S_RANKING": str(rank), "fame_ranking_list": [],
        "season_ranking_list": [], "PLATFORM_NAME_COM": "",
    }


def pvp_ranking_text(body) -> str:
    uid = _uid()
    snapshot = _pvp_snapshot(body, uid)
    if not snapshot:
        return _pvp_error("-201", "invalid PvP snapshot")
    now = int(time.time())
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                _pvp_db_upsert_snapshot(snapshot, now)
                save_obj = _pvp_db_save(uid)
                payload = _pvp_ranking_payload(uid, save_obj, _pvp_db_rows())
                DB_CONN.commit()
                return _pvp_json(payload)
            except Exception:
                DB_CONN.rollback()
                raise
        save_obj = load_save()
        board = save_obj.setdefault("pvp_leaderboard", {})
        old = board.get(uid) or {}
        snapshot.update({"total_score": _int(old.get("total_score"), 0),
                         "best_score": _int(old.get("best_score"), 0),
                         "updated_at": now})
        board[uid] = snapshot
        store_save(save_obj)
        row = (uid, snapshot["total_score"], snapshot["best_score"], now,
               snapshot["user_name"], snapshot["team"], snapshot["item"],
               snapshot["platform"], snapshot["level"], snapshot["tower_hp"],
               snapshot["tower_level"], snapshot["missile_ap"],
               snapshot["missile_level"], snapshot["missile_tick"])
        return _pvp_json(_pvp_ranking_payload(uid, save_obj, [row]))


def _pvp_db_opponent(uid, owner):
    row = DB_CONN.execute(
        "SELECT user_id,total_score,best_score,updated_at,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick FROM pvp_leaderboard WHERE user_id<>? AND team<>'' ORDER BY total_score DESC,updated_at DESC,user_id ASC LIMIT 1",
        (uid,),
    ).fetchone()
    if not row:
        return _pvp_matched_user(owner, ai=True), "AI_" + uid
    snapshot = {"user_id": row[0], "user_name": row[4], "team": row[5],
                "item": row[6], "platform": row[7], "level": row[8],
                "tower_hp": row[9], "tower_level": row[10],
                "missile_ap": row[11], "missile_level": row[12],
                "missile_tick": row[13]}
    return _pvp_matched_user(snapshot), row[0]


def pvp_enter_text(body) -> str:
    uid = _uid()
    snapshot = _pvp_snapshot(body, uid)
    if not snapshot:
        return _pvp_error("-201", "invalid PvP snapshot")
    now = int(time.time())
    mode = str(body.get("MODE", "ENTRY_TICKET") or "ENTRY_TICKET")
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                active = DB_CONN.execute(
                    "SELECT nonce,expires_at,enter_response_json FROM pvp_sessions WHERE user_id=? AND status='ACTIVE'",
                    (uid,),
                ).fetchone()
                if active and active[1] >= now and active[2]:
                    DB_CONN.commit()
                    return active[2]
                if active:
                    DB_CONN.execute("UPDATE pvp_sessions SET status='EXPIRED' WHERE nonce=?", (active[0],))
                _pvp_db_upsert_snapshot(snapshot, now)
                save_obj = _pvp_db_save(uid)
                ticket, today = _pvp_ticket_read(save_obj)
                d1, ruby = _pvp_ruby_read(save_obj)
                if mode == "ENTRY_TICKET":
                    if ticket <= 0:
                        DB_CONN.rollback()
                        return _pvp_error("-203", "no PvP ticket")
                    ticket -= 1
                elif mode == "ENTRY_RUBY":
                    if ruby < PVP_ENTRY_RUBIES:
                        DB_CONN.rollback()
                        return _pvp_error("-103", "not enough ruby")
                    ruby -= PVP_ENTRY_RUBIES
                    d1[2] = str(ruby)
                    save_obj["DATA1"] = ",".join(d1)
                else:
                    DB_CONN.rollback()
                    return _pvp_error("-202", "invalid entry mode")
                save_obj["pvp_ticket_day"] = today
                save_obj["pvp_ticket_left"] = str(ticket)
                opponent, opponent_id = _pvp_db_opponent(uid, snapshot)
                nonce = secrets.token_hex(16)
                response = {"STATE": "SUCCESS", "MATCH_NONCE": nonce,
                            "matched_user": opponent, "add_ticket": str(ticket)}
                if mode == "ENTRY_RUBY":
                    response["s_add_ruby"] = str(ruby)
                response_text = _pvp_json(response)
                DB_CONN.execute(
                    "INSERT INTO pvp_sessions (nonce,user_id,opponent_id,status,created_at,expires_at,player_team,opponent_json,enter_response_json,response_json) VALUES (?,?,?,'ACTIVE',?,?,?,?,?,'')",
                    (nonce, uid, opponent_id, now, now + PVP_SESSION_TTL,
                     snapshot["team"], _pvp_json(opponent), response_text),
                )
                _pvp_db_store_save(uid, save_obj)
                DB_CONN.commit()
                return response_text
            except Exception:
                DB_CONN.rollback()
                raise

        save_obj = load_save()
        sessions = save_obj.setdefault("pvp_sessions", {})
        for nonce, session in list(sessions.items()):
            if session.get("status") == "ACTIVE":
                if _int(session.get("expires_at"), 0) >= now:
                    return str(session.get("enter_response_json") or _pvp_error("-204", "invalid active match"))
                session["status"] = "EXPIRED"
        ticket, today = _pvp_ticket_read(save_obj)
        d1, ruby = _pvp_ruby_read(save_obj)
        if mode == "ENTRY_TICKET":
            if ticket <= 0:
                return _pvp_error("-203", "no PvP ticket")
            ticket -= 1
        elif mode == "ENTRY_RUBY":
            if ruby < PVP_ENTRY_RUBIES:
                return _pvp_error("-103", "not enough ruby")
            ruby -= PVP_ENTRY_RUBIES
            d1[2] = str(ruby)
            save_obj["DATA1"] = ",".join(d1)
        else:
            return _pvp_error("-202", "invalid entry mode")
        save_obj["pvp_ticket_day"], save_obj["pvp_ticket_left"] = today, str(ticket)
        opponent = _pvp_matched_user(snapshot, ai=True)
        nonce = secrets.token_hex(16)
        response = {"STATE": "SUCCESS", "MATCH_NONCE": nonce,
                    "matched_user": opponent, "add_ticket": str(ticket)}
        if mode == "ENTRY_RUBY":
            response["s_add_ruby"] = str(ruby)
        response_text = _pvp_json(response)
        sessions[nonce] = {"user_id": uid, "status": "ACTIVE", "created_at": now,
                           "expires_at": now + PVP_SESSION_TTL,
                           "player_team": snapshot["team"],
                           "enter_response_json": response_text, "response_json": ""}
        store_save(save_obj)
        return response_text


def _pvp_validate_result(body, expected_team) -> tuple[int, str] | None:
    try:
        score = int(str(body.get("SCORE", "")).strip())
    except Exception:
        return None
    result = _boss_result_token(str(body.get("RESULT", "") or ""))
    if score < 0 or score > PVP_SCORE_MAX or result not in {"승", "패", "무"}:
        return None
    if (result == "패" and score != 0) or (result in {"승", "무"} and score <= 0):
        return None
    if str(body.get("TEAM", "") or "") != str(expected_team):
        return None
    return score, result


def pvp_result_text(body) -> str:
    uid = _uid()
    nonce = str(body.get("MATCH_NONCE", "") or "")
    if not uid or not nonce:
        return _pvp_error("-204", "missing MATCH_NONCE")
    now = int(time.time())
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                session = DB_CONN.execute(
                    "SELECT user_id,status,expires_at,player_team,response_json FROM pvp_sessions WHERE nonce=?",
                    (nonce,),
                ).fetchone()
                if not session or session[0] != uid:
                    DB_CONN.rollback()
                    return _pvp_error("-204", "invalid MATCH_NONCE")
                if session[1] == "CONSUMED" and session[4]:
                    DB_CONN.commit()
                    return session[4]
                if session[1] != "ACTIVE":
                    DB_CONN.rollback()
                    return _pvp_error("-205", "match is not active")
                if session[2] < now:
                    DB_CONN.execute("UPDATE pvp_sessions SET status='EXPIRED' WHERE nonce=?", (nonce,))
                    DB_CONN.commit()
                    return _pvp_error("-206", "match expired")
                validated = _pvp_validate_result(body, session[3])
                if not validated:
                    DB_CONN.rollback()
                    return _pvp_error("-207", "invalid PvP result")
                score, _ = validated
                DB_CONN.execute(
                    "UPDATE pvp_leaderboard SET total_score=total_score+?,best_score=MAX(best_score,?),updated_at=? WHERE user_id=?",
                    (score, score, now, uid),
                )
                save_obj = _pvp_db_save(uid)
                payload = _pvp_ranking_payload(uid, save_obj, _pvp_db_rows())
                payload.update({"tot_score": payload["TOT_SCORE"],
                                "max_score": payload["MAX_SCORE"],
                                "score_reward_str": "0,0,0,0,0"})
                response_text = _pvp_json(payload)
                DB_CONN.execute(
                    "UPDATE pvp_sessions SET status='CONSUMED',consumed_at=?,response_json=? WHERE nonce=? AND status='ACTIVE'",
                    (now, response_text, nonce),
                )
                DB_CONN.commit()
                return response_text
            except Exception:
                DB_CONN.rollback()
                raise

        save_obj = load_save()
        session = (save_obj.get("pvp_sessions") or {}).get(nonce)
        if not session or session.get("user_id") != uid:
            return _pvp_error("-204", "invalid MATCH_NONCE")
        if session.get("status") == "CONSUMED" and session.get("response_json"):
            return session["response_json"]
        if session.get("status") != "ACTIVE":
            return _pvp_error("-205", "match is not active")
        if _int(session.get("expires_at"), 0) < now:
            session["status"] = "EXPIRED"
            store_save(save_obj)
            return _pvp_error("-206", "match expired")
        validated = _pvp_validate_result(body, session.get("player_team"))
        if not validated:
            return _pvp_error("-207", "invalid PvP result")
        score, _ = validated
        board = save_obj.setdefault("pvp_leaderboard", {})
        mine = board.setdefault(uid, {"user_id": uid, "user_name": uid,
                                      "team": session.get("player_team", ""),
                                      "item": "", "platform": "WEB", "level": 1,
                                      "tower_hp": 0, "tower_level": 0,
                                      "missile_ap": 0, "missile_level": 0,
                                      "missile_tick": 0})
        mine["total_score"] = _int(mine.get("total_score"), 0) + score
        mine["best_score"] = max(_int(mine.get("best_score"), 0), score)
        mine["updated_at"] = now
        row = (uid, mine["total_score"], mine["best_score"], now,
               mine.get("user_name", uid), mine.get("team", ""), mine.get("item", ""),
               mine.get("platform", "WEB"), mine.get("level", 1), mine.get("tower_hp", 0),
               mine.get("tower_level", 0), mine.get("missile_ap", 0),
               mine.get("missile_level", 0), mine.get("missile_tick", 0))
        payload = _pvp_ranking_payload(uid, save_obj, [row])
        payload.update({"tot_score": payload["TOT_SCORE"], "max_score": payload["MAX_SCORE"],
                        "score_reward_str": "0,0,0,0,0"})
        response_text = _pvp_json(payload)
        session.update({"status": "CONSUMED", "consumed_at": now,
                        "response_json": response_text})
        store_save(save_obj)
        return response_text


# ---------- PvP Classic 2026 (PVP_CLS_2026/*.php) ----------
# Classic is an older client contract: it has no MATCH_NONCE field.  Keep it
# isolated from PVP_2025 and use a private server-side session id so one active
# entry can still be charged/consumed only once.  The fee/ticket values below
# are offline policy defaults; the client supplies no fallback fee of its own.
PVP_CLASSIC_DAILY_TICKETS = 10
PVP_CLASSIC_ENTRY_GOLD = 10000
PVP_CLASSIC_SESSION_TTL = 1800
PVP_CLASSIC_SCORE_MAX = 1000


def _classic_ticket_read(save_obj, today=None):
    today = today or time.strftime("%Y%m%d")
    if str(save_obj.get("pvp_cls_ticket_day", "")) != today:
        return PVP_CLASSIC_DAILY_TICKETS, today
    return max(0, _int(save_obj.get("pvp_cls_ticket_left"),
                       PVP_CLASSIC_DAILY_TICKETS)), today


def _classic_gold_read(save_obj):
    d1 = str(save_obj.get("DATA1", "") or "").split(",")
    while len(d1) < 2:
        d1.append("0")
    return d1, max(0, _int(d1[1], 0))


def _classic_snapshot(body, uid):
    snapshot = _pvp_snapshot(body, uid)
    return snapshot


def _classic_db_upsert_snapshot(snapshot, now):
    DB_CONN.execute(
        "INSERT INTO pvp_classic_leaderboard (user_id,total_score,best_score,updated_at,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick) VALUES (?,0,0,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET updated_at=excluded.updated_at,user_name=excluded.user_name,team=excluded.team,item=excluded.item,platform=excluded.platform,level=excluded.level,tower_hp=excluded.tower_hp,tower_level=excluded.tower_level,missile_ap=excluded.missile_ap,missile_level=excluded.missile_level,missile_tick=excluded.missile_tick",
        (snapshot["user_id"], now, snapshot["user_name"], snapshot["team"],
         snapshot["item"], snapshot["platform"], snapshot["level"],
         snapshot["tower_hp"], snapshot["tower_level"], snapshot["missile_ap"],
         snapshot["missile_level"], snapshot["missile_tick"]),
    )


def _classic_db_rows():
    return DB_CONN.execute(
        "SELECT user_id,total_score,best_score,updated_at,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick FROM pvp_classic_leaderboard ORDER BY total_score DESC,updated_at ASC,user_id ASC LIMIT 50"
    ).fetchall()


def _classic_ranking_payload(uid, save_obj, rows):
    ranking, mine = [], None
    for pos, row in enumerate(rows, 1):
        ranking.append({"ranking": pos, "user_name": row[4] or row[0],
                        "platform": row[7] or "WEB", "team": row[5],
                        "tot_score": str(row[1])})
        if row[0] == uid:
            mine = (pos, row)
    ticket, _ = _classic_ticket_read(save_obj)
    return {
        "STATE": "SUCCESS", "ranking_list": ranking,
        "my_ranking": str(mine[0] if mine else 0),
        "TOT_SCORE": str(mine[1][1] if mine else 0),
        "TICKET": str(ticket),
        "entry_fee_gold": str(PVP_CLASSIC_ENTRY_GOLD),
        "PLATFORM_NAME_COM": "",
    }


def _classic_db_opponent(uid, owner):
    row = DB_CONN.execute(
        "SELECT user_id,user_name,team,item,platform,level,tower_hp,tower_level,missile_ap,missile_level,missile_tick FROM pvp_classic_leaderboard WHERE user_id<>? AND team<>'' ORDER BY total_score DESC,updated_at DESC,user_id ASC LIMIT 1",
        (uid,),
    ).fetchone()
    if not row:
        return _pvp_matched_user(owner, ai=True), "AI_" + uid
    snapshot = {"user_id": row[0], "user_name": row[1], "team": row[2],
                "item": row[3], "platform": row[4], "level": row[5],
                "tower_hp": row[6], "tower_level": row[7],
                "missile_ap": row[8], "missile_level": row[9],
                "missile_tick": row[10]}
    return _pvp_matched_user(snapshot), row[0]


def _classic_result_fingerprint(body):
    result = _boss_result_token(str(body.get("RESULT", "") or ""))
    raw = "|".join((str(body.get("TEAM", "") or ""),
                     str(body.get("ITEM", "") or ""),
                     str(body.get("SCORE", "") or ""), result))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _classic_validate_result(body, expected_team):
    try:
        score = int(str(body.get("SCORE", "")).strip())
    except Exception:
        return None
    result = _boss_result_token(str(body.get("RESULT", "") or ""))
    if score < 0 or score > PVP_CLASSIC_SCORE_MAX or result not in {"승", "패", "무"}:
        return None
    if (result == "패" and score != 0) or (result in {"승", "무"} and score <= 0):
        return None
    if str(body.get("TEAM", "") or "") != str(expected_team):
        return None
    return score, result


def pvp_classic_ranking_text(body) -> str:
    uid = _uid()
    snapshot = _classic_snapshot(body, uid)
    if not snapshot:
        return _pvp_error("-201", "invalid Classic PvP snapshot")
    now = int(time.time())
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                _classic_db_upsert_snapshot(snapshot, now)
                save_obj = _pvp_db_save(uid)
                payload = _classic_ranking_payload(uid, save_obj, _classic_db_rows())
                DB_CONN.commit()
                return _pvp_json(payload)
            except Exception:
                DB_CONN.rollback()
                raise
        save_obj = load_save()
        board = save_obj.setdefault("pvp_classic_leaderboard", {})
        old = board.get(uid) or {}
        snapshot.update({"total_score": _int(old.get("total_score"), 0),
                         "best_score": _int(old.get("best_score"), 0),
                         "updated_at": now})
        board[uid] = snapshot
        store_save(save_obj)
        row = (uid, snapshot["total_score"], snapshot["best_score"], now,
               snapshot["user_name"], snapshot["team"], snapshot["item"],
               snapshot["platform"], snapshot["level"], snapshot["tower_hp"],
               snapshot["tower_level"], snapshot["missile_ap"],
               snapshot["missile_level"], snapshot["missile_tick"])
        return _pvp_json(_classic_ranking_payload(uid, save_obj, [row]))


def pvp_classic_enter_text(body) -> str:
    uid = _uid()
    snapshot = _classic_snapshot(body, uid)
    if not snapshot:
        return _pvp_error("-201", "invalid Classic PvP snapshot")
    mode = str(body.get("MODE", "") or "").strip().upper()
    if mode not in ("ENTRY_TICKET", "ENTRY_GOLD"):
        return _pvp_error("-101", "unknown Classic PvP entry mode")
    now = int(time.time())
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                active = DB_CONN.execute(
                    "SELECT session_id,expires_at,enter_response_json FROM pvp_classic_sessions WHERE user_id=? AND status='ACTIVE'",
                    (uid,),
                ).fetchone()
                if active and active[1] >= now and active[2]:
                    DB_CONN.commit()
                    return active[2]
                if active:
                    DB_CONN.execute("UPDATE pvp_classic_sessions SET status='EXPIRED' WHERE session_id=?",
                                    (active[0],))
                _classic_db_upsert_snapshot(snapshot, now)
                save_obj = _pvp_db_save(uid)
                ticket, today = _classic_ticket_read(save_obj)
                d1, gold = _classic_gold_read(save_obj)
                fee = 0
                if mode == "ENTRY_TICKET":
                    if ticket <= 0:
                        DB_CONN.rollback()
                        return _pvp_error("-102", "no Classic PvP ticket")
                    ticket -= 1
                else:
                    fee = PVP_CLASSIC_ENTRY_GOLD
                    if gold < fee:
                        DB_CONN.rollback()
                        return _pvp_error("-103", "not enough gold")
                    gold -= fee
                    d1[1] = str(gold)
                    save_obj["DATA1"] = ",".join(d1)
                save_obj["pvp_cls_ticket_day"] = today
                save_obj["pvp_cls_ticket_left"] = str(ticket)
                opponent, opponent_id = _classic_db_opponent(uid, snapshot)
                response = {"STATE": "SUCCESS", "matched_user": opponent,
                            "add_ticket": str(ticket), "s_add_gold": str(gold)}
                response_text = _pvp_json(response)
                DB_CONN.execute(
                    "INSERT INTO pvp_classic_sessions (session_id,user_id,opponent_id,status,created_at,expires_at,player_team,opponent_json,enter_response_json,response_json,result_fingerprint) VALUES (?,?,?,'ACTIVE',?,?,?,?,?,'','')",
                    (secrets.token_hex(16), uid, opponent_id, now, now + PVP_CLASSIC_SESSION_TTL,
                     snapshot["team"], _pvp_json(opponent), response_text),
                )
                _pvp_db_store_save(uid, save_obj)
                DB_CONN.commit()
                return response_text
            except Exception:
                DB_CONN.rollback()
                raise

        save_obj = load_save()
        sessions = save_obj.setdefault("pvp_classic_sessions", {})
        for session in sessions.values():
            if session.get("user_id") != uid or session.get("status") != "ACTIVE":
                continue
            if _int(session.get("expires_at"), 0) >= now:
                return str(session.get("enter_response_json") or _pvp_error("-104", "invalid active match"))
            session["status"] = "EXPIRED"
        ticket, today = _classic_ticket_read(save_obj)
        d1, gold = _classic_gold_read(save_obj)
        fee = 0
        if mode == "ENTRY_TICKET":
            if ticket <= 0:
                return _pvp_error("-102", "no Classic PvP ticket")
            ticket -= 1
        else:
            fee = PVP_CLASSIC_ENTRY_GOLD
            if gold < fee:
                return _pvp_error("-103", "not enough gold")
            gold -= fee
            d1[1] = str(gold)
            save_obj["DATA1"] = ",".join(d1)
        save_obj["pvp_cls_ticket_day"], save_obj["pvp_cls_ticket_left"] = today, str(ticket)
        response = {"STATE": "SUCCESS", "matched_user": _pvp_matched_user(snapshot, ai=True),
                    "add_ticket": str(ticket), "s_add_gold": str(gold)}
        response_text = _pvp_json(response)
        sessions[secrets.token_hex(16)] = {
            "user_id": uid, "status": "ACTIVE", "created_at": now,
            "expires_at": now + PVP_CLASSIC_SESSION_TTL,
            "player_team": snapshot["team"], "enter_response_json": response_text,
            "response_json": "", "result_fingerprint": "",
        }
        store_save(save_obj)
        return response_text


def pvp_classic_result_text(body) -> str:
    uid = _uid()
    if not uid:
        return _pvp_error("-104", "missing account")
    now = int(time.time())
    fingerprint = _classic_result_fingerprint(body)
    with SAVE_LOCK:
        if DB_CONN:
            try:
                if DB_CONN.in_transaction:
                    DB_CONN.commit()
                DB_CONN.execute("BEGIN IMMEDIATE")
                replay = DB_CONN.execute(
                    "SELECT response_json FROM pvp_classic_sessions WHERE user_id=? AND status='CONSUMED' AND result_fingerprint=? AND response_json<>'' ORDER BY consumed_at DESC LIMIT 1",
                    (uid, fingerprint),
                ).fetchone()
                if replay:
                    DB_CONN.commit()
                    return replay[0]
                session = DB_CONN.execute(
                    "SELECT session_id,status,expires_at,player_team FROM pvp_classic_sessions WHERE user_id=? AND status='ACTIVE' ORDER BY created_at DESC LIMIT 1",
                    (uid,),
                ).fetchone()
                if not session:
                    DB_CONN.rollback()
                    return _pvp_error("-104", "no active Classic PvP match")
                if session[2] < now:
                    DB_CONN.execute("UPDATE pvp_classic_sessions SET status='EXPIRED' WHERE session_id=?",
                                    (session[0],))
                    DB_CONN.commit()
                    return _pvp_error("-104", "Classic PvP match expired")
                validated = _classic_validate_result(body, session[3])
                if not validated:
                    DB_CONN.rollback()
                    return _pvp_error("-105", "invalid Classic PvP result")
                score, _ = validated
                DB_CONN.execute(
                    "UPDATE pvp_classic_leaderboard SET total_score=total_score+?,best_score=MAX(best_score,?),updated_at=? WHERE user_id=?",
                    (score, score, now, uid),
                )
                save_obj = _pvp_db_save(uid)
                payload = _classic_ranking_payload(uid, save_obj, _classic_db_rows())
                payload.update({"tot_score": payload["TOT_SCORE"],
                                "max_score": payload["TOT_SCORE"],
                                "score_reward_str": "0,0,0,0,0"})
                response_text = _pvp_json(payload)
                DB_CONN.execute(
                    "UPDATE pvp_classic_sessions SET status='CONSUMED',consumed_at=?,response_json=?,result_fingerprint=? WHERE session_id=? AND status='ACTIVE'",
                    (now, response_text, fingerprint, session[0]),
                )
                DB_CONN.commit()
                return response_text
            except Exception:
                DB_CONN.rollback()
                raise

        save_obj = load_save()
        sessions = save_obj.get("pvp_classic_sessions") or {}
        for session in sessions.values():
            if session.get("user_id") == uid and session.get("status") == "CONSUMED" and session.get("result_fingerprint") == fingerprint and session.get("response_json"):
                return session["response_json"]
        session_id, session = next(((sid, s) for sid, s in sessions.items()
                                    if s.get("user_id") == uid and s.get("status") == "ACTIVE"),
                                   (None, None))
        if session is None:
            return _pvp_error("-104", "no active Classic PvP match")
        if _int(session.get("expires_at"), 0) < now:
            session["status"] = "EXPIRED"
            store_save(save_obj)
            return _pvp_error("-104", "Classic PvP match expired")
        validated = _classic_validate_result(body, session.get("player_team"))
        if not validated:
            return _pvp_error("-105", "invalid Classic PvP result")
        score, _ = validated
        board = save_obj.setdefault("pvp_classic_leaderboard", {})
        mine = board.setdefault(uid, {"user_id": uid, "user_name": uid,
                                      "team": session.get("player_team", ""),
                                      "item": "", "platform": "WEB", "level": 1,
                                      "tower_hp": 0, "tower_level": 0,
                                      "missile_ap": 0, "missile_level": 0,
                                      "missile_tick": 0, "total_score": 0,
                                      "best_score": 0})
        mine["total_score"] = _int(mine.get("total_score"), 0) + score
        mine["best_score"] = max(_int(mine.get("best_score"), 0), score)
        mine["updated_at"] = now
        row = (uid, mine["total_score"], mine["best_score"], now,
               mine.get("user_name", uid), mine.get("team", ""), mine.get("item", ""),
               mine.get("platform", "WEB"), mine.get("level", 1), mine.get("tower_hp", 0),
               mine.get("tower_level", 0), mine.get("missile_ap", 0),
               mine.get("missile_level", 0), mine.get("missile_tick", 0))
        payload = _classic_ranking_payload(uid, save_obj, [row])
        payload.update({"tot_score": payload["TOT_SCORE"], "max_score": payload["TOT_SCORE"],
                        "score_reward_str": "0,0,0,0,0"})
        response_text = _pvp_json(payload)
        session.update({"status": "CONSUMED", "consumed_at": now,
                        "response_json": response_text, "result_fingerprint": fingerprint})
        store_save(save_obj)
        return response_text

# ---------- mailbox (reward mail) ----------
# The live server delivers special/gift rewards on the USER's reward mail.
# Fully offline nobody ever sends one, so this server creates small local
# daily/attendance mails; claiming credits the account just like the real
# server would (persisted to the save file).

MAILBOX_GIFTS = (("GOLD", "100000"), ("RUBY", "250"), ("BP", "50"))

# ---------- ToolShop currency conversion ----------
# The Tower/Cloud Garden/Evolve-9 modes that normally pay out Cloud Piece and
# Celestial Essence are unreachable offline, so a small server-side exchange
# lets the player convert the supported game currencies into those resources.
# CONVERT_RATES[(from, to)] = (cost_units_of_from, gain_units_of_to).
# The player SPENDS COUNT units of `from`, gains floor(COUNT*gain/cost) of `to`
# (the leftover is never consumed).
# Only these six pairs are exposed by the ToolShop web page.  Keep the order
# stable because the client renders the API list directly.
CONVERT_RATES = {
    ("GOLD", "BP"):      (120000, 5),
    ("RUBY", "BP"):      (500, 50),
    ("GOLD", "RUBY"):    (2000, 1),
    ("RUBY", "GOLD"):    (1, 2000),
    ("RUBY", "CLOUD"):   (5, 1),
    ("RUBY", "ESSENCE"): (5, 1),
}

# Fixed 9-star evolution essence cost. The client never posts it: its
# ServerConnection.edit_cloud_garden sends only MODE/ADD_PIECE/ETC (CEL_PIECE
# is read but dropped), so the server has to apply the essence deduction by
# MODE and hand the new balance back as cel_essn.
CELESTIAL_PIECE_EVO_9 = 1000

# ---------- RubyFarm mini-games wallet ----------
# The web page rubyfarm.html plays small games and earns a SEPARATE wallet
# (s["wallet_ruby"]), then "withdraws" it into the game ruby (DATA1[2]).
# All rewards are granted server-side from the raw score, with a per-game
# cooldown and a per-day cap, so the page is just a front-end for the rules
# below. Tweak the numbers here to tune economy; no client change needed.
MINIGAME_CD_SEC = 3
DAILY_RUBY_CAP = 500
MOSS_MOON_CARE_PACKAGE_PRICE = 3
MOSS_MOON_CARE_PACKAGE_RUBY_BONUS = 1
MOSS_MOON_LUCKY_PATCH_MAX_LEVEL = 5
# Gold earned from selling produce is capped per server day. The cap scales with
# the plots you own, so early game is slow and 600k is only reachable at 50 plots:
# measured against a greedy "unlock every plot, sell every day" run, 10M gold
# takes 32 days (see TRI_THUC_DU_AN.md for the table).
MOSS_MOON_DAILY_GOLD_CAP = 600_000
MOSS_MOON_DAILY_GOLD_CAP_FLOOR = 120_000
MOSS_MOON_DAILY_GOLD_CAP_CURVE = 2.4
MOSS_MOON_SKILL_MAX = {"merchant": 5, "greenThumb": 5, "luckyPatch": 5,
                       "compost": 3, "plotSurvey": 3, "bigBasket": 5}
MOSS_MOON_GOLD_SKILL_COSTS = {"compost": [300, 1_500, 7_500],
                              "plotSurvey": [1_000, 4_000, 16_000],
                              "bigBasket": [400, 1_200, 3_600, 9_000, 22_000]}
MOSS_MOON_BIG_BASKET_CAPACITY = 12
MOSS_MOON_FARM_KEY = "moss_moon_farm_v1"
MOSS_MOON_CHARACTER_PRICES = {
    1: (1_000, 0), 2: (2_000, 0), 3: (8_000, 0), 4: (30_000, 0),
    5: (120_000, 0), 6: (400_000, 0), 7: (2_000_000, 450),
    8: (10_000_000, 2_500),
}

def _load_moss_moon_character_catalog() -> tuple[dict[int, dict], str | None]:
    wiki_path = BASE_DIR / "Wiki" / "data" / "characters.js"
    try:
        source = wiki_path.read_text(encoding="utf-8")
    except OSError:
        return {}, "character catalog unavailable"
    pattern = re.compile(
        r'\{\s*id:\s*(\d+),\s*name:\s*"([^"]+)",\s*'
        r'sourceAsset:\s*"[^"]+",\s*star:\s*(\d+),'
    )
    catalog = {}
    for match in pattern.finditer(source):
        char_id, name, star = int(match.group(1)), match.group(2), int(match.group(3))
        if char_id in catalog or not 1 <= char_id <= 114 or not 1 <= star <= 9:
            return {}, "character catalog invalid"
        catalog[char_id] = {"id": char_id, "name": name, "star": star}
    if set(catalog) != set(range(1, 115)):
        return {}, "character catalog incomplete"
    return catalog, None


MOSS_MOON_CHARACTER_CATALOG, MOSS_MOON_CHARACTER_CATALOG_ERROR = _load_moss_moon_character_catalog()
MOSS_MOON_CHARACTER_STARS = {
    char_id: info["star"] for char_id, info in MOSS_MOON_CHARACTER_CATALOG.items()
    if 1 <= info["star"] <= 8
}


def _guild_shop_hero_list() -> list:
    """`hero_list` cho card 1/2 cua Guild Shop (hero gacha).

    Client khong co endpoint nao de doi danh sach -> server cap `num` (=type_num
    gui len khi mua) cho tung hero. Bat buoc theo client:
      - `enable: true` — `glo.package.parse_hero_list` loc dung theo truong nay.
      - `char_num` + `times` — `S_GUILD_SHOP.refresh_popup_heroes` gom theo
        char_num; thieu `times:10` thi client tu suy `type_num_10 = type_num_1+1`.
      - `id` — `S_PACKAGE_STORE` doc khi mo tab hero.
    `char_num` lay tu catalog da validate 1..114, dung `co_ch<n>.png` (man ket
    qua) va `profile_icon_<n>.png` (icon trong popup chon hero) — ca hai bo
    anh deu day du 1..114.
    """
    import guild_backend

    out = []
    for char_id, info in sorted(MOSS_MOON_CHARACTER_CATALOG.items()):
        out.append({
            "id": "lunar_lucky_hero_%d" % char_id,
            "char_num": char_id,
            "times": 1,
            "num": guild_backend._shop_hero_type_num(char_id, 1),
            "enable": True,
            "cost": 4000, "costNoVat": 4000,
            "name": info["name"], "star": info["star"],
        })
    return out

# Grow times follow the requested price ladder: ~20 gold -> ~3 min, 150 -> 15 min,
# 500 -> 1 h, >3.000 -> 6 h, >10.000 -> 10 h, >50.000 -> 2 days, 75.000 -> 4 days,
# 200.000 -> 7 days. Above that the curve keeps stretching so the top crops stay
# endgame instead of dominating the daily gold cap.
MOSS_MOON_CROPS = {
    "carrot": {"name": "Carrot", "emoji": "🥕", "seed_cost": 18, "grow_ms": 180_000, "value": 34, "mutation": "Honey carrot"},
    "tomato": {"name": "Tomato", "emoji": "🍅", "seed_cost": 38, "grow_ms": 300_000, "value": 76, "mutation": "Sunblush tomato"},
    "strawberry": {"name": "Strawberry", "emoji": "🍓", "seed_cost": 52, "grow_ms": 360_000, "value": 92, "mutation": "Roseheart strawberry"},
    "sunflower": {"name": "Sunflower", "emoji": "🌻", "seed_cost": 78, "grow_ms": 480_000, "value": 144, "mutation": "Golden-hour sunflower"},
    "moonberry": {"name": "Moonberry", "emoji": "🫐", "seed_cost": 88, "grow_ms": 540_000, "value": 175, "mutation": "Star-kissed berry"},
    "pumpkin": {"name": "Pumpkin", "emoji": "🎃", "seed_cost": 115, "grow_ms": 720_000, "value": 210, "mutation": "Moonlit pumpkin"},
    "ember_chili": {"name": "Ember Chili", "emoji": "🌶️", "seed_cost": 180, "grow_ms": 900_000, "value": 360, "mutation": "Inferno Chili"},
    "frost_lily": {"name": "Frost Lily", "emoji": "🪷", "seed_cost": 650, "grow_ms": 3_600_000, "value": 1_650, "mutation": "Glacier Lily"},
    "blue_orchid": {"name": "Blue Orchid", "emoji": "🪻", "seed_cost": 1_200, "grow_ms": 7_200_000, "value": 3_800, "mutation": "Starlit Orchid"},
    "golden_melon": {"name": "Golden Melon", "emoji": "🍈", "seed_cost": 7_500, "grow_ms": 21_600_000, "value": 20_000, "mutation": "Sun-Crowned Melon"},
    "starfruit": {"name": "Starfruit", "emoji": "⭐", "seed_cost": 25_000, "grow_ms": 36_000_000, "value": 75_000, "mutation": "Comet Starfruit"},
    "nebula_wheat": {"name": "Nebula Wheat", "emoji": "🌾", "seed_cost": 120_000, "grow_ms": 432_000_000, "value": 360_000, "mutation": "Starlit Wheat"},
    "rubyflower": {"name": "Rubyflower", "emoji": "🌺", "seed_cost": 0, "seed_ruby_cost": 35, "grow_ms": 3_600_000, "value": 0, "ruby_value": 40, "mutation": "Rubyflower Bloom"},
    "diamond_bloom": {"name": "Diamond Bloom", "emoji": "💠", "seed_cost": 500_000, "grow_ms": 864_000_000, "value": 0, "diamond_value": 1, "mutation": "Prismatic Bloom"},
}
MOSS_MOON_STARTER_SEEDS = {
    "carrot": 7, "tomato": 3, "moonberry": 1,
    "strawberry": 2, "pumpkin": 1, "sunflower": 2,
}


class MossMoonActionError(ValueError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def _moss_moon_default_farm() -> dict:
    return {
        "gold": 560,
        "diamond": 3,
        "unlocked": 9,
        "capacity": 24,
        "goldDay": 0,
        "goldEarnedToday": 0,
        "goldOverflow": False,
        "seeds": {crop: MOSS_MOON_STARTER_SEEDS.get(crop, 0) for crop in MOSS_MOON_CROPS},
        "produce": {},
        "skills": {skill: 0 for skill in MOSS_MOON_SKILL_MAX},
        "plots": [None] * 50,
    }


def _moss_moon_today() -> int:
    return int(time.time() // 86_400)


def _moss_moon_gold_cap(unlocked: int) -> int:
    """Daily gold ceiling for an account with `unlocked` plots. 120k on day one,
    ramping to the 600k headline only at 50 plots, so 10M takes ~30 days."""
    span = max(0.0, min(1.0, (unlocked - 9) / 41.0))
    floor = MOSS_MOON_DAILY_GOLD_CAP_FLOOR
    cap = floor + (MOSS_MOON_DAILY_GOLD_CAP - floor) * math.pow(span, MOSS_MOON_DAILY_GOLD_CAP_CURVE)
    return int(math.floor(min(MOSS_MOON_DAILY_GOLD_CAP, cap) / 100) * 100)


def _moss_moon_gold_room(profile: dict, now: int | None = None) -> int:
    """Gold still sellable today. The daily cap is what makes 10M gold take a
    month: no amount of skill or mutation can outrun it."""
    today = _moss_moon_today() if now is None else now
    if profile["goldDay"] != today:
        profile["goldDay"] = today
        profile["goldEarnedToday"] = 0
        profile["goldOverflow"] = False
    return max(0, _moss_moon_gold_cap(profile["unlocked"]) - profile["goldEarnedToday"])


def _moss_moon_bounded_int(value, default: int, minimum: int = 0,
                           maximum: int = 2**53) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, parsed))


def _moss_moon_normalize_farm(raw) -> dict:
    profile = _moss_moon_default_farm()
    if not isinstance(raw, dict):
        return profile

    profile["gold"] = _moss_moon_bounded_int(raw.get("gold"), profile["gold"])
    profile["diamond"] = _moss_moon_bounded_int(raw.get("diamond"), profile["diamond"])
    profile["unlocked"] = _moss_moon_bounded_int(raw.get("unlocked"), 9, 7, 50)
    profile["capacity"] = _moss_moon_bounded_int(raw.get("capacity"), 24, 1, 100)

    raw_seeds = raw.get("seeds") if isinstance(raw.get("seeds"), dict) else {}
    profile["seeds"] = {
        crop: _moss_moon_bounded_int(raw_seeds.get(crop), MOSS_MOON_STARTER_SEEDS.get(crop, 0))
        for crop in MOSS_MOON_CROPS
    }

    raw_skills = raw.get("skills") if isinstance(raw.get("skills"), dict) else {}
    profile["skills"] = {
        skill: _moss_moon_bounded_int(raw_skills.get(skill), 0, 0, MOSS_MOON_SKILL_MAX[skill])
        for skill in MOSS_MOON_SKILL_MAX
    }

    profile["goldDay"] = _moss_moon_bounded_int(raw.get("goldDay"), 0)
    profile["goldEarnedToday"] = _moss_moon_bounded_int(raw.get("goldEarnedToday"), 0, 0, MOSS_MOON_DAILY_GOLD_CAP)
    profile["goldOverflow"] = bool(raw.get("goldOverflow"))

    raw_produce = raw.get("produce") if isinstance(raw.get("produce"), dict) else {}
    produce = {}
    remaining_capacity = profile["capacity"]
    for key, item in raw_produce.items():
        if not isinstance(item, dict) or remaining_capacity <= 0:
            continue
        crop_key = str(item.get("crop") or key).removesuffix("-mutated")
        crop = MOSS_MOON_CROPS.get(crop_key)
        if not crop:
            continue
        mutated = bool(item.get("mutated")) or str(key).endswith("-mutated")
        count = min(remaining_capacity, _moss_moon_bounded_int(item.get("count"), 0))
        if count <= 0:
            continue
        product_key = f"{crop_key}-mutated" if mutated else crop_key
        produce[product_key] = {
            "name": crop["mutation"] if mutated else crop["name"],
            "emoji": crop["emoji"],
            "value": crop["value"] * (3 if mutated else 1),
            "ruby_value": _int(crop.get("ruby_value"), 0),
            "diamond_value": _int(crop.get("diamond_value"), 0),
            "count": count, "crop": crop_key, "mutated": mutated,
        }
        remaining_capacity -= count
    profile["produce"] = produce

    now_ms = int(time.time() * 1000)
    raw_plots = raw.get("plots") if isinstance(raw.get("plots"), list) else []
    plots = [None] * 50
    for index, raw_plot in enumerate(raw_plots[:profile["unlocked"]]):
        if not isinstance(raw_plot, dict):
            continue
        crop_key = str(raw_plot.get("crop") or "")
        if crop_key not in MOSS_MOON_CROPS:
            continue
        planted_at = _moss_moon_bounded_int(raw_plot.get("plantedAt"), now_ms, 0, now_ms)
        plots[index] = {"crop": crop_key, "plantedAt": planted_at, "mutation": False}
    profile["plots"] = plots
    return profile


def _moss_moon_farm_public(profile: dict) -> dict:
    return {
        "gold": str(profile["gold"]), "diamond": str(profile["diamond"]),
        "unlocked": profile["unlocked"], "capacity": profile["capacity"],
        "seeds": dict(profile["seeds"]), "produce": profile["produce"],
        "skills": dict(profile["skills"]), "plots": profile["plots"],
    }


def _moss_moon_plot_price(unlocked: int) -> int:
    # Steeper than the old 1.34 curve: all 41 remaining plots now cost ~3.64M
    # gold, so plot unlocks are the main sink that stretches a 10M run to a month.
    return max(60, math.floor(200 * math.pow(max(1, unlocked - 7), 1.9) / 10) * 10)


def _moss_moon_add_harvest(profile: dict, index: int, now_ms: int) -> bool:
    plot = profile["plots"][index]
    if not isinstance(plot, dict) or plot.get("crop") not in MOSS_MOON_CROPS:
        raise MossMoonActionError("empty plot")
    crop_key = plot["crop"]
    crop = MOSS_MOON_CROPS[crop_key]
    grow_ms = crop["grow_ms"] * math.pow(0.91, profile["skills"]["greenThumb"])
    if now_ms - int(plot.get("plantedAt", now_ms)) < grow_ms:
        raise MossMoonActionError("crop not ready")
    used = sum(max(0, _int(item.get("count"), 0))
               for item in profile["produce"].values() if isinstance(item, dict))
    if used >= profile["capacity"]:
        raise MossMoonActionError("storage full")
    mutated = secrets.randbelow(10_000) < min(6_500, 1_200 + profile["skills"]["luckyPatch"] * 500)
    key = f"{crop_key}-mutated" if mutated else crop_key
    value = crop["value"] * (3 if mutated else 1)
    item = profile["produce"].setdefault(key, {
        "name": crop["mutation"] if mutated else crop["name"],
        "emoji": crop["emoji"], "value": value,
        "ruby_value": _int(crop.get("ruby_value"), 0),
        "diamond_value": _int(crop.get("diamond_value"), 0),
        "count": 0,
        "crop": crop_key, "mutated": mutated,
    })
    item["count"] += 1
    profile["plots"][index] = None
    return True


def _moss_moon_owned_character_ids(save: dict) -> set[int]:
    owned = set()
    for part in str(save.get("DATA2") or "").split(","):
        token = part.split(":", 1)[0].strip()
        if token.isdigit():
            owned.add(int(token))
    for mail in save.get("mails") or []:
        if str((mail or {}).get("what", "")).upper() == "CHAR":
            value = str((mail or {}).get("what_value", "")).strip()
            if value.isdigit():
                owned.add(int(value))
    return owned


def _moss_moon_wallet(body: dict, user_id: str) -> tuple[int, str]:
    """Serve the account-bound M&M farm, Ruby wallet, and character shop."""
    if not DB_FILE or not REQUIRE_LOGIN:
        return 503, json.dumps({"STATE": "ERROR", "msg": "account database required"})
    if not user_id or not account_exists(user_id):
        return 401, json.dumps({"STATE": "ERROR", "CODE": "AUTH_REQUIRED"})

    action = str(body.get("ACTION", "INFO") or "INFO").strip().upper()
    with SAVE_LOCK:
        try:
            if DB_CONN.in_transaction:
                DB_CONN.commit()
            DB_CONN.execute("BEGIN IMMEDIATE")
            row = DB_CONN.execute("SELECT payload FROM saves WHERE id=?", (user_id,)).fetchone()
            if not row:
                DB_CONN.rollback()
                return 404, json.dumps({"STATE": "ERROR", "msg": "account save missing"})
            save = _norm_save(json.loads(row[0]))
            wallet = max(0, _int(save.get("wallet_ruby"), 0))
            profile = _moss_moon_normalize_farm(save.get(MOSS_MOON_FARM_KEY))
            save[MOSS_MOON_FARM_KEY] = profile

            if action == "INFO":
                DB_CONN.execute("UPDATE saves SET payload=? WHERE id=?",
                                (json.dumps(save, ensure_ascii=False), user_id))
                DB_CONN.commit()
                return 200, json.dumps({
                    "STATE": "SUCCESS", "wallet": str(wallet),
                    "account_id": user_id,
                    "farm": _moss_moon_farm_public(profile),
                    "character_shop_available": not MOSS_MOON_CHARACTER_CATALOG_ERROR,
                    "character_prices": {
                        str(star): {"gold": str(cost[0]), "ruby": str(cost[1])}
                        for star, cost in MOSS_MOON_CHARACTER_PRICES.items()
                    },
                    "characters": [
                        info for char_id, info in sorted(MOSS_MOON_CHARACTER_CATALOG.items())
                        if char_id in MOSS_MOON_CHARACTER_STARS
                    ],
                }, ensure_ascii=False)

            action_id = str(body.get("ACTION_ID", "") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", action_id):
                DB_CONN.rollback()
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad action id"})

            request = {key: body.get(key) for key in (
                "ACTION", "CROP", "PLOT", "KEY", "TYPE", "LEVEL", "CHARACTER_ID",
            ) if key in body}
            request["ACTION"] = action
            fingerprint = hashlib.sha256(json.dumps(
                request, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            previous = DB_CONN.execute(
                "SELECT request_fingerprint,response_json FROM moss_moon_wallet_ops "
                "WHERE user_id=? AND action_id=?", (user_id, action_id)
            ).fetchone()
            if previous:
                DB_CONN.rollback()
                if previous[0] != fingerprint:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "action id conflict"})
                return 200, previous[1]

            response_extra = {"ACTION_ID": action_id}
            try:
                if action == "BUY_CHARACTER":
                    if MOSS_MOON_CHARACTER_CATALOG_ERROR:
                        raise MossMoonActionError("character catalog unavailable")
                    try:
                        character_id = int(body.get("CHARACTER_ID", "0"))
                    except (TypeError, ValueError):
                        raise MossMoonActionError("invalid character") from None
                    star = MOSS_MOON_CHARACTER_STARS.get(character_id)
                    if star is None:
                        raise MossMoonActionError("character unavailable")
                    owned = _moss_moon_owned_character_ids(save)
                    if character_id in owned:
                        raise MossMoonActionError("character already owned")
                    gold_cost, ruby_cost = MOSS_MOON_CHARACTER_PRICES[star]
                    if profile["gold"] < gold_cost:
                        raise MossMoonActionError("not enough farm gold", {"gold_cost": str(gold_cost)})
                    if wallet < ruby_cost:
                        raise MossMoonActionError("not enough ruby", {"ruby_cost": str(ruby_cost)})
                    profile["gold"] -= gold_cost
                    wallet -= ruby_cost
                    mails = save.get("mails")
                    if not isinstance(mails, list):
                        mails = []
                    mail_sn = next_mail_sn(mails)
                    mails.append({"sn": mail_sn, "why": "MOSS & MOON CHARACTER SHOP",
                                  "what": "CHAR", "what_value": str(character_id),
                                  "start_date": time.strftime("%Y-%m-%d"),
                                  "end_date": "20991231"})
                    save["mails"] = mails
                    response_extra.update({"action": "character", "character_id": character_id,
                                           "character_name": MOSS_MOON_CHARACTER_CATALOG[character_id]["name"],
                                           "star": star, "spent_gold": str(gold_cost),
                                           "spent_ruby": str(ruby_cost), "mail_sn": mail_sn})
                elif action == "BUY_CARE_PACKAGE":
                    cost = MOSS_MOON_CARE_PACKAGE_PRICE
                    if wallet < cost:
                        raise MossMoonActionError("not enough ruby", {"cost": str(cost)})
                    wallet = wallet - cost + MOSS_MOON_CARE_PACKAGE_RUBY_BONUS
                    profile["seeds"]["carrot"] += 3
                    profile["seeds"]["tomato"] += 2
                    response_extra.update({"action": "care_package", "spent_ruby": str(cost),
                                           "ruby_bonus": str(MOSS_MOON_CARE_PACKAGE_RUBY_BONUS)})
                elif action == "BUY_LUCKY_PATCH":
                    level = int(body.get("LEVEL", "0"))
                    current = profile["skills"]["luckyPatch"]
                    if level != current + 1 or level > MOSS_MOON_LUCKY_PATCH_MAX_LEVEL:
                        raise MossMoonActionError("bad skill level", {"level": current})
                    cost = 3 + current * 2
                    if wallet < cost:
                        raise MossMoonActionError("not enough ruby", {"cost": str(cost)})
                    wallet -= cost
                    profile["skills"]["luckyPatch"] = level
                    response_extra.update({"action": "lucky_patch", "spent_ruby": str(cost)})
                elif action == "BUY_SEED":
                    crop_key = str(body.get("CROP", ""))
                    crop = MOSS_MOON_CROPS.get(crop_key)
                    if not crop:
                        raise MossMoonActionError("unknown crop")
                    ruby_cost = _int(crop.get("seed_ruby_cost"), 0)
                    gold_cost = _int(crop.get("seed_cost"), 0)
                    if gold_cost:
                        gold_cost = max(1, math.floor(gold_cost * (1 - profile["skills"]["compost"] * 0.05)))
                    if ruby_cost:
                        if wallet < ruby_cost:
                            raise MossMoonActionError("not enough ruby", {"cost": str(ruby_cost)})
                        wallet -= ruby_cost
                    else:
                        if profile["gold"] < gold_cost:
                            raise MossMoonActionError("not enough farm gold", {"cost": str(gold_cost)})
                        profile["gold"] -= gold_cost
                    profile["seeds"][crop_key] += 1
                    response_extra.update({"action": "buy_seed", "crop": crop_key,
                                           "spent_gold": str(gold_cost), "spent_ruby": str(ruby_cost)})
                elif action == "UNLOCK_PLOT":
                    if profile["unlocked"] >= 50:
                        raise MossMoonActionError("all plots unlocked")
                    cost = _moss_moon_plot_price(profile["unlocked"])
                    cost = max(60, math.floor(cost * (1 - profile["skills"]["plotSurvey"] * 0.07)))
                    if profile["gold"] < cost:
                        raise MossMoonActionError("not enough farm gold", {"cost": str(cost)})
                    profile["gold"] -= cost
                    profile["unlocked"] += 1
                    response_extra.update({"action": "unlock_plot", "spent_gold": str(cost)})
                elif action == "UPGRADE_STORAGE":
                    storage_type = str(body.get("TYPE", ""))
                    if profile["capacity"] >= 100:
                        raise MossMoonActionError("storage maxed")
                    if storage_type == "gold":
                        cost, amount = 240, 12
                        if profile["gold"] < cost:
                            raise MossMoonActionError("not enough farm gold", {"cost": str(cost)})
                        profile["gold"] -= cost
                    elif storage_type == "diamond":
                        cost, amount = 2, 24
                        if profile["diamond"] < cost:
                            raise MossMoonActionError("not enough diamonds", {"cost": str(cost)})
                        profile["diamond"] -= cost
                    else:
                        raise MossMoonActionError("unknown storage type")
                    profile["capacity"] = min(100, profile["capacity"] + amount)
                    response_extra.update({"action": "upgrade_storage", "type": storage_type})
                elif action == "BUY_SKILL":
                    skill = str(body.get("KEY", ""))
                    if skill not in MOSS_MOON_SKILL_MAX:
                        raise MossMoonActionError("unknown skill")
                    level = profile["skills"][skill]
                    if level >= MOSS_MOON_SKILL_MAX[skill]:
                        raise MossMoonActionError("skill maxed")
                    if skill == "merchant":
                        cost = 180 + level * 220
                        if profile["gold"] < cost:
                            raise MossMoonActionError("not enough farm gold", {"cost": str(cost)})
                        profile["gold"] -= cost
                    elif skill == "greenThumb":
                        cost = 1 + level // 2
                        if profile["diamond"] < cost:
                            raise MossMoonActionError("not enough diamonds", {"cost": str(cost)})
                        profile["diamond"] -= cost
                    else:
                        cost = MOSS_MOON_GOLD_SKILL_COSTS[skill][level]
                        if profile["gold"] < cost:
                            raise MossMoonActionError("not enough farm gold", {"cost": str(cost)})
                        profile["gold"] -= cost
                    profile["skills"][skill] += 1
                    if skill == "bigBasket":
                        profile["capacity"] = min(100, profile["capacity"] + MOSS_MOON_BIG_BASKET_CAPACITY)
                    response_extra.update({"action": "buy_skill", "key": skill, "level": profile["skills"][skill]})
                elif action == "PLANT":
                    crop_key = str(body.get("CROP", ""))
                    crop = MOSS_MOON_CROPS.get(crop_key)
                    try:
                        plot_index = int(body.get("PLOT", "-1"))
                    except (TypeError, ValueError):
                        plot_index = -1
                    if not crop or not 0 <= plot_index < profile["unlocked"]:
                        raise MossMoonActionError("invalid planting request")
                    if profile["plots"][plot_index] is not None:
                        raise MossMoonActionError("plot occupied")
                    if profile["seeds"].get(crop_key, 0) <= 0:
                        raise MossMoonActionError("no seeds")
                    profile["seeds"][crop_key] -= 1
                    profile["plots"][plot_index] = {"crop": crop_key,
                                                    "plantedAt": int(time.time() * 1000),
                                                    "mutation": False}
                    response_extra.update({"action": "plant", "plot": plot_index})
                elif action in {"HARVEST", "HARVEST_ALL"}:
                    indices = list(range(profile["unlocked"])) if action == "HARVEST_ALL" else []
                    if action == "HARVEST":
                        try:
                            indices = [int(body.get("PLOT", "-1"))]
                        except (TypeError, ValueError):
                            raise MossMoonActionError("invalid plot") from None
                    now_ms = int(time.time() * 1000)
                    gathered = []
                    for index in indices:
                        if not 0 <= index < profile["unlocked"]:
                            raise MossMoonActionError("invalid plot")
                        try:
                            if _moss_moon_add_harvest(profile, index, now_ms):
                                gathered.append(index)
                        except MossMoonActionError as exc:
                            if action == "HARVEST":
                                raise
                            if str(exc) not in {"empty plot", "crop not ready", "storage full"}:
                                raise
                    if not gathered and action == "HARVEST":
                        raise MossMoonActionError("nothing harvested")
                    response_extra.update({"action": "harvest", "gathered": gathered})
                elif action in {"SELL", "SELL_ALL"}:
                    item_key = str(body.get("KEY", ""))
                    keys = list(profile["produce"]) if action == "SELL_ALL" else [item_key]
                    room = _moss_moon_gold_room(profile)
                    sold = 0
                    revenue = 0
                    ruby_earned = 0
                    diamonds_earned = 0
                    for key in keys:
                        item = profile["produce"].get(key)
                        if not isinstance(item, dict):
                            if action == "SELL":
                                raise MossMoonActionError("produce not found")
                            continue
                        count = max(0, _int(item.get("count"), 0))
                        crop = MOSS_MOON_CROPS.get(item.get("crop"))
                        if not crop:
                            raise MossMoonActionError("unknown produce crop")
                        unit = math.floor(crop["value"] * (3 if item.get("mutated") else 1)
                                          * (1 + profile["skills"]["merchant"] * 0.1))
                        sold_here = 0
                        while count > 0 and (room >= unit or (sold_here == 0 and not profile["goldOverflow"])):
                            # the cap is soft: one produce per day may overshoot it, so a crop
                            # worth more than the room left can never become unsellable
                            if room < unit:
                                profile["goldOverflow"] = True
                            count -= 1
                            room -= unit
                            sold_here += 1
                        if sold_here:
                            revenue += sold_here * unit
                            sold += sold_here
                            ruby_earned += sold_here * _int(crop.get("ruby_value"), 0)
                            diamonds_earned += sold_here * _int(crop.get("diamond_value"), 0)
                        if count > 0:
                            # daily gold cap reached: the rest stays in the pantry
                            item = dict(item)
                            item["count"] = count
                            profile["produce"][key] = item
                        else:
                            profile["produce"].pop(key, None)
                    if sold <= 0:
                        raise MossMoonActionError("gold cap reached today" if room <= 0 else "no produce",
                                                 {"cap": str(_moss_moon_gold_cap(profile["unlocked"]))})
                    wallet += ruby_earned
                    profile["goldEarnedToday"] += revenue
                    profile["gold"] += revenue
                    profile["diamond"] += diamonds_earned
                    response_extra.update({"action": "sell", "sold": sold,
                                           "earned_gold": str(revenue),
                                           "earned_ruby": str(ruby_earned),
                                           "earned_diamond": str(diamonds_earned),
                                            "gold_cap": str(_moss_moon_gold_cap(profile["unlocked"])),

                                           "gold_earned_today": str(profile["goldEarnedToday"])})
                elif action == "RESET_FARM":
                    profile["plots"] = [None] * 50
                    profile["unlocked"] = 9
                    profile["capacity"] = 24
                    profile["seeds"] = {crop: 0 for crop in MOSS_MOON_CROPS}
                    profile["produce"] = {}
                    profile["skills"] = {skill: 0 for skill in MOSS_MOON_SKILL_MAX}
                    profile["goldDay"] = 0
                    profile["goldEarnedToday"] = 0
                    profile["goldOverflow"] = False
                    response_extra.update({"action": "reset_farm"})
                else:
                    raise MossMoonActionError("unknown action")
            except MossMoonActionError as exc:
                DB_CONN.rollback()
                return 200, json.dumps({"STATE": "ERROR", "msg": str(exc), **exc.details}, ensure_ascii=False)
            except (TypeError, ValueError, OverflowError):
                DB_CONN.rollback()
                return 200, json.dumps({"STATE": "ERROR", "msg": "invalid request"})

            save["wallet_ruby"] = str(wallet)
            save[MOSS_MOON_FARM_KEY] = profile
            response = {"STATE": "SUCCESS", "ACTION_ID": action_id,
                        "wallet": str(wallet), "farm": _moss_moon_farm_public(profile),
                        **response_extra}
            response_json = json.dumps(response, ensure_ascii=False)
            DB_CONN.execute("UPDATE saves SET payload=? WHERE id=?",
                            (json.dumps(save, ensure_ascii=False), user_id))
            DB_CONN.execute(
                "INSERT INTO moss_moon_wallet_ops "
                "(user_id,action_id,request_fingerprint,response_json,created_at) VALUES (?,?,?,?,?)",
                (user_id, action_id, fingerprint, response_json, int(time.time()))
            )
            DB_CONN.commit()
            return 200, response_json
        except Exception:
            DB_CONN.rollback()
            raise

# Optional entry fee in GOLD to play a mini game (future feature — user wants
# "play costs gold" for some games). Set MINIGAME_COST[game] = gold_y to enable;
# the fee is deducted atomically inside wallet/award.php when a reward is claimed.
# Keep it {} and games are free to play, as today.
MINIGAME_COST = {}

# ---- Tickets — paid mini-games ----
# Two ticket types gate the "stakes" games. Playing costs the matching ticket;
# a ticket play NEVER checks the per-day attempt cap and is NOT recorded in the
# daily play tracker (that was the old generator 3/day rule — tickets replace it).
# Tickets come from: daily free grant, daily check-in, or the shop (gold).
TICKET_PRICES = {"generator": 2000, "sudoku": 800}  # buy price in gold
TICKET_FREE_DAILY = {"generator": 3, "sudoku": 3}    # free grant per calendar day

# ---- Generator Repair — paid "stakes" game ----
# Each difficulty costs TICKET generator ticket(s) to open one run; finishing it
# pays PRIZE into the wallet, plus GREAT bonus per great hit of that run. Losing
# (>= miss threshold) ends the run with no prize; the ticket is consumed either
# way. No per-day limit anymore — the ticket is the gate.
GENREP_SESSION_TTL = 900       # seconds a paid run stays claimable
GENREP_GREAT_CAP = 25          # clamp great hits counted for the bonus
GENREP_DIFFS = {
    "easy":     {"ticket": 1, "prize": 10,  "great": 1, "miss": 3},
    "normal":   {"ticket": 1, "prize": 20,  "great": 2, "miss": 3},
    "hard":     {"ticket": 1, "prize": 50,  "great": 3, "miss": 5},
    "nightmare": {"ticket": 1, "prize": 150, "great": 7, "miss": 10},
}

# ---- Sudoku — paid "stakes" game ----
# Each difficulty costs TICKET sudoku ticket(s); each puzzle has a TIME limit
# (seconds, reasonable for real solving). Finishing within the limit pays PRIZE
# (ruby grows with difficulty); running out of time loses the run (ticket is
# consumed, no prize).
# SUDOKU_SESSION_TTL is only a FLOOR: the session of a run is valid for that
# difficulty's own time limit plus SUDOKU_CLAIM_GRACE, otherwise the 20/25 min
# tiers could never be claimed (their clock is longer than the floor).
SUDOKU_SESSION_TTL = 900
SUDOKU_CLAIM_GRACE = 120  # slack for the last keystroke + network round-trip
SUDOKU_DIFFS = {
    "easy":   {"ticket": 1, "prize": 10,  "time": 600},
    "medium": {"ticket": 1, "prize": 20,  "time": 900},
    "hard":   {"ticket": 1, "prize": 35,  "time": 1200},
    "expert": {"ticket": 1, "prize": 50,  "time": 1500},
}

# Daily check-in gift list for the web page: one reward per day-of-month
# (day N uses CHECKIN_REWARDS[N-1]). Types: GOLD/RUBY/BP/CLOUD/ESSENCE plus
# GTICKET (generator ticket) and STICKET (sudoku ticket).
# The server grants the reward directly into the game account, once per day.
# GOLD and RUBY values below already include REWARD_MULT=5 (vàng & ruby ×5
# cho mọi phần thưởng) — đổi hằng này rồi nhân lại các ô GOLD/RUBY bằng tay.
REWARD_MULT = 5
CHECKIN_REWARDS = [
    ("GOLD", 150000), ("BP", 20), ("STICKET", 1), ("RUBY", 100), ("CLOUD", 5),
    ("GOLD", 300000), ("GTICKET", 1), ("ESSENCE", 5), ("RUBY", 150), ("STICKET", 2),
    ("BP", 50), ("CLOUD", 8), ("GOLD", 500000), ("GTICKET", 2), ("RUBY", 150),
    ("ESSENCE", 8), ("STICKET", 2), ("BP", 80), ("CLOUD", 10), ("RUBY", 250),
    ("GOLD", 750000), ("GTICKET", 3), ("BP", 100), ("STICKET", 3), ("ESSENCE", 10),
    ("CLOUD", 15), ("RUBY", 150), ("GTICKET", 3), ("GOLD", 1300000), ("RUBY", 400),
    ("RUBY", 400),
]


def ensure_ticket_grant(s):
    today = time.strftime("%Y%m%d")
    if s.get("ticket_free_day") == today:
        return
    t = s.get("tickets")
    if not isinstance(t, dict):
        t = {}
    for k, n in TICKET_FREE_DAILY.items():
        try:
            t[k] = int(t.get(k, 0) or 0) + n
        except (TypeError, ValueError):
            t[k] = n
    s["tickets"] = t
    s["ticket_free_day"] = today


def ticket_count(s, kind):
    t = s.get("tickets")
    return int(t.get(kind, 0)) if isinstance(t, dict) else 0


def spend_tickets(s, kind, n):
    t = s.get("tickets")
    if not isinstance(t, dict):
        t = {}
    cur = int(t.get(kind, 0) or 0)
    if cur < n:
        return None
    t[kind] = cur - n
    s["tickets"] = t
    return cur - n


def add_tickets(s, kind, n):
    t = s.get("tickets")
    if not isinstance(t, dict):
        t = {}
    t[kind] = int(t.get(kind, 0) or 0) + n
    s["tickets"] = t
    return t[kind]


def _minigame_ruby(game: str, score: int) -> int:
    score = max(0, int(score))
    if game == "catch":        # clicks in 30s
        return min(30, score // 10)
    if game == "memory":       # pairs matched
        return min(20, score)
    if game == "guess":        # moves to find 1..100
        return min(15, max(0, 8 - score))
    if game == "simon":        # sequence length reached
        return min(25, max(0, score - 1))
    if game == "rps":          # wins out of 3 rounds
        return min(15, score * 5)
    if game == "slide":        # 2048: highest tile value
        return min(30, max(0, score // 128))
    return 0
CONVERT_LABELS = {
    "GOLD": "Gold", "RUBY": "Ruby", "BP": "BP",
    "CLOUD": "Cloud Piece", "ESSENCE": "Celestial Essence",
}

# The client awards the normal attendance reward by calling
# cnm_update_user_to_server_cry.php with MODE=att, then expects the server to
# return ATT_GIVEN=true and deliver the reward to the mailbox.  Keep the
# currency rewards from the bundled 21-day attendance table here.  The live
# table's character days are represented as a claimable gold fallback because
# the offline save format does not have a safe, standalone character-mail
# writer.
ATTENDANCE_REWARDS = (
    ("GOLD", 100000), ("RUBY", 25), ("GOLD", 200000),
    ("RUBY", 25), ("GOLD", 300000), ("RUBY", 50),
    ("GOLD", 500000), ("GOLD", 150000), ("RUBY", 50),
    ("GOLD", 250000), ("RUBY", 100), ("GOLD", 350000),
    ("RUBY", 150), ("GOLD", 500000), ("GOLD", 200000),
    ("RUBY", 140), ("GOLD", 300000), ("RUBY", 160),
    ("GOLD", 500000), ("RUBY", 200), ("GOLD", 500000),
)


def issue_attendance_reward(s: dict, data1: str) -> tuple[bool, int, str | None]:
    """Issue one attendance reward for the date/count in the submitted DATA1.

    Returns (given, cycle_day, mail_sn).  The date marker is separate from the
    client DATA1 so a reload cannot award the same day's mail twice.
    """
    fields = (data1 or "").split(",")
    if len(fields) <= 12:
        return False, 0, None
    att_date = str(fields[11]).strip()
    try:
        chul_num = int(float(fields[12] or 0))
    except (TypeError, ValueError):
        chul_num = 0
    if not att_date or chul_num <= 0:
        return False, 0, None

    cycle_day = ((chul_num - 1) % len(ATTENDANCE_REWARDS)) + 1
    # get_reward2_mailbox parses SN with parseInt(), so it must be numeric.
    # Suffix 9 keeps this separate from the three normal daily-gift mails
    # (which use suffixes 1..3 for the same date).
    mail_sn = att_date + "9"
    mails = s.get("mails") or []
    legacy_mail_sn = "ATT" + att_date
    for mail in mails:
        if str(mail.get("sn")) == legacy_mail_sn:
            mail["sn"] = mail_sn
    already_marked = s.get("attendance_reward_date") == att_date
    already_mailed = any(str(m.get("sn")) == mail_sn for m in mails)
    if already_marked or already_mailed:
        # A previous server response may have been interrupted after the mail
        # was written.  Treat that as already granted, never duplicate it.
        s["attendance_reward_date"] = att_date
        return True, cycle_day, mail_sn

    what, value = ATTENDANCE_REWARDS[cycle_day - 1]
    mails.append({
        "sn": mail_sn,
        "what": what,
        "what_value": str(value),
        "why": "DAILY ATTENDANCE",
    })
    s["mails"] = mails
    s["attendance_reward_date"] = att_date
    return True, cycle_day, mail_sn

               # The client adds the SAME number it credits, so the multiplied
               # gold/ruby/bp persist in the save (never reverts on reload).

def next_mail_sn(mails: list) -> str:
    """Next collision-free numeric mail SN. Daily/attendance mails use the
    11-digit YYYYMMDD+key scheme; reward mails start at YYYYMMDD*1000000
    (14 digits, still < 2^53 so parseInt() survives) so they never overlap."""
    base = int(time.strftime("%Y%m%d")) * 1000000
    used = set()
    for m in mails:
        sn = str(m.get("sn", "") or "").strip()
        if sn.lstrip("+-").isdigit():
            used.add(int(sn))
    sn = base
    while sn in used:
        sn += 1
    return str(sn)


def _item_gacha_bp_purchase(body: dict) -> tuple[int, str]:
    """Server-authoritative Lunar Lucky draw paid with BP.

    The Guild Shop and BP Gacha share the same reward roller. The client may
    send its old preview fields for compatibility, but they are ignored.
    """
    try:
        type_num = int(float(body.get("TYPE_NUM") or 0))
    except (TypeError, ValueError):
        type_num = 0
    price = {26: 1000, 27: 10000}.get(type_num)
    if price is None:
        return 200, json.dumps({"STATUS": "ERROR", "ERROR_CODE": "INVALID_GACHA"})
    times = 1 if type_num == 26 else 10
    try:
        slot = int(float(body.get("GACHA_SLOT") or 0))
    except (TypeError, ValueError):
        slot = 0
    if slot < 1 or slot > 4:
        slot = 0
    request_id = str(body.get("GACHA_ID") or "").strip()[:128]
    uid = _uid()

    def make_response(save, rewards):
        d1 = str(save.get("DATA1") or "").split(",")
        while len(d1) < 3:
            d1.append("0")
        return {
            "STATUS": "SUCCESS", "RESULT": 0, "RESULT_ITEM_NUM": 0,
            "ADD_OPTION": "", "ADD_OPTION_NUM": 0,
            "after_gold": str(d1[1]), "after_ruby": str(d1[2]),
            "bp": str(save.get("bp") or 0),
            "cloud_piece": str(save.get("cloud_piece") or 0),
            "reward_info": rewards, "TYPE_NUM": type_num,
        }

    def mutate(save):
        d1 = str(save.get("DATA1") or "").split(",")
        while len(d1) < 3:
            d1.append("0")
        gold = int(float(d1[1] or 0))
        ruby = int(float(d1[2] or 0))
        bp = int(float(save.get("bp") or 0))
        cloud = int(float(save.get("cloud_piece") or 0))
        if bp < price:
            return None, {"STATUS": "ERROR", "ERROR_CODE": "NOT_ENOUGH_BP",
                           "bp": str(bp)}
        rewards = roll_lunar_lucky_rewards(times, slot)
        mails = list(save.get("mails") or [])
        for reward in rewards:
            kind = reward["type"]
            value = int(reward["value"])
            if kind == "ITEM":
                mails.append({"sn": next_mail_sn(mails),
                              "why": "LUNAR LUCKY PACKAGE",
                              "what": "ITEM", "what_value": str(value),
                              "start_date": time.strftime("%Y-%m-%d"),
                              "end_date": "20991231"})
            elif kind == "GOLD":
                gold += value
            elif kind == "RUBY":
                ruby += value
            elif kind == "BP":
                bp += value
            elif kind == "CLOUD":
                cloud += value
        bp -= price
        d1[1], d1[2] = str(gold), str(ruby)
        save["DATA1"] = ",".join(d1)
        save["bp"] = str(bp)
        save["cloud_piece"] = str(cloud)
        save["mails"] = mails
        return rewards, None

    if DB_FILE and DB_CONN is not None:
        with SAVE_LOCK:
            if DB_CONN.in_transaction:
                DB_CONN.commit()
            DB_CONN.execute("BEGIN IMMEDIATE")
            try:
                if request_id:
                    old = DB_CONN.execute(
                        "SELECT type_num, response_json FROM item_gacha_bp_ops "
                        "WHERE user_id=? AND request_id=?", (uid, request_id)
                    ).fetchone()
                    if old:
                        if int(old[0]) != type_num:
                            DB_CONN.rollback()
                            return 200, json.dumps({
                                "STATUS": "ERROR",
                                "ERROR_CODE": "GACHA_REQUEST_CONFLICT"})
                        DB_CONN.commit()
                        return 200, old[1]
                row = DB_CONN.execute(
                    "SELECT payload FROM saves WHERE id=?", (uid,)
                ).fetchone()
                save = _norm_save(json.loads(row[0])) if row else {}
                rewards, error = mutate(save)
                if error:
                    DB_CONN.rollback()
                    return 200, json.dumps(error)
                response = json.dumps(make_response(save, rewards),
                                      ensure_ascii=False)
                DB_CONN.execute(
                    "UPDATE saves SET payload=? WHERE id=?",
                    (json.dumps(save, ensure_ascii=False), uid))
                if request_id:
                    DB_CONN.execute(
                        "INSERT INTO item_gacha_bp_ops "
                        "(user_id,request_id,type_num,response_json,created_at) "
                        "VALUES (?,?,?,?,?)",
                        (uid, request_id, type_num, response, int(time.time())))
                DB_CONN.commit()
                return 200, response
            except Exception:
                DB_CONN.rollback()
                raise

    with SAVE_LOCK:
        save = load_save()
        rewards, error = mutate(save)
        if error:
            return 200, json.dumps(error)
        store_save(save)
        return 200, json.dumps(make_response(save, rewards), ensure_ascii=False)


def _farm_public(state):
    return {key: value for key, value in state.items() if key != "receipts"}


def _farm_persist(uid, save):
    """Write the farm and mailbox together; caller owns SAVE_LOCK and DB commit."""
    data = json.dumps(save, ensure_ascii=False)
    if DB_FILE:
        changed = DB_CONN.execute("UPDATE saves SET payload=? WHERE id=?", (data, uid)).rowcount
        if changed != 1:
            raise OSError("farm account save missing")
        return
    tmp = SAVE_FILE.with_name(SAVE_FILE.name + ".farm.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, SAVE_FILE)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _farm_endpoint(kind, body_str):
    if DB_FILE and REQUIRE_LOGIN and not getattr(_tl, "uid", ""):
        return 401, json.dumps({"STATE": "ERROR", "message": "login required"})
    if kind == "action" and getattr(_tl, "method", "") != "POST":
        return 405, json.dumps({"STATE": "ERROR", "message": "POST required"})
    body = parse_body(body_str)
    if not isinstance(body, dict):
        return 400, json.dumps({"STATE": "ERROR", "message": "invalid request"})
    action_id = str(body.get("ACTION_ID", ""))
    if kind == "action" and not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", action_id):
        return 400, json.dumps({"STATE": "ERROR", "message": "invalid action id"})

    def integer(name, default=None):
        raw = body.get(name)
        if raw is None or raw == "":
            return default
        if not re.fullmatch(r"-?[0-9]+", str(raw)):
            raise farm_core.FarmError("invalid " + name.lower())
        return int(raw)

    today = time.strftime("%Y%m%d")
    uid = _uid()
    try:
        with SAVE_LOCK:
            if DB_FILE:
                DB_CONN.execute("BEGIN IMMEDIATE")
            try:
                if DB_FILE:
                    row = DB_CONN.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
                    if row is None:
                        raise farm_core.FarmError("account save missing")
                    save = _norm_save(json.loads(row[0]))
                else:
                    save = load_save()
                stored_state = save.get("ruby_garden_v1")
                state = farm_core.ensure_starter_pack(
                    stored_state or farm_core.new_farm(day=today))
                if kind == "state":
                    updated = farm_core.advance_day(state, today)
                    response = {"STATE": "SUCCESS", "farm": _farm_public(updated),
                                "server_day": today,
                                "catalog": {"crops": farm_core.CROPS, "items": farm_core.ITEMS,
                                            "skills": farm_core.SKILLS, "missions": farm_core.MISSIONS,
                                            "characters": farm_core.CHARACTER_OFFERS,
                                            "land_costs": farm_core.LAND_COSTS,
                                            "watering_can_costs": farm_core.WATERING_CAN_COSTS}}
                    if updated != stored_state:
                        save["ruby_garden_v1"] = updated
                        _farm_persist(uid, save)
                else:
                    action = str(body.get("ACTION", "")).strip().lower()
                    args = {"plot_id": integer("PLOT"), "crop": body.get("CROP"),
                            "quantity": integer("QUANTITY", 1), "item": body.get("ITEM"),
                            "skill": body.get("SKILL"), "mission": body.get("MISSION"),
                            "upgrade": body.get("UPGRADE"),
                            "character_id": integer("CHARACTER_ID")}
                    fingerprint = json.dumps([action, args], sort_keys=True, ensure_ascii=False)
                    previous = state.get("receipts", {}).get(action_id)
                    if previous:
                        if previous["fingerprint"] != fingerprint:
                            raise farm_core.FarmError("action id conflict")
                        response = previous["response"]
                    else:
                        updated, event = farm_core.apply_action(state, action, today, **args)
                        if "mail" in event:
                            mails = save.get("mails") or []
                            mails.append({"sn": next_mail_sn(mails), "why": "RUBY GARDEN PURCHASE",
                                          "what": event["mail"]["what"],
                                          "what_value": event["mail"]["what_value"]})
                            save["mails"] = mails
                        response = {"STATE": "SUCCESS", "farm": _farm_public(updated),
                                    "event": event, "server_day": today}
                        updated.setdefault("receipts", {})[action_id] = {
                            "fingerprint": fingerprint, "response": response}
                        save["ruby_garden_v1"] = updated
                        _farm_persist(uid, save)
                if DB_FILE:
                    DB_CONN.commit()
                return 200, json.dumps(response, ensure_ascii=False)
            except Exception:
                if DB_FILE:
                    DB_CONN.rollback()
                raise
    except farm_core.FarmError as exc:
        return 200, json.dumps({"STATE": "ERROR", "message": str(exc)})
    except Exception:
        LOG.exception("Ruby Garden request failed")
        return 500, json.dumps({"STATE": "ERROR", "message": "farm save failed"})

# One-time offline welcome batch, seeded by the server itself (not via the
# client's put_reward_char) so the mailbox always has something to claim.
# Seeded once per stamp; after the player claims the mails they are gone for
# good (never respawned) so nothing can be farmed.
OFFLINE_GIFT_STAMP = "20260921"
# Only the low-id character is gifted. 97 and 99 were dropped on 26/09/2026 at
# the user's request: they are the strongest of the original three.
OFFLINE_GIFT_CHARS = (96,)

def mailbox_ensure_offline_gift(s: dict) -> list:
    """Seed the one-time OFFLINE GIFT batch into save['mails']."""
    mails = s.get("mails") or []
    if s.get("offline_gift_sent") == OFFLINE_GIFT_STAMP:
        return mails
    s["offline_gift_sent"] = OFFLINE_GIFT_STAMP
    gifts = [
        ("GOLD", "100000", "OFFLINE GIFT"),
        ("RUBY", "250", "OFFLINE GIFT"),
        ("BP", "50", "OFFLINE GIFT"),
    ]
    for cid in OFFLINE_GIFT_CHARS:
        gifts.append(("CHAR", str(cid), "OFFLINE GIFT CHARACTER"))
    for what, value, why in gifts:
        mails.append({
            "sn": next_mail_sn(mails),
            "why": why,
            "what": what,
            "what_value": value,
        })
    s["mails"] = mails
    s["last_gift_date"] = time.strftime("%Y%m%d")
    store_save(s)
    LOG.info("  mailbox: seeded %d OFFLINE GIFT mail(s)", len(mails))
    return mails

def mailbox_ensure_daily_mail(s: dict) -> list:
    today = time.strftime("%Y%m%d")
    mails = s.get("mails") or []
    if s.get("last_gift_date") != today:
        s["last_gift_date"] = today
        for i, (what, val) in enumerate(MAILBOX_GIFTS, 1):
            mails.append({"sn": today + str(i), "what": what,
                          "what_value": str(int(val))})
        s["mails"] = mails
        store_save(s)
        LOG.info("  mailbox: posted %d daily gift mail(s)", len(MAILBOX_GIFTS))
    return mails

# ---------- capture helpers ----------

def capture_path(rel_path: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.\-]", "_", rel_path)
    if len(safe) > 120:
        safe = safe[:120]
    return CAP_DIR / (safe + ".json")

def save_capture(rel_path, method, status, resp_headers, body_text):
    obj = {
        "method": method,
        "path": rel_path,
        "status": status,
        "headers": {k:v for k,v in resp_headers.items()
                    if k.lower() in {"content-type","location"}},
        "body": body_text,
        "ts": time.time()
    }
    p = capture_path(rel_path)
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    LOG.info("CAPTURED %s -> %s (%d bytes)", rel_path, p.name, len(body_text))

def load_capture(rel_path) -> dict | None:
    p = capture_path(rel_path)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

# ---------- static content-type ----------

def guess_ct(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".js":"application/javascript",".css":"text/css",
        ".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",
        ".gif":"image/gif",".svg":"image/svg+xml",".ico":"image/x-icon",
        ".webp":"image/webp",".bmp":"image/bmp",
        ".woff":"font/woff",".woff2":"font/woff2",".ttf":"font/ttf",
        ".otf":"font/otf",".eot":"application/vnd.ms-fontobject",
        ".mp3":"audio/mpeg",".wav":"audio/wav",".ogg":"audio/ogg",
        ".m4a":"audio/mp4",
        ".fnt":"text/plain",".xml":"application/xml",
        ".plist":"application/xml",".atlas":"text/plain",
        ".html":"text/html",".json":"application/json",
    }.get(ext, "application/octet-stream")

def cache_hdr(path: str) -> str:
    """Game art/audio never changes; let the browser keep it a day. Code we
    may still patch (js/css/html) always revalidates so fixes show instantly."""
    ext = os.path.splitext(path)[1].lower()
    if ext in {".js", ".css", ".html", ".htm", ".php", ".json", ".xml", ".plist", ".atlas"}:
        return "no-cache"
    return "max-age=86400, public"

# ---------- proxy ----------

def proxy_forward(method, rel_path, body_bytes, headers_dict) -> tuple[int, dict, bytes]:
    url = LIVE_HOST + rel_path
    req = Request(url, data=body_bytes if method in ("POST","PUT") else None, method=method)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Referer", LIVE_HOST + "/")
    for k,v in headers_dict.items():
        kl = k.lower()
        if kl in {"content-type","accept","accept-encoding"}:
            req.add_header(k, v)
    try:
        with urlopen(req, timeout=8) as resp:
            data = resp.read()
            hdrs = dict(resp.headers)
            status = resp.status
    except HTTPError as e:
        data = e.read()
        hdrs = dict(e.headers)
        status = e.code
    except Exception:
        traceback.print_exc()
        return 502, {}, b"proxy error"
    return status, hdrs, data

def rewrite_body(text: str) -> str:
    text = text.replace("https://game.busidol.com", base_url())
    text = text.replace("http://game.busidol.com", base_url())
    return text

def admin_page() -> str:
    """Read-only dashboard: one card per account with resources, characters
    and recent mail, taken straight from the SQLite saves/accounts tables."""
    def esc(v):
        return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    chars = []
    if DB_CONN is None:
        return "<h1>Admin</h1><p>Ban dang chay khong co --db. Khoi dong voi --db busidol.db de xem account.</p>"
    for (aid,) in DB_CONN.execute("SELECT id FROM accounts ORDER BY id"):
        user, gold, ruby, level = "?", "?", "?", "?"
        starinfo, mails = [], []
        pw = DB_CONN.execute("SELECT pw_hash FROM accounts WHERE id=?", (aid,)).fetchone()
        row = DB_CONN.execute("SELECT payload FROM saves WHERE id=?", (aid,)).fetchone()
        has_save = False
        if row:
            has_save = True
            try:
                d = json.loads(row[0])
                d1 = d.get("DATA1", "").split(",")
                if len(d1) > 4:
                    user, gold, ruby = d1[0], d1[1], d1[2]
                    try: level = d1[3]
                    except Exception: pass
                elif d.get("USER_NAME"):
                    user = d.get("USER_NAME")
                starinfo = [x for x in str(d.get("DATA2", "")).split(",") if x]
                mails = d.get("mails") or []
            except Exception:
                pass
        chars.append({
            "aid": aid, "has_pw": bool(pw and pw[0]), "has_save": has_save,
            "user": user, "gold": gold, "ruby": ruby, "level": level,
            "chars": starinfo, "mails": mails,
        })
    parts = [
        "<!DOCTYPE html><html lang=vi><head><meta charset=utf-8>",
        "<title>ELDORADO - Quan ly account</title>",
        "<style>",
        "body{font-family:'Segoe UI',sans-serif;background:#0e1626;color:#dfe7f5;margin:24px}",
        "h1{color:#ffd75e}h2{color:#8fb8ff;margin:8px 0}",
        "table{border-collapse:collapse;width:100%;background:#16233c;border-radius:8px;overflow:hidden;margin:10px 0}",
        "th,td{padding:6px 10px;border:1px solid #243;text-align:left;font-size:13px}",
        "th{background:#1c2c4d;color:#ffd75e}",
        "td.mono{font-family:Consolas,monospace;font-size:12px}",
        ".card{background:#141f36;border:1px solid #2a3a5c;border-radius:10px;padding:14px;margin:14px 0}",
        ".chip{display:inline-block;background:#1e3057;border-radius:12px;padding:2px 9px;margin:2px;font-size:12px}",
        ".no{border-color:#4a3a2a;color:#ffb08a}</style></head><body>",
        "<h1>ELDORADO - Quan ly account</h1>",
        f"<p style=color:#7ea no>{len(chars)} account(s)</p>",
        "<table><tr><th>Account</th><th>Login reader</th><th>Da vao game?</th>",
        "<th>Ten nhan vat</th><th>Vang</th><th>Ruby</th><th>Cap</th><th>Nhan vat so huu</th><th>Mail</th></tr>",
    ]
    for c in chars:
        cparts = "".join(f'<span class="chip">{esc(cp)}</span>' for cp in c["chars"][:12])
        # mail: show title + items count in one line each
        mail_lines = []
        for m in c["mails"]:
            try:
                mt = (m.get("title") or m.get("name") or str(m)[:40] if isinstance(m, dict) else str(m)[:40])
                items = m.get("etcs") if isinstance(m, dict) else None
                mail_lines.append(esc(f"{mt}  [{items}]") if items else esc(mt or str(m)[:40]))
            except Exception:
                mail_lines.append(esc(str(m)[:40]))
        mail_html = "<br>".join(f'<span class="chip">{x[:60]}</span>' for x in mail_lines[:5]) if mail_lines else "—"
        parts.append(
            f'<tr class="{"no" if not c["has_save"] else ""}">'
            f"<td><b>{esc(c['aid'])}</b></td>"
            f'<td>{"co" if c["has_pw"] else "khong"}</td>'
            f'<td>{"co" if c["has_save"] else "chua"}</td>'
            f"<td>{esc(c['user'])}</td>"
            f"<td>{esc(c['gold'])}</td><td>{esc(c['ruby'])}</td><td>{esc(c['level'])}</td>"
            f"<td>{cparts}</td><td>{mail_html}</td></tr>"
        )
    parts.append("</table></body></html>")
    return "\n".join(parts)

def fetch_and_cache(rel_path: str) -> bytes | None:
    """Download a missing static asset from the live host and cache it on disk.

    The game's images live at several on-the-fly bases (the deploy rotates
    subdirectories like source_20240722/). Try each candidate, cache the first
    hit under the path the game actually requests, so a missing asset heals
    itself (threaded server -> never blocks the rest of the page anymore).
    """
    candidates = [rel_path]
    # the deploy rotates subdirectories (source_YYYYMMDD/): each asset family
    # (image/, sound/, font/) may live under that mirror base.
    for family in ("/image/", "/sound/", "/font/"):
        if family in rel_path:
            candidates.append(rel_path.replace(family, "/source_20240722" + family, 1))
    if rel_path.startswith("/ELDORADO_WEB/"):
        candidates.append("/" + rel_path[len("/ELDORADO_WEB/"):])
    seen = set()
    for cand in candidates:
        if cand in seen or cand.lower().startswith("//"):
            continue
        seen.add(cand)
        status, hdrs, data = proxy_forward("GET", cand, b"", {})
        if status != 200 or not data:
            LOG.info("  -> asset fetch %s status=%s", cand, status)
            continue
        dest = BASE_DIR / rel_path.lstrip("/")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            LOG.info("  -> cached %d bytes to %s (from %s)", len(data), rel_path, cand)
        except Exception:
            LOG.info("  -> fetched %d bytes (cache write failed) %s", len(data), rel_path)
        return data
    return None

# ---------- offline stubs ----------

LOGIN_HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BUSIDOL login</title><style>
 body{font-family:system-ui,sans-serif;background:#0f1626;color:#e8edf7;text-align:center;padding:8vh 16px}
 form{display:inline-block;background:#1a2540;padding:28px 34px;border-radius:16px;box-shadow:0 10px 30px #0006}
 h1{font-size:22px;margin:0 0 18px} label{display:block;text-align:left;color:#9fb0d0;font-size:12px;margin:12px 0 4px}
 input{width:260px;padding:10px;border-radius:8px;border:1px solid #33406b;background:#0f1626;color:#fff;font-size:15px}
 button{margin-top:20px;width:100%;padding:11px;border:0;border-radius:8px;background:#3b82f6;color:#fff;font-size:15px;cursor:pointer}
 button:hover{background:#2f6fd0} #msg{margin-top:14px;font-size:13px;color:#ff8a8a;min-height:16px}
</style></head><body>
<form id="f"><h1>BUSIDOL &#183; LOGIN</h1>
 <label for="acc">Account</label><input id="acc" autocomplete="username" autofocus>
 <label for="pw">Password</label><input id="pw" type="password" autocomplete="current-password">
 <button type="submit">Play</button>
 <div id="msg"></div>
</form>
<script>
document.getElementById("f").addEventListener("submit",async function(e){
 e.preventDefault();
 var acc=document.getElementById("acc").value.trim();
 var pw=document.getElementById("pw").value;
 var msg=document.getElementById("msg");msg.textContent="";
 if(!acc||!pw){msg.textContent="Enter account and password.";return}
 var fd=new URLSearchParams();fd.set("acc",acc);fd.set("pw",pw);
 var r=await fetch("/ELDORADO_WEB/login_auth.php",{method:"POST",body:fd.toString()});
 var j=await r.json();
 if(j&&j.ok){localStorage.setItem("eldorado_fb_temp_id",j.uid);location.href="/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0";return}
 msg.textContent=(j&&j.err)||"Login failed.";
});
</script></body></html>"""

# Hard mode (ELDORADO_HARD): the client keeps CUR_HARD_STAGE_NUM and only ever
# calls STORAGE.pass_stage_hard(n), which increments by one when n equals the
# current stage. MAX_STAGE_NUM_HARD is 200 in the client bundle, so stage 201
# means "all 200 stages unlocked". Seeding 201 on a fresh save therefore opened
# the whole map at once; the correct start is stage 1 and the map is opened one
# stage at a time as the player clears it.
ELDORADO_HARD_FIRST_STAGE = 1
ELDORADO_HARD_ALL_OPEN = 201  # 200 hard stages + 1; >= this unlocks everything
ELDORADO_HARD_JEWEL_DEFAULT = "0,0,0,0,0,0,0,0,0,0"
ELDORADO_LANG_VIETNAM = 3  # LANG.VIETNAM


def _eldorado_hard_parse(raw) -> tuple[int, str]:
    """Split the "stage||jewels" string into (stage, jewels). Returns 0 when the
    value is missing or unparseable so callers can fall back to a safe default."""
    text = str(raw or "").strip()
    if "||" not in text:
        return 0, ""
    head, _, jewels = text.partition("||")
    try:
        stage = int(head.strip())
    except ValueError:
        return 0, ""
    return max(0, stage), jewels.strip() or ELDORADO_HARD_JEWEL_DEFAULT


def _eldorado_hard_clamp_progress(saved_stage: int) -> int:
    """Force a stored stage into the valid 1..201 range so a corrupt or
    hand-edited save cannot be used to skip ahead."""
    return max(ELDORADO_HARD_FIRST_STAGE, min(ELDORADO_HARD_ALL_OPEN, saved_stage))


def _eldorado_lang_of(data1_fields: list[str]) -> int:
    """LANG code stored at DATA1[3] (1=KO 2=EN 3=VN 4=ES 5=RU 6=PT).

    The client derives its language with LANG.get_code_by_data1(t[3], ENGLISH),
    so index 3 is the single source of truth. Offlines default to Vietnamese
    (3) because index__mobile.html forces it on first load; anything missing or
    out of range falls back to the same value."""
    try:
        code = int(str(data1_fields[3]))
    except (IndexError, ValueError):
        return ELDORADO_LANG_VIETNAM
    return code if 1 <= code <= 6 else ELDORADO_LANG_VIETNAM


def _eldorado_hard_apply_claim(saved_stage: int, claimed_stage: int) -> tuple[int, bool]:
    """Decide what a client-posted hard stage is allowed to do. Returns
    (stage_to_store, accepted).

    The client posts CUR_HARD_STAGE_NUM after STORAGE.pass_stage_hard, so a
    legitimate request is either the same stage (replaying a stage already
    cleared, no new progress) or exactly one more (a real clear). A bigger jump
    is unreachable by playing and is refused outright; the caller must then write
    nothing at all, otherwise a forged POST could still clobber the jewel list
    even with the stage held back.
    """
    current = _eldorado_hard_clamp_progress(saved_stage)
    claimed = _eldorado_hard_clamp_progress(claimed_stage)
    if claimed <= current:
        return current, True
    if claimed == current + 1:
        return claimed, True
    LOG.info("  hard mode rejected stage jump %s -> %s (keeping %s)",
             saved_stage, claimed_stage, current)
    return current, False


def offline_stub(rel_path, body_str: str) -> tuple[int, str]:
    """Return (status_code, response_text) for known PHP stubs."""
    lp = rel_path.lower()
    if "/garden/state.php" in lp:
        return _farm_endpoint("state", body_str)
    if "/garden/action.php" in lp:
        return _farm_endpoint("action", body_str)
    if "get_app_file.php" in lp:
        stub = (
            f"{base_url()}/ELDORADO_WEB/javascript_min/aes.js?13"
            f"|{base_url()}/ELDORADO_WEB/pwsmart.1.3.js?13"
            f"|{base_url()}/ELDORADO_WEB/GoogleAnalytics/google_analytics.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_leveling/define_glo_20241205.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_min/ovr_gold_x5.js?13"
            f"|{base_url()}/ELDORADO_WEB/custom_characters/custom_characters.generated.js?1"
            f"|{base_url()}/ELDORADO_WEB/custom_characters/custom_character_runtime.js?1"
            f"|{base_url()}/ELDORADO_WEB/runtime_patches/item_gacha_bp_runtime.js?1"
        )
        return 200, stub
    if "check_black_list_db.php" in lp:
        if DB_FILE:
            uid = _uid()
            if REQUIRE_LOGIN and (not uid or not account_exists(uid)):
                return 200, json.dumps({
                    "result": "BLACK_LIST",
                    "message": "Login required - open /login_login_page.php "
                               "and sign in first.",
                })
            return 200, json.dumps({"result": "NONE", "STATE": "OK",
                                    "UNIQ_ID": uid or UNIQ_ID})
        return 200, json.dumps({"result": "NONE", "STATE": "OK",
                                "UNIQ_ID": UNIQ_ID})
    if "login_page.php" in lp or "login_page" in lp:
        # Login page served at /login_login_page.php (friends) and at the
        # client's own fallback path. Sets localStorage eldorado_fb_temp_id
        # (= the account id the game boots as) then jumps into the game.
        return 200, LOGIN_HTML
    if "login_auth.php" in lp:
        # POST acc=NAME&pw=PASS -> validate against the accounts table.
        body = parse_body(body_str)
        acc = str(body.get("acc", ""))
        pw = str(body.get("pw", ""))
        if DB_FILE and REQUIRE_LOGIN and acc and pw and verify_account(acc, pw):
            _tl.set_cookie = issue_auth_session(acc)
            return 200, json.dumps({"ok": 1, "uid": acc})
        return 200, json.dumps({"ok": 0, "err": "wrong account or password"})
    today_ymd = time.strftime("%Y%m%d")
    now_epoch = str(int(time.time() * 1000))
    if "get_today_pv.php" in lp:
        return 200, "0"
    if "get_server_time.php" in lp:
        return 200, today_ymd
    if "get_server_timestamp.php" in lp:
        return 200, now_epoch
    if "day_counter.php" in lp:
        return 200, "0"
    if "is_connecting.php" in lp:
        return 200, "allow"
    if "get_gongji.php" in lp or "get_gongji_all.php" in lp:
        return 200, "[]"
    if "get_my_first_login_date.php" in lp or "login_date.php" in lp:
        return 200, time.strftime("%Y-%m-%d %H:%M:%S")
    if "get_realtime_notice.php" in lp:
        return 200, "{}"
    if "bonuspoint/get_bonus_point.php" in lp:
        # Main-menu bp refresh: posts at S_MAINMENU and OVERWRITES
        # USER.bonus_point from RAW response text (parse_server_bp_data(n)).
        # Returning "{}" made parseInt("{}") = NaN on the top-bar BP.
        # Must be a bare number (or "none") so the saved bp is reapplied.
        return 200, str(load_save().get("bp", "none"))
    if "bonuspoint/add_bonus_point.php" in lp:
        # Client earns bonus points (purchase bonus / event rewards) via
        # ServerConnection.add_bonus_point(ADD_POINT=+n) and deducts them
        # locally. Persist the gain so a reload keeps it; otherwise the
        # bonus vanishes and bp snaps back to the old saved value.
        try:
            body = parse_body(body_str)
            add = int(float(str(body.get("ADD_POINT", "0") or 0)))
            if add:
                with SAVE_LOCK:
                    s = load_save()
                    try:
                        cur = int(float(str(s.get("bp", 0) or 0)))
                    except Exception:
                        cur = 0
                    s["bp"] = str(max(0, cur + add))
                    store_save(s)
                LOG.info("  add_bonus_point %d -> saved bp=%s", add, s["bp"])
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "bonuspoint/reset_bonus_point.php" in lp:
        # success_fn only checks for "mysql_error" in the body.
        return 200, "ok"
    if "autoplay/get_autoplay.php" in lp.lower() or "autoplay/set_autoplay.php" in lp.lower() or "autoplay/update_autoplay_onoff.php" in lp.lower():
        # Auto-battle pass: paid feature, repriced to 1000 BP per package
        # (client default AUTO_BP=10 is wrong; price here server-side).
        try:
            body = parse_body(body_str)
            if "update_autoplay_onoff" in lp:
                with SAVE_LOCK:
                    s = load_save()
                    auto = s.setdefault("autoplay", {})
                    try:
                        auto["on_off"] = int(float(str(body.get("ON_OFF", 1) or 1)))
                    except (TypeError, ValueError):
                        auto["on_off"] = 1
                    store_save(s)
                return 200, "ok"
            if "set_autoplay" in lp.lower():
                day = int(float(str(body.get("AUTO_DAY", 1) or 1)) or 1)
                need = 1000
                with SAVE_LOCK:
                    s = load_save()
                    try:
                        cur_bp = int(float(str(s.get("bp", 0) or 0)))
                    except (TypeError, ValueError):
                        cur_bp = 0
                    if cur_bp < need:
                        return 200, json.dumps({"STATE": "NONE"})
                    s["bp"] = str(cur_bp - need)
                    auto = s.setdefault("autoplay", {})
                    auto["paid"] = 1
                    auto["end"] = int(time.time()) + day * 86400
                    auto["on_off"] = 1
                    store_save(s)
                LOG.info("  autoplay buy: -%d bp, end=%s", need, auto.get("end"))
                return 200, json.dumps({"STATE": "SUCCESS"})
            with SAVE_LOCK:
                s = load_save()
                auto = s.get("autoplay") or {}
            if auto.get("paid") and int(auto.get("end") or 0) > int(time.time()):
                return 200, json.dumps({
                    "END_DATE": str(auto.get("end", "0")),
                    "ON_OFF": int(auto.get("on_off", 1)),
                    "STATE": "SUCCESS"})
            return 200, json.dumps({"STATE": "NONE"})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "autoplay/insert_autoplay_acc.php" in lp.lower():
        # Autoplay run summary; nothing to persist, acknowledge only.
        return 200, "ok"
    if "cnm_exist_host_in_server.php" in lp:
        # USER:"NEW" -> game builds its own full user data locally
        # (STORAGE.init_firstUser + make_data1/2/3) then POSTs to
        # cnm_insert_new_user_to_server.php (fallback stub "{}").
        # limited_package_time / event_arr are read unguarded in the
        # S_MAINMENU init -> must be present.
        base = {
            "STATE":"SUCCESS",
            "USER":"NEW",
            # PHP_CALL_REDUCATION=1 -> game parses these fields from this
            # response to set S_LOGO flags (quest presence gates all 6):
            #   parse_server_item_data("none")      -> S_LOGO.flag4_item=1
            #   parse_server_hard_mode_data("0||0") -> S_LOGO.flag5_hardmode=1
            # without them S_LOGO.flag_count never hits FLAG_COUNT_MAX
            # and the logo screen hangs forever.
            "quest": "empty",
            "scorewave": "0,0",
            "bp": "none",
            "user_paid": "false",
            "item": "none",
            "hard_mode": f"{ELDORADO_HARD_FIRST_STAGE}||{ELDORADO_HARD_JEWEL_DEFAULT}",
            # Tower Awakening flag (타워각성). The client only reads it when
            # glo.APP_FEATURE.TOWER_AWAKENING is on: USER.tower_awakening =
            # parseInt(t.tower_awakening) guards the re-awaken button. Default
            # "0" (hasOwnProperty gate) -> new users start un-awakened.
            "tower_awakening": "0",
            # main-menu uses these unguarded in the cnm_exist success_fn:
            #   S_ATTENDANCE_EVENT.folder_name=t.attendance_event_folder_name
            #     becomes "image/ui/<folder>/sevent_*.png" -> was "undefined"
            #   glo.package.parse_gacha_item_list(t.gacha_item_list)
            "attendance_event_folder_name": "41_attendance_event",
            "gacha_item_list": [],
            "is_subscribe": "no",
            "is_growth": "no",
            "sub_next_date": "20300101",
            "sub_repurchase_date": "20300101",
            "sub_mul": "1",
            "growth_stage_mul": "1",
            "growth_itemup_cost": "1",
            "growth_upgrade_cost": "1",
            "growth_max_level": "0",
            "growth_min_level": "0",
            # cloud-garden fields the cnm_exist success_fn parses UNGUARDED:
            #   USER.cloud_piece=parseInt(t.cloud_piece)  <- missing -> NaN on
            #   the main-menu top-bar; the evo_8/evo_9 are stage-entry costs.
            # celestial_piece_evo_9 is the 9-star evolution essence cost; the
            # client drops CEL_PIECE from the edit_cloud_garden POST entirely
            # (ServerConnection.edit_cloud_garden only forwards MODE/ADD_PIECE/
            # ETC), so the server must apply the essence deduction by MODE.
            "cloud_piece": "0",
            "cel_essn": "0",
            "ENTER_LIMIT_STAGE": "1",
            "cloud_piece_evo_8": "500",
            "cloud_piece_evo_9": "500",
            "celestial_piece_evo_9": str(CELESTIAL_PIECE_EVO_9),
            "DRAGON_NEED_CLOUD": str(FOUR_GODS_PERSUASION_COST),
            "goldbar": "0",
            # Boss stages 245-300: client gates entry on
            # count_arr[stage].count < 5 ("map13" daily-admissions rule).
            # Offline build has no budget tracking => serve 0 used, 5 max so
            # the gate stays open; the "stage" update always returns 0 left.
            "stage_245": {"count": 0, "max": 5}, "stage_250": {"count": 0, "max": 5},
            "stage_255": {"count": 0, "max": 5}, "stage_260": {"count": 0, "max": 5},
            "stage_265": {"count": 0, "max": 5}, "stage_270": {"count": 0, "max": 5},
            "stage_275": {"count": 0, "max": 5}, "stage_280": {"count": 0, "max": 5},
            "stage_285": {"count": 0, "max": 5}, "stage_290": {"count": 0, "max": 5},
            "stage_295": {"count": 0, "max": 5}, "stage_300": {"count": 0, "max": 5},
            "timestamp": NOW_EPOCH,
            "today": TODAY,
            "limited_package_time": "1700000000||1750000000",
            "event_arr": [],
            "G_GACHA_PROBABILITY": {
                # default rates bundled in the engine; client compares its copy
                # against this server value (put_black_list if they differ).
                "gacha1": [0, 4, 12, 36, 24, 24],
                "gacha2": [0, 12, 22, 36, 16, 14],
                "gacha3": [0, 4, 20, 48, 28],
                "gacha4": [0, 4, 20, 48, 28],
                "gacha5": [0, 4, 36, 200, 760],
            },
            "char_select_arr":[],
            "char_cnt":0,"special_a_cnt":0,"special_b_cnt":0,"cloud_piece_cnt":0,
            "echo_a_cnt":0,"echo_b_cnt":0,"random_item_cnt":0,"wow_cnt":0,
            "random_box_cnt":0,"monthly_package_list":[],
            "hero_list": _guild_shop_hero_list(),
            "package_list":[],"shop_new_enable":0,"PASS_TICKET":0,"PASS_TICKET_DISCOUNT":0
        }
        save = load_save()
        if save.get("DATA1"):
            # existing user: hand back the saved DATA1/2/3 so the success_fn
            # runs STORAGE.load_n_parse_cnm(...) and restores real progress,
            # instead of treating every boot as a brand-new account.
            base["USER"] = save.get("USER_NAME") or "EXIST"
            base["USER_NAME"] = base["USER"]
            base["VERSION"] = save.get("VERSION") or ""
            # bonus point (BP, the gacha currency) lives on the server, NOT in
            # DATA1: the engine calls STORAGE.parse_server_bp_data(t.bp).
            # Served from the save (edited with resedit.py) so it sticks.
            base["bp"] = str(save.get("bp", "none"))
            base["cloud_piece"] = str(save.get("cloud_piece", "0"))
            base["cel_essn"] = str(save.get("celestial_essence", "0"))
            for k in ("DATA1", "DATA2", "DATA3", "ETC"):
                if k in save:
                    base[k] = save[k]
            # Progress the client pushes through SEPARATE endpoints (quest via
            # cnm_update_quest_to_server, item via item/update_item_to_server)
            # is handed back here so boot no longer reverts them to
            # "empty"/"none"/"0" (which wiped quests via quest_init() and
            # emptied the item list every time the game started).
            for k in ("quest", "scorewave", "hard_mode"):
                if str(save.get(k, "") or "").strip():
                    base[k] = save[k]
            base["tower_awakening"] = str(save.get("tower_awakening", "0"))
            saved_item = str(save.get("item", "") or "").strip()
            if saved_item:
                s_mile = [str(m) for m in (save.get("item_mileage") or [])]
                base["item"] = "||".join([saved_item] + s_mile) if s_mile else saved_item
        base["today"] = today_ymd
        base["timestamp"] = now_epoch
        att_date_saved = save.get("attendance_reward_date") or ""
        if not att_date_saved and save.get("DATA1"):
            d1 = save["DATA1"].split(",")
            if len(d1) > 11:
                att_date_saved = d1[11]
        chul_num_saved = 0
        if save.get("DATA1"):
            d1 = save["DATA1"].split(",")
            if len(d1) > 12:
                try:
                    chul_num_saved = int(float(d1[12] or 0))
                except Exception:
                    pass
        base["ATT_CHUL_DATE"] = str(att_date_saved or "")
        base["ATT_CHUL_NUM"] = str(chul_num_saved or 0)
        return 200, json.dumps(base)
    if "cnm_insert_new_user_to_server.php" in lp:
        # FIRST-run save: the client POSTs the freshly built user
        # (STORAGE.init_firstUser) here. Persist it so later boots can
        # restore it from cnm_exist instead of being born again.
        try:
            body = parse_body(body_str)
            if body.get("DATA1"):
                store_save({
                    "USER_NAME": body.get("USER_NAME", ""),
                    "VERSION": body.get("VERSION", ""),
                    "VER_DATE": body.get("VER_DATE", ""),
                    "DATA1": body.get("DATA1"),
                    "DATA2": body.get("DATA2", ""),
                    "DATA3": body.get("DATA3", ""),
                    "ETC": body.get("ETC", ""),
                    "bp": "0",
                })
                LOG.info("  saved new user (%d bytes DATA1)", len(body.get("DATA1")))
        except Exception:
            traceback.print_exc()
        return 200, "{}"
    if "install_count.php" in lp or "day_counter.php" in lp:
        return 200, "0"
    if "counter/daily_run_count.php" in lp or "get_cur_run_count.php" in lp:
        return 200, "1"
    if "cnm_update_user_to_server_cry.php" in lp:
        # The main progress-sync endpoint: called after stage clears,
        # purchases, quest rewards, etc. DATA1/2/3 hold the whole account
        # (the same strings load_n_parse_cnm consumes on the next login).
        # Last-write-wins persistence = offline save file.
        try:
            body = parse_body(body_str)
            if body.get("DATA1"):
                with SAVE_LOCK:
                    s = load_save()
                    mode = str(body.get("MODE", "") or "").lower()
                    s.update({
                        "USER_NAME": body.get("USER_NAME", s.get("USER_NAME", "")),
                        "VERSION": body.get("VERSION", s.get("VERSION", "")),
                        "VER_DATE": body.get("VER_DATE", s.get("VER_DATE", "")),
                        "DATA1": body.get("DATA1"),
                        "DATA2": body.get("DATA2", s.get("DATA2", "")),
                        "DATA3": body.get("DATA3", s.get("DATA3", "")),
                        "ETC": body.get("ETC", s.get("ETC", "")),
                    })
                    # Tower Awakening (타워각성) POST: MODE="tower_awakening".
                    # The flag lives on the server, NOT in DATA1/2/3 - without it
                    # the next boot gets USER.tower_awakening=0 and lets the player
                    # re-awaken the tower. Persist it so cnm_exist can hand it back.
                    if mode == "tower_awakening":
                        s["tower_awakening"] = "1"
                    store_save(s)
                    if mode == "att":
                        given, cycle_day, mail_sn = issue_attendance_reward(
                            s, body.get("DATA1", ""))
                        store_save(s)
                LOG.info("  saved progress stage=%s DATA1=%d bytes",
                         body.get("STAGE", "?"), len(body.get("DATA1")))
                if mode == "att":
                    LOG.info("  attendance: given=%s day=%s mail=%s",
                             given, cycle_day, mail_sn or "-")
                    return 200, json.dumps({
                        "STATE": "SUCCESS",
                        "ATT_GIVEN": bool(given),
                        "ATT_DAY": cycle_day,
                        "ATT_CHUL_NUM": body.get("DATA1", "").split(",")[12],
                    })
                if mode == "stage":
                    # Boss stages 245-300 gate entry on the daily admission
                    # count (client: STAGE_COUNT < 5 then count_arr[...].count
                    # = parseInt(STAGE_COUNT)). Serve 0 so the gate always
                    # opens — unlimited plays, no day tracking.
                    return 200, json.dumps({
                        "STATE": "SUCCESS",
                        "STAGE_COUNT": "0",
                    })
        except Exception:
            traceback.print_exc()
        return 200, "{}"
    if "cnm_update_quest_to_server.php" in lp:
        # Quest progress lives server-side (the client pushes it via this
        # endpoint whenever it changes; on WEB the localStorage save does NOT
        # carry quests). Persist the posted DATA so a later boot can hand it
        # back through cnm_exist 'quest' instead of parse_server_quest_data
        # seeing "empty" and running quest_init() (which wipes the quests).
        # Return "QUEST_INIT||<data>" so the success_fn re-parses it: when the
        # client post was a default all-zero wipe, echoing the stored value
        # self-heals the quest line in the same call.
        try:
            body = parse_body(body_str)
            q = str(body.get("DATA", "") or "")
            with SAVE_LOCK:
                s = load_save()
                saved_q = str(s.get("quest", "") or "").strip()
                all_zero = all(t in ("", "0") for t in q.replace(":", ",").split(","))
                if q and not (all_zero and saved_q):
                    s["quest"] = q
                    s["quest_etc"] = str(body.get("ETC", "") or "")
                    store_save(s)
                    LOG.info("  quest saved (%d bytes, zero=%s)", len(q), all_zero)
                elif q and all_zero and saved_q:
                    LOG.info("  quest wipe-guard: kept %d bytes (client posted zeros)",
                             len(saved_q))
            return 200, "QUEST_INIT||" + (s.get("quest") or saved_q or "empty")
        except Exception:
            traceback.print_exc()
        return 200, "QUEST_OK"
    if "hardmode/get_hardmode_data.php" in lp:

        # Boot/first stage-clear: parse_server_hard_mode_data(raw) sets
        # CUR_HARD_STAGE_NUM=t[0] and HARD_MODE_JEWEL=t[1]. Without a handler
        # the fallback "{}" -> Number(NaN), so the hard map never opens past
        # the very first stage. Seed stage 1 when absent; the client only
        # advances one stage per clear via STORAGE.pass_stage_hard, so the
        # map opens progressively instead of all 200 stages at once.
        hard = str(load_save().get("hard_mode", "") or "").strip()
        stage, _jewels = _eldorado_hard_parse(hard)
        if stage <= 0:
            hard = f"{ELDORADO_HARD_FIRST_STAGE}||{ELDORADO_HARD_JEWEL_DEFAULT}"
            mutate_save(lambda s: s.__setitem__("hard_mode", hard))
            LOG.info("  hard mode seeded stage=%s", ELDORADO_HARD_FIRST_STAGE)
        return 200, hard
    if "hardmode/update_hardmode_to_server.php" in lp:
        # Persist hard stage + jewel progress (POST STAGE_DATA/JEWEL_DATA) so
        # the next boot restores CUR_HARD_STAGE_NUM instead of resetting it.
        try:
            body = parse_body(body_str)
            st = str(body.get("STAGE_DATA", "") or "").strip()
            jw = str(body.get("JEWEL_DATA", "") or "").strip()
            if st:
                try:
                    claimed = int(st)
                except ValueError:
                    claimed = None
                if claimed is not None:
                    saved_stage, saved_jewels = _eldorado_hard_parse(
                        load_save().get("hard_mode", ""))
                    stage, accepted = _eldorado_hard_apply_claim(saved_stage, claimed)
                    if accepted:
                        jewels = jw or saved_jewels or ELDORADO_HARD_JEWEL_DEFAULT
                        def _save_hard(s):
                            s["hard_mode"] = f"{stage}||{jewels}"
                        mutate_save(_save_hard)
                        LOG.info("  hard mode saved stage=%s", stage)
        except Exception:
            traceback.print_exc()

        return 200, "ok"
    if "item/update_item_to_server.php" in lp:
        # Items ONLY live server-side (make_item/make_item_mileage are pushed
        # here on every item change; neither DATA1/2/3 nor localStorage holds
        # them). Persist them, then serve them back through cnm_exist 'item'
        # (same "ITEMS||MILEAGE" shape parse_server_item_data consumes).
        try:
            body = parse_body(body_str)
            if (str(body.get("MODE", "") or "") == "ITEM_GACHA"
                    and str(body.get("TYPE_NUM", "") or "") in {"26", "27"}):
                return _item_gacha_bp_purchase(body)
            with SAVE_LOCK:
                s = load_save()
                d1 = (s.get("DATA1", "") or "").split(",")
                while len(d1) < 4:
                    d1.append("0")
                try:
                    cur_ruby = int(float(d1[2] or 0))
                except (TypeError, ValueError):
                    cur_ruby = 0
                try:
                    rub = int(float(body.get("RUBY") or 0))
                except (TypeError, ValueError):
                    rub = 0
                if rub < 0 and cur_ruby + rub < 0:
                    return 200, json.dumps({"STATUS": "ERROR", "ERROR_CODE": "NOT_ENOUGH_RUBY"})
                mode = str(body.get("MODE", "") or "")
                # TYPE_NUM 26/27 never reaches here: _item_gacha_bp_purchase
                # owns the BP price, the roll and the reward payout. Keeping
                # this branch free of a second price source avoids two places
                # disagreeing on what a draw costs.
                item = str(body.get("ITEM", "") or "").strip()
                # ITEM_GACHA overflow: when the inventory is full the rolled
                # items never enter client STORAGE (add_item silently fails),
                # so they drop out of ITEM entirely. Mail the copies the client
                # clearly did not keep; the native mailbox claim readds them the
                # moment slots free up (client refuses the claim while full).
                etc = str(body.get("ETC", "") or "")
                if mode == "ITEM_GACHA" and "|" in etc:
                    etc_items = [x for x in etc.split("|", 1)[1].split(",") if ":" in x]
                    if etc_items:
                        old_items = [x for x in str(s.get("item", "") or "").split(",") if x]
                        post_items = [x for x in item.split(",") if x]
                        mails = s.get("mails") or []
                        base = len(mails)
                        for x in etc_items:
                            if post_items.count(x) <= old_items.count(x):
                                mails.append({"sn": next_mail_sn(mails),
                                              "why": "아이템 뽑기",
                                              "what": "ITEM",
                                              "what_value": x.split(":", 1)[0],
                                              "start_date": time.strftime("%Y-%m-%d"),
                                              "end_date": "20991231"})
                        if len(mails) != base:
                            s["mails"] = mails
                            store_save(s)
                            LOG.info("  item gacha overflow -> %d mail(s)",
                                     len(mails) - base)
                if item:
                    s["item"] = item
                    s["item_mileage"] = [str(body.get("MILEAGE_" + k, "") or "")
                                         for k in ("FE", "ED", "DC", "CB", "BA", "AS")]
                    store_save(s)
            LOG.info("  item saved (%d bytes)", len(item))
            try:
                cur_gold = int(float(d1[1] or 0))
            except (TypeError, ValueError):
                cur_gold = 0
            try:
                cur_bp = int(float(s.get("bp") or 0))
            except (TypeError, ValueError):
                cur_bp = 0
            try:
                cur_cloud = int(float(s.get("cloud_piece") or 0))
            except (TypeError, ValueError):
                cur_cloud = 0
            # The item-gacha draw passes RUBY (ruby won only) plus optional
            # GOLD / BP / CLOUD_PIECE wins; apply all to the save so
            # after_ruby/after_gold/bp (applied by the client) and the next
            # cnm_exist boot agree.
            for _pn in ("RUBY", "GOLD", "BP", "CLOUD_PIECE"):
                try:
                    _v = int(float(body.get(_pn) or 0))
                except (TypeError, ValueError):
                    _v = 0
                _dest = {"RUBY": cur_ruby, "GOLD": cur_gold,
                         "BP": cur_bp, "CLOUD_PIECE": cur_cloud}[_pn]
                if _v and _dest + _v >= 0:
                    if _pn == "RUBY":
                        cur_ruby = _dest + _v; d1[2] = str(cur_ruby)
                        s["DATA1"] = ",".join(d1)
                    elif _pn == "GOLD":
                        cur_gold = _dest + _v; d1[1] = str(cur_gold)
                        s["DATA1"] = ",".join(d1)
                    elif _pn == "BP":
                        cur_bp = _dest + _v; s["bp"] = str(cur_bp)
                    else:
                        cur_cloud = _dest + _v; s["cloud_piece"] = str(cur_cloud)
                    store_save(s)
            # Numeric fields for every item action callback (lock/socket/sell
            # read after_gold, gacha reads after_ruby + STATUS, upgrade reads
            # RESULT); RESULT=0 -> upgrade shows as fail, no free upgrades.
            return 200, json.dumps({
                "STATUS": "SUCCESS", "RESULT": 0, "RESULT_ITEM_NUM": 0,
                "ADD_OPTION": "", "ADD_OPTION_NUM": 0,
                "after_gold": str(cur_gold), "after_ruby": str(cur_ruby),
                "cloud_piece": str(cur_cloud), "bp": str(cur_bp),
            })
        except Exception:
            traceback.print_exc()
        return 200, "{}"
    if "get_ally_list.php" in lp:
        # Charbook query: returns "{ally_list}||{ally_reward}||{enemy_list}||{enemy_reward}"
        # Seed ally list from DATA2 if currently empty so player sees their current roster.
        s = load_save()
        ally_list = str(s.get("charbook_ally_list", "") or "").strip()
        if not ally_list and s.get("DATA2"):
            units = set()
            for part in str(s["DATA2"]).split(","):
                if part and ":" in part:
                    uid = part.split(":")[0].strip()
                    if uid and uid.isdigit():
                        units.add(uid)
            if units:
                ally_list = ",".join(sorted(units, key=int))
                mutate_save(lambda d: d.__setitem__("charbook_ally_list", ally_list))
        ally_rew = str(s.get("charbook_ally_reward", "") or "").strip()
        enemy_list = str(s.get("charbook_enemy_list", "") or "").strip()
        enemy_rew = str(s.get("charbook_enemy_reward", "") or "").strip()
        return 200, f"{ally_list}||{ally_rew}||{enemy_list}||{enemy_rew}"
    if "charbook/ally_list_update_or_insert.php" in lp or "ally_list_update_or_insert.php" in lp:
        try:
            body = parse_body(body_str)
            new_chars = str(body.get("ALLY_LIST", "") or "").strip()
            if new_chars:
                def _add_ally(d):
                    cur = [x for x in str(d.get("charbook_ally_list", "") or "").split(",") if x]
                    for c in new_chars.split(","):
                        c = c.strip()
                        if c and c not in cur:
                            cur.append(c)
                    d["charbook_ally_list"] = ",".join(cur)
                mutate_save(_add_ally)
                LOG.info("  charbook ally updated: %s", new_chars)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "charbook/ally_reward_update.php" in lp or "ally_reward_update.php" in lp:
        try:
            body = parse_body(body_str)
            rew = str(body.get("ALLY_REWARD", "") or "").strip()
            if rew:
                def _add_ally_rew(d):
                    cur = [x for x in str(d.get("charbook_ally_reward", "") or "").split(",") if x]
                    for r in rew.split(","):
                        r = r.strip()
                        if r and r not in cur:
                            cur.append(r)
                    d["charbook_ally_reward"] = ",".join(cur)
                mutate_save(_add_ally_rew)
                LOG.info("  charbook ally reward: %s", rew)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "charbook/enemy_list_update_or_insert.php" in lp or "enemy_list_update_or_insert.php" in lp:
        try:
            body = parse_body(body_str)
            new_enemies = str(body.get("ENEMY_LIST", "") or "").strip()
            if new_enemies:
                def _add_enemy(d):
                    cur = [x for x in str(d.get("charbook_enemy_list", "") or "").split(",") if x]
                    for e in new_enemies.split(","):
                        e = e.strip()
                        if e and e not in cur:
                            cur.append(e)
                    d["charbook_enemy_list"] = ",".join(cur)
                mutate_save(_add_enemy)
                LOG.info("  charbook enemy updated: %s", new_enemies)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "charbook/enemy_reward_update.php" in lp or "enemy_reward_update.php" in lp:
        try:
            body = parse_body(body_str)
            rew = str(body.get("ENEMY_REWARD", "") or "").strip()
            if rew:
                def _add_enemy_rew(d):
                    cur = [x for x in str(d.get("charbook_enemy_reward", "") or "").split(",") if x]
                    for r in rew.split(","):
                        r = r.strip()
                        if r and r not in cur:
                            cur.append(r)
                    d["charbook_enemy_reward"] = ",".join(cur)
                mutate_save(_add_enemy_rew)
                LOG.info("  charbook enemy reward: %s", rew)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "charbook/del_ally_list.php" in lp or "del_ally_list.php" in lp:
        def _del_cb(d):
            d["charbook_ally_list"] = ""
            d["charbook_ally_reward"] = ""
        mutate_save(_del_cb)
        return 200, "ok"
    if "charbook/ally_list_remove.php" in lp or "ally_list_remove.php" in lp:
        try:
            body = parse_body(body_str)
            rem = str(body.get("ALLY_LIST", "") or "").strip()
            if rem:
                rem_set = set(rem.split(","))
                def _rem_ally(d):
                    cur = [x for x in str(d.get("charbook_ally_list", "") or "").split(",") if x]
                    d["charbook_ally_list"] = ",".join([x for x in cur if x not in rem_set])
                mutate_save(_rem_ally)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "item/update_data2_item.php" in lp or "update_data2_item.php" in lp:
        # Team formation, character lock, character levelup, character evo, character sell, item changes
        try:
            body = parse_body(body_str)
            def _save_data2_item(d):
                if body.get("DATA2"):
                    d["DATA2"] = body["DATA2"]
                if body.get("ITEM") is not None and body.get("ITEM") != "":
                    d["item"] = body["ITEM"]
                if body.get("SELECTED_USER") and d.get("DATA1"):
                    d1 = d["DATA1"].split(",")
                    if len(d1) > 14:
                        d1[14] = body["SELECTED_USER"]
                        d["DATA1"] = ",".join(d1)
            mutate_save(_save_data2_item)
            LOG.info("  update_data2_item saved (mode=%s)", body.get("MODE", ""))
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "save_userinfo_after_pay.php" in lp:
        try:
            body = parse_body(body_str)
            def _save_pay(d):
                for k in ("DATA1", "DATA2", "DATA3", "ETC"):
                    if body.get(k):
                        d[k] = body[k]
            mutate_save(_save_pay)
            LOG.info("  save_UserInfo_after_PAY saved (ruby=%s, type=%s)",
                     body.get("RUBY", ""), body.get("TYPE", ""))
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "gacha/gacha_char.php" in lp:
        # success_fn: needs non-mysql_error; result is computed CLIENT-side
        # (get_gacha1/2/3 with GACHA_PROBABILITY). A success marker is enough.
        # BP here is the gacha delta: NEGATIVE for the bonus-point draws
        # (BONUS_POINT_5/6/7 spend -need_bp), POSITIVE for the BP_EVENT
        # reward. Either way the saved bp must follow the delta so it stays
        # correct across restarts. The old `spent > 0` guard never fired for
        # BP draws (delta is negative), so spends silently reset to the old
        # balance on every reload.
        try:
            body = parse_body(body_str)
            delta = 0
            raw_bp = body.get("BP")
            if raw_bp is not None and raw_bp != "":
                delta = int(float(str(raw_bp)))
            if delta:
                with SAVE_LOCK:
                    s = load_save()
                    try:
                        cur = int(float(str(s.get("bp", 0) or 0)))
                    except Exception:
                        cur = 0
                    s["bp"] = str(max(0, cur + delta))
                    store_save(s)
                LOG.info("  gacha bp delta %d -> saved bp=%s", delta, s["bp"])
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "SUCCESS"})
    if "del_reward_sn_all_n_save.php" in lp:
        # Mailbox CLAIM. The client sums the reward's ruby/gold/bp/cloud, then
        # POSTs ADD_RUBY/ADD_GOLD/ADD_POINT/ADD_CLOUD/ADD_CELESTIALBAR +
        # ALL_SN (claimed reward SNs). The REAL server credits the DB columns
        # here; we credit the save the same way so claims survive a reload
        # (the client's in-memory add + saved add represent the same amount).
        try:
            body = parse_body(body_str)
            with SAVE_LOCK:
                s = load_save()
                gold = int(float(body.get("ADD_GOLD", "0") or 0))
                ruby = int(float(body.get("ADD_RUBY", "0") or 0))
                bp = int(float(body.get("ADD_POINT", "0") or 0))
                cloud = int(float(body.get("ADD_CLOUD", "0") or 0))
                cel = int(float(body.get("ADD_CELESTIALBAR", "0") or 0))
                if gold or ruby:
                    d1 = (s.get("DATA1") or "").split(",")
                    while len(d1) < 21:
                        d1.append("0")
                    d1[1] = str(int(float(d1[1] or 0)) + gold)
                    d1[2] = str(int(float(d1[2] or 0)) + ruby)
                    s["DATA1"] = ",".join(d1)
                if bp:
                    s["bp"] = str(int(float(str(s.get("bp", 0) or 0))) + bp)
                if cloud:
                    s["cloud_piece"] = str(int(float(str(s.get("cloud_piece", 0) or 0))) + cloud)
                if cel:
                    s["celestial_essence"] = str(int(float(str(s.get("celestial_essence", 0) or 0))) + cel)
                all_sn = body.get("ALL_SN", "")
                if all_sn:
                    sns = {str(x) for x in all_sn.split(",") if x}
                    s["mails"] = [m for m in (s.get("mails") or []) if str(m.get("sn")) not in sns]
                store_save(s)
            LOG.info("  mailbox claim: +%dg +%dr +%dbp +%dcp (mails=%d",
                     gold, ruby, bp, cloud, len(s.get("mails") or []))
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "SUCCESS",
                                "ADD_ITEM": parse_body(body_str).get("ADD_ITEM", "")})
    if "del_reward_sn_i.php" in lp:
        # post-claim delete of ONE reward (check/del_reward_sn_i flow).
        # A single claim is credited by del_reward_sn_all_n_save too; just
        # drop the mail from the server list.
        try:
            body = parse_body(body_str)
            with SAVE_LOCK:
                s = load_save()
                sn = body.get("SN", "")
                if sn:
                    s["mails"] = [m for m in (s.get("mails") or []) if str(m.get("sn")) != str(sn)]
                    store_save(s)
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "check_reward_sn_i.php" in lp:
        # reward_i_run1: confirm the reward still exists; "ok" passes.
        return 200, "ok"
    if "put_mailbox_reward.php" in lp:
        # THE reward-mail CREATOR. The client fires put_reward_char(...) after
        # a first stage clear (CHAR), evolution event (RUBY), package buy
        # (GOLD) or daydungeon clear (ITEM), and the SUCCESS ack is what makes
        # it show utilNotice("...sent to your mailbox"). The mailbox only ever
        # lists mails that were stored, so a bare "ok" ack made every in-game
        # reward notification a ghost: the mail never reached get_reward2_-
        # mailbox. Store it with a unique SN (the live DB assigns the SN
        # server-side; the POST carries none).
        try:
            body = parse_body(body_str)
            what = str(body.get("WHAT", "") or "").strip()
            why = str(body.get("WHY", "") or "").strip()
            wval = str(body.get("WHAT_VALUE", "") or "").strip()
            sdate = str(body.get("START_DATE", "") or "").strip()
            edate = str(body.get("END_DATE", "") or "").strip()
            if not what or not wval:
                return 200, "ok"
            with SAVE_LOCK:
                s = load_save()
                mails = s.get("mails") or []
                # First-clear guard (live replies "mysql_error:first_clear"): the
                # reward for one stage's first clear must only ever land once.
                if "first clear" in why.lower() or "첫 클리어" in why:
                    for m in mails:
                        if (str(m.get("what", "")) == what
                                and str(m.get("what_value", "")) == wval
                                and str(m.get("why", "")) == why):
                            LOG.info("  put_mailbox_reward DUP first-clear "
                                     "what=%s value=%s -> mysql_error:first_clear",
                                     what, wval)
                            return 200, "mysql_error:first_clear"
                mails.append({
                    "sn": next_mail_sn(mails),
                    "why": why,
                    "what": what,
                    "what_value": wval,
                    "start_date": sdate,
                    "end_date": edate,
                })
                s["mails"] = mails
                store_save(s)
            LOG.info("  put_mailbox_reward stored what=%s value=%s why=%s "
                     "mails=%d", what, wval, why, len(mails))
            return 200, "ok"
        except Exception:
            traceback.print_exc()
        return 200, "ok"
    if "get_reward2_mailbox.php" in lp:
        # get_reward2_mailbox success_fn:
        #   if u.RESULT==0 -> "empty" branch -> n&&n() (check_reward_mailbox).
        #   else for(r=u.LIST;...) parse each reward mail (SN/WHY/WHAT/WHAT_VALUE).
        # A daily gift (once per UTC day) makes the mailbox useful offline.
        try:
            with SAVE_LOCK:
                s = load_save()
                mails = mailbox_ensure_offline_gift(s)
                mails = mailbox_ensure_daily_mail(s)
            if not mails:
                return 200, json.dumps({"STATE": "SUCCESS", "is_subscribe": "no", "RESULT": 0})
            today = time.strftime("%Y-%m-%d")
            return 200, json.dumps({
                "STATE": "SUCCESS", "is_subscribe": "no", "RESULT": 1,
                "LIST": [{
                    "SN": m["sn"], "WHY": m.get("why") or "DAILY GIFT",
                    "WHAT": m["what"], "WHAT_VALUE": str(m["what_value"]),
                    "START_DATE": m.get("start_date") or today,
                    "END_DATE": m.get("end_date") or "20991231",
                } for m in mails],
            })
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "SUCCESS", "is_subscribe": "no", "RESULT": 0})
    if "auto_event_system/get_event_info.php" in lp:
        # get_event_info success_fn:
        #   PACKAGE_STORE branch parses limited_package_time/buy_num etc -> keep.
        #   Then  i.EVENT_TYPE==999 ? t&&t(i) : t&&t(i.STATE)
        #   auto_event_system_check(n==999) callback does
        #   for(... i.event_arr.length ...) -> the 999 response MUST carry
        #   EVENT_TYPE=999 (number) AND event_arr array ([] -> no auto events).
        #   Non-999 callbacks expect STRING STATE ("ok"/"no") for AUTO_EVENT_FLAG.
        try:
            ev_type = int(parse_body(body_str).get("EVENT_TYPE", 999))
        except Exception:
            ev_type = 999
        r = {
            "STATE": "SUCCESS",
            "is_subscribe": "no",
            # non-zero so S_PACKAGE_STORE.buy_package_item() does NOT go
            # S_EXITPOPUP(reload). end in the past -> package event = closed
            # (flag=0), shop renders without crashing.
            "limited_package_time": "1700000000||1750000000",
            "limited_package_buy_num": "0,0,0,0",
            "char_package_cnt": 0, "special_a_package_cnt": 0, "special_b_package_cnt": 0,
            "is_grow_package": "no", "is_userpaid": 0,
            "cloud_piece_package_cnt": 0, "echo_a_cnt": 0, "echo_b_cnt": 0,
            "random_item_cnt": 0, "wow_cnt": 0, "random_box_cnt": 0,
            "ogong_random_box_cnt": 0, "mukhyang_random_box_cnt": 0, "lunar_lucky_cnt": 0,
            "serpent_box_cnt": 0, "flame_cavalier_box_cnt": 0, "blackraven_box_cnt": 0,
            "tortoise_package_cnt": 0, "serpent_package_cnt": 0, "vermilion_package_cnt": 0,
            "flame_cavalier_package_cnt": 0, "chaos_package_cnt": 0, "sage_package_cnt": 0,
            "bamboo_package_cnt": 0,
            "month_ruby_package_buy_status": "no", "month_entry_package_buy_status": "no",
            "month_cloud_package_buy_status": "no", "cloud_mul": "1",
            "month_ruby_end_date": "20300101",
            "month_entry_end_date": "20300101",
            "month_cloud_end_date": "20300101",
            "reward_info": [],
        }
        s = load_save()
        r["quest"] = str(s.get("quest") or "1,2:0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0,0,0:0,0,0:0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0:0:0,0,0:0:0:0:0:0:0:0:0:0")
        if ev_type == 999:
            r["EVENT_TYPE"] = 999
            # Auto-event list. Id 13 = "no level cap on S_UPGRADE" (the 4 gates
            # `AUTO_EVENT_FLAG[13]!=1 && (u>=USER.level | 80>USER.level)` in
            # S_UPGRADE.onClick). We always enable it so upgrade level is no
            # longer limited by player level. No other code reads flag 13.
            r["event_arr"] = [13]
            # S_MAINMENU START_BTN_NUM callback reads n.cur_boss_hp from this
            # same object when the player hits PLAY.
            r["cur_boss_hp"] = "0"
        else:
            r["EVENT_TYPE"] = ev_type
            r["STATE"] = "no"
        return 200, json.dumps(r)
    if "attendance_event.php" in lp:
        # gives S_ATTENDANCE_EVENT a valid date range so banner/folder images resolve
        # and S_MAINMENU event-entry code gets non-undefined dates. When today's
        # reward was already claimed, ALSO tell the client (menu re-entry GET) so
        # it does not re-show the daily check-in popup.
        att_today = time.strftime("%Y%m%d")
        _given = ""
        try:
            _s = load_save()
            if str(_s.get("attendance_reward_date", "") or "") == att_today:
                _given = "true"
        except Exception:
            _given = ""
        return 200, json.dumps({
            "STATE": "SUCCESS",
            "EVENT_START_DATE": "20260916 00:00:00",
            "EVENT_END_DATE": "20261016 23:59:59",
            "EVENT_VIEW_START_DATE": "20260916 00:00:00",
            "EVENT_VIEW_END_DATE": "20261016 23:59:59",
            "EVENT_NEXT_START_DATE": "20261017 00:00:00",
            "TODAY_ATT_STAMP_GET_MAX": 0, "TODAY_DAY_STAMP_GET_MAX": 0,
            "TODAY_PVP_STAMP_GET_MAX": 0, "TODAY_STAMP_GET_MAX": 0,
            "EVENT_STAMP_GET_MAX": 0, "TODAY_DAY_IF_VALUE": 0, "TODAY_PVP_IF_VALUE": 0,
            "TYPE": "EVENT_VIEW", "TOT_STAMP": 0, "SHOW_STAMP": 0,
            "EVENT_REWARD_NUM": 0, "EVENT_REWARD": [],
            "given": _given, "ATT_GIVEN": ("1" if _given == "true" else "0"),
        })
    if ("update_guild_inter.php" in lp or "update_guild_main.php" in lp
            or "update_guild_battle.php" in lp or "update_guild_boss.php" in lp
            or "update_guild_shop.php" in lp):
        # Guild thường + Guild War + Guild Boss + Guild Shop: xem guild_backend.py.
        # Stub cũ chỉ trả "no_guild" nên không tạo/join/lưu/mua được gì.
        return guild_dispatch(rel_path, body_str, DB_CONN, SAVE_LOCK, _uid())
    if "update_guild_" in lp or "guild/" in lp:
        # World Boss 2026 là thứ khác (boss_2026/*.php, xử lý ở trên). Giữ trả
        # no_guild để màn đó mở được thay vì rơi vào default -> popup lỗi mạng.
        try:
            act = json.loads(parse_body(body_str).get("json_obj", "{}")).get("act", "")
        except Exception:
            act = ""
        if act == "check_guild_member":
            return 200, json.dumps({"result": "no_guild",
                                    "exit_remain_time": None,
                                    "exit_time": None,
                                    "season_data": None})
        return 200, json.dumps({"result": "ok", "data": "no_guild",
                                "season_data": None})
    if "put_error_log.php" in lp or "put_hacking_log.php" in lp or "put_debug_log.php" in lp:
        body = parse_body(body_str)
        err = body.get("ERROR_LOG") or body.get("LOG") or body_str[:120]
        LOG.info("  client log: %s", str(err)[:200].replace("\r", " ").replace("\n", " "))
        return 200, "ok"
    if "temple/update_dragon_info.php" in lp:
        # Four Gods Temple ("사방신 신전"): main menu BD button -> S_FOUR_GODS ->
        # pick a beast -> update_dragon_info({MODE:"GET"|"UPDATE", TYPE,...}).
        #   entry (S_FOUR_GODS row_focus 1): TYPE = focus 1..4
        #      -> response EVENT + GAGE (cur_gauge), STATE must be in
        #      {GET,NOTICE,SUCCESS,FAIL}; callback is the ONLY thing that calls
        #      loading_hide(). A bare "{}" makes i.STATE.search() throw and the
        #      temple stays on the loading spinner forever.
        #   battle (S_BLUE_DRAGON.yes): TYPE = beast unit 95/101/102/103,
        #      expects STATE (SUCCESS also adds the beast char), MULTI (gauge
        #      gained per offering), CLOUD (remaining cloud pieces).
        # 140 gauge = full -> SUCCESS unlocks the crafted beast; until then
        # FAIL. Every persuasion spends the server-advertised Cloud cost.
        BEAST_BY_FOCUS = {"1": "95", "2": "101", "3": "102", "4": "103"}
        try:
            body = parse_body(body_str)
            mode = body.get("MODE", "GET")
            vtype = body.get("TYPE", "1")
            vtype = BEAST_BY_FOCUS.get(vtype, vtype)
            with SAVE_LOCK:
                s = load_save()
                tg = s.get("temple_gauge") or {}
                try:
                    gauge = int(float(str(tg.get(vtype, "0") or 0)))
                except Exception:
                    gauge = 0
                try:
                    cloud = int(float(str(s.get("cloud_piece", "0") or 0)))
                except Exception:
                    cloud = 0
                if mode == "UPDATE":
                    if cloud < FOUR_GODS_PERSUASION_COST:
                        return 200, json.dumps({"STATE": "NOTICE", "EVENT": "yes",
                                                "MULTI": "0", "CLOUD": str(cloud)})
                    cloud -= FOUR_GODS_PERSUASION_COST
                    s["cloud_piece"] = str(cloud)
                    gauge = min(140, gauge + 1)
                    tg[vtype] = gauge
                    s["temple_gauge"] = tg
                    store_save(s)
                    st = "SUCCESS" if gauge >= 140 else "FAIL"
                    return 200, json.dumps({"STATE": st, "EVENT": "yes",
                                            "MULTI": "1", "CLOUD": str(cloud)})
            return 200, json.dumps({"STATE": "GET", "EVENT": "yes",
                                    "GAGE": str(gauge), "MULTI": "1",
                                    "CLOUD": str(cloud)})
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "GET", "EVENT": "yes", "GAGE": "0",
                                    "MULTI": "1", "CLOUD": "0"})
    if "temple/dragon_info_cheat.php" in lp:
        # dev-cheat twin of update_dragon_info; same shape so it never throws.
        return 200, json.dumps({"STATE": "GET", "EVENT": "yes", "GAGE": "0",
                                "MULTI": "1", "CLOUD": "0"})
    # ---------- PvP 2025 ----------
    if "pvp_2025/" in lp:
        try:
            body = parse_body(body_str)
            if "get_pvp_ranking.php" in lp:
                return 200, pvp_ranking_text(body)
            if "enter_pvp_game.php" in lp:
                return 200, pvp_enter_text(body)
            if "update_pvp_result.php" in lp:
                return 200, pvp_result_text(body)
            return 200, _pvp_error("-201", "unknown PvP endpoint")
        except Exception:
            traceback.print_exc()
            return 200, _pvp_error("-201", "PvP handler failed")

    # ---------- PvP Classic 2026 ----------
    if "pvp_cls_2026/" in lp:
        try:
            body = parse_body(body_str)
            if "get_pvp_cls_ranking.php" in lp:
                return 200, pvp_classic_ranking_text(body)
            if "enter_pvp_cls_game.php" in lp:
                return 200, pvp_classic_enter_text(body)
            if "update_pvp_cls_result.php" in lp:
                return 200, pvp_classic_result_text(body)
            return 200, _pvp_error("-201", "unknown Classic PvP endpoint")
        except Exception:
            traceback.print_exc()
            return 200, _pvp_error("-201", "Classic PvP handler failed")

    # ---------- Sky Garden (SKY_2026) ----------
    # Ranked endless-wave board (mode_select card -> gS_RANKING). The client
    # loads the ladder with get_sky_ranking, joins a run via enter_sky_game
    # (free ticket first, then ruby continuation paid by ENTRY_FEE_RUBY), and
    # reports the run with update_sky_result. Progress is kept in:
    #   sky_wave   best cleared wave (drives the board's USER.clear_wave)
    #   sky_nonce  latest GAME_NONCE the server handed out for a run
    if "sky_2026/get_sky_ranking.php" in lp or "sky/get_sky_ranking.php" in lp:
        try:
            with SAVE_LOCK:
                s = load_save()
            d1 = (s.get("DATA1") or "").split(",")
            best = int(str(s.get("sky_wave", "0") or 0))
            name = (s.get("USER_NAME") or (d1[0] if d1 else "") or _uid() or "ME")
            lv = 1
            rby = 0
            team = "1:2:3:4:5"
            try:
                lv = int(d1[8] or 1)
            except Exception:
                lv = 1
            try:
                rby = int(float(d1[2] or 0))
            except Exception:
                rby = 0
            if len(d1) > 14:
                team = d1[14]
            shared = sky_ranking() if DB_CONN else []
            if shared:
                ranks = []
                for pos, row in enumerate(shared, 1):
                    other = db_load_save(row["user_id"]) or {}
                    od1 = (other.get("DATA1") or "").split(",")
                    ranks.append({"ranking": pos,
                                  "user_name": other.get("USER_NAME") or (od1[0] if od1 else "") or row["user_id"],
                                   "platform": "WEB", "level": int(od1[8] or 1) if len(od1) > 8 and str(od1[8] or "").isdigit() else 1,
                                   "lang": _eldorado_lang_of(od1), "team": od1[14] if len(od1) > 14 else "1:2:3:4:5",

                                  "clear_wave": row["clear_wave"]})
                my_rank = next((i for i, row in enumerate(shared, 1) if row["user_id"] == _uid()), 0)
            else:
                ranks = [{"ranking": 1, "user_name": name, "platform": "WEB",
                          "level": lv, "lang": _eldorado_lang_of(d1), "team": team,
                          "clear_wave": best}]
                my_rank = 1
            return 200, json.dumps({
                "STATE": "SUCCESS",
                "ranking_list": ranks,
                "my_ranking": str(my_rank),
                "CLEAR_WAVE": str(best),
                "CLEAR_DATE": time.strftime("%Y%m%d") if best else "",
                "entry_fee_ruby": "1",
                "PLATFORM_NAME_COM": "",
            })
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "SUCCESS", "ranking_list": [],
                                    "my_ranking": "0", "CLEAR_WAVE": "0",
                                    "CLEAR_DATE": "", "entry_fee_ruby": "1",
                                    "PLATFORM_NAME_COM": ""})
    if "sky_2026/enter_sky_game.php" in lp:
        try:
            body = parse_body(body_str)
            mode = body.get("MODE", "ENTRY_TICKET")
            wave = 0
            try:
                wave = int(float(str(body.get("CHALLENGE_WAVE", "0") or 0)))
            except Exception:
                wave = 0
            fee = (1 + wave // 10) if mode == "ENTRY_RUBY" else 0
            with SAVE_LOCK:
                s = load_save()
                d1 = (s.get("DATA1") or "").split(",")
                while len(d1) < 21:
                    d1.append("0")
                ruby = int(float(d1[2] or 0))
                if fee and ruby < fee:
                    return 200, json.dumps({"STATE": "ERROR", "CODE": "-103",
                                            "ERROR_MESSAGE": "not enough ruby"})
                if fee:
                    ruby -= fee
                    d1[2] = str(ruby)
                    s["DATA1"] = ",".join(d1)
                nonce = secrets.token_hex(8)
                s["sky_nonce"] = nonce
                store_save(s)
                sky_record_start(_uid(), nonce)
            LOG.info("  sky enter MODE=%s wave=%d fee=%d ruby_after=%d",
                     mode, wave, fee, ruby)
            return 200, json.dumps({"STATE": "SUCCESS",
                                    "GAME_NONCE": nonce,
                                    "s_add_ruby": str(ruby),
                                    "ENTRY_FEE_RUBY": str(fee)})
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "ERROR", "CODE": "-101",
                                    "ERROR_MESSAGE": "sky enter failed"})
    if "sky_2026/update_sky_result.php" in lp:
        try:
            body = parse_body(body_str)
            wave = 0
            try:
                wave = int(float(str(body.get("CHALLENGE_WAVE", "0") or 0)))
            except Exception:
                wave = 0
            res = str(body.get("RESULT", "") or "")
            nonce = str(body.get("GAME_NONCE", "") or "")
            if DB_CONN and not sky_record_result(_uid(), nonce, wave, res):
                return 200, json.dumps({"STATE": "ERROR", "CODE": "-104",
                                        "ERROR_MESSAGE": "invalid or used sky run"})
            with SAVE_LOCK:
                s = load_save()
                best = int(str(s.get("sky_wave", "0") or 0))
                if res == "W":
                    best = max(best, wave)
                    s["sky_wave"] = str(best)
                d1 = (s.get("DATA1") or "").split(",")
                ruby = 0
                try:
                    ruby = int(float(d1[2] or 0))
                except Exception:
                    ruby = 0
                store_save(s)
            LOG.info("  sky result RESULT=%s wave=%d best=%d", res, wave, best)
            return 200, json.dumps({"STATE": "SUCCESS",
                                    "CLEAR_WAVE": str(best),
                                    "CLEAR_DATE": time.strftime("%Y%m%d"),
                                    "my_ranking": "1",
                                    "s_add_ruby": str(ruby)})
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "SUCCESS", "CLEAR_WAVE": "0",
                                    "CLEAR_DATE": ""})
    # ---------- WORLD BOSS 2026 (BOSS_2026/*.php) ----------
    # The three endpoints the client actually calls. It asks for BOSS_2026/ and
    # for BOSS_2026_TEST/ when TEST_MODE.BOSS_TEST_SERVER is on -> same handler
    # for both prefixes. Nothing here may answer "{}": every reply carries STATE
    # and the fields parse_ranking_info()/run_boss_game() read.
    if "boss_2026/" in lp or "boss_2026_test/" in lp:
        try:
            if "get_boss_ranking.php" in lp:
                return 200, boss_ranking_text()
            if "enter_boss_game.php" in lp:
                return 200, boss_enter_text(parse_body(body_str))
            if "update_boss_result.php" in lp:
                return 200, boss_result_text(parse_body(body_str))
            return _boss_err("-101", "unknown world boss endpoint")
        except Exception:
            traceback.print_exc()
            return _boss_err("-101", "world boss handler failed")
    if "boss/get_boss_tiket_to_server.php" in lp:
        # Legacy ticket read; the 2026 screen does not need it but the daily
        # attendance path still calls it. The client does parseInt(body), so a
        # non-number would make S_RANKING_BOSS.tiket NaN.
        try:
            with SAVE_LOCK:
                s = load_save()
            return 200, str(_boss_ticket_read(s, time.strftime("%Y%m%d"))[0])
        except Exception:
            traceback.print_exc()
            return 200, "0"
    if "boss/update_boss_tiket_to_server.php" in lp:
        # The attendance screen pushes "10 tickets" here on EVERY open, so the
        # grant has to be day-guarded or reopening it would refill a spent
        # ticket. The posted TIKET is not trusted for the same reason -- the
        # offline server owns the daily count (BOSS_DAILY_TICKETS).
        try:
            with SAVE_LOCK:
                s = load_save()
                _boss_ticket_take(s, time.strftime("%Y%m%d"))
                store_save(s)
            return 200, json.dumps({"STATE": "SUCCESS"})
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "ERROR"})
    # ---------- Cloud Garden arena (cloud_garden/cloud_garden_ranking.php) --
    # Timed ranked minigame (mode_select card -> gS_RANKING_CLOUD_GARDEN).
    # All interactions go through this one endpoint with a MODE switch:
    #   RANKING_GET  ladder + season config (called on board open)
    #   GAME_TICKET  start a run with a free daily ticket
    #   GAME_RUBY    start a run paying ENTER_RUBY
    #   GAME_END     report the finished run, bank cloud pieces
    # Board progress lives in: cloud_score (best), cloud_score_day (last
    # score date so a tie-in-day keeps the newer score), cloud_ticket_day /
    # cloud_ticket_left (daily free tickets), cloud_piece (spendable).
    if "cloud_garden/cloud_garden_ranking.php" in lp:
        try:
            body = parse_body(body_str)
            mode = body.get("MODE", "RANKING_GET")
            today = time.strftime("%Y%m%d")
            with SAVE_LOCK:
                s = load_save()
                d1 = (s.get("DATA1") or "").split(",")
                while len(d1) < 21:
                    d1.append("0")
                ruby = int(float(d1[2] or 0))
                name = (s.get("USER_NAME") or (d1[0] if d1 else "") or _uid() or "ME")
                best = max(0, int(float(str(s.get("cloud_score", "0") or 0))))
                cur_ticket = 0
                if s.get("cloud_ticket_day") == today:
                    cur_ticket = max(0, int(float(str(s.get("cloud_ticket_left", "3") or 0))))
                if mode == "RANKING_GET":
                    # Initialize the daily free-ticket balance when the board
                    # is opened.  Previously this happened only after the
                    # first GAME_TICKET click, so a fresh day displayed zero
                    # tickets and the client skipped the free-entry path.
                    if s.get("cloud_ticket_day") != today:
                        s["cloud_ticket_day"] = today
                        s["cloud_ticket_left"] = "3"
                        cur_ticket = 3
                        store_save(s)
                    reset_start, reset_end, reset_start_text, reset_end_text = cloud_ranking_reset_window()
                    team = d1[14] if len(d1) > 14 else "1:2:3:4:5"
                    ranks, board_score, board_rank = _cloud_ranking_payload(
                        _uid(), s,
                        _cloud_ranking_rows(_uid(), s, name, team.replace(":", "||")),
                    )
                    return 200, json.dumps({
                        "STATE": "SUCCESS",
                        "RANKING_ARR": ranks,
                        "MY_SCORE": str(board_score),
                        "MY_RANKING": str(board_rank),
                        "cur_ticket": str(cur_ticket),
                        "TODAY_LIMIT_TICKET": "3",
                        "ORDER_LIMIT": "50",
                        "ENTER_LIMIT_STAGE": str(s.get("cloud_enter_stage") or "1"),
                        "PLAY_LIMIT_TIME": "60",
                        "ENTER_RUBY": str(s.get("cloud_enter_ruby") or "100"),
                        "BOSS_AP_INFO": "0:0",
                        "CHAR_AP_INFO": {
                            "char_down": "",
                            "char_up": "",
                            "down": "",
                            "up": "",
                        },
                        "CHAR_AP_UP_NUM": "0",
                        "CHAR_AP_DOWN_NUM": "0",
                        "RANKING_PLAY_DATETIME": reset_end_text,
                        "RANKING_SHOW_DATETIME": reset_start_text,
                        "RANKING_INIT_TIMESTAMP": str(reset_start),
                        "RANKING_PLAY_TIMESTAMP": str(reset_end),
                        "RANKING_SHOW_TIMESTAMP": str(reset_start),
                        "REWARD_DEFAULT_VALUE": "",
                        "REWARD_INFO": [],
                    })
                if mode == "GAME_TICKET":
                    if s.get("cloud_ticket_day") != today:
                        s["cloud_ticket_day"] = today
                        s["cloud_ticket_left"] = "3"
                        cur_ticket = 3
                    if cur_ticket <= 0:
                        return 200, json.dumps({"STATE": "SUCCESS", "TYPE": "GAME_START_ERROR",
                                                "DESCRIPTION": "no ticket",
                                                "DESCRIPTION_EN": "no ticket"})
                    s["cloud_ticket_left"] = str(cur_ticket - 1)
                    nonce = secrets.token_hex(8)
                    s["cloud_nonce"] = nonce
                    store_save(s)
                    return 200, json.dumps({"STATE": "SUCCESS", "TYPE": "OK",
                                            "after_ticket": str(cur_ticket - 1),
                                            "GAME_NONCE": nonce})
                if mode == "GAME_RUBY":
                    fee = int(float(str(s.get("cloud_enter_ruby") or "100")))
                    if ruby < fee:
                        return 200, json.dumps({"STATE": "SUCCESS", "TYPE": "GAME_START_ERROR",
                                                "DESCRIPTION": "not enough ruby",
                                                "DESCRIPTION_EN": "not enough ruby"})
                    ruby -= fee
                    d1[2] = str(ruby)
                    s["DATA1"] = ",".join(d1)
                    nonce = secrets.token_hex(8)
                    s["cloud_nonce"] = nonce
                    store_save(s)
                    return 200, json.dumps({"STATE": "SUCCESS", "TYPE": "OK",
                                            "after_ruby": str(ruby),
                                            "GAME_NONCE": nonce})
                if mode == "GAME_END":
                    score = 0
                    try:
                        score = int(float(str(body.get("SCORE", "0") or 0)))
                    except Exception:
                        score = 0
                    win = max(1, min(500, max(0, score) // 20))
                    # tie-in-day keeps the newer score as the best
                    if score > best or s.get("cloud_score_day") == today:
                        best = max(best, score)
                        s["cloud_score_day"] = today
                        s["cloud_score"] = str(best)
                    pc = int(float(str(s.get("cloud_piece", "0") or 0)))
                    pc += win
                    s["cloud_piece"] = str(pc)
                    _cloud_ranking_rows(_uid(), s, name, d1[14].replace(":", "||") if len(d1) > 14 else "")
                    store_save(s)
                    return 200, json.dumps({"STATE": "SUCCESS", "TYPE": "OK",
                                            "MY_SCORE": str(best),
                                            "win_piece": str(win),
                                            "tot_piece": str(pc),
                                            "IS_SCORE_REFRESH": "1"})
            return 200, json.dumps({"STATE": "ERROR", "DESCRIPTION": "bad cloud_garden mode"})
        except Exception:
            traceback.print_exc()
            return 200, json.dumps({"STATE": "ERROR", "DESCRIPTION": "cloud_garden failed"})
    if "mobile_link/get_cur_run_count.php" in lp:
        # daily run counter; client parses a plain non-empty number and the
        # mismatch penalty is compiled out with &&!1, so a simple "1" is safe.
        return 200, "1"
    if "cloud_garden/edit_cloud_garden.php" in lp or "edit_cloud_garden.php" in lp:
        # Team 7-star -> 8-star evolution (client S_MAKETEAM.evolution_8_star).
        # The client POSTs MODE=CHAR_EVO_8 with ADD_PIECE=cloud_piece_evo_8
        # (500) and expects the remaining balance back in tot_piece so it can
        # set USER.cloud_piece and flip the character to 8-star locally via
        # evolution_yes(). CHAR_EVO_6/7/9 use the same endpoint but older
        # targets; we always deduct ADD_PIECE and return the new balance.
        # The client never sends its essence cost: edit_cloud_garden forwards
        # only MODE/ADD_PIECE/ETC (CEL_PIECE is dropped). CHAR_EVO_9 has a
        # fixed cost (CELESTIAL_PIECE_EVO_9) that the server must deduct and
        # return as cel_essn, otherwise the 9-star evolution spends zero
        # essence and the number never changes after reloading.
        try:
            body = parse_body(body_str)
            mode = body.get("MODE", "")
            add = int(float(str(body.get("ADD_PIECE", "0") or 0)))
            cel_cost = int(CELESTIAL_PIECE_EVO_9) if mode == "CHAR_EVO_9" else 0
            with SAVE_LOCK:
                s = load_save()
                cur = int(float(str(s.get("cloud_piece", "0") or 0)))
                if mode and add > 0:
                    cur = max(0, cur - add)
                s["cloud_piece"] = str(cur)
                cel = int(float(str(s.get("celestial_essence", "0") or 0)))
                if cel_cost > 0:
                    cel = max(0, cel - cel_cost)
                    s["celestial_essence"] = str(cel)
                store_save(s)
            LOG.info("  cloud_garden edit MODE=%s ADD_PIECE=%d -> cloud_piece=%d cel_essn=%d",
                     mode, add, cur, cel)
            return 200, json.dumps({"STATE": "SUCCESS", "tot_piece": str(cur),
                                    "cel_essn": str(cel),
                                    "add_piece": add, "MODE": mode})
        except Exception:
            traceback.print_exc()
            cur = int(float(str(load_save().get("cloud_piece", "0") or 0)))
            return 200, json.dumps({"STATE": "ERROR", "tot_piece": str(cur)})
    if "toolshop/get_balances.php" in lp:
        try:
            s = load_save()
            d1 = (s.get("DATA1") or "").split(",")
            return 200, json.dumps({
                "STATE": "SUCCESS",
                "gold": d1[1] if len(d1) > 1 else "0",
                "ruby": d1[2] if len(d1) > 2 else "0",
                "bp": s.get("bp", "0"),
                "cloud": s.get("cloud_piece", "0"),
                "essence": s.get("celestial_essence", "0"),
                "rates": [{"from": k[0], "to": k[1], "cost": v[0], "gain": v[1]}
                          for k, v in CONVERT_RATES.items()],
            })
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "toolshop/convert.php" in lp:
        # Atomic conversion: player SPENDS COUNT units of FROM, gains
        # floor(COUNT * gain / cost) units of TO. Runs under SAVE_LOCK so the
        # same gold/cloud can never be double-spent by concurrent exchanges.
        try:
            body = parse_body(body_str)
            frm = str(body.get("FROM", "") or "").strip().upper()
            to = str(body.get("TO", "") or "").strip().upper()
            rate = CONVERT_RATES.get((frm, to))
            if not rate:
                return 200, json.dumps({"STATE": "ERROR", "msg": "unknown pair"})
            cost, gain = rate
            try:
                count = int(float(str(body.get("COUNT", "0") or 0)))
            except (TypeError, ValueError):
                count = 0
            if count <= 0 or count > 10**9:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad count"})
            with SAVE_LOCK:
                s = load_save()
                d1 = (s.get("DATA1") or "").split(",")
                while len(d1) < 21:
                    d1.append("0")
                cur = {
                    "GOLD": int(float(d1[1] or 0)),
                    "RUBY": int(float(d1[2] or 0)),
                }
                cur["BP"] = int(float(str(s.get("bp", "0") or 0)))
                cur["CLOUD"] = int(float(str(s.get("cloud_piece", "0") or 0)))
                cur["ESSENCE"] = int(float(str(s.get("celestial_essence", "0") or 0)))
                gained = count * gain // cost
                spent = gained * cost // gain
                if gained <= 0:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "too small"})
                if cur[frm] < spent:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "not enough"})
                cur[frm] -= spent
                cur[to] += gained
                d1[1] = str(cur["GOLD"])
                d1[2] = str(cur["RUBY"])
                s["DATA1"] = ",".join(d1)
                s["bp"] = str(cur["BP"])
                s["cloud_piece"] = str(cur["CLOUD"])
                s["celestial_essence"] = str(cur["ESSENCE"])
                store_save(s)
            LOG.info("  ToolShop %d %s -> %d %s", spent, frm, gained, to)
            return 200, json.dumps({
                "STATE": "SUCCESS",
                "spent": spent,
                "gained": gained,
                "gold": cur["GOLD"], "ruby": cur["RUBY"], "bp": cur["BP"],
                "cloud": cur["CLOUD"], "essence": cur["ESSENCE"],
            })
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/moss_moon.php" in lp:
        try:
            return _moss_moon_wallet(parse_body(body_str), _uid())
        except Exception:
            traceback.print_exc()
            return 500, json.dumps({"STATE": "ERROR", "msg": "wallet operation failed"})
    if "wallet/checkin.php" in lp:
        # Web daily check-in. State lives in s["farm_ci"] = {"ym","days"}; each
        # calendar day can be claimed once, granting CHECKIN_REWARDS[day-1]
        # straight into the game account, atomically.
        try:
            body = parse_body(body_str)
            now = time.localtime()
            ym = time.strftime("%Y%m", now)
            today = now.tm_mday
            action = str(body.get("ACTION", "info") or "info").strip().upper()
            with SAVE_LOCK:
                s = load_save()
                ci = s.get("farm_ci")
                if not isinstance(ci, dict) or ci.get("ym") != ym:
                    ci = {"ym": ym, "days": []}
                days = [int(x) for x in (ci.get("days") or [])]

                def ciresp(extra):
                    resp = {"STATE": "SUCCESS", "ym": ym, "today": today,
                            "days": days, "rewards": CHECKIN_REWARDS}
                    resp.update(extra)
                    return 200, json.dumps(resp)

                if action != "CLAIM":
                    return ciresp({})
                if today in days:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "already"})
                if today > len(CHECKIN_REWARDS):
                    return 200, json.dumps({"STATE": "ERROR", "msg": "no reward for today"})
                typ, amt = CHECKIN_REWARDS[today - 1]
                d1 = (s.get("DATA1") or "").split(",")
                while len(d1) < 21:
                    d1.append("0")
                if typ == "GOLD":
                    d1[1] = str(int(float(d1[1] or 0)) + amt)
                    s["DATA1"] = ",".join(d1)
                elif typ == "RUBY":
                    d1[2] = str(int(float(d1[2] or 0)) + amt)
                    s["DATA1"] = ",".join(d1)
                elif typ == "BP":
                    s["bp"] = str(int(float((s.get("bp") or "0"))) + amt)
                elif typ == "CLOUD":
                    s["cloud_piece"] = str(int(float((s.get("cloud_piece") or "0"))) + amt)
                elif typ == "ESSENCE":
                    s["celestial_essence"] = str(int(float((s.get("celestial_essence") or "0"))) + amt)
                elif typ == "GTICKET":
                    add_tickets(s, "generator", amt)
                elif typ == "STICKET":
                    add_tickets(s, "sudoku", amt)
                else:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "bad reward"})
                days.append(today)
                ci["days"] = days
                s["farm_ci"] = ci
                store_save(s)
            LOG.info("  RubyFarm checkin day=%d +%d %s (days=%d)", today, amt, typ, len(days))
            return ciresp({"claimed": typ, "amount": amt})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/mywallet.php" in lp:
        # RubyFarm wallet readout. "game" is separately stored from the save
        # wallet so a misbehaving page can never touch the real ruby directly.
        # Also lazily grants the daily free tickets (ticket_free_day marker).
        try:
            with SAVE_LOCK:
                s = load_save()
                ensure_ticket_grant(s)
                d1 = (s.get("DATA1") or "").split(",")
                w = s.get("wallet_ruby") or 0
                t = s.get("tickets")
                tgn = int(t.get("generator", 0)) if isinstance(t, dict) else 0
                tsd = int(t.get("sudoku", 0)) if isinstance(t, dict) else 0
                store_save(s)
                return 200, json.dumps({
                    "STATE": "SUCCESS",
                    "wallet": str(int(float(w))),
                    "ruby": d1[2] if len(d1) > 2 else "0",
                    "gold": d1[1] if len(d1) > 1 else "0",
                    "bp": s.get("bp", "0"),
                    "cloud": s.get("cloud_piece", "0"),
                    "essence": s.get("celestial_essence", "0"),
                    "day": s.get("wallet_day", ""),
                    "earned": str(s.get("wallet_earned", 0)),
                    "cap": str(DAILY_RUBY_CAP),
                    "cd": str(MINIGAME_CD_SEC),
                    "tgen": str(tgn),
                    "tsud": str(tsd),
                    "tfree": {k: str(v) for k, v in TICKET_FREE_DAILY.items()},
                    "tprices": {k: str(v) for k, v in TICKET_PRICES.items()},
                })
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/award.php" in lp:
        # Reward a mini-game result. GAME + SCORE; server computes the award,
        # enforces the per-game cooldown and the daily cap, then credits the
        # wallet (never the game ruby directly).
        try:
            body = parse_body(body_str)
            game = str(body.get("GAME", "") or "").strip().lower()
            try:
                score = int(float(str(body.get("SCORE", "0") or 0)))
            except (TypeError, ValueError):
                score = 0
            award = _minigame_ruby(game, score)
            if award <= 0:
                return 200, json.dumps({"STATE": "ERROR", "msg": "no reward"})
            with SAVE_LOCK:
                s = load_save()
                today = time.strftime("%Y%m%d")
                if s.get("wallet_day") != today:
                    s["wallet_day"] = today
                    s["wallet_earned"] = "0"
                earned = int(float(str(s.get("wallet_earned", 0) or 0)))
                left = DAILY_RUBY_CAP - earned
                if left <= 0:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "daily cap"})
                if award > left:
                    award = left
                last = (s.get("wallet_last") or {})
                last_ts = int(float(str(last.get(game, 0) or 0)))
                wait = int(MINIGAME_CD_SEC - (time.time() - last_ts))
                if wait > 0:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "cooldown", "wait": wait})
                cost = int(float(str(MINIGAME_COST.get(game, 0) or 0)))
                if cost > 0:
                    d1c = (s.get("DATA1") or "").split(",")
                    while len(d1c) < 21:
                        d1c.append("0")
                    if int(float(d1c[1] or 0)) < cost:
                        return 200, json.dumps({"STATE": "ERROR", "msg": "need gold"})
                    d1c[1] = str(int(float(d1c[1] or 0)) - cost)
                    s["DATA1"] = ",".join(d1c)
                cur = int(float(str(s.get("wallet_ruby", 0) or 0)))
                cur += award
                s["wallet_ruby"] = str(cur)
                s["wallet_earned"] = str(earned + award)
                last[game] = str(int(time.time()))
                s["wallet_last"] = last
                store_save(s)
            LOG.info("  RubyFarm award game=%s score=%d +%dr (wallet=%d, gold_fee=%d)", game, score, award, cur, cost)
            return 200, json.dumps({"STATE": "SUCCESS", "earned": award,
                                    "wallet": str(cur), "cost": cost,
                                    "day": s.get("wallet_day"), "earned_today": s.get("wallet_earned")})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/genrep_start.php" in lp:
        # Open a paid Generator Repair run: spend TICKET generator ticket(s).
        # No per-day cap — a ticket play never counts toward (or is capped by)
        # daily plays. Rewards are claimed separately via genrep_claim.php.
        try:
            body = parse_body(body_str)
            diff = str(body.get("DIFF", "") or "").strip().lower()
            cfg = GENREP_DIFFS.get(diff)
            if not cfg:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad diff"})
            with SAVE_LOCK:
                s = load_save()
                ensure_ticket_grant(s)
                rem = spend_tickets(s, "generator", cfg["ticket"])
                if rem is None:
                    tg = ticket_count(s, "generator")
                    return 200, json.dumps({"STATE": "ERROR", "msg": "need ticket",
                                            "tickets": str(tg), "ticket": cfg["ticket"]})
                s["genrep_session"] = {"diff": diff, "ts": time.time()}
                store_save(s)
            LOG.info("  RubyFarm genrep start diff=%s -%d genrep-ticket (left=%d)", diff, cfg["ticket"], rem)
            return 200, json.dumps({"STATE": "SUCCESS", "diff": diff, "ticket": cfg["ticket"],
                                    "tickets": str(rem)})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/genrep_claim.php" in lp:
        # Settle a paid Generator repair run: verify the session opened by
        # genrep_start matches, pay PRIZE + GREAT*greatBonus into the wallet,
        # close the session. Not subject to the 300/day cap (tickets throttle it).
        try:
            body = parse_body(body_str)
            diff = str(body.get("DIFF", "") or "").strip().lower()
            cfg = GENREP_DIFFS.get(diff)
            if not cfg:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad diff"})
            try:
                greats = max(0, min(GENREP_GREAT_CAP, int(float(str(body.get("GREAT", "0") or 0)))))
            except (TypeError, ValueError):
                greats = 0
            with SAVE_LOCK:
                s = load_save()
                sess = s.get("genrep_session")
                if (not isinstance(sess, dict) or sess.get("diff") != diff
                        or time.time() - float(sess.get("ts", 0)) > GENREP_SESSION_TTL):
                    return 200, json.dumps({"STATE": "ERROR", "msg": "no session"})
                reward = cfg["prize"] + greats * cfg["great"]
                cur = int(float(str(s.get("wallet_ruby", 0) or 0))) + reward
                s["wallet_ruby"] = str(cur)
                today = time.strftime("%Y%m%d")
                if s.get("wallet_day") != today:
                    s["wallet_day"] = today
                    s["wallet_earned"] = "0"
                s["wallet_earned"] = str(int(float(str(s.get("wallet_earned", "0") or 0))) + reward)
                if "genrep_session" in s:
                    del s["genrep_session"]
                store_save(s)
            LOG.info("  RubyFarm genrep claim diff=%s great=%d +%dr (wallet=%d)", diff, greats, reward, cur)
            return 200, json.dumps({"STATE": "SUCCESS", "diff": diff, "greats": greats,
                                    "reward": reward, "prize": cfg["prize"], "wallet": str(cur)})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/sudoku_start.php" in lp:
        # Open a paid Sudoku run: spend TICKET sudoku ticket(s) for the chosen
        # difficulty, start the clock. Finishing inside the limit is settled via
        # sudoku_claim.php; timing out consumes the ticket with no prize.
        try:
            body = parse_body(body_str)
            diff = str(body.get("DIFF", "") or "").strip().lower()
            cfg = SUDOKU_DIFFS.get(diff)
            if not cfg:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad diff"})
            with SAVE_LOCK:
                s = load_save()
                ensure_ticket_grant(s)
                rem = spend_tickets(s, "sudoku", cfg["ticket"])
                if rem is None:
                    ts = ticket_count(s, "sudoku")
                    return 200, json.dumps({"STATE": "ERROR", "msg": "need ticket",
                                            "tickets": str(ts), "ticket": cfg["ticket"]})
                s["sudoku_session"] = {"diff": diff, "ts": time.time()}
                store_save(s)
            LOG.info("  RubyFarm sudoku start diff=%s -%d sudoku-ticket (left=%d)", diff, cfg["ticket"], rem)
            return 200, json.dumps({"STATE": "SUCCESS", "diff": diff, "ticket": cfg["ticket"],
                                    "prize": cfg["prize"], "time": cfg["time"],
                                    "tickets": str(rem)})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/sudoku_claim.php" in lp:
        # Settle a paid Sudoku run: verify the session opened by sudoku_start
        # matches, pay PRIZE into the wallet, close the session.
        try:
            body = parse_body(body_str)
            diff = str(body.get("DIFF", "") or "").strip().lower()
            cfg = SUDOKU_DIFFS.get(diff)
            if not cfg:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad diff"})
            with SAVE_LOCK:
                s = load_save()
                sess = s.get("sudoku_session")
                ttl = max(SUDOKU_SESSION_TTL, int(cfg.get("time", 0)) + SUDOKU_CLAIM_GRACE)
                if (not isinstance(sess, dict) or sess.get("diff") != diff
                        or time.time() - float(sess.get("ts", 0)) > ttl):
                    return 200, json.dumps({"STATE": "ERROR", "msg": "no session"})
                reward = cfg["prize"]
                cur = int(float(str(s.get("wallet_ruby", 0) or 0))) + reward
                s["wallet_ruby"] = str(cur)
                today = time.strftime("%Y%m%d")
                if s.get("wallet_day") != today:
                    s["wallet_day"] = today
                    s["wallet_earned"] = "0"
                s["wallet_earned"] = str(int(float(str(s.get("wallet_earned", "0") or 0))) + reward)
                if "sudoku_session" in s:
                    del s["sudoku_session"]
                store_save(s)
            LOG.info("  RubyFarm sudoku claim diff=%s +%dr (wallet=%d)", diff, reward, cur)
            return 200, json.dumps({"STATE": "SUCCESS", "diff": diff,
                                    "reward": reward, "prize": cfg["prize"], "wallet": str(cur)})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/tickets.php" in lp:
        # Ticket wallet: ACTION=info returns balances + prices + daily free;
        # ACTION=buy&TYPE=generator|sudoku&AMOUNT=n spends gold, adds tickets.
        # Each call also grants the daily free tickets (idempotent per day).
        try:
            body = parse_body(body_str)
            action = str(body.get("ACTION", "info") or "info").strip().upper()
            with SAVE_LOCK:
                s = load_save()
                ensure_ticket_grant(s)
                if action == "BUY":
                    typ = str(body.get("TYPE", "") or "").strip().lower()
                    if typ == "generator":
                        # Purchasing generator tickets is disabled: they are only
                        # granted for free via the daily login (ensure_ticket_grant).
                        return 200, json.dumps({"STATE": "ERROR", "msg": "daily only",
                                                "free": str(TICKET_FREE_DAILY.get("generator", 0))})
                    if typ not in TICKET_PRICES:
                        return 200, json.dumps({"STATE": "ERROR", "msg": "bad type"})
                    try:
                        n = max(1, min(99, int(float(str(body.get("AMOUNT", "1") or 1)))))
                    except (TypeError, ValueError):
                        n = 1
                    price = TICKET_PRICES[typ] * n
                    d1 = (s.get("DATA1") or "").split(",")
                    while len(d1) < 21:
                        d1.append("0")
                    gold = int(float(d1[1] or 0))
                    if gold < price:
                        return 200, json.dumps({"STATE": "ERROR", "msg": "need gold",
                                                "price": str(price), "gold": str(gold)})
                    gold -= price
                    d1[1] = str(gold)
                    s["DATA1"] = ",".join(d1)
                    add_tickets(s, typ, n)
                    LOG.info("  RubyFarm ticket buy type=%s n=%d -%d gold (gold=%d)", typ, n, price, gold)
                store_save(s)
                t = s.get("tickets")
                tgn = int(t.get("generator", 0)) if isinstance(t, dict) else 0
                tsd = int(t.get("sudoku", 0)) if isinstance(t, dict) else 0
                d1 = (s.get("DATA1") or "").split(",")
                return 200, json.dumps({"STATE": "SUCCESS",
                                        "generator": str(tgn), "sudoku": str(tsd),
                                        "gold": d1[1] if len(d1) > 1 else "0",
                                        "prices": {k: str(v) for k, v in TICKET_PRICES.items()},
                                        "free": {k: str(v) for k, v in TICKET_FREE_DAILY.items()},
                                        "day": s.get("ticket_free_day")})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    if "wallet/withdraw.php" in lp:
        # Move wallet ruby into the game account (DATA1[2]). Atomic under the
        # save lock so the same ruby can never be withdrawn twice.
        try:
            body = parse_body(body_str)
            try:
                amount = int(float(str(body.get("AMOUNT", "0") or 0)))
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0:
                return 200, json.dumps({"STATE": "ERROR", "msg": "bad amount"})
            with SAVE_LOCK:
                s = load_save()
                cur = int(float(str(s.get("wallet_ruby", 0) or 0)))
                if cur < amount:
                    return 200, json.dumps({"STATE": "ERROR", "msg": "not enough"})
                cur -= amount
                s["wallet_ruby"] = str(cur)
                d1 = (s.get("DATA1") or "").split(",")
                while len(d1) < 21:
                    d1.append("0")
                ruby = int(float(d1[2] or 0)) + amount
                d1[2] = str(ruby)
                s["DATA1"] = ",".join(d1)
                store_save(s)
            LOG.info("  RubyFarm withdraw +%dr to account (wallet=%d ruby=%d)", amount, cur, ruby)
            return 200, json.dumps({"STATE": "SUCCESS", "wallet": str(cur), "ruby": str(ruby)})
        except Exception:
            traceback.print_exc()
        return 200, json.dumps({"STATE": "ERROR"})
    # DayDungeon (added 9/23; restored from pyc)
    if "daydungeon/get_cur_day.php" in lp:
        try:
            now = time.localtime()
            cur_day = now.tm_wday + 1
            cur_week_num = int(time.time() // 604800)
            nxt = datetime.datetime(now.tm_year, now.tm_mon, now.tm_mday) + datetime.timedelta(days=1)
            next_day_timestamp = int(nxt.timestamp())
            return 200, f"{cur_day},{cur_week_num},{next_day_timestamp}"
        except Exception:
            traceback.print_exc()
            return 200, "1,1,2147483647"

    if "daydungeon/get_daydungeon_cur_ticket.php" in lp:
        today = time.strftime("%Y%m%d")
        with SAVE_LOCK:
            s = load_save()
            if s.get("dd_free_day") != today:
                s["dd_free_day"] = today
                s["dd_free_ticket"] = str(DAYDUNGEON_FREE_TICKET_DAY)
                store_save(s)
                return 200, str(DAYDUNGEON_FREE_TICKET_DAY)
            return 200, str(max(0, int(float(str(s.get("dd_free_ticket", "0") or 0)))))

    if "daydungeon/update_daydungeon_cur_ticket.php" in lp:
        today = time.strftime("%Y%m%d")
        try:
            body = parse_body(body_str)
            delta = int(float(str(body.get("FREE_TICKET_NUM", "0") or 0)))
        except Exception:
            delta = 0
        with SAVE_LOCK:
            s = load_save()
            if s.get("dd_free_day") != today:
                s["dd_free_day"] = today
                cur = DAYDUNGEON_FREE_TICKET_DAY
            else:
                cur = max(0, int(float(str(s.get("dd_free_ticket", "0") or 0))))
            new = max(0, cur + delta)
            s["dd_free_ticket"] = str(new)
            store_save(s)
            return 200, str(new)
    # Farm web (F0 khung): state nông trại nằm trong cùng save payload.
    if "farm/" in lp:
        try:
            return farm_dispatch(rel_path, body_str, DB_CONN, SAVE_LOCK, _uid())
        except PermissionError:
            return 401, json.dumps({"STATE": "ERROR", "CODE": "AUTH_REQUIRED"})
        except Exception:
            traceback.print_exc()
            return 500, json.dumps({"STATE": "ERROR"})
    # fallback
    return 200, "{}"

# ---------- HTTP handler ----------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    admin_control_only = False

    def log_message(self, fmt, *args):
        LOG.info("%s %s %s", time.strftime("%H:%M:%S"), self.command,
                 urlparse(self.path).path)

    def _is_direct_loopback(self):
        try:
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return False
        except ValueError:
            return False
        return not any(self.headers.get(h) for h in
                       ("Forwarded", "X-Forwarded-For", "CF-Connecting-IP"))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def _dispatch(self, method):
        path = urlparse(self.path).path.rstrip("/") or "/"
        is_admin_control = (
            path == "/admin-control" or path.startswith("/admin-control/")
        )
        is_legacy_admin = path == "/admin"

        if self.admin_control_only:
            if is_admin_control and try_handle_admin_control(
                    self, DB_CONN, SAVE_LOCK, BASE_DIR):
                return
            self._consume_rejected_body(method)
            self._respond(404, "Not Found", "text/plain; charset=utf-8")
            return

        if is_admin_control or is_legacy_admin:
            self._consume_rejected_body(method)
            self._respond(404, "Not Found", "text/plain; charset=utf-8")
            return
        self._handle(method)

    def _consume_rejected_body(self, method):
        if method != "POST":
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.close_connection = True
            return
        if content_length:
            self.rfile.read(content_length)

    def _handle(self, method):
        parsed = urlparse(self.path)
        rel_path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length else b""
        body_str = body_bytes.decode("utf-8", "replace") if body_bytes else ""

        # Per-request (thread-local) context: which Host did the client use
        # (drives base_url rewrites for LAN/internet play) and which account
        # is talking (routes save reads/writes to the right SQLite row).
        _tl.host = self.headers.get("Host") or f"localhost:{SRV_PORT}"
        _tl.scheme = "https" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else "http"
        _tl.method = method
        _tl.set_cookie = None

        LOG.info("%s %s body=%d", method, rel_path, content_length)
        if body_bytes:
            if "login_auth.php" in rel_path.lower():
                LOG.info("  body: <redacted login>")
            else:
                LOG.info("  body: %s", body_str[:400].replace("\r"," ").replace("\n"," "))

        # Account routing: the client carries its identity as HOST_ID on most
        # calls and UNIQ_ID on check_black_list_db; both map to the same id.
        wire_uid = ""
        for key in ("HOST_ID", "UNIQ_ID"):
            m = re.search(rf"(?:^|[&;]){re.escape(key)}=([^&;]*)", body_str)
            if m:
                v = unquote(m.group(1))
                if v and v.lower() != "null":
                    wire_uid = v
                    break
        if not wire_uid:
            q = urlparse(self.path).query
            for key in ("HOST_ID", "UNIQ_ID", "uid"):
                m = re.search(rf"(?:^|[&;]){re.escape(key)}=([^&;]*)", q or "")
                if m:
                    v = unquote(m.group(1))
                    if v and v.lower() != "null":
                        wire_uid = v
                        break
        session_uid = authenticated_user(self.headers.get("Cookie", ""))
        if DB_FILE and REQUIRE_LOGIN:
            _tl.uid = session_uid
            if WIRE_IDENTITY:
                # Client gui json_obj RAW (khong url-encode nen HOST_ID nam
                # trong JSON, khong phai o top-level form nen regex cua wire_uid
                # o tren khong bat duoc). Session la nen de, wire chi ghi de khi
                # ten mot tai khoan that — get_cur_run_count gui
                # HOST_ID=ELDORADO_OFFLINE_0001 nen phai lui ve session.
                # ponytail: toi da 3 SELECT doi 1 request; index accounts.id du.
                # `\+?` chi de chiu ban url-encode (encode con dau + = space).
                flat = unquote(body_str)
                for key in ("HOST_ID", "UNIQ_ID", "USER_NAME"):
                    m = re.search(rf'"{key}"\s*:\s*\+?\s*"([^"]*)"', flat)
                    if m and account_exists(m.group(1)):
                        _tl.uid = m.group(1)
                        break
        else:
            _tl.uid = session_uid or wire_uid

        # --- static assets from disk always ---
        fs_path = BASE_DIR / rel_path.lstrip("/")
        if not fs_path.is_file() and fs_path.suffix.lower() in STATIC_EXT:
            alt_ext = ".jpg" if fs_path.suffix.lower() == ".png" else (".png" if fs_path.suffix.lower() in {".jpg", ".jpeg"} else None)
            if alt_ext:
                alt_p = fs_path.with_suffix(alt_ext)
                if alt_p.is_file():
                    fs_path = alt_p
        if fs_path.is_file() and fs_path.suffix.lower() in STATIC_EXT:
            data = fs_path.read_bytes()
            # Rewrite embedded host/port in text assets so plain files
            # (loader.js boot endpoint, min.js bodies) always call THIS
            # server no matter which --port it binds.
            if fs_path.suffix.lower() in {".js", ".html", ".htm", ".css", ".json"}:
                txt = data.decode("utf-8", "replace")
                b = base_url()
                txt = txt.replace("https://game.busidol.com", b)
                txt = txt.replace("http://game.busidol.com", b)
                txt = txt.replace("https://localhost:8023", b)
                txt = txt.replace("http://localhost:8023", b)
                data = txt.encode("utf-8")
                LOG.info("  -> rewrote static to %s", b)
            self.send_response(200)
            self.send_header("Content-Type", guess_ct(rel_path))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache_hdr(rel_path))
            self.end_headers()
            self.wfile.write(data)
            LOG.info("  -> static %d", len(data))
            return

        # --- missing static asset: fetch from live host + cache to disk ---
        if (method == "GET" and fs_path.suffix.lower() in STATIC_EXT
                and not rel_path.endswith(".php")):
            for alias_key, alias_to in ASSET_ALIAS.items():
                # rpartition tren key bo "/" dau de phan `head` giu duoc dau
                # "/" phan cach giua goc asset va duong danh file.
                head, sep, _ = rel_path.rpartition(alias_key.lstrip("/"))
                if not sep:
                    continue
                alt = BASE_DIR / (head + alias_to.lstrip("/")).lstrip("/")
                if alt.is_file():
                    LOG.info("ASSET-ALIAS %s -> %s", rel_path, alias_to)
                    self._respond(200, alt.read_bytes(), guess_ct(alias_to))
                else:
                    LOG.info("ASSET-ALIAS MISS %s -> %s", rel_path, alias_to)
                    LOG.info("MISSING-ASSET %s", rel_path)
                    self._respond(200, BLANK_PNG, guess_ct(rel_path))
                return
            data = fetch_and_cache(rel_path)
            if data is None:
                if fs_path.suffix.lower() in IMAGE_EXT:
                    LOG.info("MISSING-ASSET %s", rel_path)
                    self._respond(200, BLANK_PNG, guess_ct(rel_path))
                    return
                self._respond(404, "", "text/plain")
                return
            self.send_response(200)
            self.send_header("Content-Type", guess_ct(rel_path))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache_hdr(rel_path))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        # Login is public; every other PHP-like account API requires the
# opaque server session when --require-login is enabled.
        lp = rel_path.lower()
        php_like = (rel_path.endswith(".php") or "/APP_VALIDATE/" in rel_path
                    or "/APP_ANALYSIS/" in rel_path or "/KR_INPUT/" in rel_path)
        public_login = ("login_page" in lp or "login_auth.php" in lp
                        or "check_black_list_db.php" in lp)
        if DB_FILE and REQUIRE_LOGIN and php_like and not public_login and not _tl.uid:
            self._respond(401, json.dumps({"STATE": "ERROR", "CODE": "AUTH_REQUIRED",
                                           "ERROR_MESSAGE": "login required"}),
                          "application/json; charset=utf-8")
            return

        # --- get_app_file always local (even in proxy) ---
        if "get_app_file.php" in rel_path:
            code, text = offline_stub(rel_path, body_str)
            self._respond(code, text, "text/plain; charset=utf-8")
            return

        # --- admin panel (localhost-only; guarded by startup key) ---
        if rel_path == "/admin" or rel_path == "/admin/":
            if not self._is_direct_loopback():
                self._respond(403, "Forbidden", "text/plain; charset=utf-8")
                return
            supplied = parse_qs(urlparse(self.path).query).get("key", [""])[0]
            if not supplied or not secrets.compare_digest(supplied, ADMIN_KEY):
                self._respond(401, "Unauthorized", "text/plain; charset=utf-8")
                return
            self._respond(200, admin_page(), "text/html; charset=utf-8")
            return

        # --- HTML pages: rewrite localhost ---
        if fs_path.is_file() and fs_path.suffix.lower() in {".html",".htm"}:
            data = fs_path.read_bytes().decode("utf-8","replace")
            b = base_url()
            data = data.replace("https://game.busidol.com", b)
            data = data.replace("http://game.busidol.com", b)
            self._respond(200, data, "text/html; charset=utf-8")
            return

        # --- PHP endpoints ---
        if rel_path.endswith(".php") or "/APP_VALIDATE/" in rel_path or "/APP_ANALYSIS/" in rel_path or "/KR_INPUT/" in rel_path:
            if MODE == "proxy":
                try:
                    status, hdrs, data = proxy_forward(method, rel_path, body_bytes, self.headers)
                    text = data.decode("utf-8","replace") if data else ""
                    text = rewrite_body(text)
                    save_capture(rel_path, method, status, hdrs, text)
                    ct = hdrs.get("Content-Type","text/plain")
                    self._respond(status, text, ct)
                    LOG.info("  -> proxy %d %dbytes", status, len(text))
                except Exception:
                    traceback.print_exc()
                    self._respond(502, "proxy error", "text/plain")
                return
            # offline mode: try stub first, then capture for unhandled endpoints
            code, text = offline_stub(rel_path, body_str)
            if text != "{}" or "cnm_insert_new_user_to_server.php" in rel_path:
                ct = "text/html; charset=utf-8" if "login_page" in rel_path.lower() else "text/plain; charset=utf-8"
                self._respond(code, text, ct)
                LOG.info("  -> stub %dbytes", len(text))
                return
            cap = load_capture(rel_path)
            if cap:
                text = cap.get("body","{}")
                b = base_url()
                text = text.replace("https://game.busidol.com", b)
                text = text.replace("http://game.busidol.com", b)
                text = text.replace("http://localhost:8023", b)
                self._respond(200, text, "text/plain; charset=utf-8")
                LOG.info("  -> replay(capture) %dbytes", len(text))
                return
            self._respond(code, text, "text/plain; charset=utf-8")
            LOG.info("  -> stub %dbytes", len(text))
            return

        # unknown path
        self._respond(404, "", "text/plain")

    def _respond(self, code, body, ct="text/plain; charset=utf-8"):
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        cookie = getattr(_tl, "set_cookie", None)
        if cookie:
            value = (f"dol_session={cookie}; Path=/; Max-Age={AUTH_SESSION_TTL}; "
                     "HttpOnly; SameSite=Lax")
            if getattr(_tl, "scheme", "http") == "https":
                value += "; Secure"
            self.send_header("Set-Cookie", value)
            _tl.set_cookie = None
        self.end_headers()
        self.wfile.write(data)


class AdminHandler(Handler):
    """Local-only listener: expose Admin Control and nothing from the game."""

    admin_control_only = True

# ---------- main ----------

def _proj_path(v):
    """Anchor a relative CLI path to the project dir, so the server always
    reads/writes the same files no matter which cwd launched it."""
    p = Path(v)
    return p if p.is_absolute() else BASE_DIR / p


def main():
    global MODE, CAP_DIR, SAVE_FILE, UNIQ_ID, DB_FILE, DB_CONN, REQUIRE_LOGIN, WIRE_IDENTITY
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline","proxy"], default="proxy")
    ap.add_argument("--port", type=int, default=8029)
    ap.add_argument("--admin-port", type=int, default=None,
                help="start Admin Control on 127.0.0.1 at this separate port")
    ap.add_argument("--host", default="127.0.0.1",
                help="bind address; use 0.0.0.0 so friends can reach the "
                      "server over LAN/internet.")
    ap.add_argument("--capture", default=str(CAP_DIR))
    ap.add_argument("--save-file", default=str(BASE_DIR / "offline_save.json"),
                help="which save file this instance reads/writes; lets several "
                      "instances run side-by-side, one account each.")
    ap.add_argument("--uniq-id", default="ELDORADO_OFFLINE_0001",
                help="account id returned by check_black_list_db; should match "
                      "the USER_NAME (and DATA1 field 0) in --save-file.")
    ap.add_argument("--log", default=str(BASE_DIR / "serve.log"),
                help="per-instance log file (default serve.log).")
    ap.add_argument("--db", default=None,
                help="SQLite database path for multi-account saves (e.g. "
                      "busidol.db). When set, every request's HOST_ID/UNIQ_ID "
                      "routes to its own save row; --add-user creates accounts.")
    ap.add_argument("--require-login", action="store_true",
                help="with --db, only accounts created by --add-user can "
                      "enter; unknown ids get blocked at check_black_list_db.")
    ap.add_argument("--wire-identity", action="store_true",
                help="with --db, run a request as the account named by its "
                      "wire HOST_ID/UNIQ_ID when that account exists, instead "
                      "of the browser-cookie session. Lets one browser profile "
                      "play several accounts in separate windows; unsafe on any "
                      "server reachable from outside this machine.")
    ap.add_argument("--add-user", default=None, metavar="ACCOUNT",
                help="create/update an account in --db and exit. Use with "
                      "--add-pass (and --db).")
    ap.add_argument("--add-pass", default=None, metavar="PASSWORD",
                help="password for --add-user.")
    args = ap.parse_args()

    if args.admin_port == args.port:
        ap.error("--admin-port must differ from --port")

    args.capture   = str(_proj_path(args.capture))
    args.save_file = str(_proj_path(args.save_file))
    args.log       = str(_proj_path(args.log))
    if args.db:
        args.db    = str(_proj_path(args.db))

    if args.db:
        init_db(args.db)
        if args.add_user:
            if not args.add_pass:
                print("ERROR: --add-user requires --add-pass")
                sys.exit(2)
            add_account(args.add_user, args.add_pass)
            print(f"Account '{args.add_user}' created/updated in {args.db}")
            return
    elif args.add_user:
        print("ERROR: --add-user requires --db <file>")
        sys.exit(2)
    if args.require_login and not args.db:
        print("ERROR: --require-login requires --db <file>")
        sys.exit(2)
    if args.wire_identity and not args.db:
        print("ERROR: --wire-identity requires --db <file>")
        sys.exit(2)

    MODE = args.mode
    global SRV_PORT
    SRV_PORT = args.port
    REQUIRE_LOGIN = args.require_login
    WIRE_IDENTITY = args.wire_identity
    CAP_DIR = Path(args.capture)
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_FILE = Path(args.save_file)
    UNIQ_ID = args.uniq_id
    for h in list(LOG.handlers):
        LOG.removeHandler(h)
    fh2  = logging.FileHandler(args.log, encoding="utf-8", delay=True)
    fh2.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(fh2)
    game_server = None
    admin_server = None
    admin_thread = None
    try:
        game_server = ThreadingHTTPServer((args.host, args.port), Handler)
        if args.admin_port is not None:
            admin_server = ThreadingHTTPServer(
                ("127.0.0.1", args.admin_port), AdminHandler
            )
            admin_thread = threading.Thread(
                target=admin_server.serve_forever,
                name="busidol-admin-control",
                daemon=True,
            )
            admin_thread.start()

        if args.db:
            print(f"  DB      : {args.db}  (multi-account)"
                  + (", login required" if REQUIRE_LOGIN else "")
                  + (", wire identity" if WIRE_IDENTITY else ""))
        print(f"  Save    : {SAVE_FILE}")
        print(f"  UniQ ID : {UNIQ_ID}")
        print(f"  Static  : {WEB_ROOT}")
        print(f"  Capture : {CAP_DIR}")
        shown_host = args.host if args.host != "0.0.0.0" else "localhost"
        print(f"  GAME BOOT: http://{shown_host}:{args.port}/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0")
        if args.db and REQUIRE_LOGIN:
            print(f"  GAME LOGIN: http://{shown_host}:{args.port}/ELDORADO_WEB/login_page.php")
        if args.admin_port is not None:
            print(f"  ADMIN CONTROL: http://127.0.0.1:{args.admin_port}/admin-control")
        print("Ctrl+C to stop")
        game_server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if admin_server is not None:
            admin_server.shutdown()
            admin_server.server_close()
        if admin_thread is not None:
            admin_thread.join(timeout=5)
        if game_server is not None:
            game_server.server_close()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ELDORADO offline / proxy-capture server.
Usage:  python serve.py [--mode offline|proxy] [--port 8029] [--capture DIR]
"""
import argparse, io, json, logging, math, os, re, secrets, sqlite3, sys, threading, time, traceback, hashlib, datetime
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, quote as urlquote, unquote
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent
WEB_ROOT  = BASE_DIR / "ELDORADO_WEB"
CAP_DIR   = BASE_DIR / "capture"
LIVE_HOST = "https://game.busidol.com"
SRV_PORT = 8029  # set from --port in main(); kept dynamic so HTML/handler
                # rewrites point at the SAME port this server actually binds.
UNIQ_ID = "ELDORADO_OFFLINE_0001"  # account id returned by check_black_list_db
                                    # stub; override per instance via --uniq-id

# Multi-account / multi-user mode (--db busidol.db):
#   DB_FILE  != None  -> saves are routed per-request by the HOST_ID /
#                        UNIQ_ID the client posts, stored in SQLite keyed by
#                        that account id. If REQUIRE_LOGIN is on, only ids in
#                        the accounts table are served (access via the login
#                        page / login_login_page.php first).
DB_FILE = None
DB_CONN = None
REQUIRE_LOGIN = False
ADMIN_KEY = secrets.token_hex(4)  # shown at boot; /admin?key=... grants the panel
# ThreadingHTTPServer gives every request its OWN thread, so thread-local is a
# safe per-request scratchpad for "which account is talking" (set in _handle)
# and "what Host header did they use" (drives base-url rewriting over the net).
_tl = threading.local()

TODAY = time.strftime("%Y-%m-%d")
NOW_EPOCH = str(int(time.time() * 1000))

STATIC_EXT = {".js",".css",".png",".jpg",".jpeg",".gif",".svg",".ico",
              ".woff",".woff2",".ttf",".otf",".eot",
              ".mp3",".wav",".ogg",".m4a",
              ".webp",".bmp",".fnt",".xml",".plist",".atlas",".bin"}

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
    with SAVE_LOCK:
        try:
            SAVE_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
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
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, pw_hash TEXT)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS saves (id TEXT PRIMARY KEY, payload TEXT)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS sky_sessions (nonce TEXT PRIMARY KEY, user_id TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL)")
        DB_CONN.execute("CREATE TABLE IF NOT EXISTS sky_leaderboard (user_id TEXT PRIMARY KEY, clear_wave INTEGER NOT NULL DEFAULT 0, achieved_at INTEGER NOT NULL)")
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

def _uid() -> str:
    """Account id of the CURRENT request (thread-local), set in _handle from
    the posted HOST_ID / UNIQ_ID. Falls back to the instance default."""
    uid = getattr(_tl, "uid", None)
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

# ---------- mailbox (reward mail) ----------
# The live server delivers special/gift rewards on the USER's reward mail.
# Fully offline nobody ever sends one, so this server creates small local
# daily/attendance mails; claiming credits the account just like the real
# server would (persisted to the save file).

MAILBOX_GIFTS = (("GOLD", "1000000"), ("RUBY", "500"), ("BP", "200"))

# ---------- ToolShop currency conversion ----------
# The Tower/Cloud Garden/Evolve-9 modes that normally pay out Cloud Piece and
# Celestial Essence are unreachable offline, so a small server-side exchange
# lets the player turn farmable gold into the mode-locked currencies.
# CONVERT_RATES[(from, to)] = (cost_units_of_from, gain_units_of_to).
# The player SPENDS COUNT units of `from`, gains floor(COUNT*gain/cost) of `to`
# (the leftover is never consumed).
# Full conversion matrix: every currency pair (from, to) among the five
# currencies. Rates are derived from a common gold-value table so all pairs
# stay coherent, then the long-standing pairs below are grafted back verbatim
# (the player is used to those numbers). cost = units of FROM spent, gain =
# units of TO received (COUNT*FROM -> floor(COUNT*gain/cost) of TO).
_CUR_VALUE = {"GOLD": 1, "RUBY": 2000, "BP": 20000, "CLOUD": 10000, "ESSENCE": 10000}
CONVERT_RATES = {}
for _a in _CUR_VALUE:
    for _b in _CUR_VALUE:
        if _a == _b:
            continue
        _g = math.gcd(_CUR_VALUE[_a], _CUR_VALUE[_b])
        CONVERT_RATES[(_a, _b)] = (_CUR_VALUE[_b] // _g, _CUR_VALUE[_a] // _g)
del _a, _b, _g
CONVERT_RATES.update({
    ("GOLD", "BP"):      (120000, 5),
    ("RUBY", "BP"):      (500, 50),
    ("GOLD", "CLOUD"):   (120000, 12),
    ("GOLD", "ESSENCE"): (100000, 10),
    ("BP", "RUBY"):      (100, 5000),
    ("BP", "GOLD"):      (100, 2000000),
})

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
    ("GOLD", 250000), ("BP", 20), ("STICKET", 1), ("RUBY", 500), ("CLOUD", 5),
    ("GOLD", 500000), ("GTICKET", 1), ("ESSENCE", 5), ("RUBY", 750), ("STICKET", 2),
    ("BP", 50), ("CLOUD", 8), ("GOLD", 1000000), ("GTICKET", 2), ("RUBY", 1000),
    ("ESSENCE", 8), ("STICKET", 2), ("BP", 80), ("CLOUD", 10), ("RUBY", 1500),
    ("GOLD", 1500000), ("GTICKET", 3), ("BP", 100), ("STICKET", 3), ("ESSENCE", 10),
    ("CLOUD", 15), ("RUBY", 2000), ("GTICKET", 3), ("GOLD", 2500000), ("RUBY", 4000),
    ("RUBY", 5000),
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

GIFT_MULT = 1  # set from --gift-mult in main(); applied when POSTING the daily
               # mail so the WHAT_VALUE the client reads is already multiplied.
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

# One-time offline welcome batch, seeded by the server itself (not via the
# client's put_reward_char) so the mailbox always has something to claim.
# Seeded once per stamp; after the player claims the mails they are gone for
# good (never respawned) so nothing can be farmed.
OFFLINE_GIFT_STAMP = "20260921"
OFFLINE_GIFT_CHARS = (96, 97, 99)

def mailbox_ensure_offline_gift(s: dict) -> list:
    """Seed the one-time OFFLINE GIFT batch into save['mails']."""
    mails = s.get("mails") or []
    if s.get("offline_gift_sent") == OFFLINE_GIFT_STAMP:
        return mails
    s["offline_gift_sent"] = OFFLINE_GIFT_STAMP
    gifts = [
        ("GOLD", "200000", "OFFLINE GIFT"),
        ("RUBY", "500", "OFFLINE GIFT"),
        ("BP", "1500", "OFFLINE GIFT"),
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
                          "what_value": str(int(val) * GIFT_MULT)})
        s["mails"] = mails
        store_save(s)
        LOG.info("  mailbox: posted %d daily gift mail(s), gift-mult=%s",
                 len(MAILBOX_GIFTS), GIFT_MULT)
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
        f"<p style=color:#7ea no>Key:  <code>{esc(ADMIN_KEY)}</code>   |   {len(chars)} account(s)</p>",
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

def offline_stub(rel_path, body_str: str) -> tuple[int, str]:
    """Return (status_code, response_text) for known PHP stubs."""
    lp = rel_path.lower()
    if "get_app_file.php" in lp:
        stub = (
            f"{base_url()}/ELDORADO_WEB/javascript_min/aes.js?13"
            f"|{base_url()}/ELDORADO_WEB/pwsmart.1.3.js?13"
            f"|{base_url()}/ELDORADO_WEB/GoogleAnalytics/google_analytics.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_leveling/define_glo_20241205.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js?13"
            f"|{base_url()}/ELDORADO_WEB/javascript_min/ovr_gold_x5.js?13"
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
            _tl.set_cookie = acc
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
        # Auto-battle pass: paid feature, repriced to 1000 BP per day
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
                need = 1000 * day
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
            "hard_mode": "0||0",
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
            "random_box_cnt":0,"monthly_package_list":[],"hero_list":[],
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
        # the very first stage. Seed a full-unlock value when absent so both
        # hard map AND normal stage 201+ (stage201_in_check) open up.
        hard = str(load_save().get("hard_mode", "") or "").strip()
        if "||" not in hard:
            hard = "201||0,0,0,0,0,0,0,0,0,0"
            mutate_save(lambda s: s.__setitem__("hard_mode", hard))
            LOG.info("  hard mode seeded stage=201")
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
                    int(st)
                except ValueError:
                    st = ""
                if st:
                    def _save_hard(s):
                        s["hard_mode"] = f"{st}||{jw or '0,0,0,0,0,0,0,0,0,0'}"
                    mutate_save(_save_hard)
                    LOG.info("  hard mode saved stage=%s", st)
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
                item = str(body.get("ITEM", "") or "").strip()
                # ITEM_GACHA overflow: when the inventory is full the rolled
                # items never enter client STORAGE (add_item silently fails),
                # so they drop out of ITEM entirely. Mail the copies the client
                # clearly did not keep; the native mailbox claim readds them the
                # moment slots free up (client refuses the claim while full).
                mode = str(body.get("MODE", "") or "")
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
            # item-gacha draw passes RUBY = -price (+ any ruby won) and optional
            # GOLD / BP / CLOUD_PIECE as positive wins; apply all to the save so
            # after_ruby/after_gold (applied by the client) and the next
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
    if "update_guild_" in lp or "guild/" in lp:
        # Stub responses are read by S_MAINMENU guild switches:
        #   update_guild_act_get_guild_normal() auto-called on EVERY main
        #   menu init -> switch(n.result){case "ok": ... } -> a bare "{}"
        #   made n.result undefined -> default:utilNotice("Error - GGN e | "+...).
        #   check_guild_member()  (user clicks GUILD) ->
        #     switch(n.result){case "no_guild": ...S_GUILD_ENTER... }
        # Returning "ok"/"no_guild" keeps both switches out of the error
        # popups and lets the guild-enter screen open offline.
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
        # FAIL. cost_num stays 0 (cnm_exist never sends DRAGON_NEED_CLOUD).
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
                    # cost is 0 offline (DRAGON_NEED_CLOUD never sent), so battles
                    # are free and always fill the gauge.
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
                                  "lang": 2, "team": od1[14] if len(od1) > 14 else "1:2:3:4:5",
                                  "clear_wave": row["clear_wave"]})
                my_rank = next((i for i, row in enumerate(shared, 1) if row["user_id"] == _uid()), 0)
            else:
                ranks = [{"ranking": 1, "user_name": name, "platform": "WEB",
                          "level": lv, "lang": 2, "team": team,
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
                    team = d1[14] if len(d1) > 14 else "1:2:3:4:5"
                    ranks = [{"RANKING": 1, "NAME": name, "PLATFORM": "WEB",
                              "SCORE": best, "TEAM": team.replace(":", "||")}]
                    return 200, json.dumps({
                        "STATE": "SUCCESS",
                        "RANKING_ARR": ranks,
                        "MY_SCORE": str(best),
                        "MY_RANKING": "1",
                        "cur_ticket": str(cur_ticket),
                        "TODAY_LIMIT_TICKET": "3",
                        "ORDER_LIMIT": "50",
                        "ENTER_LIMIT_STAGE": str(s.get("cloud_enter_stage") or "1"),
                        "PLAY_LIMIT_TIME": "60",
                        "ENTER_RUBY": str(s.get("cloud_enter_ruby") or "100"),
                        "BOSS_AP_INFO": "0:0",
                        "CHAR_AP_INFO": "0:0:0:0:0:0",
                        "CHAR_AP_UP_NUM": "0",
                        "CHAR_AP_DOWN_NUM": "0",
                        "RANKING_PLAY_DATETIME": "20390101",
                        "RANKING_SHOW_DATETIME": today,
                        "RANKING_INIT_TIMESTAMP": "0",
                        "RANKING_PLAY_TIMESTAMP": "2200000000",
                        "RANKING_SHOW_TIMESTAMP": "0",
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
    # fallback
    return 200, "{}"

# ---------- HTTP handler ----------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        LOG.info("%s %s %s", time.strftime("%H:%M:%S"), self.command, self.path)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

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

        LOG.info("%s %s body=%d", method, rel_path, content_length)
        if body_bytes:
            LOG.info("  body: %s", body_str[:400].replace("\r"," ").replace("\n"," "))

        # Account routing: the client carries its identity as HOST_ID on most
        # calls and UNIQ_ID on check_black_list_db; both map to the same id.
        _tl.uid = ""
        for key in ("HOST_ID", "UNIQ_ID"):
            m = re.search(rf"(?:^|[&;]){re.escape(key)}=([^&;]*)", body_str)
            if m:
                v = unquote(m.group(1))
                if v and v.lower() != "null":
                    _tl.uid = v
                    break
        if not _tl.uid:
            q = urlparse(self.path).query
            for key in ("HOST_ID", "UNIQ_ID", "uid"):
                m = re.search(rf"(?:^|[&;]){re.escape(key)}=([^&;]*)", q or "")
                if m:
                    v = unquote(m.group(1))
                    if v and v.lower() != "null":
                        _tl.uid = v
                        break
        if not _tl.uid:
            # Reload/refresh: the client deletes eldorado_fb_temp_id at boot
            # so check_black_list posts UNIQ_ID=null. The login cookie keeps
            # the account identity so a refresh doesn't get BLACK_LIST (which
            # the GLO client renders as the "HACKING DETECTED" exit popup).
            m = re.search(r"(?:^|;\s*)dol_uid=([^;]*)",
                          self.headers.get("Cookie", ""))
            if m and m.group(1):
                v = unquote(m.group(1))
                if v and v.lower() != "null":
                    _tl.uid = v

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
            data = fetch_and_cache(rel_path)
            if data is None:
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

        # --- get_app_file always local (even in proxy) ---
        if "get_app_file.php" in rel_path:
            code, text = offline_stub(rel_path, body_str)
            self._respond(code, text, "text/plain; charset=utf-8")
            return

        # --- admin panel (localhost-only; guarded by startup key) ---
        if rel_path == "/admin" or rel_path == "/admin/":
            q = urlparse(self.path).query
            allowed = False
            try:
                allowed = _tl.host.split(":")[0] in {"localhost", "127.0.0.1"}
            except Exception:
                pass
            if not allowed:
                self._respond(403, "truy cap tu 192.168.x/lan hoac tunnel bi tu choi; vao tu may chinh: http://localhost:8029/admin", "text/plain; charset=utf-8")
                return
            if q != f"key={ADMIN_KEY}" and not q.startswith(f"key={ADMIN_KEY}&"):
                self._respond(401, 'Sai key. Dung: http://localhost:8029/admin?key=' + ADMIN_KEY, "text/plain; charset=utf-8")
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
            self.send_header("Set-Cookie",
                             f"dol_uid={cookie}; Path=/; Max-Age=34560000; "
                             "SameSite=Lax")
            _tl.set_cookie = None
        self.end_headers()
        self.wfile.write(data)

# ---------- main ----------

def _proj_path(v):
    """Anchor a relative CLI path to the project dir, so the server always
    reads/writes the same files no matter which cwd launched it."""
    p = Path(v)
    return p if p.is_absolute() else BASE_DIR / p


def main():
    global MODE, CAP_DIR, SAVE_FILE, UNIQ_ID, DB_FILE, DB_CONN, REQUIRE_LOGIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline","proxy"], default="proxy")
    ap.add_argument("--port", type=int, default=8029)
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
    ap.add_argument("--gift-mult", type=int, default=1, choices=[1, 5, 10],
                help="multiply the daily-mail gift values (gold/ruby/bp/cloud). " 
                      "Client reads WHAT_VALUE and adds the SAME number it " 
                      "credits server-side, so the boost persists across " 
                      "reloads (never reverts). 1/5/10.")
    ap.add_argument("--db", default=None,
                help="SQLite database path for multi-account saves (e.g. "
                      "busidol.db). When set, every request's HOST_ID/UNIQ_ID "
                      "routes to its own save row; --add-user creates accounts.")
    ap.add_argument("--require-login", action="store_true",
                help="with --db, only accounts created by --add-user can "
                      "enter; unknown ids get blocked at check_black_list_db.")
    ap.add_argument("--add-user", default=None, metavar="ACCOUNT",
                help="create/update an account in --db and exit. Use with "
                      "--add-pass (and --db).")
    ap.add_argument("--add-pass", default=None, metavar="PASSWORD",
                help="password for --add-user.")
    args = ap.parse_args()

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

    MODE = args.mode
    global SRV_PORT
    SRV_PORT = args.port
    REQUIRE_LOGIN = args.require_login
    CAP_DIR = Path(args.capture)
    CAP_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_FILE = Path(args.save_file)
    UNIQ_ID = args.uniq_id
    for h in list(LOG.handlers):
        LOG.removeHandler(h)
    fh2  = logging.FileHandler(args.log, encoding="utf-8", delay=True)
    fh2.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(fh2)
    global GIFT_MULT
    GIFT_MULT = args.gift_mult
    if args.db:
        print(f"  DB      : {args.db}  (multi-account)"
              + (", login required" if REQUIRE_LOGIN else ""))
    print(f"  Save    : {SAVE_FILE}")
    print(f"  UniQ ID : {UNIQ_ID}")
    print(f"  Static : {WEB_ROOT}")
    print(f"  Capture: {CAP_DIR}")
    print(f"  Admin  : http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/admin?key={ADMIN_KEY}")
    print(f"  Boot URL: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0")
    if args.db and REQUIRE_LOGIN:
        print(f"  Login  : http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/ELDORADO_WEB/login_page.php")
    print("Ctrl+C to stop")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()

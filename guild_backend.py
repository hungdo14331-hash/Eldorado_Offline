"""
BUSIDOL Guild backend — core + Guild War + Guild Boss + Guild Shop
================================================================

Server-side cho guild thường, Guild War (`update_guild_battle.php`), Guild
Boss (`update_guild_boss.php`) và Guild Shop (`update_guild_shop.php`).
**Không** phải World Boss 2026 (`boss_2026/*.php`, đã làm trong serve.py).

Hợp đồng wire (đã đối chiếu từ `eldorado_all_20260915.min.js`, không đoán):
- Endpoint `SERVER_URL + "Guild/update_guild_inter.php"`,
  `update_guild_main.php`, `update_guild_battle.php` (Guild War),
  `update_guild_boss.php` (Guild Boss), `update_guild_shop.php` (Guild Shop).
  Guild War/Boss/Shop có bảng act riêng (`_ACT_BATTLE`, `_ACT_BOSS`,
  `_ACT_SHOP`) vì act trùng tên với act guild thường sẽ gọi nhầm handler.
- Mọi act đi qua `ServerConnection.update_guild(data, type, cb)`; `act` nằm
  trong `data`. Server tự gắn `HOST_ID/USER_NAME/user_level/language/
  profile_num/VER_DATE` vào request.
- BẪY 1: `success_fn` coi body thô chứa chuỗi "error" là lỗi mạng và return
  sớm. **Không response nào được chứa "error".**
- BẪY 2: `result:"CGM_NO_GUILD"` bị transport bắt: client đá về main menu kèm
  `TXT.guild_kick`. Chỉ trả khi người chơi thật sự bị kick khỏi guild.
- BẪY 3: `insert_new_guild` / `update_member_donate` / `guild_add_max_member`:
  **client tự trừ ruby/vàng/cloud sau khi server trả `ok`** (qua
  `glo.fun.set_ruby_gold`). Server chỉ kiểm tra đủ không, TUYỆT ĐỐI không trừ
  lần hai — trừ hai lần là mất gấp đôi.
- BẪY 4: `guild_type` gửi lên là **string** ("free"/"approve") nhưng đọc về
  là **số** (`guild_type==1` → free). Module này tự quy đổi.
- BẪY 5: `season_data` không có guard ở client; thiếu field là màn trắng.
- BẪY 6: `get_member_list`/`get_approve_list` cần `cur_member`+`max_member` ở
  **top-level** (khác `guild_cur_member`/`guild_max_member` trong `guild_data`).
- BẪY 7: `update_guild_member` trả `guild_data`+`member_data` ở **top-level**,
  không phải trong `data`.
- BẪY 8: client rate-limit 500ms theo cặp `type:act` — không phải lỗi server.
- BẪY 9 (Guild War): `get_battle_normal` trả payload **thẳng** ở top-level, còn
  `update_deck_defence`/`update_deck_attack` trả nó trong `guild_battle_normal`.
  `update_guild_battle_result` trả **lồng** `result.result`. Sai một tầng là
  client rơi vào `default` -> popup lỗi.
- BẪY 10 (Guild War): `clear_guild_list`, `week_rank`, `attack_success`,
  `defence_fail`, member history là mảng **1-based** (phần tử 0 rỗng, client
  `for(1..length)`); Guild Boss `ranking`/`get_help.data` là mảng **0-based**.
  `deck30` là **object** khoá "1".."30", không phải mảng.
- BẪY 11 (Guild War): client tự trừ `USER.cloud_piece -= 30` khi gọi
  `next_guild_matching_cloud30` mà không báo server — server phải trừ cho khớp.
- BẪY 12 (Guild Boss): `report_damage` nhận `damage_mult` là **float**
  (0.001 bản release, 10 bản TEST). Ép int trước khi nhân là sát thương = 0.

State nằm trong SQLite (cùng file với `saves`), không đụng save_lock/session
của serve.py. Bất biến "mỗi người ở tối đa 1 guild" và "tên guild là duy nhất"
được chặn bằng PRIMARY KEY, không bằng if trong code.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from urllib.parse import parse_qsl, urlsplit

# --- luật chơi (người dùng chốt 2026-09-27) --------------------------------
GUILD_TYPE_FREE = 1
GUILD_TYPE_APPROVE = 2
GUILD_BASE_MAX_MEMBER = 20      # số slot khi tạo guild
GUILD_ADD_MEMBER_RUBY = 500     # giá mua thêm 1 slot (client tự trừ)
GUILD_APPROVE_MAX = 5           # khớp client S_GUILD_JOIN.approve_max_cnt
GUILD_BUFF_MAX_LEVEL = 5        # khớp guard client (guild_buff_level >= 5)
GUILD_CREATE_MIN_LEVEL = 30     # client đã chặn trước, server kiểm lại

# server quyết định, client chỉ hiển thị "long"/"str_not_allowed"
GUILD_NAME_MAX = 12
# client tự chặn trước khi gọi (S_GUILD_CREATE.guild_name_min_length = 4)
GUILD_NAME_MIN = 4
GUILD_NOTICE_MAX = 70           # khớp client S_GUILD_SETTING_MENU.notice_max_length
GUILD_CHAT_MAX = 70             # khớp client
GUILD_CHAT_KEEP = 50            # số dòng chat giữ lại mỗi guild
# 4 nhiệm vụ guild, đúng thứ tự S_GUILD_MAIN_MISSION của client
GUILD_MISSIONS = (("attendance", 10), ("dungeon", 5), ("pvp", 5), ("cloud_garden", 5))
# Thang buff: index = level hiện tại. price[L] = giá nâng L -> L+1.
GUILD_BUFF_PRICE = (0, 100000, 200000, 400000, 800000, 1600000)
GUILD_BUFF_VALUE = (0, 5, 12, 22, 35, 50)

# Donate: act_detail -> (key, tên tài nguyên, quy mô quyên góp, vàng guild)
# S_GUILD_DONATE_VALUE / _CONTRIBUTE_VALUE / _GOLDBAR_VALUE của client.
GUILD_DONATE = {
    "CLOUD": ("cloud", "cloud_piece", 50, 20),
    "RUBY": ("ruby", "ruby", 20, 8),
    "GOLD": ("gold", "gold", 10, 4),
}

# --- Guild Shop (update_guild_shop.php) -------------------------------------
# Client S_GUILD_SHOP.CARDS hardcode 4 card, KHONG co endpoint nao de server
# doi danh sach -> server tu chon `type_num` cho card 1/2 (hero).
# Client gui `price`/`times` chi de hien thi, khong duoc tin.
GUILD_SHOP_CARD = {26: (1, 4000), 27: (10, 40000)}
# Client S_POPUP_GACHA_RESULT.preload chi tai co_item16/26/36/46.png, va
# `et(n)` lai tra "co_item" + floor(item_num/10) -> item_num phai co tens
# digit 6. Item gia cap o 15x/16x/17x thi icon trong. Fix grade 6.
GUILD_SHOP_GRADE = 6
# Card 1/2 (hero gacha): client cho `char_reward` = 0 va gui `type_num` bang
# `POPUP_HEROES[i].type_num_1` / `.type_num_10`, gia tri do SERVER cap qua
# `hero_list` (serve.py). `refresh_popup_heroes` tu suy
# `type_num_10 = type_num_1 + 1` khi hero chi co 1 entry -> chi can 1 entry.
# Dung cong thuc de khoi phai bang 114*2 dong:
#   type_num_1  = GUILD_SHOP_HERO_BASE + char_num*2
#   type_num_10 = type_num_1 + 1
GUILD_SHOP_HERO_BASE = 1000
GUILD_SHOP_HERO_PRICE = (4000, 40000)   # index theo times == 10
GUILD_SHOP_HERO_MAX = 114          # DEFINE_CHAR char_num 1..114, khop co_ch<n>.png


def _shop_hero_type_num(char_num: int, times: int) -> int:
    """type_num server cap cho `hero_list` -> client gui nguoc len khi mua."""
    return GUILD_SHOP_HERO_BASE + char_num * 2 + (1 if times >= 10 else 0)


def _shop_hero_spec(type_num: int):
    """type_num -> (times, price, char_num) cho card hero, None neu la item card."""
    off = type_num - GUILD_SHOP_HERO_BASE
    if off < 2 or off > GUILD_SHOP_HERO_MAX * 2 + 1:
        return None
    char_num, ten = off // 2, off % 2
    return (10 if ten else 1), GUILD_SHOP_HERO_PRICE[ten], char_num


_GUILD_NAME_BAD = set('<>&"\'/\\@#$%^*+=~`^{}|;:,.<>?()[]\t\r\n')


# --- wire helpers ----------------------------------------------------------
def _res(payload: dict) -> tuple[int, str]:
    return 200, json.dumps(payload, ensure_ascii=False)


def _body_json_obj(body_str: str) -> dict:
    """Client post `json_obj` (object khi ENABLE_CRYPT, chuỗi JSON khi tắt).
    Client luôn gửi content-type x-www-form-urlencoded, nên phải URL-decode
    giá trị trước khi json.loads — parse_qsl của stdlib lo phần này."""
    body_str = body_str or ""
    outer = None
    try:
        outer = json.loads(body_str)
    except Exception:
        try:
            outer = dict(parse_qsl(body_str, keep_blank_values=True))
        except Exception:
            outer = None
    if not isinstance(outer, dict):
        return {}
    v = outer.get("json_obj")
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            got = json.loads(v)
            return got if isinstance(got, dict) else {}
        except Exception:
            return {}
    return {}


def _as_int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _int_or_zero(v, default=0) -> int:
    return _as_int(v, default)


def _as_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _season_data() -> dict:
    """Mùa 1, mở vô thời hạn. Client đọc season_num/season_start_date/
    season_end_date không có guard nào."""
    return {"season_num": 1, "season_start_date": "2026-01-01",
            "season_end_date": "2099-12-31"}


# --- db --------------------------------------------------------------------
def init_db(db_conn, save_lock):
    with save_lock:
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guilds (guild_name TEXT PRIMARY KEY, "
            "guild_type INTEGER NOT NULL DEFAULT 1, flag_img TEXT NOT NULL DEFAULT '', "
            "symbol_img TEXT NOT NULL DEFAULT '', notice TEXT NOT NULL DEFAULT '', "
            "max_member INTEGER NOT NULL DEFAULT 20, money INTEGER NOT NULL DEFAULT 0, "
            "buff_level INTEGER NOT NULL DEFAULT 0, master_id TEXT NOT NULL DEFAULT '', "
            "season_score INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL DEFAULT 0)")
        # user_id là PRIMARY KEY: một người tối đa một guild, chặn ở tầng DB.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_members (user_id TEXT PRIMARY KEY, "
            "guild_name TEXT NOT NULL, user_name TEXT NOT NULL DEFAULT '', "
            "platform TEXT NOT NULL DEFAULT 'WEB', user_level INTEGER NOT NULL DEFAULT 1, "
            "profile_num INTEGER NOT NULL DEFAULT 1, is_master INTEGER NOT NULL DEFAULT 0, "
            "season_score INTEGER NOT NULL DEFAULT 0, gold_bar INTEGER NOT NULL DEFAULT 0, "
            "mission_data TEXT NOT NULL DEFAULT '{}', donate_day TEXT NOT NULL DEFAULT '', "
            "donate_data TEXT NOT NULL DEFAULT '{}', joined_at INTEGER NOT NULL DEFAULT 0, "
            "last_attendance INTEGER NOT NULL DEFAULT 0)")
        db_conn.execute(
            "CREATE INDEX IF NOT EXISTS guild_members_guild ON guild_members (guild_name, joined_at)")
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_applies (guild_name TEXT NOT NULL, "
            "user_id TEXT NOT NULL, user_name TEXT NOT NULL DEFAULT '', "
            "platform TEXT NOT NULL DEFAULT 'WEB', user_level INTEGER NOT NULL DEFAULT 1, "
            "profile_num INTEGER NOT NULL DEFAULT 1, member_no INTEGER NOT NULL DEFAULT 0, "
            "created_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (guild_name, user_id))")
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "guild_name TEXT NOT NULL, host_id TEXT NOT NULL DEFAULT '', "
            "user_name TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT 'WEB', "
            "chat TEXT NOT NULL DEFAULT '', etc TEXT NOT NULL DEFAULT '', "
            "created_at INTEGER NOT NULL DEFAULT 0)")
        db_conn.execute(
            "CREATE INDEX IF NOT EXISTS guild_chat_guild ON guild_chat (guild_name, id)")
        # --- Guild War (update_guild_battle.php) ---
        # 1 dòng / guild / tuần: deck tấn công, điểm, đối thủ đã ghép.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_bt_guild (guild_name TEXT NOT NULL, "
            "week_key INTEGER NOT NULL, opponent TEXT NOT NULL DEFAULT '', "
            "deck_attack1 TEXT NOT NULL DEFAULT 'none', deck_attack2 TEXT NOT NULL DEFAULT 'none', "
            "deck_attack3 TEXT NOT NULL DEFAULT 'none', score INTEGER NOT NULL DEFAULT 0, "
            "updated_at INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (guild_name, week_key))")
        # 30 ô phòng thủ. Mỗi thành viên tự đặt 1 deck -> 1 dòng.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_bt_slot (week_key INTEGER NOT NULL, "
            "guild_name TEXT NOT NULL, slot INTEGER NOT NULL, host_id TEXT NOT NULL DEFAULT '', "
            "user_name TEXT NOT NULL DEFAULT '', user_info TEXT NOT NULL DEFAULT '', "
            "deck TEXT NOT NULL DEFAULT '', platform TEXT NOT NULL DEFAULT 'WEB', "
            "clear_status TEXT NOT NULL DEFAULT '', who_clear TEXT NOT NULL DEFAULT '', "
            "who_ing TEXT NOT NULL DEFAULT '', who_fail TEXT NOT NULL DEFAULT '', "
            "who_clear_platform TEXT NOT NULL DEFAULT '', "
            "updated_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (week_key, guild_name, slot))")
        # Nhật ký trận: vừa làm lịch sử thành viên, vừa tính xếp hạng.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_bt_record (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "week_key INTEGER NOT NULL, my_guild_name TEXT NOT NULL, "
            "other_guild_name TEXT NOT NULL DEFAULT '', user_name TEXT NOT NULL DEFAULT '', "
            "host_id TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '', "
            "score INTEGER NOT NULL DEFAULT 0, deck_index INTEGER NOT NULL DEFAULT 0, "
            "kind TEXT NOT NULL DEFAULT 'battle', at INTEGER NOT NULL DEFAULT 0, "
            "other_slot INTEGER NOT NULL DEFAULT 0)")
        db_conn.execute(
            "CREATE INDEX IF NOT EXISTS guild_bt_record_week "
            "ON guild_bt_record (week_key, my_guild_name)")
        # other_slot là khoá idempotent của update_guild_battle_result: mỗi
        # (thành viên, ô đối phương, bộ deck) chỉ được tính một lần.
        if not any(r["name"] == "other_slot"
                   for r in _rows(db_conn, "PRAGMA table_info(guild_bt_record)")):
            db_conn.execute("ALTER TABLE guild_bt_record "
                            "ADD COLUMN other_slot INTEGER NOT NULL DEFAULT 0")
        # --- Guild Boss (update_guild_boss.php) ---
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_boss_stage (guild_name TEXT NOT NULL, "
            "week_key INTEGER NOT NULL, stage INTEGER NOT NULL, "
            "boss_no INTEGER NOT NULL DEFAULT 5, max_hp INTEGER NOT NULL DEFAULT 0, "
            "cur_hp INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (guild_name, week_key, stage))")
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_boss_damage (guild_name TEXT NOT NULL, "
            "week_key INTEGER NOT NULL, user_name TEXT NOT NULL, "
            "host_id TEXT NOT NULL DEFAULT '', user_chars TEXT NOT NULL DEFAULT '', "
            "total_damage INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (guild_name, week_key, user_name))")
        # Token lượt đánh: report_damage chỉ được ghi đúng một lần.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_boss_token (token TEXT PRIMARY KEY, "
            "guild_name TEXT NOT NULL, week_key INTEGER NOT NULL, user_id TEXT NOT NULL, "
            "user_name TEXT NOT NULL DEFAULT '', stage INTEGER NOT NULL DEFAULT 0, "
            "created_at INTEGER NOT NULL DEFAULT 0, used_at INTEGER)")
        # --- Guild Shop (update_guild_shop.php) ---
        # fp = type_num|times|slot|goldbar client gui len. Client gui lai nguyen
        # body khi timeout nen phai tra lai ket qua cu chu khong mua 2 lan.
        # `gold_bar_after` phai bang gold_bar hien tai moi coi la retry: neu
        # so du da doi (user kiem them tien roi mua tiep) thi do la don moi.
        db_conn.execute(
            "CREATE TABLE IF NOT EXISTS guild_shop_buy (user_id TEXT NOT NULL, "
            "fp TEXT NOT NULL, gold_bar_after INTEGER NOT NULL DEFAULT 0, "
            "created_at INTEGER NOT NULL DEFAULT 0, response TEXT NOT NULL DEFAULT '', "
            "PRIMARY KEY (user_id, fp))")
        db_conn.commit()


# --- db helpers ------------------------------------------------------------
# Đọc bằng cursor riêng có row_factory=sqlite3.Row để lấy `row["ten_cot"]`.
# KHÔNG set row_factory cho cả connection: serve.py dùng chung DB_CONN và đang
# truy cập row theo vị trí, đổi toàn cục là đổi hành vi của mọi feature khác.
def _rows(db, sql: str, args=()):
    cur = db.cursor()
    cur.row_factory = sqlite3.Row
    try:
        return cur.execute(sql, args).fetchall()
    finally:
        cur.close()


def _one(db, sql: str, args=()):
    got = _rows(db, sql, args)
    return got[0] if got else None


def _scalar(db, sql: str, args=()):
    cur = db.cursor()
    try:
        row = cur.execute(sql, args).fetchone()
        return row[0] if row else None
    finally:
        cur.close()


# --- reads -----------------------------------------------------------------
def _load_save_payload(db_conn, uid: str) -> dict:
    row = db_conn.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row[0])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _store_save_payload(db_conn, uid: str, data: dict):
    db_conn.execute("INSERT OR REPLACE INTO saves (id, payload) VALUES (?,?)",
                    (uid, json.dumps(data, ensure_ascii=False)))


def _guild(db_conn, name):
    if not name or name.lower() == "none":
        return None
    return _one(db_conn, "SELECT * FROM guilds WHERE guild_name=?", (name,))


def _member(db_conn, uid: str):
    return _one(db_conn, "SELECT * FROM guild_members WHERE user_id=?", (uid,))


def _member_count(db_conn, name) -> int:
    return int(_scalar(db_conn, "SELECT COUNT(*) FROM guild_members WHERE guild_name=?",
                       (name,)))


def _mission_default() -> dict:
    return {act: 0 for act, _ in GUILD_MISSIONS}


def _mission_of(row) -> dict:
    out = _mission_default()
    try:
        got = json.loads(row["mission_data"] or "{}")
        if isinstance(got, dict):
            for act, _ in GUILD_MISSIONS:
                out[act] = 1 if _as_int(got.get(act)) == 1 else 0
    except Exception:
        pass
    return out


def _donate_of(row, day_key: str) -> dict:
    """Phần donate hôm nay; reset theo ngày. Luôn trả object vì client đọc
    thẳng `.cloud/.ruby/.gold` — null là TypeError."""
    out = {"cloud": 0, "ruby": 0, "gold": 0}
    if (row["donate_day"] or "") == day_key:
        try:
            got = json.loads(row["donate_data"] or "{}")
            if isinstance(got, dict):
                for k in out:
                    out[k] = _int_or_zero(got.get(k))
        except Exception:
            pass
    return out


def _flag(g) -> dict:
    return {"flagImg": g["flag_img"] or "flag_red1.png",
            "symbolImg": g["symbol_img"] or "flagsymbol1.png"}


def _guild_data(db_conn, g, uid: str, day_key: str) -> dict:
    """Shape guild_data dùng chung cho mọi act. Phải đủ field — client đọc
    thẳng không guard, thiếu là màn trắng hoặc NaN."""
    name = g["guild_name"]
    lvl = min(_int_or_zero(g["buff_level"]), GUILD_BUFF_MAX_LEVEL)
    mine = _member(db_conn, uid)
    return {
        "guild_name": name,
        "guild_type": _int_or_zero(g["guild_type"]) or GUILD_TYPE_FREE,
        "guild_flag": _flag(g),
        "guild_notice": g["notice"] or "",
        "guild_money": _int_or_zero(g["money"]),
        "guild_buff_level": lvl,
        "guild_buff_value": GUILD_BUFF_VALUE[lvl],
        "guild_buff_next_price": GUILD_BUFF_PRICE[lvl],
        "guild_position": "MASTER" if (mine is not None and mine["is_master"]) else "MEMBER",
        "guild_cur_member": _member_count(db_conn, name),
        "guild_max_member": _int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER,
        "guild_next_max_member": (_int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER) + 1,
        "guild_add_member_ruby_value": GUILD_ADD_MEMBER_RUBY,
        "guild_season_score": _int_or_zero(g["season_score"]),
        "guild_master": _master_of(db_conn, g),
        "guild_data_mine": _mine_of(db_conn, mine, day_key),
    }


def _master_of(db_conn, g) -> dict:
    row = _one(db_conn, "SELECT user_name, platform, user_level FROM guild_members "
                        "WHERE user_id=?", (g["master_id"],))
    if row is None:
        return {"name": "", "platform": "WEB", "level": 1}
    return {"name": row["user_name"] or "", "platform": row["platform"] or "WEB",
            "level": _int_or_zero(row["user_level"]) or 1}


def _mine_of(db_conn, mine, day_key: str) -> dict:
    """`guild_data_mine` phải nằm trong `guild_data` vì hook json_secure đọc
    `obj.guild_data_mine.guild_gold_bar` để set `USER.goldbar`."""
    if mine is None:
        return {"guild_season_score": 0, "guild_gold_bar": 0,
                "guild_today_donate": {"cloud": 0, "ruby": 0, "gold": 0},
                "guild_today_ad_donate": "none"}
    return {
        "guild_season_score": _int_or_zero(mine["season_score"]),
        "guild_gold_bar": _int_or_zero(mine["gold_bar"]),
        "guild_today_donate": _donate_of(mine, day_key),
        "guild_today_ad_donate": "none",
    }


def _member_item(row, uid: str) -> dict:
    return {
        "is_mine": "yes" if row["user_id"] == uid else "no",
        "user_name": row["user_name"] or "",
        "platform": row["platform"] or "WEB",
        "user_level": _int_or_zero(row["user_level"]) or 1,
        "profile_num": _int_or_zero(row["profile_num"]) or 1,
        "season_score": _int_or_zero(row["season_score"]),
        "last_attendance": _int_or_zero(row["last_attendance"]),
    }


def _apply_item(row) -> dict:
    return {
        "user_name": row["user_name"] or "",
        "platform": row["platform"] or "WEB",
        "user_level": _int_or_zero(row["user_level"]) or 1,
        "profile_num": _int_or_zero(row["profile_num"]) or 1,
        "member_no": _int_or_zero(row["member_no"]),
    }


def _list_item(db_conn, g) -> dict:
    return {
        "guild_name": g["guild_name"],
        "guild_type": _int_or_zero(g["guild_type"]) or GUILD_TYPE_FREE,
        "guild_flag": _flag(g),
        "guild_cur_member": _member_count(db_conn, g["guild_name"]),
        "guild_max_member": _int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER,
        "guild_buff_level": _int_or_zero(g["buff_level"]),
        "guild_master": _master_of(db_conn, g),
    }


def _name_free(db_conn, name) -> bool:
    return _one(db_conn, "SELECT 1 FROM guilds WHERE lower(guild_name)=lower(?)",
                (name,)) is None


def _check_name(db_conn, name: str) -> str:
    """Trả result code cho check_guild_name. Không chặn độ dài tối thiểu: client
    tự chặn trước khi gọi nên không có case nào để trả."""
    if not name or any(ch in _GUILD_NAME_BAD for ch in name):
        return "str_not_allowed"
    if len(name) > GUILD_NAME_MAX:
        return "long"
    if not _name_free(db_conn, name):
        return "duplication"
    return "ok"


def _today() -> str:
    """Khoá ngày cho donate/attendance. Ngày server, không tin body."""
    return time.strftime("%Y%m%d", time.localtime())


# --- identity --------------------------------------------------------------
def _me(data: dict, uid: str) -> dict:
    """Thông tin người gọi. user_id LUÔN lấy từ session server, không tin body.
    user_name/user_level/profile_num là dữ liệu hiển thị nên lấy từ body
    (client tự gửi), platform không có trong body nên mặc định 'WEB'."""
    return {
        "user_id": uid,
        "user_name": str(data.get("USER_NAME") or "").strip(),
        "platform": str(data.get("platform") or "WEB").strip() or "WEB",
        "user_level": max(1, _as_int(data.get("user_level"), 1)),
        "profile_num": max(1, _as_int(data.get("profile_num"), 1)),
    }


def _ruby_of(save: dict) -> int:
    d1 = str(save.get("DATA1") or "").split(",")
    return _int_or_zero(d1[2]) if len(d1) > 2 else 0


def _wallet_of(save: dict, key: str) -> int:
    if key == "gold":
        d1 = str(save.get("DATA1") or "").split(",")
        return _int_or_zero(d1[1]) if len(d1) > 1 else 0
    if key == "ruby":
        return _ruby_of(save)
    return _int_or_zero(save.get(key))


def _mark_kicked(db_conn, uid: str, now: int):
    """Bẫy 2: client đọc CGM_NO_GUILD là bị kick. Cần dấu bên server vì bản ghi
    thành viên đã bị xoá. Cất trong save để khỏi thêm bảng."""
    data = _load_save_payload(db_conn, uid)
    if not data:
        return
    data["guild_kick_at"] = now
    _store_save_payload(db_conn, uid, data)


def _take_kick_mark(db_conn, uid: str) -> bool:
    """Đọc rồi xoá dấu kick, để thông báo chỉ hiện một lần."""
    data = _load_save_payload(db_conn, uid)
    if not data or not data.get("guild_kick_at"):
        return False
    data.pop("guild_kick_at", None)
    _store_save_payload(db_conn, uid, data)
    return True


# --- guild_inter -----------------------------------------------------------
def _act_check_guild_name(db, save, data, uid, day):
    return _res({"result": _check_name(db, str(data.get("guild_name") or "").strip())})


def _act_get_guild_normal(db, save, data, uid, day):
    """Chạy mỗi lần mở main menu. Phải trả data dạng OBJECT: chuỗi lạ sẽ rơi
    vào case đã mojibake và khoá nút Guild."""
    m = _member(db, uid)
    if m is None:
        if _take_kick_mark(db, uid):
            return _res({"result": "CGM_NO_GUILD"})
        return _res({"result": "ok", "data": "no_guild", "season_data": _season_data()})
    g = _guild(db, m["guild_name"])
    if g is None:
        return _res({"result": "ok", "data": "no_guild", "season_data": _season_data()})
    return _res({"result": "ok", "data": _guild_data(db, g, uid, day),
                 "season_data": _season_data()})


def _act_check_guild_member(db, save, data, uid, day):
    m = _member(db, uid)
    if m is None:
        _take_kick_mark(db, uid)
        return _res({"result": "no_guild", "exit_remain_time": None, "exit_time": 0,
                     "season_data": _season_data()})
    g = _guild(db, m["guild_name"])
    if g is None:
        return _res({"result": "no_guild", "exit_remain_time": None, "exit_time": 0,
                     "season_data": _season_data()})
    return _res({"result": "has_guild", "data": _guild_data(db, g, uid, day),
                 "season_data": _season_data()})


def _act_insert_new_guild(db, save, data, uid, day):
    me = _me(data, uid)
    if not me["user_name"]:
        return _res({"result": "no_user_name"})
    if me["user_level"] < GUILD_CREATE_MIN_LEVEL:
        # Client đã chặn dưới level 30 trước khi gọi, và switch của client không
        # có case riêng cho level -> dùng code gần nghĩa nhất.
        return _res({"result": "not_enough_ruby"})
    if _member(db, uid) is not None:
        return _res({"result": "already"})
    name = str(data.get("guild_name") or "").strip()
    verdict = _check_name(db, name)
    if verdict != "ok":
        return _res({"result": verdict})
    # BẪY 3: client tự trừ sau khi nhận "ok". Server chỉ chặn khi thiếu.
    if _ruby_of(save) < 3000:
        return _res({"result": "not_enough_ruby"})
    gtype = GUILD_TYPE_APPROVE if str(data.get("guild_type") or "") == "approve" else GUILD_TYPE_FREE
    flag = data.get("guild_flag") or {}
    if not isinstance(flag, dict):
        flag = {}
    now = int(time.time())
    db.execute("INSERT INTO guilds (guild_name,guild_type,flag_img,symbol_img,notice,"
               "max_member,money,buff_level,master_id,season_score,created_at) "
               "VALUES (?,?,?,?,'',?,0,0,?,0,?)",
               (name, gtype, str(flag.get("flagImg") or "flag_red1.png"),
                str(flag.get("symbolImg") or "flagsymbol1.png"),
                GUILD_BASE_MAX_MEMBER, uid, now))
    db.execute("INSERT INTO guild_members (user_id,guild_name,user_name,platform,user_level,"
               "profile_num,is_master,season_score,gold_bar,mission_data,donate_day,"
               "donate_data,joined_at,last_attendance) VALUES (?,?,?,?,?,?,1,0,0,'{}','','{}',?,?)",
               (uid, name, me["user_name"], me["platform"], me["user_level"],
                me["profile_num"], now, now))
    g = _guild(db, name)
    return _res({"result": "ok", "data": _guild_data(db, g, uid, day)})


def _act_get_guild_list(db, save, data, uid, day):
    sort = str(data.get("sort_type") or "default")
    search = str(data.get("search_str") or "").strip().lower()
    rows = _rows(db, "SELECT * FROM guilds")
    items = [_list_item(db, g) for g in rows]
    if search:
        items = [it for it in items if search in it["guild_name"].lower()]
    if sort == "open":
        items = [it for it in items if it["guild_type"] == GUILD_TYPE_FREE]
    elif sort == "approve":
        items = [it for it in items if it["guild_type"] == GUILD_TYPE_APPROVE]
    else:
        by_name = {g["guild_name"]: g for g in rows}
        if sort in ("default", "recent"):
            items.sort(key=lambda it: -_int_or_zero(by_name[it["guild_name"]]["created_at"]))
        elif sort == "fewest":
            items.sort(key=lambda it: (it["guild_cur_member"], it["guild_name"]))
        elif sort == "most":
            items.sort(key=lambda it: (-it["guild_cur_member"], it["guild_name"]))
        else:
            items.sort(key=lambda it: it["guild_name"])
    mine = _member(db, uid)
    approve_cnt = 0
    if mine is not None:
        approve_cnt = int(_scalar(db, "SELECT COUNT(*) FROM guild_applies WHERE guild_name=?",
                                  (mine["guild_name"],)))
    return _res({"result": "ok", "data": items, "my_approve_cnt": approve_cnt})


def _act_join_open_guild(db, save, data, uid, day):
    me = _me(data, uid)
    if not me["user_name"]:
        return _res({"result": "no_user_name"})
    if _member(db, uid) is not None:
        return _res({"result": "duplication"})
    g = _guild(db, str(data.get("guild_name") or ""))
    if g is None:
        return _res({"result": "no_user_name"})
    if _int_or_zero(g["guild_type"]) != GUILD_TYPE_FREE:
        return _res({"result": "not_yet"})
    if _member_count(db, g["guild_name"]) >= (_int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER):
        return _res({"result": "full"})
    now = int(time.time())
    db.execute("INSERT INTO guild_members (user_id,guild_name,user_name,platform,user_level,"
               "profile_num,is_master,season_score,gold_bar,mission_data,donate_day,"
               "donate_data,joined_at,last_attendance) VALUES (?,?,?,?,?,?,0,0,0,'{}','','{}',?,?)",
               (uid, g["guild_name"], me["user_name"], me["platform"], me["user_level"],
                me["profile_num"], now, now))
    return _res({"result": "ok", "data": _guild_data(db, g, uid, day)})


def _act_join_approve_guild(db, save, data, uid, day):
    me = _me(data, uid)
    if not me["user_name"]:
        return _res({"result": "no_user_name"})
    if _member(db, uid) is not None:
        return _res({"result": "duplication"})
    g = _guild(db, str(data.get("guild_name") or ""))
    if g is None:
        return _res({"result": "no_user_name"})
    if _member_count(db, g["guild_name"]) >= (_int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER):
        return _res({"result": "full"})
    name = g["guild_name"]
    if _one(db, "SELECT 1 FROM guild_applies WHERE guild_name=? AND user_id=?",
            (name, uid)) is not None:
        return _res({"result": "already"})
    cnt = int(_scalar(db, "SELECT COUNT(*) FROM guild_applies WHERE guild_name=?", (name,)))
    if cnt >= GUILD_APPROVE_MAX:
        return _res({"result": "over"})
    nxt = int(_scalar(db, "SELECT COALESCE(MAX(member_no),0) FROM guild_applies "
                          "WHERE guild_name=?", (name,))) + 1
    db.execute("INSERT OR REPLACE INTO guild_applies (guild_name,user_id,user_name,platform,"
               "user_level,profile_num,member_no,created_at) VALUES (?,?,?,?,?,?,?,?)",
               (name, uid, me["user_name"], me["platform"], me["user_level"],
                me["profile_num"], nxt, int(time.time())))
    return _res({"result": "ok", "my_approve_cnt": cnt + 1})


def _act_get_guild_season_ranking_data(db, save, data, uid, day):
    rows = _rows(db, "SELECT * FROM guilds")
    ranked = sorted(rows, key=lambda g: (-_int_or_zero(g["season_score"]), g["guild_name"]))
    board = [{"rank": i, "guild_name": g["guild_name"], "guild_flag": _flag(g),
              "season_score": _int_or_zero(g["season_score"])}
             for i, g in enumerate(ranked, 1)]
    mine = _member(db, uid)
    my = None
    if mine is not None:
        g = _guild(db, mine["guild_name"])
        if g is not None:
            for row in board:
                if row["guild_name"] == g["guild_name"]:
                    my = dict(row)
                    break
    return _res({"result": "ok", "data": {
        "guild_season_ranking_data": board,
        "my_guild_season_ranking_data": my}})


# --- guild_main ------------------------------------------------------------
def _require_member(db, uid: str):
    m = _member(db, uid)
    if m is None:
        return None, None
    return m, _guild(db, m["guild_name"])


def _act_get_member_list(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "ok", "data": [], "cur_member": 0,
                     "max_member": GUILD_BASE_MAX_MEMBER})
    # BẪY 6: cur_member/max_member phải ở top-level.
    if str(data.get("order_by") or "") == "SEASON_SCORE":
        rows = _rows(db, "SELECT * FROM guild_members WHERE guild_name=? "
                         "ORDER BY season_score DESC, joined_at ASC", (g["guild_name"],))
    else:
        rows = _rows(db, "SELECT * FROM guild_members WHERE guild_name=? "
                         "ORDER BY is_master DESC, joined_at ASC", (g["guild_name"],))
    return _res({"result": "ok", "data": [_member_item(r, uid) for r in rows],
                 "cur_member": _member_count(db, g["guild_name"]),
                 "max_member": _int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER})


def _act_get_approve_list(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None or not m["is_master"]:
        return _res({"result": "ok", "data": [], "cur_member": 0,
                     "max_member": GUILD_BASE_MAX_MEMBER})
    rows = _rows(db, "SELECT * FROM guild_applies WHERE guild_name=? ORDER BY member_no ASC",
                 (g["guild_name"],))
    return _res({"result": "ok", "data": [_apply_item(r) for r in rows],
                 "cur_member": _member_count(db, g["guild_name"]),
                 "max_member": _int_or_zero(g["max_member"]) or GUILD_BASE_MAX_MEMBER})


def _act_get_guild_chat(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "ok", "data": []})
    rows = _rows(db, "SELECT * FROM guild_chat WHERE guild_name=? ORDER BY id DESC LIMIT ?",
                 (g["guild_name"], GUILD_CHAT_KEEP))
    # update_time phải là chuỗi "YYYY-MM-DD HH:MM:SS" — client cắt substring
    # không có guard, truyền số là crash.
    out = [{"update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"])),
            "host_id": r["host_id"] or "", "user_name": r["user_name"] or "",
            "platform": r["platform"] or "WEB", "chat": r["chat"] or "",
            "etc": r["etc"] or ""} for r in reversed(rows)]
    return _res({"result": "ok", "data": out})


def _act_send_guild_chat(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "no_guild", "comment": "chua vao guild"})
    msg = str(data.get("message") or "")
    if not msg.strip():
        return _res({"result": "empty"})
    if len(msg) > GUILD_CHAT_MAX:
        return _res({"result": "long", "comment": "qua %d ky tu" % GUILD_CHAT_MAX})
    name = str(data.get("user_name") or m["user_name"] or "")
    db.execute("INSERT INTO guild_chat (guild_name,host_id,user_name,platform,chat,etc,"
               "created_at) VALUES (?,?,?,?,?,'',?)",
               (g["guild_name"], str(data.get("HOST_ID") or uid), name,
                m["platform"], msg, int(time.time())))
    return _res({"result": "ok"})


def _act_update_leave_guild(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "not_yet"})
    if m["is_master"]:
        return _res({"result": "master_cannot_leave"})
    db.execute("DELETE FROM guild_members WHERE user_id=?", (uid,))
    db.execute("DELETE FROM guild_applies WHERE user_id=?", (uid,))
    return _res({"result": "ok"})


def _act_update_guild_member(db, save, data, uid, day):
    detail = str(data.get("act_detail") or "")
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "not_yet"})

    if detail == "change_notice":
        notice = str(data.get("notice_str") or "")
        if len(notice) > GUILD_NOTICE_MAX:
            return _res({"result": "long"})
        if any(ch in _GUILD_NAME_BAD for ch in notice):
            return _res({"result": "str_not_allowed"})
        db.execute("UPDATE guilds SET notice=? WHERE guild_name=?", (notice, g["guild_name"]))
        return _res({"result": "ok"})

    if detail == "guild_add_max_member":
        if not m["is_master"]:
            return _res({"result": "not_yet"})
        # BẪY 3: client tự trừ ruby sau khi nhận "ok".
        if _ruby_of(save) < GUILD_ADD_MEMBER_RUBY:
            return _res({"result": "not_enough_ruby"})
        db.execute("UPDATE guilds SET max_member=max_member+1 WHERE guild_name=?",
                   (g["guild_name"],))
        return _res({"result": "ok", **_pair(db, g["guild_name"], uid, day)})

    if detail == "transfer_guild_master":
        if not m["is_master"]:
            return _res({"result": "not_yet"})
        target = _one(db, "SELECT * FROM guild_members WHERE guild_name=? AND user_name=?",
                      (g["guild_name"], str(data.get("member_name") or "")))
        if target is None:
            return _res({"result": "not_yet"})
        db.execute("UPDATE guild_members SET is_master=0 WHERE guild_name=?", (g["guild_name"],))
        db.execute("UPDATE guild_members SET is_master=1 WHERE user_id=?", (target["user_id"],))
        db.execute("UPDATE guilds SET master_id=? WHERE guild_name=?",
                   (target["user_id"], g["guild_name"]))
        return _res({"result": "ok", **_pair(db, g["guild_name"], uid, day)})

    if detail == "kick_member":
        if not m["is_master"]:
            return _res({"result": "not_yet"})
        target = _one(db, "SELECT * FROM guild_members WHERE guild_name=? AND user_name=?",
                      (g["guild_name"], str(data.get("member_name") or "")))
        if target is None:
            return _res({"result": "not_yet"})
        if target["is_master"]:
            return _res({"result": "not_yet"})
        db.execute("DELETE FROM guild_members WHERE user_id=?", (target["user_id"],))
        _mark_kicked(db, target["user_id"], int(time.time()))
        return _res({"result": "ok", **_pair(db, g["guild_name"], uid, day)})

    if detail == "guild_delete":
        if not m["is_master"]:
            return _res({"result": "not_yet"})
        others = _rows(db, "SELECT user_id FROM guild_members WHERE guild_name=? AND user_id<>?",
                       (g["guild_name"], uid))
        for row in others:
            _mark_kicked(db, row["user_id"], int(time.time()))
        db.execute("DELETE FROM guild_members WHERE guild_name=?", (g["guild_name"],))
        db.execute("DELETE FROM guild_applies WHERE guild_name=?", (g["guild_name"],))
        db.execute("DELETE FROM guild_chat WHERE guild_name=?", (g["guild_name"],))
        db.execute("DELETE FROM guilds WHERE guild_name=?", (g["guild_name"],))
        return _res({"result": "ok"})

    if detail == "approve_member":
        if not m["is_master"]:
            return _res({"result": "not_yet"})
        want = str(data.get("approve_reject") or "").upper()
        row = _one(db, "SELECT * FROM guild_applies WHERE guild_name=? AND member_no=?",
                   (g["guild_name"], _as_int(data.get("member_no"), -1)))
        if row is None:
            return _res({"result": "not_yet"})
        db.execute("DELETE FROM guild_applies WHERE guild_name=? AND user_id=?",
                   (g["guild_name"], row["user_id"]))
        if want == "APPROVE":
            if _member(db, row["user_id"]) is not None:
                return _res({"result": "already_other_guild"})
            if _member_count(db, g["guild_name"]) >= (_int_or_zero(g["max_member"])
                                                      or GUILD_BASE_MAX_MEMBER):
                return _res({"result": "full"})
            now = int(time.time())
            db.execute("INSERT INTO guild_members (user_id,guild_name,user_name,platform,"
                       "user_level,profile_num,is_master,season_score,gold_bar,mission_data,"
                       "donate_day,donate_data,joined_at,last_attendance) "
                       "VALUES (?,?,?,?,?,?,0,0,0,'{}','','{}',?,?)",
                       (row["user_id"], g["guild_name"], row["user_name"], row["platform"],
                        _int_or_zero(row["user_level"]), _int_or_zero(row["profile_num"]),
                        now, now))
        return _res({"result": "ok", **_pair(db, g["guild_name"], uid, day)})

    return _res({"result": "no", "comment": "act_detail la"})


def _pair(db, name: str, uid: str, day: str) -> dict:
    """BẪY 7: guild_data và member_data nằm ở TOP-LEVEL của response."""
    g = _guild(db, name)
    rows = _rows(db, "SELECT * FROM guild_members WHERE guild_name=? "
                     "ORDER BY is_master DESC, joined_at ASC", (name,))
    return {"guild_data": _guild_data(db, g, uid, day) if g is not None else None,
            "member_data": [_member_item(r, uid) for r in rows]}


def _act_update_guild_buff(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None or not m["is_master"]:
        return _res({"result": "not_yet"})
    lvl = min(_int_or_zero(g["buff_level"]), GUILD_BUFF_MAX_LEVEL)
    if lvl >= GUILD_BUFF_MAX_LEVEL:
        return _res({"result": "max_level"})
    price = GUILD_BUFF_PRICE[lvl]
    if _int_or_zero(g["money"]) < price:
        return _res({"result": "not_enough_money"})
    db.execute("UPDATE guilds SET buff_level=?, money=money-? WHERE guild_name=?",
               (lvl + 1, price, g["guild_name"]))
    g = _guild(db, g["guild_name"])
    return _res({"result": "ok", "data": _guild_data(db, g, uid, day)})


def _act_update_guild_mission(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "not_yet"})
    idx = _as_int(data.get("guild_mission_index"), -1)
    if idx < 0 or idx >= len(GUILD_MISSIONS):
        return _res({"result": "no", "comment": "index mission la"})
    act, need = GUILD_MISSIONS[idx]
    have = _mission_of(m)
    value = _as_int(data.get("guild_act_value"), 0)
    if value >= need:
        have[act] = 1
    db.execute("UPDATE guild_members SET mission_data=? WHERE user_id=?",
               (json.dumps(have), uid))
    return _res({"result": "ok", "data": {
        "guild_data": _guild_data(db, g, uid, day),
        "mission_data": have}})


def _act_update_member_donate(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "not_yet"})
    detail = str(data.get("act_detail") or "").upper()
    spec = GUILD_DONATE.get(detail)
    if spec is None:
        return _res({"result": "no", "comment": "kieu donate la"})
    _key, res_key, contrib, goldbar = spec
    gname = g["guild_name"]
    already = _donate_of(m, day)
    if already[_key] > 0:
        return _res({"result": "already",
                     "guild_data_mine": _mine_of(db, m, day)})
    # BẪY 3: client tự trừ tài nguyên sau khi nhận "ok" — server không trừ.
    if res_key and _wallet_of(save, res_key) < _as_int(data.get("act_value"), 0):
        return _res({"result": "not_enough"})
    already[_key] = 1
    db.execute("UPDATE guild_members SET donate_day=?, donate_data=?, "
               "season_score=season_score+?, gold_bar=gold_bar+? WHERE user_id=?",
               (day, json.dumps(already), contrib, goldbar, uid))
    db.execute("UPDATE guilds SET money=money+?, season_score=season_score+? "
               "WHERE guild_name=?", (_as_int(data.get("act_value"), 0), contrib, gname))
    m = _member(db, uid)
    return _res({"result": "ok", "guild_data_mine": _mine_of(db, m, day)})


# =====================================================================
# GUILD WAR — update_guild_battle.php
# =====================================================================
# Hợp đồng lấy từ eldorado_all_20260915.min.js, không đoán tên field.
#
# BẪY đã kiểm, ghi lại để không phá:
# 1. `period` client so bằng chuỗi Hàn, mà bundle đã bị mojibake hoá (byte UTF-8
#    đọc như latin-1). Hằng số dưới phải copy đúng byte — sai 1 byte là client
#    rơi vào nhánh "không phải kỳ tấn công". Sinh tự động từ bundle, không gõ tay.
# 2. `deck30` là OBJECT khoá "1".."30" (client duyệt n=1..30). `clear_guild_list`,
#    `week_rank`, `attack_success`, `defence_fail`, lịch sử thành viên là mảng
#    1-based (phần tử 0 rỗng, client duyệt `length-1`). Ngược lại `ranking` của
#    Guild Boss và `get_help.data` là mảng 0-based.
# 3. `update_guild_battle_result` trả response LỒNG: client đọc `t.result.result`,
#    `t.result.order`, `t.result.score` — trả phẳng là rơi vào default.
# 4. Client tự trừ `USER.cloud_piece -= 30` khi gọi next_guild_matching_cloud30
#    mà KHÔNG báo server, nên server phải tự trừ 30 (xem _bt_act_next_matching).
#    `insert_guild_battle_revive` thì client đã gọi save_UserInfo_after_PAY.php,
#    không trừ thêm ở đây.
GUILD_BT_PERIOD_READY = '\xec\xa4\x80\xeb\xb9\x84\xea\xb8\xb0\xea\xb0\x84'
GUILD_BT_PERIOD_ATTACK = '\xea\xb3\xb5\xea\xb2\xa9\xea\xb8\xb0\xea\xb0\x84'
GUILD_BT_PERIOD_SETTLE = '\xec\xa0\x95\xec\x82\xb0\xea\xb8\xb0\xea\xb0\x84'
GUILD_BT_WIN = '\xec\x8a\xb9'
GUILD_BT_LOSE = '\xed\x8c\xa8'
GUILD_BT_DRAW = '\xeb\xac\xb4\xec\x8a\xb9\xeb\xb6\x80'
GUILD_BT_PROGRESS = '\xec\xa7\x84\xed\x96\x89\xec\xa4\x91'
GUILD_BT_NO_MATCH = '\xeb\xa7\xa4\xec\xb9\xad\xea\xb8\xb8\xeb\x93\x9c\xed\x9b\x84\xeb\xb3\xb4\xec\x97\x86\xec\x9d\x8c'
GUILD_BT_BAD_MATCH = '[\xec\x98\x88\xec\x99\xb8\xec\xb2\x98\xeb\xa6\xac:'

GUILD_BT_SLOTS = 30        # client duyệt n=1..30
GUILD_BT_DECKS = 3         # deck_attack1..3
GUILD_BT_TZ = 9 * 3600     # múi giờ Hàn Quốc
GUILD_BT_READY_LEN = 86400        # T2 11:00 (KST)
GUILD_BT_ATTACK_LEN = 561600      # CN 23:00 (KST)
GUILD_BT_CLOUD30_PRICE = 30
GUILD_BT_WIN_SCORE = 10    # util_get_score: 10pt mỗi trận thắng
GUILD_BT_DECK_EMPTY = '{"char":"0:0:0:0,0:0:0:0,0:0:0:0,0:0:0:0,0:0:0:0","item":""}'
GUILD_BT_CLEAR_LIST_MAX = 8    # client Math.min(f, 8)

# ponytail: lịch tuần cố định theo giờ Hàn, không cấu hình được. Nếu muốn
# đổi lịch (vd theo múi giờ máy người chơi) thì đọc từ _bt_tz override.
def _bt_clock(now=None) -> tuple[int, str, int]:
    """(week_key, period, remain_seconds). Tuần bắt đầu T2 11:00 giờ Hàn."""
    now = int(time.time()) if now is None else int(now)
    tm = time.gmtime(now + GUILD_BT_TZ)
    sod = tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec
    mon11 = now - (tm.tm_wday * 86400 + sod - 11 * 3600)
    delta = now - mon11
    if delta < GUILD_BT_READY_LEN:
        return mon11, GUILD_BT_PERIOD_READY, mon11 + GUILD_BT_READY_LEN - now
    if delta < GUILD_BT_ATTACK_LEN:
        return mon11, GUILD_BT_PERIOD_ATTACK, mon11 + GUILD_BT_ATTACK_LEN - now
    return mon11, GUILD_BT_PERIOD_SETTLE, mon11 + 7 * 86400 - now


def _bt_row(db, name, week, now):
    db.execute("INSERT OR IGNORE INTO guild_bt_guild (guild_name, week_key, updated_at) "
               "VALUES (?,?,?)", (name, week, now))
    return _one(db, "SELECT * FROM guild_bt_guild WHERE guild_name=? AND week_key=?",
                (name, week))


def _bt_now() -> int:
    return int(time.time())


def _bt_slot_of(db, gname, uid) -> int:
    """Slot 1..30 của thành viên trong guild. 0 = ngoài 30 người."""
    rows = _rows(db, "SELECT user_id FROM guild_members WHERE guild_name=? "
                     "ORDER BY is_master DESC, joined_at ASC LIMIT ?",
                 (gname, GUILD_BT_SLOTS))
    for i, r in enumerate(rows, 1):
        if r["user_id"] == uid:
            return i
    return 0


def _bt_order(db, week, gname) -> int:
    """Thứ hạng theo điểm tuần. 0 = chưa có dòng nào (client hiện '-')."""
    ahead = _scalar(db, "SELECT COUNT(*) FROM guild_bt_guild WHERE week_key=? AND score > "
                        "(SELECT COALESCE(score,0) FROM guild_bt_guild WHERE week_key=? "
                        "AND guild_name=?)", (week, week, gname))
    if not ahead:
        row = _one(db, "SELECT score FROM guild_bt_guild WHERE week_key=? AND guild_name=?",
                   (week, gname))
        if row is None or not _int_or_zero(row["score"]):
            return 0
        return 1
    return _int_or_zero(ahead) + 1


def _bt_cleared_opponents(db, week, gname) -> list[str]:
    """Guild đã bị mình đánh trọn vẹn (mọi ô phòng thủ của họ đều thắng)."""
    done = set()
    for r in _rows(db, "SELECT DISTINCT other_guild_name FROM guild_bt_record "
                       "WHERE week_key=? AND my_guild_name=?", (week, gname)):
        done.add(r["other_guild_name"] or "")
    tot = {}
    won = {}
    for r in _rows(db, "SELECT guild_name, clear_status FROM guild_bt_slot WHERE week_key=?",
                   (week,)):
        tot[r["guild_name"]] = tot.get(r["guild_name"], 0) + 1
        if r["clear_status"] == GUILD_BT_WIN:
            won[r["guild_name"]] = won.get(r["guild_name"], 0) + 1
    return [nm for nm, t in tot.items()
            if nm and nm in done and t and won.get(nm, 0) >= t]


def _bt_flag_pair(db, gname) -> tuple[str, str]:
    g = _guild(db, gname)
    f = _flag(g) if g is not None else {"flagImg": "", "symbolImg": ""}
    return f["flagImg"], f["symbolImg"]


def _bt_slot_tot(db, week, gname) -> int:
    if not gname:
        return 0
    return _int_or_zero(_scalar(db, "SELECT COUNT(*) FROM guild_bt_slot "
                                    "WHERE week_key=? AND guild_name=?", (week, gname)), 0)


def _bt_slot_won(db, week, gname) -> int:
    if not gname:
        return 0
    return _int_or_zero(_scalar(db, "SELECT COUNT(*) FROM guild_bt_slot WHERE week_key=? "
                                    "AND guild_name=? AND clear_status=?",
                                (week, gname, GUILD_BT_WIN)), 0)


def _bt_normal_payload(db, g, uid, week, period, remain) -> dict:
    name = g["guild_name"]
    st = _bt_row(db, name, week, _bt_now())
    opp = st["opponent"] or ""
    m = _member(db, uid)
    my_slot = _bt_slot_of(db, name, uid)
    my_deck = ""
    if my_slot > 0:
        r = _one(db, "SELECT deck FROM guild_bt_slot WHERE week_key=? AND guild_name=? AND slot=?",
                 (week, name, my_slot))
        my_deck = (r["deck"] if r is not None else "") or ""
    cleared = _bt_cleared_opponents(db, week, name)
    clear_list = [None]
    for i, onm in enumerate(cleared[:GUILD_BT_CLEAR_LIST_MAX], 1):
        img, sym = _bt_flag_pair(db, onm)
        clear_list.append({"guild_name": onm, "flag": img, "symbol": sym})
    og = _guild(db, opp) if opp else None
    return {
        "result": "ok",
        "period": period,
        "remain_seconds": max(0, _int_or_zero(remain)),
        "rank_info": {"order": _bt_order(db, week, name),
                      "score": _int_or_zero(st["score"])},
        "other_guild_name": opp if og is not None else GUILD_BT_BAD_MATCH,
        "other_guild_deck_tot": _bt_slot_tot(db, week, opp),
        "other_guild_deck_clear": _bt_slot_won(db, week, opp),
        "my_guild_defence_deck_num": _bt_slot_tot(db, week, name),
        "deck_defence": my_deck,
        "deck_attack1": st["deck_attack1"] or "none",
        "deck_attack2": st["deck_attack2"] or "none",
        "deck_attack3": st["deck_attack3"] or "none",
        "other_guild_flag": (json.dumps(_flag(og), ensure_ascii=False)
                             if og is not None else ""),
        "last_week_clear_guild_num": 0,
        "last_week_guild_score": 0,
        "clear_guild_num_this_week": len(cleared),
        "clear_guild_list": clear_list,
        "season_data": _season_data(),
    }


def _bt_guard(db, uid):
    """(member_row, guild_row) hoặc response lỗi dạng tuple."""
    m = _member(db, uid)
    if m is None:
        return None, None, _res({"result": "no", "comment": "chua co guild"})
    g = _guild(db, m["guild_name"])
    if g is None:
        return None, None, _res({"result": "no", "comment": "chua co guild"})
    return m, g, None


def _bt_act_get_battle_normal(db, save, data, uid, day):
    _, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week, period, remain = _bt_clock()
    return _res(_bt_normal_payload(db, g, uid, week, period, remain))


def _bt_act_update_deck_defence(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week, period, remain = _bt_clock()
    slot = _bt_slot_of(db, g["guild_name"], uid)
    if slot <= 0:
        return _res({"result": "no", "comment": "ngoi 30 o phong thu"})
    cur = _one(db, "SELECT clear_status FROM guild_bt_slot WHERE week_key=? "
                   "AND guild_name=? AND slot=?", (week, g["guild_name"], slot))
    # Chặn đổi deck sau khi ô này đã bị đánh trong tuần — nếu không thì người
    # chơi sửa phòng thủ sau khi thua để né điểm. Không phụ thuộc lịch READY
    # để không chặn nhầm lúc client vẫn cho sửa.
    if cur is not None and (cur["clear_status"] or ""):
        return _res({"result": "no", "comment": "da bi danh trong tuan nay",
                     "guild_battle_normal": _bt_normal_payload(db, g, uid, week, period, remain)})
    me = _me(data, uid)
    now = _bt_now()
    # ponytail: giữ nguyên clear_* để lưu lại deck giữa kỳ không xoá kết quả
    # đánh; chỉ khi server tự dọn mới cần xoá. Nếu client sửa deck sau khi đã
    # bị đánh thì nên reset clear_* ở đây.
    db.execute(
        "INSERT INTO guild_bt_slot (week_key, guild_name, slot, host_id, user_name, "
        "user_info, deck, platform, updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT (week_key, guild_name, slot) DO UPDATE SET host_id=excluded.host_id, "
        "user_name=excluded.user_name, user_info=excluded.user_info, deck=excluded.deck, "
        "platform=excluded.platform, updated_at=excluded.updated_at",
        (week, g["guild_name"], slot, uid, me["user_name"],
         str(data.get("user_info") or ""), str(data.get("defence_deck") or ""),
         me["platform"], now))
    return _res({"result": "ok", "guild_battle_normal":
                 _bt_normal_payload(db, g, uid, week, period, remain)})


def _bt_act_update_deck_attack(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week, period, remain = _bt_clock()
    _bt_row(db, g["guild_name"], week, _bt_now())
    # Client tu gui ca 3 deck. Giu nguyen gia tri client gui, chi can "none"/""
    # de client hieu la chua dat (util_is_set_my_attack_deck).
    def deck(k):
        v = data.get(k)
        return str(v) if v not in (None, "") else "none"

    db.execute("UPDATE guild_bt_guild SET deck_attack1=?, deck_attack2=?, deck_attack3=?, "
               "updated_at=? WHERE guild_name=? AND week_key=?",
               (deck("attack_deck1"), deck("attack_deck2"), deck("attack_deck3"),
                _bt_now(), g["guild_name"], week))
    return _res({"result": "ok", "guild_battle_normal":
                 _bt_normal_payload(db, g, uid, week, period, remain)})


def _bt_pick_opponent(db, gname, week) -> str:
    """Guild nao co deck phong thu va chua bi danh ghep trong tuan nay."""
    done = set()
    for r in _rows(db, "SELECT DISTINCT other_guild_name FROM guild_bt_record "
                       "WHERE week_key=? AND my_guild_name=?", (week, gname)):
        done.add(r["other_guild_name"] or "")
    for r in _rows(db, "SELECT DISTINCT guild_name FROM guild_bt_slot WHERE week_key=?",
                   (week,)):
        nm = r["guild_name"] or ""
        if nm and nm != gname and nm not in done and _guild(db, nm) is not None:
            return nm
    return ""


def _bt_act_next_matching(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week, _, _ = _bt_clock()
    now = _bt_now()
    paid = str(data.get("act") or "") == "next_guild_matching_cloud30"
    if paid:
        # Client tu tru USER.cloud_piece -= 30 ma khong bao server -> server
        # phai tru de 2 ben khong lech nhau.
        have = _wallet_of(save, "cloud_piece")
        if have < GUILD_BT_CLOUD30_PRICE:
            return _res({"result": "no", "comment": "khong du cloud",
                         "guild_name": GUILD_BT_NO_MATCH})
        save["cloud_piece"] = have - GUILD_BT_CLOUD30_PRICE
        _store_save_payload(db, uid, save)
    opp = _bt_pick_opponent(db, g["guild_name"], week)
    _bt_row(db, g["guild_name"], week, now)
    db.execute("UPDATE guild_bt_guild SET opponent=?, updated_at=? "
               "WHERE guild_name=? AND week_key=?", (opp, now, g["guild_name"], week))
    if not opp:
        return _res({"result": "ok", "guild_name": GUILD_BT_NO_MATCH})
    return _res({"result": "ok", "guild_name": opp})


def _bt_used_info(db, week, gname, uid) -> dict:
    m = _member(db, uid)
    uname = (m["user_name"] if m is not None else "") or ""
    out = {}
    for i in range(1, GUILD_BT_DECKS + 1):
        used = _int_or_zero(_scalar(db, "SELECT COUNT(*) FROM guild_bt_record WHERE week_key=? "
                                        "AND my_guild_name=? AND user_name=? AND deck_index=? "
                                        "AND kind='battle'", (week, gname, uname, i)), 0)
        rev = _int_or_zero(_scalar(db, "SELECT COUNT(*) FROM guild_bt_record WHERE week_key=? "
                                       "AND my_guild_name=? AND user_name=? AND deck_index=? "
                                       "AND kind='revive'", (week, gname, uname, i)), 0)
        res = ""
        if used - rev != 0:
            row = _one(db, "SELECT result FROM guild_bt_record WHERE week_key=? "
                           "AND my_guild_name=? AND user_name=? AND deck_index=? "
                           "AND kind='battle' ORDER BY id DESC LIMIT 1", (week, gname, uname, i))
            res = (row["result"] if row is not None else "") or ""
        out["attack%d" % i] = used
        out["attack%d_revive" % i] = rev
        out["attack%d_result" % i] = res
    return out


def _bt_act_get_defence_deck30(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week, _, _ = _bt_clock()
    other = str(data.get("other_guild_name") or "").strip()
    if not other or other == "none":
        return _res({"result": "no", "comment": "chua ghep tran"})
    # Chỉ được xem phòng thủ của đối thủ mình đã ghep trong tuần này.
    mine = _bt_row(db, g["guild_name"], week, 0)
    if (mine["opponent"] or "") != other and not _one(
            db, "SELECT 1 FROM guild_bt_record WHERE week_key=? AND my_guild_name=? "
                "AND other_guild_name=?", (week, g["guild_name"], other)):
        return _res({"result": "no", "comment": "khong phai doi thu da ghep",
                     "my_used_info": _bt_used_info(db, week, g["guild_name"], uid),
                     "deck30": {}})
    deck30 = {}
    for r in _rows(db, "SELECT * FROM guild_bt_slot WHERE week_key=? AND guild_name=? "
                       "ORDER BY slot", (week, other)):
        slot = _int_or_zero(r["slot"])
        if slot < 1 or slot > GUILD_BT_SLOTS:
            continue
        item = {
            "HOST_ID": r["host_id"] or "",
            "PLATFORM": r["platform"] or "WEB",
            "USER_INFO": r["user_info"] or "",
            "DECK_DEFENCE": r["deck"] or "",
            "CLEAR_INFO": None,
        }
        if r["clear_status"]:
            item["CLEAR_INFO"] = {
                "status": r["clear_status"],
                "who_clear": r["who_clear"] or "",
                "who_ing": r["who_ing"] or "",
                "who_fail": r["who_fail"] or "",
                "who_clear_platform": r["who_clear_platform"] or "WEB",
            }
        deck30[str(slot)] = item
    return _res({"result": "ok", "my_used_info":
                 _bt_used_info(db, week, g["guild_name"], uid), "deck30": deck30})


def _bt_act_insert_start(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week = _bt_clock()[0]
    now = _bt_now()
    other = str(data.get("other_guild_name") or "").strip()
    slot = _as_int(data.get("other_guild_slot_no"), 0)
    if not other or other == "none" or slot < 1 or slot > GUILD_BT_SLOTS:
        return _res({"result": "no", "comment": "sai o doi thu"})
    row = _one(db, "SELECT clear_status FROM guild_bt_slot WHERE week_key=? AND guild_name=? "
                   "AND slot=?", (week, other, slot))
    if row is None:
        # Khong co o phong thu = chua dat deck, khong phai muc tieu hop le.
        return _res({"result": "no", "comment": "khong co o phong thu"})
    if row["clear_status"] == GUILD_BT_PROGRESS:
        return _res({"result": "already_doing"})
    me = _me(data, uid)
    db.execute("UPDATE guild_bt_slot SET clear_status=?, who_ing=?, updated_at=? "
               "WHERE week_key=? AND guild_name=? AND slot=?",
               (GUILD_BT_PROGRESS, me["user_name"], now, week, other, slot))
    return _res({"result": "ok"})


def _bt_act_insert_revive(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return err
    week = _bt_clock()[0]
    now = _bt_now()
    other = str(data.get("other_guild_name") or "").strip()
    slot = _as_int(data.get("other_guild_slot_no"), 0)
    di = _as_int(data.get("attack_deck_index"), 1) or 1
    me = _me(data, uid)
    db.execute("INSERT INTO guild_bt_record (week_key, my_guild_name, other_guild_name, "
               "user_name, host_id, result, score, deck_index, kind, at) "
               "VALUES (?,?,?,?,?,'',0,?,'revive',?)",
               (week, g["guild_name"], other, me["user_name"],
                str(data.get("other_host_id") or ""), di, now))
    if other and other != "none" and 1 <= slot <= GUILD_BT_SLOTS:
        db.execute("UPDATE guild_bt_slot SET clear_status='', who_ing='', updated_at=? "
                   "WHERE week_key=? AND guild_name=? AND slot=?",
                   (now, week, other, slot))
    return _res({"result": "ok"})


def _bt_act_update_result(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        # update_guild_battle_result dung response long, loi cung phai long.
        return _res({"result": {"result": "no", "comment": "chua co guild"}})
    week = _bt_clock()[0]
    now = _bt_now()
    gname = g["guild_name"]
    other = str(data.get("other_guild_name") or "").strip()
    slot = _as_int(data.get("other_guild_slot_no"), 0)
    res = str(data.get("battle_result") or "")
    di = _as_int(data.get("attack_deck_index"), 1) or 1
    if res not in (GUILD_BT_WIN, GUILD_BT_LOSE, GUILD_BT_DRAW):
        return _res({"result": {"result": "no", "comment": "battle_result sai"}})
    me = _me(data, uid)
    gain = GUILD_BT_WIN_SCORE if res == GUILD_BT_WIN else 0
    # Retry van phai ra "ok" (client khong doi trang thai) nhung KHONG tinh
    # lai — mot (vien, o doi phuong, bo deck) chi mot lan.
    if slot > 0 and _one(db, "SELECT 1 FROM guild_bt_record WHERE week_key=? "
                              "AND my_guild_name=? AND other_guild_name=? AND user_name=? "
                              "AND other_slot=? AND deck_index=? AND kind='battle'",
                         (week, gname, other, me["user_name"], slot, di)):
        strow = _bt_row(db, gname, week, now)
        return _res({"result": {"result": "ok", "order": _bt_order(db, week, gname),
                                "score": _int_or_zero(strow["score"])}})
    db.execute("INSERT INTO guild_bt_record (week_key, my_guild_name, other_guild_name, "
               "user_name, host_id, result, score, deck_index, kind, at, other_slot) "
               "VALUES (?,?,?,?,?,?,?,?,'battle',?,?)",
               (week, gname, other, me["user_name"],
                str(data.get("other_host_id") or ""), res, gain, di, now, slot))
    st = GUILD_BT_WIN if res == GUILD_BT_WIN else GUILD_BT_LOSE
    if other and other != "none" and 1 <= slot <= GUILD_BT_SLOTS:
        db.execute("UPDATE guild_bt_slot SET clear_status=?, who_clear=?, who_fail=?, "
                   "who_ing='', who_clear_platform=?, updated_at=? "
                   "WHERE week_key=? AND guild_name=? AND slot=?",
                   (st, me["user_name"] if st == GUILD_BT_WIN else "",
                    me["user_name"] if st == GUILD_BT_LOSE else "",
                    me["platform"], now, week, other, slot))
    if gain:
        db.execute("UPDATE guild_bt_guild SET score=score+?, updated_at=? "
                   "WHERE guild_name=? AND week_key=?", (gain, now, gname, week))
        db.execute("UPDATE guild_members SET season_score=season_score+? WHERE user_id=?",
                   (gain, uid))
    strow = _bt_row(db, gname, week, now)
    return _res({"result": {"result": "ok", "order": _bt_order(db, week, gname),
                            "score": _int_or_zero(strow["score"])}})


def _bt_rank_list(db, week, mode) -> list:
    """Mảng 1-based cho week_rank / attack_success / defence_fail.

    Cả 3 tab render bằng cùng một hàng nên đều đọc `defeated_num`; khác nhau ở
    nghĩa theo tab: số guild đã hạ / số trận thắng / số ô thủ bị thua. Đếm
    thẳng từ bảng nhật ký thay vì denormalize — cột kiểu cũ (`beaten_num`)
    không ai cập nhật nên xếp hạng sai.
    """
    won = {}
    for r in _rows(db, "SELECT my_guild_name AS nm, COUNT(*) AS c FROM guild_bt_record "
                       "WHERE week_key=? AND kind='battle' AND result=? GROUP BY my_guild_name",
                   (week, GUILD_BT_WIN)):
        won[r["nm"] or ""] = _int_or_zero(r["c"])
    lost = {}
    for r in _rows(db, "SELECT guild_name AS nm, COUNT(*) AS c FROM guild_bt_slot "
                       "WHERE week_key=? AND clear_status=? GROUP BY guild_name",
                   (week, GUILD_BT_LOSE)):
        lost[r["nm"] or ""] = _int_or_zero(r["c"])
    rows = _rows(db, "SELECT guild_name, score FROM guild_bt_guild WHERE week_key=?", (week,))
    if mode == "attack":
        key = lambda nm: won.get(nm, 0)
        rows = sorted(rows, key=lambda r: (-key(r["guild_name"] or ""),
                                           -_int_or_zero(r["score"]), r["guild_name"] or ""))
    elif mode == "defence":
        key = lambda nm: lost.get(nm, 0)
        rows = sorted(rows, key=lambda r: (-key(r["guild_name"] or ""), r["guild_name"] or ""))
    else:
        key = lambda nm: _bt_cleared_count(db, week, nm) if nm else 0
        rows = sorted(rows, key=lambda r: (-_int_or_zero(r["score"]), r["guild_name"] or ""))
    out = [None]
    for i, r in enumerate(rows, 1):
        img, sym = _bt_flag_pair(db, r["guild_name"])
        out.append({
            "order": i,
            "guild_name": r["guild_name"],
            "score": _int_or_zero(r["score"]),
            "defeated_num": key(r["guild_name"] or ""),
            "flag_info": {"flagImg": img, "symbolImg": sym},
        })
    return out


def _bt_cleared_count(db, week, gname) -> int:
    return len(_bt_cleared_opponents(db, week, gname)) if gname else 0


def _bt_act_rank_all(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return _res({"result": "no", "comment": "chua co guild"})
    week = _bt_clock()[0]
    return _res({"result": "ok", "data": {
        "week_rank": _bt_rank_list(db, week, "week"),
        "attack_success": _bt_rank_list(db, week, "attack"),
        "defence_fail": _bt_rank_list(db, week, "defence"),
    }})


def _bt_act_member_history(db, save, data, uid, day):
    m, g, err = _bt_guard(db, uid)
    if err is not None:
        return _res({"result": "no", "comment": "chua co guild", "data": [None]})
    week = _bt_clock()[0]
    gname = g["guild_name"]
    agg = {}
    for r in _rows(db, "SELECT user_name, result, score FROM guild_bt_record "
                       "WHERE week_key=? AND my_guild_name=? AND kind='battle' "
                       "ORDER BY id ASC", (week, gname)):
        a = agg.setdefault(r["user_name"] or "",
                           {"TOT": 0, "WIN": 0, "DRAW": 0, "LOSE": 0, "score": 0})
        a["TOT"] += 1
        if r["result"] == GUILD_BT_WIN:
            a["WIN"] += 1
        elif r["result"] == GUILD_BT_DRAW:
            a["DRAW"] += 1
        elif r["result"] == GUILD_BT_LOSE:
            a["LOSE"] += 1
        a["score"] += _int_or_zero(r["score"])
    rows = _rows(db, "SELECT user_id, user_name, platform FROM guild_members "
                     "WHERE guild_name=? ORDER BY is_master DESC, joined_at ASC", (gname,))
    out = [None]
    for r in rows:
        a = agg.get(r["user_name"] or "", None) or {"TOT": 0, "WIN": 0, "DRAW": 0,
                                                    "LOSE": 0, "score": 0}
        out.append({"TOT": a["TOT"], "WIN": a["WIN"], "DRAW": a["DRAW"], "LOSE": a["LOSE"],
                    "score": a["score"], "name": r["user_name"] or "",
                    "platform": r["platform"] or "WEB",
                    "me_flag": 1 if r["user_id"] == uid else 0})
    return _res({"result": "ok", "data": out})


# =====================================================================
# GUILD BOSS — update_guild_boss.php
# =====================================================================
# 5 act (KHONG phai 3 nhu ghi so trong tai lieu): get_lobby, check_can_enter,
# enter_battle, report_damage, get_help. Client goi qua S_BOSS (dong bo voi
# World Boss) nhung moi du lieu deu qua update_guild_boss.php.
# `ranking` va `get_help.data` la mang 0-based (client duyet tu 0).
GUILD_BOSS_BOSS_NO = 5
GUILD_BOSS_STAGE_NUM = 7
GUILD_BOSS_STAGE_HP = (300000, 500000, 800000, 1200000, 1800000, 2600000, 4000000)
# Client co san bang cap {3:50,4:40,5:30,6:20,7:10} trong trang help 1; tra
# cap_pct giong het de 2 ben khop.
GUILD_BOSS_STAGE_CAP = (100, 100, 50, 40, 30, 20, 10)
GUILD_BOSS_REWARD = (
    (300, 0, 30, 20, 0), (400, 0, 35, 20, 0), (500, 0, 40, 25, 0),
    (700, 0, 45, 25, 0), (900, 0, 50, 30, 0), (1200, 0, 55, 30, 0),
    (1500, 0, 60, 40, 0),
)   # gold_bar, ruby, contribution, cloud, cel_essn
GUILD_BOSS_FREE_PER_DAY = 1
GUILD_BOSS_PAID_GOLD = 10000


def _boss_ensure(db, gname, week, now):
    for i in range(1, GUILD_BOSS_STAGE_NUM + 1):
        db.execute("INSERT OR IGNORE INTO guild_boss_stage (guild_name, week_key, stage, "
                   "boss_no, max_hp, cur_hp, updated_at) VALUES (?,?,?,?,?,?,?)",
                   (gname, week, i, GUILD_BOSS_BOSS_NO, GUILD_BOSS_STAGE_HP[i - 1],
                    GUILD_BOSS_STAGE_HP[i - 1], now))
    db.execute("INSERT OR IGNORE INTO guild_boss_stage (guild_name, week_key, stage, "
               "boss_no, max_hp, cur_hp, updated_at) VALUES (?,?,?,?,?,?,?)",
               (gname, week, 0, GUILD_BOSS_BOSS_NO, 0, 0, now))


def _boss_stages(db, gname, week) -> list:
    out = []
    for i in range(1, GUILD_BOSS_STAGE_NUM + 1):
        r = _one(db, "SELECT max_hp, cur_hp FROM guild_boss_stage WHERE guild_name=? "
                     "AND week_key=? AND stage=?", (gname, week, i))
        mx = _int_or_zero(r["max_hp"]) if r is not None else 0
        cur = _int_or_zero(r["cur_hp"]) if r is not None else 0
        out.append({"stage": i, "max_hp": mx, "current_hp": cur,
                    "cleared": 1 if mx and cur <= 0 else 0})
    return out


def _boss_active(db, gname, week) -> int:
    for s in _boss_stages(db, gname, week):
        if s["cleared"]:
            continue
        return s["stage"]
    return 0


def _boss_my_damage(db, gname, week, uid) -> int:
    m = _member(db, uid)
    uname = (m["user_name"] if m is not None else "") or ""
    if not uname:
        return 0
    row = _one(db, "SELECT total_damage FROM guild_boss_damage WHERE guild_name=? "
                   "AND week_key=? AND user_name=?", (gname, week, uname))
    return _int_or_zero(row["total_damage"]) if row is not None else 0


def _boss_free_left(save: dict, day: str) -> int:
    if str(save.get("gb_free_day") or "") != day:
        return GUILD_BOSS_FREE_PER_DAY
    return max(0, _int_or_zero(save.get("gb_free_left"), GUILD_BOSS_FREE_PER_DAY))


def _boss_lobby(db, g, save, uid, day) -> dict:
    gname = g["guild_name"]
    week, _, _ = _bt_clock()
    now = _bt_now()
    _boss_ensure(db, gname, week, now)
    mine = _boss_my_damage(db, gname, week, uid)
    plat = {}
    for mr in _rows(db, "SELECT user_name, platform FROM guild_members WHERE guild_name=?",
                    (gname,)):
        plat[mr["user_name"] or ""] = mr["platform"] or "WEB"
    ranking = []
    for i, r in enumerate(_rows(db, "SELECT user_name, user_chars, total_damage "
                                    "FROM guild_boss_damage WHERE guild_name=? AND week_key=? "
                                    "ORDER BY total_damage DESC, user_name ASC",
                                (gname, week)), 1):
        ranking.append({
            "rank": i,
            "user_chars": r["user_chars"] or "",
            "user_name": r["user_name"] or "",
            "platform": plat.get(r["user_name"] or "", "WEB"),
            "total_damage": _int_or_zero(r["total_damage"]),
        })
    my_rank = 0
    for i, r in enumerate(ranking, 1):
        if mine > 0 and _int_or_zero(r["total_damage"]) == mine:
            my_rank = i
            break
    return {
        "result": "ok",
        "week_id": week,
        "boss_no": GUILD_BOSS_BOSS_NO,
        "active_stage": _boss_active(db, gname, week),
        "stages": _boss_stages(db, gname, week),
        "free_remain": _boss_free_left(save, day),
        "my_total_damage": mine,
        "my_rank": my_rank,
        "ranking": ranking,
        "paid_entry_gold": GUILD_BOSS_PAID_GOLD,
    }


def _boss_guard(db, uid):
    m = _member(db, uid)
    if m is None:
        return None, None, _res({"result": "no", "comment": "chua co guild"})
    g = _guild(db, m["guild_name"])
    if g is None:
        return None, None, _res({"result": "no", "comment": "chua co guild"})
    return m, g, None


def _boss_act_get_lobby(db, save, data, uid, day):
    _, g, err = _boss_guard(db, uid)
    if err is not None:
        return err
    return _res(_boss_lobby(db, g, save, uid, day))


def _boss_act_check_can_enter(db, save, data, uid, day):
    _, g, err = _boss_guard(db, uid)
    if err is not None:
        return err
    week, _, _ = _bt_clock()
    _boss_ensure(db, g["guild_name"], week, _bt_now())
    if _boss_active(db, g["guild_name"], week) <= 0:
        return _res({"result": "gb-all-cleared"})
    return _res({"result": "ok", "free_remain": _boss_free_left(save, day),
                 "paid_entry_gold": GUILD_BOSS_PAID_GOLD})


def _boss_act_enter_battle(db, save, data, uid, day):
    m, g, err = _boss_guard(db, uid)
    if err is not None:
        return err
    week, _, _ = _bt_clock()
    now = _bt_now()
    gname = g["guild_name"]
    _boss_ensure(db, gname, week, now)
    stage = _boss_active(db, gname, week)
    if stage <= 0:
        return _res({"result": "gb-all-cleared"})
    srow = _one(db, "SELECT max_hp, cur_hp FROM guild_boss_stage WHERE guild_name=? "
                    "AND week_key=? AND stage=?", (gname, week, stage))
    free = _boss_free_left(save, day)
    if free > 0:
        save["gb_free_day"] = day
        save["gb_free_left"] = str(free - 1)
        used_type = "free"
    else:
        d1 = (save.get("DATA1") or "").split(",")
        gold = _int_or_zero(d1[1]) if len(d1) > 1 else 0
        if gold < GUILD_BOSS_PAID_GOLD:
            return _res({"result": "gb-not-enough-gold"})
        d1[1] = str(gold - GUILD_BOSS_PAID_GOLD)
        save["DATA1"] = ",".join(d1)
        used_type = "paid"
    _store_save_payload(db, uid, save)
    mine = _boss_my_damage(db, gname, week, uid)
    cap = GUILD_BOSS_STAGE_CAP[stage - 1]
    cap_allow = _int_or_zero(srow["max_hp"]) * cap // 100
    token = secrets.token_hex(16)
    db.execute("INSERT INTO guild_boss_token (token, guild_name, week_key, user_id, "
               "user_name, stage, created_at, used_at) VALUES (?,?,?,?,?,?,?,NULL)",
               (token, gname, week, uid, (m["user_name"] or ""), stage, now))
    return _res({"result": "ok", "week_id": week, "boss_no": GUILD_BOSS_BOSS_NO,
                 "stage": stage, "stage_max_hp": _int_or_zero(srow["max_hp"]),
                 "stage_current_hp": _int_or_zero(srow["cur_hp"]),
                 "used_type": used_type, "battle_token": token, "cap_pct": cap,
                 "my_cap_remain_raw": max(0, cap_allow - mine),
                 "my_cur_raw": _int_or_zero(srow["cur_hp"])})


def _boss_act_report_damage(db, save, data, uid, day):
    m, g, err = _boss_guard(db, uid)
    if err is not None:
        return err
    week, _, _ = _bt_clock()
    now = _bt_now()
    gname = g["guild_name"]
    token = str(data.get("battle_token") or "").strip()
    row = _one(db, "SELECT * FROM guild_boss_token WHERE token=?", (token,))
    if row is None or row["user_id"] != uid:
        return _res({"result": "gb-bad-token",
                     "lobby": _boss_lobby(db, g, save, uid, day)})
    if row["used_at"]:
        # Client gui lai (retry/timeout) -> khong cong damage 2 lan.
        return _res({"result": "gb-already-cleared", "applied_raw": 0,
                     "lobby": _boss_lobby(db, g, save, uid, day)})
    stage = _int_or_zero(row["stage"])
    mult = _as_float(data.get("damage_mult"), 0.0)
    mult = max(0.0, min(1000.0, mult))
    applied = int(max(0, _as_int(data.get("damage_raw"), 0)) * mult)
    srow = _one(db, "SELECT max_hp, cur_hp FROM guild_boss_stage WHERE guild_name=? "
                    "AND week_key=? AND stage=?", (gname, week, stage))
    mine = _boss_my_damage(db, gname, week, uid)
    cap = GUILD_BOSS_STAGE_CAP[stage - 1] if 1 <= stage <= GUILD_BOSS_STAGE_NUM else 100
    cap_allow = _int_or_zero(srow["max_hp"]) * cap // 100
    room = max(0, cap_allow - mine)
    applied = min(applied, room, max(0, _int_or_zero(srow["cur_hp"])))
    db.execute("UPDATE guild_boss_stage SET cur_hp=cur_hp-?, updated_at=? "
               "WHERE guild_name=? AND week_key=? AND stage=?",
               (applied, now, gname, week, stage))
    db.execute("INSERT INTO guild_boss_damage (guild_name, week_key, user_name, host_id, "
               "user_chars, total_damage, updated_at) VALUES (?,?,?,?,?,?,?) "
               "ON CONFLICT (guild_name, week_key, user_name) DO UPDATE SET "
               "total_damage=guild_boss_damage.total_damage+excluded.total_damage, "
               "user_chars=excluded.user_chars, updated_at=excluded.updated_at",
               (gname, week, (m["user_name"] or ""), uid,
                str(data.get("user_chars") or ""), applied, now))
    db.execute("UPDATE guild_boss_token SET used_at=? WHERE token=?", (now, token))
    return _res({"result": "ok", "applied_raw": applied,
                 "lobby": _boss_lobby(db, g, save, uid, day)})


def _boss_act_get_help(db, save, data, uid, day):
    _, g, err = _boss_guard(db, uid)
    if err is not None:
        return err
    out = []
    for i in range(1, GUILD_BOSS_STAGE_NUM + 1):
        gb, rb, co, cl, ce = GUILD_BOSS_REWARD[i - 1]
        out.append({"stage": i, "cap_pct": GUILD_BOSS_STAGE_CAP[i - 1],
                    "reward": {"gold_bar": gb, "ruby": rb, "contribution": co,
                               "cloud": cl, "cel_essn": ce}})
    return _res({"result": "ok", "data": out})


# --- Guild Shop — endpoint update_guild_shop.php -----------------------------
# BẪY 13 (Guild Shop): client chi doc `result` + `goldbar_cnt` + `reward_info`,
# roi tu hien popup S_POPUP_GACHA_RESULT. Nó KHONG goi update_item_to_server
# trong path nay -> server phai tu cap item (qua mailbox, dung TXT
# .random_box_tip "The item will be delivered to your mailbox.").
# Client gui `price`/`times`/`user_goldbar` chi de hien thi, khong duoc tin.
def _shop_mail_sn(mails: list) -> str:
    base = int(time.strftime("%Y%m%d")) * 1000000
    used = {int(m["sn"]) for m in mails
            if str(m.get("sn", "") or "").strip().lstrip("+-").isdigit()}
    sn = base
    while sn in used:
        sn += 1
    return str(sn)


def _shop_roll_item(slot: int) -> dict:
    """1 luot item. Mirror S_POPUP_PACKAGE_STORE client (ITEM_GACHA):
    slot (1..4) x grade x variant (1/2/3 theo
    DEFINE_ITEM_UPGRADE.probability_sangjungha = 60/30/10).

    Ghi 3 chu so de client tu random sub-option khi nhan mail:
    S_MAILBOX.reward_get_in_server case "ITEM" — `d==3` thi chon ngau nhien
    DEFINE_ITEM_SUB_OPTION[1..7] va tu roll so theo grade suy ra tu chinh
    item_num (S_ITEM.num_apply_item_grade_return_num). Ghi 4 chu so se khong
    random duoc (digit thu 4 chinh la option index)."""
    p3 = secrets.randbelow(100) + 1
    variant = 1 if p3 <= 60 else (2 if p3 <= 90 else 3)
    if slot < 1 or slot > 4:
        slot = secrets.randbelow(4) + 1
    return {"type": "ITEM",
            "value": int("%d%d%d" % (slot, GUILD_SHOP_GRADE, variant))}


def roll_lunar_lucky_rewards(times: int, slot: int = 0) -> list[dict]:
    """Roll the shared Lunar Lucky item package on the server.

    Guild Shop and BP Gacha must use the same reward table. Keeping the roll
    here prevents the two endpoints from drifting in probability, grade, or
    amount ranges.
    """
    rewards = []
    for _ in range(max(0, int(times))):
        r = secrets.randbelow(100) + 1
        if r <= 55:
            rewards.append(_shop_roll_item(slot))
        elif r <= 70:
            rewards.append({"type": "GOLD",
                            "value": 1000 + secrets.randbelow(9001)})
        elif r <= 80:
            rewards.append({"type": "RUBY",
                            "value": 10 + secrets.randbelow(91)})
        elif r <= 90:
            rewards.append({"type": "BP",
                            "value": 50 + secrets.randbelow(251)})
        else:
            rewards.append({"type": "CLOUD",
                            "value": 5 + secrets.randbelow(46)})
    return rewards


def _shop_act_purchase(db, save, data, uid, day):
    m, g = _require_member(db, uid)
    if g is None:
        return _res({"result": "gs-not-in-guild"})
    type_num = _as_int(data.get("type_num"), 0)
    spec = GUILD_SHOP_CARD.get(type_num)
    hero = None
    if spec is None:
        # Card 1/2 (hero gacha): type_num do server cap qua `hero_list`.
        hero = _shop_hero_spec(type_num)
        if hero is None:
            return _res({"result": "gs-bad-card"})
        spec = hero[:2]
    times, price = spec
    if _as_int(data.get("times"), 0) != times:
        return _res({"result": "gs-bad-times"})
    slot = _as_int(data.get("char_reward"), 0)
    if slot < 1 or slot > 4:
        slot = 0
    # Idempotent: client gui lai nguyen body sau timeout. `user_goldbar` client
    # gui len la so du TRUOC lan mua, nen retry giong het -> tra lai ket qua cu.
    # Chi khi so du hien tai DUNG bang so du sau giao dich moi la retry: user
    # kiem lai duoc tien roi mua tiep thi so du da doi -> phai la don moi.
    gold_now = _int_or_zero(_member(db, uid)["gold_bar"])
    fp = "%d|%d|%d|%d" % (type_num, times, slot, _as_int(data.get("user_goldbar"), 0))
    dup = _one(db, "SELECT gold_bar_after, response FROM guild_shop_buy "
                   "WHERE user_id=? AND fp=?", (uid, fp))
    if dup is not None and _int_or_zero(dup["gold_bar_after"]) == gold_now:
        return 200, dup["response"]

    cur = db.execute("UPDATE guild_members SET gold_bar=gold_bar-? "
                     "WHERE user_id=? AND gold_bar>=?", (price, uid, price))
    if cur.rowcount != 1:
        return _res({"result": "not_enough"})
    left = _int_or_zero(_member(db, uid)["gold_bar"])

    if hero is not None:
        # Card hero: nguoi choi CHON san hero trong popup nen khong random.
        # Client S_POPUP_GACHA_RESULT preload co_ch<value>.png cho type=="CHAR".
        reward_info = [{"type": "CHAR", "value": hero[2]}] * times
    else:
        reward_info = roll_lunar_lucky_rewards(times, slot)

    gold = sum(x["value"] for x in reward_info if x["type"] == "GOLD")
    ruby = sum(x["value"] for x in reward_info if x["type"] == "RUBY")
    bp = sum(x["value"] for x in reward_info if x["type"] == "BP")
    cloud = sum(x["value"] for x in reward_info if x["type"] == "CLOUD")

    d1 = str(save.get("DATA1") or "").split(",")
    while len(d1) < 21:
        d1.append("0")
    if gold:
        d1[1] = str(_int_or_zero(d1[1]) + gold)
    if ruby:
        d1[2] = str(_int_or_zero(d1[2]) + ruby)
    save["DATA1"] = ",".join(d1)
    if bp:
        save["bp"] = str(_int_or_zero(save.get("bp")) + bp)
    if cloud:
        save["cloud_piece"] = str(_int_or_zero(save.get("cloud_piece")) + cloud)

    # Client khong tu ghi STORAGE trong path nay -> item/hero phai qua mailbox.
    # Mailbox case "CHAR" goi STORAGE.add_char, case "ITEM" tu random
    # sub-option. Quy uoc `why` English uppercase, khop serve.py.
    drops = [(x["type"], str(x["value"])) for x in reward_info
             if x["type"] in ("ITEM", "CHAR")]
    if drops:
        mails = save.get("mails") or []
        sdate, edate = time.strftime("%Y-%m-%d"), "20991231"
        for what, value in drops:
            mails.append({"sn": _shop_mail_sn(mails), "why": "LUNAR LUCKY PACKAGE",
                          "what": what, "what_value": value,
                          "start_date": sdate, "end_date": edate})
        save["mails"] = mails
    _store_save_payload(db, uid, save)

    text = json.dumps({"result": "ok", "goldbar_cnt": left,
                       "reward_info": reward_info}, ensure_ascii=False)
    db.execute("INSERT OR REPLACE INTO guild_shop_buy (user_id, fp, gold_bar_after, "
               "created_at, response) VALUES (?,?,?,?,?)",
               (uid, fp, left, _bt_now(), text))
    db.execute("DELETE FROM guild_shop_buy WHERE user_id=? AND created_at<?",
               (uid, _bt_now() - 86400))
    return 200, text


_ACT = {
    "check_guild_name": _act_check_guild_name,
    "get_guild_normal": _act_get_guild_normal,
    "check_guild_member": _act_check_guild_member,
    "insert_new_guild": _act_insert_new_guild,
    "get_guild_list": _act_get_guild_list,
    "join_open_guild": _act_join_open_guild,
    "join_approve_guild": _act_join_approve_guild,
    "get_guild_season_ranking_data": _act_get_guild_season_ranking_data,
    "get_member_list": _act_get_member_list,
    "get_approve_list": _act_get_approve_list,
    "get_guild_chat": _act_get_guild_chat,
    "send_guild_chat": _act_send_guild_chat,
    "update_leave_guild": _act_update_leave_guild,
    "update_guild_member": _act_update_guild_member,
    "update_guild_buff": _act_update_guild_buff,
    "update_guild_mission": _act_update_guild_mission,
    "update_member_donate": _act_update_member_donate,
}

# Guild War — endpoint update_guild_battle.php
_ACT_BATTLE = {
    "get_battle_normal": _bt_act_get_battle_normal,
    "update_deck_defence": _bt_act_update_deck_defence,
    "update_deck_attack": _bt_act_update_deck_attack,
    "next_guild_matching": _bt_act_next_matching,
    "next_guild_matching_cloud30": _bt_act_next_matching,
    "get_defence_deck30": _bt_act_get_defence_deck30,
    "insert_guild_battle_start": _bt_act_insert_start,
    "insert_guild_battle_revive": _bt_act_insert_revive,
    "update_guild_battle_result": _bt_act_update_result,
    "get_guild_battle_rank_all": _bt_act_rank_all,
    "get_guild_battle_member_history": _bt_act_member_history,
}

# Guild Boss — endpoint update_guild_boss.php
_ACT_BOSS = {
    "get_lobby": _boss_act_get_lobby,
    "check_can_enter": _boss_act_check_can_enter,
    "enter_battle": _boss_act_enter_battle,
    "report_damage": _boss_act_report_damage,
    "get_help": _boss_act_get_help,
}

# Guild Shop — endpoint update_guild_shop.php
_ACT_SHOP = {
    "guild_shop_purchase": _shop_act_purchase,
}

_ACT_BY_GROUP = {"guild_inter": _ACT, "guild_main": _ACT,
                 "guild_battle": _ACT_BATTLE, "guild_boss": _ACT_BOSS,
                 "guild_shop": _ACT_SHOP}


def guild_dispatch(rel_path: str, body_str: str, db_conn, save_lock, uid: str) -> tuple[int, str]:
    """Trả (status, json_text) cho `Guild/update_guild_inter.php`,
    `update_guild_main.php`, `update_guild_battle.php` (Guild War),
    `update_guild_boss.php` (Guild Boss) và `update_guild_shop.php`
    (Guild Shop). uid là account server-side đang nói
    chuyện ("" khi chưa login) — không bao giờ tin `USER_NAME` trong body."""
    path = urlsplit(rel_path or "/").path
    lp = path.lower()
    if "update_guild_inter.php" in lp:
        group = "guild_inter"
    elif "update_guild_main.php" in lp:
        group = "guild_main"
    elif "update_guild_battle.php" in lp:
        group = "guild_battle"
    elif "update_guild_boss.php" in lp:
        group = "guild_boss"
    elif "update_guild_shop.php" in lp:
        group = "guild_shop"
    else:
        return 404, json.dumps({"result": "no", "comment": "het endpoint"}, ensure_ascii=False)

    acts = _ACT_BY_GROUP[group]
    data = _body_json_obj(body_str)
    act = str(data.get("act") or "")

    if not uid:
        return _res({"result": "no", "comment": "chua dang nhap"})
    if db_conn is None:
        # Khong co --db thi khong luu duoc guild. Giu hien trang stub de game
        # van chay, thay vi tra du lieu gia.
        if act == "get_guild_normal":
            # Client: switch(result){case"ok": switch(data){case"no_guild":...}}
            # -> phai tra result="ok" + data="no_guild", tra result="no_guild"
            # se roi vao default va bam loi "Error - GGN e".
            return _res({"result": "ok", "data": "no_guild",
                         "season_data": _season_data()})
        if act == "check_guild_member":
            # Client switch(result): case"no_guild" -> mo man GUILD_ENTER,
            # case"has_guild" -> vao thang S_GUILD_MAIN. Khac get_guild_normal,
            # act nay switch truc tiep tren `result`, khong qua `data`.
            return _res({"result": "no_guild", "exit_remain_time": None,
                         "exit_time": 0, "season_data": _season_data()})
        if act in acts:
            return _res({"result": "no", "comment": "server chua bat --db"})
        return _res({"result": "no", "comment": "act chua lam"})

    handler = acts.get(act)
    if handler is None:
        return _res({"result": "no", "comment": "act chua lam", "act": act})

    day = _today()
    with save_lock:
        save = _load_save_payload(db_conn, uid)
        status, text = handler(db_conn, save, data, uid, day)
        db_conn.commit()
    return status, text

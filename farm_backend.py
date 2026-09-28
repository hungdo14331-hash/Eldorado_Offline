"""
BUSIDOL Farm web backend (F0 — khung)
=====================================

Backend cho game farm nông trại 2.5D, chạy chung server với RubyFarm.
State farm nằm trong cùng payload save của account (`s["farm"]`), nguồn sự
thật duy nhất với phần còn lại của game; đọc/ghi trực tiếp qua SQLite giống
admin_control_backend để tránh đụng save_lock và session của serve.py.

Security model:
- account tới từ session (uid do serve.py truyền), không tin body
- mọi mutation chạy dưới save_lock
- không tin client về số dư (server tính toán toàn bộ)

Hợp đồng mọi endpoint: JSON {STATE: "SUCCESS"|"ERROR", ...}. Không trả {}.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from admin_control_backend import _append_mail, _next_mail_sn

# Trạng thái farm mặc định khi account chưa có farm.
# slots_total: số ô đất (chỉ số khung; dữ liệu cây F2+).
# upgrades: cấp bắt đầu 0 của 4 nhánh (F3 sẽ định thang+effect).
# skills: cây kỹ năng đã mua/active (F4).
FARM_VERSION = 1
# Tổng số ô đất; 5 ô đầu free, các ô sau mở khóa bằng coins (unlock_slot).
FARM_SLOTS_TOTAL = 20
FARM_FREE_SLOTS = 5

# Giá mở khóa ô kế tiếp theo số ô đã mở: cost = round(50 * 1.25^(n-free)).
# n = số ô đang mở. Mở tuần tự, ô 6 (index 5) giá 50 → ô 20 giá ~1136 coins.
def slot_unlock_cost(unlocked_count: int) -> int:
    return int(50 * round(1.25 ** (unlocked_count - FARM_FREE_SLOTS)))


# Nâng cấp 4 nhánh (F3). Mỗi nhánh cấp 0..MAX_UPGRADE_LEVEL.
# Effect:
#   grow_speed — mọc nhanh hơn: grow_sec /(1 + 0.15*level)
#   grow_time  — giảm thêm giờ mọc tuyệt đối: -30*(level) giây
#   sell_price — giá bán ×(1 + 0.10*level)
#   seed_cost  — giá hạt ×(1 - 0.10*level), tối thiểu 1
MAX_UPGRADE_LEVEL = 5
UPGRADE_BRANCHES = {"grow_speed", "grow_time", "sell_price", "seed_cost"}
FARM_API_VERSION = "1.1.0"


def upgrade_cost(current_level: int) -> int:
    """Tiền để lên cấp từ current_level lên +1 (cấp mới ^2 * 120)."""
    return 120 * (current_level + 1) ** 2


# Cây kỹ năng (F4). Mỗi skill đan chéo với một nhánh upgrade (prereq cấp tối
# thiểu) và tiêu coins cố định. Effect nhân THÊM lên hiệu ứng upgrade cùng
# nhánh. Chỉnh số liệu ở đây, logic không đổi.
SKILL_DESIGN = {
    "green_thumb": {
        "name_vi": "bàn tay xanh",
        "cost": 5000,
        "require_branch": "sell_price",
        "require_level": 3,
        # bán thêm +5% (nhân với sell_price upgrade)
    },
    "quick_hands": {
        "name_vi": "tay thoăn thoắt",
        "cost": 5000,
        "require_branch": "grow_time",
        "require_level": 3,
        # thêm -20s mọc (cộng dồn dưới mức floor 5s)
    },
    "fertilize": {
        "name_vi": "phân bón siêu cấp",
        "cost": 5000,
        "require_branch": "grow_speed",
        "require_level": 3,
        # mọc nhanh thêm: thêm pip 0.15 vào mẫu số
    },
    "bulk_discount": {
        "name_vi": "mua sỉ",
        "cost": 5000,
        "require_branch": "seed_cost",
        "require_level": 3,
        # hạt rẻ thêm -5% (nhân với seed_cost upgrade)
    },
}

SKILL_MULT_SELL = 1.05
SKILL_GROW_TIME_BONUS = 20
SKILL_GROW_SPEED_PIP = 0.15
SKILL_SEED_COST_MULT = 0.95


def _has_skill(skills: list, skill: str) -> bool:
    return isinstance(skills, list) and skill in skills


def effective_grow_sec(base_grow_sec: int, upgrades: dict, skills: list = None) -> int:
    speed = int(upgrades.get("grow_speed", 0) or 0)
    time_ = int(upgrades.get("grow_time", 0) or 0)
    denom = 1 + 0.15 * speed
    if _has_skill(skills, "fertilize"):
        denom += SKILL_GROW_SPEED_PIP
    minus = 30 * time_
    if _has_skill(skills, "quick_hands"):
        minus += SKILL_GROW_TIME_BONUS
    return max(5, int(base_grow_sec / denom) - minus)


def effective_sell(base_sell: int, upgrades: dict, skills: list = None) -> int:
    v = base_sell * (1 + 0.10 * int(upgrades.get("sell_price", 0) or 0))
    if _has_skill(skills, "green_thumb"):
        v *= SKILL_MULT_SELL
    return int(v)


def effective_seed_cost(base_cost: int, upgrades: dict, skills: list = None) -> int:
    v = base_cost * (1 - 0.10 * int(upgrades.get("seed_cost", 0) or 0))
    if _has_skill(skills, "bulk_discount"):
        v *= SKILL_SEED_COST_MULT
    return max(1, int(v))

# 4 độ hiếm hạt giống (bậc 1 → 4). bậc cao: hạt đắt hơn, mọc lâu hơn,
# nhưng lợi nhuận/phút cao hơn hẳn (đầu tư high-tier đáng giá).
SEED_RARITY_ORDER = ["common", "rare", "epic", "legendary"]
SEED_RARITY_VI = {
    "common": "bình thường",
    "rare": "hiếm",
    "epic": "cao cấp",
    "legendary": "huyền thoại",
}

# Danh sách cây trồng (nguồn sự thật cho F2+). Ý nghĩa:
#   cost      — giá mua hạt giống (coins)
#   sell      — giá bán cây/trái thu hoạch (coins)
#   grow_sec  — thời gian lớn từ khi trồng tới khi thu hoạch (giây, server-side)
#   rarity    — bậc hiếm (thuộc SEED_RARITY_ORDER)
#   ruby_cost — (bậc 3/4) giá mua hạt bằng ruby từ ví rubyfarm (trả bằng wallet_ruby)
#   sell_ruby — (bậc 3/4) thưởng ruby về ví khi bán 1 trái (TẠM: ép 2, huyền thoại 5,
#               user chốt số chính thức sau)
# Cân bằng: sell > cost luôn; lợi nhuận/phút trung bình tăng dần theo bậc
# (test invariant ép điều này). Điều chỉnh số liệu ở đây, không cần đụng
# logic F2. Toàn cây quen thuộc, dễ nhận diện.
SEED_DESIGN = {
    # ── bậc 1: bình thường (mọc 1–6 phút) ──
    "wheat":     {"rarity": "common", "name_vi": "lúa mì",    "cost": 5,  "sell": 14,   "grow_sec": 120},
    "carrot":    {"rarity": "common", "name_vi": "cà rốt",    "cost": 5,  "sell": 16,   "grow_sec": 90},
    "corn":      {"rarity": "common", "name_vi": "ngô",        "cost": 10, "sell": 30,   "grow_sec": 180},
    "potato":    {"rarity": "common", "name_vi": "khoai tây",  "cost": 10, "sell": 34,   "grow_sec": 240},
    "mung_bean": {"rarity": "common", "name_vi": "đậu xanh",   "cost": 12, "sell": 40,   "grow_sec": 180},
    "tomato":    {"rarity": "common", "name_vi": "cà chua",    "cost": 15, "sell": 50,   "grow_sec": 300},
    "cabbage":   {"rarity": "common", "name_vi": "bắp cải",    "cost": 18, "sell": 62,   "grow_sec": 360},
    "sweet_potato": {"rarity": "common", "name_vi": "khoai lang", "cost": 20, "sell": 70, "grow_sec": 360},
    # ── bậc 2: hiếm (mọc 15–40 phút) ──
    "luffa":     {"rarity": "rare", "name_vi": "mướp",          "cost": 30, "sell": 140,  "grow_sec": 900},
    "pumpkin":   {"rarity": "rare", "name_vi": "bí ngô",         "cost": 40, "sell": 190,  "grow_sec": 1200},
    "eggplant":  {"rarity": "rare", "name_vi": "cà tím",         "cost": 45, "sell": 220,  "grow_sec": 1500},
    "cucumber":  {"rarity": "rare", "name_vi": "dưa chuột",      "cost": 50, "sell": 250,  "grow_sec": 1500},
    "orange":    {"rarity": "rare", "name_vi": "cam",            "cost": 70, "sell": 350,  "grow_sec": 2400},
    "watermelon":{"rarity": "rare", "name_vi": "dưa hấu",        "cost": 80, "sell": 420,  "grow_sec": 2400},
    "strawberry":{"rarity": "rare", "name_vi": "dâu tây",        "cost": 90, "sell": 500,  "grow_sec": 2400},
    # ── bậc 3: cao cấp (mọc 1–2 giờ) ──
    "sugarcane": {"rarity": "epic", "name_vi": "mía",            "cost": 220, "sell": 1000,  "grow_sec": 3600, "ruby_cost": 15,  "sell_ruby": 2},
    "pineapple": {"rarity": "epic", "name_vi": "dứa",            "cost": 250, "sell": 1150,  "grow_sec": 3600, "ruby_cost": 18,  "sell_ruby": 2},
    "sunflower": {"rarity": "epic", "name_vi": "hướng dương",    "cost": 300, "sell": 1400,  "grow_sec": 3600, "ruby_cost": 20,  "sell_ruby": 2},
    "grape":     {"rarity": "epic", "name_vi": "nho",            "cost": 350, "sell": 1680,  "grow_sec": 5400, "ruby_cost": 25,  "sell_ruby": 2},
    "blueberry": {"rarity": "epic", "name_vi": "việt quất",      "cost": 400, "sell": 1950,  "grow_sec": 5400, "ruby_cost": 30,  "sell_ruby": 2},
    "mango":     {"rarity": "epic", "name_vi": "xoài",           "cost": 450, "sell": 2220,  "grow_sec": 5400, "ruby_cost": 35,  "sell_ruby": 2},
    "durian":    {"rarity": "epic", "name_vi": "sầu riêng",      "cost": 600, "sell": 2950,  "grow_sec": 7200, "ruby_cost": 40,  "sell_ruby": 2},
    # ── bậc 4: huyền thoại (mọc 3–6 giờ) ──
    "tea":       {"rarity": "legendary", "name_vi": "chè",        "cost": 1200, "sell": 6000,  "grow_sec": 10800, "ruby_cost": 60,   "sell_ruby": 5},
    "carambola": {"rarity": "legendary", "name_vi": "khế",        "cost": 1500, "sell": 7600,  "grow_sec": 10800, "ruby_cost": 75,   "sell_ruby": 5},
    "dragon_fruit": {"rarity": "legendary", "name_vi": "thanh long", "cost": 2000, "sell": 10000, "grow_sec": 14400, "ruby_cost": 100,  "sell_ruby": 5},
    "coffee":    {"rarity": "legendary", "name_vi": "cà phê",      "cost": 2500, "sell": 12500, "grow_sec": 14400, "ruby_cost": 125,  "sell_ruby": 5},
    "ginseng":   {"rarity": "legendary", "name_vi": "nhân sâm",    "cost": 3500, "sell": 18000, "grow_sec": 18000, "ruby_cost": 175,  "sell_ruby": 5},
    "agarwood":  {"rarity": "legendary", "name_vi": "trầm hương",  "cost": 5000, "sell": 26000, "grow_sec": 21600, "ruby_cost": 200,  "sell_ruby": 5},
}
FARM_DEFAULT = {
    "version": FARM_VERSION,
    "coins": 0,
    "gold": 0,
    "diamond": 0,
    "slots_total": FARM_SLOTS_TOTAL,
    "unlocked_count": FARM_FREE_SLOTS,
    "slots": [],
    # Kho vật phẩm: dict key -> số lượng nguyên. Key format:
    #   "seed:<seed>"  — hạt giống (mua về, plant tiêu thụ)
    #   "crop:<seed>"  — sản phẩm thu hoạch (bán qua sell.php)
    #   "item:<tên>"   — vật phẩm khác sau này
    "inventory": {},
    "upgrades": {
        "grow_speed": 0,
        "grow_time": 0,
        "sell_price": 0,
        "seed_cost": 0,
    },
    "skills": [],
    "created_at": None,
    "updated_at": None,
}


def _load_save_payload(db_conn, uid: str) -> dict:
    if db_conn is None:
        raise RuntimeError("Farm requires --db SQLite mode")
    if not uid:
        raise PermissionError("not authenticated")
    row = db_conn.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
    if not row:
        raise RuntimeError("account has no save yet")
    try:
        data = json.loads(row[0])
    except Exception as exc:
        raise RuntimeError("account save payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("account save payload is not a JSON object")
    return data


def _store_save_payload(db_conn, uid: str, data: dict):
    db_conn.execute(
        "INSERT OR REPLACE INTO saves (id, payload) VALUES (?,?)",
        (uid, json.dumps(data, ensure_ascii=False)),
    )


def _farm_state(data: dict):
    farm = data.get("farm")
    if not isinstance(farm, dict):
        farm = dict(FARM_DEFAULT)
        farm["created_at"] = int(time.time())
    farm = dict(farm)
    farm["updated_at"] = int(time.time())
    return farm


FARM_WALLET_KEYS = {"coins", "gold", "diamond"}


def _farm_inventory(farm: dict) -> dict:
    inv = farm.get("inventory")
    if not isinstance(inv, dict):
        inv = {}
        farm["inventory"] = inv
    return inv


def inventory_add(farm: dict, item: str, qty: int):
    """Cộng qty (>= 0) vào kho. Chạy dưới save_lock."""
    if qty < 0:
        raise ValueError("negative inventory add")
    inv = _farm_inventory(farm)
    try:
        cur = int(str(inv.get(item, 0) or 0))
    except (TypeError, ValueError):
        cur = 0
    inv[item] = min(2**63 - 1, cur + qty)


def inventory_take(farm: dict, item: str, qty: int):
    """Trừ qty ở kho. Không cho âm — raise ValueError nếu thiếu."""
    if qty < 0:
        raise ValueError("negative inventory take")
    inv = _farm_inventory(farm)
    try:
        cur = int(str(inv.get(item, 0) or 0))
    except (TypeError, ValueError):
        cur = 0
    if cur < qty:
        raise ValueError("insufficient inventory")
    if cur == qty:
        inv.pop(item, None)
    else:
        inv[item] = cur - qty


def farm_balances(farm: dict) -> dict[str, int]:
    """Số dư 3 loại tiền farm (int). farm là dict state do server quản lý."""
    out = {k: 0 for k in FARM_WALLET_KEYS}
    if not isinstance(farm, dict):
        return out
    for k in FARM_WALLET_KEYS:
        try:
            v = int(float(str(farm.get(k, 0) or 0)))
        except (TypeError, ValueError):
            v = 0
        out[k] = max(0, v)
    return out


def farm_credit(farm: dict, currency: str, amount: int):
    """Cộng tiền farm. amount phải >= 0; chạy dưới save_lock."""
    if currency not in FARM_WALLET_KEYS:
        raise ValueError("invalid farm currency")
    if amount < 0:
        raise ValueError("negative credit")
    balances = farm_balances(farm)
    balances[currency] = min(2**63 - 1, balances[currency] + amount)
    farm.update(balances)


def farm_spend(farm: dict, currency: str, amount: int):
    """Trừ tiền farm. Không cho âm — raise ValueError nếu không đủ."""
    if currency not in FARM_WALLET_KEYS:
        raise ValueError("invalid farm currency")
    if amount < 0:
        raise ValueError("negative spend")
    balances = farm_balances(farm)
    if balances[currency] < amount:
        raise ValueError("insufficient funds")
    balances[currency] -= amount
    farm.update(balances)


# ── Ruby: ví dùng chung với RubyFarm web (s["wallet_ruby"]) ──
# Khác coin/gold/diamond farm, ruby là ví liên kết với web ruby_farm: mua hạt
# bậc 3/4 và mua nhân vật trả bằng ruby; thưởng ruby khi bán trả về ví này.
# Không đụng ruby game gốc (DATA1[2]).
def _wallet_ruby(data: dict) -> int:
    try:
        return max(0, int(float(str(data.get("wallet_ruby", 0) or 0))))
    except (TypeError, ValueError):
        return 0


def _wallet_ruby_set(data: dict, value: int):
    data["wallet_ruby"] = str(min(2**63 - 1, max(0, value)))


def _wallet_ruby_credit(data: dict, amount: int):
    if amount < 0:
        raise ValueError("negative ruby credit")
    _wallet_ruby_set(data, _wallet_ruby(data) + amount)


def _wallet_ruby_spend(data: dict, amount: int):
    if amount < 0:
        raise ValueError("negative ruby spend")
    bal = _wallet_ruby(data)
    if bal < amount:
        raise ValueError("insufficient ruby")
    _wallet_ruby_set(data, bal - amount)


# ── Mua nhân vật gốc bằng ruby (F6) ──
# Giá theo độ hiếm đã chốt: 1-2★=10, 3★=20, 4★=40, 5★=90, 6★=400, 7★=2700,
# 8★=7000. Không bán nhân vật thần (9★). Id/tên/star đọc TRỰC TIẾP từ
# Wiki/data/characters.js (nguồn sự thật của dự án — wiki chứa id + tên nhân vật).
CHARACTER_PRICE_RUBY = {1: 10, 2: 10, 3: 20, 4: 40, 5: 90, 6: 400, 7: 2700, 8: 7000}

# Fallback nếu file wiki thiếu/hỏng — giữ danh sách id→star đã đối chiếu wiki
# (26/09/2026); khi wiki đọc được thì cosine này không dùng.
_CHARACTER_STAR_FALLBACK = {
    1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 2,
    11: 3, 12: 4, 13: 5, 14: 6, 15: 2, 16: 3, 17: 4, 18: 5, 19: 6, 20: 2,
    21: 3, 22: 4, 23: 5, 24: 6, 25: 1, 26: 2, 27: 3, 28: 4, 29: 5, 30: 6,
    31: 1, 32: 2, 33: 3, 34: 4, 35: 5, 36: 6, 37: 1, 38: 2, 39: 3, 40: 4,
    41: 5, 42: 6, 43: 2, 44: 3, 45: 4, 46: 5, 47: 6, 48: 7, 49: 7, 50: 7,
    51: 2, 52: 3, 53: 4, 54: 5, 55: 6, 56: 7, 57: 2, 58: 3, 59: 4, 60: 5,
    61: 6, 62: 7, 63: 7, 64: 7, 65: 7, 66: 7, 67: 7, 68: 7, 69: 1, 70: 2,
    71: 3, 72: 4, 73: 5, 74: 6, 75: 7, 76: 2, 77: 3, 78: 4, 79: 5, 80: 6,
    81: 7, 82: 8, 83: 8, 84: 8, 85: 8, 86: 8, 87: 8, 88: 8, 89: 8, 90: 8,
    91: 8, 92: 8, 93: 8, 94: 8, 95: 8, 96: 4, 97: 5, 98: 6, 99: 7, 100: 8,
    101: 8, 102: 8, 103: 8, 104: 8, 105: 8, 106: 8, 107: 8, 108: 9, 109: 9,
    110: 9, 111: 9, 112: 8, 113: 9, 114: 9,
}


def _load_character_catalog(base_dir: Path) -> dict:
    """Đọc {id: {"name", "star"}} từ Wiki/data/characters.js (const CHARACTERS)."""
    path = base_dir / "Wiki" / "data" / "characters.js"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = re.search(r"const\s+CHARACTERS\s*=\s*\[", text)
    if not m:
        return {}
    end = text.find("];", m.end())
    block = text[m.end(): end if end != -1 else None]
    catalog = {}
    for obj in re.finditer(r"\{\s*id:\s*(\d+)\s*,\s*name:\s*\"([^\"]*)\"[^\}]*?\}", block):
        mid = re.search(r"star:\s*(\d+)", obj.group(0))
        if not mid:
            continue
        catalog[int(obj.group(1))] = {"name": obj.group(2), "star": int(mid.group(1))}
    return catalog


catalog = _load_character_catalog(Path(__file__).resolve().parent)
CHARACTER_CATALOG = {cid: {"name": d.get("name", "?"), "star": d.get("star") or _CHARACTER_STAR_FALLBACK.get(cid, 1)}
                     for cid, d in catalog.items()}
CHARACTER_STAR = {cid: d["star"] for cid, d in CHARACTER_CATALOG.items()}
if not CHARACTER_STAR:  # wiki không đọc được → fallback toàn bộ
    CHARACTER_CATALOG = {cid: {"name": "?", "star": s} for cid, s in _CHARACTER_STAR_FALLBACK.items()}
    CHARACTER_STAR = dict(_CHARACTER_STAR_FALLBACK)
VALID_CHARACTER_IDS = set(CHARACTER_STAR)


def _state_response(data: dict, uid: str) -> dict:
    farm = data.get("farm")
    if not isinstance(farm, dict):
        farm = {k: (v.copy() if isinstance(v, dict) else v)
                for k, v in FARM_DEFAULT.items()}
    b = farm_balances(farm)
    # coins/gold/diamond farm tách riêng; ruby là ví chung RubyFarm (wallet_ruby).
    return {
        "STATE": "SUCCESS",
        "farm": {
            "version": farm.get("version", FARM_VERSION),
            "ruby": str(_wallet_ruby(data)),
            "coins": str(b["coins"]),
            "gold": str(b["gold"]),
            "diamond": str(b["diamond"]),
            "slots_total": str(int(farm.get("slots_total", FARM_SLOTS_TOTAL))),
            "unlocked_count": str(int(farm.get("unlocked_count", FARM_FREE_SLOTS))),
            "next_unlock_cost": str(
                slot_unlock_cost(int(farm.get("unlocked_count", FARM_FREE_SLOTS)))
            ),
            "slots": list(farm.get("slots", [])),
            "inventory": _farm_inventory(farm),
            "upgrades": farm.get("upgrades", dict(FARM_DEFAULT["upgrades"])),
            "upgrade_cost": {
                b: str(upgrade_cost(int(farm.get("upgrades", {}).get(b, 0) or 0)))
                for b in sorted(UPGRADE_BRANCHES)
            },
            "skills": list(farm.get("skills", [])),
        },
        "account": uid,
    }


def _get_state(db_conn, save_lock, uid: str):
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
            data["farm"]["updated_at"] = int(time.time())
            _store_save_payload(db_conn, uid, data)
            db_conn.commit()
        return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _reset(db_conn, save_lock, uid: str):
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        farm = dict(FARM_DEFAULT)
        farm["created_at"] = int(time.time())
        farm["updated_at"] = int(time.time())
        data["farm"] = farm
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(
        {"STATE": "SUCCESS", "reset": True, **(_state_response(data, uid)["farm"])},
        ensure_ascii=False,
    )


def _body_form(body_str: str) -> dict:
    try:
        parsed = parse_qs(body_str or "", keep_blank_values=True)
    except Exception:
        return {}
    return {k: v[0] for k, v in parsed.items()}


def _slots(farm: dict, total: int) -> list:
    """Trả danh sách ô đất, mỗi ô None (=trống) hoặc dict cây. Đảm bảo độ dài."""
    slots = farm.get("slots")
    if not isinstance(slots, list):
        slots = []
    if len(slots) < total:
        slots = slots + [None] * (total - len(slots))
    farm["slots"] = slots
    return slots


def _unlock_slot(db_conn, save_lock, uid: str):
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
        farm = data["farm"]
        total = int(farm.get("slots_total", FARM_SLOTS_TOTAL))
        unlocked = int(farm.get("unlocked_count", FARM_FREE_SLOTS))
        if unlocked >= total:
            return 400, json.dumps({"STATE": "ERROR", "message": "ALL_UNLOCKED"}, ensure_ascii=False)
        cost = slot_unlock_cost(unlocked)
        try:
            farm_spend(farm, "coins", cost)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_FUNDS"}, ensure_ascii=False)
        farm["unlocked_count"] = unlocked + 1
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _buy_seed(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    seed = form.get("seed", "")
    cfg = SEED_DESIGN.get(seed)
    if not cfg:
        return 400, json.dumps({"STATE": "ERROR", "message": "SEED_NOT_FOUND"}, ensure_ascii=False)
    try:
        qty = int(form.get("qty", "1"))
    except (TypeError, ValueError):
        qty = 1
    if qty < 1 or qty > 999:
        return 400, json.dumps({"STATE": "ERROR", "message": "BAD_QTY"}, ensure_ascii=False)
    # currency=coins (mặc định) hoặc ruby. Hạt bậc 3/4 có ruby_cost,
    # trả bằng ví chung wallet_ruby; upgrade seed_cost KHÔNG áp vào giá ruby.
    currency = form.get("currency", "coins")
    if currency == "ruby":
        ruby_cost = int(cfg.get("ruby_cost", 0) or 0)
        if ruby_cost <= 0:
            return 400, json.dumps({"STATE": "ERROR", "message": "SEED_NOT_RUBY"}, ensure_ascii=False)
        with save_lock:
            data = _load_save_payload(db_conn, uid)
            if "farm" not in data or not isinstance(data["farm"], dict):
                data["farm"] = dict(FARM_DEFAULT)
                data["farm"]["created_at"] = int(time.time())
            farm = data["farm"]
            cost = ruby_cost * qty
            try:
                _wallet_ruby_spend(data, cost)
            except ValueError:
                return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_FUNDS"}, ensure_ascii=False)
            inventory_add(farm, "seed:" + seed, qty)
            farm["updated_at"] = int(time.time())
            _store_save_payload(db_conn, uid, data)
            db_conn.commit()
        return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)
    if currency != "coins":
        return 400, json.dumps({"STATE": "ERROR", "message": "BAD_CURRENCY"}, ensure_ascii=False)
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
        farm = data["farm"]
        cost = effective_seed_cost(int(cfg["cost"]), farm.get("upgrades", {}), farm.get("skills")) * qty
        try:
            farm_spend(farm, "coins", cost)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_FUNDS"}, ensure_ascii=False)
        inventory_add(farm, "seed:" + seed, qty)
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _upgrade(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    branch = form.get("branch", "")
    if branch not in UPGRADE_BRANCHES:
        return 400, json.dumps({"STATE": "ERROR", "message": "BRANCH_NOT_FOUND"}, ensure_ascii=False)
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
        farm = data["farm"]
        upgrades = farm.get("upgrades")
        if not isinstance(upgrades, dict):
            upgrades = dict(FARM_DEFAULT["upgrades"])
            farm["upgrades"] = upgrades
        level = int(upgrades.get(branch, 0) or 0)
        if level >= MAX_UPGRADE_LEVEL:
            return 400, json.dumps({"STATE": "ERROR", "message": "MAX_LEVEL"}, ensure_ascii=False)
        cost = upgrade_cost(level)
        try:
            farm_spend(farm, "coins", cost)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_FUNDS"}, ensure_ascii=False)
        upgrades[branch] = level + 1
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _learn_skill(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    skill = form.get("skill", "")
    cfg = SKILL_DESIGN.get(skill)
    if not cfg:
        return 400, json.dumps({"STATE": "ERROR", "message": "SKILL_NOT_FOUND"}, ensure_ascii=False)
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
        farm = data["farm"]
        skills = farm.get("skills")
        if not isinstance(skills, list):
            skills = []
            farm["skills"] = skills
        if skill in skills:
            return 400, json.dumps({"STATE": "ERROR", "message": "ALREADY_OWNED"}, ensure_ascii=False)
        upgrades = farm.get("upgrades")
        if not isinstance(upgrades, dict):
            upgrades = dict(FARM_DEFAULT["upgrades"])
            farm["upgrades"] = upgrades
        branch_level = int(upgrades.get(cfg["require_branch"], 0) or 0)
        if branch_level < int(cfg["require_level"]):
            return 400, json.dumps({"STATE": "ERROR", "message": "PREREQ_NOT_MET"}, ensure_ascii=False)
        cost = int(cfg["cost"])
        try:
            farm_spend(farm, "coins", cost)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_FUNDS"}, ensure_ascii=False)
        skills.append(skill)
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _plant(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    seed = form.get("seed", "")
    cfg = SEED_DESIGN.get(seed)
    if not cfg:
        return 400, json.dumps({"STATE": "ERROR", "message": "SEED_NOT_FOUND"}, ensure_ascii=False)
    try:
        slot = int(form.get("slot", "-1"))
    except (TypeError, ValueError):
        slot = -1
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        if "farm" not in data or not isinstance(data["farm"], dict):
            data["farm"] = dict(FARM_DEFAULT)
            data["farm"]["created_at"] = int(time.time())
        farm = data["farm"]
        total = int(farm.get("slots_total", FARM_SLOTS_TOTAL))
        unlocked = int(farm.get("unlocked_count", FARM_FREE_SLOTS))
        slots = _slots(farm, total)
        if slot < 0 or slot >= total:
            return 400, json.dumps({"STATE": "ERROR", "message": "SLOT_NOT_FOUND"}, ensure_ascii=False)
        if slot >= unlocked:
            return 400, json.dumps({"STATE": "ERROR", "message": "SLOT_LOCKED"}, ensure_ascii=False)
        if slots[slot] is not None:
            return 400, json.dumps({"STATE": "ERROR", "message": "SLOT_BUSY"}, ensure_ascii=False)
        try:
            inventory_take(farm, "seed:" + seed, 1)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "NO_SEED"}, ensure_ascii=False)
        slots[slot] = {
            "seed": seed,
            "planted_at": int(time.time()),
            "grow_sec": effective_grow_sec(int(cfg["grow_sec"]), farm.get("upgrades", {}), farm.get("skills")),
        }
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _harvest(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    try:
        slot = int(form.get("slot", "-1"))
    except (TypeError, ValueError):
        slot = -1
    now = int(time.time())
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        farm = data.get("farm")
        if not isinstance(farm, dict):
            return 400, json.dumps({"STATE": "ERROR", "message": "NO_FARM"}, ensure_ascii=False)
        total = int(farm.get("slots_total", FARM_SLOTS_TOTAL))
        unlocked = int(farm.get("unlocked_count", FARM_FREE_SLOTS))
        slots = _slots(farm, total)
        if slot < 0 or slot >= total:
            return 400, json.dumps({"STATE": "ERROR", "message": "SLOT_NOT_FOUND"}, ensure_ascii=False)
        if slot >= unlocked:
            return 400, json.dumps({"STATE": "ERROR", "message": "SLOT_LOCKED"}, ensure_ascii=False)
        planted = slots[slot]
        if planted is None:
            return 400, json.dumps({"STATE": "ERROR", "message": "EMPTY_SLOT"}, ensure_ascii=False)
        ready_at = int(planted.get("planted_at", 0)) + int(planted.get("grow_sec", 0))
        if now < ready_at:
            return 400, json.dumps(
                {"STATE": "ERROR", "message": "NOT_READY", "remaining_sec": ready_at - now},
                ensure_ascii=False,
            )
        cfg = SEED_DESIGN.get(planted.get("seed"))
        if not cfg:
            return 400, json.dumps({"STATE": "ERROR", "message": "SEED_NOT_FOUND"}, ensure_ascii=False)
        # thu hoach vao kho, khong ban thang (ban qua sell.php)
        inventory_add(farm, "crop:" + planted.get("seed"), 1)
        slots[slot] = None
        farm["updated_at"] = now
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _sell(db_conn, save_lock, uid: str, body_str: str):
    form = _body_form(body_str)
    item = form.get("item", "")
    seed = item[5:] if item.startswith("crop:") else ""
    cfg = SEED_DESIGN.get(seed)
    if not cfg:
        return 400, json.dumps({"STATE": "ERROR", "message": "ITEM_NOT_SELLABLE"}, ensure_ascii=False)
    try:
        qty = int(form.get("qty", "1"))
    except (TypeError, ValueError):
        qty = 1
    if qty < 1 or qty > 999:
        return 400, json.dumps({"STATE": "ERROR", "message": "BAD_QTY"}, ensure_ascii=False)
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        farm = data.get("farm")
        if not isinstance(farm, dict):
            return 400, json.dumps({"STATE": "ERROR", "message": "NO_FARM"}, ensure_ascii=False)
        try:
            inventory_take(farm, item, qty)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "NO_ITEM"}, ensure_ascii=False)
        sell = effective_sell(int(cfg["sell"]), farm.get("upgrades", {}), farm.get("skills")) * qty
        farm_credit(farm, "coins", sell)
        # Thưởng ruby về ví chung (wallet_ruby) khi bán cây bậc 3/4.
        # Số liệu TẠM: ép 2 ruby/trái, huyền thoại 5 ruby/trái — chốt sau.
        sel_ruby = int(cfg.get("sell_ruby", 0) or 0) * qty
        if sel_ruby > 0:
            _wallet_ruby_credit(data, sel_ruby)
        farm["updated_at"] = int(time.time())
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps(_state_response(data, uid), ensure_ascii=False)


def _bootstrap(db_conn, save_lock, uid: str) -> tuple[int, str]:
    """Đóng gói cho client: state + toàn bộ cấu hình cần vẽ UI."""
    status, text = _get_state(db_conn, save_lock, uid)
    if status != 200:
        return status, text
    data = json.loads(text)
    data["api_version"] = FARM_API_VERSION
    data["upgrade"] = {
        "branches": sorted(UPGRADE_BRANCHES),
        "max_level": MAX_UPGRADE_LEVEL,
        "curve": [upgrade_cost(i) for i in range(MAX_UPGRADE_LEVEL)],
    }
    data["buy_character"] = {
        "enabled": True,
        "price": CHARACTER_PRICE_RUBY,
        # catalog từ Wiki/data/characters.js: id → tên + sao (để client vẽ shop)
        "catalog": {
            str(cid): {"name": c["name"], "star": c["star"]}
            for cid, c in sorted(CHARACTER_CATALOG.items())
        },
    }
    return 200, json.dumps(data, ensure_ascii=False)


def _buy_character(db_conn, save_lock, uid: str, body_str: str) -> tuple[int, str]:
    """
    Mua nhân vật game gốc bằng ruby, gửi hòm thư (mail CHAR) giống admin.
    Giá theo độ hiếm: CHARACTER_PRICE_RUBY. Trả ruby từ ví chung wallet_ruby.
    Toàn bộ trạng thái client (id, star) do server tra cứu, không tin client.
    """
    form = _body_form(body_str)
    try:
        character_id = int(form.get("character", "0") or "0")
    except (TypeError, ValueError):
        return 400, json.dumps({"STATE": "ERROR", "message": "MISSING_CHARACTER"}, ensure_ascii=False)
    if character_id <= 0:
        return 400, json.dumps({"STATE": "ERROR", "message": "MISSING_CHARACTER"}, ensure_ascii=False)
    star = CHARACTER_STAR.get(character_id)
    if star is None:
        return 400, json.dumps({"STATE": "ERROR", "message": "INVALID_CHARACTER"}, ensure_ascii=False)
    price = CHARACTER_PRICE_RUBY.get(star)
    if price is None:  # star 9 (thần) không bán
        return 400, json.dumps({"STATE": "ERROR", "message": "NOT_FOR_SALE"}, ensure_ascii=False)
    with save_lock:
        data = _load_save_payload(db_conn, uid)
        try:
            _wallet_ruby_spend(data, price)
        except ValueError:
            return 400, json.dumps({"STATE": "ERROR", "message": "INSUFFICIENT_RUBY"}, ensure_ascii=False)
        sn = _append_mail(data, "CHAR", str(character_id), "FARM PURCHASE")
        _store_save_payload(db_conn, uid, data)
        db_conn.commit()
    return 200, json.dumps({
        "STATE": "SUCCESS",
        "character_id": character_id,
        "name": CHARACTER_CATALOG.get(character_id, {}).get("name", "?"),
        "star": star,
        "price_ruby": price,
        "mail_sn": sn,
        "ruby": str(_wallet_ruby(data)),
    }, ensure_ascii=False)


def farm_dispatch(rel_path: str, body_str: str, db_conn, save_lock, uid: str) -> tuple[int, str]:
    """
    Trả (status, json_text). rel_path chuẩn hoá (bỏ query), uid = account
    server-side đang nói chuyện ("" khi chưa login).
    """
    path = urlsplit(rel_path or "/").path.rstrip("/") or "/"
    lp = path.lower()
    if "farm/bootstrap.php" in lp:
        return _bootstrap(db_conn, save_lock, uid)
    if "farm/buy_character.php" in lp:
        return _buy_character(db_conn, save_lock, uid, body_str)
    if "farm/get_state.php" in lp:
        return _get_state(db_conn, save_lock, uid)
    if "farm/seeds.php" in lp:
        return 200, json.dumps(
            {"STATE": "SUCCESS", "seeds": SEED_DESIGN, "skills": SKILL_DESIGN},
            ensure_ascii=False,
        )
    if "farm/plant.php" in lp:
        return _plant(db_conn, save_lock, uid, body_str)
    if "farm/upgrade.php" in lp:
        return _upgrade(db_conn, save_lock, uid, body_str)
    if "farm/skill.php" in lp:
        return _learn_skill(db_conn, save_lock, uid, body_str)
    if "farm/buy_seed.php" in lp:
        return _buy_seed(db_conn, save_lock, uid, body_str)
    if "farm/sell.php" in lp:
        return _sell(db_conn, save_lock, uid, body_str)
    if "farm/unlock_slot.php" in lp:
        return _unlock_slot(db_conn, save_lock, uid)
    if "farm/harvest.php" in lp:
        return _harvest(db_conn, save_lock, uid, body_str)
    if "farm/reset.php" in lp:
        return _reset(db_conn, save_lock, uid)
    return 404, json.dumps({"STATE": "ERROR", "message": "NOT_FOUND"}, ensure_ascii=False)
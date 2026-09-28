"""Validate custom character packs and generate the browser registry."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent / "characters"
ASSET_ROOT = ROOT / "ELDORADO_WEB" / "source_20240722" / "image" / "char"
OUTPUT = ROOT / "ELDORADO_WEB" / "custom_characters" / "custom_characters.generated.js"

FEATURES = {"SPEED", "WIDE", "HP", "ATTACK", "TARGET", "ATTACK_WIDE", "ARMOR"}
ATTACK_TYPES = {"SINGLE", "WIDE", "FULL_WIDE", "HIT_WIDE", "TARGET"}
SPECIAL_ABILITIES = {
    "FORTITUDE", "INSTANT_KILL", "PVP_TEAM_DAMAGE_REDUCTION", "PVP_CHAR_SEAL",
    "PVP_HP_AP_UP", "PVP_TOWER_DAMAGE", "PVP_TOWER_SHIELD", "PVP_SCORE_UP",
    "ARMOR", "ONESHOT", "OSOK_IMM", "OSOK_CHANCE", "MOVE_INV", "CAN_ABS",
    "SLOW_DOWN", "PUSH", "GM_SA_DEF", "STG_BURN_INC", "CB_DMG", "SNAKE_BIND",
    "COLD_AURA", "ENHANCED_HEALER", "TORTOISE_SPIRIT", "VALOR_BUGLE",
    "PVP_TOWER_HP_HEAL_DOWN", "CUR_HP_DAMAGE", "STEALTH", "SPRINT",
}
INNATE_ABILITIES = {
    "PUSH_IMM", "DIGNITY_IMM", "TIME_STOP_IMM", "INSTANT_KILL_IMM", "FREEZE_IMM",
    "SLOW_IMM", "BURN_IMM", "OSOK_IMM", "TF_ATTACK_UPGRADE", "ARMOR",
    "TORTOISE_AP_BUFF", "MULTI_HIT", "ANGRY_BURN_IMM", "CHAOS_GALE_IMM",
}
REQUIRED_SKILL_PARAMETERS = {
    "PUSH": "push_per",
    "INSTANT_KILL": "instant_kill_per",
    "FORTITUDE": "fortitude_per",
    "CUR_HP_DAMAGE": "cur_hp_damage_per",
    "STEALTH": "stealth_per",
    "SNAKE_BIND": "snake_bind_duration",
    "COLD_AURA": "cold_slow_per",
    "ENHANCED_HEALER": "summon_heal_per",
    "TORTOISE_SPIRIT": "tortoise_buff_per",
    "VALOR_BUGLE": "valor_bugle_per",
}


def read_png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:26]
    if len(header) < 26 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"khong phai PNG hop le: {path}")
    if header[25] not in (4, 6):
        raise ValueError(f"PNG phai co kenh alpha: {path}")
    return struct.unpack(">II", header[16:24])


def load_configs(config_dir: Path = CONFIG_DIR) -> list[dict]:
    configs = []
    for path in sorted(config_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_configPath"] = str(path.relative_to(ROOT)).replace("\\", "/")
        configs.append(data)
    return configs


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} phai la so nguyen duong")
    return value


def validate_configs(configs: list[dict], check_assets: bool = False) -> list[dict]:
    seen = set()
    for char in configs:
        char_id = _positive_int(char.get("id"), "id")
        if char_id <= 114:
            raise ValueError(f"ID tuy bien phai lon hon 114: {char_id}")
        if char_id in seen:
            raise ValueError(f"trung ID {char_id}")
        seen.add(char_id)
        if not str(char.get("name", "")).strip():
            raise ValueError(f"nhan vat {char_id} thieu name")
        expected_filename = f"ally_{char_id}"
        if char.get("filename") != expected_filename:
            raise ValueError(f"filename cua {char_id} phai la {expected_filename}")
        if char.get("feature") not in FEATURES:
            raise ValueError(f"feature khong ho tro: {char.get('feature')}")
        if char.get("attackType") not in ATTACK_TYPES:
            raise ValueError(f"attackType khong ho tro: {char.get('attackType')}")
        if not 1 <= _positive_int(char.get("star"), "star") <= 9:
            raise ValueError("star phai nam trong 1..9")

        for section, keys in {
            "size": ("width", "height"),
            "fireSize": ("width", "height"),
            "frames": ("wait", "move", "attack", "beattack", "fire"),
            "combat": ("attackFireFrame", "attackLength", "moveSpeed", "attackSpeed"),
            "stats": ("apStart", "apEnd", "hpStart", "hpEnd", "mineralStart",
                      "mineralEnd", "maxLevel"),
            "layout": ("centerX", "centerY", "gagebarX", "gagebarY"),
        }.items():
            values = char.get(section)
            if not isinstance(values, dict):
                raise ValueError(f"nhan vat {char_id} thieu {section}")
            for key in keys:
                if key not in values or not isinstance(values[key], (int, float)):
                    raise ValueError(f"nhan vat {char_id} thieu {section}.{key}")

        skills = char.get("specialAbilities", [])
        innate = char.get("innateAbilities", [])
        unknown = [skill for skill in skills if skill not in SPECIAL_ABILITIES]
        unknown += [skill for skill in innate if skill not in INNATE_ABILITIES]
        if unknown:
            raise ValueError(f"skill khong ho tro: {', '.join(unknown)}")
        parameters = char.get("skillParameters", {})
        for skill in skills:
            required = REQUIRED_SKILL_PARAMETERS.get(skill)
            if required and required not in parameters:
                raise ValueError(f"skill {skill} can skillParameters.{required}")

        if check_assets:
            validate_assets(char)
    return configs


def validate_assets(char: dict) -> None:
    folder = ASSET_ROOT / f"ally_{char['id']}"
    prefix = char["filename"]
    body_size = (int(char["size"]["width"]), int(char["size"]["height"]))
    fire_size = (int(char["fireSize"]["width"]), int(char["fireSize"]["height"]))
    for action in ("wait", "move", "attack", "beattack", "fire"):
        count = int(char["frames"][action])
        for frame in range(1, count + 1):
            if action == "fire" and count == 1:
                name = f"{prefix}_fire.png"
            else:
                name = f"{prefix}_{action}_{10 + frame}.png"
            path = folder / name
            if not path.is_file():
                raise ValueError(f"thieu asset: {path.relative_to(ROOT)}")
            expected = fire_size if action == "fire" else body_size
            actual = read_png_size(path)
            if actual != expected:
                raise ValueError(f"sai kich thuoc {name}: {actual}, can {expected}")

    portrait = ROOT / "ELDORADO_WEB" / "source_20240722" / "image" / "ui" / "4_game" / "char" / f"ga_ally_{char['id']}.jpg"
    common = ROOT / "ELDORADO_WEB" / "source_20240722" / "image" / "ui" / "0_common" / f"co_ch{char['id']}.png"
    for path in (portrait, common):
        if not path.is_file():
            raise ValueError(f"thieu asset UI: {path.relative_to(ROOT)}")


def generated_text(configs: list[dict]) -> str:
    clean = []
    for char in configs:
        clean.append({key: value for key, value in char.items() if not key.startswith("_")})
    payload = json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=True)
    return "/* Sinh tu character_workshop/characters/*.json - khong sua tay. */\n" \
           f"window.BUSIDOL_CUSTOM_CHARACTERS = {payload};\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build nhan vat tuy bien Busidol")
    parser.add_argument("--check", action="store_true", help="chi kiem tra, khong ghi file")
    args = parser.parse_args()
    configs = validate_configs(load_configs(), check_assets=True)
    text = generated_text(configs)
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != text:
            raise ValueError("registry generated da cu; chay build_characters.py")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print("Custom characters OK: " + ", ".join(f"{c['name']} ({c['id']})" for c in configs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

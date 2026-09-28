# Character Workshop

Thu muc nay la lop nen de tao nhan vat moi cho Busidol Offline ma khong phai sua truc tiep bundle game lon.

Nhan vat mau hien co la `ASTRA` voi ID `115`. Ban co the sao chep `characters/astra.json`, doi ID va asset tuong ung, roi chay build de game tu nap nhan vat moi.

## Cach tao nhan vat moi

1. Sao chep file cau hinh trong `character_workshop/characters/`, vi du `astra.json`.
2. Chon `id` moi lon hon `114`, vi cac nhan vat goc dang dung khoang `1..114`.
3. Dat `filename` dung mau `ally_<id>`, vi du ID `116` thi dung `ally_116`.
4. Tao thu muc asset battle:

```text
ELDORADO_WEB/source_20240722/image/char/ally_<id>/
```

5. Dat du asset theo ten:

```text
ally_<id>_wait_11.png
ally_<id>_wait_12.png
ally_<id>_wait_13.png
ally_<id>_wait_14.png
ally_<id>_move_11.png
ally_<id>_move_12.png
ally_<id>_move_13.png
ally_<id>_move_14.png
ally_<id>_attack_11.png
ally_<id>_attack_12.png
ally_<id>_attack_13.png
ally_<id>_attack_14.png
ally_<id>_beattack_11.png
ally_<id>_beattack_12.png
ally_<id>_beattack_13.png
ally_<id>_beattack_14.png
ally_<id>_fire_11.png
ally_<id>_fire_12.png
ally_<id>_fire_13.png
ally_<id>_fire_14.png
```

6. Tao du asset UI:

```text
ELDORADO_WEB/source_20240722/image/ui/0_common/co_ch<id>.png
ELDORADO_WEB/source_20240722/image/ui/4_game/char/ga_ally_<id>.jpg
```

7. Chinh chi so trong `stats`, animation trong `frames`, thong so chien dau trong `combat`, va skill trong `specialAbilities`.
8. Chay `character_workshop/BUILD.bat`, hoac lenh:

```powershell
python character_workshop\build_characters.py
```

Build thanh cong se cap nhat:

```text
ELDORADO_WEB/custom_characters/custom_characters.generated.js
```

Khong sua tay file generated nay; hay sua JSON roi build lai.

## Kich thuoc asset

Theo nhan vat mau:

- Sprite than nhan vat: PNG trong suot `256x256`.
- Sprite dan/skill bay (`fire`): PNG trong suot `128x128`.
- Moi nhom animation hien dang co 4 frame: `Wait`, `Move`, `Attack`, `BeAttack`, `Fire`.

Neu muon doi kich thuoc, sua `size` hoac `fireSize` trong JSON. Build se kiem tra file PNG co dung kich thuoc va co kenh alpha.

## Chinh chi so

Trong `stats`:

- `apStart`, `apEnd`: cong dau va cong toi da.
- `hpStart`, `hpEnd`: mau dau va mau toi da.
- `mineralStart`, `mineralEnd`: gia trieu hoi dau va cuoi.
- `maxLevel`: cap toi da.

Trong `combat`:

- `attackFireFrame`: frame bat dau tao dan/skill.
- `attackLength`: tam danh.
- `moveSpeed`: toc do di chuyen.
- `attackSpeed`: toc do danh.

## Skill dac biet

`specialAbilities` hien ho tro cac ma co san trong engine:

```text
FORTITUDE, INSTANT_KILL, PVP_TEAM_DAMAGE_REDUCTION, PVP_CHAR_SEAL,
PVP_HP_AP_UP, PVP_TOWER_DAMAGE, PVP_TOWER_SHIELD, PVP_SCORE_UP,
ARMOR, ONESHOT, OSOK_IMM, OSOK_CHANCE, MOVE_INV, CAN_ABS,
SLOW_DOWN, PUSH, GM_SA_DEF, STG_BURN_INC, CB_DMG, SNAKE_BIND,
COLD_AURA, ENHANCED_HEALER, TORTOISE_SPIRIT, VALOR_BUGLE,
PVP_TOWER_HP_HEAL_DOWN, CUR_HP_DAMAGE, STEALTH, SPRINT
```

Mot so skill can them tham so trong `skillParameters`:

```text
PUSH -> push_per
INSTANT_KILL -> instant_kill_per
FORTITUDE -> fortitude_per
CUR_HP_DAMAGE -> cur_hp_damage_per
STEALTH -> stealth_per
SNAKE_BIND -> snake_bind_duration
COLD_AURA -> cold_slow_per
ENHANCED_HEALER -> summon_heal_per
TORTOISE_SPIRIT -> tortoise_buff_per
VALOR_BUGLE -> valor_bugle_per
```

Vi du ASTRA:

```json
"specialAbilities": ["PUSH"],
"skillParameters": {
  "push_per": 30
}
```

`innateAbilities` hien ho tro:

```text
PUSH_IMM, DIGNITY_IMM, TIME_STOP_IMM, INSTANT_KILL_IMM, FREEZE_IMM,
SLOW_IMM, BURN_IMM, OSOK_IMM, TF_ATTACK_UPGRADE, ARMOR,
TORTOISE_AP_BUFF, MULTI_HIT, ANGRY_BURN_IMM, CHAOS_GALE_IMM
```

Luu y: cac skill tren la hanh vi da co san trong engine. Neu muon tao hanh vi hoan toan moi, can them code cho engine/runtime, khong chi them JSON.

## Kiem tra nhanh

```powershell
python character_workshop\build_characters.py --check
python -m unittest -v TESTS.test_custom_characters
node --check ELDORADO_WEB\custom_characters\custom_character_runtime.js
node --check ELDORADO_WEB\custom_characters\custom_characters.generated.js
```

Neu co Playwright, co the chay them test browser khi server game dang mo o `http://127.0.0.1:18066`:

```powershell
node TESTS\test_custom_character_ui.mjs
```


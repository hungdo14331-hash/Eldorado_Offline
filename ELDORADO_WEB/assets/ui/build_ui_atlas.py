#!/usr/bin/env python3
"""Cong cu build sprite atlas "Style Anchor v1" cho RubyFarm.

Luong:  atlas/rubyfarm_anchor_v1.png --(--measure)--> atlas.json --> ui_atlas.css

  python build_ui_atlas.py --measure   # do sheet: ghi atlas.json + atlas/derived/*.png, in bao cao
  python build_ui_atlas.py             # doc atlas.json, kiem tra lai, ghi ui_atlas.css
  python build_ui_atlas.py --check     # chi kiem tra atlas.json voi sheet, khong ghi gi
  python build_ui_atlas.py --parity    # doi chieu CSS dung co voi atlas.json (khong sua gi)

atlas.json la source of truth cho toa do sprite. KHONG sua tay ui_atlas.css.
approved_mapping trong atlas.json = bang 12 asset da duoc nguoi dung chot (x,y top-left,
w,h kich thuoc that); core/box = so do tuong ung sau khi loc nhieu (alpha>16, bo dom rac)
+ dem chong bleed (PAD). Lech giua hai nguon duoc gioi han va kiem tra bang --parity.
Chi can Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SHEET_FILE = HERE / "atlas" / "rubyfarm_anchor_v1.png"
ATLAS_FILE = HERE / "atlas.json"
CSS_FILE = HERE / "ui_atlas.css"
DERIVED_DIR = HERE / "atlas" / "derived"

SHEET_W, SHEET_H = 1448, 1086  # kich thuoc sheet da xac nhan truoc do
CORE_T = 16    # nguong alpha de nhan dien "ruot" asset
MIN_AREA = 40  # bo qua dom rac nho hon (px)
PAD = 2        # dem quanh bbox ruot (px nguon) — ly do cu the: chong bleed khi scale nho
GAP_SPLIT = 6  # dai trong >= 6 px (khong co pixel ruot) thi tach band/o

# Thu tu doc: band 1..4, trai sang phai. Dung de dat ten + kiem tra so luong.
EXPECTED_ROWS = [5, 3, 2, 2]
NAMES = [
    ["res_gold", "res_ruby", "res_bp", "res_cloud", "res_ticket"],
    ["game_gold_mine", "game_memory", "game_sudoku"],
    ["frame_hud", "btn_primary"],
    ["card_game", "panel_wallet"],
]
# Bang chot cua nguoi dung: bao gom (x0,y0)-(x1,y1) va w,h = kich thuoc that.
# Day la du lieu tham chieu; toa do can thuc thi nam o core/box.
APPROVED_MAPPING = {
    "res_gold":       {"x0": 80,  "y0": 30,  "x1": 297,  "y1": 247,  "w": 218, "h": 218},
    "res_ruby":       {"x0": 353, "y0": 26,  "x1": 557,  "y1": 249,  "w": 205, "h": 224},
    "res_bp":         {"x0": 609, "y0": 22,  "x1": 806,  "y1": 253,  "w": 198, "h": 232},
    "res_cloud":      {"x0": 851, "y0": 44,  "x1": 1107, "y1": 250,  "w": 257, "h": 207,
                       "note": "Bang chot loai spark tach roi tren dinh cua o (khong gom vao bbox). "
                               "Core do lai co chua spark do (34..250) va la co so CSS chinh thuc."},
    "res_ticket":     {"x0": 1136, "y0": 41, "x1": 1393, "y1": 251,  "w": 258, "h": 211},
    "game_gold_mine": {"x0": 192, "y0": 282, "x1": 521,  "y1": 549,  "w": 330, "h": 268},
    "game_memory":    {"x0": 565, "y0": 292, "x1": 880,  "y1": 546,  "w": 316, "h": 255},
    "game_sudoku":    {"x0": 927, "y0": 273, "x1": 1254, "y1": 546,  "w": 328, "h": 274},
    "frame_hud":      {"x0": 68,  "y0": 571, "x1": 731,  "y1": 690,  "w": 664, "h": 120},
    "btn_primary":    {"x0": 789, "y0": 560, "x1": 1377, "y1": 702,  "w": 589, "h": 143},
    "card_game":      {"x0": 28,  "y0": 711, "x1": 620,  "y1": 1047, "w": 593, "h": 337},
    "panel_wallet":   {"x0": 660, "y0": 712, "x1": 1420, "y1": 1052, "w": 761, "h": 341},
}
# Chong ble cho truoc: lech gioi han giua approved_mapping va core sau loc nhieu (px).
APPROVED_TOLERANCE = 3

# Chi cat file rieng cho asset dung ngoai atlas. Prototype 1 chi dung card_game
# lam anh rieng (banner the game, can co aspect responsive); cac asset khac dung
# truc tiep tu atlas.
DERIVED = ["card_game"]
# Asset can do "tinh deo vien" de quyet dinh 9-slice (khong phai asset nao cung cat).
STRIP_REPORT = ["frame_hud", "btn_primary", "card_game", "panel_wallet"]
REPORT_B_INSETS = (16, 24, 32, 48)

# Class CSS can sinh ra (quyet dinh thiet ke, khong do tu sheet).
# Moi target: "h" = chieu cao px, hoac "fit" = [rong, cao] hop can vua;
# "media" = "" (mac dinh) hoac dieu kien @media. Chieu rong do generator tinh.
# "fit" la rang buoc CUNG cho phan art (ruot): phan tu co the rong hon vai px
# trong suot do lech lam tron, nhung pixel that khong duoc vuot qua hop.
CSS_TARGETS = {
    "res_gold":   [{"class": "sp-res-gold",   "h": 22, "media": ""},
                   {"class": "sp-res-gold",   "h": 18, "media": "(max-width:900px)"}],
    "res_ruby":   [{"class": "sp-res-ruby",   "h": 22, "media": ""},
                   {"class": "sp-res-ruby",   "h": 18, "media": "(max-width:900px)"}],
    "res_bp":     [{"class": "sp-res-bp",     "h": 22, "media": ""},
                   {"class": "sp-res-bp",     "h": 18, "media": "(max-width:900px)"}],
    "res_cloud":  [{"class": "sp-res-cloud",  "h": 22, "media": ""},
                   {"class": "sp-res-cloud",  "h": 18, "media": "(max-width:900px)"}],
    "res_ticket": [{"class": "sp-res-ticket", "h": 22, "media": ""},
                   {"class": "sp-res-ticket", "h": 18, "media": "(max-width:900px)"}],
    "game_gold_mine": [{"class": "sp-nav-catch",    "fit": [22, 22], "media": ""},
                       {"class": "sp-nav-catch",    "fit": [19, 19], "media": "(max-width:1024px)"},
                       {"class": "sp-game-gold-mine", "fit": [40, 40], "media": ""},
                       {"class": "sp-game-gold-mine", "fit": [34, 34], "media": "(max-width:900px)"}],
    "game_memory":    [{"class": "sp-nav-memory", "fit": [22, 22], "media": ""},
                       {"class": "sp-nav-memory", "fit": [19, 19], "media": "(max-width:1024px)"}],
    "game_sudoku":    [{"class": "sp-nav-sudoku", "fit": [22, 22], "media": ""},
                       {"class": "sp-nav-sudoku", "fit": [19, 19], "media": "(max-width:1024px)"}],
    "frame_hud":      [{"class": "sp-frame-hud", "fit": [560, 120], "media": ""}],
    "btn_primary":    [{"class": "sp-btn-primary", "h": 36, "media": ""}],
}


def die(msg: str) -> "None":
    print("LOI: " + msg, file=sys.stderr)
    raise SystemExit(1)


def load_sheet():
    if not SHEET_FILE.is_file():
        die(f"khong thay {SHEET_FILE}")
    img = Image.open(SHEET_FILE)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if img.size != (SHEET_W, SHEET_H):
        die(f"sheet {img.size} khac mong doi {(SHEET_W, SHEET_H)}")
    raw = img.tobytes()
    alpha = raw[3::4]  # bytes, dai W*H
    return img, raw, alpha


def runs_empty(flags, min_gap):
    """Tra ve (start, end) cua cac doan lien tiep 'co noi dung' (flags[i] != 0)."""
    segs, start = [], None
    for i, v in enumerate(flags):
        if v and start is None:
            start = i
        elif not v and start is not None:
            segs.append((start, i))
            start = None
    if start is not None:
        segs.append((start, len(flags)))
    # gop 2 doan cach nhau < min_gap (nhieu kha nang cung mot khoi)
    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] < min_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def core_flags(alpha, w, h):
    has = bytearray(w * h)
    t = CORE_T
    for i, v in enumerate(alpha):
        if v > t:
            has[i] = 1
    return has


def rect_max_alpha(alpha, w, x0, y0, x1, y1):
    m = 0
    for y in range(y0, y1):
        row = alpha[y * w + x0 : y * w + x1]
        if row:
            v = max(row)
            if v > m:
                m = v
    return m


def components(has, w, x0, y0, x1, y1):
    """Connected component (8 huong) tren mask 'has' trong hinh chu nhat."""
    seen = set()
    comps = []
    for yy in range(y0, y1):
        base = yy * w
        for xx in range(x0, x1):
            i = base + xx
            if not has[i] or i in seen:
                continue
            stack = [i]
            seen.add(i)
            n = 0
            bx0 = bx1 = xx
            by0 = by1 = yy
            while stack:
                j = stack.pop()
                jy, jx = divmod(j, w)
                n += 1
                if jx < bx0: bx0 = jx
                if jx > bx1: bx1 = jx
                if jy < by0: by0 = jy
                if jy > by1: by1 = jy
                for dy in (-1, 0, 1):
                    ny = jy + dy
                    if ny < y0 or ny >= y1:
                        continue
                    for dx in (-1, 0, 1):
                        nx = jx + dx
                        if nx < x0 or nx >= x1:
                            continue
                        k = ny * w + nx
                        if has[k] and k not in seen:
                            seen.add(k)
                            stack.append(k)
            comps.append({"area": n, "box": (bx0, by0, bx1 + 1, by1 + 1)})
    comps.sort(key=lambda c: -c["area"])
    return comps


def luma_at(raw, i):
    r = raw[4 * i]
    g = raw[4 * i + 1]
    b = raw[4 * i + 2]
    return (r * 299 + g * 587 + b * 114) // 1000


def strip_stats(raw, alpha, w, bx0, by0, bx1, by1, inset):
    """Do "tinh deo" cua vien 9-slice tai inset cho truoc.

    - top/bottom: do lech chuan luma theo hang (mong muon thap = keo ngang khong vo).
    - left/right: do lech chuan luma theo cot (mong muon thap = keo doc khong vo).
    - center: ca hai huong.
    Tra ve dict so lieu + co dat nguong khong.
    """
    def line_std(pixels):
        vals = [luma_at(raw, i) for i, a in pixels if a > 8]
        if len(vals) < 2:
            return 0.0
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        return var ** 0.5

    def row_std(y, x0, x1):
        return line_std(((y * w + x, alpha[y * w + x]) for x in range(x0, x1)))

    def col_std(x, y0, y1):
        return line_std(((y * w + x, alpha[y * w + x]) for y in range(y0, y1)))

    cx0, cy0, cx1, cy1 = bx0 + inset, by0 + inset, bx1 - inset, by1 - inset
    out = {}
    if cx1 <= cx0 or cy1 <= cy0:
        return None
    out["top"] = max(row_std(y, cx0, cx1) for y in range(by0, cy0))
    out["bottom"] = max(row_std(y, cx0, cx1) for y in range(cy1, by1))
    out["left"] = max(col_std(x, cy0, cy1) for x in range(bx0, cx0))
    out["right"] = max(col_std(x, cy0, cy1) for x in range(cx1, bx1))
    out["center_row"] = max(row_std(y, cx0, cx1) for y in range(cy0, cy1))
    out["center_col"] = max(col_std(x, cy0, cy1) for x in range(cx0, cx1))
    return out


def verify_approved(atlas):
    """approved_mapping (bang nguoi dung chot) phai khong bao gio cach core qua luong.

    Lech > APPENDED_TOLERANCE chi duoc cho qua khi entry co note ghi ro ly do cu the;
    note duoc in ra de nguoi doc tu dong hieu, khong co nghia la bo sang.
    """
    approved = atlas.get("approved_mapping")
    bad = []
    if not approved:
        bad.append("thieu approved_mapping trong atlas.json")
        return bad
    for s in atlas["sprites"]:
        a = approved.get(s["name"])
        if not a:
            bad.append(f"{s['name']}: khong co trong approved_mapping")
            continue
        c, b = s["core"], s["box"]
        # approved dung quy uoc x,y top-left, w,h = mau x1-x0+1, y1-y0+1
        aw, ah = a["x1"] - a["x0"] + 1, a["y1"] - a["y0"] + 1
        aok = True
        for label, va, vc in (("x", a["x0"], c["x"]), ("y", a["y0"], c["y"]),
                              ("w", aw, c["w"]), ("h", ah, c["h"])):
            if abs(va - vc) > APPROVED_TOLERANCE:
                aok = False
                print(f"  INFO {s['name']}.{label}: approved {va} vs core {vc} lech {abs(va-vc)}px")
        if aw != a["w"] or ah != a["h"]:
            bad.append(f"{s['name']}: w/h trong approved khong khop ({a['w']}x{a['h']} vs tinh lai {aw}x{ah})")
        if not aok and "note" not in a:
            bad.append(f"{s['name']}: lech approved vs core > {APPROVED_TOLERANCE}px ma khong co note giai thich")
        elif not aok and "note" in a:
            print(f"  GHI CHU {s['name']}: {a['note']}")
    return bad


# ---------------------------------------------------------------- measure ----
def measure(args):
    img, raw, alpha = load_sheet()
    w, h = img.size
    print(f"sheet  : {SHEET_FILE.name} {w}x{h} mode={img.mode}")
    print(f"sha256 : {hashlib.sha256(SHEET_FILE.read_bytes()).hexdigest()}")
    has = core_flags(alpha, w, h)

    row_flags = [max(has[y * w : (y + 1) * w]) for y in range(h)]
    bands = runs_empty(row_flags, GAP_SPLIT)
    print(f"\nband theo hang (alpha>{CORE_T}): {[b for b in bands]}")
    if len(bands) != len(EXPECTED_ROWS):
        die(f"thay {len(bands)} band, mong doi {len(EXPECTED_ROWS)}")

    sprites = []
    problems = []
    for bi, (by0, by1) in enumerate(bands):
        col_flags = [1 if max(has[y * w + x] for y in range(by0, by1)) else 0 for x in range(w)]
        cells = runs_empty(col_flags, GAP_SPLIT)
        print(f"  band {bi + 1} y[{by0},{by1}) -> {len(cells)} o: {cells}")
        if len(cells) != EXPECTED_ROWS[bi]:
            die(f"band {bi + 1} co {len(cells)} o, mong doi {EXPECTED_ROWS[bi]}")
        for ci, (cx0, cx1) in enumerate(cells):
            name = NAMES[bi][ci]
            comps = components(has, w, cx0, by0, cx1, by1)
            kept = [c for c in comps if c["area"] >= MIN_AREA]
            dropped = [c for c in comps if c["area"] < MIN_AREA]
            if not kept:
                die(f"{name}: khong co component nao >= {MIN_AREA} px")
            kx0 = min(c["box"][0] for c in kept)
            ky0 = min(c["box"][1] for c in kept)
            kx1 = max(c["box"][2] for c in kept)
            ky1 = max(c["box"][3] for c in kept)
            core = {"x": kx0, "y": ky0, "w": kx1 - kx0, "h": ky1 - ky0}
            box = {"x": core["x"] - PAD, "y": core["y"] - PAD,
                   "w": core["w"] + 2 * PAD, "h": core["h"] + 2 * PAD}
            if box["x"] < 0 or box["y"] < 0 or box["x"] + box["w"] > w or box["y"] + box["h"] > h:
                die(f"{name}: bbox {box} vuot ra ngoai sheet")
            # halo: vung alpha>0 trong o nay (de bao cao, khong cat theo)
            hx0 = hx1 = hy0 = hy1 = None
            for y in range(by0, by1):
                base = y * w
                for x in range(cx0, cx1):
                    if alpha[base + x]:
                        if hx0 is None or x < hx0: hx0 = x
                        if hx1 is None or x > hx1: hx1 = x
                        if hy0 is None or y < hy0: hy0 = y
                        if hy1 is None or y > hy1: hy1 = y
            halo_outside = 0
            halo_outside_max = 0
            for y in range(hy0, hy1 + 1):
                base = y * w
                for x in range(hx0, hx1 + 1):
                    a = alpha[base + x]
                    if a and not (box["x"] <= x < box["x"] + box["w"] and box["y"] <= y < box["y"] + box["h"]):
                        halo_outside += 1
                        if a > halo_outside_max:
                            halo_outside_max = a
            sprites.append({
                "name": name,
                "cell": {"x": cx0, "y": by0, "w": cx1 - cx0, "h": by1 - by0},
                "core": core,
                "box": box,
                "css": CSS_TARGETS.get(name, []),
                "components": [{"area": c["area"], "box": list(c["box"])} for c in comps],
                "dropped_specks": [{"area": c["area"], "box": list(c["box"])} for c in dropped],
                "halo": {"x": hx0, "y": hy0, "x1": hx1, "y1": hy1,
                         "outside_box_px": halo_outside, "outside_box_max_alpha": halo_outside_max},
            })
            print(f"    {name:15s} core=({core['x']},{core['y']},{core['w']},{core['h']}) "
                  f"box=({box['x']},{box['y']},{box['w']},{box['h']}) comps={len(comps)} "
                  f"kept={len(kept)} speck={len(dropped)} "
                  f"halo_outside={halo_outside}px maxA={halo_outside_max}")

    # ---- kiem tra bat buoc ----
    print("\nKIEM TRA:")
    for s in sprites:
        b, c = s["box"], s["core"]
        ok_inside = b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["w"] <= w and b["y"] + b["h"] <= h
        print(f"  [{'ok' if ok_inside else 'FAIL'}] {s['name']}: box nam trong {w}x{h}")
        if not ok_inside:
            problems.append(f"{s['name']}: box ngoai sheet")
    for i in range(len(sprites)):
        for j in range(i + 1, len(sprites)):
            a, b = sprites[i]["box"], sprites[j]["box"]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            overlap = ox > 0 and oy > 0
            if overlap:
                problems.append(f"{sprites[i]['name']} va {sprites[j]['name']}: box overlap {ox}x{oy}px")
    # padding khong duoc cham vao asset khac: box cua asset i khong giao core cua asset j
    for i, s in enumerate(sprites):
        for j, t in enumerate(sprites):
            if i == j:
                continue
            a, c = s["box"], t["core"]
            if (a["x"] < c["x"] + c["w"] and c["x"] < a["x"] + a["w"]
                    and a["y"] < c["y"] + c["h"] and c["y"] < a["y"] + a["h"]):
                problems.append(f"padding cua {s['name']} cham vao core cua {t['name']}")
    if problems:
        print("\nVAN DE:")
        for p in problems:
            print("  - " + p)
        die("kiem tra bbox that bai, khong ghi atlas.json")

    # ---- phan tich vien cho quyet dinh 9-slice ----
    print("\nPHAN TICH VIEN (do lech chuan luma; thap = deo duoc, 0 = phang):")
    derived_info = {}
    for s in sprites:
        if s["name"] not in STRIP_REPORT:
            continue
        b = s["box"]
        x0, y0, x1, y1 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
        info = {}
        for B in REPORT_B_INSETS:
            st = strip_stats(raw, alpha, w, x0, y0, x1, y1, B)
            if st:
                info[B] = {k: round(v, 2) for k, v in st.items()}
                print(f"  {s['name']:14s} B={B:3d}  top={st['top']:6.2f} bottom={st['bottom']:6.2f} "
                      f"left={st['left']:6.2f} right={st['right']:6.2f} "
                      f"c_row={st['center_row']:6.2f} c_col={st['center_col']:6.2f}")
        derived_info[s["name"]] = info

    # ---- ghi derived crops ----
    DERIVED_DIR.mkdir(exist_ok=True)
    for s in sprites:
        if s["name"] not in DERIVED:
            continue
        b = s["box"]
        crop = img.crop((b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]))
        out = DERIVED_DIR / f"{s['name']}.png"
        crop.save(out)
        print(f"  ghi {out.relative_to(HERE)} {crop.size}")

    atlas = {
        "_doc": [
            "Source of truth cho sprite atlas Style Anchor v1 cua RubyFarm.",
            "Toa do do tu atlas/rubyfarm_anchor_v1.png bang: python build_ui_atlas.py --measure",
            "Sinh CSS bang: python build_ui_atlas.py  — KHONG sua tay ui_atlas.css.",
            "box = core + PAD px dem trong suot; core = bbox pixel alpha>%d sau khi bo dom rac." % CORE_T,
            "approved_mapping = bang 12 asset nguoi dung chot (x,y top-left, w,h kich thuoc that).",
            "slice_analysis: do lech chuan luma tung phia tai nhieu inset. Prototype 1 khong dung",
            "  9-slice cho asset nao vi moi phia deu lech chuan > 30 (vien co ornament, khong phang).",
        ],
        "version": 1,
        "sheet": {
            "file": "atlas/rubyfarm_anchor_v1.png",
            "w": w, "h": h,
            "sha256": hashlib.sha256(SHEET_FILE.read_bytes()).hexdigest(),
            "origin": "ChatGPT Image 3.png (Style Anchor v1, 12 asset, khong sua noi dung)",
        },
        "thresholds": {"core_alpha": CORE_T, "min_component_area": MIN_AREA,
                       "pad": PAD, "gap_split": GAP_SPLIT},
        "sprites": sprites,
        "approved_mapping": APPROVED_MAPPING,
        "slice_analysis": derived_info,
    }
    ATLAS_FILE.write_text(json.dumps(atlas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nghi {ATLAS_FILE.name}: {len(sprites)} sprite")


# ------------------------------------------------------------------ check ----
def load_atlas():
    if not ATLAS_FILE.is_file():
        die("chua co atlas.json — chay: python build_ui_atlas.py --measure")
    return json.loads(ATLAS_FILE.read_text(encoding="utf-8"))


def verify_atlas(atlas, img, alpha):
    w, h = img.size
    sprites = atlas["sprites"]
    bad = []
    if atlas["sheet"]["w"] != w or atlas["sheet"]["h"] != h:
        bad.append("kich thuoc sheet trong atlas.json khac anh")
    for s in sprites:
        b, c = s["box"], s["core"]
        if not (0 <= b["x"] and 0 <= b["y"] and b["x"] + b["w"] <= w and b["y"] + b["h"] <= h):
            bad.append(f"{s['name']}: box ngoai sheet")
        if b["x"] > c["x"] or b["y"] > c["y"] or b["x"] + b["w"] < c["x"] + c["w"] or b["y"] + b["h"] < c["y"] + c["h"]:
            bad.append(f"{s['name']}: box khong bao core")
        if b["w"] != c["w"] + 2 * atlas["thresholds"]["pad"] or b["h"] != c["h"] + 2 * atlas["thresholds"]["pad"]:
            bad.append(f"{s['name']}: box khong dung core + pad")
    for i in range(len(sprites)):
        for j in range(i + 1, len(sprites)):
            a, b = sprites[i]["box"], sprites[j]["box"]
            if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                bad.append(f"{sprites[i]['name']} overlap {sprites[j]['name']}")
            c = sprites[j]["core"]
            if (a["x"] < c["x"] + c["w"] and c["x"] < a["x"] + a["w"]
                    and a["y"] < c["y"] + c["h"] and c["y"] < a["y"] + a["h"]):
                bad.append(f"padding cua {sprites[i]['name']} cham core cua {sprites[j]['name']}")
    return bad + verify_approved(atlas)


def solve_axis(pos_core, size_core, pos_box, size_box, sheet_n, target_n, foreign,
               ideal_n_hint=None, max_art=None):
    """Chon (bg_n, pos_px, elem_px) nguyen cho mot truc.

    Yeu cau cung: cua so nguon phai chua tron core, va khong duoc cham pixel
    alpha> CORE_T cua asset khac. Uu tien so px hien thi sat ty le thiet ke
    (ideal_n_hint), roi moi den background-size va vi tri.
    max_art: chan tren cho kich thuoc ART hien thi (px) — phan tu co the rong
    hon do lech lam tron, nhung pixel that thi khong.
    Tra ve dict {bg,pos,elem,window} hoac None.
    """
    scale = target_n / size_box
    bg0 = max(1, round(sheet_n * scale))
    best = None
    for bg in range(max(1, bg0 - 2), bg0 + 3):
        s = bg / sheet_n
        if max_art is not None and size_core * s > max_art + 0.01:
            continue  # art vuot hop cho phep
        ideal_p = pos_box * s
        ideal_n = size_box * s
        n_ref = ideal_n if ideal_n_hint is None else ideal_n_hint
        lo = max(1, int(min(ideal_n, n_ref)) - 3)
        hi = int(max(ideal_n, n_ref)) + 5
        for n in range(lo, hi):
            for p in range(max(0, int(ideal_p) - 2), int(ideal_p) + 4):
                left = p / s
                right = (p + n) / s
                if left > pos_core + 0.01 or right < pos_core + size_core - 0.01:
                    continue  # cat vao core
                if not foreign(left, right):
                    continue
                cost = 2 * abs(n - n_ref) + 0.5 * abs(bg - bg0) + 0.25 * abs(p - ideal_p)
                if best is None or cost < best[0]:
                    best = (cost, bg, p, n, (left, right))
    if best is None:
        return None
    _, bg, p, n, win = best
    return {"bg": bg, "pos": p, "elem": n, "window": win}


def gen_css(atlas, img, alpha):
    w, h = img.size
    pad = atlas["thresholds"]["pad"]
    sprites = {s["name"]: s for s in atlas["sprites"]}
    all_sprites = atlas["sprites"]
    lines = []
    lines.append("/* ui_atlas.css — SINH TU DONG tu atlas.json, khong sua tay.")
    lines.append(" * Chay lai: python build_ui_atlas.py")
    lines.append(f" * Nguon: {atlas['sheet']['file']} ({w}x{h})")
    lines.append(" * Moi class la mot sprite: kich thuoc px + background-size/position da tinh san.")
    lines.append(" */")
    base_media = {}
    derived_media = {}
    problems = []
    for s in all_sprites:
        b, c = s["box"], s["core"]
        targets = s.get("css") or []
        for t in targets:
            if "fit" in t:
                # chon chieu cao lon nhat sao cho ca rong lan cao deu nam trong hop
                fw, fh = t["fit"]
                ar_core = c["w"] / c["h"]
                target_h = next(hh for hh in range(fh, 0, -1) if round(hh * ar_core) <= fw)
            else:
                target_h = t["h"]
                fw = fh = None
            others = [o for o in all_sprites if o is not s]

            def foreign_y(lo, hi):
                # cua so doc [lo,hi) khong duoc cham pixel core cua asset khac
                for o in others:
                    oc = o["core"]
                    if oc["x"] + oc["w"] <= b["x"] or b["x"] + b["w"] <= oc["x"]:
                        continue
                    if rect_max_alpha(alpha, w, max(oc["x"], b["x"]), int(max(lo, oc["y"])),
                                      min(oc["x"] + oc["w"], b["x"] + b["w"]), int(min(hi, oc["y"] + oc["h"]))) > CORE_T:
                        return False
                return True

            def foreign_x(lo, hi):
                for o in others:
                    oc = o["core"]
                    if oc["y"] + oc["h"] <= b["y"] or b["y"] + b["h"] <= oc["y"]:
                        continue
                    if rect_max_alpha(alpha, w, int(max(lo, oc["x"])), max(oc["y"], b["y"]),
                                      int(min(hi, oc["x"] + oc["w"])), min(oc["y"] + oc["h"], b["y"] + b["h"])) > CORE_T:
                        return False
                return True

            ay = solve_axis(b["y"], b["h"], b["y"], b["h"], h, target_h,
                            lambda lo, hi: foreign_y(lo, hi), ideal_n_hint=target_h, max_art=fh)
            if ay is None:
                problems.append(f"{s['name']} h={target_h}: khong tim duoc hinh hoc doc an toan")
                continue
            scale_y = ay["bg"] / h
            ideal_w = ay["elem"] * c["w"] / c["h"]  # rong px giu dung ty le core
            # Truyen thang scale truc y (chua lam tron) lam dich cho truc x: lam tron
            # truoc khi suy background-size se khuech dai sai so ty le len ~3% voi sprite nho.
            ax = solve_axis(b["x"], b["w"], b["x"], b["w"], w, b["w"] * scale_y,
                            lambda lo, hi: foreign_x(lo, hi), ideal_n_hint=ideal_w, max_art=fw)
            if ax is None:
                problems.append(f"{s['name']} h={target_h}: khong tim duoc hinh hoc ngang an toan")
                continue
            cls = t["class"]
            sel = f".{cls}"
            body = (f"{sel}{{width:{ax['elem']}px;height:{ay['elem']}px;"
                    f"background-size:{ax['bg']}px {ay['bg']}px;"
                    f"background-position:-{ax['pos']}px -{ay['pos']}px}}")
            media = t.get("media")
            if media:
                derived_media.setdefault(media, []).append(body)
            else:
                base_media.setdefault("", []).append(body)
            # bao cao do lech ty le
            src_ar = c["w"] / c["h"]
            out_ar = ax["elem"] / ay["elem"]
            if abs(out_ar - src_ar) / src_ar > 0.03:
                problems.append(f"{cls}: ty le {out_ar:.3f} lech {abs(out_ar - src_ar) / src_ar * 100:.1f}% so voi core {src_ar:.3f}")
    if problems:
        print("CANH BAO HINH HOC:")
        for p in problems:
            print("  - " + p)

    out = list(lines)
    out.append(".sp{background-repeat:no-repeat;display:inline-block;flex:none;background-image:url(\"%s\")}"
               % atlas["sheet"]["file"])
    out.extend(base_media.get("", []))
    for media, rules in derived_media.items():
        out.append(f"@media {media}{{")
        out.extend(rules)
        out.append("}")
    out.append("")
    return "\n".join(out), problems


# ------------------------------------------------------------------ parity ----
def parity(atlas, img, alpha):
    """Doi chieu ui_atlas.css dang co voi atlas.json 100% (khong sua gi)."""
    css_text, problems = gen_css(atlas, img, alpha)
    on_disk = CSS_FILE.read_text(encoding="utf-8") if CSS_FILE.is_file() else ""
    ok = True
    if on_disk != css_text:
        ok = False
        print("PARITY FAIL: ui_atlas.css khong khop voi atlas.json (CSS sua tay hay JSON doi doi).")
    else:
        print("PARITY ok: ui_atlas.css 100% khop voi atlas.json")
    print(f"  quy tac css: {css_text.count('.sp-')} class sprite")
    bad_approved = verify_approved(atlas)
    if bad_approved:
        ok = False
        print("PARITY FAIL (approved_mapping):")
        for b in bad_approved:
            print("  - " + b)
    else:
        for s in atlas["sprites"]:
            a = atlas["approved_mapping"][s["name"]]
            c = s["core"]
            print(f"  {s['name']:15s} approved=({a['w']}x{a['h']} @ {a['x0']},{a['y0']}) "
                  f"core=({c['w']}x{c['h']} @ {c['x']},{c['y']})")
    if not ok:
        die("parity that bai")
    print("parity tong: ok")


def main():
    ap = argparse.ArgumentParser(description="Build sprite atlas cho RubyFarm (Style Anchor v1)")
    ap.add_argument("--measure", action="store_true", help="do sheet va ghi atlas.json + derived crops")
    ap.add_argument("--check", action="store_true", help="chi kiem tra atlas.json voi sheet")
    ap.add_argument("--parity", action="store_true", help="doi chieu ui_atlas.css dung co voi atlas.json")
    args = ap.parse_args()

    if args.measure:
        measure(args)
        args.check = True

    img, raw, alpha = load_sheet()
    atlas = load_atlas()
    bad = verify_atlas(atlas, img, alpha)
    if bad:
        print("KIEM TRA THAT BAI:")
        for b in bad:
            print("  - " + b)
        die("atlas.json khong nhat quan voi sheet")
    print(f"kiem tra atlas.json: ok ({len(atlas['sprites'])} sprite, box trong sheet, khong overlap, padding sach, approved_mapping khop)")

    if args.parity:
        parity(atlas, img, alpha)
    elif not args.check:
        css_text, problems = gen_css(atlas, img, alpha)
        CSS_FILE.write_text(css_text, encoding="utf-8")
        print(f"ghi {CSS_FILE.name}: {css_text.count('.sp-')} class sprite")


if __name__ == "__main__":
    main()
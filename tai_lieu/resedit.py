#!/usr/bin/env python3
"""Chinh tai nguyen offline (gold / ruby / level) trong offline_save.json.

Cach dung:
  python resedit.py                 # xem so du hien tai
  python resedit.py --show          # xem so du hien tai
  python resedit.py gold=999999999 ruby=99999 level=50
  python resedit.py level=99

DATA1 (chuoi CSV do game luu) co:
  [1]=gold  [2]=ruby  [8]=level

BP (diem thuong mua gacha 75/450/2700 - "gói BP") la field
rieng cua server (khong nam trong DATA1):
  bp
"""
import json
import shutil
import sys
from pathlib import Path

SAVE = Path(__file__).resolve().parent / "offline_save.json"
FIELDS = {"gold": 1, "ruby": 2, "level": 8}
# bp + autoplay... chi luu cap-top trong save (khong thuoc DATA1)
SERVER_FIELDS = {"bp"}


def current(data1):
    d1 = data1.split(",")
    out = {}
    for k, i in FIELDS.items():
        if 0 <= i < len(d1):
            out[k] = d1[i]
    return out


def main():
    args = sys.argv[1:]
    if not SAVE.exists():
        print("Chua co offline_save.json - hay chay game 1 lan de tao save truoc.")
        return 1
    data = json.loads(SAVE.read_text(encoding="utf-8"))
    d1 = (data.get("DATA1") or "").split(",")
    if len(d1) <= max(FIELDS.values()):
        print("DATA1 khong hop le (qua ngan).")
        return 1

    edits = []
    server_edits = {}
    for a in args:
        if not a.startswith("--") and "=" in a:
            k, v = a.split("=", 1)
            k = k.strip().lower()
            try:
                num = int(float(v))
            except ValueError:
                print("So khong hop le: %r" % v)
                continue
            if k in FIELDS:
                if k == "level" and num < 1:
                    num = 1
                edits.append((k, num))
            elif k in SERVER_FIELDS:
                server_edits[k] = str(num)
            else:
                print("Khong biet key %r (ho tro: gold, ruby, level, bp)." % k)

    if not edits and not server_edits:
        cur = current(",".join(d1))
        print("Tai nguyen hien tai: gold=%s ruby=%s level=%s bp=%s" % (
            cur.get("gold"), cur.get("ruby"), cur.get("level"),
            data.get("bp", "0" if not data else "none")))
        return 0

    bak = SAVE.with_suffix(".json.bak")
    shutil.copy2(SAVE, bak)
    for k, num in edits:
        d1[FIELDS[k]] = str(num)
    data["DATA1"] = ",".join(d1)
    data.update(server_edits)
    SAVE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print("Da luu (sao luu cu: %s)" % bak.name)
    for k, num in edits + [(k, v) for k, v in server_edits.items()]:
        print("  %s = %s" % (k, num))
    return 0


if __name__ == "__main__":
    sys.exit(main())
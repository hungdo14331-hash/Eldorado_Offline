"""
patch_pvp_nonce.py -- Round 3A: CLIENT MATCH_NONCE PATCH
Patch byte-level cho ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js

3 chức năng (5 byte-replacements):
  A1+A2 STORAGE : var m trong IIFE glo.pvp + accessor set/get/clear gắn truoc Object.freeze(n)
  B     RECEIVE : validate + luu nonce trong SUCCESS callback cua
                  PVP_2025/enter_pvp_game.php; missing/null/empty thi clear,
                  hien error UI va return truoc parse/battle
  C     SEND    : t.MATCH_NONCE trong payload PVP_2025/update_pvp_result.php (URL-anchored)
  D     CLEAR   : dau callback update_pvp_result (Ajax layer chi goi khi STATE==="SUCCESS")

KHONG dung offset cung. Chi exact byte anchors + assert so hit.
KHONG decode/re-encode toan bundle. Byte ngoai 5 vung patch giu nguyen.
"""

import hashlib
import os
import sys

BUNDLE = r"ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js"
BACKUP = r"ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js.M0_BACKUP_20260924"
TMP    = BUNDLE + ".tmp_round3a"

EXPECTED_IN_SHA256 = "090b3674dd9a56fd6091680097f0734401c3dcf505332ed2db791c2e733ade50"

# (tag, expected_hits, needle, replacement) -- tat ca ASCII, khong mojibake
PATCHES = [
    ("A1_DECLARE_M", 1,
     b'lt=500,b=null,f,e;return n.RESULT_TYPE',
     b'lt=500,b=null,f,e,m;return n.RESULT_TYPE'),
    ("A2_ACCESSORS", 1,
     b'},Object.freeze(n)}();var MAX_GLOBAL_RANK_NVN=10,',
     b'},m="",n.set_game_nonce=function(n){m=n==null?"":""+n},'
     b'n.get_game_nonce=function(){return m},'
     b'n.clear_game_nonce=function(){m=""},'
     b'Object.freeze(n)}();var MAX_GLOBAL_RANK_NVN=10,'),
    ("B_RECEIVE", 1,
     b'encoding_add_ruby(-glo.pvp.get_entry_fee_rubies()));glo.pvp.parse_matched_user(n.matched_user)',
     b'encoding_add_ruby(-glo.pvp.get_entry_fee_rubies()));'
     b'if(n.MATCH_NONCE==null||n.MATCH_NONCE===""){' 
     b'glo.pvp.clear_game_nonce();'
     b'glo.fun.show_s_error_network("enter_pvp_game: missing MATCH_NONCE");return}'
     b'glo.pvp.set_game_nonce(n.MATCH_NONCE);'
     b'glo.pvp.parse_matched_user(n.matched_user)'),
    ("C_SEND", 1,
     b'PVP_2025/update_pvp_result.php";t={};t.HOST_ID=glo.fun.get_uniq_id();'
     b't.LANG=USER.lang;t.TEAM=glo.char.get_decks();t.SCORE=glo.pvp.get_game_score();'
     b't.RESULT=glo.pvp.get_game_result();t.VER_DATE=glo.VER_DATE;t.ETC="";',
     b'PVP_2025/update_pvp_result.php";t={};t.HOST_ID=glo.fun.get_uniq_id();'
     b't.LANG=USER.lang;t.TEAM=glo.char.get_decks();t.SCORE=glo.pvp.get_game_score();'
     b't.RESULT=glo.pvp.get_game_result();t.VER_DATE=glo.VER_DATE;'
     b't.MATCH_NONCE=glo.pvp.get_game_nonce();t.ETC="";'),
    ("D_CLEAR", 1,
     b'function(n){s=parseInt(n.tot_score);o=parseInt(n.my_ranking);',
     b'function(n){glo.pvp.clear_game_nonce();s=parseInt(n.tot_score);o=parseInt(n.my_ranking);'),
]


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def main():
    if not os.path.isfile(BUNDLE):
        fail("khong tim thay bundle: " + BUNDLE)

    data = open(BUNDLE, "rb").read()
    in_sha = sha256(data)
    print("input  size=%d sha256=%s" % (len(data), in_sha))

    if in_sha != EXPECTED_IN_SHA256:
        fail("source bundle khong dung version mong doi (expected %s).\n"
             "  -> co the bundle da patched truoc do; restore tu %s roi chay lai."
             % (EXPECTED_IN_SHA256, BACKUP))

    # --- kiem tra anchors truoc khi ghi bat ky file nao ---
    applied = []  # (tag, in_start, needle, replacement)
    for tag, expected, needle, repl in PATCHES:
        cnt = data.count(needle)
        if cnt != expected:
            fail("anchor %s: %d hit (expected %d) -> khong ghi file" % (tag, cnt, expected))
        in_start = data.find(needle)
        applied.append((tag, in_start, needle, repl))
        print("anchor %-14s OK  1 hit @ %d (len needle=%d, repl=%d)"
              % (tag, in_start, len(needle), len(repl)))

    if data.count(b'MATCH_NONCE') != 0:
        fail("MATCH_NONCE da ton tai trong input (da patch?) -> dung")

    # --- backup: chi tao neu chua ton tai, khong bao gio overwrite ---
    if os.path.isfile(BACKUP):
        print("backup da ton tai, giu nguyen: " + BACKUP)
    else:
        with open(BACKUP, "wb") as f:
            f.write(data)
        b_sha = sha256(open(BACKUP, "rb").read())
        if b_sha != EXPECTED_IN_SHA256:
            fail("backup ghi khong khop SHA-256 input")
        print("backup da tao: %s (sha256=%s)" % (BACKUP, b_sha))

    # --- replacements trong memory ---
    out = data
    for tag, in_start, needle, repl in applied:
        assert out.count(needle) == 1
        out = out.replace(needle, repl, 1)
    out_sha = sha256(out)
    print("output size=%d sha256=%s" % (len(out), out_sha))

    # --- verify output: du cac patch khong co gi them ---
    checks = [
        (b'MATCH_NONCE', 5),                       # B x4 incl. message + C x1
        (b'glo.pvp.set_game_nonce', 1),            # B
        (b'glo.pvp.get_game_nonce', 1),            # C
        (b'glo.pvp.clear_game_nonce', 2),          # B invalid + D success
        (b'n.set_game_nonce=function', 2),         # A2 def + sky co san
        (b'n.get_game_nonce=function', 2),         # A2 def + sky co san
        (b'n.clear_game_nonce=function', 1),       # A2 def (sky khong co clear)
        (b'n.set_game_nonce=function(n){s=n==null?"":""+n}', 1),  # sky def nguyen ven
        (b'var n={},t=[],i=[],u=[],c=0,l=0,a=[],k=0,d=0,g="",nt="",tt=[],it=[],rt=[],ut=0,v=0,o=0,s=0,y="",r=[],h=0,p=0,w=0,ft=0,et=0,ot=1,st=1,ht=1,ct=1,lt=500,b=null,f,e,m;return n.RESULT_TYPE', 1),
        (b'm="",n.set_game_nonce=function(n){m=n==null?"":""+n},n.get_game_nonce=function(){return m},n.clear_game_nonce=function(){m=""},Object.freeze(n)}();', 1),
        (b'PVP_2025/update_pvp_result.php', 1),
        (b'PVP_2025/enter_pvp_game.php', 1),
        (b'PVP_CLS_2026/enter_pvp_cls_game.php', 1),   # Classic nguyen ven
        (b'PVP_CLS_2026/update_pvp_cls_result.php', 1),  # Classic nguyen ven
        (b'if(n.MATCH_NONCE==null||n.MATCH_NONCE===""){glo.pvp.clear_game_nonce();glo.fun.show_s_error_network("enter_pvp_game: missing MATCH_NONCE");return}glo.pvp.set_game_nonce(n.MATCH_NONCE);glo.pvp.parse_matched_user(n.matched_user)', 1),
        (b'n.MATCH_NONCE!=null&&glo.pvp.set_game_nonce', 0),
    ]
    for needle, expected in checks:
        cnt = out.count(needle)
        if cnt != expected:
            fail("verify output: %r = %d (expected %d)" % (needle, cnt, expected))
    print("verify output: %d static checks OK" % len(checks))

    # --- moi byte ngoai 5 vung patch phai identical voi input ---
    applied_sorted = sorted(applied, key=lambda x: x[1])  # theo offset tang dan
    delta = 0
    ranges = []  # (tag, out_start, out_end)
    for tag, in_start, needle, repl in applied_sorted:
        out_start = in_start + delta
        out_end = out_start + len(repl)
        if out[out_start:out_end] != repl:
            fail("verify range %s: replacement khong nam dung vi tri" % tag)
        ranges.append((tag, out_start, out_end))
        delta += len(repl) - len(needle)

    prev_out_end = 0
    prev_in_end = 0
    for (tag, out_start, out_end), (t2, in_start, needle, repl) in zip(ranges, applied_sorted):
        in_start_of_this = in_start
        if out[prev_out_end:out_start] != data[prev_in_end:in_start_of_this]:
            fail("byte ngoai vung patch khac nguyen ban truoc %s" % tag)
        prev_out_end = out_end
        prev_in_end = in_start_of_this + len(needle)
    if out[prev_out_end:] != data[prev_in_end:]:
        fail("byte duoi cuoi (tail) khac nguyen ban")
    total_changed = sum(e - s for _, s, e in ranges)
    print("verify diff ranges: %d vung, tong %d byte thay doi" % (len(ranges), total_changed))
    for tag, s, e in ranges:
        print("  %s out_range=[%d:%d] (%d bytes)" % (tag, s, e, e - s))

    # --- Classic byte-identical: cac anchor Classic nam hoan toan ngoai diff ranges ---
    classic_anchors = [
        (b'PVP_CLS_2026/enter_pvp_cls_game.php', "cls enter URL"),
        (b'PVP_CLS_2026/update_pvp_cls_result.php', "cls result URL"),
        (b'n.hasOwnProperty("s_add_gold")&&(USER.gold=parseInt(n.s_add_gold));glo.pvp.parse_matched_user(n.matched_user)', "cls enter callback"),
    ]
    for needle, name in classic_anchors:
        pos = out.find(needle)
        if pos < 0:
            fail("Classic anchor mat: " + name)
        for tag, s, e in ranges:
            if not (pos + len(needle) <= s or pos >= e):
                fail("Classic anchor %s overlap vung patch %s" % (name, tag))
        # byte-identical voi input
        in_pos = data.find(needle)
        if out[pos:pos + len(needle)] != data[in_pos:in_pos + len(needle)]:
            fail("Classic anchor %s khong byte-identical" % name)
        print("classic %-18s [%d:%d] ngoai vung patch, byte-identical" % (name, pos, pos + len(needle)))

    # --- ghi temp + os.replace ---
    with open(TMP, "wb") as f:
        f.write(out)
    if sha256(open(TMP, "rb").read()) != out_sha:
        os.remove(TMP)
        fail("temp file ghi khong dung SHA-256")
    os.replace(TMP, BUNDLE)
    print("da ghi bundle (temp + os.replace): " + BUNDLE)
    print("DONE. input=%s output=%s" % (in_sha, out_sha))


if __name__ == "__main__":
    main()

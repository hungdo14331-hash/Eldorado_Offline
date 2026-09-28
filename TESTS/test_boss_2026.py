#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 2 -- WORLD BOSS 2026 (BOSS_2026/*.php) acceptance tests A..O.

Every instance runs on a private port against its own DB/save under
_boss_test/. The live 8029 server, busidol.db, the real save files and
M0_BASELINE_20260924_014351 are never touched.

    python test_boss_2026.py            # full suite, wipes _boss_test/ first
    python test_boss_2026.py --keep     # keep _boss_test/ for inspection
    python test_boss_2026.py --ui       # private UI instance for the browser
                                        # smoke test (uses a COPY of a save)

Coverage map to §14:
    A  board contract / STATE / ranking_list array       (core + JSON)
    B  enter with ticket -> charged exactly once         (core + JSON)
    C  repeat enter with ACTIVE session -> no 2nd charge (core)
    D  win update -> HP down once, ranking up once       (core + JSON)
    E  exact resend -> cached response, no 2nd mutation  (core + JSON)
    E2 §9 late retry after a new match is open           (core)
    E3 RUN_COUNT/USER_KEY/IS_SYNC/VERSION ignored        (core)
    F  two users, one shared HP pool, ranking order      (core)
    G  two concurrent updates, same user -> one mutation (core)
    G2 same race but DIFFERENT SCORE -> loser gets -101, not a
       wrong replay                                         (core)
    H  damage clamped to current HP, HP never negative   (drain)
    I  HP=0 -> new enter refused, no fake HP=1           (drain)
    J  restart -> boss state + ranking survive           (core + JSON)
    R  restart -> consumed result still replays, no 2nd
       mutation                                            (core)
    K  season expiry rolls exactly once (fake clock)     (in-process)
    L  ENTRY_GOLD -> gold down exactly once              (core + JSON)
    M  missing ticket / gold -> typed error, no session  (core)
    N  bad payload -> no mutation                        (core)
    T  legacy Boss/*tiket_to_server.php stubs            (JSON)
    P  literal double-encoded RESULT bytes; canonical and mojibake
       forms of one match share the retry cache           (core)
    S  atomic JSON save fault injection (fail-before-replace
       + success)                                          (in-process)
    O  real UI smoke                                     (--ui + browser)
"""
import argparse
import atexit
import http.client
import json
import logging
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
TEST_DIR = BASE / "_boss_test"
TODAY = time.strftime("%Y%m%d")
WIN, LOSE = "\uc2b9", "\ud328"          # canonical 승 / 패 (server normalises onto these)
# What the shipped bundle LITERALLY puts on the wire: the file stores the Korean
# literals as the UTF-8 encoding of their latin-1 misreading, so the bytes are
# "ì\u008a¹" / "í\u008c¨" instead of the canonical pair. Taken byte-for-byte from
# eldorado_all_20260915.min.js (offsets 3237116 and 3317116).
WIN_WIRE, LOSE_WIRE = "\u00ec\u008a\u00b9", "\u00ed\u008c\u00a8"
# A double-encoded syllable that is NOT a result token: repairs to "가", so it
# proves the normaliser maps onto the canonical pair instead of accepting
# anything repairable.
BAD_WIRE = "\u00ea\u00b0\u0080"

RANK = "/ELDORADO_WEB/BOSS_2026/get_boss_ranking.php"
ENTER = "/ELDORADO_WEB/BOSS_2026/enter_boss_game.php"
UPDATE = "/ELDORADO_WEB/BOSS_2026/update_boss_result.php"
RANK_TEST_ALIAS = "/ELDORADO_WEB/BOSS_2026_TEST/get_boss_ranking.php"
TIK_GET = "/ELDORADO_WEB/Boss/get_boss_tiket_to_server.php"
TIK_SET = "/ELDORADO_WEB/Boss/update_boss_tiket_to_server.php"

SUCCESS_FIELDS = ("ranking_list", "my_ranking", "TOT_SCORE", "BOSS_NUM",
                  "BOSS_HP", "boss_cur_hp", "run_out_time", "SERVER_TIME")


def form(**kv) -> str:
    """Body the real client sends: get_string_by_obj just joins key=value&
    (no percent-encoding), so Korean RESULT stays raw UTF-8."""
    return "&".join(f"{k}={v}" for k, v in kv.items() if v is not None)


def free_port(start):
    for port in range(start, start + 60):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port")


def seed_save(db, uid, data1=None, extra=None):
    payload = {"USER_NAME": uid, "DATA1": data1 or f"{uid},0,0"}
    payload.update(extra or {})
    con = sqlite3.connect(str(db), timeout=15)
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                (uid, json.dumps(payload, ensure_ascii=False)))
    con.commit()
    con.close()


def db_one(db, sql, args=()):
    con = sqlite3.connect(str(db), timeout=15)
    con.execute("PRAGMA busy_timeout=5000")
    try:
        return con.execute(sql, args).fetchone()
    finally:
        con.close()


def hp_at(db):
    row = db_one(db, "SELECT cur_hp FROM boss_state WHERE boss_num=1")
    return None if row is None else int(row[0])


def gold_of(db, uid):
    row = db_one(db, "SELECT payload FROM saves WHERE id=?", (uid,))
    if not row:
        return None
    d1 = (json.loads(row[0]).get("DATA1") or "").split(",")
    return int(float(d1[1])) if len(d1) > 1 and d1[1] not in ("", None) else 0


class Suite:
    def __init__(self):
        self.n = 0
        self.fails = []

    def check(self, name, cond, detail=""):
        self.n += 1
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}   {detail}")
            self.fails.append(name)

    def section(self, title):
        print(f"\n=== {title} ===")


def contract(S, name, p, text):
    """§12: no endpoint ever answers {}, every reply carries STATE, and a
    SUCCESS reply carries every field the client's handlers read."""
    S.check(f"{name}: JSON with STATE", isinstance(p, dict)
            and p.get("STATE") in ("SUCCESS", "ERROR"), text[:160])
    if not isinstance(p, dict):
        return
    if p.get("STATE") == "ERROR":
        S.check(f"{name}: ERROR carries CODE + ERROR_MESSAGE",
                bool(p.get("CODE")) and bool(p.get("ERROR_MESSAGE")), text[:160])
        return
    missing = [k for k in SUCCESS_FIELDS if k not in p]
    S.check(f"{name}: all SUCCESS fields present", not missing, str(missing))
    S.check(f"{name}: ranking_list is an array", isinstance(p.get("ranking_list"), list),
            text[:160])
    S.check(f"{name}: BOSS_NUM is a real BOSS_DESIGN index",
            str(p.get("BOSS_NUM")) in ("1", "2", "3", "5", "6", "7"), text[:160])


class Instance:
    def __init__(self, name, port, extra_args, env_extra=None):
        self.name, self.port, self.args = name, port, extra_args
        self.dir = TEST_DIR / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.env_extra = env_extra or {}
        self.proc = None

    def start(self):
        cmd = [sys.executable, "-u", str(BASE / "serve.py"), "--mode", "offline",
               "--host", "127.0.0.1", "--port", str(self.port),
               "--log", str(self.dir / "serve.log")] + self.args
        env = dict(os.environ)
        env.update(self.env_extra)
        self.proc = subprocess.Popen(cmd, cwd=str(BASE), env=env,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.STDOUT)
        atexit.register(self.stop)
        t0 = time.time()
        while time.time() - t0 < 25:
            if self.proc.poll() is not None:
                raise RuntimeError(f"{self.name}: server exited early "
                                   f"(see {self.dir / 'serve.log'})")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.15)
        raise RuntimeError(f"{self.name}: not listening on {self.port}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.proc = None

    def req(self, path, body="", timeout=20):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            if body is None:
                c.request("GET", path)
            else:
                c.request("POST", path, body=body.encode("utf-8"),
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
            r = c.getresponse()
            return r.status, r.read().decode("utf-8", "replace")
        finally:
            c.close()

    def jreq(self, path, body=""):
        st, txt = self.req(path, body)
        try:
            return st, json.loads(txt), txt
        except Exception:
            return st, None, txt


# ---------------------------------------------------------------- core (--db)

def t_core(S, c, db):
    maxhp = 2_000_000_000_000

    S.section("A. board contract (fresh user)")
    st, p, txt = c.jreq(RANK, form(HOST_ID="uA"))
    S.check("A HTTP 200", st == 200, str(st))
    contract(S, "A", p, txt)
    if isinstance(p, dict) and p.get("STATE") == "SUCCESS":
        S.check("A TICKET starts at 10 (daily)", p.get("TICKET") == "10", txt[:160])
        S.check("A ENTER_COUNT starts at 0", p.get("ENTER_COUNT") == "0", txt[:160])
        S.check("A my_ranking=0 TOT_SCORE=0", p.get("my_ranking") == "0"
                and p.get("TOT_SCORE") == "0", txt[:160])
        S.check("A BOSS_HP = BOSS_DESIGN[1].max_hp", p.get("BOSS_HP") == str(maxhp), txt[:160])
        S.check("A run_out_time is after SERVER_TIME",
                int(p.get("run_out_time", "0")) > int(p.get("SERVER_TIME", "0")), txt[:160])
        S.check("A BC_BOSS_2_HP/3_HP neutral 0",
                p.get("BC_BOSS_2_HP") == "0" and p.get("BC_BOSS_3_HP") == "0", txt[:160])
    row = db_one(db, "SELECT cur_hp,max_hp,season_start,season_end FROM boss_state WHERE boss_num=1")
    S.check("A state row created with max_hp", row is not None and row[0] == maxhp
            and row[1] == maxhp, str(row))
    S.check("A season is 7 days", row is not None and row[3] - row[2] == 7 * 86400, str(row))
    st2, p2, txt2 = c.jreq(RANK_TEST_ALIAS, form(HOST_ID="uA"))
    S.check("A BOSS_2026_TEST/ alias hits the same handler",
            st2 == 200 and isinstance(p2, dict) and p2.get("STATE") == "SUCCESS", txt2[:160])

    S.section("B. enter charges exactly one ticket")
    p0 = c.jreq(RANK, form(HOST_ID="uB"))[1]
    S.check("B starts with 10", p0.get("TICKET") == "10")
    ebody = form(HOST_ID="uB", MODE="ENTRY_TICKET", TEAM="1,2,3", ITEM="", ETC="")
    st, e1, t1 = c.jreq(ENTER, ebody)
    contract(S, "B enter", e1, t1)
    S.check("B enter SUCCESS", isinstance(e1, dict) and e1.get("STATE") == "SUCCESS", t1[:200])
    S.check("B MODE echoed for run_boss_game()", e1.get("MODE") == "ENTRY_TICKET", t1[:160])
    S.check("B ticket 10->9 (cur_ticket)", e1.get("cur_ticket") == "9"
            and e1.get("TICKET") == "9", t1[:160])
    S.check("B ENTER_COUNT=1", e1.get("ENTER_COUNT") == "1", t1[:160])
    p1 = c.jreq(RANK, form(HOST_ID="uB"))[1]
    S.check("B persisted: board reads 9", p1.get("TICKET") == "9", json.dumps(p1)[:160])
    S.check("B persisted: ENTER_COUNT=1", p1.get("ENTER_COUNT") == "1")
    S.check("B exactly 1 ACTIVE session", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uB' AND status='ACTIVE'")[0] == 1)

    S.section("C. repeat enter with an ACTIVE session -> no second charge")
    cbody = form(HOST_ID="uC", MODE="ENTRY_TICKET", TEAM="1,2,3")
    c1 = c.jreq(ENTER, cbody)[1]
    S.check("C first enter SUCCESS ticket 9", c1.get("STATE") == "SUCCESS"
            and c1.get("cur_ticket") == "9", json.dumps(c1)[:160])
    st, c2, tc2 = c.jreq(ENTER, cbody)
    contract(S, "C repeat", c2, tc2)
    S.check("C repeat is a compatible SUCCESS, not an error",
            isinstance(c2, dict) and c2.get("STATE") == "SUCCESS", tc2[:160])
    S.check("C repeat did not charge (still 9)", c2.get("cur_ticket") == "9"
            and c2.get("TICKET") == "9", tc2[:160])
    S.check("C board still 9", c.jreq(RANK, form(HOST_ID="uC"))[1].get("TICKET") == "9")
    S.check("C exactly 1 session row for uC", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uC'")[0] == 1)

    S.section("D/E/E3. win update applies once; every resend replays")
    eD = c.jreq(ENTER, form(HOST_ID="uD", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    hp0 = int(eD.get("boss_cur_hp"))
    ubody = form(HOST_ID="uD", RESULT=WIN, SCORE="100000", TEAM="1,2,3", ITEM="", ETC="")
    st, u1, tU1 = c.jreq(UPDATE, ubody)
    contract(S, "D update", u1, tU1)
    S.check("D update SUCCESS", isinstance(u1, dict) and u1.get("STATE") == "SUCCESS", tU1[:200])
    S.check("D HP down by SCORE", int(u1.get("boss_cur_hp")) == hp0 - 100000,
            f"{u1.get('boss_cur_hp')} != {hp0 - 100000}")
    S.check("D my_ranking=1 TOT_SCORE=100000", u1.get("my_ranking") == "1"
            and u1.get("TOT_SCORE") == "100000", tU1[:200])
    lst = u1.get("ranking_list") or []
    r0 = lst[0] if lst else {}
    S.check("D ranking_list row carries user_name/team/tot_score/platform",
            r0.get("tot_score") == "100000" and r0.get("ranking") == "1"
            and r0.get("user_name") == "uD" and r0.get("platform"),
            json.dumps(lst, ensure_ascii=False)[:200])
    S.check("D DB hp matches", hp_at(db) == hp0 - 100000, str(hp_at(db)))
    S.check("D damage row 100000", db_one(
        db, "SELECT total_damage FROM boss_damage WHERE user_id='uD'")[0] == 100000)
    srow = db_one(db, "SELECT status,response_json FROM boss_sessions "
                      "WHERE user_id='uD' ORDER BY opened_at DESC LIMIT 1")
    S.check("D session CONSUMED with stored response", srow[0] == "CONSUMED"
            and (srow[1] or "").strip().startswith("{"), str(srow)[:160])
    st, u2, tU2 = c.jreq(UPDATE, ubody)
    S.check("E exact resend returns the stored body", tU2 == tU1,
            f"{tU1[:110]} || {tU2[:110]}")
    S.check("E HP unchanged after resend", hp_at(db) == hp0 - 100000, str(hp_at(db)))
    S.check("E damage unchanged after resend", db_one(
        db, "SELECT total_damage FROM boss_damage WHERE user_id='uD'")[0] == 100000)
    ubody3 = ubody + "&IS_SYNC=1&USER_KEY=&RUN_COUNT=7&VERSION=EL_GLO_20260915"
    st, u3, tU3 = c.jreq(UPDATE, ubody3)
    S.check("E3 transport fields ignored -> same stored body", tU3 == tU1,
            f"{tU1[:110]} || {tU3[:110]}")
    S.check("E3 HP unchanged", hp_at(db) == hp0 - 100000, str(hp_at(db)))

    S.section("E2. §9: match A's late retry while match B is open")
    eE = c.jreq(ENTER, form(HOST_ID="uE", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    hA = int(eE.get("boss_cur_hp"))
    bodyA = form(HOST_ID="uE", RESULT=WIN, SCORE="5000", TEAM="1,2,3")
    st, rA, tA = c.jreq(UPDATE, bodyA)
    S.check("E2 match A applied", rA.get("STATE") == "SUCCESS" and hp_at(db) == hA - 5000,
            f"hp={hp_at(db)} want {hA - 5000}")
    eE2 = c.jreq(ENTER, form(HOST_ID="uE", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    S.check("E2 match B opened (ticket 8)", eE2.get("STATE") == "SUCCESS"
            and eE2.get("cur_ticket") == "8", json.dumps(eE2)[:200])
    st, late, tLate = c.jreq(UPDATE, bodyA)
    S.check("E2 late retry replays A's stored body", tLate == tA,
            f"{tA[:110]} || {tLate[:110]}")
    S.check("E2 late retry did not damage again", hp_at(db) == hA - 5000, str(hp_at(db)))
    S.check("E2 match B stayed ACTIVE", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uE' AND status='ACTIVE'")[0] == 1)
    st, rB, tB = c.jreq(UPDATE, form(HOST_ID="uE", RESULT=WIN, SCORE="7000", TEAM="1,2,3"))
    S.check("E2 B's own result still applies", rB.get("STATE") == "SUCCESS"
            and hp_at(db) == hA - 12000, f"{tB[:140]} hp={hp_at(db)}")
    S.check("E2 uE total damage 12000", db_one(
        db, "SELECT total_damage FROM boss_damage WHERE user_id='uE'")[0] == 12000)

    S.section("F. two users share one HP pool; ranking order")
    eF1 = c.jreq(ENTER, form(HOST_ID="uF1", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    eF2 = c.jreq(ENTER, form(HOST_ID="uF2", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    h0 = int(eF1.get("boss_cur_hp"))
    S.check("F both sessions opened at the same HP", eF2.get("boss_cur_hp") == str(h0))
    c.jreq(UPDATE, form(HOST_ID="uF1", RESULT=WIN, SCORE="800", TEAM="1,2,3"))
    c.jreq(UPDATE, form(HOST_ID="uF2", RESULT=WIN, SCORE="1200", TEAM="1,2,3"))
    S.check("F shared HP dropped by both hits", hp_at(db) == h0 - 2000, str(hp_at(db)))
    p = c.jreq(RANK, form(HOST_ID="uF1"))[1]
    lst = p.get("ranking_list") or []
    names = [r.get("user_name") for r in lst]
    S.check("F uF2 (1200) ranked above uF1 (800)",
            "uF2" in names and "uF1" in names and names.index("uF2") < names.index("uF1"),
            json.dumps(lst, ensure_ascii=False)[:300])
    S.check("F ranking numbers are 1..N",
            [r.get("ranking") for r in lst] == [str(i) for i in range(1, len(lst) + 1)],
            json.dumps(lst, ensure_ascii=False)[:200])
    S.check("F my_ranking / TOT_SCORE derived server-side",
            p.get("my_ranking") == str(names.index("uF1") + 1) and p.get("TOT_SCORE") == "800",
            json.dumps(p, ensure_ascii=False)[:200])

    S.section("G. two concurrent identical updates -> one mutation")
    eG = c.jreq(ENTER, form(HOST_ID="uG", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    hG = int(eG.get("boss_cur_hp"))
    bodyG = form(HOST_ID="uG", RESULT=WIN, SCORE="4321", TEAM="1,2,3")
    out = []

    def _post():
        try:
            out.append(c.req(UPDATE, bodyG))
        except Exception as ex:            # noqa: BLE001 - reported as a failure
            out.append((0, f"EXC {ex}"))

    ths = [threading.Thread(target=_post) for _ in range(2)]
    for t in ths:
        t.start()
    for t in ths:
        t.join(30)
    S.check("G both requests answered", len(out) == 2 and all(r[0] == 200 for r in out),
            str(out)[:200])
    S.check("G both answers identical (one applied, one replayed)",
            len({r[1] for r in out}) == 1, str({r[1][:80] for r in out})[:300])
    S.check("G HP dropped exactly once", hp_at(db) == hG - 4321, str(hp_at(db)))
    S.check("G damage counted once", db_one(
        db, "SELECT total_damage FROM boss_damage WHERE user_id='uG'")[0] == 4321)
    S.check("G one CONSUMED / zero ACTIVE", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uG' AND status='CONSUMED'")[0] == 1
        and db_one(db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uG' AND status='ACTIVE'")[0] == 0)

    S.section("G2. two concurrent updates, same user, DIFFERENT SCORE")
    eG2 = c.jreq(ENTER, form(HOST_ID="uG2", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    hG2 = int(eG2.get("boss_cur_hp"))
    bodiesG2 = (form(HOST_ID="uG2", RESULT=WIN, SCORE="4321", TEAM="1,2,3"),
                form(HOST_ID="uG2", RESULT=WIN, SCORE="8765", TEAM="1,2,3"))
    outG2 = []

    def _post2(body):
        try:
            outG2.append(c.req(UPDATE, body))
        except Exception as ex:            # noqa: BLE001 - reported as a failure
            outG2.append((0, f"EXC {ex}"))

    ths = [threading.Thread(target=_post2, args=(b,)) for b in bodiesG2]
    for t in ths:
        t.start()
    for t in ths:
        t.join(30)
    S.check("G2 both requests answered", len(outG2) == 2 and all(r[0] == 200 for r in outG2),
            str(outG2)[:200])
    parsed = []
    for st, txt in outG2:
        try:
            parsed.append(json.loads(txt))
        except Exception:
            parsed.append(None)
    S.check("G2 exactly one SUCCESS and one -101 (no wrong replay)",
            sorted((p or {}).get("STATE", "?") for p in parsed) == ["ERROR", "SUCCESS"]
            and sum(1 for p in parsed if (p or {}).get("CODE") == "-101") == 1,
            str(outG2)[:300])
    dmg2 = db_one(db, "SELECT total_damage FROM boss_damage WHERE user_id='uG2'")[0]
    S.check("G2 damage counted once (one of the two scores)", dmg2 in (4321, 8765), str(dmg2))
    S.check("G2 HP dropped by exactly that one score, never the sum",
            hp_at(db) == hG2 - dmg2, f"{hp_at(db)} want {hG2 - dmg2}")
    S.check("G2 one CONSUMED / zero ACTIVE", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uG2' AND status='CONSUMED'")[0] == 1
        and db_one(db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uG2' AND status='ACTIVE'")[0] == 0)

    S.section("L. ENTRY_GOLD charges the ladder fee exactly once")
    seed_save(db, "uL", "uL,100000,0,0,0,0,0,0,0,0,0,0,0,0,0",
              {"boss_ticket_day": TODAY, "boss_ticket_left": "0",
               "boss_enter_day": TODAY, "boss_enter_count": "20"})
    lb = form(HOST_ID="uL", MODE="ENTRY_GOLD", TEAM="1,2,3")
    st, l1, tL1 = c.jreq(ENTER, lb)
    contract(S, "L gold enter", l1, tL1)
    S.check("L ENTRY_GOLD SUCCESS", isinstance(l1, dict) and l1.get("STATE") == "SUCCESS", tL1[:200])
    S.check("L fee = 3000 (enter 21 in 10..30 band)", l1.get("need_gold") == "3000", tL1[:160])
    S.check("L gold 100000 -> 97000 once", l1.get("s_add_gold") == "97000"
            and gold_of(db, "uL") == 97000, f"{l1.get('s_add_gold')} db={gold_of(db,'uL')}")
    S.check("L ENTER_COUNT 20 -> 21", l1.get("ENTER_COUNT") == "21", tL1[:160])
    st, l2, tL2 = c.jreq(ENTER, lb)
    S.check("L repeat enter replays (no second charge)", tL2 == tL1
            and gold_of(db, "uL") == 97000, f"{tL1[:110]} || {tL2[:110]}")

    S.section("M. missing ticket / gold -> typed error, no session, no mutation")
    seed_save(db, "uM1", "uM1,100000,0",
              {"boss_ticket_day": TODAY, "boss_ticket_left": "0",
               "boss_enter_day": TODAY, "boss_enter_count": "20"})
    st, m1, tM1 = c.jreq(ENTER, form(HOST_ID="uM1", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    contract(S, "M1", m1, tM1)
    S.check("M1 -102 (no ticket)", isinstance(m1, dict) and m1.get("STATE") == "ERROR"
            and m1.get("CODE") == "-102", tM1[:200])
    S.check("M1 no session created", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uM1'")[0] == 0)
    seed_save(db, "uM2", "uM2,100,0",
              {"boss_ticket_day": TODAY, "boss_ticket_left": "0",
               "boss_enter_day": TODAY, "boss_enter_count": "20"})
    st, m2, tM2 = c.jreq(ENTER, form(HOST_ID="uM2", MODE="ENTRY_GOLD", TEAM="1,2,3"))
    contract(S, "M2", m2, tM2)
    S.check("M2 -103 (not enough gold)", isinstance(m2, dict) and m2.get("STATE") == "ERROR"
            and m2.get("CODE") == "-103", tM2[:200])
    S.check("M2 gold untouched", gold_of(db, "uM2") == 100, str(gold_of(db, "uM2")))
    S.check("M2 no session created", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uM2'")[0] == 0)

    S.section("N. bad payload -> no mutation")
    c.jreq(ENTER, form(HOST_ID="uN", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    hN = hp_at(db)
    bad = (("negative SCORE", form(HOST_ID="uN", RESULT=WIN, SCORE="-1")),
           ("non-numeric SCORE", form(HOST_ID="uN", RESULT=WIN, SCORE="abc")),
           ("RESULT not in the client set", form(HOST_ID="uN", RESULT="W", SCORE="10")),
           ("SCORE above HP at match start", form(HOST_ID="uN", RESULT=WIN, SCORE=str(hN + 1))))
    for label, body in bad:
        st, p, t = c.jreq(UPDATE, body)
        contract(S, f"N {label}", p, t)
        S.check(f"N {label}: STATE=ERROR -101", isinstance(p, dict)
                and p.get("STATE") == "ERROR" and p.get("CODE") == "-101", t[:160])
    S.check("N HP unchanged by all four", hp_at(db) == hN, str(hp_at(db)))
    S.check("N session left ACTIVE (nothing consumed)", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uN' AND status='ACTIVE'")[0] == 1)
    st, p, t = c.jreq(UPDATE, form(HOST_ID="uN5", RESULT=WIN, SCORE="10"))
    S.check("N update with no session -> -101", isinstance(p, dict)
            and p.get("STATE") == "ERROR" and p.get("CODE") == "-101", t[:160])
    st, p, t = c.jreq(ENTER, form(HOST_ID="uN6", MODE="BOGUS", TEAM="1,2,3"))
    S.check("N unknown MODE -> -101", isinstance(p, dict)
            and p.get("STATE") == "ERROR" and p.get("CODE") == "-101", t[:160])
    S.check("N no session for the bogus entry", db_one(
        db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uN6'")[0] == 0)

    S.section("J. restart -> shared boss state + ranking survive")
    before = c.jreq(RANK, form(HOST_ID="uD"))[1]
    hpB = hp_at(db)
    c.stop()
    c.start()
    after = c.jreq(RANK, form(HOST_ID="uD"))[1]
    S.check("J board answers after restart", after.get("STATE") == "SUCCESS")
    S.check("J HP survived", hp_at(db) == hpB and after.get("BOSS_HP") == str(hpB),
            f"{hpB} vs {after.get('BOSS_HP')}")
    S.check("J uD score survived", after.get("TOT_SCORE") == "100000",
            json.dumps(after, ensure_ascii=False)[:200])
    S.check("J ranking list survived",
            (after.get("ranking_list") or []) == (before.get("ranking_list") or []))
    S.check("J ACTIVE session survived (uC enter still replays with 9)",
            c.jreq(ENTER, form(HOST_ID="uC", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
            .get("cur_ticket") == "9")

    S.section("R. restart -> consumed result still replays, no 2nd mutation")
    st, uR, tUR = c.jreq(UPDATE, ubody)
    S.check("R post-restart resend replays the stored body", tUR == tU1,
            f"{tU1[:110]} || {tUR[:110]}")
    S.check("R HP unchanged by the post-restart resend", hp_at(db) == hpB, str(hp_at(db)))
    S.check("R damage unchanged (no 2nd mutation)", db_one(
        db, "SELECT total_damage FROM boss_damage WHERE user_id='uD'")[0] == 100000)

    S.section("P. the client's literal RESULT bytes (double-encoded in the bundle)")
    # The real UI posted RESULT=<mojibake> and the server answered "bad RESULT"
    # until the token was normalised; these are the exact bundle bytes.
    hpP = hp_at(db)
    c.jreq(ENTER, form(HOST_ID="uP1", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    st, pw, tpw = c.jreq(UPDATE, form(HOST_ID="uP1", RESULT=WIN_WIRE, SCORE="1234"))
    contract(S, "P win", pw, tpw)
    S.check("P literal-win bytes accepted, damage applied once",
            isinstance(pw, dict) and pw.get("STATE") == "SUCCESS"
            and hp_at(db) == hpP - 1234 and pw.get("TOT_SCORE") == "1234", tpw[:200])
    S.check("P resending the same literal bytes replays (no second hit)",
            c.jreq(UPDATE, form(HOST_ID="uP1", RESULT=WIN_WIRE, SCORE="1234"))[2] == tpw
            and hp_at(db) == hpP - 1234)
    c.jreq(ENTER, form(HOST_ID="uP2", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    st, pl, tpl = c.jreq(UPDATE, form(HOST_ID="uP2", RESULT=LOSE_WIRE, SCORE="0"))
    contract(S, "P loss", pl, tpl)
    S.check("P literal-loss bytes accepted; a loss credits nothing",
            isinstance(pl, dict) and pl.get("STATE") == "SUCCESS"
            and pl.get("TOT_SCORE") == "0" and hp_at(db) == hpP - 1234
            and db_one(db, "SELECT COUNT(*) FROM boss_damage WHERE user_id='uP2'")[0] == 0,
            tpl[:200])
    c.jreq(ENTER, form(HOST_ID="uP3", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    st, pb, tb = c.jreq(UPDATE, form(HOST_ID="uP3", RESULT=BAD_WIRE, SCORE="10"))
    S.check("P an unrelated double-encoded token is still rejected",
            isinstance(pb, dict) and pb.get("STATE") == "ERROR" and pb.get("CODE") == "-101"
            and hp_at(db) == hpP - 1234
            and db_one(db, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uP3'"
                           " AND status='ACTIVE'")[0] == 1, tb[:200])

    S.section("P2. canonical and mojibake forms of one match share the retry cache")
    c.jreq(ENTER, form(HOST_ID="uP4", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    t_can = c.jreq(UPDATE, form(HOST_ID="uP4", RESULT=WIN, SCORE="2500"))[2]
    S.check("P2 canonical result applied", json.loads(t_can).get("STATE") == "SUCCESS",
            t_can[:160])
    S.check("P2 retrying that match in mojibake form replays it",
            c.jreq(UPDATE, form(HOST_ID="uP4", RESULT=WIN_WIRE, SCORE="2500"))[2] == t_can
            and hp_at(db) == hpP - 1234 - 2500)
    c.jreq(ENTER, form(HOST_ID="uP5", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    t_wir = c.jreq(UPDATE, form(HOST_ID="uP5", RESULT=WIN_WIRE, SCORE="3500"))[2]
    S.check("P2 mojibake result applied", json.loads(t_wir).get("STATE") == "SUCCESS",
            t_wir[:160])
    S.check("P2 retrying that match in canonical form replays it",
            c.jreq(UPDATE, form(HOST_ID="uP5", RESULT=WIN, SCORE="3500"))[2] == t_wir
            and hp_at(db) == hpP - 1234 - 2500 - 3500)


# ------------------------------------------------------- drain (small max HP)

def t_drain(S, d, ddb):
    S.section("H. damage clamps to current HP; HP never negative")
    e1 = d.jreq(ENTER, form(HOST_ID="uH", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    e2 = d.jreq(ENTER, form(HOST_ID="uH2", MODE="ENTRY_TICKET", TEAM="1,2,3"))[1]
    S.check("H BOSS_MAX_HP override in effect (1000)",
            e1.get("BOSS_HP") == "1000" and e2.get("BOSS_HP") == "1000",
            f"{e1.get('BOSS_HP')} {e2.get('BOSS_HP')}")
    st, h1, th1 = d.jreq(UPDATE, form(HOST_ID="uH", RESULT=WIN, SCORE="1000"))
    S.check("H win zeroes the boss", isinstance(h1, dict) and h1.get("STATE") == "SUCCESS"
            and h1.get("boss_cur_hp") == "0", th1[:200])
    st, h2, th2 = d.jreq(UPDATE, form(HOST_ID="uH2", RESULT=WIN, SCORE="1000"))
    S.check("H stale full-score hit clamps to 0 (no negative)",
            isinstance(h2, dict) and h2.get("STATE") == "SUCCESS"
            and h2.get("boss_cur_hp") == "0", th2[:200])
    S.check("H DB HP exactly 0", hp_at(ddb) == 0, str(hp_at(ddb)))
    S.check("H clamped hit is not credited on the board",
            db_one(ddb, "SELECT COUNT(*) FROM boss_damage WHERE user_id='uH2'")[0] == 0)
    S.check("H board reports 0", d.jreq(RANK, form(HOST_ID="uH"))[1].get("BOSS_HP") == "0")

    S.section("I. dead boss refuses entry (never fakes HP=1)")
    st, i1, ti1 = d.jreq(ENTER, form(HOST_ID="uI", MODE="ENTRY_TICKET", TEAM="1,2,3"))
    contract(S, "I", i1, ti1)
    S.check("I -104 boss defeated", isinstance(i1, dict) and i1.get("STATE") == "ERROR"
            and i1.get("CODE") == "-104", ti1[:200])
    S.check("I error carries boss_cur_hp=0 for the 0% label",
            i1.get("boss_cur_hp") == "0" and i1.get("BOSS_HP") == "0", ti1[:160])
    S.check("I no session created", db_one(
        ddb, "SELECT COUNT(*) FROM boss_sessions WHERE user_id='uI'")[0] == 0)
    S.check("I ticket not charged", d.jreq(RANK, form(HOST_ID="uI"))[1].get("TICKET") == "10")
    S.check("I HP still exactly 0", hp_at(ddb) == 0, str(hp_at(ddb)))


# ------------------------------------------------------- JSON-mode backend

def t_json(S, j, jdir):
    savef = jdir / "test_save.json"
    uid = "TESTJSON"

    S.section("JSON. sidecar backend (--save-file)")
    st, a, ta = j.jreq(RANK, form(HOST_ID=uid))
    contract(S, "JSON-A", a, ta)
    S.check("JSON-A TICKET=10", isinstance(a, dict) and a.get("TICKET") == "10", ta[:160])
    S.check("JSON-A boss state sidecar written", (jdir / "test_save.boss.json").is_file(),
            str([p.name for p in jdir.iterdir()]))

    eb = form(HOST_ID=uid, MODE="ENTRY_TICKET", TEAM="1,2,3")
    st, b, tb = j.jreq(ENTER, eb)
    contract(S, "JSON-B", b, tb)
    S.check("JSON-B enter SUCCESS, ticket 10->9", isinstance(b, dict)
            and b.get("STATE") == "SUCCESS" and b.get("cur_ticket") == "9", tb[:200])
    saved = json.loads(savef.read_text(encoding="utf-8"))
    S.check("JSON-B save file carries the charge",
            saved.get("boss_ticket_left") == "9" and saved.get("boss_enter_count") == "1",
            json.dumps(saved, ensure_ascii=False)[:200])
    S.check("JSON-B repeat enter replays without a second charge",
            j.jreq(ENTER, eb)[2] == tb)

    hp0 = int(b.get("boss_cur_hp"))
    ub = form(HOST_ID=uid, RESULT=WIN, SCORE="60000", TEAM="1,2,3")
    st, d1, td1 = j.jreq(UPDATE, ub)
    contract(S, "JSON-D", d1, td1)
    S.check("JSON-D update applied once", isinstance(d1, dict) and d1.get("STATE") == "SUCCESS"
            and int(d1.get("boss_cur_hp")) == hp0 - 60000, td1[:200])
    S.check("JSON-E resend replays, HP unchanged",
            j.jreq(UPDATE, ub)[2] == td1
            and j.jreq(RANK, form(HOST_ID=uid))[1].get("BOSS_HP") == str(hp0 - 60000))

    saved = json.loads(savef.read_text(encoding="utf-8"))
    saved["DATA1"] = f"{uid},100000,0"
    saved["boss_ticket_left"] = "0"
    saved["boss_enter_count"] = "20"
    savef.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    st, lg, tlg = j.jreq(ENTER, form(HOST_ID=uid, MODE="ENTRY_GOLD", TEAM="1,2,3"))
    S.check("JSON-L ENTRY_GOLD writes gold 100000->97000 to the save file",
            isinstance(lg, dict) and lg.get("s_add_gold") == "97000"
            and json.loads(savef.read_text(encoding="utf-8")).get("DATA1", "").split(",")[1] == "97000",
            f"{lg.get('s_add_gold')} {tlg[:140]}")

    S.section("T. legacy attendance ticket stubs")
    # Close the ENTRY_GOLD match opened above first: while it is still ACTIVE the
    # enter below replays it (correct per the retry rule) and charges nothing.
    j.jreq(UPDATE, form(HOST_ID=uid, RESULT=WIN, SCORE="1000", TEAM="1,2,3"))
    savef.write_text(json.dumps({"USER_NAME": uid, "DATA1": f"{uid},100000,0"},
                                ensure_ascii=False), encoding="utf-8")
    j.req(TIK_SET, form(HOST_ID=uid, TIKET="10", ETC="dau tien"))
    st, txt = j.req(TIK_GET, form(HOST_ID=uid))
    S.check("T ticket read answers a bare number (parseInt)", txt.strip() == "10", txt[:120])
    st, te, tte = j.jreq(ENTER, form(HOST_ID=uid, MODE="ENTRY_TICKET", TEAM="1,2,3"))
    S.check("T enter charged 10->9", isinstance(te, dict) and te.get("STATE") == "SUCCESS"
            and te.get("cur_ticket") == "9", tte[:200])
    j.req(TIK_SET, form(HOST_ID=uid, TIKET="10", ETC="mo lai man"))
    st, txt = j.req(TIK_GET, form(HOST_ID=uid))
    S.check("T day-guard: reopening attendance does not refill", txt.strip() == "9", txt[:120])

    S.section("JSON-J. restart keeps boss state + save")
    before = j.jreq(RANK, form(HOST_ID=uid))[1]
    j.stop()
    j.start()
    after = j.jreq(RANK, form(HOST_ID=uid))[1]
    S.check("JSON-J HP survived restart",
            after.get("BOSS_HP") == before.get("BOSS_HP")
            and after.get("TOT_SCORE") == before.get("TOT_SCORE") == "61000",
            json.dumps(after, ensure_ascii=False)[:200])
    S.check("JSON-J sidecar still present", (jdir / "test_save.boss.json").is_file())


# ------------------------------------------------- season (in-process clock)

def t_season(S, kdb):
    S.section("K. season expiry rolls exactly once (in-process, fake clock)")
    import serve
    for h in list(serve.LOG.handlers):
        serve.LOG.removeHandler(h)
    serve.LOG.addHandler(logging.FileHandler(TEST_DIR / "k_serve.log",
                                             encoding="utf-8", delay=True))
    serve.init_db(str(kdb))
    serve.UNIQ_ID = "k_user"
    serve.BOSS_MAX_HP = 1000            # test override, same hook as BOSS_MAX_HP env
    tick = [1_700_000_000]
    serve._boss_now = lambda: tick[0]
    seed_save(kdb, "k_user", "k_user,0,0")

    fp0 = serve._boss_fingerprint({"RESULT": WIN, "SCORE": "5", "RUN_COUNT": "1"})
    fp1 = serve._boss_fingerprint({"RESULT": WIN, "SCORE": "5", "RUN_COUNT": "99",
                                   "USER_KEY": "x", "IS_SYNC": "1", "VERSION": "v"})
    S.check("K fingerprint ignores RUN_COUNT/USER_KEY/IS_SYNC/VERSION", fp0 == fp1)
    S.check("K fingerprint still tracks SCORE",
            fp0 != serve._boss_fingerprint({"RESULT": WIN, "SCORE": "6"}))
    S.check("K fingerprint: canonical WIN == wire mojibake WIN",
            fp0 == serve._boss_fingerprint({"RESULT": WIN_WIRE, "SCORE": "5"}))
    S.check("K fingerprint: canonical LOSE == wire mojibake LOSE",
            serve._boss_fingerprint({"RESULT": LOSE, "SCORE": "5"})
            == serve._boss_fingerprint({"RESULT": LOSE_WIRE, "SCORE": "5"}))
    S.check("K fingerprint: WIN still differs from LOSE",
            fp0 != serve._boss_fingerprint({"RESULT": LOSE, "SCORE": "5"}))

    r1 = json.loads(serve.boss_ranking_text())
    S.check("K season created at max_hp", r1.get("STATE") == "SUCCESS"
            and r1.get("BOSS_HP") == "1000", json.dumps(r1, ensure_ascii=False)[:200])
    e1 = json.loads(serve.boss_enter_text({"MODE": "ENTRY_TICKET", "TEAM": "1,2,3"}))
    S.check("K enter ok (ticket 9)", e1.get("STATE") == "SUCCESS"
            and e1.get("cur_ticket") == "9", json.dumps(e1, ensure_ascii=False)[:200])
    u1 = json.loads(serve.boss_result_text({"RESULT": WIN, "SCORE": "400", "TEAM": "1,2,3"}))
    S.check("K damage 400 applied", u1.get("STATE") == "SUCCESS"
            and u1.get("boss_cur_hp") == "600" and u1.get("TOT_SCORE") == "400",
            json.dumps(u1, ensure_ascii=False)[:200])
    e2 = json.loads(serve.boss_enter_text({"MODE": "ENTRY_TICKET", "TEAM": "1,2,3"}))
    S.check("K a second session is open at roll time", e2.get("STATE") == "SUCCESS")

    st1 = db_one(kdb, "SELECT season_start,cur_hp FROM boss_state WHERE boss_num=1")
    tick[0] += 7 * 86400 + 10
    r2 = json.loads(serve.boss_ranking_text())
    S.check("K roll: HP refilled + board cleared", r2.get("BOSS_HP") == "1000"
            and r2.get("TOT_SCORE") == "0" and r2.get("ranking_list") == [],
            json.dumps(r2, ensure_ascii=False)[:250])
    st2 = db_one(kdb, "SELECT season_start,season_end,cur_hp FROM boss_state WHERE boss_num=1")
    S.check("K roll happened at the fake now and once", st2[0] == tick[0]
            and st2[0] != st1[0] and st2[2] == 1000, str(st2))
    r3 = json.loads(serve.boss_ranking_text())
    st3 = db_one(kdb, "SELECT season_start,season_end,cur_hp FROM boss_state WHERE boss_num=1")
    S.check("K next read does not re-roll", st3[0] == st2[0]
            and st3[1] - st3[0] == 7 * 86400, f"{st2} -> {st3} r3={r3.get('BOSS_HP')}")
    old = json.loads(serve.boss_result_text({"RESULT": WIN, "SCORE": "100", "TEAM": "1,2,3"}))
    S.check("K old-season session retired -> -101", old.get("STATE") == "ERROR"
            and old.get("CODE") == "-101", json.dumps(old, ensure_ascii=False)[:200])
    e3 = json.loads(serve.boss_enter_text({"MODE": "ENTRY_TICKET", "TEAM": "1,2,3"}))
    S.check("K new season allows a fresh enter", e3.get("STATE") == "SUCCESS",
            json.dumps(e3, ensure_ascii=False)[:200])


# ------------------------------------------ atomic JSON save (in-process)

def t_atomic(S):
    S.section("S. atomic JSON save: fault injection (in-process)")
    import serve
    for h in list(serve.LOG.handlers):
        serve.LOG.removeHandler(h)
    serve.LOG.addHandler(logging.FileHandler(TEST_DIR / "s_serve.log",
                                             encoding="utf-8", delay=True))
    sdir = TEST_DIR / "atomic"
    sdir.mkdir(parents=True, exist_ok=True)
    sfile = sdir / "save.json"
    orig = {"USER_NAME": "atomic_user", "DATA1": "atomic_user,50,0"}
    sfile.write_text(json.dumps(orig, ensure_ascii=False), encoding="utf-8")
    before_bytes = sfile.read_bytes()
    tmp = sfile.with_name(sfile.name + ".tmp")

    saved_db, saved_save = serve.DB_FILE, serve.SAVE_FILE
    real_replace = os.replace

    def boom(a, b=None):
        raise OSError("replace failed (injected)")

    try:
        serve.DB_FILE = None
        serve.SAVE_FILE = sfile
        os.replace = boom
        serve.store_save({"USER_NAME": "atomic_user", "DATA1": "atomic_user,51,0"})
    finally:
        os.replace = real_replace
    S.check("S fail-before-replace: original save byte-identical",
            sfile.read_bytes() == before_bytes)
    S.check("S fail-before-replace: original still parses to the old payload",
            json.loads(sfile.read_text(encoding="utf-8")) == orig)
    S.check("S fail-before-replace: temp cleaned up best-effort", not tmp.exists())

    try:
        serve.DB_FILE = None
        serve.SAVE_FILE = sfile
        newp = {"USER_NAME": "atomic_user", "DATA1": "atomic_user,51,0"}
        serve.store_save(newp)
    finally:
        serve.DB_FILE, serve.SAVE_FILE = saved_db, saved_save
    S.check("S successful store: new save parses to the new payload",
            json.loads(sfile.read_text(encoding="utf-8")) == newp)
    S.check("S successful store: no temp file left", not tmp.exists())


# ---------------------------------------------------------------- UI helper

def run_ui(args):
    """Private instance for the browser smoke test. Uses a COPY of a real save
    (the original file is only read) and its own sidecar + DB next to it."""
    d = TEST_DIR / "ui"
    d.mkdir(parents=True, exist_ok=True)
    src = BASE / "save_anh.json"
    dst = d / "ui_save.json"
    data = None
    if src.is_file():
        for _ in range(10):
            try:
                data = json.loads(src.read_text(encoding="utf-8"))
                break
            except Exception:
                time.sleep(0.3)
    if data is None:
        data = {"USER_NAME": "ELDORADO_OFFLINE_0001", "DATA1": "ELDORADO_OFFLINE_0001,500000,0"}
    dst.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    port = args.ui_port or free_port(8629)
    inst = Instance("ui", port, ["--save-file", str(dst),
                                 "--uniq-id", "ELDORADO_OFFLINE_0001",
                                 "--log", str(d / "serve.log")])
    inst.start()
    print(f"UI instance ready on port {port}")
    print(f"  boot: http://127.0.0.1:{port}/ELDORADO_WEB/source_20240722/"
          f"index__mobile.html#sign=offline&time=0")
    print(f"  save copy: {dst}   (original {src} only read)")
    print("Ctrl+C (or kill this process) to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        inst.stop()


# ------------------------------------------------------------------- runner

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true", help="keep _boss_test/ afterwards")
    ap.add_argument("--ui", action="store_true",
                    help="start the private UI instance and wait (browser smoke test)")
    ap.add_argument("--ui-port", type=int, default=0)
    args = ap.parse_args()
    if args.ui:
        run_ui(args)
        return

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    S = Suite()
    core_db = TEST_DIR / "core" / "core.db"
    drain_db = TEST_DIR / "drain" / "drain.db"
    insts = []
    try:
        c = Instance("core", free_port(8577), ["--db", str(core_db)])
        insts.append(c)
        c.start()
        t_core(S, c, core_db)

        d = Instance("drain", free_port(8587), ["--db", str(drain_db)],
                     env_extra={"BOSS_MAX_HP": "1000"})
        insts.append(d)
        d.start()
        t_drain(S, d, drain_db)

        j = Instance("json", free_port(8597), ["--save-file", str(TEST_DIR / "json" / "test_save.json")])
        insts.append(j)
        j.start()
        t_json(S, j, j.dir)

        t_season(S, TEST_DIR / "k.db")
        t_atomic(S)
    finally:
        for i in insts:
            i.stop()

    print(f"\n==== {S.n - len(S.fails)}/{S.n} checks passed ====")
    if S.fails:
        print("FAILED:")
        for n in S.fails:
            print(f"  - {n}")
    if args.keep:
        print(f"artifacts kept in {TEST_DIR}")
    else:
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        print("test artifacts removed (use --keep to inspect)")
    raise SystemExit(1 if S.fails else 0)


if __name__ == "__main__":
    main()

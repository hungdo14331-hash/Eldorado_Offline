"""
Test cho guild_backend.py (guild thường, giai đoạn 1).

Chạy trực tiếp module với SQLite tạm, không cần dựng HTTP server: phần logic
cần kiểm là DB + shape response, còn đường dẫn URL chỉ có 3 dòng nối trong
serve.py (route "update_guild_inter.php"/"update_guild_main.php") và test route
ở đây đã phủ đúng phần ghép `json_obj` + `act`.

Bốn bẫy được khoá bằng test vì sai là client vỡ:
  1. body KHÔNG được chứa chuỗi "error" (transport coi là lỗi mạng, callback
     không chạy).
  2. `CGM_NO_GUILD` chỉ dùng khi thật sự bị kick.
  3. `cur_member`/`max_member` và `guild_data`/`member_data` phải ở top-level.
  4. `season_data` phải đủ field (client đọc không guard).
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import guild_backend as gb


def save_payload(ruby=50000, gold=1000000, cloud=1000, user="pilot"):
    d1 = ["0"] * 21
    d1[1] = str(gold)
    d1[2] = str(ruby)
    return json.dumps({"USER_NAME": user, "DATA1": ",".join(d1),
                       "cloud_piece": str(cloud), "tickets": {}})


class GuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = sqlite3.connect(str(Path(self.tmp.name) / "g.db"))
        self.lock = __import__("threading").RLock()
        # `saves` do serve.init_db tạo, không thuộc guild -> tự tạo ở đây.
        self.db.execute("CREATE TABLE IF NOT EXISTS saves (id TEXT PRIMARY KEY, payload TEXT)")
        gb.init_db(self.db, self.lock)
        self.db.commit()
        self.n = 0
        self.users = {}

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    # --- helpers ----------------------------------------------------------
    def account(self, ruby=50000, user="pilot", level=40):
        self.n += 1
        uid = "u%d" % self.n
        self.users[uid] = user
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO saves (id,payload) VALUES (?,?)",
                            (uid, save_payload(ruby=ruby, user=user)))
            self.db.commit()
        return uid

    def call(self, uid, act, group="guild_inter", level=40, user=None, **extra):
        data = {"act": act, "USER_NAME": self.users.get(uid, "pilot") if user is None else user,
                "user_level": level, "profile_num": 101, "HOST_ID": uid}
        data.update(extra)
        body = json.dumps({"crypt": 0, "url": "x",
                           "json_obj": json.dumps(data, ensure_ascii=False)})
        path = "/ELDORADO_WEB/Guild/update_guild_%s.php" % group.replace("guild_", "")
        with self.lock:
            status, text = gb.guild_dispatch(path, body, self.db, self.lock, uid)
        return status, json.loads(text)

    def create_guild(self, uid, name="Alpha", gtype="free", ruby=50000, level=40):
        st, r = self.call(uid, "insert_new_guild", guild_name=name, guild_type=gtype,
                          level=level, ruby=ruby,
                          guild_flag={"flagImg": "flag_green3.png", "symbolImg": "flagsymbol7.png"})
        self.assertEqual("ok", r["result"], r)
        return r["data"]

    def member_rows(self, name=None):
        if name:
            return self.q("SELECT * FROM guild_members WHERE guild_name=?", (name,))
        return self.q("SELECT * FROM guild_members")

    def ruby_of(self, uid):
        row = self.db.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
        return gb._ruby_of(json.loads(row[0]))

    def spend_ruby(self, uid, amount):
        """Mô phỏng phía client: sau khi nhận "ok", client tự trừ DATA1[2] rồi
        ghi lại save. Server không trừ, nên test phải tự giảm ruby nếu muốn
        kiểm tra nhánh 'không đủ' ở lượt gọi sau."""
        row = self.db.execute("SELECT payload FROM saves WHERE id=?", (uid,)).fetchone()
        pay = json.loads(row[0])
        d1 = pay["DATA1"].split(",")
        d1[2] = str(int(d1[2]) - amount)
        pay["DATA1"] = ",".join(d1)
        self.db.execute("UPDATE saves SET payload=? WHERE id=?",
                        (json.dumps(pay), uid))
        self.db.commit()

    def q(self, sql, args=()):
        cur = self.db.cursor()
        cur.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in cur.execute(sql, args).fetchall()]
        finally:
            cur.close()

    # --- rong ten / tao guild --------------------------------------------
    def test_check_guild_name(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual("ok", self.call(a, "check_guild_name", guild_name="Beta")[1]["result"])
        self.assertEqual("duplication",
                         self.call(a, "check_guild_name", guild_name="Alpha")[1]["result"])
        self.assertEqual("long",
                         self.call(a, "check_guild_name", guild_name="B" * 30)[1]["result"])
        self.assertEqual("str_not_allowed",
                         self.call(a, "check_guild_name", guild_name="a<b")[1]["result"])

    # --- shape bat buoc client, ke ca khi chay khong co --db ---------------
    def test_no_db_branch_keeps_client_switch_shape(self):
        # Client `get_guild_normal`: switch(result){case"ok": switch(data){
        # case"no_guild":...}}. Tra result="no_guild" se roi vao default va
        # bam notice "Error - GGN e".
        body = json.dumps({"crypt": 0, "url": "x",
                           "json_obj": json.dumps({"act": "get_guild_normal",
                                                   "USER_NAME": "pilot"})})
        st, text = gb.guild_dispatch("/ELDORADO_WEB/Guild/update_guild_inter.php",
                                     body, None, self.lock, "u1")
        r = json.loads(text)
        self.assertEqual(200, st)
        self.assertEqual("ok", r["result"])
        self.assertEqual("no_guild", r["data"])
        self.assertIn("season_data", r)

    def test_check_guild_member_switches_on_result_not_data(self):
        # Client switch(result){case"no_guild"/"has_guild"}.
        a = self.account()
        r = self.call(a, "check_guild_member")[1]
        self.assertEqual("no_guild", r["result"])
        for k in ("exit_remain_time", "exit_time", "season_data"):
            self.assertIn(k, r, "thieu field: %s" % k)
        self.create_guild(a, "Alpha")
        r = self.call(a, "check_guild_member")[1]
        self.assertEqual("has_guild", r["result"])
        self.assertEqual("Alpha", r["data"]["guild_name"])
        self.assertIn("season_data", r)

    def test_guild_data_has_every_field_client_reads(self):
        a = self.account()
        d = self.create_guild(a, "Alpha")
        for k in ("guild_name", "guild_type", "guild_flag", "guild_notice", "guild_money",
                  "guild_buff_level", "guild_buff_value", "guild_buff_next_price",
                  "guild_position", "guild_cur_member", "guild_max_member",
                  "guild_next_max_member", "guild_add_member_ruby_value",
                  "guild_master", "guild_data_mine"):
            self.assertIn(k, d, "thieu field guild_data: %s" % k)
        self.assertEqual("flag_green3.png", d["guild_flag"]["flagImg"])
        self.assertEqual("flagsymbol7.png", d["guild_flag"]["symbolImg"])
        self.assertEqual("MASTER", d["guild_position"])
        self.assertEqual(1, d["guild_cur_member"])
        self.assertEqual(gb.GUILD_BASE_MAX_MEMBER, d["guild_max_member"])
        self.assertEqual(gb.GUILD_BASE_MAX_MEMBER + 1, d["guild_next_max_member"])
        self.assertEqual(gb.GUILD_ADD_MEMBER_RUBY, d["guild_add_member_ruby_value"])
        # hook json_secure doc guild_data.guild_data_mine.guild_gold_bar -> USER.goldbar
        self.assertEqual(0, d["guild_data_mine"]["guild_gold_bar"])
        self.assertEqual({"cloud": 0, "ruby": 0, "gold": 0},
                         d["guild_data_mine"]["guild_today_donate"])
        self.assertEqual("pilot", d["guild_master"]["name"])

    def test_guild_type_is_number_in_response(self):
        a = self.account()
        # request gui string, response phai la so (client so sanh ==1)
        self.assertEqual(1, self.create_guild(a, "FreeOne", gtype="free")["guild_type"])
        b = self.account()
        self.assertEqual(2, self.create_guild(b, "ApproveOne", gtype="approve")["guild_type"])

    def test_insert_new_guild_guards(self):
        low = self.account(ruby=50000)
        self.assertEqual("not_enough_ruby",
                         self.call(low, "insert_new_guild", guild_name="NoRuby", level=10)[1]["result"])
        broke = self.account(ruby=10)
        self.assertEqual("not_enough_ruby",
                         self.call(broke, "insert_new_guild", guild_name="Poor")[1]["result"])
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual("already",
                         self.call(a, "insert_new_guild", guild_name="Beta")[1]["result"])
        self.assertEqual("no_user_name",
                         self.call(self.account(), "insert_new_guild", guild_name="Beta", user="")[1]["result"])

    def test_create_does_not_double_charge(self):
        """Client tu tru ruby sau khi nhan "ok" (set_ruby_gold). Server chi kiem
        tra du khong tru -> DATA1[2] phai nguyen ven."""
        a = self.account(ruby=50000)
        self.create_guild(a, "Alpha")
        row = self.db.execute("SELECT payload FROM saves WHERE id=?", (a,)).fetchone()
        self.assertEqual(50000, gb._ruby_of(json.loads(row[0])))

    def test_only_one_guild_per_player(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account()
        self.create_guild(b, "Bravo")
        # join guild thu hai phai bi tu choi
        self.assertEqual("duplication",
                         self.call(a, "join_open_guild", guild_name="Bravo")[1]["result"])

    # --- xem danh sach / tim kiem ----------------------------------------
    def test_get_guild_list_item_shape_and_sort(self):
        a = self.account()
        b = self.account()
        c = self.account()
        self.create_guild(a, "Alpha", gtype="free")
        self.create_guild(b, "Bravo", gtype="approve")
        self.create_guild(c, "Charlie", gtype="free")
        _, r = self.call(a, "get_guild_list")
        self.assertEqual("ok", r["result"])
        self.assertEqual(3, len(r["data"]))
        it = r["data"][0]
        for k in ("guild_name", "guild_type", "guild_flag", "guild_cur_member",
                  "guild_max_member", "guild_buff_level", "guild_master"):
            self.assertIn(k, it, "thieu field item: %s" % k)
        for k in ("name", "platform", "level"):
            self.assertIn(k, it["guild_master"])
        self.assertEqual({"Alpha", "Bravo", "Charlie"},
                         {x["guild_name"] for x in r["data"]})
        _, r2 = self.call(a, "get_guild_list", search_str="rav")
        self.assertEqual(["Bravo"], [x["guild_name"] for x in r2["data"]])
        _, r3 = self.call(a, "get_guild_list", sort_type="open")
        self.assertEqual({"Alpha", "Charlie"}, {x["guild_name"] for x in r3["data"]})
        _, r4 = self.call(a, "get_guild_list", sort_type="approve")
        self.assertEqual(["Bravo"], [x["guild_name"] for x in r4["data"]])

    # --- join --------------------------------------------------------------
    def test_join_free_guild(self):
        a = self.account()
        self.create_guild(a, "Alpha", gtype="free")
        b = self.account(user="bravo")
        st, r = self.call(b, "join_open_guild", guild_name="Alpha")
        self.assertEqual("ok", r["result"])
        self.assertEqual("Alpha", r["data"]["guild_name"])
        self.assertEqual(2, r["data"]["guild_cur_member"])
        self.assertEqual("MEMBER", r["data"]["guild_position"])
        # `a` (pilot) là chủ guild; `b` chỉ là member thường.
        self.assertEqual("pilot", r["data"]["guild_master"]["name"])

    def test_cannot_join_approve_guild_directly(self):
        a = self.account()
        self.create_guild(a, "Alpha", gtype="approve")
        b = self.account(user="bravo")
        self.assertEqual("not_yet", self.call(b, "join_open_guild", guild_name="Alpha")[1]["result"])

    def test_join_when_full(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.db.execute("UPDATE guilds SET max_member=1 WHERE guild_name='Alpha'")
        self.db.commit()
        b = self.account(user="bravo")
        self.assertEqual("full", self.call(b, "join_open_guild", guild_name="Alpha")[1]["result"])

    def test_join_approve_flow(self):
        a = self.account()
        self.create_guild(a, "Alpha", gtype="approve")
        b = self.account(user="bravo")
        st, r = self.call(b, "join_approve_guild", guild_name="Alpha")
        self.assertEqual("ok", r["result"])
        self.assertEqual(1, r["my_approve_cnt"])
        # xin lai -> already
        self.assertEqual("already",
                         self.call(b, "join_approve_guild", guild_name="Alpha")[1]["result"])
        # master xem danh sach xin: phai co member_no
        _, lst = self.call(a, "get_approve_list", group="guild_main")
        self.assertEqual("ok", lst["result"])
        self.assertEqual(1, len(lst["data"]))
        self.assertIn("member_no", lst["data"][0])
        for k in ("user_name", "user_level", "profile_num", "platform"):
            self.assertIn(k, lst["data"][0])
        # top-level cur_member/max_member (khac guild_cur_member trong guild_data)
        self.assertEqual(1, lst["cur_member"])
        self.assertEqual(gb.GUILD_BASE_MAX_MEMBER, lst["max_member"])
        # master duyet
        no = lst["data"][0]["member_no"]
        _, ap = self.call(a, "update_guild_member", group="guild_main",
                          act_detail="approve_member", member_no=no, approve_reject="APPROVE")
        self.assertEqual("ok", ap["result"])
        self.assertEqual(2, ap["member_data"][0] and len(ap["member_data"]))
        self.assertEqual(0, len(self.db.execute(
            "SELECT * FROM guild_applies WHERE guild_name='Alpha'").fetchall()))

    def test_approve_list_caps_at_five(self):
        a = self.account()
        self.create_guild(a, "Alpha", gtype="approve")
        for i in range(6):
            u = self.account(user="p%d" % i)
            r = self.call(u, "join_approve_guild", guild_name="Alpha")[1]
            self.assertEqual("over" if i == 5 else "ok", r["result"])

    def test_reject_keeps_player_out(self):
        a = self.account()
        self.create_guild(a, "Alpha", gtype="approve")
        b = self.account(user="bravo")
        self.call(b, "join_approve_guild", guild_name="Alpha")
        _, lst = self.call(a, "get_approve_list", group="guild_main")
        self.call(a, "update_guild_member", group="guild_main", act_detail="approve_member",
                  member_no=lst["data"][0]["member_no"], approve_reject="REJECT")
        self.assertEqual(0, len(self.member_rows("Alpha")) - 1)  # chi con master

    # --- member list -------------------------------------------------------
    def test_get_member_list_shape(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        _, r = self.call(a, "get_member_list", group="guild_main", guild_name="Alpha",
                         order_by="SEASON_SCORE")
        self.assertEqual("ok", r["result"])
        self.assertEqual(2, r["cur_member"])
        self.assertEqual(gb.GUILD_BASE_MAX_MEMBER, r["max_member"])
        mine = [x for x in r["data"] if x["is_mine"] == "yes"]
        self.assertEqual(1, len(mine))
        self.assertEqual("pilot", mine[0]["user_name"])
        other = [x for x in r["data"] if x["is_mine"] == "no"][0]
        self.assertEqual("bravo", other["user_name"])
        for k in ("is_mine", "user_name", "platform", "user_level", "profile_num",
                  "season_score", "last_attendance"):
            self.assertIn(k, other, "thieu field member: %s" % k)
        # is_mine phai la chuoi "yes"/"no", khong phai bool
        self.assertNotIsInstance(other["is_mine"], bool)

    def test_outside_member_sees_no_guild(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        out = self.account(user="outsider")
        _, r = self.call(out, "get_member_list", group="guild_main")
        self.assertEqual([], r["data"])

    # --- kick / leave / transfer / delete ----------------------------------
    def test_kick_then_target_gets_cgm_no_guild(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        _, r = self.call(a, "update_guild_member", group="guild_main",
                         act_detail="kick_member", member_name="bravo")
        self.assertEqual("ok", r["result"])
        self.assertEqual(1, len(self.member_rows("Alpha")))
        # BAY 2: nguoi bi kick phai thay CGM_NO_GUILD, va chi mot lan
        _, n1 = self.call(b, "get_guild_normal")
        self.assertEqual("CGM_NO_GUILD", n1["result"])
        _, n2 = self.call(b, "get_guild_normal")
        self.assertEqual("no_guild", n2["data"])
        self.assertEqual(0, len(self.member_rows()) - 1)

    def test_master_cannot_leave_but_member_can(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        self.assertEqual("master_cannot_leave",
                         self.call(a, "update_leave_guild", group="guild_main",
                                   guild_name="Alpha")[1]["result"])
        self.assertEqual("ok",
                         self.call(b, "update_leave_guild", group="guild_main",
                                   guild_name="Alpha")[1]["result"])
        self.assertEqual(1, len(self.member_rows("Alpha")))

    def test_transfer_master(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        r = self.call(a, "update_guild_member", group="guild_main",
                      act_detail="transfer_guild_master", member_name="bravo")[1]
        self.assertEqual("ok", r["result"])
        rows = {x["user_name"]: x["is_master"] for x in self.member_rows("Alpha")}
        self.assertEqual(1, rows["bravo"])
        self.assertEqual(0, rows["pilot"])
        # gio master moi duoc buff
        self.assertEqual("ok", self.call(b, "update_guild_buff", group="guild_main",
                                         guild_name="Alpha")[1].get("result") in ("ok", "not_enough_money")
                         and "ok")

    def test_guild_delete_kicks_everyone(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        r = self.call(a, "update_guild_member", group="guild_main", act_detail="guild_delete")[1]
        self.assertEqual("ok", r["result"])
        self.assertEqual(0, len(self.member_rows()))
        self.assertEqual(0, len(self.db.execute(
            "SELECT * FROM guilds WHERE guild_name='Alpha'").fetchall()))
        _, n1 = self.call(b, "get_guild_normal")
        self.assertEqual("CGM_NO_GUILD", n1["result"])
        _, n2 = self.call(a, "get_guild_normal")
        self.assertEqual("no_guild", n2["data"])

    def test_only_master_mutates(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        for detail, extra in (("change_notice", {"notice_str": "hi"}),
                              ("kick_member", {"member_name": "pilot"}),
                              ("transfer_guild_master", {"member_name": "pilot"}),
                              ("guild_delete", {}),
                              ("guild_add_max_member", {})):
            r = self.call(b, "update_guild_member", group="guild_main",
                          act_detail=detail, **extra)[1]
            if detail == "change_notice":
                continue  # doi thong bao ai cung duoc
            self.assertEqual("not_yet", r["result"], "%s phai bi chan" % detail)

    def test_change_notice_limits(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual("ok", self.call(a, "update_guild_member", group="guild_main",
                                        act_detail="change_notice", notice_str="hello")[1]["result"])
        self.assertEqual("hello", self.db.execute(
            "SELECT notice FROM guilds WHERE guild_name='Alpha'").fetchone()[0])
        self.assertEqual("long", self.call(a, "update_guild_member", group="guild_main",
                                           act_detail="change_notice",
                                           notice_str="x" * 71)[1]["result"])
        self.assertEqual("str_not_allowed", self.call(a, "update_guild_member", group="guild_main",
                                                      act_detail="change_notice",
                                                      notice_str="a<b")[1]["result"])

    # --- slot / buff / mission / donate ------------------------------------
    def test_add_member_slot(self):
        a = self.account(ruby=50000)
        self.create_guild(a, "Alpha")
        r = self.call(a, "update_guild_member", group="guild_main",
                      act_detail="guild_add_max_member")[1]
        self.assertEqual("ok", r["result"])
        self.assertEqual(gb.GUILD_BASE_MAX_MEMBER + 1, r["guild_data"]["guild_max_member"])
        # client tu tru ruby -> server khong tru
        row = self.db.execute("SELECT payload FROM saves WHERE id=?", (a,)).fetchone()
        self.assertEqual(50000, gb._ruby_of(json.loads(row[0])))
        poor = self.account(ruby=3000)
        self.create_guild(poor, "Poor", ruby=3000)
        self.spend_ruby(poor, 3000)  # client đã trừ 3.000 ruby lúc tạo guild
        self.assertEqual(0, self.ruby_of(poor))
        self.assertEqual("not_enough_ruby",
                         self.call(poor, "update_guild_member", group="guild_main",
                                   act_detail="guild_add_max_member")[1]["result"])

    def test_guild_buff_respects_money_then_max_level(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual(0, self.q("SELECT money FROM guilds WHERE guild_name='Alpha'")[0]["money"])
        # price[0] = 0 -> level 1 nâng miễn phí dù quỹ guild rỗng.
        self.assertEqual(0, gb.GUILD_BUFF_PRICE[0])
        r = self.call(a, "update_guild_buff", group="guild_main", guild_name="Alpha")[1]
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(1, r["data"]["guild_buff_level"])
        # level 2 tốn tiền, quỹ rỗng -> chặn.
        self.assertEqual("not_enough_money",
                         self.call(a, "update_guild_buff", group="guild_main",
                                   guild_name="Alpha")[1]["result"])
        self.db.execute("UPDATE guilds SET money=99999999")
        self.db.commit()
        for want in range(2, gb.GUILD_BUFF_MAX_LEVEL + 1):
            r = self.call(a, "update_guild_buff", group="guild_main", guild_name="Alpha")[1]
            self.assertEqual("ok", r["result"], r)
            self.assertEqual(want, r["data"]["guild_buff_level"])
        self.assertEqual("max_level",
                         self.call(a, "update_guild_buff", group="guild_main",
                                   guild_name="Alpha")[1]["result"])
        self.assertEqual(gb.GUILD_BUFF_VALUE[gb.GUILD_BUFF_MAX_LEVEL],
                         self.call(a, "get_guild_normal")[1]["data"]["guild_buff_value"])

    def test_guild_mission_data_has_all_four_keys(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        r = self.call(a, "update_guild_mission", group="guild_main", guild_name="Alpha",
                      guild_mission_index=1, guild_mission_act="dungeon",
                      guild_act_value=5, guild_mission_value=5)[1]
        self.assertEqual("ok", r["result"])
        self.assertEqual({"attendance", "dungeon", "pvp", "cloud_garden"},
                         set(r["data"]["mission_data"]))
        self.assertEqual(1, r["data"]["mission_data"]["dungeon"])
        self.assertEqual(0, r["data"]["mission_data"]["pvp"])
        # index ngoai danh
        self.assertEqual("no", self.call(a, "update_guild_mission", group="guild_main",
                                         guild_mission_index=99)[1]["result"])

    def test_mission_screen_entry_call_does_not_cheat(self):
        """Client goi update_guild_mission(0) khi vao man, khong gui value."""
        a = self.account()
        self.create_guild(a, "Alpha")
        r = self.call(a, "update_guild_mission", group="guild_main", guild_name="Alpha",
                      guild_mission_index=0, guild_mission_act="attendance")[1]
        self.assertEqual("ok", r["result"])
        self.assertEqual(0, r["data"]["mission_data"]["attendance"])

    def test_donate_once_per_day(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        r = self.call(a, "update_member_donate", group="guild_main", guild_name="Alpha",
                      act_detail="RUBY", act_value=10)[1]
        self.assertEqual("ok", r["result"])
        self.assertEqual(20, r["guild_data_mine"]["guild_season_score"])
        self.assertEqual(8, r["guild_data_mine"]["guild_gold_bar"])
        self.assertEqual(1, r["guild_data_mine"]["guild_today_donate"]["ruby"])
        again = self.call(a, "update_member_donate", group="guild_main", guild_name="Alpha",
                          act_detail="RUBY", act_value=10)[1]
        self.assertEqual("already", again["result"])
        self.assertEqual(20, again["guild_data_mine"]["guild_season_score"])
        g = self.q("SELECT money, season_score FROM guilds WHERE guild_name='Alpha'")[0]
        self.assertEqual(10, g["money"])
        self.assertEqual(20, g["season_score"])
        self.assertEqual("no", self.call(a, "update_member_donate", group="guild_main",
                                         act_detail="DIAMOND", act_value=1)[1]["result"])

    def test_donate_rejects_when_resource_short(self):
        # Tạo guild cần 3.000 ruby; client trừ ngay sau khi nhận "ok". Nên
        # người chơi vừa tạo guild xong có thể không còn đủ ruby để quyên.
        a = self.account(ruby=3000)
        self.create_guild(a, "Alpha", ruby=3000)
        self.spend_ruby(a, 3000)
        self.assertEqual(0, self.ruby_of(a))
        r = self.call(a, "update_member_donate", group="guild_main", guild_name="Alpha",
                      act_detail="RUBY", act_value=10)[1]
        self.assertEqual("not_enough", r["result"])

    # --- chat ---------------------------------------------------------------
    def test_chat_roundtrip_and_time_format(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual("ok", self.call(a, "send_guild_chat", group="guild_main",
                                         guild_name="Alpha", message="xin chao")[1]["result"])
        _, r = self.call(a, "get_guild_chat", group="guild_main", guild_name="Alpha")
        self.assertEqual("ok", r["result"])
        self.assertEqual(1, len(r["data"]))
        line = r["data"][0]
        self.assertRegex(line["update_time"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertEqual("xin chao", line["chat"])
        for k in ("host_id", "user_name", "platform", "etc"):
            self.assertIn(k, line)

    def test_chat_limits(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.assertEqual("empty", self.call(a, "send_guild_chat", group="guild_main",
                                            message="   ")[1]["result"])
        self.assertEqual("long", self.call(a, "send_guild_chat", group="guild_main",
                                           message="x" * 71)[1]["result"])
        self.assertEqual("ok", self.call(a, "send_guild_chat", group="guild_main",
                                         message="x" * 70)[1]["result"])

    def test_chat_trimmed_to_keep_window(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        for i in range(gb.GUILD_CHAT_KEEP + 10):
            self.call(a, "send_guild_chat", group="guild_main", message="m%d" % i)
        _, r = self.call(a, "get_guild_chat", group="guild_main")
        self.assertEqual(gb.GUILD_CHAT_KEEP, len(r["data"]))

    # --- season / entry gates ----------------------------------------------
    def test_season_data_present_always(self):
        a = self.account()
        for act in ("get_guild_normal", "check_guild_member"):
            r = self.call(a, act)[1]
            self.assertIn("season_data", r, act)
            for k in ("season_num", "season_start_date", "season_end_date"):
                self.assertIn(k, r["season_data"], "%s.%s" % (act, k))
        self.create_guild(a, "Alpha")
        for act in ("get_guild_normal", "check_guild_member"):
            r = self.call(a, act)[1]
            for k in ("season_num", "season_start_date", "season_end_date"):
                self.assertIn(k, r["season_data"], "%s.%s" % (act, k))

    def test_check_guild_member_states(self):
        a = self.account()
        r = self.call(a, "check_guild_member")[1]
        self.assertEqual("no_guild", r["result"])
        self.assertIn("exit_time", r)
        self.create_guild(a, "Alpha")
        r = self.call(a, "check_guild_member")[1]
        self.assertEqual("has_guild", r["result"])
        self.assertEqual("Alpha", r["data"]["guild_name"])

    def test_get_guild_normal_returns_object_not_weird_string(self):
        a = self.account()
        r = self.call(a, "get_guild_normal")[1]
        self.assertEqual("no_guild", r["data"])
        self.create_guild(a, "Alpha")
        r = self.call(a, "get_guild_normal")[1]
        self.assertIsInstance(r["data"], dict, "guild_data phai la OBJECT")

    def test_season_ranking_board(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.create_guild(b, "Bravo")
        self.db.execute("UPDATE guilds SET season_score=500 WHERE guild_name='Bravo'")
        self.db.commit()
        _, r = self.call(a, "get_guild_season_ranking_data", guild_name="Alpha")
        self.assertEqual("ok", r["result"])
        board = r["data"]["guild_season_ranking_data"]
        self.assertEqual(["Bravo", "Alpha"], [x["guild_name"] for x in board])
        for k in ("rank", "guild_name", "guild_flag", "season_score"):
            self.assertIn(k, board[0])
        self.assertEqual("Alpha", r["data"]["my_guild_season_ranking_data"]["guild_name"])
        # nguoi khong co guild -> my_... = null, van co board
        out = self.account(user="outsider")
        _, r2 = self.call(out, "get_guild_season_ranking_data", guild_name="none")
        self.assertIsNone(r2["data"]["my_guild_season_ranking_data"])

    # --- traps ---------------------------------------------------------------
    def test_no_response_body_contains_the_word_error(self):
        """Transport client kiem n.includes("error") -> popup loi mang, callback
        khong chay. Bat response nao cchu "error" la vo."""
        a = self.account()
        self.create_guild(a, "Alpha")
        b = self.account(user="bravo")
        self.call(b, "join_open_guild", guild_name="Alpha")
        calls = [
            ("check_guild_name", "guild_inter", {"guild_name": "a<b"}),
            ("check_guild_name", "guild_inter", {"guild_name": "x" * 40}),
            ("get_guild_normal", "guild_inter", {}),
            ("check_guild_member", "guild_inter", {}),
            ("get_guild_list", "guild_inter", {}),
            ("join_open_guild", "guild_inter", {"guild_name": "Alpha"}),
            ("join_approve_guild", "guild_inter", {"guild_name": "Alpha"}),
            ("get_guild_season_ranking_data", "guild_inter", {}),
            ("get_member_list", "guild_main", {"guild_name": "Alpha"}),
            ("get_approve_list", "guild_main", {"guild_name": "Alpha"}),
            ("get_guild_chat", "guild_main", {"guild_name": "Alpha"}),
            ("send_guild_chat", "guild_main", {"message": "hi"}),
            ("update_leave_guild", "guild_main", {"guild_name": "Alpha"}),
            ("update_guild_member", "guild_main", {"act_detail": "khong_ton_tai"}),
            ("update_guild_member", "guild_main", {"act_detail": "change_notice",
                                                   "notice_str": "a<b"}),
            ("update_guild_buff", "guild_main", {"guild_name": "Alpha"}),
            ("update_guild_mission", "guild_main", {"guild_mission_index": 99}),
            ("update_member_donate", "guild_main", {"act_detail": "DIAMOND"}),
            ("act_biet_khong_co", "guild_inter", {}),
        ]
        for act, group, extra in calls:
            _, r = self.call(b, act, group=group, **extra)
            self.assertNotIn("error", json.dumps(r, ensure_ascii=False).lower(),
                             "act %s tra chuoi 'error'" % act)

    def test_unknown_endpoint_and_anonymous(self):
        st, r = self.call("nobody", "get_guild_list", group="khong_co")
        self.assertEqual(404, st)
        body = json.dumps({"json_obj": json.dumps({"act": "get_guild_list"})})
        status, text = self.db and gb.guild_dispatch(
            "/Guild/update_guild_inter.php", body, self.db, self.lock, "")
        self.assertEqual(200, status)
        self.assertNotIn("error", text.lower())
        self.assertEqual("no", json.loads(text)["result"])

    def test_json_obj_accepts_both_encodings(self):
        """Client gui json_obj la object (ENABLE_CRYPT) hoac chuoi JSON."""
        a = self.account()
        self.create_guild(a, "Alpha")
        for payload in ({"crypt": 0, "json_obj": {"act": "get_guild_list"}},
                        {"crypt": 0, "json_obj": json.dumps({"act": "get_guild_list"})}):
            body = json.dumps(payload)
            with self.lock:
                _, text = gb.guild_dispatch("/Guild/update_guild_inter.php", body,
                                            self.db, self.lock, a)
            self.assertEqual("ok", json.loads(text)["result"], payload)

    def test_persistence_across_calls(self):
        a = self.account()
        self.create_guild(a, "Alpha")
        self.db.commit()
        got = self.db.execute(
            "SELECT guild_name, guild_type, max_member, master_id FROM guilds").fetchall()
        self.assertEqual(1, len(got))
        self.assertEqual(("Alpha", 1, gb.GUILD_BASE_MAX_MEMBER, a), tuple(got[0]))
        # mot nguoi khong the ghi de ban ghi cua nguoi khac
        b = self.account(user="bravo")
        self.assertEqual("no_guild", self.call(b, "get_guild_normal")[1]["data"])


if __name__ == "__main__":
    unittest.main()

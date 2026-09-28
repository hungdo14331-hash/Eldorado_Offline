"""Guild Shop (`update_guild_shop.php`) — act `guild_shop_purchase`.

Chay qua HTTP that cua serve.py nen bat duoc route sai va handler that.
Kiem tra phan client that su doc: `result`, `goldbar_cnt`, `reward_info`
(list object `{type, value}`), va tien phai tru tu `guild_members.gold_bar`.
"""

import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import serve
import guild_backend


def save_for(account):
    d1 = ["0"] * 21
    d1[1] = "1000"
    d1[2] = "50000"
    return {"USER_NAME": account, "DATA1": ",".join(d1),
            "cloud_piece": "1000", "bp": "10", "mails": []}


class GuildShopTests(unittest.TestCase):
    ACCOUNTS = ("g_sh_a", "g_sh_b")

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_guild_shop_")
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        serve.init_db(Path(cls.tmp.name) / "guild.db")
        for account in cls.ACCOUNTS:
            serve.add_account(account, "test-only-password")
        cls.server = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        serve.SRV_PORT = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        if serve.DB_CONN is not None:
            serve.DB_CONN.close()
            serve.DB_CONN = None
        serve.DB_FILE = None
        serve.REQUIRE_LOGIN = False
        serve.AUTH_SESSIONS.clear()
        cls.tmp.cleanup()

    def setUp(self):
        serve.AUTH_SESSIONS.clear()
        with serve.SAVE_LOCK:
            for account in self.ACCOUNTS:
                serve.db_store_save(account, save_for(account))
                for table in ("guild_members", "guild_applies", "guild_chat", "guilds",
                              "guild_shop_buy"):
                    serve.DB_CONN.execute("DELETE FROM %s" % table)
            serve.DB_CONN.execute(
                "UPDATE guild_members SET gold_bar=50000")
            serve.DB_CONN.commit()

    # --- helpers -----------------------------------------------------------
    def post(self, act, account=None, group="shop", **fields):
        fields["act"] = act
        fields.setdefault("user_level", 40)
        fields.setdefault("profile_num", 101)
        fields.setdefault("HOST_ID", account or "")
        fields.setdefault("language", "EN")
        path = "/Guild/update_guild_%s.php" % group
        form = urlencode({"crypt": 0, "url": path,
                          "json_obj": json.dumps(fields, ensure_ascii=False)})
        cookie = ("dol_session=" + serve.issue_auth_session(account)) if account else None
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=10)
        try:
            conn.request("POST", "/ELDORADO_WEB" + path,
                         body=form,
                         headers={"Content-Type": "application/x-www-form-urlencoded",
                                  **({"Cookie": cookie} if cookie else {})})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"__raw__": raw}
        finally:
            conn.close()

    def create(self, account, name):
        st, r = self.post("insert_new_guild", account, group="inter",
                          USER_NAME=account, guild_name=name, guild_type="free",
                          guild_flag=json.dumps({"flagImg": "flag_green3.png",
                                                 "symbolImg": "flagsymbol7.png"}))
        self.assertEqual("ok", r.get("result"), (st, r))
        serve.DB_CONN.execute("UPDATE guild_members SET gold_bar=50000")
        serve.DB_CONN.commit()

    def buy(self, account="g_sh_a", type_num=26, times=1, **extra):
        fields = {"guild_name": "SHOP", "type_num": type_num, "times": times,
                  "user_goldbar": 50000, "price": 4000, "char_reward": 2}
        fields.update(extra)
        return self.post("guild_shop_purchase", account, **fields)

    def top_up(self, amount=50000, account="g_sh_a"):
        serve.DB_CONN.execute("UPDATE guild_members SET gold_bar=? WHERE user_id=?",
                              (amount, account))
        serve.DB_CONN.commit()

    def gold_bar(self, account="g_sh_a"):
        return self.rows("SELECT gold_bar FROM guild_members WHERE user_id=?",
                         (account,))[0]["gold_bar"]

    def save_of(self, account="g_sh_a"):
        row = serve.DB_CONN.execute("SELECT payload FROM saves WHERE id=?",
                                   (account,)).fetchone()
        return json.loads(row[0])

    def mails(self, what, account="g_sh_a"):
        return [m["what_value"] for m in (self.save_of(account).get("mails") or [])
                if m.get("what") == what and "LUNAR" in str(m.get("why", ""))]

    def rows(self, sql, args=()):
        cur = serve.DB_CONN.cursor()
        cur.row_factory = __import__("sqlite3").Row
        try:
            return [dict(r) for r in cur.execute(sql, args).fetchall()]
        finally:
            cur.close()

    def setUpGuild(self):
        self.create("g_sh_a", "SHOP")

    # --- route / contract --------------------------------------------------
    def test_route_reaches_backend_and_unknown_act_rejected(self):
        self.setUpGuild()
        st, r = self.post("guild_shop_purchase_bogus", "g_sh_a")
        self.assertEqual("no", r.get("result"), r)
        st, r = self.buy()
        self.assertEqual(200, st, r)
        self.assertEqual("ok", r.get("result"), r)

    def test_success_shape_matches_client_reads(self):
        self.setUpGuild()
        st, r = self.buy()
        self.assertEqual("ok", r["result"], r)
        # Client: USER.goldbar = n.goldbar_cnt
        self.assertEqual(50000 - 4000, r["goldbar_cnt"], r)
        # Client: typeof t=="object" && t.length>0 -> S_POPUP_GACHA_RESULT
        self.assertIsInstance(r["reward_info"], list, r)
        self.assertTrue(r["reward_info"], r)
        for x in r["reward_info"]:
            self.assertIsInstance(x, dict, r)
            self.assertIn(x["type"], ("ITEM", "GOLD", "RUBY", "BP", "CLOUD"), x)
            self.assertIsInstance(x["value"], int, x)
        # Client gui `result` vao utilNotice khi default -> khong chua "error"
        self.assertNotIn("error", json.dumps(r).lower(), r)

    def test_ten_draw_card_charges_40000_and_returns_ten_rewards(self):
        self.setUpGuild()
        st, r = self.buy(type_num=27, times=10)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(50000 - 40000, r["goldbar_cnt"], r)
        self.assertEqual(10, len(r["reward_info"]), r)

    def test_server_price_wins_over_body_price(self):
        self.setUpGuild()
        st, r = self.buy(type_num=26, times=1, price=1, user_goldbar=10**9)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(50000 - 4000, r["goldbar_cnt"], r)
        self.assertEqual(46000, self.gold_bar())

    def test_not_enough_gold_bar_does_not_charge_or_grant(self):
        self.setUpGuild()
        serve.DB_CONN.execute("UPDATE guild_members SET gold_bar=3999")
        serve.DB_CONN.commit()
        st, r = self.buy()
        self.assertEqual("not_enough", r["result"], r)
        self.assertEqual(3999, self.gold_bar())
        self.assertEqual([], self.save_of().get("mails", []))

    def test_bad_card_or_times_is_rejected(self):
        self.setUpGuild()
        st, r = self.buy(type_num=0, times=1)          # card 1/2 la hero
        self.assertEqual("gs-bad-card", r["result"], r)
        st, r = self.buy(type_num=26, times=10)        # gia 10 lan cho card 1
        self.assertEqual("gs-bad-times", r["result"], r)
        st, r = self.buy(type_num=27, times=1)
        self.assertEqual("gs-bad-times", r["result"], r)
        self.assertEqual(50000, self.gold_bar(), "mua sai card khong duoc tru tien")

    def test_non_member_cannot_buy(self):
        self.setUpGuild()
        st, r = self.buy(account="g_sh_b")
        self.assertEqual("gs-not-in-guild", r["result"], r)

    def test_no_session_cannot_buy(self):
        self.setUpGuild()
        st, r = self.buy(account=None)
        self.assertNotEqual("ok", r.get("result"), r)

    # --- reward / persistence ---------------------------------------------
    def test_items_go_to_mailbox_with_3_digit_value(self):
        self.setUpGuild()
        st, r = self.buy(type_num=27, times=10)
        self.assertEqual("ok", r["result"], r)
        save = self.save_of()
        mails = [m for m in save.get("mails", []) if m.get("what") == "ITEM"]
        items = [x["value"] for x in r["reward_info"] if x["type"] == "ITEM"]
        self.assertEqual(len(items), len(mails), (items, mails))
        for m in mails:
            # 3 chu so -> client tu random sub-option luc nhan (S_MAILBOX_HERO)
            self.assertEqual(3, len(str(m["what_value"])), m)
            self.assertIn(str(m["what_value"]),
                          {str(x["value"]) for x in r["reward_info"] if x["type"] == "ITEM"})
        # reward_info khong duoc lo chuoi/field thua client khong doc
        for x in r["reward_info"]:
            self.assertEqual({"type", "value"}, set(x.keys()), x)

    def test_currencies_credited_to_save(self):
        self.setUpGuild()
        st, r = self.buy(type_num=27, times=10)
        self.assertEqual("ok", r["result"], r)
        want = {"GOLD": 0, "RUBY": 0, "BP": 0, "CLOUD": 0}
        for x in r["reward_info"]:
            if x["type"] in want:
                want[x["type"]] += x["value"]
        save = self.save_of()
        d1 = str(save["DATA1"]).split(",")
        self.assertEqual(1000 + want["GOLD"], int(d1[1]), save["DATA1"])
        self.assertEqual(50000 + want["RUBY"], int(d1[2]), save["DATA1"])
        self.assertEqual(10 + want["BP"], int(save["bp"]), save["bp"])
        self.assertEqual(1000 + want["CLOUD"], int(save["cloud_piece"]), save)

    def test_item_ids_have_client_icon_and_define_entry(self):
        """Client `et(n)` = "co_item" + floor(item/10), va bundle chi co
        co_item16/26/36/46.png -> item phai co tens digit 6."""
        seen = set()
        self.setUpGuild()
        for _ in range(40):
            st, r = self.buy(type_num=27, times=10, char_reward=2,
                             user_goldbar=self.gold_bar())
            self.assertEqual("ok", r["result"], r)
            self.top_up(50000)
            seen.update(x["value"] for x in r["reward_info"] if x["type"] == "ITEM")
        self.assertTrue(seen)
        js = (Path(serve.BASE_DIR) / "ELDORADO_WEB" / "javascript_min"
              / "eldorado_all_20260915.min.js").read_text(encoding="utf-8", errors="ignore")
        img = Path(serve.BASE_DIR) / "ELDORADO_WEB" / "image" / "ui" / "40_package_store"
        for num in sorted(seen):
            self.assertEqual(6, num // 10 % 10, "thieu icon co_item: %d" % num)
            self.assertIn("DEFINE_ITEM[%d]={" % num, js, num)
            self.assertTrue((img / ("co_item%d.png" % (num // 10))).exists(),
                            "thieu anh co_item%d.png" % (num // 10))

    def test_char_reward_picks_item_slot(self):
        """Client gui `char_reward` = S_POPUP_PACKAGE_STORE.checked_num (1..4,
        loai item nguoi choi chon). Server phai giu nguyen, khong random lai."""
        self.setUpGuild()
        for slot in (1, 2, 3, 4):
            self.top_up(50000)
            st, r = self.buy(type_num=27, times=10, char_reward=slot,
                             user_goldbar=50000)
            self.assertEqual("ok", r["result"], r)
            items = [x for x in r["reward_info"] if x["type"] == "ITEM"]
            self.assertTrue(items, r)
            for x in items:
                self.assertEqual(slot, x["value"] // 100, x)

    def test_char_reward_out_of_range_falls_back_to_random_slot(self):
        self.setUpGuild()
        seen = set()
        for bad in (0, 5, -1):
            self.top_up(50000)
            st, r = self.buy(type_num=27, times=10, char_reward=bad,
                             user_goldbar=50000)
            self.assertEqual("ok", r["result"], r)
            seen.update(x["value"] // 100 for x in r["reward_info"]
                        if x["type"] == "ITEM")
        self.assertLessEqual(seen, {1, 2, 3, 4}, seen)

    # --- card 1/2: hero gacha (type_num do server cap qua hero_list) --------
    def test_hero_list_is_offered_with_enable_and_valid_type_nums(self):
        """`glo.package.parse_hero_list` loc entry theo `enable === true`; thieu
        field nay thi client khong hien hero nao trong popup."""
        heroes = serve._guild_shop_hero_list()
        self.assertTrue(heroes)
        seen = set()
        for h in heroes:
            self.assertIs(True, h["enable"], h)
            self.assertIn(h["char_num"], range(1, 115), h)
            self.assertEqual(1, h["times"], h)
            self.assertNotIn(h["num"], seen, "trung type_num: %r" % h)
            seen.add(h["num"])
            self.assertIsNotNone(guild_backend._shop_hero_spec(h["num"]), h)
        self.assertEqual({h["char_num"] for h in heroes}, set(range(1, 115)))

    def test_hero_icons_exist_for_every_offered_hero(self):
        """Popup chon hero ve `profile_icon_<char_num>.png`; man ket qua ve
        `co_ch<char_num>.png`. Thieu anh = o trong."""
        root = Path(serve.BASE_DIR) / "ELDORADO_WEB" / "source_20240722" / "image" / "ui"
        for h in serve._guild_shop_hero_list():
            n = h["char_num"]
            self.assertTrue((root / "52_profile" / ("profile_icon_%d.png" % n)).exists(), n)
            self.assertTrue((root / "0_common" / ("co_ch%d.png" % n)).exists(), n)

    def test_hero_type_num_roundtrip_times_and_price(self):
        for char_num in (1, 57, 114):
            t1 = guild_backend._shop_hero_type_num(char_num, 1)
            t10 = guild_backend._shop_hero_type_num(char_num, 10)
            self.assertEqual(t1 + 1, t10, "client tu suy type_num_10 = type_num_1 + 1")
            self.assertEqual((1, 4000, char_num), guild_backend._shop_hero_spec(t1))
            self.assertEqual((10, 40000, char_num), guild_backend._shop_hero_spec(t10))

    def test_hero_card_x1_charges_4000_and_mails_one_char(self):
        self.setUpGuild()
        char_num = 42
        st, r = self.buy(type_num=guild_backend._shop_hero_type_num(char_num, 1),
                         times=1, char_reward=0)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(50000 - 4000, r["goldbar_cnt"], r)
        self.assertEqual([{"type": "CHAR", "value": char_num}], r["reward_info"])
        self.assertEqual(46000, self.gold_bar())
        self.assertEqual([str(char_num)], self.mails("CHAR"))

    def test_hero_card_x10_charges_40000_and_mails_ten_chars(self):
        self.setUpGuild()
        char_num = 7
        st, r = self.buy(type_num=guild_backend._shop_hero_type_num(char_num, 10),
                         times=10, char_reward=0, user_goldbar=50000)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(10, len(r["reward_info"]), r)
        self.assertEqual({char_num}, {x["value"] for x in r["reward_info"]})
        self.assertEqual(10000, self.gold_bar())
        self.assertEqual(10, len(self.mails("CHAR")))

    def test_hero_price_is_not_spoofable_and_membership_still_required(self):
        self.setUpGuild()
        tn = guild_backend._shop_hero_type_num(3, 10)
        st, r = self.buy(type_num=tn, times=10, char_reward=0, price=1,
                         user_goldbar=50000)
        self.assertEqual("ok", r["result"], r)
        self.assertEqual(10000, self.gold_bar(), "gia client gui phai bi bo qua")
        st, r = self.buy("g_sh_out", type_num=tn, times=10, char_reward=0)
        self.assertEqual("gs-not-in-guild", r["result"], r)

    def test_unknown_hero_type_num_rejected(self):
        self.setUpGuild()
        for bad in (0, 1, 28, 999, 1000, 1001, 1230, 1231, -5):
            st, r = self.buy(type_num=bad, times=1, char_reward=0)
            self.assertEqual("gs-bad-card", r["result"], (bad, r))
        self.assertEqual(50000, self.gold_bar(), "card la phai khong tru tien")

    def test_hero_card_wrong_times_rejected(self):
        self.setUpGuild()
        st, r = self.buy(type_num=guild_backend._shop_hero_type_num(5, 1),
                         times=10, char_reward=0)
        self.assertEqual("gs-bad-times", r["result"], r)
        st, r = self.buy(type_num=guild_backend._shop_hero_type_num(5, 10),
                         times=1, char_reward=0, user_goldbar=50000)
        self.assertEqual("gs-bad-times", r["result"], r)
        self.assertEqual(50000, self.gold_bar())

    def test_hero_list_over_http_yields_114_popup_heroes(self):
        """Moc vong tron: endpoint that `parse_hero_list` doc -> popup hero ->
        type_num gui len khi mua. Chay lai thuat toan client de chắc chắn."""
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:%d/ELDORADO_WEB/cnm_exist_host_in_server.php"
            % serve.SRV_PORT, data=b"crypt=0",
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Cookie": "dol_session=" + serve.issue_auth_session("g_sh_a")})
        boot = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())

        # glo.package.parse_hero_list
        parsed = [h for h in boot["hero_list"] if h.get("enable") is True]
        self.assertEqual(114, len(parsed), boot["hero_list"][:2])

        # S_GUILD_SHOP.refresh_popup_heroes
        by = {}
        for h in parsed:
            row = by.setdefault(h["char_num"],
                                {"char_num": h["char_num"],
                                 "type_num_1": 0, "type_num_10": 0})
            row["type_num_10" if h["times"] == 10 else "type_num_1"] = h["num"]
        for row in by.values():
            if row["type_num_1"] > 0 and row["type_num_10"] == 0:
                row["type_num_10"] = row["type_num_1"] + 1
        pop = [v for v in by.values() if v["type_num_1"] > 0 or v["type_num_10"] > 0]
        pop.sort(key=lambda x: -x["char_num"])
        self.assertEqual(114, len(pop))
        self.assertEqual(114, pop[0]["char_num"], "client sort giam dan char_num")
        for row in pop:
            self.assertEqual((1, 4000, row["char_num"]),
                             guild_backend._shop_hero_spec(row["type_num_1"]))
            self.assertEqual((10, 40000, row["char_num"]),
                             guild_backend._shop_hero_spec(row["type_num_10"]))

    # --- idempotency -------------------------------------------------------
    def test_same_body_retry_returns_same_result_and_charges_once(self):
        self.setUpGuild()
        st, first = self.buy()
        self.assertEqual("ok", first["result"], first)
        st, second = self.buy()
        self.assertEqual(first, second)
        self.assertEqual(50000 - 4000, self.gold_bar(), "retry khong duoc tru 2 lan")

    def test_new_purchase_after_balance_update_is_charged_again(self):
        self.setUpGuild()
        st, first = self.buy()
        self.assertEqual("ok", first["result"], first)
        # Client nhan goldbar_cnt roi USER.goldbar = 46000 -> body doi -> ban moi
        st, second = self.buy(user_goldbar=first["goldbar_cnt"])
        self.assertEqual("ok", second["result"], second)
        self.assertEqual(50000 - 8000, self.gold_bar())

    def test_same_balance_body_after_earning_back_is_a_new_purchase(self):
        """fp chi gom so du client gui nen se trung neu user kiem lai duoc
        dung so tien vua tieu. Khoi do phai kiem them so du sau giao dich."""
        self.setUpGuild()
        st, first = self.buy()
        self.assertEqual("ok", first["result"], first)
        self.assertEqual(46000, self.gold_bar())
        # User kiem them 4000 tu noi khac -> ve lai 50000, body giong het lan 1.
        serve.DB_CONN.execute("UPDATE guild_members SET gold_bar=50000")
        serve.DB_CONN.commit()
        st, second = self.buy()
        self.assertEqual("ok", second["result"], second)
        self.assertEqual(46000, second["goldbar_cnt"], second)
        self.assertEqual(46000, self.gold_bar(), "phai tru tien lan 2")

    def test_concurrent_duplicate_requests_charge_once(self):
        """4 request cung body dung luc: tat ca deu tra ve cung mot ket qua
        (retry = ban cu), va chi tru tien 1 lan."""
        self.setUpGuild()
        with ThreadPoolExecutor(max_workers=4) as pool:
            out = list(pool.map(lambda _: self.buy(), range(4)))
        self.assertEqual(4, len(out), out)
        for _, r in out:
            self.assertEqual("ok", r.get("result"), out)
        self.assertEqual(1, len({json.dumps(r, sort_keys=True) for _, r in out}), out)
        self.assertEqual(50000 - 4000, self.gold_bar())
        self.assertEqual(1, len(self.rows(
            "SELECT fp FROM guild_shop_buy WHERE user_id=?", ("g_sh_a",))))


if __name__ == "__main__":
    unittest.main()

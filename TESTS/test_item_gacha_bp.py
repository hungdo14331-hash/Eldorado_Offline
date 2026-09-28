"""Item gacha (Package Store / Lunar Lucky, TYPE_NUM 26/27) — pay with BP.

Chay qua HTTP that cua serve.py nen bat duoc route sai va handler that.
Gia 26 (x1) = 1000 BP, 27 (x10) = 10000 BP, server tu tinh tu `TYPE_NUM` nen
client tam gia rieng khong doi gia. Roll chay o server (`_item_gacha_bp_purchase`),
client chi gui `TYPE_NUM` / `GACHA_SLOT` / `GACHA_ID` va lap popup tu
`reward_info` tra ve. `GACHA_ID` la idempotency key: post lai cung ID se replay
ket qua cu, khong tru tien lan hai.

Client side: kiem tra nhanh 26/27 trong `eldorado_all_20260915.min.js` da bo
roll cuc bo (khong con `add_item_refactoring`), co gui GACHA_ID/GACHA_SLOT, dung
`reward_info` server, va gia 1000/10000 BP hien o popup/card.
"""

import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

import serve

CLIENT_JS = (Path(__file__).resolve().parent.parent / "ELDORADO_WEB"
             / "javascript_min" / "eldorado_all_20260915.min.js")
RUNTIME_PATCH = (Path(__file__).resolve().parent.parent / "ELDORADO_WEB"
                 / "runtime_patches" / "item_gacha_bp_runtime.js")

FAKE_ITEM = "9999:0:FAKE-1:0:0"


def save_for(account, bp):
    d1 = ["0"] * 21
    d1[1] = "1000"          # gold
    d1[2] = "50000"         # ruby
    return {"USER_NAME": account, "DATA1": ",".join(d1),
            "cloud_piece": "1000", "bp": str(bp), "mails": []}


def fixed_roll(reward):
    """Deterministic stand-in for roll_lunar_lucky_rewards."""
    def _roll(times, slot=0):
        return [dict(reward) for _ in range(int(times))]
    return _roll


class ItemGachaBpTests(unittest.TestCase):
    ACCOUNT = "ig_bp"
    START_BP = 20000

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_item_gacha_")
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        serve.init_db(Path(cls.tmp.name) / "gacha.db")
        serve.add_account(cls.ACCOUNT, "test-only-password")
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
            serve.db_store_save(self.ACCOUNT, save_for(self.ACCOUNT, self.START_BP))
            serve.DB_CONN.execute("DELETE FROM item_gacha_bp_ops")
            serve.DB_CONN.commit()

    # --- helpers -----------------------------------------------------------
    def draw(self, type_num, gacha_id=None, slot=None, item=FAKE_ITEM,
             bp_win=0, gold_win=0, ruby_win=0):
        """POST item/update_item_to_server.php the way the client does."""
        fields = {
            "HOST_ID": self.ACCOUNT,
            "MODE": "ITEM_GACHA",
            "RUBY": str(ruby_win),
            "GOLD": str(gold_win),
            "BP": str(bp_win),
            "CLOUD_PIECE": "0",
            "ITEM": item,
        }
        if type_num is not None:
            fields["TYPE_NUM"] = str(type_num)
        if gacha_id is not None:
            fields["GACHA_ID"] = str(gacha_id)
        if slot is not None:
            fields["GACHA_SLOT"] = str(slot)
        path = "/item/update_item_to_server.php"
        # The client merges `send_data` into the top-level form (plus
        # crypt/url), so the handler reads these fields flat, not json_obj.
        form = urlencode({"crypt": 0, "url": path, **fields})
        cookie = "dol_session=" + serve.issue_auth_session(self.ACCOUNT)
        conn = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=10)
        try:
            conn.request("POST", "/ELDORADO_WEB" + path, body=form,
                         headers={"Content-Type": "application/x-www-form-urlencoded",
                                  "Cookie": cookie,
                                  "HOST_ID": self.ACCOUNT})
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"__raw__": raw}
        finally:
            conn.close()

    def save_now(self):
        with serve.SAVE_LOCK:
            return serve.db_load_save(self.ACCOUNT) or {}

    def bp_now(self):
        return int(float(self.save_now().get("bp") or 0))

    def gold_now(self):
        d1 = str(self.save_now().get("DATA1") or "").split(",")
        while len(d1) < 3:
            d1.append("0")
        return int(float(d1[1] or 0))

    def ruby_now(self):
        d1 = str(self.save_now().get("DATA1") or "").split(",")
        while len(d1) < 3:
            d1.append("0")
        return int(float(d1[2] or 0))

    # --- price -------------------------------------------------------------
    def test_x1_costs_1000_bp(self):
        roll = fixed_roll({"type": "GOLD", "value": 500})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            st, r = self.draw(26, gacha_id="x1")
        self.assertEqual(200, st)
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual(self.START_BP - 1000, self.bp_now())
        self.assertEqual(str(self.START_BP - 1000), r.get("bp"))
        self.assertEqual(1000 + 500, self.gold_now())
        self.assertEqual([{"type": "GOLD", "value": 500}], r.get("reward_info"))
        self.assertEqual(str(1000 + 500), r.get("after_gold"))

    def test_x10_costs_10000_bp(self):
        roll = fixed_roll({"type": "GOLD", "value": 500})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            st, r = self.draw(27, gacha_id="x10")
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual(self.START_BP - 10000, self.bp_now())
        self.assertEqual(10, len(r.get("reward_info") or []))
        self.assertEqual(1000 + 5000, self.gold_now())

    def test_price_boundary_999_bp_is_rejected_for_x1(self):
        with serve.SAVE_LOCK:
            serve.db_store_save(self.ACCOUNT, save_for(self.ACCOUNT, 999))
        with mock.patch.object(serve, "roll_lunar_lucky_rewards",
                               fixed_roll({"type": "GOLD", "value": 500})):
            st, r = self.draw(26, gacha_id="b1")
        self.assertEqual("ERROR", r.get("STATUS"), r)
        self.assertEqual("NOT_ENOUGH_BP", r.get("ERROR_CODE"), r)
        self.assertEqual(999, self.bp_now(), "BP phai giu nguyen")
        self.assertEqual(1000, self.gold_now(), "khong duoc them thuong")

    def test_price_boundary_9999_bp_is_rejected_for_x10(self):
        with serve.SAVE_LOCK:
            serve.db_store_save(self.ACCOUNT, save_for(self.ACCOUNT, 9999))
        with mock.patch.object(serve, "roll_lunar_lucky_rewards",
                               fixed_roll({"type": "GOLD", "value": 500})):
            st, r = self.draw(27, gacha_id="b10")
        self.assertEqual("NOT_ENOUGH_BP", r.get("ERROR_CODE"), r)
        self.assertEqual(9999, self.bp_now())

    def test_exact_price_is_accepted(self):
        with serve.SAVE_LOCK:
            serve.db_store_save(self.ACCOUNT, save_for(self.ACCOUNT, 1000))
        with mock.patch.object(serve, "roll_lunar_lucky_rewards",
                               fixed_roll({"type": "GOLD", "value": 500})):
            st, r = self.draw(26, gacha_id="exact")
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual(0, self.bp_now())

    # --- server authority --------------------------------------------------
    def test_client_posted_wins_are_ignored(self):
        with mock.patch.object(serve, "roll_lunar_lucky_rewards",
                               fixed_roll({"type": "GOLD", "value": 500})):
            st, r = self.draw(26, gacha_id="tamper", bp_win=999999,
                              gold_win=999999, ruby_win=999999)
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual(self.START_BP - 1000, self.bp_now())
        self.assertEqual(1000 + 500, self.gold_now())
        self.assertEqual(50000, self.ruby_now())
        self.assertNotIn(FAKE_ITEM, str(self.save_now().get("item") or ""))

    def test_item_reward_goes_to_mail_not_client_storage(self):
        roll = fixed_roll({"type": "ITEM", "value": 12345})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            st, r = self.draw(26, gacha_id="mail")
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual([{"type": "ITEM", "value": 12345}], r.get("reward_info"))
        self.assertNotIn("12345", str(self.save_now().get("item") or ""))
        mails = self.save_now().get("mails") or []
        self.assertEqual(1, len(mails), mails)
        self.assertEqual("12345", str(mails[0].get("what_value")))

    def test_gacha_slot_is_forwarded_to_the_roller(self):
        seen = {}

        def _roll(times, slot=0):
            seen["times"], seen["slot"] = times, slot
            return [{"type": "GOLD", "value": 1} for _ in range(int(times))]

        with mock.patch.object(serve, "roll_lunar_lucky_rewards", _roll):
            self.draw(27, gacha_id="slot3", slot=3)
        self.assertEqual({"times": 10, "slot": 3}, seen)

    def test_out_of_range_gacha_slot_falls_back_to_random(self):
        seen = {}

        def _roll(times, slot=0):
            seen["slot"] = slot
            return [{"type": "GOLD", "value": 1} for _ in range(int(times))]

        with mock.patch.object(serve, "roll_lunar_lucky_rewards", _roll):
            self.draw(26, gacha_id="slot99", slot=99)
        self.assertEqual(0, seen["slot"])

    # --- idempotency -------------------------------------------------------
    def test_same_gacha_id_replays_one_result(self):
        roll = fixed_roll({"type": "GOLD", "value": 500})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            first = self.draw(26, gacha_id="dup")
            bp_after_first = self.bp_now()
            gold_after_first = self.gold_now()
            second = self.draw(26, gacha_id="dup")
        self.assertEqual(first, second)
        self.assertEqual(bp_after_first, self.bp_now(), "khong tru tien lan hai")
        self.assertEqual(gold_after_first, self.gold_now(),
                         "khong trao phan thuong lan hai")

    def test_same_gacha_id_with_other_type_is_a_conflict(self):
        roll = fixed_roll({"type": "GOLD", "value": 500})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            self.draw(26, gacha_id="clash")
            st, r = self.draw(27, gacha_id="clash")
        self.assertEqual("GACHA_REQUEST_CONFLICT", r.get("ERROR_CODE"), r)
        self.assertEqual(self.START_BP - 1000, self.bp_now())

    def test_different_gacha_id_charges_again(self):
        roll = fixed_roll({"type": "GOLD", "value": 500})
        with mock.patch.object(serve, "roll_lunar_lucky_rewards", roll):
            self.draw(26, gacha_id="one")
            self.draw(26, gacha_id="two")
        self.assertEqual(self.START_BP - 2000, self.bp_now())

    # --- legacy callers ----------------------------------------------------
    def test_legacy_item_gacha_without_type_num_is_not_charged(self):
        """Other ITEM_GACHA callers post no TYPE_NUM; they keep the old path
        and must not be charged BP."""
        st, r = self.draw(None, gacha_id="legacy")
        self.assertEqual(200, st)
        self.assertEqual("SUCCESS", r.get("STATUS"), r)
        self.assertEqual(self.START_BP, self.bp_now())
        self.assertNotIn("reward_info", r)


class ClientPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = CLIENT_JS.read_text(encoding="utf-8")
        start = cls.src.index(
            "if(!this._from_guild_shop&&this.from_gacha"
            "&&(this.type_num===26||this.type_num===27))")
        end = cls.src.index("if(this._from_guild_shop){", start)
        cls.branch = cls.src[start:end]
        cls.guild = cls.src[end:end + 4000]

    def test_branch_sends_gacha_id_and_slot(self):
        self.assertIn("GACHA_SLOT:_slot", self.branch)
        self.assertIn("GACHA_ID:_tn", self.branch)
        self.assertRegex(self.branch, r"GACHA_ID:_tn\+\"_\"\+Date\.now\(\)")

    def test_branch_reads_server_reward_info(self):
        self.assertIn("_ri=_t.reward_info", self.branch)
        self.assertIn("S_POPUP_GACHA_RESULT.goto_scene(_ri,!0,_tn)", self.branch)
        self.assertIn("S_POPUP_PACKAGE_STORE.back()", self.branch)

    def test_branch_refuses_any_non_success_reply(self):
        """A `{}` or partial body would turn Number(undefined) into NaN and
        blank the top-bar balances, so bail out before touching them."""
        self.assertIn('if(_t.STATUS!=="SUCCESS"){', self.branch)

    def test_branch_has_no_local_roll(self):
        for bad in ("add_item_refactoring", "S_ITEM_GACHA_COMPLETE",
                    "Math.random()<0.45", "Math.random()<0.15"):
            self.assertNotIn(bad, self.branch, "roll cuc bo con trong nhanh 26/27")

    def test_branch_guards_on_bp_before_posting(self):
        self.assertIn("_cost=_tn===26?1000:10000", self.branch)
        self.assertIn("if(USER.bonus_point<_cost)", self.branch)
        self.assertIn("S_ITEM_GACHA.need_ruby=0", self.branch)

    def test_branch_refreshes_balances_from_response(self):
        self.assertIn("USER.bonus_point=Number(_t.bp)", self.branch)
        self.assertIn("USER.ruby=Number(_t.after_ruby)", self.branch)
        self.assertIn("S_MAINMENU.update_screen_top()", self.branch)

    def test_guild_shop_path_is_untouched(self):
        """Guild Shop still buys with goldbar through its own endpoint."""
        self.assertIn('act:"guild_shop_purchase"', self.guild)
        self.assertIn("USER.goldbar<r.price", self.guild)
        self.assertNotIn("bonus_point", self.guild,
                         "nhanh Guild khong duoc dung BP")
        self.assertNotIn('"ITEM_GACHA"', self.guild)

    def test_stale_ruby_price_is_gone(self):
        self.assertNotIn("this.type_num===26?1000:9000", self.src)
        self.assertNotIn('"ITEM_GACHA",S_ITEM_GACHA.need_ruby*-1+_ruby', self.src)

    def test_price_shown_in_popup_and_on_card(self):
        self.assertIn('if(h&&(this.type_num===26||this.type_num===27))'
                      'c=utilGetNumber_withComma(this.type_num===26?1000:10000)'
                      '+" BP"', self.src)
        self.assertIn('s.id="Txt_bp_"+n', self.src)

    def test_no_ruby_paid_on_the_post(self):
        posts = re.findall(r'"ITEM_GACHA",[^;]{0,200}', self.branch)
        self.assertTrue(posts, "khong tim thay loi goi ITEM_GACHA")
        for call in posts:
            self.assertNotIn("need_ruby*-1", call)
            self.assertIn("0", call)


class RuntimePatchScopeTests(unittest.TestCase):
    """The runtime patch is display-only.

    It used to own a second purchase path. Two of them mean a silent install
    failure falls back to the old client-side roll while the server still
    rolls, so the reward lands twice. The min.js branch is the only buyer.
    """

    @classmethod
    def setUpClass(cls):
        raw = RUNTIME_PATCH.read_text(encoding="utf-8")
        cls.src = "\n".join(line for line in raw.splitlines()
                            if not line.lstrip().startswith("//"))

    def test_runtime_patch_does_not_post_a_draw(self):
        for bad in ("update_item_to_server", "ITEM_GACHA", "GACHA_ID",
                    "reward_info", "bonus_point", "loading_show"):
            self.assertNotIn(bad, self.src,
                             "runtime patch khong duoc phay lai mua hang: " + bad)

    def test_runtime_patch_does_not_wrap_menuRun_Run(self):
        self.assertNotIn("menuRun_Run", self.src)

    def test_runtime_patch_still_paints_the_bp_cards(self):
        self.assertIn("function paintBpCards()", self.src)
        self.assertIn("make_screen_bottom_item", self.src)
        self.assertIn("image/ui/40_package_store/co_bp.png", self.src)
        self.assertIn('price.textContent = formatted + " BP"', self.src)


if __name__ == "__main__":
    unittest.main()

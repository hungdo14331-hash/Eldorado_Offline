import http.client
import json
import math
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import serve


class MossMoonWalletTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="busidol_moss_moon_wallet_")
        cls.db_path = Path(cls.tmp.name) / "wallet.db"
        serve.DB_FILE = None
        serve.DB_CONN = None
        serve.REQUIRE_LOGIN = True
        serve.MODE = "offline"
        serve.SAVE_FILE = Path(cls.tmp.name) / "unused.json"
        serve.CAP_DIR = Path(cls.tmp.name) / "capture"
        serve.CAP_DIR.mkdir()
        serve.init_db(cls.db_path)
        for account in ("moss_a", "moss_b"):
            serve.add_account(account, "test-only-password")
            serve.db_store_save(account, {"wallet_ruby": "0", "DATA1": ""})
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
            serve.DB_CONN.execute("DELETE FROM moss_moon_wallet_ops WHERE user_id IN (?,?)",
                                  ("moss_a", "moss_b"))
            serve.DB_CONN.commit()
        serve.db_store_save("moss_a", {"wallet_ruby": "10", "DATA1": "",
                                       serve.MOSS_MOON_FARM_KEY: serve._moss_moon_default_farm()})
        serve.db_store_save("moss_b", {"wallet_ruby": "0", "DATA1": "",
                                       serve.MOSS_MOON_FARM_KEY: serve._moss_moon_default_farm()})
        self.cookie_a = "dol_session=" + serve.issue_auth_session("moss_a")
        self.cookie_b = "dol_session=" + serve.issue_auth_session("moss_b")

    def request(self, fields=None, cookie=None):
        connection = http.client.HTTPConnection("127.0.0.1", serve.SRV_PORT, timeout=5)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if cookie:
            headers["Cookie"] = cookie
        connection.request("POST", "/ELDORADO_WEB/wallet/moss_moon.php",
                           body=urlencode(fields or {}), headers=headers)
        response = connection.getresponse()
        result = response.status, json.loads(response.read().decode("utf-8"))
        connection.close()
        return result

    def saved(self, user_id):
        return serve.db_load_save(user_id)

    def test_wallet_is_authenticated_and_per_account(self):
        self.assertEqual(401, self.request({"ACTION": "INFO"})[0])
        _, info_a = self.request({"ACTION": "INFO", "LUCKY_PATCH_LEVEL": "5",
                      "MIGRATION": '{"gold":999999999}'}, self.cookie_a)
        _, info_b = self.request({"ACTION": "INFO"}, self.cookie_b)
        self.assertEqual("10", info_a["wallet"])
        self.assertEqual(0, info_a["farm"]["skills"]["luckyPatch"])
        self.assertEqual("560", info_a["farm"]["gold"])
        self.assertEqual(108, len(info_a["characters"]))
        self.assertFalse(info_a["character_shop_available"] is False)
        self.assertEqual("0", info_b["wallet"])

    def test_character_purchase_uses_wiki_star_and_mailbox_delivery(self):
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 5_000
        save["DATA2"] = "10:1:30:0:0:0"
        serve.db_store_save("moss_a", save)
        result = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "1",
                               "STAR": "8", "ACTION_ID": "character-purchase-0001"},
                              self.cookie_a)
        self.assertEqual(200, result[0])
        self.assertEqual("SUCCESS", result[1]["STATE"])
        self.assertEqual(1, result[1]["star"])
        self.assertEqual("1000", result[1]["spent_gold"])
        self.assertEqual("4000", result[1]["farm"]["gold"])
        self.assertEqual("10", result[1]["wallet"])
        saved = self.saved("moss_a")
        self.assertEqual("CHAR", saved["mails"][-1]["what"])
        self.assertEqual("1", saved["mails"][-1]["what_value"])
        self.assertEqual(4_000, saved[serve.MOSS_MOON_FARM_KEY]["gold"])
        self.assertEqual("10:1:30:0:0:0", saved["DATA2"])

    def test_eight_star_purchase_charges_gold_and_ruby_in_single_transaction(self):
        save = self.saved("moss_a")
        save["wallet_ruby"] = "2600"
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 12_000_000
        serve.db_store_save("moss_a", save)
        result = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "82",
                               "ACTION_ID": "character-purchase-8star-01"}, self.cookie_a)
        self.assertEqual("SUCCESS", result[1]["STATE"])
        self.assertEqual(8, result[1]["star"])
        self.assertEqual("10000000", result[1]["spent_gold"])
        self.assertEqual("2500", result[1]["spent_ruby"])
        self.assertEqual("2000000", result[1]["farm"]["gold"])
        self.assertEqual("100", result[1]["wallet"])
        self.assertEqual("82", self.saved("moss_a")["mails"][-1]["what_value"])

    def test_seven_star_price_and_duplicate_character_protection(self):
        save = self.saved("moss_a")
        save["wallet_ruby"] = "500"
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 3_000_000
        serve.db_store_save("moss_a", save)
        result = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "48",
                               "ACTION_ID": "character-purchase-7star-01"}, self.cookie_a)
        self.assertEqual("SUCCESS", result[1]["STATE"])
        self.assertEqual(7, result[1]["star"])
        self.assertEqual("2000000", result[1]["spent_gold"])
        self.assertEqual("450", result[1]["spent_ruby"])
        duplicate = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "48",
                                  "ACTION_ID": "character-purchase-7star-02"}, self.cookie_a)
        self.assertEqual("character already owned", duplicate[1]["msg"])
        self.assertEqual(1, len(self.saved("moss_a")["mails"]))

    def test_nine_star_is_not_in_the_paid_shop_catalog(self):
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 99_000_000
        serve.db_store_save("moss_a", save)
        response = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "108",
                                 "ACTION_ID": "character-purchase-9star-01"}, self.cookie_a)
        self.assertEqual("character unavailable", response[1]["msg"])
        self.assertEqual(99_000_000, self.saved("moss_a")[serve.MOSS_MOON_FARM_KEY]["gold"])
        self.assertEqual([], self.saved("moss_a").get("mails", []))

    def test_eight_star_insufficient_ruby_rolls_back_gold_and_mail(self):
        save = self.saved("moss_a")
        save["wallet_ruby"] = "2499"
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 15_000_000
        serve.db_store_save("moss_a", save)
        response = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "82",
                                 "ACTION_ID": "character-purchase-8star-poor"}, self.cookie_a)
        self.assertEqual("not enough ruby", response[1]["msg"])
        saved = self.saved("moss_a")
        self.assertEqual(15_000_000, saved[serve.MOSS_MOON_FARM_KEY]["gold"])
        self.assertEqual("2499", saved["wallet_ruby"])
        self.assertEqual([], saved.get("mails", []))

    def test_farm_gold_and_crops_change_only_through_server_actions(self):
        _, initial = self.request({"ACTION": "INFO", "MIGRATION": '{"gold":999999999}'}, self.cookie_a)
        self.assertEqual("560", initial["farm"]["gold"])
        bought = self.request({"ACTION": "BUY_SEED", "CROP": "carrot",
                               "ACTION_ID": "farm-buy-carrot-0001"}, self.cookie_a)
        self.assertEqual("542", bought[1]["farm"]["gold"])
        self.assertEqual(8, bought[1]["farm"]["seeds"]["carrot"])
        planted = self.request({"ACTION": "PLANT", "CROP": "carrot", "PLOT": "0",
                                "ACTION_ID": "farm-plant-carrot-0001"}, self.cookie_a)
        self.assertEqual("SUCCESS", planted[1]["STATE"])
        self.assertEqual(7, planted[1]["farm"]["seeds"]["carrot"])
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["plots"][0]["plantedAt"] -= serve.MOSS_MOON_CROPS["carrot"]["grow_ms"] + 1_000
        serve.db_store_save("moss_a", save)
        harvested = self.request({"ACTION": "HARVEST", "PLOT": "0",
                                  "ACTION_ID": "farm-harvest-carrot-0001"}, self.cookie_a)
        self.assertEqual("SUCCESS", harvested[1]["STATE"], harvested)
        earned_crop = next(iter(harvested[1]["farm"]["produce"].values()))
        self.assertEqual(1, earned_crop["count"])
        sold = self.request({"ACTION": "SELL_ALL", "GOLD": "999999999",
                             "ACTION_ID": "farm-sell-carrot-0001"}, self.cookie_a)
        self.assertEqual("SUCCESS", sold[1]["STATE"])
        self.assertEqual(542 + earned_crop["value"], int(sold[1]["farm"]["gold"]))
        self.assertEqual({}, sold[1]["farm"]["produce"])

    def test_rubyflower_buys_with_ruby_and_sells_for_ruby_and_diamond_bloom_rewards_diamond(self):
        save = self.saved("moss_a")
        save["wallet_ruby"] = "500"
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 2_000_000
        serve.db_store_save("moss_a", save)

        seed = self.request({"ACTION": "BUY_SEED", "CROP": "rubyflower",
                             "ACTION_ID": "rubyflower-seed-buy-0001"}, self.cookie_a)[1]
        self.assertEqual("465", seed["wallet"])
        self.assertEqual(1, seed["farm"]["seeds"]["rubyflower"])
        planted = self.request({"ACTION": "PLANT", "CROP": "rubyflower", "PLOT": "0",
                                "ACTION_ID": "rubyflower-plant-0001"}, self.cookie_a)[1]
        self.assertEqual("SUCCESS", planted["STATE"])
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["plots"][0]["plantedAt"] -= serve.MOSS_MOON_CROPS["rubyflower"]["grow_ms"] + 1_000
        serve.db_store_save("moss_a", save)
        harvested = self.request({"ACTION": "HARVEST", "PLOT": "0",
                                  "ACTION_ID": "rubyflower-harvest-0001"}, self.cookie_a)[1]
        ruby_key, ruby_item = next(iter(harvested["farm"]["produce"].items()))
        self.assertEqual("rubyflower", ruby_item["crop"])
        self.assertEqual(1, ruby_item["count"])
        sold = self.request({"ACTION": "SELL", "KEY": ruby_key,
                             "ACTION_ID": "rubyflower-sell-0001"}, self.cookie_a)[1]
        self.assertEqual("40", sold["earned_ruby"])
        self.assertEqual("505", sold["wallet"])

        seed = self.request({"ACTION": "BUY_SEED", "CROP": "diamond_bloom",
                             "ACTION_ID": "diamond-bloom-seed-buy-01"}, self.cookie_a)[1]
        self.assertEqual(1, seed["farm"]["seeds"]["diamond_bloom"])
        self.request({"ACTION": "PLANT", "CROP": "diamond_bloom", "PLOT": "0",
                      "ACTION_ID": "diamond-bloom-plant-01"}, self.cookie_a)
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["plots"][0]["plantedAt"] -= serve.MOSS_MOON_CROPS["diamond_bloom"]["grow_ms"] + 1_000
        serve.db_store_save("moss_a", save)
        harvested = self.request({"ACTION": "HARVEST", "PLOT": "0",
                      "ACTION_ID": "diamond-bloom-harvest-01"}, self.cookie_a)[1]
        diamond_key = next(iter(harvested["farm"]["produce"]))
        sold = self.request({"ACTION": "SELL", "KEY": diamond_key,
                             "ACTION_ID": "diamond-bloom-sell-01"}, self.cookie_a)[1]
        self.assertEqual("1", sold["earned_diamond"])
        self.assertEqual("4", sold["farm"]["diamond"])

    def test_new_gold_crops_price_and_payout_come_from_the_server_catalog(self):
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 500_000_000
        serve.db_store_save("moss_a", save)
        for index, crop in enumerate(("ember_chili", "frost_lily", "nebula_wheat")):
            spec = serve.MOSS_MOON_CROPS[crop]
            gold_before = int(self.saved("moss_a")[serve.MOSS_MOON_FARM_KEY]["gold"])
            bought = self.request({"ACTION": "BUY_SEED", "CROP": crop,
                                   "ACTION_ID": f"newcrop-buy-{index}0001"}, self.cookie_a)[1]
            self.assertEqual("SUCCESS", bought["STATE"], bought)
            self.assertEqual(gold_before - spec["seed_cost"],
                             int(bought["farm"]["gold"]), f"{crop} must charge the catalog seed price")
            self.assertEqual(1, bought["farm"]["seeds"][crop])
            self.request({"ACTION": "PLANT", "CROP": crop, "PLOT": str(index),
                          "ACTION_ID": f"newcrop-plant-{index}0001"}, self.cookie_a)
            save = self.saved("moss_a")
            save[serve.MOSS_MOON_FARM_KEY]["plots"][index]["plantedAt"] -= spec["grow_ms"] + 1_000
            serve.db_store_save("moss_a", save)
            harvested = self.request({"ACTION": "HARVEST", "PLOT": str(index),
                                      "ACTION_ID": f"newcrop-harvest-{index}0001"}, self.cookie_a)[1]
            key, item = next((key, item) for key, item in harvested["farm"]["produce"].items()
                             if item["crop"] == crop)
            self.assertIn(item["value"], (spec["value"], spec["value"] * 3))
            gold_before = int(harvested["farm"]["gold"])
            sold = self.request({"ACTION": "SELL", "KEY": key, "GOLD": "999999999",
                                 "ACTION_ID": f"newcrop-sell-{index}0001"}, self.cookie_a)[1]
            self.assertEqual("SUCCESS", sold["STATE"])
            self.assertEqual(gold_before + item["value"], int(sold["farm"]["gold"]),
                             f"{crop} must pay the catalog value and ignore the client amount")

    def test_ten_million_gold_needs_about_a_month_of_play(self):
        # A flat 600k cap would hand out 10M in 17 days, so the cap ramps with the
        # plots you own and plot prices are steep. Simulate a greedy run: sell out
        # every day (always allowed thanks to the one-item overflow) and buy the
        # next patch the moment it is affordable.
        gold, unlocked, day = 0.0, 9, 0
        while gold < 10_000_000 and day < 400:
            day += 1
            gold += serve._moss_moon_gold_cap(unlocked)
            while unlocked < 50 and gold >= serve._moss_moon_plot_price(unlocked):
                gold -= serve._moss_moon_plot_price(unlocked)
                unlocked += 1
        self.assertGreaterEqual(day, 30, f"10M gold must need at least 30 days, got {day}")
        self.assertLessEqual(day, 45, f"10M gold must not drag past 45 days, got {day}")

    def test_daily_gold_cap_ramps_from_120k_up_to_600k(self):
        self.assertEqual(120_000, serve._moss_moon_gold_cap(9))
        self.assertEqual(600_000, serve._moss_moon_gold_cap(50))
        caps = [serve._moss_moon_gold_cap(u) for u in range(9, 51)]
        self.assertEqual(sorted(caps), caps, "the daily cap must never drop as plots open")
        for a, b in zip(caps, caps[1:]):
            self.assertLess(b, a * 1.5, "the cap ramp must stay gradual")

    def test_daily_gold_cap_stops_sales_and_keeps_the_rest_in_the_pantry(self):
        cap = serve._moss_moon_gold_cap(9)
        self.assertEqual(120_000, cap)
        self.assertGreaterEqual(math.ceil(10_000_000 / serve.MOSS_MOON_DAILY_GOLD_CAP), 1)
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["capacity"] = 100
        save[serve.MOSS_MOON_FARM_KEY]["produce"] = {
            "golden_melon": {"name": "Golden Melon", "emoji": "🍈", "value": 20_000,
                             "count": 100, "crop": "golden_melon", "mutated": False}}
        serve.db_store_save("moss_a", save)
        cap_sell = self.request({"ACTION": "SELL_ALL",
                                 "ACTION_ID": "goldcap-sell-0001"}, self.cookie_a)[1]
        self.assertEqual("SUCCESS", cap_sell["STATE"])
        self.assertEqual(str(cap), cap_sell["gold_cap"])
        self.assertEqual(str(cap), cap_sell["gold_earned_today"])
        self.assertEqual(str(cap), cap_sell["earned_gold"])
        leftover = self.saved("moss_a")[serve.MOSS_MOON_FARM_KEY]["produce"]
        self.assertEqual(100 - cap // 20_000, leftover["golden_melon"]["count"],
                         "produce that does not fit under the cap must stay in the pantry")
        overflow = self.request({"ACTION": "SELL_ALL",
                                 "ACTION_ID": "goldcap-sell-0002"}, self.cookie_a)[1]
        self.assertEqual("SUCCESS", overflow["STATE"])
        self.assertEqual(1, overflow["sold"], "only one produce per day may overshoot the cap")
        self.assertEqual("20000", overflow["earned_gold"])
        self.assertEqual(str(cap + 20_000), overflow["gold_earned_today"])
        blocked = self.request({"ACTION": "SELL_ALL",
                                "ACTION_ID": "goldcap-sell-0003"}, self.cookie_a)[1]
        self.assertEqual("ERROR", blocked["STATE"])
        self.assertEqual("gold cap reached today", blocked["msg"])

    def test_new_gold_skills_cost_gold_and_apply_their_discounts(self):
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 10_000_000
        serve.db_store_save("moss_a", save)
        bought = self.request({"ACTION": "BUY_SKILL", "KEY": "compost",
                               "ACTION_ID": "skill-compost-0001"}, self.cookie_a)[1]
        self.assertEqual("SUCCESS", bought["STATE"])
        self.assertEqual(1, bought["farm"]["skills"]["compost"])
        self.assertEqual(10_000_000 - 300, int(bought["farm"]["gold"]))
        seed = self.request({"ACTION": "BUY_SEED", "CROP": "carrot",
                             "ACTION_ID": "compost-seed-0001"}, self.cookie_a)[1]
        self.assertEqual(10_000_000 - 300 - 17, int(seed["farm"]["gold"]),
                         "compost level 1 must take 5% off the seed price")

        bought = self.request({"ACTION": "BUY_SKILL", "KEY": "plotSurvey",
                               "ACTION_ID": "skill-survey-0001"}, self.cookie_a)[1]
        self.assertEqual(10_000_000 - 300 - 17 - 1_000, int(bought["farm"]["gold"]))
        unlock = self.request({"ACTION": "UNLOCK_PLOT",
                               "ACTION_ID": "survey-unlock-0001"}, self.cookie_a)[1]
        base_price = serve._moss_moon_plot_price(9)
        self.assertEqual(10_000_000 - 300 - 17 - 1_000 - int(base_price * 0.93),
                         int(unlock["farm"]["gold"]), "plot survey level 1 must take 7% off a patch")

        for level, cost in enumerate(serve.MOSS_MOON_GOLD_SKILL_COSTS["bigBasket"], start=1):
            self.request({"ACTION": "BUY_SKILL", "KEY": "bigBasket",
                          "ACTION_ID": f"basket-skill-{level:04d}"}, self.cookie_a)
        basket = self.request({"ACTION": "INFO", "ACTION_ID": "basket-info-0001"}, self.cookie_a)[1]
        self.assertEqual(5, basket["farm"]["skills"]["bigBasket"])
        self.assertEqual(24 + 5 * serve.MOSS_MOON_BIG_BASKET_CAPACITY, basket["farm"]["capacity"])
        overflow = self.request({"ACTION": "BUY_SKILL", "KEY": "bigBasket",
                                 "ACTION_ID": "basket-skill-0006"}, self.cookie_a)[1]
        self.assertEqual("skill maxed", overflow["msg"])

    def test_client_crop_catalog_matches_the_server_catalog(self):
        game_js = (Path(serve.__file__).parent / "ELDORADO_WEB" / "moss_moon" / "game.js").read_text(encoding="utf-8")
        block = game_js.split("const CROPS = {", 1)[1].split("\n  };", 1)[0]
        lines = {line.split(":", 1)[0].strip(): line.replace("_", "")
                 for line in block.splitlines() if line.startswith("    ") and ": {" in line}
        self.assertEqual(set(serve.MOSS_MOON_CROPS), set(lines))
        for key, spec in serve.MOSS_MOON_CROPS.items():
            self.assertIn(f"name: '{spec['name']}'", lines[key], f"{key} name must match the server catalog")
            self.assertIn(f"seedCost: {spec['seed_cost']}", lines[key], f"{key} seed price must match the server catalog")
            self.assertIn(f"growMs: {spec['grow_ms']}", lines[key], f"{key} grow time must match the server catalog")
            self.assertIn(f"value: {spec['value']}", lines[key], f"{key} payout must match the server catalog")
        self.assertIn(f"const DAILY_GOLD_CAP = {serve.MOSS_MOON_DAILY_GOLD_CAP}",
                      game_js, "the client daily gold cap must match the server cap")

    def test_farm_supports_50_plots_and_stops_at_cap(self):
        save = self.saved("moss_a")
        farm = serve._moss_moon_default_farm()
        farm["unlocked"] = 49
        farm["gold"] = 100_000_000
        save[serve.MOSS_MOON_FARM_KEY] = farm
        serve.db_store_save("moss_a", save)
        info = self.request({"ACTION": "INFO"}, self.cookie_a)[1]
        self.assertEqual(50, len(info["farm"]["plots"]))
        self.assertEqual(49, info["farm"]["unlocked"])
        unlocked = self.request({"ACTION": "UNLOCK_PLOT",
                                 "ACTION_ID": "plot-unlock-last-0001"}, self.cookie_a)[1]
        self.assertEqual(50, unlocked["farm"]["unlocked"])
        blocked = self.request({"ACTION": "UNLOCK_PLOT",
                                "ACTION_ID": "plot-unlock-over-0001"}, self.cookie_a)[1]
        self.assertEqual("all plots unlocked", blocked["msg"])

    def test_character_purchase_retry_and_insufficient_funds(self):
        save = self.saved("moss_a")
        save[serve.MOSS_MOON_FARM_KEY]["gold"] = 2_500
        serve.db_store_save("moss_a", save)
        fields = {"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "5",
                  "ACTION_ID": "character-purchase-2star-01"}
        first = self.request(fields, self.cookie_a)
        replay = self.request(fields, self.cookie_a)
        self.assertEqual(first, replay)
        self.assertEqual("2000", first[1]["spent_gold"])
        self.assertEqual("500", first[1]["farm"]["gold"])
        denied = self.request({"ACTION": "BUY_CHARACTER", "CHARACTER_ID": "6",
                               "ACTION_ID": "character-purchase-3star-01"}, self.cookie_a)
        self.assertEqual("not enough farm gold", denied[1]["msg"])
        self.assertEqual(500, self.saved("moss_a")[serve.MOSS_MOON_FARM_KEY]["gold"])
        self.assertEqual(1, len(self.saved("moss_a")["mails"]))


    def test_care_package_is_replay_safe_and_conflicts_are_rejected(self):
        fields = {"ACTION": "BUY_CARE_PACKAGE", "ACTION_ID": "care-package-action-0001"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, replay = list(pool.map(lambda _: self.request(fields, self.cookie_a), range(2)))
        self.assertEqual(first, replay)
        self.assertEqual("SUCCESS", first[1]["STATE"])
        self.assertEqual("8", first[1]["wallet"])
        self.assertEqual(10, first[1]["farm"]["seeds"]["carrot"])
        self.assertEqual("8", self.saved("moss_a")["wallet_ruby"])
        changed = self.request({"ACTION": "BUY_LUCKY_PATCH", "LEVEL": "1",
                                "ACTION_ID": fields["ACTION_ID"]}, self.cookie_a)
        self.assertEqual("action id conflict", changed[1]["msg"])
        self.assertEqual(1, serve.DB_CONN.execute(
            "SELECT COUNT(*) FROM moss_moon_wallet_ops WHERE user_id='moss_a'"
        ).fetchone()[0])

    def test_concurrent_care_packages_cannot_overspend(self):
        serve.db_store_save("moss_a", {"wallet_ruby": "3", "DATA1": ""})
        actions = [f"care-package-action-{index:04d}" for index in range(2)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda action_id: self.request({"ACTION": "BUY_CARE_PACKAGE",
                                                 "ACTION_ID": action_id}, self.cookie_a),
                actions,
            ))
        final_save = self.saved("moss_a")
        self.assertEqual(1, sum(body["STATE"] == "SUCCESS" for _, body in results),
                 {"results": results, "save": final_save})
        self.assertEqual("1", final_save["wallet_ruby"], results)

    def test_insufficient_ruby_does_not_create_a_purchase_or_change_balance(self):
        serve.db_store_save("moss_a", {"wallet_ruby": "2", "DATA1": ""})
        status, result = self.request({"ACTION": "BUY_CARE_PACKAGE",
                                       "ACTION_ID": "care-package-action-poor"}, self.cookie_a)
        self.assertEqual(200, status)
        self.assertEqual("not enough ruby", result["msg"])
        self.assertEqual("2", self.saved("moss_a")["wallet_ruby"])
        self.assertEqual(0, serve.DB_CONN.execute(
            "SELECT COUNT(*) FROM moss_moon_wallet_ops WHERE user_id='moss_a'"
        ).fetchone()[0])

    def test_lucky_patch_level_cost_and_retry_are_server_controlled(self):
        fields = {"ACTION": "BUY_LUCKY_PATCH", "LEVEL": "1",
                  "ACTION_ID": "lucky-patch-action-0001"}
        first = self.request(fields, self.cookie_a)
        replay = self.request(fields, self.cookie_a)
        self.assertEqual(first, replay)
        self.assertEqual("SUCCESS", first[1]["STATE"])
        self.assertEqual("3", first[1]["spent_ruby"])
        self.assertEqual("7", first[1]["wallet"])
        second = self.request({"ACTION": "BUY_LUCKY_PATCH", "LEVEL": "2",
                               "ACTION_ID": "lucky-patch-action-0002"}, self.cookie_a)
        self.assertEqual("5", second[1]["spent_ruby"])
        self.assertEqual(2, second[1]["farm"]["skills"]["luckyPatch"])
        invalid = self.request({"ACTION": "BUY_LUCKY_PATCH", "LEVEL": "4",
                                "ACTION_ID": "lucky-patch-action-0003"}, self.cookie_a)
        self.assertEqual("bad skill level", invalid[1]["msg"])
        self.assertEqual(2, self.saved("moss_a")[serve.MOSS_MOON_FARM_KEY]["skills"]["luckyPatch"])


if __name__ == "__main__":
    unittest.main()
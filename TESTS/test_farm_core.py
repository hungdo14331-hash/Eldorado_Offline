import importlib
import unittest


farm = importlib.import_module("farm_core")


class FarmCoreTests(unittest.TestCase):
    def test_starter_pack_is_small_and_granted_only_once(self):
        fresh = farm.new_farm(day="20260925")
        self.assertEqual(250, fresh["coins"])
        self.assertEqual({"diamond": 2, "emerald": 3}, fresh["gems"])
        self.assertEqual({"fertilizer": 1, "speed_boost": 1}, fresh["items"])
        self.assertEqual(3, fresh["seeds"]["carrot"])
        self.assertEqual(2, fresh["seeds"]["potato"])
        self.assertEqual(1, fresh["seeds"]["strawberry"])
        self.assertEqual(1, fresh["starter_pack_version"])

        legacy = farm.new_farm(day="20260925")
        legacy.pop("starter_pack_version", None)
        legacy["coins"] = 100
        legacy["gems"] = {"diamond": 0, "emerald": 0}
        legacy["items"] = {"fertilizer": 0, "speed_boost": 0}
        legacy["seeds"] = {crop: 0 for crop in farm.CROPS}
        upgraded = farm.ensure_starter_pack(legacy)
        self.assertEqual(fresh, upgraded)
        self.assertEqual(upgraded, farm.ensure_starter_pack(upgraded))

    def test_buy_plant_water_harvest_then_sell(self):
        state = farm.new_farm(day="20260925")
        self.assertEqual(state["coins"], 250)
        self.assertEqual(state["seeds"]["carrot"], 3)

        bought, event = farm.apply_action(state, "buy_seed", "20260925", crop="carrot", quantity=1)
        self.assertEqual(event["spent"], 10)
        self.assertEqual(bought["coins"], 240)
        self.assertEqual(bought["seeds"]["carrot"], 4)
        self.assertEqual(state["coins"], 250)

        planted, _ = farm.apply_action(bought, "plant", "20260925", plot_id=0, crop="carrot")
        self.assertEqual(planted["seeds"]["carrot"], 3)
        watered, _ = farm.apply_action(planted, "water", "20260925", plot_id=0)
        self.assertEqual(watered["water_left"], 5)
        ready = farm.advance_day(watered, "20260926")
        self.assertEqual(farm.plot_status(ready, 0), "ready")

        harvested, event = farm.apply_action(ready, "harvest", "20260926", plot_id=0)
        self.assertEqual(event["crop"], "carrot")
        self.assertEqual(harvested["produce"]["carrot"], 1)
        self.assertEqual(harvested["coins"], 240)
        sold, event = farm.apply_action(harvested, "sell", "20260926", crop="carrot", quantity=1)
        self.assertEqual(event["received"], 17)
        self.assertEqual(sold["coins"], 257)
        self.assertEqual(sold["produce"]["carrot"], 0)

    def test_unwatered_day_does_not_grow_crop(self):
        state = farm.new_farm(day="20260925")
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="potato")
        state, _ = farm.apply_action(state, "plant", "20260925", plot_id=0, crop="potato")
        state, _ = farm.apply_action(state, "water", "20260925", plot_id=0)
        state = farm.advance_day(state, "20260926")
        self.assertEqual(farm.plot_status(state, 0), "growing")
        state = farm.advance_day(state, "20260927")
        self.assertEqual(state["plots"][0]["growth"], 1)
        state, _ = farm.apply_action(state, "water", "20260927", plot_id=0)
        state = farm.advance_day(state, "20260928")
        self.assertEqual(farm.plot_status(state, 0), "ready")

    def test_invalid_trade_or_locked_plot_never_changes_inventory(self):
        state = farm.new_farm(day="20260925")
        with self.assertRaisesRegex(farm.FarmError, "insufficient coins"):
            farm.apply_action(state, "buy_seed", "20260925", crop="pumpkin", quantity=5)
        with self.assertRaisesRegex(farm.FarmError, "no produce"):
            farm.apply_action(state, "sell", "20260925", crop="carrot")
        with self.assertRaisesRegex(farm.FarmError, "plot locked"):
            farm.apply_action(state, "plant", "20260925", plot_id=6, crop="carrot")
        self.assertEqual(state["coins"], 250)
        self.assertEqual(state["produce"]["carrot"], 0)

    def test_water_is_one_action_per_plot_each_day(self):
        state = farm.new_farm(day="20260925")
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="potato")
        state, _ = farm.apply_action(state, "plant", "20260925", plot_id=0, crop="potato")
        state, _ = farm.apply_action(state, "water", "20260925", plot_id=0)
        with self.assertRaisesRegex(farm.FarmError, "already watered"):
            farm.apply_action(state, "water", "20260925", plot_id=0)
        next_day = farm.advance_day(state, "20260926")
        self.assertEqual(next_day["water_left"], 6)
        next_day, _ = farm.apply_action(next_day, "water", "20260926", plot_id=0)
        self.assertEqual(next_day["water_left"], 5)

    def test_shop_has_several_crops_with_distinct_investment_profiles(self):
        self.assertGreaterEqual(len(farm.CROPS), 8)
        self.assertGreater(len({c["seed_price"] for c in farm.CROPS.values()}), 4)
        self.assertGreater(len({c["growth_days"] for c in farm.CROPS.values()}), 3)
        self.assertTrue(all(c["sell_price"] > c["seed_price"] for c in farm.CROPS.values()))

    def test_coins_expand_the_next_land_plot(self):
        state = farm.new_farm(day="20260925")
        state["coins"] = 150
        expanded, event = farm.apply_action(state, "buy_land", "20260925", plot_id=6)
        self.assertEqual(event["spent"], 150)
        self.assertEqual(expanded["coins"], 0)
        self.assertEqual(farm.plot_status(expanded, 6), "empty")
        self.assertEqual(farm.plot_status(state, 6), "locked")
        with self.assertRaisesRegex(farm.FarmError, "insufficient coins"):
            farm.apply_action(expanded, "buy_land", "20260925", plot_id=7)

    def test_rare_crop_sale_funds_fertilizer_and_shortens_growth(self):
        state = farm.new_farm(day="20260925")
        state["gems"]["emerald"] = 0
        state["items"]["fertilizer"] = 0
        state["produce"]["pumpkin"] = 1
        sold, event = farm.apply_action(state, "sell", "20260925", crop="pumpkin")
        self.assertEqual(event["gems"], {"emerald": 1})
        self.assertEqual(sold["gems"]["emerald"], 1)
        state, _ = farm.apply_action(sold, "buy_item", "20260925", item="fertilizer")
        self.assertEqual(state["gems"]["emerald"], 0)
        self.assertEqual(state["items"]["fertilizer"], 1)
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="potato")
        state, _ = farm.apply_action(state, "plant", "20260925", plot_id=0, crop="potato")
        state, _ = farm.apply_action(state, "fertilize", "20260925", plot_id=0)
        self.assertEqual(state["plots"][0]["required_days"], 1)
        state, _ = farm.apply_action(state, "water", "20260925", plot_id=0)
        self.assertEqual(farm.plot_status(farm.advance_day(state, "20260926"), 0), "ready")

    def test_diamond_speed_buff_advances_a_watered_crop(self):
        state = farm.new_farm(day="20260925")
        state["gems"]["diamond"] = 0
        state["items"]["speed_boost"] = 0
        state["produce"]["rubyflower"] = 1
        state, event = farm.apply_action(state, "sell", "20260925", crop="rubyflower")
        self.assertEqual(event["gems"], {"diamond": 1})
        state, _ = farm.apply_action(state, "buy_item", "20260925", item="speed_boost")
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="potato")
        state, _ = farm.apply_action(state, "plant", "20260925", plot_id=0, crop="potato")
        state, _ = farm.apply_action(state, "boost", "20260925", plot_id=0)
        state, _ = farm.apply_action(state, "water", "20260925", plot_id=0)
        tomorrow = farm.advance_day(state, "20260926")
        self.assertEqual(farm.plot_status(tomorrow, 0), "ready")
        self.assertEqual(tomorrow["items"]["speed_boost"], 0)

    def test_level_grants_a_skill_point_that_reduces_seed_price(self):
        state = farm.new_farm(day="20260925")
        state["xp"] = 9
        state["plots"][0].update(crop="carrot", growth=1, required_days=1)
        state, _ = farm.apply_action(state, "harvest", "20260925", plot_id=0)
        self.assertEqual(state["level"], 2)
        self.assertEqual(state["skill_points"], 1)
        state, _ = farm.apply_action(state, "learn_skill", "20260925", skill="seed_discount")
        self.assertEqual(state["skill_points"], 0)
        state, event = farm.apply_action(state, "buy_seed", "20260925", crop="carrot")
        self.assertEqual(event["spent"], 9)

    def test_growth_skill_branches_stack_without_free_instant_harvest(self):
        state = farm.new_farm(day="20260925")
        state["skill_points"] = 2
        state, _ = farm.apply_action(state, "learn_skill", "20260925", skill="grow_shorter")
        state, _ = farm.apply_action(state, "learn_skill", "20260925", skill="growth_speed")
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="pumpkin")
        state, _ = farm.apply_action(state, "plant", "20260925", plot_id=0, crop="pumpkin")
        self.assertEqual(state["plots"][0]["required_days"], 4)
        state, _ = farm.apply_action(state, "water", "20260925", plot_id=0)
        tomorrow = farm.advance_day(state, "20260926")
        self.assertEqual(tomorrow["plots"][0]["growth"], 2)
        self.assertEqual(farm.plot_status(tomorrow, 0), "growing")

    def test_daily_plant_mission_awards_emerald_once(self):
        state = farm.new_farm(day="20260925")
        state["gems"]["emerald"] = 0
        state, _ = farm.apply_action(state, "buy_seed", "20260925", crop="carrot", quantity=3)
        for plot_id in range(3):
            state, _ = farm.apply_action(state, "plant", "20260925", plot_id=plot_id, crop="carrot")
        claimed, event = farm.apply_action(state, "claim_mission", "20260925", mission="plant_3")
        self.assertEqual(event["gems"], {"emerald": 1})
        self.assertEqual(claimed["gems"]["emerald"], 1)
        with self.assertRaisesRegex(farm.FarmError, "already claimed"):
            farm.apply_action(claimed, "claim_mission", "20260925", mission="plant_3")
        tomorrow = farm.advance_day(claimed, "20260926")
        with self.assertRaisesRegex(farm.FarmError, "mission incomplete"):
            farm.apply_action(tomorrow, "claim_mission", "20260926", mission="plant_3")

    def test_coins_upgrade_water_capacity(self):
        state = farm.new_farm(day="20260925")
        state["coins"] = 250
        upgraded, event = farm.apply_action(state, "buy_upgrade", "20260925", upgrade="watering_can")
        self.assertEqual(event["spent"], 120)
        self.assertEqual(upgraded["coins"], 130)
        self.assertEqual(upgraded["water_left"], 8)
        self.assertEqual(farm.advance_day(upgraded, "20260926")["water_left"], 8)

    def test_character_offer_returns_mail_payload_after_coin_charge(self):
        state = farm.new_farm(day="20260925")
        state["coins"] = 500
        purchased, event = farm.apply_action(state, "buy_character", "20260925", character_id=1)
        self.assertEqual(event["mail"], {"what": "CHAR", "what_value": "1"})
        self.assertEqual(purchased["coins"], 500 - event["spent"])
        self.assertGreater(event["spent"], 0)
        with self.assertRaisesRegex(farm.FarmError, "invalid character"):
            farm.apply_action(state, "buy_character", "20260925", character_id=115)

    def test_harvest_skill_ranks_increase_warehouse_yield(self):
        state = farm.new_farm(day="20260925")
        state["skill_points"] = 2
        state, _ = farm.apply_action(state, "learn_skill", "20260925", skill="bountiful_harvest")
        state, _ = farm.apply_action(state, "learn_skill", "20260925", skill="bountiful_harvest")
        state["plots"][0].update(crop="carrot", growth=1, required_days=1)
        harvested, event = farm.apply_action(state, "harvest", "20260925", plot_id=0)
        self.assertEqual(event["quantity"], 3)
        self.assertEqual(harvested["produce"]["carrot"], 3)


if __name__ == "__main__":
    unittest.main()

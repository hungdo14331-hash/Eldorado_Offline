"""Deterministic rules for the Ruby Garden economy; storage belongs to the server."""

from copy import deepcopy
from datetime import datetime


START_COINS = 100
STARTER_PACK_VERSION = 1
STARTER_PACK = {
    "coins": 150,
    "gems": {"diamond": 2, "emerald": 3},
    "items": {"fertilizer": 1, "speed_boost": 1},
    "seeds": {"carrot": 3, "potato": 2, "strawberry": 1},
}
DAILY_WATER = 6
LAND_COSTS = (150, 225, 300, 400, 525, 675)
WATERING_CAN_COSTS = (120, 220, 350)
CHARACTER_OFFERS = {
    1: {"name": "ACE", "price": 350},
    2: {"name": "ECHO", "price": 450},
    3: {"name": "SMARTY", "price": 600},
}
MISSIONS = {
    "plant_3": {"counter": "plant", "target": 3, "gem": "emerald", "amount": 1},
    "sell_2": {"counter": "sell", "target": 2, "gem": "emerald", "amount": 1},
    "harvest_2": {"counter": "harvest", "target": 2, "gem": "diamond", "amount": 1},
}
ITEMS = {
    "fertilizer": {"currency": "emerald", "price": 1},
    "speed_boost": {"currency": "diamond", "price": 1},
}
SKILLS = {
    "seed_discount": "Giảm giá hạt",
    "sell_bonus": "Tăng giá bán",
    "growth_speed": "Tăng tốc lớn",
    "grow_shorter": "Rút ngắn vụ",
    "water_keeper": "Bình tưới lớn",
    "bountiful_harvest": "Thu hoạch dồi dào",
}
GEM_CROPS = {"pumpkin": "emerald", "melon": "emerald", "rubyflower": "diamond"}
CROPS = {
    "carrot": {"name": "Cà rốt", "seed_price": 10, "sell_price": 17, "growth_days": 1},
    "potato": {"name": "Khoai tây", "seed_price": 18, "sell_price": 31, "growth_days": 2},
    "sunflower": {"name": "Hướng dương", "seed_price": 20, "sell_price": 37, "growth_days": 2},
    "tomato": {"name": "Cà chua", "seed_price": 25, "sell_price": 43, "growth_days": 3},
    "strawberry": {"name": "Dâu tây", "seed_price": 30, "sell_price": 55, "growth_days": 3},
    "corn": {"name": "Bắp", "seed_price": 35, "sell_price": 62, "growth_days": 4},
    "pumpkin": {"name": "Bí ngô", "seed_price": 60, "sell_price": 115, "growth_days": 5},
    "melon": {"name": "Dưa lưới", "seed_price": 70, "sell_price": 135, "growth_days": 5},
    "rubyflower": {"name": "Hoa ruby", "seed_price": 90, "sell_price": 180, "growth_days": 6},
}


class FarmError(ValueError):
    pass


def _check_day(day):
    if not isinstance(day, str) or len(day) != 8 or not day.isdigit():
        raise FarmError("invalid day")
    try:
        datetime.strptime(day, "%Y%m%d")
    except ValueError as exc:
        raise FarmError("invalid day") from exc


def new_farm(*, day):
    _check_day(day)
    state = {
        "day": day,
        "coins": START_COINS,
        "water_left": DAILY_WATER,
        "gems": {"diamond": 0, "emerald": 0},
        "items": {item: 0 for item in ITEMS},
        "level": 1,
        "xp": 0,
        "skill_points": 0,
        "skills": {skill: 0 for skill in SKILLS},
        "upgrades": {"watering_can": 0},
        "mission_progress": {"plant": 0, "sell": 0, "harvest": 0},
        "claimed_missions": [],
        "seeds": {crop: 0 for crop in CROPS},
        "produce": {crop: 0 for crop in CROPS},
        "plots": [
            {"unlocked": index < 6, "crop": None, "growth": 0, "watered": False,
             "required_days": 0, "fertilized": False, "boost_pending": False}
            for index in range(12)
        ],
    }
    return ensure_starter_pack(state)


def ensure_starter_pack(state):
    updated = deepcopy(state)
    if updated.get("starter_pack_version", 0) >= STARTER_PACK_VERSION:
        return updated
    updated["coins"] = updated.get("coins", 0) + STARTER_PACK["coins"]
    for group in ("gems", "items", "seeds"):
        bucket = updated.setdefault(group, {})
        for name, amount in STARTER_PACK[group].items():
            bucket[name] = bucket.get(name, 0) + amount
    updated["starter_pack_version"] = STARTER_PACK_VERSION
    return updated


def advance_day(state, day):
    _check_day(day)
    updated = deepcopy(state)
    if day <= updated["day"]:
        return updated
    for plot in updated["plots"]:
        if plot["crop"] and plot["watered"]:
            step = 1 + updated["skills"]["growth_speed"] + int(plot["boost_pending"])
            plot["growth"] = min(plot["growth"] + step, plot["required_days"])
            plot["boost_pending"] = False
        plot["watered"] = False
    updated["water_left"] = (DAILY_WATER + updated["skills"]["water_keeper"]
                             + 2 * updated["upgrades"]["watering_can"])
    updated["mission_progress"] = {"plant": 0, "sell": 0, "harvest": 0}
    updated["claimed_missions"] = []
    updated["day"] = day
    return updated


def _plot(state, plot_id):
    if not isinstance(plot_id, int) or isinstance(plot_id, bool) or not 0 <= plot_id < len(state["plots"]):
        raise FarmError("invalid plot")
    return state["plots"][plot_id]


def plot_status(state, plot_id):
    plot = _plot(state, plot_id)
    if not plot["unlocked"]:
        return "locked"
    if plot["crop"] is None:
        return "empty"
    return "ready" if plot["growth"] >= plot["required_days"] else "growing"


def _gain_xp(state, amount):
    state["xp"] += amount
    while state["xp"] >= state["level"] * 10:
        state["xp"] -= state["level"] * 10
        state["level"] += 1
        state["skill_points"] += 1


def apply_action(state, action, day, *, plot_id=None, crop=None, quantity=1, item=None,
                 skill=None, mission=None, upgrade=None, character_id=None):
    _check_day(day)
    if day < state["day"]:
        raise FarmError("stale day")
    if action not in {"buy_seed", "plant", "water", "harvest", "sell",
                      "buy_land", "buy_item", "fertilize", "boost", "learn_skill",
                      "claim_mission", "buy_upgrade", "buy_character"}:
        raise FarmError("invalid action")
    updated = advance_day(state, day)
    event = {"action": action}

    if action in {"buy_seed", "sell"}:
        if crop not in CROPS:
            raise FarmError("invalid crop")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 99:
            raise FarmError("invalid quantity")
        event.update(crop=crop, quantity=quantity)
        if action == "buy_seed":
            rank = updated["skills"]["seed_discount"]
            unit_price = max(1, (CROPS[crop]["seed_price"] * (100 - 10 * rank) + 99) // 100)
            cost = unit_price * quantity
            if updated["coins"] < cost:
                raise FarmError("insufficient coins")
            updated["coins"] -= cost
            updated["seeds"][crop] += quantity
            event["spent"] = cost
        else:
            if updated["produce"][crop] < quantity:
                raise FarmError("no produce")
            rank = updated["skills"]["sell_bonus"]
            unit_price = CROPS[crop]["sell_price"] * (100 + 10 * rank) // 100
            revenue = unit_price * quantity
            updated["produce"][crop] -= quantity
            updated["coins"] += revenue
            updated["mission_progress"]["sell"] += quantity
            event["received"] = revenue
            if crop in GEM_CROPS:
                gem = GEM_CROPS[crop]
                updated["gems"][gem] += quantity
                event["gems"] = {gem: quantity}
        return updated, event

    if action == "buy_item":
        if item not in ITEMS:
            raise FarmError("invalid item")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 99:
            raise FarmError("invalid quantity")
        currency = ITEMS[item]["currency"]
        cost = ITEMS[item]["price"] * quantity
        if updated["gems"][currency] < cost:
            raise FarmError("insufficient gems")
        updated["gems"][currency] -= cost
        updated["items"][item] += quantity
        event.update(item=item, quantity=quantity, currency=currency, spent=cost)
        return updated, event

    if action == "learn_skill":
        if skill not in SKILLS:
            raise FarmError("invalid skill")
        if updated["skill_points"] < 1:
            raise FarmError("no skill points")
        if updated["skills"][skill] >= 3:
            raise FarmError("skill maxed")
        updated["skill_points"] -= 1
        updated["skills"][skill] += 1
        event.update(skill=skill, rank=updated["skills"][skill])
        return updated, event

    if action == "claim_mission":
        if mission not in MISSIONS:
            raise FarmError("invalid mission")
        if mission in updated["claimed_missions"]:
            raise FarmError("already claimed")
        rule = MISSIONS[mission]
        if updated["mission_progress"][rule["counter"]] < rule["target"]:
            raise FarmError("mission incomplete")
        updated["claimed_missions"].append(mission)
        updated["gems"][rule["gem"]] += rule["amount"]
        event.update(mission=mission, gems={rule["gem"]: rule["amount"]})
        return updated, event

    if action == "buy_upgrade":
        if upgrade != "watering_can":
            raise FarmError("invalid upgrade")
        rank = updated["upgrades"][upgrade]
        if rank >= len(WATERING_CAN_COSTS):
            raise FarmError("upgrade maxed")
        cost = WATERING_CAN_COSTS[rank]
        if updated["coins"] < cost:
            raise FarmError("insufficient coins")
        updated["coins"] -= cost
        updated["upgrades"][upgrade] += 1
        updated["water_left"] += 2
        event.update(upgrade=upgrade, rank=rank + 1, spent=cost)
        return updated, event

    if action == "buy_character":
        if not isinstance(character_id, int) or isinstance(character_id, bool) or character_id not in CHARACTER_OFFERS:
            raise FarmError("invalid character")
        cost = CHARACTER_OFFERS[character_id]["price"]
        if updated["coins"] < cost:
            raise FarmError("insufficient coins")
        updated["coins"] -= cost
        event.update(character_id=character_id, spent=cost,
                     mail={"what": "CHAR", "what_value": str(character_id)})
        return updated, event

    plot = _plot(updated, plot_id)
    if action == "buy_land":
        next_plot = next((index for index, candidate in enumerate(updated["plots"])
                          if not candidate["unlocked"]), None)
        if plot_id != next_plot:
            raise FarmError("land order")
        cost = LAND_COSTS[plot_id - 6]
        if updated["coins"] < cost:
            raise FarmError("insufficient coins")
        updated["coins"] -= cost
        plot["unlocked"] = True
        event.update(plot=plot_id, spent=cost)
        return updated, event
    if not plot["unlocked"]:
        raise FarmError("plot locked")
    event["plot"] = plot_id

    if action == "plant":
        if plot["crop"] is not None:
            raise FarmError("plot occupied")
        if crop not in CROPS:
            raise FarmError("invalid crop")
        if updated["seeds"][crop] < 1:
            raise FarmError("no seeds")
        updated["seeds"][crop] -= 1
        required = max(1, CROPS[crop]["growth_days"] - updated["skills"]["grow_shorter"])
        plot.update(crop=crop, growth=0, watered=False, required_days=required,
                    fertilized=False, boost_pending=False)
        event["crop"] = crop
        updated["mission_progress"]["plant"] += 1
        _gain_xp(updated, 1)
    elif action == "water":
        status = plot_status(updated, plot_id)
        if status == "empty":
            raise FarmError("empty plot")
        if status == "ready":
            raise FarmError("already ready")
        if plot["watered"]:
            raise FarmError("already watered")
        if updated["water_left"] < 1:
            raise FarmError("no water")
        updated["water_left"] -= 1
        plot["watered"] = True
        _gain_xp(updated, 1)
    elif action in {"fertilize", "boost"}:
        if plot_status(updated, plot_id) != "growing":
            raise FarmError("no growing crop")
        item_name = "fertilizer" if action == "fertilize" else "speed_boost"
        marker = "fertilized" if action == "fertilize" else "boost_pending"
        if plot[marker]:
            raise FarmError("already applied")
        if updated["items"][item_name] < 1:
            raise FarmError("no item")
        updated["items"][item_name] -= 1
        plot[marker] = True
        if action == "fertilize":
            plot["required_days"] = max(1, plot["required_days"] - 1)
    else:
        if plot_status(updated, plot_id) != "ready":
            raise FarmError("not ready")
        picked = plot["crop"]
        amount = 1 + updated["skills"]["bountiful_harvest"]
        updated["produce"][picked] += amount
        updated["mission_progress"]["harvest"] += amount
        plot.update(crop=None, growth=0, watered=False, required_days=0,
                    fertilized=False, boost_pending=False)
        event.update(crop=picked, quantity=amount)
        _gain_xp(updated, 5)

    return updated, event

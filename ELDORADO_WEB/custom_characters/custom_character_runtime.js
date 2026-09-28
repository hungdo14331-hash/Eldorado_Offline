(function (root) {
    "use strict";

    var configs = root.BUSIDOL_CUSTOM_CHARACTERS || [];
    if (!configs.length || !root.CHAR_OUR_TEAM || !root.g) return;

    var names = {};

    function enumValue(table, name, label) {
        if (!table || table[name] === undefined) throw new Error("Custom character " + label + ": " + name);
        return table[name];
    }

    function register(config) {
        var id = Number(config.id);
        var layout = config.layout;
        var stats = config.stats;
        var combat = config.combat;
        var frames = config.frames;
        var body = config.size;
        var fire = config.fireSize;
        var character = {
            name: config.name,
            filename: config.filename,
            feature: enumValue(root.FEATURE, config.feature, "feature"),
            attack_type: enumValue(root.ATTACK_TYPE, config.attackType, "attackType"),
            star: Number(config.star),
            w: Number(body.width),
            h: Number(body.height),
            move_frame_num: Number(frames.move),
            wait_frame_num: Number(frames.wait),
            attack_frame_num: Number(frames.attack),
            beattack_frame_num: Number(frames.beattack),
            fire_frame_num: Number(frames.fire),
            fire_img_frame_num: Number(frames.fire),
            attack_fire_frame: Number(combat.attackFireFrame),
            attack_len: Number(combat.attackLength),
            move_speed: Number(combat.moveSpeed),
            attack_speed: Number(combat.attackSpeed),
            ap_start: Number(stats.apStart),
            ap_end: Number(stats.apEnd),
            hp_start: Number(stats.hpStart),
            hp_end: Number(stats.hpEnd),
            nm_start: Number(stats.mineralStart),
            nm_end: Number(stats.mineralEnd),
            max_level: Number(stats.maxLevel),
            center_gap_x: Number(layout.centerGapX || 0),
            center_gap_y: Number(layout.centerGapY || 0),
            beattack_margine: Number(layout.beattackMargin || 0),
            gagebar_x: Number(layout.gagebarX),
            gagebar_y: Number(layout.gagebarY),
            fire_img_width: Number(fire.width),
            fire_img_height: Number(fire.height),
            fire_len_margin: Number(layout.fireLengthMargin || 0),
            center_x: Number(layout.centerX),
            center_y: Number(layout.centerY),
            special_ability: [],
            innate_ability: [],
            end: ""
        };
        var i;
        for (i = 0; i < (config.specialAbilities || []).length; i++) {
            character.special_ability.push(enumValue(root.SPECIAL_ABILITY,
                config.specialAbilities[i], "special ability"));
        }
        for (i = 0; i < (config.innateAbilities || []).length; i++) {
            character.innate_ability.push(enumValue(root.INNATE_ABILITY,
                config.innateAbilities[i], "innate ability"));
        }
        var parameters = config.skillParameters || {};
        for (var key in parameters) {
            if (Object.prototype.hasOwnProperty.call(parameters, key)) character[key] = parameters[key];
        }

        root.CHAR_OUR_TEAM[id] = character;
        root.MAX_OUR_TEAM_NUM = Math.max(Number(root.MAX_OUR_TEAM_NUM) || 0, id);
        names[id] = config.name;

        var found = false;
        for (i = 1; i < root.g.CHAR_NUM.length; i++) {
            if (root.g.CHAR_NUM[i].indexOf(id) >= 0) found = true;
        }
        if (!found) root.g.CHAR_NUM.push([0, id]);
        if (root.g.STAR && root.g.STAR[character.star]
                && root.g.STAR[character.star].indexOf(id) < 0) {
            root.g.STAR[character.star].push(id);
        }
    }

    for (var i = 0; i < configs.length; i++) register(configs[i]);
    root.CHARBOOK_CHAR_MAX_NUM = Math.max(Number(root.CHARBOOK_CHAR_MAX_NUM) || 0,
        root.g.CHAR_NUM.length - 1);

    function applyNames() {
        root.TXT = root.TXT || {};
        for (var id in names) {
            if (!Object.prototype.hasOwnProperty.call(names, id)) continue;
            root.TXT["char_name_" + id] = names[id];
            if (root.CHAR_OUR_TEAM[id]) root.CHAR_OUR_TEAM[id].name = names[id];
        }
    }

    applyNames();
    if (root.LANG && typeof root.LANG.init === "function" && !root.LANG.init.__busidolCustomCharacters) {
        var originalInit = root.LANG.init;
        root.LANG.init = function () {
            applyNames();
            var result = originalInit.apply(this, arguments);
            applyNames();
            return result;
        };
        root.LANG.init.__busidolCustomCharacters = true;
    }

    if (root.DEFINE && typeof root.DEFINE.set_deploy_type === "function") {
        root.DEFINE.set_deploy_type();
    }
    console.log("[CUSTOM_CHAR] registered " + configs.length + " character(s)");
}(window));

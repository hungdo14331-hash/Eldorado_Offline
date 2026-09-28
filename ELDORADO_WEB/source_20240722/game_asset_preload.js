(function (root, factory) {
	if (typeof module === "object" && module.exports) {
		module.exports = factory();
	} else {
		root.__BUSIDOL_GAME_ASSET_PRELOAD__ = factory();
	}
}(typeof window !== "undefined" ? window : globalThis, function () {
	"use strict";

	var FIXED_BATTLE_ASSETS = [
		"image/char/ally_49/ally_49_effect_11.png",
		"image/char/ally_49/ally_49_effect_12.png",
		"image/char/ally_49/ally_49_effect_13.png",
		"image/char/ally_49/ally_49_effect_14.png",
		"image/char/ally_49/ally_49_effect_15.png",
		"image/char/ally_49/ally_49_effect_16.png",
		"image/char/ally_49/ally_49_effect_17.png",
		"image/char/ally_49/ally_49_effect_18.png",
		"image/ui/98_effect/ef_star.png",
		"image/ui/98_effect/ef_twinkle.png",
		"image/ui/4_game/char_shield_increase_0.png",
		"image/ui/4_game/ga_enemy96_fire01.png",
		"image/ui/4_game/ga_enemy96_fire02.png",
		"image/ui/4_game/ga_enemy96_fire03.png",
		"image/ui/4_game/ga_ally106_fire01.png",
		"image/ui/4_game/ga_ally106_fire02.png",
		"image/ui/4_game/ga_ally106_fire03.png",
		"image/ui/4_game/stagefire/goldWind_crystal.png"
	];

	// These are created lazily by the battle renderer when a matching character
	// fires. They are small and few enough to warm once for the whole game.
	var DEFERRED_CHAR_ASSETS = {
		34: ["fire_21", "fire_22"],
		56: ["fire_21", "fire_22"],
		63: ["fire_21", "fire_22"],
		67: ["fire_21", "fire_22"],
		84: ["fire_21", "fire_22"],
		100: ["fire_21", "fire_22"],
		102: ["fire_21", "fire_22"],
		108: ["fire_21", "fire_22"],
		111: ["fire_21"],
		113: ["fire_21", "fire_22"],
		114: ["fire_21", "fire_22"]
	};

	function addUnique(out, seen, url) {
		if (url && !seen[url]) {
			seen[url] = true;
			out.push(url);
		}
	}

	function withBase(base, path) {
		base = base || "./";
		return base.charAt(base.length - 1) === "/" ? base + path : base + "/" + path;
	}

	function collectBattleAssetUrls(options) {
		options = options || {};
		var base = options.base || "./";
		var out = [];
		var seen = {};
		var i, id, names, j;

		for (i = 0; i < FIXED_BATTLE_ASSETS.length; i++) {
			addUnique(out, seen, withBase(base, FIXED_BATTLE_ASSETS[i]));
		}

		var units = [];
		(options.allyUnits || []).forEach(function (unit) { units.push(Number(unit)); });
		(options.enemyUnits || []).forEach(function (unit) { units.push(Number(unit)); });
		for (i = 0; i < units.length; i++) {
			id = units[i];
			names = DEFERRED_CHAR_ASSETS[id];
			if (!names) continue;
			for (j = 0; j < names.length; j++) {
				addUnique(out, seen, withBase(base,
					"image/char/ally_" + id + "/ally_" + id + "_" + names[j] + ".png"));
			}
		}

		return out;
	}

	function preloadUrls(urls, imageFactory) {
		imageFactory = imageFactory || function () { return new Image(); };
		var tasks = [];
		(urls || []).forEach(function (url) {
			tasks.push(new Promise(function (resolve) {
				var image = imageFactory();
				var finished = false;
				function finish() {
					if (finished) return;
					finished = true;
					resolve(url);
				}
				image.onload = finish;
				image.onerror = finish;
				image.src = url;
				if (image.complete && image.naturalWidth > 0) finish();
			}));
		});
		return Promise.all(tasks);
	}

	function getRuntimeAssetOptions(gameRoot) {
		var glo = gameRoot.glo || {};
		var base = glo.img_url || "./";
		var allyUnits = [];
		var enemyUnits = [];
		var sockets = gameRoot.OUR_TEAM_SOCKET || [];
		var npc = gameRoot.USER_NPC && gameRoot.USER_NPC.char;
		var i;

		for (i = 1; i < sockets.length; i++) {
			if (sockets[i] && sockets[i].unit_num) allyUnits.push(sockets[i].unit_num);
		}
		if (npc) {
			for (i = 1; i < npc.length; i++) {
				if (npc[i] && npc[i].unit_num) enemyUnits.push(npc[i].unit_num);
			}
		}
		return { base: base, allyUnits: allyUnits, enemyUnits: enemyUnits };
	}

	function install(gameRoot) {
		if (!gameRoot || gameRoot.__BUSIDOL_GAME_ASSET_PRELOAD_INSTALLED__) return;
		gameRoot.__BUSIDOL_GAME_ASSET_PRELOAD_INSTALLED__ = true;
		var cache = {};
		var pendingStart = null;

		function preloadBeforeGameStart() {
			var options = getRuntimeAssetOptions(gameRoot);
			var urls = collectBattleAssetUrls(options);
			var fresh = urls.filter(function (url) {
				if (cache[url]) return false;
				cache[url] = true;
				return true;
			});
			var imageFactory = typeof gameRoot.Image === "function" ?
				function () { return new gameRoot.Image(); } : undefined;
			return preloadUrls(fresh, imageFactory);
		}

		function hook() {
			var stageSelect = gameRoot.S_SELECTSTAGE;
			if (!stageSelect || typeof stageSelect.game_start !== "function" || stageSelect.game_start.__busidolAssetPreload) return false;
			var original = stageSelect.game_start;
			function guardedGameStart() {
				var self = this;
				var args = arguments;
				if (pendingStart) return;
				if (typeof gameRoot.loading_show === "function") gameRoot.loading_show();
				pendingStart = preloadBeforeGameStart().then(function () {
					pendingStart = null;
					if (typeof gameRoot.loading_hide === "function") gameRoot.loading_hide();
					return original.apply(self, args);
				}, function () {
					pendingStart = null;
					if (typeof gameRoot.loading_hide === "function") gameRoot.loading_hide();
					return original.apply(self, args);
				});
			}
			guardedGameStart.__busidolAssetPreload = true;
			stageSelect.game_start = guardedGameStart;
			return true;
		}

		if (!hook()) {
			var timer = setInterval(function () {
				if (hook()) clearInterval(timer);
			}, 100);
		}
		return { preloadBeforeGameStart: preloadBeforeGameStart };
	}

	return {
		collectBattleAssetUrls: collectBattleAssetUrls,
		preloadUrls: preloadUrls,
		install: install
	};
}));

if (typeof window !== "undefined" && window.__BUSIDOL_GAME_ASSET_PRELOAD__) {
	window.__BUSIDOL_GAME_ASSET_PRELOAD__.install(window);
}

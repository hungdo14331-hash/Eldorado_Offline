const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const htmlPath = path.join(
  root,
  'ELDORADO_WEB',
  'source_20240722',
  'index__mobile.html'
);
const html = fs.readFileSync(htmlPath, 'utf8');

assert.match(
  html,
  /game_asset_preload\.js(?:\?[^"']*)?/,
  'game page must load the battle asset preloader'
);
const preloaderPath = path.join(
  root,
  'ELDORADO_WEB',
  'source_20240722',
  'game_asset_preload.js'
);
const preloaderSource = fs.readFileSync(preloaderPath, 'utf8');
assert.match(
  preloaderSource,
  /__BUSIDOL_GAME_ASSET_PRELOAD__/,
  'preloader must expose the battle asset preload hook'
);
const preloader = require(preloaderPath);

assert.deepEqual(
  preloader.collectBattleAssetUrls({
    base: './',
    allyUnits: [49],
    enemyUnits: []
  }),
  [
    './image/char/ally_49/ally_49_effect_11.png',
    './image/char/ally_49/ally_49_effect_12.png',
    './image/char/ally_49/ally_49_effect_13.png',
    './image/char/ally_49/ally_49_effect_14.png',
    './image/char/ally_49/ally_49_effect_15.png',
    './image/char/ally_49/ally_49_effect_16.png',
    './image/char/ally_49/ally_49_effect_17.png',
    './image/char/ally_49/ally_49_effect_18.png',
    './image/ui/98_effect/ef_star.png',
    './image/ui/98_effect/ef_twinkle.png',
    './image/ui/4_game/char_shield_increase_0.png',
    './image/ui/4_game/ga_enemy96_fire01.png',
    './image/ui/4_game/ga_enemy96_fire02.png',
    './image/ui/4_game/ga_enemy96_fire03.png',
    './image/ui/4_game/ga_ally106_fire01.png',
    './image/ui/4_game/ga_ally106_fire02.png',
    './image/ui/4_game/ga_ally106_fire03.png',
    './image/ui/4_game/stagefire/goldWind_crystal.png'
  ],
  'preloader must include lazy battle assets before the first match'
);

async function runRuntimeGateTest() {
  const createdImages = [];
  class FakeImage {
    constructor() {
      this.complete = false;
      this.naturalWidth = 0;
      createdImages.push(this);
    }
  }

  let originalCalls = 0;
  let loadingShown = 0;
  let loadingHidden = 0;
  const gameRoot = {
    Image: FakeImage,
    glo: { img_url: './' },
    OUR_TEAM_SOCKET: [],
    USER_NPC: { char: [] },
    loading_show() { loadingShown += 1; },
    loading_hide() { loadingHidden += 1; },
    S_SELECTSTAGE: {
      game_start() { originalCalls += 1; }
    }
  };

  preloader.install(gameRoot);
  gameRoot.S_SELECTSTAGE.game_start();
  assert.equal(originalCalls, 0, 'game_start must wait for battle assets');
  assert.equal(loadingShown, 1, 'preloader must show loading state while warming assets');
  assert.equal(createdImages.length, 18, 'preloader must create one request per unique asset');

  createdImages.forEach((image) => image.onload());
  await Promise.resolve();
  await Promise.resolve();

  assert.equal(originalCalls, 1, 'original game_start must run after assets finish');
  assert.equal(loadingHidden, 1, 'preloader must hide loading state before entering battle');
}

runRuntimeGateTest().then(() => {
  console.log('game asset preload tests: PASS');
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

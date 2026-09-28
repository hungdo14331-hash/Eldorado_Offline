import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (error) {
  if (error && error.code === 'MODULE_NOT_FOUND') {
    console.log('custom character browser runtime: SKIP (playwright is not installed)');
    process.exit(0);
  }
  throw error;
}

const baseUrl = process.env.BUSIDOL_TEST_URL || 'http://127.0.0.1:18066';
const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
});

try {
  const pageErrors = [];
  const missingCustomAssets = [];
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('pageerror', (error) => pageErrors.push(error.message));
  page.on('response', (response) => {
    if (response.status() >= 400 && response.url().includes('ally_115')) {
      missingCustomAssets.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto(
    `${baseUrl}/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0`,
    { waitUntil: 'domcontentloaded' },
  );
  await page.waitForLoadState('networkidle', { timeout: 20_000 });
  await page.waitForFunction(() => window.CHAR_OUR_TEAM?.[115]?.name === 'ASTRA', null, {
    timeout: 30_000,
  });

  const runtime = await page.evaluate(async () => {
    const character = window.CHAR_OUR_TEAM[115];
    const files = [];
    for (const action of ['wait', 'move', 'attack', 'beattack', 'fire']) {
      for (let frame = 1; frame <= 4; frame += 1) {
        files.push(`/ELDORADO_WEB/source_20240722/image/char/ally_115/ally_115_${action}_1${frame}.png`);
      }
    }
    files.push('/ELDORADO_WEB/source_20240722/image/ui/0_common/co_ch115.png');
    files.push('/ELDORADO_WEB/source_20240722/image/ui/4_game/char/ga_ally_115.jpg');

    const dimensions = await Promise.all(files.map((src) => new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve([src, image.naturalWidth, image.naturalHeight]);
      image.onerror = () => reject(new Error(`cannot load ${src}`));
      image.src = src;
    })));

    return {
      id: character.char_num,
      name: character.name,
      stats: [character.ap_start, character.ap_end, character.hp_start, character.hp_end],
      frames: [character.wait_frame, character.move_frame, character.attack_frame,
        character.beattack_frame, character.fire_frame],
      skillWorks: window.S_GAME.has_special_ability(
        'our', 115, window.SPECIAL_ABILITY.PUSH,
      ),
      inCollection: window.g.CHAR_NUM.some((group) => group.includes(115)),
      maxId: window.MAX_OUR_TEAM_NUM,
      dimensions,
    };
  });

  assert.equal(runtime.id, 115);
  assert.equal(runtime.name, 'ASTRA');
  assert.deepEqual(runtime.stats, [220, 4200, 900, 18000]);
  assert.deepEqual(runtime.frames, [4, 4, 4, 4, 4]);
  assert.equal(runtime.skillWorks, true);
  assert.equal(runtime.inCollection, true);
  assert.equal(runtime.maxId, 115);
  assert.equal(runtime.dimensions.length, 22);
  for (const [src, width, height] of runtime.dimensions) {
    if (src.includes('/char/')) {
      const expected = src.includes('_fire_') ? 128 : 256;
      assert.deepEqual([width, height], [expected, expected], src);
    }
  }
  assert.deepEqual(missingCustomAssets, []);
  assert.deepEqual(pageErrors, []);
  console.log('custom character browser runtime: PASS (22/22 assets)');
} finally {
  await browser.close();
}

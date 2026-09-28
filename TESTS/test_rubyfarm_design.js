const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const htmlPath = path.join(root, 'ELDORADO_WEB', 'rubyfarm.html');
const gardenPath = path.join(root, 'ELDORADO_WEB', 'ruby_garden.html');
const mossMoonDir = path.join(root, 'ELDORADO_WEB', 'moss_moon');
const assetDir = path.join(root, 'ELDORADO_WEB', 'assets', 'rubyfarm');
const mossMoonLayoutCss = fs.readFileSync(path.join(mossMoonDir, 'seed-layout.css'), 'utf8');
const html = fs.readFileSync(htmlPath, 'utf8');
const gardenHtml = fs.readFileSync(gardenPath, 'utf8');
const mossMoonHtml = fs.readFileSync(path.join(mossMoonDir, 'index.html'), 'utf8');
const mossMoonGame = fs.readFileSync(path.join(mossMoonDir, 'game.js'), 'utf8');

for (const asset of [
  'rubyfarm_hero_garden.png',
  'rubyfarm_game_catch_goldmine.png',
  'rubyfarm_game_memory_crystals.png',
  'rubyfarm_game_guess_orbs.png',
  'rubyfarm_game_simon_wheel.png',
  'rubyfarm_game_rock_paper_scissors.png',
  'rubyfarm_game_2048.png',
  'rubyfarm_game_generator_repair.png',
  'rubyfarm_game_sudoku.png',
  'rubyfarm_essence_icon.png'
]) {
  assert.ok(
    fs.existsSync(path.join(assetDir, asset)),
    `missing RubyFarm design asset: ${asset}`
  );
}

assert.match(html, /rubyfarm_hero_garden\.png/, 'home hero must use the new generated art');
assert.match(html, /id="game_search"/, 'home must expose a game search field');
assert.match(html, /data-filter="all"/, 'home must expose an all-games filter');
assert.match(html, /data-filter="free"/, 'home must expose a free-games filter');
assert.match(html, /data-filter="ticket"/, 'home must expose a ticket-games filter');
assert.match(html, /function setHomeFilter\(/, 'home must implement game filtering');
assert.match(html, /function filterGames\(/, 'home must filter the registered game list');
assert.match(html, /class="g-art"/, 'game cards must render generated artwork when available');
assert.match(html, /slide:\s*"assets\/rubyfarm\/rubyfarm_game_2048\.png"/, '2048 card must map its registered slide id to artwork');
for (const asset of [
  'rubyfarm_game_rock_paper_scissors\.png',
  'rubyfarm_game_2048\.png',
  'rubyfarm_game_generator_repair\.png',
  'rubyfarm_game_sudoku\.png'
]) {
  assert.match(html, new RegExp(asset), `game cards must reference ${asset}`);
}
assert.match(html, /ic\.startsWith\("image\/"\)\s*\|\|\s*ic\.startsWith\("assets\/"\)/, 'reward icons must render both legacy and RubyFarm asset paths as images');
assert.match(html, /class="hud-search"/, 'HUD must expose the main game search shortcut');
assert.match(html, /function focusGameSearch\(/, 'HUD search shortcut must focus the home search field');
assert.match(html, /class="back-chip"[^>]*>\s*<span class="back-mark"/, 'back link must use the new text button treatment');
assert.doesNotMatch(html, /class="back-chip sp-btn-chip"/, 'back link must not depend on the old sprite frame');
assert.match(html, /rubyfarm_essence_icon\.png/, 'essence must use the cropped icon asset without the old capsule');
assert.doesNotMatch(html, /sp-frame-hud hud-frame/, 'HUD must not render the oversized gold frame');
assert.match(html, /<aside class="side">/, 'redesign must keep the main navigation shell');
assert.match(html, /id="side_wallet"/, 'redesign must keep the wallet summary');
assert.match(
  gardenHtml,
  /(?:href=['"]rubyfarm\.html['"]|location\.href=['"]rubyfarm\.html['"])/,
  'Ruby Garden must expose a way back to RubyFarm'
);
for (const file of ['index.html', 'game.js', 'styles.css']) {
  assert.ok(fs.existsSync(path.join(mossMoonDir, file)), `missing Moss & Moon web file: ${file}`);
}
assert.match(mossMoonHtml, /href="seed-layout\.css"/, 'Moss & Moon must load the responsive seed layout');
assert.match(mossMoonLayoutCss, /\.seed-picker\s*\{[\s\S]*?min-width:\s*0/, 'seed picker must be allowed to shrink so the tray cannot slide under the Overview panel');
assert.match(mossMoonLayoutCss, /\.seed-options\s*\{[\s\S]*?overflow-x:\s*auto/, 'seed tray must scroll sideways instead of spreading across the screen');
assert.match(mossMoonLayoutCss, /\.seed-options\s*\{[\s\S]*?max-width:\s*min\(\s*520px/, 'seed tray must stay a short capped strip');
assert.match(mossMoonLayoutCss, /\.seed-choice\s*\{[\s\S]*?flex:\s*0 0 auto/, 'seed chips must keep a fixed width instead of stretching');
assert.doesNotMatch(mossMoonLayoutCss, /\.seed-choice\s*\{[^}]*flex:\s*1\b/, 'seed chips must not grow to fill the row');
assert.match(html, /href="moss_moon\/index\.html"/, 'RubyFarm home must link to Moss & Moon');
assert.match(mossMoonHtml, /href="\.\.\/rubyfarm\.html"/, 'Moss & Moon must link back to RubyFarm');
assert.match(mossMoonHtml, /<a class="return-to-ruby" href="\.\.\/rubyfarm\.html">[\s\S]*?Back to RubyFarm[\s\S]*?<\/a>/, 'Moss & Moon must expose a clearly labeled back button');
assert.match(mossMoonLayoutCss, /\.return-to-ruby\s*\{[\s\S]*?background:\s*#345c40;/, 'Moss & Moon return link must use prominent button styling');
assert.match(mossMoonLayoutCss, /\.panel-bottom\s*\{[\s\S]*?flex-wrap:\s*wrap;/, 'Moss & Moon footer controls must wrap on narrow screens');
assert.match(mossMoonGame, /fetch\('\.\.\/wallet\/moss_moon\.php'/, 'Moss & Moon must use the authenticated account wallet API');
assert.match(mossMoonGame, /ACTION:\s*'INFO'/, 'Moss & Moon must load the shared Ruby balance');
assert.match(mossMoonGame, /ACTION:\s*pending\.action[\s\S]*ACTION_ID:\s*pending\.id/, 'Ruby purchases must send their persistent idempotency key');
assert.match(mossMoonGame, /if \(!saveState\(\)\) \{ state\.pendingRubyAction = null; return; \}/, 'Ruby purchases must not debit if the retry key cannot be persisted locally');
assert.doesNotMatch(mossMoonGame, /state\.ruby\b/, 'Moss & Moon must not spend its old local-only Ruby balance');
assert.match(mossMoonHtml, /id="ruby-wallet-label"/, 'Moss & Moon must label whether the Ruby wallet is linked');
assert.match(mossMoonGame, /rubyWalletConnected \? 'LINKED' : 'LOGIN'/, 'Moss & Moon must show login status for the shared wallet');
assert.match(mossMoonGame, /id="character-search"/, 'Moss & Moon must render the account character shop search');
assert.match(mossMoonGame, /id="character-select"/, 'Moss & Moon must render the Wiki-driven character selector');
assert.match(mossMoonGame, /beginFarmAction\('BUY_CHARACTER',\s*\{\s*CHARACTER_ID:/, 'Moss & Moon must send character purchases to the account wallet API');
assert.match(mossMoonGame, /response\.characters/, 'Moss & Moon must populate characters from the server catalog');
assert.doesNotMatch(mossMoonGame, /state\.gold\s*(?:\+=|-=)/, 'farm Gold must not be generated or spent only in the browser');
assert.match(mossMoonGame, /LOCAL_FARM_BACKUP_KEY/, 'Moss & Moon must archive the previous local farm before server sync');
assert.match(mossMoonGame, /const PLOT_LIMIT = 50/, 'Moss & Moon farm must support up to 50 plots');
assert.match(mossMoonGame, /blue_orchid:|golden_melon:|starfruit:/, 'Moss & Moon must offer higher-value Gold crops');
assert.match(mossMoonGame, /rubyflower:[\s\S]*seedRubyCost:\s*35[\s\S]*rubyValue:\s*40/, 'Rubyflower must cost Ruby to plant and reward Ruby when sold');
assert.match(mossMoonGame, /diamond_bloom:[\s\S]*diamondValue:\s*1/, 'Diamond Bloom must provide a server-sellable Diamond reward');
assert.match(mossMoonGame, /for \(let row = 0; row < 5; row \+= 1\) for \(let column = 0; column < 10; column \+= 1\)/, 'farm canvas must draw all 50 plots');
assert.match(html, /href="moss_moon\/index\.html">🌿 Chơi Moss &amp; Moon/, 'RubyFarm CTA must clearly launch Moss & Moon');
assert.match(html, /<a class="btn gold lg" href="moss_moon\/index\.html"/, 'RubyFarm must emphasize Moss & Moon with its gold primary CTA');
assert.equal((html.match(/href="moss_moon\/index\.html"/g) || []).length, 2, 'RubyFarm navigation and home CTA must link directly to Moss & Moon');
assert.doesNotMatch(html, /href="ruby_garden\.html"/, 'RubyFarm must replace the Ruby Garden entry points with Moss & Moon');
assert.match(mossMoonGame, /seeds:\s*\{\s*\.\.\.INITIAL_STATE\.seeds,\s*\.\.\.saved\.seeds\s*\}/, 'existing saves must inherit newly added seed defaults');
for (const crop of ['strawberry', 'pumpkin', 'sunflower']) {
  assert.match(mossMoonGame, new RegExp(`\\b${crop}:\\s*\\{`), `${crop} must be in the crop catalog`);
  assert.match(mossMoonGame, new RegExp(`seeds:\\s*\\{[^}]*\\b${crop}:\\s*[1-9]`), `${crop} must have starting seeds`);
  assert.match(mossMoonGame, new RegExp(`crop\\.name === '${crop[0].toUpperCase()}${crop.slice(1)}'`), `${crop} must have its own fruit drawing`);
}
assert.match(mossMoonGame, /Object\.entries\(CROPS\)\.map/, 'seed picker and shop must render from the crop catalog');

// Every panel must actually render. A local `const` that shadows a same-named
// helper used earlier in the same block throws "Cannot access before
// initialization" at click time, leaving the tab blank with no visible error,
// so run each renderer for real instead of only grepping the source.
const panelNodes = new Map();
function stubNode(id) {
  if (panelNodes.has(id)) return panelNodes.get(id);
  const node = {
    id, innerHTML: '', textContent: '', value: '', disabled: false, dataset: {}, style: {},
    classList: { toggle() {}, add() {}, remove() {}, contains: () => false },
    addEventListener() {}, focus() {}, setSelectionRange() {},
    querySelectorAll: () => [], closest: () => null,
    getContext: () => new Proxy({}, { get: () => () => ({ addColorStop() {} }) }),
    getBoundingClientRect: () => ({ width: 800, height: 600, left: 0, top: 0 })
  };
  panelNodes.set(id, node);
  return node;
}
const previousGlobals = { document: global.document, window: global.window, localStorage: global.localStorage };
global.document = { body: stubNode('body'), getElementById: stubNode, querySelectorAll: () => [], addEventListener() {}, createElement: () => stubNode('tmp') };
global.window = { crypto: { randomUUID: () => 'probe' }, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.requestAnimationFrame = () => 0;
// never resolve: loadRubyWallet() fires on eval and would call render() later,
// after the DOM stubs are restored, throwing an unhandled rejection.
global.fetch = () => new Promise(() => {});
global.AudioContext = function () { return { createOscillator: () => ({ start() {}, stop() {}, connect() {} }), createGain: () => ({}), destination: {} }; };
const probed = mossMoonGame
  .replace(/\}\)\(\);\s*$/, 'globalThis.__panels = { renderOverview, renderStorage, renderShop, renderSkills, get state() { return state; }, set farmConnected(v) { farmConnected = v; }, set walletRuby(v) { walletRuby = v; } };\n})();\n');
eval(probed);
const panels = globalThis.__panels;
panels.state.gold = 617996;
panels.state.unlocked = 50;
panels.farmConnected = true;
panels.walletRuby = 500;
for (const name of ['renderOverview', 'renderStorage', 'renderShop', 'renderSkills']) {
  assert.doesNotThrow(() => panels[name](), `${name} must render without throwing`);
  if (name === 'renderShop') {
    assert.ok(panelNodes.get('panel-content').innerHTML.includes('data-buy-seed'), 'Market must render seed buy buttons');
  }
}
assert.doesNotMatch(mossMoonGame, /const seedPrice = rubySeed/, 'a display label must not shadow the seedPrice() helper used in the same block');
Object.assign(global, previousGlobals);

console.log('rubyfarm design tests: PASS');

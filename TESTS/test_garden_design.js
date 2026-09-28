const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const page = path.join(root, 'ELDORADO_WEB', 'ruby_garden.html');
const assetDir = path.join(root, 'ELDORADO_WEB', 'assets', 'ruby_garden');
const html = fs.readFileSync(page, 'utf8');

for (const asset of ['garden_island.png', 'garden_crop_strip.png']) {
  assert.ok(fs.existsSync(path.join(assetDir, asset)), `missing garden asset: ${asset}`);
}
assert.match(html, /garden_island\.png/);
assert.match(html, /garden_crop_strip\.png/);
assert.match(html, /garden\/state\.php/);
assert.match(html, /garden\/action\.php/);
assert.match(html, /id="garden_grid"/);
assert.match(html, /data-plot="11"/);
assert.match(html, /ACTION_ID/);
assert.match(html, /buy_seed|Mua hạt/);
assert.match(html, /warehouse|Kho đồ/);
assert.match(html, /skill|Kỹ năng/);
assert.match(html, /id="item_list"/, 'garden must expose fertilizer and speed item controls');
assert.match(html, /id="upgrade_list"/, 'garden must expose land and watering-can upgrades');
assert.match(html, /buy_item/, 'garden must connect item purchases to the farm API');
assert.match(html, /buy_land/, 'garden must connect land expansion to the farm API');
assert.match(html, /buy_upgrade/, 'garden must connect watering-can upgrades to the farm API');
assert.match(html, /data\.STATE\s*===\s*['"]ERROR['"]/, 'garden must surface server-declined actions instead of rendering stale state');
assert.match(html, /typeof x===['"]string['"]\?x:x\.name/, 'garden must render skill names from the server string catalog');

console.log('garden design tests: PASS');

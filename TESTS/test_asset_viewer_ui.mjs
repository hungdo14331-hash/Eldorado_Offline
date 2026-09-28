import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const viewerPath = path.join(root, 'asset_viewer', 'index.html');
const assetDir = path.join(root, 'ELDORADO_WEB', 'source_20240722', 'image', 'char', 'ally_1');
const screenshotDir = path.join(root, '_TEMP_ASSET_VIEWER_QA');
const consoleErrors = [];

fs.mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));

  await page.goto(pathToFileURL(viewerPath).href);
  await page.waitForLoadState('networkidle');
  await page.locator('#asset_files').setInputFiles(assetDir);
  await page.locator('#filter_query').fill('ally_01_move');
  await page.locator('#asset_limit').fill('3');
  await page.locator('#load_delay').fill('25');
  await page.locator('#load_assets').click();
  await page.getByText('Đã nạp 3 asset.').waitFor();

  assert.equal(await page.locator('.film-frame').count(), 3, 'load limit must cap the rendered filmstrip');
  assert.match(await page.locator('#frame_name').innerText(), /ally_01_move_11\.png$/, 'natural order must start at frame 11');

  await page.locator('#next_frame').click();
  assert.match(await page.locator('#frame_name').innerText(), /ally_01_move_12\.png$/, 'next control must show the following frame');

  await page.locator('#zoom').fill('2');
  assert.equal(await page.locator('#preview_image').evaluate((image) => image.style.width), '194px', 'zoom must scale the 97px sprite to 2x');

  await page.locator('#toggle_playback').click();
  assert.equal(await page.locator('#toggle_playback').getAttribute('aria-label'), 'Tạm dừng', 'play control must enter the running state');
  await page.locator('#toggle_playback').click();
  assert.equal(await page.locator('#toggle_playback').getAttribute('aria-label'), 'Phát chuỗi', 'play control must return to the paused state');

  await page.screenshot({ path: path.join(screenshotDir, 'asset_viewer_desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth),
    true,
    'mobile layout must not overflow horizontally',
  );
  await page.screenshot({ path: path.join(screenshotDir, 'asset_viewer_mobile.png'), fullPage: true });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.locator('#grid_columns').fill('2');
  await page.locator('#grid_rows').fill('1');
  await page.locator('#frame_width').fill('20');
  await page.locator('#frame_height').fill('10');
  await page.locator('#grid_divider').fill('4');
  await page.locator('#build_template').click();
  assert.deepEqual(
    await page.locator('#template_canvas').evaluate((canvas) => ({ width: canvas.width, height: canvas.height })),
    { width: 52, height: 18 },
    'template canvas must include the configured outer and inner dividers',
  );
  const templateDownloadPromise = page.waitForEvent('download');
  await page.locator('#download_template').click();
  const templateDownload = await templateDownloadPromise;
  assert.equal(
    templateDownload.suggestedFilename(),
    'sprite-template-2x1-20x10.png',
    'template download must describe its grid and frame dimensions',
  );

  const sheetBase64 = await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 104;
    canvas.height = 36;
    const context = canvas.getContext('2d');
    context.fillStyle = '#ff00ff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#ff0000';
    context.fillRect(8, 8, 40, 20);
    context.fillStyle = '#0000ff';
    context.fillRect(56, 8, 40, 20);
    return canvas.toDataURL('image/png').split(',')[1];
  });
  await page.locator('#sheet_file').setInputFiles({
    name: 'generated_sheet.png',
    mimeType: 'image/png',
    buffer: Buffer.from(sheetBase64, 'base64'),
  });
  await page.locator('#frame_prefix').fill('walk');
  await page.locator('#split_sheet').click();
  await page.getByText('Đã tách 2 frame PNG · 20 × 10 px.').waitFor();

  assert.equal(await page.locator('.film-frame').count(), 2, 'split sheet must replace the filmstrip with every extracted frame');
  assert.equal(await page.locator('#frame_name').innerText(), 'walk_01.png', 'split frames must use the requested ordered filename');
  assert.equal(await page.locator('#save_split_frames').isEnabled(), true, 'split frames must be available for folder export');
  const frameDownloadPromise = page.waitForEvent('download');
  await page.locator('#download_frame').click();
  assert.equal((await frameDownloadPromise).suggestedFilename(), 'walk_01.png', 'current frame download must keep the generated filename');

  async function currentFramePixel() {
    return page.locator('#preview_image').evaluate(async (image) => {
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d');
      context.drawImage(image, 0, 0);
      return Array.from(context.getImageData(5, 5, 1, 1).data);
    });
  }

  assert.deepEqual(await currentFramePixel(), [255, 0, 0, 255], 'first extracted frame must exclude the divider and keep the first cell');
  await page.locator('#next_frame').click();
  assert.deepEqual(await currentFramePixel(), [0, 0, 255, 255], 'second extracted frame must exclude the divider and keep the second cell');
  assert.deepEqual(consoleErrors, [], 'viewer must not emit browser errors');
  console.log('asset viewer UI tests: PASS');
} finally {
  await browser.close();
}

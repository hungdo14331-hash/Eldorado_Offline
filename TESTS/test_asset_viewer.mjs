import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const {
  advanceFrame,
  buildGenerationPrompt,
  createFrameRects,
  createGridLayout,
  loadAssetsSequentially,
  pickAssetFiles,
} = require('../asset_viewer/asset_viewer.js');

const files = [
  { name: 'ally_wait_10.png', webkitRelativePath: 'ally/wait/ally_wait_10.png' },
  { name: 'notes.txt', webkitRelativePath: 'ally/wait/notes.txt' },
  { name: 'ally_wait_2.png', webkitRelativePath: 'ally/wait/ally_wait_2.png' },
  { name: 'ALLY_WAIT_09.PNG', webkitRelativePath: 'ally/wait/ALLY_WAIT_09.PNG' },
  { name: 'ally_move_1.webp', webkitRelativePath: 'ally/move/ally_move_1.webp' },
];

assert.deepEqual(
  pickAssetFiles(files, { query: 'wait', limit: 2 }).map((file) => file.name),
  ['ally_wait_2.png', 'ALLY_WAIT_09.PNG'],
  'viewer must filter image files, sort numeric frame names naturally, then apply the load limit',
);

assert.deepEqual(
  pickAssetFiles(files, { query: 'missing', limit: 20 }),
  [],
  'viewer must return an empty queue when no image matches the filter',
);

const calls = [];
const loaded = await loadAssetsSequentially(
  [{ name: '01.png' }, { name: '02.png' }, { name: '03.png' }],
  {
    delayMs: 75,
    decodeAsset: async (file) => {
      calls.push(`decode:${file.name}`);
      return { file, url: `memory://${file.name}` };
    },
    sleep: async (milliseconds) => calls.push(`wait:${milliseconds}`),
    onProgress: (done, total) => calls.push(`progress:${done}/${total}`),
  },
);

assert.deepEqual(
  calls,
  [
    'decode:01.png', 'progress:1/3', 'wait:75',
    'decode:02.png', 'progress:2/3', 'wait:75',
    'decode:03.png', 'progress:3/3',
  ],
  'viewer must decode in order, report every frame, and wait only between frames',
);
assert.deepEqual(
  loaded.map((asset) => asset.url),
  ['memory://01.png', 'memory://02.png', 'memory://03.png'],
  'viewer must preserve the loaded frame order',
);

assert.equal(advanceFrame(7, 8, 1), 0, 'next frame must wrap to the first frame');
assert.equal(advanceFrame(0, 8, -1), 7, 'previous frame must wrap to the last frame');
assert.equal(advanceFrame(0, 0, 1), -1, 'an empty viewer must not select a frame');

const grid = createGridLayout({
  columns: 4,
  rows: 2,
  frameWidth: 97,
  frameHeight: 110,
  divider: 8,
});
assert.deepEqual(
  { width: grid.width, height: grid.height, frameCount: grid.frames.length },
  { width: 428, height: 244, frameCount: 8 },
  'template dimensions must include every frame plus outer and inner dividers',
);
assert.deepEqual(
  grid.frames.at(-1),
  { index: 7, row: 1, column: 3, x: 323, y: 126, width: 97, height: 110 },
  'the last frame must use left-to-right, top-to-bottom coordinates',
);

assert.deepEqual(
  createFrameRects(grid, 856, 488).at(-1),
  {
    index: 7,
    row: 1,
    column: 3,
    sourceX: 646,
    sourceY: 252,
    sourceWidth: 194,
    sourceHeight: 220,
    outputWidth: 97,
    outputHeight: 110,
  },
  'sheet slicing must scale divider coordinates when the generated sheet is larger than the template',
);

assert.match(
  buildGenerationPrompt(grid),
  /4 cột × 2 hàng.*428 × 244 px.*#ff00ff/is,
  'generated instructions must carry the exact grid, canvas size, and divider color',
);
assert.throws(
  () => createGridLayout({ columns: 0, rows: 2, frameWidth: 97, frameHeight: 110, divider: 8 }),
  /columns/,
  'invalid grid sizes must be rejected instead of producing an unusable template',
);

console.log('asset viewer tests: PASS');

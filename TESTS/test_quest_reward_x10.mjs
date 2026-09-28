// Regression: thưởng Quest x10 (Ruby + Gold) — override runtime trong
// index__mobile.html, không sửa min.js.
//
// Test bắt chuyện quan trọng nhất: min.js gán LẠI QUEST[1], QUEST[4], QUEST[9]
// ở cuối bundle, tức sau mảng QUEST=[{...}]. Nếu chỉ nhân một lần lúc mảng vừa
// có, 3 quest đó sẽ bị ghi đè về số gốc. Test mô phỏng đúng thứ tự đó.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
    path.join(here, "..", "ELDORADO_WEB", "source_20240722", "index__mobile.html"),
    "utf8");

// Lấy đúng khối script của patch quest (không hardcode toàn bộ HTML).
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const patch = blocks.find(b => b.includes("__eldQuestX10"));
if (!patch) throw new Error("khong tim thay khoi script override quest x10");

// Số liệu lấy nguyên văn từ eldorado_all_20260915.min.js
const QUEST_1_ARRAY   = { r_ruby: [-1,0,0,1,1,2,2,2,3,3,3], r_gold: [-1,500,1000,2000,3000,4000,5000,6000,7000,8000,9000] };
const QUEST_1_OVERRIDE = { r_ruby: [-1,0,0,0,0,0,0,0,1,1,2], r_gold: [-1,300,500,700,900,1100,1500,2000,0,0,0] };
const QUEST_2         = { r_ruby: [-1,0,0,0,0,1,1,2],       r_gold: [-1,500,1000,1500,2000,0,0,0] };

function runScenario(applyBundleOverrides) {
    const timers = [];
    const win = {
        QUEST_NUM: 2,
        QUEST: [{}, { ...QUEST_1_ARRAY, r_ruby: [...QUEST_1_ARRAY.r_ruby], r_gold: [...QUEST_1_ARRAY.r_gold] },
                   { ...QUEST_2,       r_ruby: [...QUEST_2.r_ruby],       r_gold: [...QUEST_2.r_gold] }],
        setInterval: fn => { timers.push(fn); return timers.length; },
        console: { log() {} }
    };
    win.window = win;
    const ctx = vm.createContext(win);
    vm.runInContext(patch, ctx);              // chạy pass đầu tiên

    if (applyBundleOverrides) {
        // min.js gán lại QUEST[1] bằng object MỚI, chưa nhân
        win.QUEST[1] = { r_ruby: [...QUEST_1_OVERRIDE.r_ruby], r_gold: [...QUEST_1_OVERRIDE.r_gold] };
        for (const fn of timers) fn();        // vòng poll 500ms kế tiếp
    }
    return { win, timers };
}

const assert = (cond, msg) => { if (!cond) throw new Error(msg); };

// 1. Pass đầu tiên nhân đúng 1 lần, sentinel [-1] ở index 0 giữ nguyên.
{
    const { win: w } = runScenario(false);
    assert(w.QUEST[1].r_ruby[9] === 3 * 10, "quest 1 ruby chua nhan x10");
    assert(w.QUEST[1].r_gold[9] === 8000 * 10, "quest 1 gold chua nhan x10");
    assert(w.QUEST[1].r_gold[10] === 9000 * 10, "quest 1 gold index 10 chua nhan x10");
    assert(w.QUEST[2].r_ruby[6] === 1 * 10, "quest 2 ruby chua nhan x10");
    assert(w.QUEST[2].r_gold[3] === 1500 * 10, "quest 2 gold chua nhan x10");
    assert(w.QUEST[1].r_ruby[0] === -1, "sentinel index 0 bi doi");
    assert(w.QUEST[1].r_gold[0] === -1, "sentinel index 0 bi doi");
    // Giá trị 0 vẫn phải là 0 (UI dùng ==0 để ẩn icon).
    assert(w.QUEST[1].r_ruby[1] === 0, "gia tri 0 khong con la 0");
    assert(w.QUEST[2].r_gold[5] === 0, "gia tri 0 khong con la 0");
}

// 2. Vẫn đúng khi min.js gán lại QUEST[1] SAU khi patch đã chạy.
{
    const { win: w } = runScenario(true);
    assert(w.QUEST[1].r_ruby[9] === 1 * 10, "quest 1 override chua duoc nhan x10");
    assert(w.QUEST[1].r_gold[3] === 700 * 10, "quest 1 override gold chua nhan x10");
    assert(w.QUEST[1].r_ruby[0] === -1, "sentinel index 0 bi doi");
}

// 3. Các vòng poll sau không nhân trùng (x100, x1000...).
{
    const { win: w, timers } = runScenario(false);
    for (let round = 0; round < 5; round++) for (const fn of timers) fn();
    assert(w.QUEST[1].r_ruby[9] === 3 * 10, "quest 1 ruby bi nhan trung o cac vong poll sau");
    assert(w.QUEST[1].r_gold[9] === 8000 * 10, "quest 1 gold bi nhan trung o cac vong poll sau");
    assert(w.QUEST[2].r_gold[3] === 1500 * 10, "quest 2 gold bi nhan trung o cac vong poll sau");
}

console.log("OK - quest x10 patch hoat dong dung");

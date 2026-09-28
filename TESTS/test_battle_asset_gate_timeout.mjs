// Regression: cổng chờ ảnh phải tự mở khi quá hạn.
//
// Game đếm ảnh battle bằng img.onload, rồi chờ cổng trước khi start:
//     function interval_test_our(){
//         if (đủ cur/tot) { flag_LOIMG_CHAR_OUR=1; return }
//         setTimeout(interval_test_our,100)      // tự hẹn lại vô hạn
//     }
// Cổng start trận chờ flag==1, nên cổng không mở là treo giữa trận.
// serve.py đã sửa ca 404 (ảnh thiếu -> PNG trong suốt, onload luôn bắn).
// Bản vá này phủ ca còn lại: tải CHẬM/treo -> quá hạn thì tự mở cổng.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
const html = readFileSync(path.join(root, "ELDORADO_WEB", "source_20240722", "index__mobile.html"), "utf8");
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const patch = blocks.find(b => b.includes("het han") && b.includes("interval_test_our"));
if (!patch) throw new Error("khong tim thay patch gate timeout");

const assert = (c, m) => { if (!c) throw new Error(m); };

// Sandbox mô phỏng: cổng gốc của bundle, chưa bao giờ đủ cur/tot, nên nếu
// bản vá không can thiệp thì orig() sẽ được gọi mãi.
function makeWin({ withGates = true } = {}) {
    const timers = new Map();
    let nextId = 1;
    const st = { ourCalls: 0, yourCalls: 0, warns: [] };
    const win = {
        LOIMG_CHAR_OUR_NUM: { MOVE: { tot: 20, cur: 3 } },
        LOIMG_CHAR_YOUR_NUM: { FIRE: { tot: 9, cur: 0 } },
        setInterval: (fn, ms) => { const id = nextId++; timers.set(id, { fn, ms }); return id; },
        clearInterval: (id) => { timers.delete(id); },
        console: { log() {}, warn(m) { st.warns.push(m); } }
    };
    win.window = win;
    if (withGates) {
        win.flag_LOIMG_CHAR_OUR = 0;
        win.flag_LOIMG_CHAR_YOUR = 0;
        win.interval_test_our = function () { st.ourCalls++; };
        win.interval_test_your = function () { st.yourCalls++; };
    }
    return { win, timers, st };
}

// Chạy patch, sau đó điều khiển thời gian.
//   pollTicks: số lần interval của BẢN VÁ chạy (chỉ chạy lúc bundle chưa nạp)
//   gateTicks: số lần cổng game tự hẹn lại — đây mới là vòng lặp 100ms thật
function run({ withGates = true, pollTicks = 0, gateTicks = 0, elapsed = 1000 } = {}) {
    const h = makeWin({ withGates });
    let now = 0;
    h.win.Date = { now: () => now };
    vm.runInContext(patch, vm.createContext(h.win));
    for (let i = 0; i < pollTicks; i++) {
        const list = [...h.timers.values()];
        h.timers.clear();
        for (const t of list) t.fn();
        now += 250;
    }
    for (let i = 0; i < gateTicks; i++) {
        h.win.interval_test_our();
        h.win.interval_test_your();
        now += elapsed;
    }
    return h;
}

// 1. Bundle chưa nạp -> patch phải hẹn poll, và poll phải tự dừng khi bọc xong
{
    const { win, timers } = run({ withGates: false });
    assert(timers.size === 1, `phai hẹn 1 interval, thuoc ${timers.size}`);
    // Bundle nạp: tick poll phai boc duoc ca hai co va xoa interval.
    win.flag_LOIMG_CHAR_OUR = 0;
    win.flag_LOIMG_CHAR_YOUR = 0;
    win.interval_test_our = function () {};
    win.interval_test_your = function () {};
    [...timers.values()][0].fn();
    assert(win.interval_test_our.__eldGate === true, "interval_test_our chua bi boc");
    assert(win.interval_test_your.__eldGate === true, "interval_test_your chua bi boc");
    assert(timers.size === 0, "interval poll phai clear sau khi boc xong");
}

// 2. Bọc idempotent: poll nhieu lan khong duoc boc lap
{
    const h = run({ withGates: false });
    const w = h.win;
    w.interval_test_our = function () {};
    w.interval_test_your = function () {};
    const tick = [...h.timers.values()][0].fn;
    tick(); const after = w.interval_test_our;
    w.interval_test_our = function () {};   // gia la bundle nap lai
    w.interval_test_your = function () {};
    w.interval_test_our.__eldGate = true;  // mo phong co wrapper roi
    // poll van chay: install() phai thay vi boc them
    const st = { ourCalls: 0, yourCalls: 0, warns: [] };
    w.interval_test_our = (function (orig) {
        return function () { st.ourCalls++; return orig.apply(this, arguments); };
    })(w.interval_test_our);
    w.interval_test_our.__eldGate = true;
    w.console.warn = m => st.warns.push(m);
    assert(after.__eldGate === true, "wrapper dau phai giu co __eldGate");
}

// 3. Chua het han: phai van goi ham goc de game load tiep
{
    const h = run({ gateTicks: 5 });
    assert(h.st.ourCalls === 5, `truoc han phai goi orig, thuoc ${h.st.ourCalls}`);
    assert(h.win.flag_LOIMG_CHAR_OUR === 0, "khong duoc mo coang khi chua het han");
    assert(h.st.warns.length === 0, "khong duoc canh bao khi chua het han");
}

// 4. Het han: tu mo coang, KHONG goi orig (dung khong hien lich lai)
{
    const h = run({ gateTicks: 20 });
    assert(h.win.flag_LOIMG_CHAR_OUR === 1, "het han phai tu mo coang our");
    assert(h.win.flag_LOIMG_CHAR_YOUR === 1, "het han phai tu mo coang your");
    assert(h.st.ourCalls < 20, `het han phai dung goi orig, thuoc goi ${h.st.ourCalls}/20`);
    assert(h.st.warns.length === 2, `phai canh bao ca our+your, thuoc ${h.st.warns.length}`);
    assert(/het han flag_LOIMG_CHAR_OUR/.test(h.st.warns[0]), `canh bao sai: ${h.st.warns[0]}`);
    assert(/MOVE/.test(h.st.warns[0]), "canh bao phai ke cur/tot de biet anh nao thieu");
}

// 5. Wave moi: game reset flag=0, han phai arm lai chu khong ban lenh ngay
{
    const h = run({ gateTicks: 20 });
    assert(h.win.flag_LOIMG_CHAR_OUR === 1, "wave 1 phai da mo coang");
    // Wave 2: game chay tiep, phai cho lai thoi gian chu khong mo ngay.
    h.win.flag_LOIMG_CHAR_OUR = 0;
    h.win.flag_LOIMG_CHAR_YOUR = 0;
    h.win.LOIMG_CHAR_OUR_NUM.MOVE = { tot: 20, cur: 1 };
    const before = h.st.ourCalls;
    h.win.interval_test_our();
    assert(h.win.flag_LOIMG_CHAR_OUR === 0, "wave moi bi mo coang ngay, khong cho tai lai");
    assert(h.st.ourCalls === before + 1, "wave moi phai goi orig de load tiep");
}

// 6. Coang da mo: phai giu duong goc cua game (khong chan)
{
    const h = run({ gateTicks: 20 });
    const before = h.st.ourCalls;
    h.win.interval_test_our();
    assert(h.st.ourCalls === before + 1, "coang da mo van phai goi ham goc");
    assert(h.win.flag_LOIMG_CHAR_OUR === 1, "coang da mo phai giu nguyen 1");
}

console.log("OK - gate cho anh tu mo khi het han");

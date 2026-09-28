// Regression: sua loi double-encode UTF-8 cho chuoi trong game.
//
// File bundle luu van ban non-ASCII theo kieu:
//     byte goc -> giai ma latin-1/cp1252 -> ma hoa lai UTF-8
// nen trinh duyet hien "Deck phÃ²ng thá»§" thay vi "Deck phòng thủ".
// Test lay chuoi THAT tu bundle, khong che tu dung.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
const html = readFileSync(path.join(root, "ELDORADO_WEB", "source_20240722", "index__mobile.html"), "utf8");
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const patch = blocks.find(b => b.includes("da sua loi double-encode"));
if (!patch) throw new Error("khong tim thay khoi script sua mojibake");

// --- lay chuoi that tu bundle ---
// Doc bundle bang UTF-8 — dung charset ma trinh duyet dung. Doc bang latin1 se
// tao ra mojibake 2 lan va khong phai anh chup gi cua game.
const bundle = readFileSync(path.join(root, "ELDORADO_WEB", "javascript_min", "eldorado_all_20260915.min.js"), "utf8");
function pickValue(key, which) {
    const re = new RegExp(`${key}="([^"]*)"`, "g");
    const all = [...bundle.matchAll(re)].map(m => m[1]);
    if (!all[which]) throw new Error(`khong lay duoc ${key} #${which}`);
    return all[which];
}
const KO_MOJI = pickValue("TXT.guild_battle_defence_title", 0);
const EN_TXT  = pickValue("TXT.guild_battle_defence_title", 1);
const VI_MOJI = pickValue("TXT.guild_battle_defence_title", 2);

// Menu ngon ngu trong Settings — lay ban khai bao that (6 muc, co "Tieng Viet").
// Luu y: bundle con co mot than ham gan S_SETTING_LANG=[2 muc] trong
// apply_only_ko_en_lang, nhung chi chay tren webOS TV nen khong co hieu luc.
function settingLangs() {
    const re = /S_SETTING_LANG\s*=\s*\[([^\]]*)\]/g;
    let best = [];
    for (const m of bundle.matchAll(re)) {
        const items = [...m[1].matchAll(/"([^"]*)"/g)].map(x => x[1]);
        if (items.length > best.length) best = items;
    }
    if (best.length !== 6) throw new Error(`S_SETTING_LANG phai co 6 muc, thuoc hien ${best.length}`);
    return best;
}
const LANG_MENU = settingLangs();

const assert = (c, m) => { if (!c) throw new Error(m); };

function run(TXT, S_SETTING_LANG) {
    const win = {
        TXT,
        S_SETTING_LANG,
        // Patch moc vao LANG.init; trinh duyet luon co LANG sau khi bundle nap.
        // O day LANG.init la no-op: TXT da co san gia tri -> repairAll chay ngay.
        LANG: { init() {} },
        setInterval: () => 1,
        clearInterval: () => {},
        // TextDecoder la global cua Node, khong phai intrinsic ECMAScript, nen vm
        // sandbox khong co san. Browser thi co.
        TextDecoder,
        console: { log() {} }
    };
    win.window = win;
    const ctx = vm.createContext(win);
    vm.runInContext(patch, ctx);
    return win;
}

// 1. Tieng Viet: "Deck phÃ²ng thá»§" -> "Deck phòng thủ"
{
    const TXT = { a: VI_MOJI, b: EN_TXT };
    run(TXT);
    assert(TXT.a === "Deck phòng thủ", `tieng Viet chua sua: ${JSON.stringify(TXT.a)}`);
    assert(TXT.b === "Defense Deck", `tieng Anh bi doi: ${JSON.stringify(TXT.b)}`);
}

// 2. Tieng Han cung hong cung kieu -> phai sua luon
{
    const TXT = { a: KO_MOJI };
    run(TXT);
    assert(TXT.a === "수비 덱 설정", `tieng Han chua sua: ${JSON.stringify(TXT.a)}`);
}

// 3. ASCII thuan giu nguyen
{
    const TXT = { a: "", b: "lv.120/150", c: "^0 khong du." };
    run(TXT);
    assert(TXT.b === "lv.120/150" && TXT.c === "^0 khong du.", "ASCII bi doi");
}

// 4. Chuoi da co ky tu Unicode that (>255) -> giu nguyen, khong sua lung tung
{
    const TXT = { a: "Tiếng Việt", b: "日本語", c: "emoji 😀" };
    run(TXT);
    assert(TXT.a === "Tiếng Việt", `chuoi Unicode that bi sua: ${JSON.stringify(TXT.a)}`);
    assert(TXT.b === "日本語" && TXT.c === "emoji 😀", "chuoi Unicode that bi sua");
}

// 5. Khong sua hai lan: repairAll chay nhieu lan phai ra cung ket qua
{
    const TXT = { a: VI_MOJI, ko: KO_MOJI, en: EN_TXT };
    run(TXT);
    const once = { ...TXT };
    for (let i = 0; i < 5; i++) run(TXT);
    assert(TXT.a === once.a, `sua hai lan khong ton tai: ${JSON.stringify(TXT.a)}`);
    assert(TXT.ko === once.ko, "tieng Han sua hai lan khong ton tai");
    assert(TXT.en === once.en, "tieng Anh sua hai lan khong doi");
}

// 6. Hook LANG.init: doi ngon ngu sau cung duoc sua
{
    let inited = 0;
    const win = {
        TXT: {},
        S_SETTING_LANG: LANG_MENU,
        LANG: {
            // Bundle that khai bao TXT={} mot lan roi TXT.key="..." gan vao chinh
            // object do — khong thay the. Fake phai mo phong dung dieu nay.
            init() { inited++; win.TXT.x = VI_MOJI; win.TXT.y = EN_TXT; }
        },
        setInterval: () => 1,
        clearInterval: () => {},
        TextDecoder,
        console: { log() {} }
    };
    win.window = win;
    vm.runInContext(patch, vm.createContext(win));
    win.LANG.init();
    assert(inited === 1, "LANG.init goc bi chặn, khong chay");
    assert(win.TXT.x === "Deck phòng thủ", `hook LANG.init chua sua: ${JSON.stringify(win.TXT.x)}`);
    assert(win.TXT.y === "Defense Deck", "hook lam doi tieng Anh");
    // menu Settings cung phai sua
    assert(win.S_SETTING_LANG[0] === "한국어", `menu lang[0] chua sua: ${JSON.stringify(win.S_SETTING_LANG[0])}`);
    assert(win.S_SETTING_LANG[2] === "Tiếng Việt", `menu lang[2] chua sua: ${JSON.stringify(win.S_SETTING_LANG[2])}`);
    assert(win.S_SETTING_LANG[1] === "English", "menu lang[1] bi doi");
}

// 7. Bundle nap sau onload: phai dung interval de thu hook, va PHAI clear
//    ngay khi bat duoc — giu se quet lai ~2299 chuoi TXT moi 500ms ke tu do.
{
    const timers = new Map();
    let nextId = 1;
    const win = {
        TXT: {},
        S_SETTING_LANG: [],
        setInterval: (fn) => { const id = nextId++; timers.set(id, fn); return id; },
        clearInterval: (id) => { timers.delete(id); },
        TextDecoder,
        console: { log() {} }
    };
    win.window = win;
    vm.runInContext(patch, vm.createContext(win));

    assert(timers.size === 1, `phai co 1 interval cho san, thuoc co ${timers.size}`);

    // Bundle chua nap -> hook that bai -> phai giu interval de thu lai.
    timers.get(1)();
    assert(timers.size === 1, "interval bi clear khi LANG chua san");

    // Bundle da nap -> hook bat duoc -> phai clear interval ngay.
    win.LANG = { init() { win.TXT.z = VI_MOJI; } };
    timers.get(1)();
    assert(timers.size === 0, "interval khong duoc clear sau khi hook thanh cong");

    // Clear interval khong duoc lam hong hook LANG.init.
    win.LANG.init();
    assert(win.TXT.z === "Deck phòng thủ", `hook LANG.init chua sua: ${JSON.stringify(win.TXT.z)}`);
}

console.log("OK - sua mojibake double-encode hoat dong dung");

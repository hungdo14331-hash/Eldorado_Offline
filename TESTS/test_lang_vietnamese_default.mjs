// Regression: mac dinh tieng Viet (LANG.VIETNAM) qua runtime override.
//
// Canh 3 tinh huong that, tat ca deu lay tu hanh vi thiet bi cua game:
//  1. Lan tai dau: chua co co -> ep LANG.VIETNAM, LANG.init() chay.
//  2. Client nap bundle SAU window.onload nen login sau do ghi de
//     USER.lang = LANG.get_code_by_data1(t[3], LANG.ENGLISH) -> phai giu ap de
//     cho toi khi gia tri on dinh 3s, neu khong se rot ve English.
//  3. Lan tai sau: da co co -> phai TON TRONG lua chon cua nguoi choi
//     (nguoi doi sang English trong Settings thi phai giu English).
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const html = readFileSync(
    path.join(here, "..", "ELDORADO_WEB", "source_20240722", "index__mobile.html"),
    "utf8");

const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const patch = blocks.find(b => b.includes("eldorado_default_vi_done"));
if (!patch) throw new Error("khong tim thay khoi script mac dinh tieng Viet");

const KO = 1, EN = 2, VI = 3;
const assert = (c, m) => { if (!c) throw new Error(m); };

// store = gia tri localStorage ban dau (null = chua tung ap dung)
function newPage({ lang = EN, store = {}, storageBroken = false } = {}) {
    const timers = [];
    let initCount = 0;
    const win = {
        LANG: {
            KOREA: KO, ENGLISH: EN, VIETNAM: VI,
            setVIETNAM() {},
            init() { initCount++; },
            // Ban sao cua ham that cua bundle. Kiem tra gia tri tra ve de
            // chung ta biet client co that su suy ra Viet hay khong.
            get_code_by_data1: (n, t) => {
                if (n === null) return t === undefined ? EN : t;   // chua luu -> fallback
                const v = parseInt(n, 10);
                return (v >= 1 && v <= 6) ? v : t;                // da luu -> tra ve luu
            }
        },
        STORAGE: { data1: { lang: EN } },
        USER: { lang },
        setInterval: fn => { timers.push(fn); return timers.length; },
        clearInterval: () => { win.__cleared = true; },
        console: { log() {} }
    };
    if (!storageBroken) {
        win.localStorage = {
            getItem: k => (k in store ? store[k] : null),
            setItem: (k, v) => { store[k] = v; }
        };
    }
    win.window = win;
    const ctx = vm.createContext(win);
    vm.runInContext(patch, ctx);
    return { win, timers, store, ticks: () => { for (const f of timers) f(); }, initCount: () => initCount };
}

// 1. Lan tai dau: chua co co -> ep ngay lap tuc.
{
    const p = newPage();
    assert(p.win.USER.lang === VI, "lan tai dau chua ep sang tieng Viet");
    assert(p.win.STORAGE.data1.lang === VI, "data1.lang chua dong bo");
    assert(p.initCount() === 1, "LANG.init() chua duoc goi");
    // Bundle chua nap xong: patch phai chua dung, khong danh dau xong.
    assert(p.store.eldorado_default_vi_done === undefined, "khong duoc danh dau xong khi bundle chua nap");
}

// 2. Login ghi de ve English sau -> phai giu ap de va phuc hui.
{
    const p = newPage();
    p.ticks();                                   // bundle nap xong, idle=1
    p.win.USER.lang = EN;                        // login ghi de nhu that
    p.ticks();                                   // phai ep lai
    assert(p.win.USER.lang === VI, "login ghi de English -> khong ap de lai duoc");
    assert(p.initCount() === 2, "LANG.init() phai chay lai sau khi bi ghi de");
    // Giu ap de 3s (6 nhip) roi danh dau xong.
    for (let i = 0; i < 6; i++) p.ticks();
    assert(p.store.eldorado_default_vi_done === "1", "gia tri on dinh 3s phai danh dau xong");
}

// 3. Lan tai sau: nguoi choi tu doi sang English -> phai giu English.
{
    const p = newPage({ lang: EN, store: { eldorado_default_vi_done: "1" } });
    p.ticks();
    p.ticks();
    assert(p.win.USER.lang === EN, "da ap dung xong thi khong duoc ep lai - se lam mat lua chon cua nguoi choi");
    assert(p.initCount() === 0, "khong duoc goi LANG.init() khi da ap dung xong");
    assert(p.win.__cleared === true, "phai clearInterval khi da ap dung xong");
}

// 4. Nguoi choi doi sang ngon ngu khac giua chung (idle reset, khong gianh quyen).
{
    const p = newPage();
    for (let i = 0; i < 3; i++) p.ticks();      // dang on dinh
    p.win.USER.lang = KO;                        // nguoi doi sang Han
    p.ticks();                                   // -> ep lai Viet, idle reset
    assert(p.win.USER.lang === VI, "phai ap de lai khi bi doi ngoai y");
    assert(p.store.eldorado_default_vi_done === undefined, "khong duoc chot sau khi vua bi doi ngoai y");
}

// 5. localStorage bi chan -> khong duoc crash.
{
    const p = newPage({ storageBroken: true });
    p.ticks();
    assert(p.win.USER.lang === VI, "khong ap duoc khi localStorage bi chan");
}

// 6. Ham boc LANG.get_code_by_data1: day la chan khe goc. Login goi
//    USER.lang = STORAGE.data1.lang = LANG.get_code_by_data1(t[3], ENGLISH).
//    Neu khong chan, login ghi de ve English lam UI da dung kiet tieng Anh.
{
    const p = newPage();
    p.ticks();                                   // bundle nap xong -> da boc ham
    // Gia loi chua luu trong save (t[3] == null) -> phai ra Viet.
    assert(p.win.LANG.get_code_by_data1(null, EN) === VI,
        "chua luu lang trong save -> phai suy ra Viet, khong phai fallback English");
    // Gia tri trong save la 2 (English) -> lan dau van phai ra Viet,
    // vi day la lan ap dung "mot lan" ma nguoi chua co quyen chon.
    assert(p.win.LANG.get_code_by_data1(2, EN) === VI,
        "lan dau phai bo qua gia tri English da luu trong save");
    assert(p.win.LANG.get_code_by_data1("vi", EN) === VI, "chuoi 'vi' phai ra Viet");

    // Sau khi chot (3s on dinh) -> ham boc phai trong suot tro lai.
    for (let i = 0; i < 6; i++) p.ticks();
    assert(p.store.eldorado_default_vi_done === "1", "chua chot sau 3s on dinh");
    assert(p.win.LANG.get_code_by_data1(null, EN) === EN,
        "sau khi chot, chua luu lang phai tro ve fallback goc");
    assert(p.win.LANG.get_code_by_data1(2, EN) === EN,
        "sau khi chot, gia tri trong save phai duoc ton trung");
    assert(p.win.LANG.get_code_by_data1(1, EN) === KO,
        "sau khi chot, Han Quoc trong save phai duoc ton trung");
}

// 7. Cac lan tai sau tren cung mot trinh duyet: setting cua nguoi choi la
//    nguon suy ra duy nhat.
{
    const p = newPage({ lang: EN, store: { eldorado_default_vi_done: "1" } });
    p.ticks();
    assert(p.win.LANG.get_code_by_data1(2, EN) === EN,
        "lan tai sau phai doc lang tu save, khong ep Viet");
    assert(p.win.LANG.get_code_by_data1(1, EN) === KO,
        "lan tai sau phai doc lang tu save, khong ep Viet");
}

console.log("OK - mac dinh tieng Viet hoat dong dung");

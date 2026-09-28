// Regression: một ảnh hỏng không được giết vĩnh viễn vòng lặp trận.
//
// Bằng chứng thực tế từ console người dùng:
//   Uncaught InvalidStateError: Failed to execute 'drawImage' on
//   'CanvasRenderingContext2D': The HTMLImageElement provided is in the
//   'broken' state.  at S_GAME.interval_set_your_div / move_our_or_enmey
//   / S_GAME.interval
//
// S_GAME.interval tự nối lại bằng setTimeout ở CUỐI hàm, nên exception ném ra
// ở move_our_or_enmey() khiến dòng hẹn lại không bao giờ chạy => loop chết hẳn,
// không hồi phục được nếu không rời trận. Rời trận vào lại thì hết vì asset đã
// nằm trong cache.
import { readFileSync } from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
const html = readFileSync(path.join(root, "ELDORADO_WEB", "source_20240722", "index__mobile.html"), "utf8");
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const patch = blocks.find(b => b.includes("CanvasRenderingContext2D.prototype") && b.includes("drawImage"));
if (!patch) throw new Error("khong tim thay patch guard drawImage");

const assert = (c, m) => { if (!c) throw new Error(m); };

// Ảnh giả: 'broken' = tải xong nhưng hỏng; 'loading' = còn đang tải; 'ok' = dùng được.
function img(kind) {
    if (kind === "broken") return { tagName: "IMG", complete: true, naturalWidth: 0, id: "broken" };
    if (kind === "loading") return { tagName: "IMG", complete: false, naturalWidth: 0, id: "loading" };
    if (kind === "empty") return { tagName: "IMG", complete: false, naturalWidth: 0, id: "empty-src" };
    return { tagName: "IMG", complete: true, naturalWidth: 64, naturalHeight: 64, id: "ok" };
}

function harness() {
    const st = { drawn: [], armed: 0 };
    // CanvasContext2D giả: ném InvalidStateError đúng như trình duyệt khi
    // không có pixel nào để vẽ (hỏng, còn đang tải, hoặc không phải IMG).
    function FakeCtx() {}
    FakeCtx.prototype.drawImage = function (im, ...rest) {
        st.drawn.push(im && im.id);
        if (!im || im.complete === false || !im.naturalWidth) {
            const e = new Error("InvalidStateError: ... 'broken' state.");
            e.name = "InvalidStateError";
            throw e;
        }
        return "drawn:" + im.id;
    };
    const win = { CanvasRenderingContext2D: FakeCtx, console: { log() {}, warn() {} } };
    win.window = win;
    vm.runInContext(patch, vm.createContext(win));
    return { ctx: new FakeCtx(), win, st };
}

// 1. Ảnh tốt thì vẫn vẽ bình thường, trả về giá trị gốc
{
    const h = harness();
    assert(h.ctx.drawImage(img("ok"), 0, 0, 10, 10) === "drawn:ok", "anh tot bi chan do ve");
    assert(h.st.drawn.length === 1, "phai ve that");
}

// 2. Ảnh hỏng (tải xong nhưng naturalWidth=0) -> bỏ qua, KHÔNG ném
{
    const h = harness();
    h.ctx.drawImage(img("broken"), 0, 0, 10, 10);
    assert(h.st.drawn.length === 1, "van pho len ctx.drawImage goc");
}

// 3. Ảnh còn đang tải (complete=false) -> cũng phải bỏ qua, không ném.
//    Cần vì cổng chờ 15 s có thể mở cổng khi ảnh chưa tải xong.
{
    const h = harness();
    h.ctx.drawImage(img("loading"), 0, 0, 10, 10);
    h.ctx.drawImage(img("empty"), 0, 0, 10, 10);
    assert(h.st.drawn.length === 2, "anh dang tai phai bi bo qua");
}

// 4. Lỗi KHÁC thì vẫn ném lại, không bị nuốt
{
    const h = harness();
    // Canvas khác loại: có tagName khác IMG nên phải nổi lên.
    let threw = null;
    try { h.ctx.drawImage({ tagName: "CANVAS", complete: true, naturalWidth: 0 }, 0, 0); }
    catch (e) { threw = e; }
    assert(threw !== null, "loi khac bi nuot mat, se che loi that");

    // Arg null cũng phải ném.
    threw = null;
    try { h.ctx.drawImage(null, 0, 0); } catch (e) { threw = e; }
    assert(threw !== null, "drawImage(null) phai nem, khong phai anh IMG");

    // Canvas TOT van phai ve duoc, khong bi guard lam hong.
    threw = null;
    try { h.ctx.drawImage({ tagName: "CANVAS", complete: true, naturalWidth: 8, naturalHeight: 8 }, 0, 0); }
    catch (e) { threw = e; }
    assert(threw === null, "canvas tot bi chan do ve");
}

// 5. Quan trọng nhất: mô phỏng đúng S_GAME.interval — ảnh hỏng ở giữa vòng lặp
//    thì dòng setTimeout tự nối lại ở CUỐI vẫn phải chạy.
{
    const h = harness();
    let ticks = 0;
    function S_GAME_interval() {
        // setTimeout(S_GAME.interval) nằm CUỐI hàm, giống bundle thật.
        const im = ticks === 0 ? img("broken") : img("ok");
        h.ctx.drawImage(im, 0, 0);            // chỗ vỡ trong log thật
        h.st.armed++;                          // tương đương setTimeout hẹn lại
        ticks++;
    }
    for (let i = 0; i < 5; i++) S_GAME_interval();
    assert(ticks === 5, `vong lap phay tiep tuc, thuoc chay ${ticks}/5 vong`);
    assert(h.st.armed === 5, `setTimeout phai duoc hen lai 5 lan, thuoc ${h.st.armed}`);
}

// 6. Không có bản vá thì vòng lặp phải chết — dùng để chứng minh test có răng
{
    function BareCtx() {}
    BareCtx.prototype.drawImage = function (im) {
        if (im.tagName === "IMG" && !im.naturalWidth) {
            const e = new Error("InvalidStateError: ... 'broken' state.");
            e.name = "InvalidStateError";
            throw e;
        }
    };
    const bare = new BareCtx();
    let armed = 0;
    function loop() {
        bare.drawImage(img("broken"), 0, 0);
        armed++;      // setTimeout hẹn lại ở CUỐI hàm — không bao giờ tới đây
    }
    let threw = false;
    try { loop(); } catch (e) { threw = true; }
    assert(threw === true, "ban khong patch phai nem ngay lan dau");
    assert(armed === 0, `ban khong patch phai vong lap chet, nhung da hen lai ${armed} lan`);
}

console.log("OK - anh hong khong giet vong lap tran");

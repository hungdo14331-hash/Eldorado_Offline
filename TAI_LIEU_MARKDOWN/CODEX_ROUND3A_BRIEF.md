# BRIEF CHO CODEX — PvP Round 3A (CLIENT MATCH_NONCE PATCH)

Ngày: 2026-09-24
Repo: `E:\UserData\Desktop\TEST ELDORADO\busidol_offline` (git branch `master`)
Trạng thái Round 3A: **HOÀN TẤT và ĐÃ KIỂM CHỨNG** (static + runtime). Việc còn lại chỉ là
closeout (docs + cleanup + bàn giao). **Chưa implement backend PvP** (đó là Round 3B, chờ
người dùng duyệt).

Đọc bắt buộc trước khi làm bất cứ điều gì: `AGENTS.md`, `TRI_THUC_DU_AN.md`.
Giao tiếp với người dùng bằng tiếng Việt.

---

## 1. TÓM TẮT ĐÃ LÀM GÌ (đều có bằng chứng, đã chạy thật)

Patch 5 vùng byte vào bundle client `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js`
bằng script `patch_pvp_nonce.py` (ở repo root), để client hỗ trợ MATCH_NONCE của PvP 2025:

- **A1** khai báo biến closure `m` trong IIFE `glo.pvp` (lưu nonce)
- **A2** 3 accessor `set_game_nonce` / `get_game_nonce` / `clear_game_nonce` gắn vào `glo.pvp`
  trước `Object.freeze(n)`
- **B** trong callback SUCCESS của `S_RANKING_PVP.enter_pvp_game` (PVP_2025): lưu
  `n.MATCH_NONCE` vào `glo.pvp` NGAY TRƯỚC `parse_matched_user(n.matched_user)`
- **C** trong payload `ServerConnection.update_pvp_result` (PVP_2025): thêm
  `t.MATCH_NONCE=glo.pvp.get_game_nonce();` (giữa `t.VER_DATE` và `t.ETC`)
- **D** ở ĐẦU callback SUCCESS của update trong `glo.pvp.goto_result_scene` (nhánh
  non-Classic): `glo.pvp.clear_game_nonce();` chạy trước mọi lệnh khác

### SHA-256

| File | Size (bytes) | SHA-256 |
|---|---|---|
| Input gốc (backup `eldorado_all_20260915.min.js.M0_BACKUP_20260924`) | 6,580,741 | `090b3674dd9a56fd6091680097f0734401c3dcf505332ed2db791c2e733ade50` |
| Output đã patch (bundle hiện tại) | 6,580,995 | `f3a15580215d3c8e94c17e2043ea51c5b41429547cab8838697caf7965d64389` |

Kiểm lại bất cứ lúc nào:
```
python -c "import hashlib;d=open('ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js','rb').read();print(len(d),hashlib.sha256(d).hexdigest())"
```

### 5 patch: anchor, offset (theo input gốc), vùng output thay đổi

| Tag | Offset input | Needle (rút gọn) | Vùng output | Số byte |
|---|---|---|---|---|
| B_RECEIVE | 893037 | `encoding_add_ruby(-glo.pvp.get_entry_fee_rubies()));glo.pvp.parse_matched_user(n.matched_user)` | [893037:893190] | 153 |
| A1_DECLARE_M | 904232 | `lt=500,b=null,f,e;return n.RESULT_TYPE` | [904291:904331] | 40 |
| D_CLEAR | 909768 | `function(n){s=parseInt(n.tot_score);o=parseInt(n.my_ranking);` | [909829:909917] | 88 |
| A2_ACCESSORS | 910048 | `},Object.freeze(n)}();var MAX_GLOBAL_RANK_NVN=10,` | [910136:910312] | 176 |
| C_SEND | 6392078 | `PVP_2025/update_pvp_result.php";t={};...t.VER_DATE=glo.VER_DATE;t.ETC="";` | [6392293:6392547] | 254 |

Tổng 711 byte thay đổi. **Mọi byte ngoài 5 vùng = byte-identical với bản gốc** (script tự
verify between-ranges + tail). Needle đầy đủ nằm trong `PATCHES` của `patch_pvp_nonce.py`.

### Static verification (script tự chạy khi patch, 14 check, tất cả PASS)

- `MATCH_NONCE` xuất hiện đúng 3 lần; `glo.pvp.set/get/clear_game_nonce` đúng 1 lần gọi mỗi loại.
- `n.set_game_nonce=function` = 2 (glo.pvp mới + glo.sky cũ vốn có — KHÔNG đụng sky),
  sky def `n.set_game_nonce=function(n){s=n==null?"":""+n}` vẫn đúng 1 lần, nguyên vẹn.
- URL `PVP_2025/enter_pvp_game.php` và `PVP_2025/update_pvp_result.php` đúng 1 hit mỗi URL.
- URL `PVP_CLS_2026/enter_pvp_cls_game.php`, `PVP_CLS_2026/update_pvp_cls_result.php` đúng 1 hit
  mỗi URL — **Classic không bị sửa**; 3 anchor Classic byte-identical sau patch:
  `[6375244:6375279]`, `[6377020:6377058]`, `[895814:895923]` (callback
  `parse_matched_user(n.matched_user)` thứ 2 @895822 là của Classic — đừng nhầm với patch B).
- Double-patch protection: chạy `python patch_pvp_nonce.py` lần nữa sẽ FAIL ngay ở cổng
  SHA-256 (đã thử, FAIL đúng như thiết kế). Muốn patch lại: phục hồi từ file backup rồi chạy.

### Runtime verification (§9 spec — 4/4 PASS, chạy 2026-09-24)

Môi trường: `harness_server.py` (HTTP 127.0.0.1:8023) + Chrome thật mở
`http://localhost:8023/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0`
(trước khi mở cần `localStorage.setItem('eldorado_fb_temp_id','harness_user')`).
Client boot đầy đủ qua loader.js → bundle đã patch → `glo.pvp` frozen, có đủ 3 accessor,
nonce khởi đầu `""`.

| Test | Gọi gì | Kết quả observed |
|---|---|---|
| T1 enter | `S_RANKING_PVP.enter_pvp_game("ENTRY_RUBY")` | nonce `""` → `"TEST_NONCE_123"`; `USER_NPC.id="NPC_HARNESS_1"`, `name="HARNESS_NPC"` (parse_matched_user chạy đúng fixture) |
| T2 update ERROR | `ServerConnection.update_pvp_result(cb)` (harness mode ERROR) | body wire chứa `MATCH_NONCE=TEST_NONCE_123`; callback KHÔNG được gọi; nonce vẫn `"TEST_NONCE_123"` |
| T3 update SUCCESS | `glo.pvp.set_game_result(glo.pvp.RESULT_TYPE.W)` + `glo.pvp.goto_result_scene()` (harness mode SUCCESS) | nonce `"TEST_NONCE_123"` → `""`; scene chuyển `S_STAGECLEAR` (callback chạy hết đường thật) |
| T4 enter lần 2 | `curl /__ctl?enter=TEST_NONCE_456` + gọi wrapper enter như T1 | nonce bị ghi đè thành `"TEST_NONCE_456"` |

Body wire 2 lần update (bằng chứng, từ `GET /__log` — field `update_calls`):
```
HOST_ID=HARNESS_UID_1&LANG=2&TEAM=1:1:20:0:0:1,...&SCORE=0&RESULT=&VER_DATE=20260908&MATCH_NONCE=TEST_NONCE_123&ETC=&IS_SYNC=false&USER_KEY=&RUN_COUNT=NaN&VERSION=EL_GLO_20260915&
```
(xuất hiện ở cả 2 lần gửi; lần SUCCESS nonce bị clear SAU khi gửi — đúng lifecycle.)

---

## 2. CÁC BẪY PHƯƠNG PHÁP ĐÃ MẶC (quan trọng khi test lại)

1. **Phải gọi đúng tầng.** Patch B nằm trong callback của `S_RANKING_PVP.enter_pvp_game`
   (wrapper UI), KHÔNG phải trong `ServerConnection.enter_pvp_game`. Gọi
   `ServerConnection.enter_pvp_game(...)` trực tiếp sẽ nhận SUCCESS nhưng nonce KHÔNG được lưu
   (đã vấp sai lần đầu — đây là lỗi test, không phải lỗi patch).
2. **Patch D nằm trong callback mà `glo.pvp.goto_result_scene` truyền cho
   `ServerConnection.update_pvp_result`.** Muốn test clear-on-SUCCESS phải đi qua
   `goto_result_scene()` (set `set_game_result(RESULT_TYPE.W)` trước để `set_game_score()`
   không báo lỗi). Gọi `ServerConnection.update_pvp_result(myCb)` trực tiếp chỉ test được C_SEND.
3. **Trang tự reload loop** (boot có TypeError trong S_EVENT/S_MAINMENU → put_error_log →
   trang load lại). Đọc nonce NGAY sau callback; nếu trang reload giữa chừng, nonce sẽ về `""`
   do page-load mới.
4. **Log harness chỉ giữ 120 entry cuối** — boot mỗi lần ~60+ request sẽ tràn cửa sổ và
   làm entry ENTER/UPDATE "biến mất". In toàn bộ window hoặc lọc `type == ENTER|UPDATE`.
5. Khi test enter, có thể tạm stub `ChangeScene.start = function(){}` để trang không nhảy vào
   trận battle (nonce được set TRƯỚC ChangeScene nên không ảnh hưởng kết luận); nhớ restore.
   Lưu ý: poll xong restore sớm có thể để ChangeScene thật chạy sau — vô hại.

---

## 3. HARNESS (nếu cần chạy lại / cho Round 3B)

File: `_pvp_patch_work/harness_server.py` — chạy `python _pvp_patch_work/harness_server.py`
(đang chạy nền từ session trước trên port 8023; nếu chết thì khởi lại bằng lệnh trên).

- Intercept MỌI request của client vì loader.js và mọi biến thể SERVER_URL trong bundle đều
  hardcode `http://localhost:8023/...` — không có gì ra internet.
- Boot stubs mô phỏng serve.py (`cnm_exist_host_in_server.php` trả USER:"NEW" + fixture đầy đủ
  để client tự dựng nhân vật mới; get_app_file trả danh sách 6 script).
- Điều khiển bằng curl:
  - `GET /__ctl?enter=<nonce>` — đặt nonce cho enter kế tiếp (mặc định `TEST_NONCE_123`)
  - `GET /__ctl?update=ERROR|SUCCESS` — đặt STATE cho update kế tiếp (mặc định ERROR)
  - `GET /__reset` — về mặc định + xóa log
  - `GET /__log` — JSON `{ctl, log(120 cuối), update_calls}` (update_calls giữ body nguyên văn)
- `PVP_2025/enter_pvp_game.php` trả: `{"STATE":"SUCCESS","MATCH_NONCE":<ctl.enter_nonce>,
  "s_add_ruby":"5000","add_ticket":"5","matched_user":MATCHED_USER}` với MATCHED_USER fixture:
  `ID=NPC_HARNESS_1, NAME=HARNESS_NPC, LEVEL=12, TOWER_HP=1200, TOWER_LEVEL=5, MISSILE_AP=77,
  MISSILE_LEVEL=3, MISSILE_TICK=600, TEAM="101:1:10:0:0:101,102:1:10:0:0:102,103:1:10:0:0:103",
  ITEM="", PLATFORM="PC", PROFILE="1"`.
- `PVP_2025/update_pvp_result.php`: capture body vào `update_calls`; ERROR →
  `{"STATE":"ERROR","CODE":"-104",...}`; SUCCESS → `{"STATE":"SUCCESS","tot_score":"100",
  "my_ranking":"1","max_score":"200","score_reward_str":"1,2,3","ranking_list":[]}`.

---

## 4. VIỆC CÒN LẠI CỦA ROUND 3A (closeout — chưa làm)

1. Cập nhật `TRI_THUC_DU_AN.md`: thêm đợt Round 3A (ngày 2026-09-24, mục tiêu, bằng chứng như
   mục 1 ở trên, file liên quan, giới hạn, bước tiếp theo). Không ghi "đã kiểm tra" cho gì
   chưa chạy thật.
2. Dọn artefact: xóa `_pvp_patch_work/` (audit scripts + harness + report) SAU khi kết quả đã
   nằm trong TRI_THUC_DU_AN.md; dừng task nền harness (nếu còn chạy). GIỮ: bundle đã patch,
   file backup `.M0_BACKUP_20260924`, `patch_pvp_nonce.py` ở repo root. Nếu người dùng duyệt
   Round 3B thì cân nhắc giữ/đánh dấu `harness_server.py` (nó là nền để test backend mới).
3. Bàn giao theo §11 spec: 10 mục (input SHA, output SHA, 3 anchor chính, byte ranges, tính
   identical ngoài ranges, lifecycle, static verification, runtime evidence, Classic
   byte-identical, danh sách file). Sau đó DỪNG.

## 5. RÀNG BUỘC TUYỆT ĐỐI (kế thừa từ spec Round 3A + AGENTS.md)

- **PVP_CLS_2026 không được sửa** (Classic giữ nguyên vẹn, đã verify byte-identical).
- Không patch: Ajax wrapper, timers, global fetch/XHR, World Boss, Sky, Cloud, RubyFarm.
- `serve.py` ĐANG ĐÓNG (Boss Round kết thúc) — chỉ dùng làm tham chiếu read-only cho stubs.
- Không đụng: server 8029 (của người dùng, không restart), save thật (`save_anh.json`,
  `offline_save.json`), `busidol.db`, `busidol_banbe.db`, `M0_BASELINE_20260924_014351/`,
  `index__mobile.html`. Không commit nếu chưa được yêu cầu.
- Thao tác tiền/trận/tài khoản chỉ chạy trên dữ liệu test riêng (harness dùng HOST_ID
  `HARNESS_UID_1`, user mới "NEW" — không chạm save thật).

## 6. NẾU ĐƯỢC GIAO ROUND 3B (backend PvP thật — CHỜ NGƯỜI DÙNG DUYỆT, chưa làm)

Hợp đồng client-side đã biết (đọc từ bundle + wire):

- `enter_pvp_game` request: `HOST_ID, LANG, NAME, LEVEL, TEAM, ITEM, TOWER_HP, TOWER_LEVEL,
  MISSILE_AP, MISSILE_LEVEL, MISSILE_TICK, MODE(ENTRY_RUBY|ENTRY_TICKET), VER_DATE, ETC` +
  meta `IS_SYNC/USER_KEY/RUN_COUNT/VERSION`. Ajax enter trả CẢ SUCCESS lẫn ERROR cho callback.
- enter SUCCESS cần trả: `MATCH_NONCE` (sinh server, single-use), `s_add_ruby`, `add_ticket`
  (optional, client check `hasOwnProperty`), `matched_user` (cấu trúc như fixture ở mục 3).
- enter ERROR codes client đã biết map thông báo: `-101` timelimit, `-102` cloud_garden,
  `-103` ruby_lack, `-104` matching_user_error.
- `update_pvp_result` request: `HOST_ID, LANG, TEAM, SCORE, RESULT, VER_DATE, MATCH_NONCE,
  ETC` + meta. Ajax update CHỈ giao STATE==="SUCCESS" cho callback app (ERROR/NONE/mysql_error
  đều early-return) → lỗi chỉ cần trả STATE=ERROR, client tự giữ nguyên nonce.
- update SUCCESS cần trả: `tot_score, my_ranking, max_score, score_reward_str, ranking_list`.
- Server semantics theo spec người dùng: enter SUCCESS ghi đè nonce cũ; update SUCCESS consume
  nonce (single-use) + TTL/re-entry xử lý session bỏ rơi; không fingerprint-only.
- Lưu ý: `RESULT` trên wire có thể rỗng nếu game flow không set kết quả trước khi gọi — server
  Round 3B cần quyết định validate thế nào (đề xuất: chỉ nhận W/L/D/B khớp `glo.pvp.RESULT_TYPE`).

Quyết định phạm vi Round 3B (ranking/opponent pool/reward/rating có làm ngay không) phải hỏi
người dùng trước — theo đúng quy trình đã thống nhất.

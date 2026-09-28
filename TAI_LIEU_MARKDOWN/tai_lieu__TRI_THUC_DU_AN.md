# Tri thức dự án Eldorado / Busidol Offline

Cập nhật: 24/09/2026 03:44. File này được tạo theo yêu cầu của người dùng để lưu kiến thức sau mỗi đợt làm việc.

## 1. Cách sử dụng

- Đọc phần hiện trạng trước khi sửa; xem nhật ký để hiểu nguồn bằng chứng.
- Sau mỗi đợt làm việc có thông tin mới, cập nhật hiện trạng và thêm một mục nhật ký theo mẫu cuối file.
- Phân biệt: **đã kiểm chứng bằng thử nghiệm**, **đã thấy trong mã/schema**, **đề xuất**, **chưa xác nhận**.
- Không chứa bí mật đăng nhập hoặc dữ liệu riêng tư. Khi có xung đột, yêu cầu hiện tại của người dùng và bằng chứng mới là căn cứ cập nhật.

## 2. Các quyết định đã chốt với người dùng

- PvP bản đầu là đấu đội hình đã lưu của người khác; không yêu cầu cả hai cùng online.
- Đợt thử kín đầu tiên dành cho 5–20 người bạn.
- Mục tiêu: bảng xếp hạng PvP/Sky lưu bền, hoàn thiện Cloud Garden/World Boss, giao diện, nhân vật, tính năng, sửa lỗi, trải nghiệm, bảo mật và database.
- Cài các skill ưu tiên cao trước; các skill còn lại bổ sung khi cần.
- Cập nhật tri thức vào file Markdown mới sau mỗi đợt hoạt động.
- Yêu cầu gần nhất là tiếp tục triển khai; lát M1 đầu tiên đã được thực hiện cho bảng hạng Sky Garden trên SQLite.
- Đợt 24/09/2026 (RubyFarm + đường dẫn): phạm vi nâng cấp `ELDORADO_WEB/rubyfarm.html` là **sửa các lỗi đã xác định + giao diện/UX** (trạng thái đang tải/lỗi/thử lại, hiện vé–phí–điều kiện trước khi vào game, chữ tiếng Việt rõ hơn, hiển thị tốt hơn trên màn nhỏ); **không thêm tính năng mới**.
- Vé máy phát (genrep): **chỉ sửa chữ cho khớp server** (3 vé miễn phí/ngày, không bán bằng vàng); không mở bán vé máy phát.
- `serve.py`: đường dẫn CLI tương đối (`--save-file/--db/--log/--capture`) resolve theo thư mục project; đường dẫn tuyệt đối giữ nguyên hành vi.
- Cách kiểm chứng đã chốt cho đợt RubyFarm: chạy server tạm ở cổng riêng với dữ liệu riêng, mở trang thật trong trình duyệt, xong thì tắt instance tạm.

## 3. Bản đồ dự án — đã thấy trong mã

| Thành phần | Vị trí | Vai trò |
|---|---|---|
| Máy chủ | `serve.py` | Python HTTP server; chế độ offline/proxy; trả các API có đuôi PHP |
| Game chính | `ELDORADO_WEB/source_20240722/index__mobile.html` | Trang mở game, có các phần tùy chỉnh giao diện/tốc độ |
| Logic client | `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js` | JavaScript nén, chứa chiến đấu và giao thức API |
| RubyFarm | `ELDORADO_WEB/rubyfarm.html` | 8 minigame, ví ruby, điểm danh và vé |
| Đổi tài nguyên | `ELDORADO_WEB/convert.html` | Giao diện đổi tiền/tài nguyên |
| Game nhúng | `minigame/generator_repair.html`, `minigame/sudoku.html` | Sửa máy phát và Sudoku |
| Cầu nối minigame | `minigame/rubyfarm_bridge.js` | Gọi API và yêu cầu trang cha cập nhật ví |
| Database | `busidol.db`, `busidol_banbe.db` | SQLite cho nhiều tài khoản |
| Save riêng | `offline_save.json`, `save_anh.json`, `save_em.json`, `save_moi.json` | Dữ liệu cho các chế độ/instance riêng; chưa xác nhận file nào đang dùng trực tiếp |
| Khởi động | `CHOI_*.bat`, `ELDORADO_OFFLINE.bat`, `KHOIDONG.bat` | Các cách chạy local, nhiều tài khoản và tunnel |

Workspace đang làm: `E:\UserData\Desktop\TEST ELDORADO\busidol_offline`. Trước đợt 24/09/2026 dự án được chép từ `C:\busidol_offline` và các launcher/script còn trỏ đường dẫn cũ; đã sửa (xem mục 9). Chưa khảo sát nội dung workspace `C:\busidol_offlineR`.

Thư mục có nhiều sửa đổi và tài nguyên chưa commit. Không coi tất cả thay đổi đó là do đợt làm việc hiện tại tạo ra.

`file_A/` (tạo 24/09/2026) là bản trích chọn lọc mã nguồn + tài liệu — 81 file, 7,9 MB — để chia sẻ cho AI bên ngoài đọc hiểu dự án; giữ nguyên cấu trúc đường dẫn, **không chứa asset nặng, log, bản sao lưu hay dữ liệu riêng tư** (xem mục 9). Đây không phải bản chạy được đầy đủ.

## 4. Database và lưu dữ liệu — đã đọc schema

- Hai database đã đọc ở chế độ chỉ đọc đều có `accounts(id TEXT PRIMARY KEY, pw_hash TEXT)` và `saves(id TEXT PRIMARY KEY, payload TEXT)`.
- `payload` chứa JSON save, còn `DATA1`, `DATA2`, `DATA3` dùng chuỗi dữ liệu kiểu CSV theo game cũ.
- Chế độ JSON và SQLite cùng tồn tại. SQLite chọn save theo tài khoản trong ngữ cảnh request.
- `SAVE_LOCK` là khóa RLock; nhiều luồng đọc–sửa–ghi đã dùng khóa, nhưng còn phải kiểm tra tính nguyên tử từng API khi triển khai dữ liệu mới.
- Đã thêm bảng `sky_sessions` và `sky_leaderboard` khi khởi tạo SQLite. Đây là nền tối thiểu cho Sky; mùa, trận PvP và giao dịch thưởng vẫn chưa có bảng riêng.
- Ngày 24/09/2026 01:43 đã xác nhận tiến trình PID 17160 chạy `python serve.py --mode offline --port 8029`, nghe tại `127.0.0.1:8029`. Không có `--db` hoặc `--save-file`, nên phiên này dùng save JSON mặc định `offline_save.json`; SQLite chưa phải dữ liệu trực tiếp của phiên đang chạy.
- Kiểm tra cuối đợt 24/09/2026 03:44: không có tiến trình `python.exe` nào đang chạy và cổng 8029 không nghe; đợt làm việc không dừng tiến trình này. Instance tạm cổng 8039 của đợt kiểm chứng đã được tắt sạch.

## 5. Chế độ chơi và xếp hạng — đã thấy trong mã

### Sky Garden

- API: `SKY_2026/get_sky_ranking.php`, `enter_sky_game.php`, `update_sky_result.php`.
- Có lưu `sky_wave` trong save cá nhân; danh sách trả về chỉ có chính người gọi và hạng luôn 1.
- Có tạo `sky_nonce`; client gửi `GAME_NONCE` lúc báo kết quả, nhưng server chưa kiểm tra ở nhánh cập nhật.
- Cần kiểm tra một lượt gửi kết quả từng wave hay chỉ lúc kết thúc để thiết kế khóa chống ghi lặp đúng.

### Cloud Garden

- API: `cloud_garden/cloud_garden_ranking.php`, phân nhánh `RANKING_GET`, `GAME_TICKET`, `GAME_RUBY`, `GAME_END`.
- Có lưu điểm cá nhân, vé và Cloud Piece. Bảng hiện chỉ có chính người gọi với hạng 1.
- Có tạo `cloud_nonce`; `GAME_END` chưa kiểm tra/tiêu thụ phiên tương ứng để chặn trả thưởng nhiều lần.
- Lịch mùa có mốc cố định, chưa phải vòng mùa thật.

### PvP

- Client có **4 nhánh PvP** (đã tra trực tiếp từ `eldorado_all_20260915.min.js`):
  - `PVP_2025/` — `get_pvp_ranking.php`, `enter_pvp_game.php`, `update_pvp_result.php`.
  - `PVP_CLS_2026/` — `get_pvp_cls_ranking.php`, `enter_pvp_cls_game.php`, `update_pvp_cls_result.php`. **Đây là "PvP Classic".**
  - `PvP/` (cũ) — `get_rank50_from_server_pvp.php`, `get_user_info_for_pvp.php`.
  - `CPvP/` (cũ) — `get_rank50_from_server_cpvp.php`, `get_user_info_for_nvn.php`, `put_score_to_server_cpvp.php`, `del_pvp_one_data_to_server_cpvp.php`.
- Xác minh 28/09/2026 bằng grep `serve.py`: chỉ `PVP_2025/` **có** handler (L3689, bảng `pvp_sessions`/`pvp_leaderboard`, có ticket + ruby + nonce). `PVP_CLS_2026/`, `PvP/`, `CPvP/` **không có chuỗi nào trong `serve.py`** → rơi xuống `offline_stub`.
- Bản ghi cũ ở mục này nói "chưa tìm thấy handler riêng" là đã lỗi thời: `PVP_2025` đã làm. Việc còn thiếu là **PvP Classic** và hai nhánh API cũ.
- Client gửi đội hình/chỉ số và điểm; cần chốt đội hình trên server và định danh trận cho các nhánh mới.

### World Boss

- Client có `BOSS_2026/*`, nhánh thử và `Boss/*` cũ; chưa tìm thấy handler riêng trong server được đọc.
- Thông tin sự kiện hiện đặt `cur_boss_hp` thành 0.
- HP chung, đóng góp sát thương, lịch đợt và thưởng là phần cần thiết kế/hoàn thiện.

## 6. Lỗi và bằng chứng đã thu thập

Các kết quả dưới đây được thử ngày 24/09/2026 bằng instance tạm bind localhost với SQLite `:memory:`, tài khoản giả; không thử ghi trên tài khoản người dùng. Cần chạy lại khi mã thay đổi.

| Vấn đề | Bằng chứng | Trạng thái |
|---|---|---|
| API tin ID tài khoản do client gửi | Đọc được số dư của tài khoản thử qua `HOST_ID` dù không đăng nhập, khi `REQUIRE_LOGIN=True` | Đã tái hiện, chưa sửa |
| Trang quản trị lộ khóa | Request thiếu khóa nhận lỗi 401 nhưng nội dung chứa khóa thực; kiểm tra nội bộ dựa vào Host | Đã tái hiện, chưa sửa |
| Autoplay nhận số ngày âm | `AUTO_DAY=-1` tăng BP trên dữ liệu thử | Đã tái hiện, chưa sửa |
| Sudoku nhận thưởng chưa xác minh lời giải | Phiên hard vừa tạo nhận claim thành công mà không có dữ liệu lời giải | Đã tái hiện, chưa sửa |
| Hard mode mở sẵn toàn bộ 200 màn | Save mới được seed `201\|\|0,...`; `parse_server_hard_mode_data` đọc `CUR_HARD_STAGE_NUM=201`, mà `S_SELECTSTAGE_HARD.set_maxfocus` coi `>=200` là mở hết | Đã sửa 26/09/2026 |
| Hard mode nhận `STAGE_DATA` tùy ý, không kiểm tra chuyển màn | `update_hardmode_to_server.php` gói thẳng giá trị int client gửi; một POST `STAGE_DATA=201` là mở hết map | Đã sửa 26/09/2026 |
| Sudoku hết phiên trước hạn giao diện | Hard khai báo 1.200 giây, claim ở 960 giây bị từ chối vì TTL 900 giây | Đã sửa: `ttl = max(900, thời lượng độ khó + 120)` (`SUDOKU_CLAIM_GRACE`); đã kiểm chứng lại (mục 9) |
| RubyFarm hiện số liệu lệch server | Trang ghi "5 giây nghỉ", "hạn mức 300/ngày" và "vé máy phát… mua thêm trong Ví" trong khi server dùng cooldown 3 giây, hạn mức 500/ngày và từ chối mua vé máy phát | Đã sửa: đọc `cd`/`cap` từ `mywallet.php`, sửa chữ theo thực tế server |
| Trang Ví hiện `NaN` ở ô "Hôm nay kiếm" | `fmt()` nhận chuỗi `"88 / 500"` thay vì số (có từ bản gốc) | Đã sửa: định dạng từng số trước khi ghép chuỗi |
| Hạn mức "Hôm nay +N/cap" hiện số của hôm trước vào đầu ngày mới | `mywallet.php` trả `wallet_earned` đã lưu, không tự sang ngày (`serve.py` dòng 2205–2206); chỉ `award`/`claim` mới đặt lại khi thấy `wallet_day` khác hôm nay (dòng 2234–2237, 2321–2324, 2381–2384). Thấy trực tiếp: HUD "+93/500" trước lượt thưởng đầu tiên của ngày, "+3/500" sau đó | Đã tái hiện, **chưa sửa** (ngoài phạm vi redesign, chỉ ghi nhận) |
| Chip "⚠️ Mất kết nối · Thử lại" không xuất hiện | `retryAll()` gán `CONN` sau khi `renderHud()` đã chạy | Đã sửa: gọi `renderHud()` sau khi cập nhật `CONN`; kiểm chứng bằng cách tắt/bật server thật |
| Bảng hạng Garden chỉ có một người | Đọc nhánh xây `ranking_list`/`RANKING_ARR`, hạng gán 1 | Đã sửa cho chế độ SQLite; JSON đơn tài khoản vẫn giữ fallback cũ |
| Kết quả/thưởng Garden có thể gửi lặp | Nhánh nhận kết quả thiếu kiểm tra/đóng mã trận | Sky đã có nonce một lần; Cloud vẫn chưa sửa |
| Tốc độ 2x bọc timer toàn trang | HTML thay `setInterval`/`setTimeout` | Cần tái hiện ảnh hưởng tới chế độ xếp hạng và bật/tắt |
| **Đứng máy giữa trận khi gặp asset chưa cache** | Game đếm ảnh battle bằng `img.onload` (`LOIMG_CHAR_OUR_NUM.<AC>.cur++`, `LOIMG_ETC_OUR.cur++`) nhưng **không** có `onerror`. Ảnh lỗi chỉ bắn `onerror` nên `cur` không bao giờ đạt `tot`; `interval_test_our`/`interval_test_your` tự hẹn lại mỗi 100 ms **vô hạn**, `flag_LOIMG_CHAR_OUR/YOUR` kẹt 0, cổng start trận không bao giờ mở | Đã sửa 27/09/2026: ảnh thiếu trả `200` + PNG trong suốt 1×1; thêm timeout 15 s cho cổng chờ |
| **Vòng lặp trận chết vĩnh viễn khi 1 ảnh hỏng** (nguyên nhân đứng thật) | `S_GAME.interval` tự nối lại bằng `setTimeout` ở **cuối** hàm. `drawImage` trên ảnh `broken` ném `InvalidStateError` ở `move_our_or_enmey()` **trước** dòng hẹn lại → loop chết hẳn, không tự hồi phục | Đã sửa 27/09/2026: guard `CanvasRenderingContext2D.prototype.drawImage` bỏ qua ảnh chưa có pixel, mọi lỗi khác vẫn ném |
| Timer sửa mojibake quét lại vô hạn | `else setInterval(hook, 500)` không lưu/clear timer nên sau khi bundle nạp, mỗi 500 ms quét lại ~2299 chuỗi `TXT` | Đã sửa 27/09/2026: lưu timer, `clearInterval` ngay khi hook thành công |

Kiểm tra cú pháp đã đạt ở đợt khảo sát: Python `serve.py`; JavaScript bundle chính, `rubyfarm_bridge.js`, `ovr_gold_x5.js`; script nhúng trong RubyFarm, Convert, Sudoku và Generator. Đây không phải chứng nhận gameplay hoàn chỉnh.

## 7. Skill đã cài ngày 24/09/2026

Thư mục: `C:\Users\THE HUAN\.codex\skills`. Cài bằng công cụ Skill Installer, lấy bản cố định theo commit để truy vết.

| Skill | Nguồn | Dùng cho |
|---|---|---|
| `systematic-debugging` | `obra/superpowers` | Tái hiện và tìm nguyên nhân lỗi |
| `test-driven-development` | `obra/superpowers` | Kiểm tra hành vi trước khi sửa logic quan trọng |
| `verification-before-completion` | `obra/superpowers` | Xác nhận bằng chứng trước khi báo hoàn thành |
| `security-best-practices` | `openai/skills` | Rà soát/cải thiện bảo mật theo phạm vi yêu cầu |
| `webapp-testing` | `anthropics/skills` | Kiểm thử giao diện và luồng trình duyệt |
| `frontend-design` | `anthropics/skills` | Thiết kế giao diện khi tới mốc M5 |
| `ponytail` | `DietrichGebert/ponytail` | Ưu tiên giải pháp nhỏ nhất đủ dùng, tái sử dụng mã sẵn có và tránh phụ thuộc/mã thừa |
| `codex-with-chatgpt` | `XiaoDuoYa/codex-with-chatgpt` | Kết nối ChatGPT với workspace để lập kế hoạch/review bằng quyền đọc |

Commit nguồn:

- `obra/superpowers`: `5bf4e78011075bcfc0dc295f0724994cd123ee71`.
- `openai/skills`: `49f948faa9258a0c61caceaf225e179651397431`.
- `anthropics/skills`: `34040c9c568585f6929bedeaad110ad08f079624`.
- `DietrichGebert/ponytail`: `e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156`.

Các bộ trên đã được chép vào thư mục skill; sẽ khả dụng ở lượt tương tác tiếp theo. Chưa kiểm tra/cài thêm runtime Playwright hoặc trình duyệt của nó trong đợt này. Imagegen, Computer Use, Skill Creator đã được cung cấp sẵn trong phiên.

Ponytail được cài ở dạng skill thuần, không cài plugin và hai hook nền. Nó giúp hạn chế mã, abstraction, dependency và phần giải thích không cần thiết; không tự động nén mọi context/token hệ thống.

Để sau: UI/UX Pro Max, Develop Web Game; skill riêng cho Busidol mới là đề xuất, chưa tạo. Không cài toàn bộ bộ Superpowers hoặc các skill điều phối agent.

## 8. Lộ trình và quyết định còn mở

- Chi tiết: `KE_HOACH_PHAT_TRIEN.md`. Sơ đồ và ước lượng sơ bộ: `LICH_TRINH_DU_AN.md`.
- Thứ tự: M0 bản nền → M1 tài khoản/database → M2 Sky → M3 PvP → M4 Cloud/Boss → M5 giao diện → M6 nhân vật → M7 chơi thử.
- Mốc đầu tiên: nhiều tài khoản thấy cùng bảng Sky, điểm còn sau restart và gửi lặp không cộng lần nữa.
- Luật điểm, lịch mùa, phần thưởng, xử lý tài khoản tăng tài nguyên để thử, phong cách nhân vật và ngân sách vận hành chưa chốt.
- Xác minh chiến đấu trên server là phần chưa rõ khối lượng. Mã trận và giới hạn điểm không bảo đảm ngăn mọi kết quả giả do client tạo.
- Guild: **HOÀN TẤT 100%, người dùng xác nhận trên trình duyệt 28/09/2026** — giai đoạn 1 (guild thường) 27/09/2026: tạo/join/duyệt/thành viên/chat/đuổi/chuyển chủ/xoá/slot/buff/nhiệm vụ/quyên góp/xếp hạng mùa. 28/09/2026: Guild War (`update_guild_battle.php`, 11 act), Guild Boss (`update_guild_boss.php`, 5 act), Guild Shop (`update_guild_shop.php`) gồm cả 4 card (item ×1/×10 + hero ×1/×10), và gỡ bộ lọc từ cấm chat. Xem các mục nhật ký tương ứng.
  - **LUNAR LUCKY không giới hạn số lượt — người dùng quyết 28/09/2026.** Client vẽ `/60` bằng `get_lunar_lucky_cnt()` nhưng server **không hề có** bộ đếm hay chặn: `serve.py` chỉ trả `lunar_lucky_cnt: 0` cứng trong response boot, `guild_backend._act_send` không đọc số này. Đây là quyết định của người dùng, **không phải phần còn thiếu** — không cần viết code thêm. Con số `/60` trên màn hình chỉ là chữ vẽ, không có tác dụng gì.
  - Số giá buff, trần duyệt, giá card, tỉ lệ rút 55/15/10/10/10 là **số do server tự đặt**, chưa đối chiếu game gốc.
  - Vấn đề cookie session dùng chung giữa các cửa sổ trình duyệt (mất quyền chủ khi chơi 2 tài khoản cùng lúc) **đã hết triệu chứng theo xác nhận của người dùng**; cơ chế `--wire-identity` vẫn còn trong mã nhưng **mặc định tắt** — xem mục 9.
  - **Đính chính 28/09/2026:** câu "Guild Boss đã làm thật từ trước" ở bản ghi cũ là **ghi nhầm** — cái đã làm là **World Boss 2026** (`boss_2026/*.php`, bảng `boss_state`/`boss_damage`/`boss_sessions`, `serve.py:215`). `update_guild_boss.php` **chưa** làm ở thời điểm ghi nhận sai đó; hiện đã làm 28/09/2026.

## 9. Nhật ký đợt làm việc

### 24/09/2026 — Khảo sát và lập kế hoạch

- Đã đọc cấu trúc, mã máy chủ/client, ghi chú lịch sử và schema SQLite.
- Đã thử các lỗi ở mục 6 trên dữ liệu tạm và kiểm tra cú pháp; chưa sửa mã game, dữ liệu thật hoặc khởi động lại server người dùng.
- Đã tạo `KE_HOACH_PHAT_TRIEN.md` dựa trên lựa chọn PvP bất đồng bộ và nhóm 5–20 người.

### 24/09/2026 — Cài skill, thiết lập tri thức và lịch trình

- Cài 6 skill ưu tiên cao từ các commit nguồn ở mục 7; installer trả thành công cho từng skill.
- Tạo `TRI_THUC_DU_AN.md`, `AGENTS.md` để nhắc việc đọc/cập nhật tri thức ở các đợt sau, và `LICH_TRINH_DU_AN.md` để lưu sơ đồ.
- Bổ sung liên kết lịch trình vào kế hoạch. Mã game, save và database không được chỉnh sửa trong đợt này.
- Kiểm tra bàn giao đã đạt: SHA-256 của cả sáu `SKILL.md` khớp bản từ commit nguồn; mỗi skill có metadata và tài nguyên kèm theo. Bốn file Markdown đọc được UTF-8, khối mã đóng đủ, các liên kết tài liệu nội bộ tồn tại. Tổng khoảng dự kiến các mốc là 22–40 ngày công. Chưa chạy kiểm thử gameplay hoặc kiểm tra runtime của các skill.
- Bước tiếp theo: khi người dùng yêu cầu triển khai, bắt đầu M0; xác nhận runtime kiểm thử, cổng/database thử và giao thức từng chế độ trước khi sửa server.

### 24/09/2026 — M0, lát đầu: mốc phục hồi

- Người dùng yêu cầu bắt đầu bước đầu và cho rằng ước lượng theo ngày quá rộng. Lịch đã đổi M0 thành một buổi, trong đó lát sao lưu đầu dự kiến 30–90 phút; các mốc sau sẽ ước lượng lại từ dữ liệu thực tế.
- Đã xác nhận server local đang chạy ở chế độ offline mặc định, PID 17160, cổng 8029; không dừng hoặc khởi động lại server.
- Đã tạo `M0_BASELINE_20260924_014351` gồm mã liên quan, save, file khởi động và hai bản sao SQLite nhất quán. README trong thư mục ghi trạng thái, phạm vi và cách phục hồi an toàn.
- Trước khi sao lưu: bốn save JSON đều đọc được; `busidol.db` integrity `ok` với 7 tài khoản/4 save; `busidol_banbe.db` integrity `ok` với 0 tài khoản/0 save.
- Chưa sửa logic game, save đang hoạt động hoặc schema. Phần M0 tiếp theo là dựng một server/database thử ở cổng riêng và ghi lại giao thức Sky; chưa thực hiện trong lát này.
- Theo yêu cầu bổ sung, đã cài `ponytail` dạng skill thuần từ commit đã ghi ở mục 7; không cài plugin/hook nền để giữ cấu hình nhẹ.
- Kiểm tra sau cùng: 20/20 file thường trong baseline khớp SHA-256 với nguồn; 4/4 save JSON đọc được; 2/2 database backup có integrity `ok` và đúng số dòng; `ponytail/SKILL.md` khớp SHA-256 với commit nguồn; tài liệu UTF-8 và khối Markdown hợp lệ.

### 24/09/2026 — M0, lát hai: giao thức Sky trên môi trường tách biệt

- Đã tạo `M0_TEST_20260924` với SQLite riêng, ba tài khoản giả và server tạm ở `127.0.0.1:8049`. Không dùng hoặc ghi vào database/save thật.
- Đã chạy luồng đăng nhập → đọc bảng → mở lượt → ghi kết quả → đọc bảng cho M0_A/B/C với wave 12/25/18. Mỗi tài khoản chỉ thấy một dòng của chính mình và đều nhận hạng 1.
- Đã gửi wave 99 cho M0_A bằng nonce giả; server chấp nhận và lưu. Sau một lần khởi động server thử mới, điểm 99/25/18 vẫn tồn tại. SQLite thử có integrity `ok`.
- Tài liệu giao thức, trường request/response và kết luận thiết kế nằm ở `M0_TEST_20260924/SKY_PROTOCOL.md`; bài kiểm tra lặp lại nằm ở `sky_protocol_probe.py`.
- Python Playwright chưa có sẵn; không cài thêm ở bước khảo sát API. Kiểm tra giao diện hình ảnh sẽ thực hiện khi bắt đầu thay đổi frontend.
- Helper `with_server.py` để lại tiến trình con trên Windows. Đã xác định đúng hai tiến trình thử theo cổng/dòng lệnh và dừng chúng; cổng 8049 không còn nghe, server thật cổng 8029/PID 17160 vẫn chạy.
- Mã và save thật giữ nguyên hash so với mốc đầu. Chưa sửa lỗi Sky; bằng chứng này là đầu vào cho thiết kế và kiểm thử M2.

### 24/09/2026 — M0, lát ba: Cloud Garden, PvP và World Boss

- Trên tài khoản giả, Cloud `RANKING_GET` chỉ trả một người/hạng 1. Hai request `GAME_END` liên tiếp với cùng nonce giả, không mở lượt trước, đều thành công; Cloud Piece tăng 4245→4265→4285 và điểm lưu thành 400.
- Ba endpoint `PVP_2025` (bảng/vào trận/kết quả) đều trả `{}`. Ba endpoint `BOSS_2026` tương ứng cũng trả `{}` trong offline không có capture. Client mong đợi trường `STATE`, vì vậy hai chế độ chưa có hợp đồng server tối thiểu.
- Đã ghi request/response và trường client gửi vào `M0_TEST_20260924/OTHER_MODES_PROTOCOL.md`; bài dò lặp lại ở `remaining_protocol_probe.py`.
- Lần chạy mới dùng tiến trình server trực tiếp và `finally`, đã dừng sạch sau bài dò. Không cài Playwright và không thay đổi mã/save thật.
- M0 đã có: mốc phục hồi, môi trường tách biệt, dữ liệu thử nhiều tài khoản và bản đồ API thực tế cho bốn chế độ. Bước kế tiếp theo lộ trình là thiết kế tối thiểu nền phiên trận/bảng hạng SQLite và kiểm thử mong muốn cho Sky trước khi sửa production.
- Kiểm tra bàn giao M0: 7 artifact bắt buộc tồn tại; 2/2 bài dò biên dịch; SQLite thử integrity `ok` với state Sky 99/25/18 và Cloud score 400; `serve.py`/`offline_save.json` thật giữ nguyên hash; 4/4 tài liệu UTF-8/Markdown hợp lệ; cổng thử 8049 đã tắt và server thật 8029/PID 17160 vẫn chạy.

### 24/09/2026 — M1 lát đầu: bảng hạng Sky dùng chung trên SQLite

- Mục tiêu: cho nhiều tài khoản thấy cùng bảng Sky, lưu điểm bền qua restart, và chặn gửi lại cùng một kết quả.
- Đã thêm `sky_sessions(nonce,user_id,consumed,created_at)` và `sky_leaderboard(user_id,clear_wave,achieved_at)` vào `init_db()`; không thay đổi schema JSON.
- `enter_sky_game.php` tạo phiên SQLite và làm hết hiệu lực phiên Sky cũ của cùng tài khoản. `update_sky_result.php` yêu cầu đúng nonce chưa dùng, đánh dấu đã dùng trước khi lưu điểm. Điểm thấp hơn không hạ điểm cao nhất.
- `get_sky_ranking.php` đọc tối đa 50 dòng theo `clear_wave` giảm dần, thời điểm đạt tăng dần, rồi định danh tài khoản; trả đúng `ranking` và `my_ranking` cho tài khoản hiện tại.
- File kiểm thử: `test_sky_leaderboard.py` (đơn vị) và `M1_TEST_20260924/sky_shared_http_probe.py` (HTTP, restart, replay). Đã chạy `python -m unittest discover -v`, `python -m py_compile serve.py test_sky_leaderboard.py`, và probe HTTP; tất cả đều đạt. Probe dùng database/cổng tạm, không dùng dữ liệu thật.
- Giới hạn: tiến trình PID 17160 đang chạy JSON (`offline_save.json`), nên chưa thể thấy bảng hạng chung trong phiên chơi đang mở. Muốn bật thay đổi cần khởi động một phiên server với `--db` sau khi có kế hoạch chuyển dữ liệu; chưa tự khởi động lại để tránh làm gián đoạn người chơi.
- Bước tiếp theo: bổ sung bảng hạng Cloud hoặc chuyển sang PvP theo hợp đồng API đã ghi, sau đó lập kế hoạch chuyển server thật sang SQLite có backup và kiểm tra đăng nhập.

### 24/09/2026 — Cài Codex with ChatGPT

- Mục tiêu/phạm vi được yêu cầu: cài và cấu hình `Codex with ChatGPT` tự động, chỉ gọi người dùng khi cần đăng nhập/nhập mã xác thực.
- Đã xác nhận môi trường: Git có sẵn; Node.js `v24.18.0` đạt yêu cầu >=20; `cloudflared` ban đầu thiếu và đã cài bằng winget, bản `2026.9.1`; repo được clone vào `C:\Users\THE HUAN\codex-with-chatgpt`.
- Đã chạy `corepack pnpm install` và `corepack pnpm build` trong checkout; build TypeScript đạt.
- Đã cài skill vào `C:\Users\THE HUAN\.codex\skills\codex-with-chatgpt\SKILL.md` và cập nhật dòng checkout path đúng với máy hiện tại.
- Đã cấu hình kết nối cho workspace `busidol_offline` bằng địa chỉ tạm, bật Developer mode trong ChatGPT, tạo connector tên `Codex with ChatGPT · busidol_offline` và ghép cặp thành công. Không ghi pairing code vào tri thức vì mã ngắn hạn/nhạy cảm.
- Kiểm tra thực sự đã chạy: `c2c doctor -w C:\busidol_offline --json` báo Node, sandbox, workspace, bridge, MCP, OAuth và tunnel đều `ok`; ChatGPT đã gọi connector và trả về `C2C_WORKSPACE workspace_name: busidol_offline`.
- Session C2C đã lưu tại state cục bộ với URL chat kiểm thử và `conversationMode` là `long-chat`. Lệnh `c2c session --json` vẫn hiển thị mode Project mặc định cho workspace mới, nên khi dùng C2C về sau cần ưu tiên file session đã lưu hoặc chạy kiểm tra lại.
- Giới hạn: connector hiện dùng địa chỉ tạm; sau khi máy/Codex tắt mở lại, có thể cần sửa kết nối lại theo workflow của skill. Chưa tạo ChatGPT Project riêng vì yêu cầu hiện tại ưu tiên cài tự động và kiểm tra đọc file.

### 24/09/2026 — Nâng cấp RubyFarm và sửa đường dẫn sau khi chuyển thư mục

- Mục tiêu/phạm vi được yêu cầu: (1) nâng cấp trang `ELDORADO_WEB/rubyfarm.html`; (2) sửa các đường dẫn còn trỏ vị trí cũ sau khi chép dự án sang thư mục mới. Người dùng yêu cầu trình kế hoạch trước; kế hoạch đã chốt: RubyFarm = sửa lỗi + giao diện/UX (không thêm tính năng); vé máy phát = chỉ sửa chữ cho khớp server; gia cố `serve.py` cho đường dẫn tương đối; kiểm chứng bằng server tạm + mở trang thật.
- Đường dẫn: các launcher `.bat` (`CHOI_ANH`, `CHOI_BANBE`, `CHOI_BANBE_TUNNEL`, `CHOI_EM`, `CHOI_MOI`, `DOI_TAIKHOAN`, `ELDORADO_OFFLINE`, `ELDORADO_PROXY`, `KHOIDONG`, `AUTOCAPTURE`), cùng `autocapture.js`, `patch.py` và `_c` còn trỏ `C:\busidol_offline`. Đã đổi sang `%~dp0` (batch) và đường dẫn theo `__file__`/`BASE_DIR` (Python/Node).
- `serve.py`: thêm `_proj_path()` để `--save-file/--db/--log/--capture` dạng tương đối resolve theo thư mục project; dạng tuyệt đối giữ nguyên hành vi.
- RubyFarm — số liệu lấy từ server: `mywallet.php` trả thêm `cd` (cooldown giây) bên cạnh `cap`; trang đọc `W.cd`/`W.cap` thay cho số cứng "5 giây"/"300" trước đây; nhãn hạn mức ở sidebar và trang chủ đều lấy từ server.
- RubyFarm — chữ cho khớp thực tế: vé máy phát chỉ có nguồn miễn phí 3 vé/ngày, không bán bằng vàng (server từ chối mua bằng `{"STATE":"ERROR","msg":"daily only"}`); vé sudoku hết thì mua thêm bằng vàng. Ghi chú cũ "mua thêm trong Ví" cho genrep đã bỏ.
- RubyFarm — Sudoku hết phiên trước hạn: `serve.py` tính `ttl = max(900, thời lượng độ khó + 120)` với hằng `SUDOKU_CLAIM_GRACE` cho độ khó dài (20/25 phút).
- RubyFarm — giao diện/UX: HUD có nút "🎮 Về game", chip cảnh báo mất kết nối bấm được để thử lại, khối "yêu cầu vé" hiện trước khi vào game (đủ/không đủ vé, kèm nguồn vé), trạng thái đang tải và thử lại cho ví/điểm danh, chữ lỗi tiếng Việt rõ hơn, iframe game có khung và chiều cao hợp lý, vài chỉnh CSS cho màn nhỏ.
- Lỗi tìm thấy trong lúc kiểm chứng (đã sửa): (a) ô "⚡ Hôm nay kiếm" ở trang Ví hiện `NaN` vì `fmt()` nhận chuỗi — lỗi có từ bản gốc; (b) `retryAll()` cập nhật `CONN` sau khi `renderHud()` đã chạy nên chip mất kết nối không xuất hiện — chỉ lộ ra khi thử tắt/bật server thật.
- Kiểm tra đã chạy trên server tạm cổng 8039 với dữ liệu riêng, khởi động từ thư mục Temp để thử đường dẫn tương đối; thư mục tạm và tiến trình đã được dọn sau khi xong:
  - `python -m py_compile serve.py` đạt; trích script nhúng của `rubyfarm.html` và kiểm cú pháp bằng Node đạt (1 khối, ~38.000 ký tự).
  - Đường dẫn: chạy từ `C:\Users\THE HUAN\AppData\Local\Temp` với `--capture _verify_tmp/capture` tạo đúng thư mục trong project.
  - Sudoku: đặt `sudoku_session.ts` lùi 1.000 giây (quá mốc 900 cũ, trong hạn mới) → `sudoku_claim` độ khó expert trả `SUCCESS`, thưởng 50; lùi 2.000 giây → `ERROR no session` (hết hạn vẫn bị chặn).
  - Vé máy phát: mua vé genrep bị từ chối `daily only` — khớp chữ mới trên trang.
  - Trình duyệt thật: HUD hiện đúng hạn mức 500 và cooldown 3 giây; khối yêu cầu vé hiện đúng cả trạng thái đủ và không đủ vé; chơi game Trí nhớ bằng click thật đến hết lượt → cộng ruby vào ví, HUD tăng 62→70→88; nhánh chờ cooldown hiện "Chờ 2s…" và khoá nút.
  - Mất kết nối: tắt server → bấm nút "Mua" trên trang Ví → hiện chip "⚠️ Mất kết nối · Thử lại" và toast đúng; bật lại server → bấm chip → "Đã kết nối lại ✅", HUD tải lại, vẫn ở trang Ví.
  - Sau hai bản sửa cuối: nạp lại trang (bỏ cache), 7 trang đều không còn `NaN`; console trình duyệt không có thông báo lỗi.
- Giới hạn: (a) công cụ chụp ảnh của trình duyệt trong phiên báo `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE` nên **không có ảnh chụp màn hình**; bằng chứng là snapshot DOM và script đọc trạng thái trang; (b) mọi thao tác tiền/trận trong đợt này chỉ trên save tạm, không chạm save/database thật; (c) chưa thử trên thiết bị di động thật, chỉ thu nhỏ cửa sổ; (d) server thật cổng 8029 không chạy trong đợt này nên các thay đổi chưa được thấy trong phiên chơi thật.
- Việc còn lại: "Sudoku nhận thưởng chưa xác minh lời giải" và các lỗi bảo mật ở mục 6 (API tin `HOST_ID`, trang quản trị lộ khoá, autoplay ngày âm) vẫn chưa sửa. Bước tiếp theo đề xuất: người dùng chạy launcher mong muốn từ thư mục mới để xác nhận đường dẫn và trang RubyFarm trong môi trường chơi thật.

### 24/09/2026 — M5: redesign giao diện RubyFarm, 6 khu vực (chỉ lớp hiển thị)

- Mục tiêu/phạm vi được yêu cầu: theo đặc tả redesign riêng cho `ELDORADO_WEB/rubyfarm.html` — biến trang từ "dashboard mặc áo game" thành một màn hình game fantasy/Eldorado; **không đổi gameplay, API, save, database**. Người dùng đã chốt phương án "Redesign toàn bộ 6 khu vực". Chỉ một file được sửa: `ELDORADO_WEB/rubyfarm.html` (47.511 → 72.153 byte; chỗ dùng biến CSS 63 → 152; media query 2 → 6). Mốc `M0_BASELINE_20260924_014351/` chỉ đọc để đối chiếu, không sửa.
- Sidebar: logo + nhóm CHÍNH và nhóm MINI GAME, trạng thái active/hover rõ, chỉ báo giới hạn ≤30 / ≤20, vùng nav cuộn được khi màn thấp nhưng khối chân (ví ruby + hạn mức/ngày) luôn hiển thị.
- HUD trên: mỗi tài nguyên = icon + giá trị + màu nhận diện + khung + hover; chip "Ví ruby" nổi bật hơn (nhãn + số + "Hôm nay +N/cap"); "🎮 Về game" tách riêng bên phải; trạng thái mất kết nối là chip "⚠️ Mất kết nối · Thử lại" bấm được để chạy `retryAll()`.
- Hero: nền ảnh + lớp phủ, phân cấp tiêu đề, CTA chính "Điểm danh hôm nay" + CTA phụ "Rút ruby", điểm nhấn vàng.
- Thẻ mini game (phần quan trọng nhất): bỏ mũi tên ▶ trơ; mỗi thẻ trả lời đủ tên, icon, mô tả, phí, thưởng ruby, giới hạn, loại (Miễn phí · Vé ⚙️ · Vé 🧩), trạng thái và CTA "Chơi ngay ▶"; giới hạn/trạng thái lấy từ server (`cd`, `cap`, `tfree`); thẻ hết vé có lớp `.locked` + CTA xám; hover nâng nhẹ + viền vàng + bóng.
- Điểm danh: panel thưởng thật — "Đã điểm danh N/31 ngày", NGÀY n/31, quà hôm nay theo `rewards` của server, trạng thái đã nhận, dải 31 ô (đã nhận / hôm nay / chưa tới); không thêm dữ liệu mới ngoài server.
- Typography, hierarchy, responsive, a11y: một họ chữ cho cả trang kể cả nút/ô nhập, token `--fs-*`; 3 tầng ưu tiên (hero + ví ruby / mini game + điểm danh / giới hạn & chú thích); thêm `:focus-visible`, `prefers-reduced-motion`, breakpoint 1240/1024/640.
- Lỗi tìm thấy khi kiểm chứng, **đã sửa** (đều thuộc lớp hiển thị): (a) chữ trong nút/ô nhập rơi về Arial vì khối reset không kế thừa `font-family`; (b) ô nhập số lượng ở trang Quy đổi không cập nhật ước tính khi gõ — lỗi có từ bản gốc, thấy cả ở baseline dòng 802 — đã thêm `oninput`; (c) trang Quy đổi lồng `.homeblk` nên bị chia 2 cột chật trong thẻ 760px — làm phẳng và thêm nhánh lỗi "không đọc được số dư/tỉ giá" kèm nút "Thử lại"; (d) `.bals .rate` chỉ chiếm 1 ô lưới lúc đang tải — cho trải hết hàng; (e) mất kết nối giữa phiên không hiện gì khi trang còn dữ liệu cũ (`api()` nuốt lỗi mạng, các trang chỉ đọc lại khi cache trống) — `loadWallet()`/`loadCheckin()` nay gọi `netFail(true)`: chỉ bật chip, không thêm toast trùng.
- Lỗi chỉ **ghi nhận, không sửa** (ngoài phạm vi): dòng mới ở bảng mục 6 — hạn mức trong ngày hiện số của hôm trước vào đầu ngày mới, do server sang ngày muộn.
- Kiểm tra đã chạy trên server tạm cổng **8041** với **bản sao** save `_REG_TEST/rf_test_save.json`; server thật cổng 8029 của người dùng đang không chạy và không bị chạm:
  - Cú pháp: trích script nhúng (41.286 ký tự) → `node --check` đạt. Kiểm tra tĩnh: 0 lớp CSS được dùng mà chưa định nghĩa; 48/48 tham chiếu `$("id")` khớp id có thật; khoá vé trong save thật là `tickets.{generator,sudoku}`, đúng như `serve.py` đọc.
  - Trình duyệt thật: 8 thẻ mini game hiện đúng số liệu server; trang Sửa máy phát hiện "đang có 9 vé" (đủ) và "⛔ đang có 0 vé" (hết); mua vé sudoku 9→11; điểm danh 2/31→3/31 rồi panel "đã điểm danh"; thưởng game "+3 ruby 🎉" kèm cooldown "Chờ 1s…" khoá nút; trang Quy đổi cập nhật ước tính khi gõ; nhánh lỗi rút ruby; HUD đổi đúng sau mỗi thao tác.
  - Trạng thái hết: đặt bản sao save về 0 vé và chạm hạn mức → 6 thẻ "Hết hạn mức hôm nay — mai chơi tiếp", Sửa máy phát "Hết vé — mai được tặng tiếp", Sudoku "Hết vé — mua thêm trong Ví"; CTA đổi từ gradient xanh sang xám (đo computed style); thẻ miễn phí không bị gắn `locked`.
  - Mất kết nối: tắt server → trang Quy đổi hiện "⚠️ Chưa đọc được số dư/tỉ giá" + chip "⚠️ Mất kết nối · Thử lại" + toast lỗi; bật lại server → bấm chip → "Đã kết nối lại ✅", chip biến mất, số dư tải lại, 14 request đều 200; console chỉ có 1 dòng `ERR_CONNECTION_REFUSED` đúng lúc cố ý tắt server, không có lỗi JS.
  - Kích thước màn hình: đo trong iframe cùng origin ở 1920×1080, 1600×900, 1366×768, 1280×720, 1024×768, 768×900 → không tràn ngang, sidebar dính 252px từ 1024 trở lên và xếp dọc ở 768, HUD cao 77→159px (biết xuống dòng), lưới thẻ 2–3 cột, nav cuộn được nhưng khối chân vẫn hiện, không cắt chữ ở 1024/768.
  - Khả năng truy cập (đo, không phải ảnh): tương phản chữ/nền thấp nhất đo được 7,65; 0 vùng bấm thấp hơn 32px. Quét `NaN`/`undefined`/`[object`/`null` trên 4 trang (chủ, điểm danh, ví, quy đổi): không có.
- Giới hạn: (a) công cụ chụp ảnh của trình duyệt vẫn báo `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE` nên **không có ảnh chụp màn hình** — bằng chứng là DOM và số đo computed style; (b) cửa sổ trình duyệt thật chỉ 738×570 @dpr 1.25 nên phần responsive đo bằng iframe cùng origin, không phải kéo giãn cửa sổ thật; (c) mọi thao tác tiền/vé/trận chỉ trên bản sao save trong `_REG_TEST/`, không ghi vào `offline_save.json`/database thật; (d) chưa thử trên thiết bị di động thật; (e) server thật cổng 8029 không chạy trong đợt này nên giao diện mới chưa được nhìn trong phiên chơi thật.
- Việc còn lại và bước tiếp theo: người dùng chạy launcher mong muốn (`KHOIDONG.bat`, …) rồi mở lại RubyFarm để xác nhận trong môi trường chơi thật; các lỗi bảo mật/backlog ở mục 6 vẫn nguyên vì không thuộc phạm vi redesign; `_REG_TEST/` chỉ là artefact kiểm thử, xoá được khi không cần.

### 24/09/2026 — Đóng gói `file_A/` để AI bên ngoài đọc hiểu dự án

- Mục tiêu/phạm vi được yêu cầu: tạo thư mục `file_A` chứa thông tin quan trọng để một AI khác (ChatGPT+) đọc và hiểu sâu kiến trúc + mã nguồn; chỉ giữ HTML/CSS/JS/Python, tài liệu `.md`, test, launcher, config và vài asset đại diện; bỏ qua asset nặng và các mục sao lưu.
- Đã làm: sao chép có chọn lọc **81 file / 7,9 MB** vào `file_A/`, giữ nguyên cấu trúc đường dẫn của dự án để đối chiếu được với tài liệu; thêm `file_A/README_FILE_A.md` làm chỉ mục (thứ tự đọc, bảng cấu trúc, danh sách đã loại trừ, lưu ý kỹ thuật khi đọc).
- Nội dung đã đưa vào: `serve.py`; toàn bộ tài liệu `.md` gốc và 2 tài liệu protocol trong `M0_TEST_20260924/`; 6 trang HTML (RubyFarm, Quy đổi, 2 minigame, khung trang game gốc, harness test); JS client (`javascript/`, `javascript_min/` gồm bundle 6,5 MB, `javascript_leveling/`, `GoogleAnalytics/`, `source_20240722/`, `KR_INPUT/`); 10 launcher `.bat` + `get_tunnel_url.ps1`; test và công cụ (`test_*.py`, `verify_convert*`, `_rf_check.js`, `autocapture.js`, `walk.js`, `sweep.js`, `stage.js`, `pause.js`, `evalstate.js`, `console.js`, `shot.js`, `jsx.js`, `patch.py`, `resedit.py`, `warmup.py`, `inspect3.py`, `tao_huando.py`); 9 mẫu protocol trong `capture/` (đã xem nội dung, không có dữ liệu tài khoản); config `.gitignore`, `config.yml`; 7 asset đại diện (`1_mainmenu/mm_bg.jpg` + 6 ảnh UI nhỏ trong `0_common/`).
- Đã loại trừ: asset nặng (`image/` ~38 MB, `sound/`, `source_20240722/image|sound` ~214 MB), `cloudflared.exe`; mọi bản sao lưu (`archive/`, `M0_BASELINE_20260924_014351/`, `serve - Copy.py`, `ACCT_*`, `TRAI_TAIKHOAN_CU_GIU_LAI`, `*_BACKUP_*`, `*.bak`); log, `__pycache__/`, `cls_pycdc_serve.marshal`, `_c`; và **toàn bộ dữ liệu riêng tư** (`busidol.db`, `busidol_banbe.db`, `m0_test.db`, `offline_save.json`, `save_*.json`, bản sao save trong `_REG_TEST/`) — theo quy tắc không đưa hash mật khẩu / nội dung save người chơi vào tài liệu chia sẻ.
- Kiểm tra đã chạy: đếm lại 81 file / 7,9 MB; đối chiếu danh sách 10 launcher `.bat` ở thư mục gốc với `file_A` (đủ 10, không thiếu file nào); quét loại trừ `*.db`, `*.log`, `*.bak`, `*.pyc`, `save_*.json`, `cloudflared*`, `*- Copy*` → rỗng; xác nhận 14 file quan trọng có mặt; `rubyfarm.html` trong `file_A` đúng 72.153 byte như bản gốc.
- Giới hạn: `file_A` **không chạy được đầy đủ** vì thiếu asset, database và save — chỉ dùng để đọc hiểu mã; chưa thử chạy server từ trong `file_A`.
- Việc còn lại: nếu cần `file_A` chạy được thì phải bổ sung asset và tạo save trống; `file_A/` hiện chưa được git theo tracking.

### 2026-09-26 — Hard mode: bỏ mở sẵn toàn bộ map, khóa chuyển màn tuần tự

- Mục tiêu/phạm vi được yêu cầu: hard mode đang mở thoải mái, phải sửa để đi từng màn. Người dùng đồng ý cả hai việc: (1) đặt tiến độ account về màn 1, (2) chặn POST tự mở màn.
- Phát hiện mới và bằng chứng (đọc từ `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js`):
  - `MAX_STAGE_NUM=300`, `MAX_STAGE_NUM_HARD=200`; `CUR_HARD_STAGE_NUM` mặc định `-1`.
  - `STORAGE.parse_server_hard_mode_data(raw)`: `CUR_HARD_STAGE_NUM=Number(t[0])`, `HARD_MODE_JEWEL=t[1]`.
  - `STORAGE.pass_stage_hard(n)`: `t = (CUR==n) ? 0 : 1; if t==0 && n<=200 → CUR++`. Client chỉ tăng đúng 1 màn khi clear đúng màn kế tiếp → client vốn đã chặt tuần tự, lỗi nằm ở server.
  - `S_SELECTSTAGE_HARD.set_maxfocus`: `200 <= CUR` → `maxfocus=20` (mở hết 20 trang × 10 màn). Nên mốc "mở hết" là 201, không phải 200.
  - `S_SELECTMAP.stage201_in_check()` yêu cầu `CUR_HARD_STAGE_NUM==201`; `stage201_in_check_jewel()` yêu cầu đủ 10 viên. Đây là cổng vào màn đặc biệt 201+.
  - `S_STAGECLEAR.hardmode_get_jewel`: viên jewel thứ i được cấp khi `stage%20==0` (màn 20,40,…,200) → tổng 10 viên, **tự kiếm lại được**.
- Quyết định đã chốt:
  - Save mới seed `1||0,0,0,0,0,0,0,0,0,0` thay vì `201||...`.
  - `STAGE_DATA` chỉ được nhận khi bằng màn hiện tại (replay) hoặc đúng +1 (clear thật). Nhảy lớn hơn bị từ chối **và không ghi gì cả** — nếu vẫn ghi, một POST giả vẫn xoá được list jewel.
  - `JEWEL_DATA` vẫn nhận từ client khi màn hợp lệ (client là nguồn chân lý cho jewel khi clear).
  - Account `HUANDO` đặt stage 201 → 1 nhưng **giữ nguyên 10 jewel**; xoá jewel sẽ bắt chơi lại 200 màn, vượt ngoài phạm vi yêu cầu.
  - Chưa thêm kiểm tra jewel theo mốc `stage >= 20*i`. Không cần cho mục tiêu này vì cổng 201+ vẫn cần stage 201, mà stage 201 không thể đạt ngoài 200 clear thật.
- File đã thay đổi: `serve.py` (hằng `ELDORADO_HARD_FIRST_STAGE/ALL_OPEN/JEWEL_DEFAULT`, `_eldorado_hard_parse`, `_eldorado_hard_clamp_progress`, `_eldorado_hard_apply_claim`, template `cnm_exist`, 2 handler hardmode); `TESTS/test_eldorado_hard_mode.py` (mới, 12 test); `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md`.
- Kiểm tra đã chạy:
  - `python -m unittest` toàn bộ `TESTS/test_*.py`: **101 test OK** (89 cũ + 12 mới).
  - Test end-to-end trong process trên DB tạm, đúng chuỗi client gửi: seed mới ra `1||...`; forge `201` và forge `100` đều bị giữ nguyên stage **và** không đổi jewel; clear lần lượt `2,3,4,5,6,7` tiến đúng từng màn; `STAGE_DATA=-9` và `STAGE_DATA=abc` không làm hỏng save.
  - Bảo toàn dữ liệu: sao lưu `BACKUP_HARDMODE_20260926_230116/` (busidol.db + serve.py.bak) trước khi sửa save.
- Giới hạn:
  - Test e2e phải trỏ **cả** `serve.DB_FILE` lẫn `serve.DB_CONN` sang DB tạm. `DB_CONN` mở lúc import theo tham số CLI; chỉ đổi `DB_FILE` khiến `db_load_save` trả `None` → đọc rỗng và ghi im lặng, test thành vô nghĩa. Lần chạy đầu đã dính lỗi này; DB thật không bị đổi vì `DB_CONN` vẫn là `None` nên mọi ghi đều no-op, đã kiểm lại `HUANDO` còn nguyên.
  - Chưa thử bằng trình duyệt thật. Server đang chạy vẫn là tiến trình cũ (khởi động 21:17:53) nên **cần người dùng tự restart** mới nạp code mới.
- Việc còn lại và bước tiếp theo: người dùng restart server, vào Hard mode xác nhận map chỉ mở tới màn đang chơi; nếu muốn siết jewel nữa thì thêm kiểm tra `jewel_i=1 ⇒ stage>=20*i`.

### 2026-09-26 — Giảm quà mail: bỏ gift mult, vàng 100k / ruby 250 / bp 50

- Mục tiêu/phạm vi được yêu cầu: tắt gift mult của mail, mỗi lần chỉ ~100k vàng; `OFFLINE GIFT` cũng 100k vàng, ruby 250, bp 50.
- Đã xác nhận trước khi sửa (đọc mã, không suy đoán):
  - Có **hai** quà qua thư dễ nhầm. `MAILBOX_GIFTS` (serve.py, khối mailbox) là **daily mail** lặp lại 1 lần/ngày: trước đây GOLD 1.000.000 / RUBY 500 / BP 200 nhân `GIFT_MULT`. `mailbox_ensure_offline_gift` là `OFFLINE GIFT` **một lần**: GOLD 200.000 / RUBY 500 / BP 1500 + 3 nhân vật (CHAR 96, 97, 99). Người dùng nói "500 ruby 200 bp" → chỉ `MAILBOX_GIFTS`.
  - Ngày của daily mail lấy bằng `time.strftime("%Y%m%d")` — **giờ máy**, dù tài liệu cũ ghi UTC.
  - Cả hai hàm `mailbox_ensure_*` đều tự gọi `store_save()`, rồi handler claim lại ghi thêm một lần nữa. Thừa nhưng không sai; chưa sửa.
- Quyết định đã chốt:
  - `MAILBOX_GIFTS` → `("GOLD","100000"), ("RUBY","250"), ("BP","50")`.
  - `OFFLINE GIFT` → cùng bộ số trên; **giữ nguyên 3 CHAR** vì người dùng không nhắc tới nhân vật.
  - Xoá hẳn `--gift-mult` + hằng `GIFT_MULT`. Lý do: nó chỉ dùng cho daily mail, không launcher `.bat` nào truyền cờ này; giữ lại sẽ là cờ chết âm thầm — người dùng tưởng còn nhân.
  - **Không** đụng `CHECKIN_REWARDS` (REWARD_MULT=5). Đó là quà check-in 28 ngày, grant thẳng vào account, không qua thư — khác hệ thống, người dùng không yêu cầu.
- File đã thay đổi: `serve.py` (`MAILBOX_GIFTS`, danh sách `gifts` trong `mailbox_ensure_offline_gift`, `mailbox_ensure_daily_mail`, argparse `--gift-mult`, `global GIFT_MULT`); `TESTS/test_mail_gifts.py` (mới, 6 test); `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md`.
- Kiểm tra đã chạy:
  - `python -m unittest` toàn bộ `TESTS/test_*.py`: **107 test OK** (101 cũ + 6 mới).
  - Test post thật vào DB tạm: daily mail ra đúng `{GOLD 100000, RUBY 250, BP 50}` không nhân; SN vẫn parse được bằng `int()`; `OFFLINE GIFT` ra đúng bộ số mới và giữ đủ CHAR 96/97/99.
  - Xác nhận DB thật không đổi sau khi chạy test.
- Giới hạn / điểm cần người dùng quyết:
  - **`OFFLINE GIFT` là một lần** (`OFFLINE_GIFT_STAMP = "20260921"`) và **mọi account đã có** stamp trong `busidol.db`. Sửa danh sách `gifts` chỉ có tác dụng với account chưa từng nhận; với các account hiện có, code này là nhánh chết.
  - Hai account vẫn còn thư `OFFLINE GIFT` **chưa claim** ở giá trị cũ: `ELDORADO_OFFLINE_0001` (6 thư) và `testuser1` (7 thư, gồm 1 thư DAILY ATTENDANCE). Claim là nhận đúng 200.000/500/1500. Chưa sửa vì đụng dữ liệu người chơi; cần người dùng đồng ý mới đồng bộ giá trị.
  - `ELDORADO_OFFLINE_0001` có `last_gift_date=20260924`, nên khi mở mailbox sẽ post daily mail mới với giá trị mới ngay.
  - Chưa thử bằng trình duyệt thật; server đang chạy vẫn là tiến trình cũ nên cần người dùng tự restart.
- Việc còn lại và bước tiếp theo: người dùng restart server; quyết định có đồng bộ 2 account trên sang giá trị mới không.

### 2026-09-26 — Bỏ 2 nhân vật kèm quà, đồng bộ 2 account còn thư cũ

- Mục tiêu/phạm vi được yêu cầu: bỏ 2 nhân vật có số lớn nhất trong 3 nhân vật tặng kèm (`96, 97, 99`); đồng bộ giá trị quà cho 2 account còn thư cũ.
- Quyết định đã chốt: giữ lại **CHAR 96** (số nhỏ nhất), bỏ **97 và 99** — hai nhân vật mạnh nhất trong bộ ba.
- Đã xác nhận không có hệ thống quà-acc-mới thứ hai: `cnm_exist` chỉ là template boot, `add_account` chỉ insert dòng `accounts`, `_norm_save` không set default. `OFFLINE GIFT` **chính là** quà tạo acc (comment serve.py gọi là "One-time offline welcome batch").
- File đã thay đổi: `serve.py` (`OFFLINE_GIFT_CHARS` → `(96,)`); `TESTS/test_mail_gifts.py` (test CHAR đổi từ `{96,97,99}` sang `{96}`).
- Dữ liệu đã sửa (sao lưu `BACKUP_MAILSYNC_20260926_092017/busidol.db` trước khi ghi):
  - `ELDORADO_OFFLINE_0001`: 6 thư → 4 thư. GOLD 200000→100000, RUBY 500→250, BP 1500→50, xoá 2 thư CHAR 97 và 99.
  - `testuser1`: 7 thư → 5 thư, cùng thay đổi. Thư `DAILY ATTENDANCE` (GOLD 100000) **không** đụng vì thuộc hệ check-in, không phải `OFFLINE GIFT`.
  - `HUAN` có 7 thư `First Clear Reward` (phần thưởng clear màn) — không phải quà tặng, không đụng.
- Kiểm tra đã chạy:
  - `python -m unittest` toàn bộ `TESTS/test_*.py`: **107 test OK**.
  - Quét lại `busidol.db` sau khi sửa: không còn thư `OFFLINE GIFT` nào mang giá trị cũ hay CHAR 97/99 (đếm 0).
- Giới hạn:
  - Account đã claim quà rồi (`HUANDO`, `TEN`, `ctus`, `huando`, `huando2007`) không còn thư nào để sửa; nếu họ đã nhận CHAR 97/99 thì vẫn giữ trong `DATA2`. Muốn thu hồi thì phải xoá nhân vật khỏi save — **chưa làm, cần người dùng đồng ý**.
  - 8 account có stamp `20260921` → nhánh seed là chết với họ; chỉ `tusiubel`, `BM`, `EM`, `MOI` và account tạo sau mới nhận bộ số mới.
  - Chưa thử bằng trình duyệt; server đang chạy vẫn là tiến trình cũ, cần người dùng tự restart.

### 2026-09-26 — Thưởng Quest x10 Ruby + Gold

- Mục tiêu/phạm vi được yêu cầu: nhân x10 phần thưởng ruby và vàng của hệ Quest.
- Phát hiện (đọc `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js`):
  - Bảng thưởng **không nằm ở server**. `cnm_update_quest_to_server.php` chỉ lưu blob tiến độ (`status` + `arrive`), không có giá trị thưởng. Toàn bộ giá trị nằm ở bảng global `QUEST[i].r_ruby` / `r_gold` hardcode trong bundle.
  - **Client tự cộng thưởng khi bấm nhận**: `t += QUEST[n].r_ruby[r]; i += QUEST[n].r_gold[r]`. Nhân ở server vô nghĩa — phải nhân ở bảng phía client.
  - `QUEST_NUM = 11`.
  - **Bẫy quan trọng**: min.js gán LẠI `QUEST[1]`, `QUEST[4]`, `QUEST[9]` ở cuối bundle, tức **sau** mảng `QUEST=[{...}]`. Giá trị hiệu lực là bản gán sau (ví dụ quest 1 vàng: mảng gốc `500..9e3`, hiệu lực `300,500,700,900,1100,1500,2e3,0,0,0`).
  - Những quest không thuộc `QUEST_NUM`/`_MIN` bị ảnh hưởng: không có; cả 11 quest đều trong bảng.
  - `a[0]` của mọi mảng là sentinel `-1`; code chỉ đọc từ chỉ số 1. Giá trị `0` phải giữ nguyên vì UI dùng `r_gold[n]==0` để ẩn icon.
- Quyết định đã chốt:
  - **Không sửa min.js** — đúng quy ước dự án (comment `index__mobile.html:299`: "Không sửa min.js -> override runtime").
  - Thêm khối `<script>` mới trong `ELDORADO_WEB/source_20240722/index__mobile.html`, đặt cạnh các override runtime sẵn có (item gacha, autoplay).
  - Dùng marker **trên từng object** (`__eldQuestX10`) thay vì một cờ chung, để thứ tự load không quan trọng: object nào chưa nhân thì nhân. Nếu dùng cờ chung thì 3 quest bị gán lại sẽ thoát khỏi vòng nhân và giữ số gốc.
  - Vẫn chừa `setInterval(..., 500)` + chạy thử ngay, đúng như hai override sẵn có; `loader.js` nạp bundle sau `window.onload` nên lúc script inline chạy thì `window.QUEST` chưa tồn tại.
- File đã thay đổi: `ELDORADO_WEB/source_20240722/index__mobile.html` (khối script mới); `TESTS/test_quest_reward_x10.mjs` (mới, 3 tình huống).
- Kiểm tra đã chạy:
  - `node TESTS/test_quest_reward_x10.mjs` → OK. Ba tình huống: (1) nhân đúng 1 lần, sentinel `-1` và giá trị `0` giữ nguyên; (2) min.js gán lại `QUEST[1]` **sau** khi patch đã chạy → object mới vẫn được nhân; (3) 5 vòng poll sau không nhân trùng.
  - `python -m unittest` toàn bộ `TESTS/test_*.py`: **107 test OK**.
  - `node --check game_asset_preload.js` OK.
  - Bóc số trực tiếp từ bundle (kể cả 3 bản gán lại) để đối chiếu: tổng sau khi x10 là **1.510 ruby** và **2.395.000 gold** cho toàn bộ 11 quest.
- Giới hạn:
  - Chỉ nhân `r_ruby` và `r_gold`. Quest không có loại thưởng khác trong bảng này, nhưng nếu sau này thêm mảng mới (ví d. `r_item`) thì phải thêm vào danh sách key trong patch.
  - Nếu tài khoản đang dùng gói (`glo.package.get_is_subscribe()=="yes"` hoặc cloud package) thì client còn nhân thêm `S_QUESTDETAIL.sub_mul` / `cloud_mul`; offline không có gói nên không ảnh hưởng.
  - Thay đổi ở HTML nên trình duyệt phải tải lại trang (F5). **Không** cần restart server.
  - Chưa thử bằng trình duyệt thật; test mô phỏng bằng `node:vm` với bảng `QUEST` dựng lại đúng số liệu bundle.

### 2026-09-26 — Hỗ trợ tiếng Việt

- Mục tiêu/phạm vi được yêu cầu: game chạy bằng tiếng Việt. Người dùng chọn phương án **mặc định tiếng Việt một lần** (không bật lại màn hình chọn ngôn ngữ gốc).
- Phát hiện — **không cần dịch gì cả**:
  - Bundle đã có `LANG={KOREA:1,ENGLISH:2,VIETNAM:3,SPAIN:4,RUSSIA:5,PORTUGAL:6}` và `LANG.init()` dispatch `switch(USER.lang)` sang `LANG.setVIETNAM()`.
  - Bản dịch tiếng Việt **đầy đủ nhất trong 6 ngôn ngữ**: `LANG.setVIETNAM()` gán **2299** khoá `TXT.*`, nhiều hơn English (2297), thiếu **0** so với English và 0 so với Korean. Hai khoá này là của riêng VI.
  - Menu Settings đã có sẵn "Tiếng Việt" trong `S_SETTING_LANG`.
- Nguyên nhân game vẫn ra tiếng Anh:
  - Màn hình chọn ngôn ngữ bị cờ tắt: `glo.APP_FEATURE.LANG_SELECT && (S_LANG_SELECT.is_need_lang_select() || STORAGE.data1.chul_num==0) ? ...`. `LANG_SELECT` mặc định `0` và `serve.py` không bật, nên nhánh này không bao giờ chạy.
  - Client suy ra ngôn ngữ từ save: `USER.lang = STORAGE.data1.lang = LANG.get_code_by_data1(t[3], LANG.ENGLISH)`. Đã kiểm tra DB thật: **`DATA1[3]` của mọi tài khoản đang lưu `"2"`** (English) — vì chưa ai chọn, save nhận luôn giá trị fallback.
  - Server **không** ép ngôn ngữ: không có `hasOwnProperty("LANG")` trong bất kỳ response nào, `serve.py` không gửi field `LANG`.
  - `apply_only_ko_en_lang()` không chạy: cần `gTARGET_PLATFORM===LGWEBOS_TV` + `ONLY_KO_EN`; ta là ENTRIX_CNM/PC. Nên menu không bị cắt còn 2 ngôn ngữ.
  - `apply_only_ko_lang()` chỉ áp cho `gPLATFORM.SKB` (TV Samsung).
- Quyết định đã chốt:
  - **Không bật `LANG_SELECT`**: `S_LANG_SELECT.make_screen()` vẽ div cứng chuẩn TV 1280x720, sẽ lệch layout trên PC.
  - Ép `LANG.VIETNAM` **đúng một lần** rồi thôi, gắn cờ `localStorage["eldorado_default_vi_done"]`, để người chơi tự đổi trong Settings mà không bị ghi đè.
  - **Sửa tận gốc thay vì giành quyền với vòng lặp**: bọc `LANG.get_code_by_data1` để nó trả `VIETNAM` khi patch còn active. Nhờ vậy login không bao giờ ghi đè về English, nên **UI không bị kẹt chuỗi English** sau khi đã dựng. Khi hết active, hàm trở lại trong suốt.
  - Vẫn giữ vòng lặp 500ms và chỉ chốt sau khi `USER.lang` ổn định 3 giây (`idle >= 6`), vì `loader.js` nạp bundle **sau** `window.onload`. Nếu `USER.lang` bị đổi sang ngôn ngữ khác (dấu hiệu người chơi tự chọn) thì `idle` reset — không giành quyền.
- File đã thay đổi:
  - `ELDORADO_WEB/source_20240722/index__mobile.html`: khối script mới "Mặc định tiếng Việt".
  - `serve.py`: hằng `ELDORADO_LANG_VIETNAM = 3` và helper `_eldorado_lang_of(data1_fields)`; thay 2 chỗ hardcode `"lang": 2` trong `sky_2026/get_sky_ranking.php` bằng `_eldorado_lang_of(...)`.
  - `TESTS/test_lang_vietnamese_default.mjs` (mới, 7 tình huống), `TESTS/test_eldorado_lang.py` (mới, 5 test).
- Vì sao sửa `lang` trong ranking: `get_sky_ranking.php` gửi cứng `"lang": 2` cho từng dòng bảng xếp hạng Sky. `lang` đó chỉ dùng để vẽ cờ hiệu ngôn ngữ, **không** nạp vào `USER.lang` (đã xác minh), nên nó không gây revert — nhưng để cứng English thì bảng xếp hạng hiện sai ngôn ngữ cho người chơi Việt. Nay đọc từ `DATA1[3]` như client.
- Kiểm tra đã chạy:
  - `node TESTS/test_lang_vietnamese_default.mjs` → OK, 7 tình huống: (1) lần tải đầu ép ngay; (2) login ghi đè English sau đó thì kéo lại được, `LANG.init()` chạy lại, chốt sau 3s ổn định; (3) lần tải sau tôn trọng lựa chọn của người chơi, không gọi `LANG.init()` lần nào nữa, có `clearInterval`; (4) người chơi đổi sang Hàn giữa chừng thì `idle` reset, không chốt; (5) `localStorage` bị chặn thì không crash; (6) hàm bọc trả `3` khi save rỗng **và** khi save đang lưu `2`, rồi trở lại trong suốt sau khi chốt; (7) lần tải sau đọc ngôn ngữ từ save.
  - `python -m unittest` toàn bộ `TESTS/test_*.py`: **112 test OK** (107 trước đó + 5 mới).
  - `node TESTS/test_quest_reward_x10.mjs` OK, `node --check game_asset_preload.js` OK, `ast.parse(serve.py)` OK.
- Giới hạn:
  - **Cần F5 là đủ, nhưng phần `serve.py` (`get_sky_ranking.php`) cần restart server** mới có hiệu lực. Không tự restart.
  - Cờ `eldorado_default_vi_done` lưu theo profile trình duyệt. Mở cửa sổ ẩn danh thì cờ mất → mỗi lần mở lại vẫn ép Viet (vẫn đúng ý, chỉ là không "một lần").
  - Cạnh tranh với lần ghi save đầu tiên: patch gán `STORAGE.data1.lang = 3` ngay khi bám được bundle, nên save đầu tiên của phiên đó mang `3`. Nếu đóng game **trước** lần ghi save đầu tiên thì save vẫn là `2` và lần tải sau rơi về English — sửa được bằng 1 cú bấm trong Settings (đường dẫn này hoạt động bình thường, không qua cờ `LANG_SELECT`).
  - Chuỗi không thuộc `TXT.*` (ví dụ tên nhân vật trong `CHAR_OUR_TEAM` lấy từ `TXT[...]`) đã được `LANG.init()` xử lý; tên riêng của người chơi thì không dịch, đúng như bản gốc.
  - Chưa thử bằng trình duyệt thật.

### 2026-09-26 — Sửa lỗi chữ khó đọc (mojibake double-encode UTF-8)

- Mục tiêu/phạm vi được yêu cầu: người dùng báo "có tiếng Việt đấy nhưng lỗi font chữ rất khó đọc".
- **Phát hiện quan trọng: không phải lỗi font.** Toàn bộ văn bản non-ASCII trong bundle bị **double-encode UTF-8**:
  - Cách lưu sai: byte gốc → giải mã latin-1/cp1252 → mã hoá lại UTF-8.
  - Hệ quả: `HTML` khai báo `charset=utf-8` nên trình duyệt hiện mojibake.
  - Byte thô đã kiểm: `"Deck phòng thủ"` bị lưu thành `44 65 63 6b ... c3 83 c2 b2` (`c3 83` = UTF-8 của `Ã`).
  - Chuỗi hiện ra: `Deck phÃ²ng thá»§`; đúng ra phải là `Deck phòng thủ`.
- Về font (đã kiểm để loại trừ):
  - `Main.load_font()` nạp `SERVER_URL + "font/MuJeogHaeByeongBold.ttf"`, rồi gán `document.body.style.fontFamily = "'MuJeogHaeByeongBold','NanumGothicBold',sans-serif"`.
  - `SERVER_URL=""` nên url là `font/MuJeogHaeByeongBold.ttf`; **file này không tồn tại** trong dự án (`font/`, `ELDORADO_WEB/font/`, `img/font/`, `images/font/` đều không có).
  - `@font-face` 404 → rơi về `sans-serif` của hệ điều hành, vẫn đủ dấu tiếng Việt. Nên **chữ khó đọc là do ký tự sai, không phải thiếu font**. Không thêm font mới (xem "Giới hạn").
  - Văn bản hiển thị bằng **DOM div + CSS**, không phải canvas: không có `fillText`/`strokeText`/`ctx.font`; game dùng `getComputedStyle` để đo `fontSize`/`lineHeight`/`fontFamily` (544 chỗ `util_draw_text`).
- Phạm vi hỏng rộng hơn tiếng Việt — đã đo toàn bộ:
  | Ngôn ngữ | chuỗi non-ASCII | sửa được |
  |---|---|---|
  | Korean | 2207 | 2207 |
  | Vietnam | 1105 | 1105 |
  | Spain | 825 | 825 |
  | Portugal | 967 | 967 |
  - 0 chuỗi hỏng byte, 0 ký tự C1 sót lại. **Tiếng Hàn cũng đang hỏng cùng kiểu** — chỉ là bản mặc định là English nên không thấy.
- Quyết định đã chốt:
  - Sửa tận gốc bằng `latin-1 → utf-8`: lấy mã ký tự của chuỗi rồi giải mã như UTF-8 bằng `TextDecoder("utf-8",{fatal:true})`. `fatal:true` loại chuỗi không phải mojibake (byte không hợp lệ) thay vì sinh ký tự thay thế.
  - Bỏ guard chặn khoảng C1 (`\u0080-\u009f`): mojibake của `’`, `“`, `–` rơi đúng vào khoảng đó nên guard sẽ **bỏ sót** các chuỗi đó. `fatal:true` đã đủ làm lưới an toàn.
  - Chống sửa hai lần **không cần cờ đánh dấu**: móc vào `LANG.init()` — sau mỗi lần init, `TXT` lại đầy giá trị mojibake mới, nên sửa đúng một lần mỗi lần là chuẩn. Chuỗi đã sửa có dấu tổ hợp (>U+00FF) hoặc byte không hợp lệ nên `repair()` trả về nguyên bản, tự idempotent.
  - `S_SETTING_LANG` cũng sửa (1 lần, có cờ `__eldFixed` vì đây là mảng cố định không được nạp lại).
- File đã thay đổi:
  - `ELDORADO_WEB/source_20240722/index__mobile.html`: khối script mới "Sửa lỗi double-encode UTF-8".
  - `TESTS/test_txt_mojibake_fix.mjs` (mới, 6 nhóm tình huống).
- Đính chính một điểm từ mục trên: `S_SETTING_LANG` **có 6 mục** (kèm "Tiếng Việt") ở khai báo `@2148034`. Ngoài ra còn một `S_SETTING_LANG=[2 mục]` tại `@375559` nhưng đó là **thân hàm** `apply_only_ko_en_lang`, chỉ chạy khi `is_only_ko_en_lang()` đúng (webOS TV) — ta là ENTRIX_CNM/PC nên không có hiệu lực.
- Kiểm tra đã chạy:
  - `node TESTS/test_txt_mojibake_fix.mjs` → OK. Chuỗi thật lấy từ bundle, không chế tay. 6 nhóm: (1) tiếng Việt sửa đúng; (2) **tiếng Hàn** sửa đúng; (3) ASCII giữ nguyên; (4) chuỗi đã có Unicode thật (`Tiếng Việt`, `日本語`, emoji) không bị đụng; (5) chạy 6 lần vẫn ra kết quả như nhau (idempotent); (6) hook `LANG.init` — đổi ngôn ngữ sau vẫn được sửa, `LANG.init` gọc vẫn chạy, menu `S_SETTING_LANG` sửa đủ 6 mục.
  - Đo diện rộng trên bundle: 1105/1105 chuỗi tiếng Việt sửa thành công, 0 lỗi, 0 ký tự C1 còn lại. Mẫu: `Bắt đầu trò chơi`, `Hộp thư`, `Cài đặt`, `Nhận hết`, `Thời gian chuẩn bị`, `Vườn mê cung`.
  - Python **112 test OK**; 3 test JS khác OK; `node --check` OK.
- Bẫy khi test (đã trải qua, ghi lại để không lặp lại):
  - `TextDecoder` **không phải intrinsic ECMAScript** nên `node:vm` sandbox không có sẵn — phải truyền vào context, nếu không `ReferenceError` bị `catch` nuốt và test báo "chưa sửa" trong khi code đúng.
  - Đọc bundle bằng `latin1` sẽ ra mojibake **hai lần**, không phải thứ trình duyệt thấy. Phải đọc bằng `utf8` cho khớp `charset` mà trình duyệt dùng.
  - `LANG.init` thật của bundle gán vào object `TXT` sẵn có (`TXT={}` khai báo 1 lần rồi `TXT.key="..."`), **không** thay thế object — fake trong test phải mô phỏng đúng điều đó.
- Giới hạn:
  - Chỉ cần **F5**, không restart server (thay đổi nằm ở HTML).
  - Chỉ sửa chuỗi trong `TXT` và `S_SETTING_LANG`. Nếu còn văn bản non-ASCII hardcode ở nơi khác ngoài `TXT` (ví dụ tên riêng trong data game) thì chưa đụng tới; cần báo thêm nếu thấy.
  - File `font/MuJeogHaeByeongBold.ttf` vẫn thiếu nên game vẫn dùng `sans-serif` hệ thống. Chữ vẫn đọc được và giờ đã đúng dấu, nhưng nét không giống bản gốc Hàn. Chưa thêm font mới vì đó là thay đổi ngoài phạm vi yêu cầu — nói nếu muốn đặt font cụ thể.
  - Chưa thử bằng trình duyệt thật.

### 2026-09-27 — Sửa đứng máy giữa trận do asset lỗi/không tải kịp

- Mục tiêu/phạm vi được yêu cầu: game gốc Eldorado không bị đứng khi trong trận gặp asset mới chưa tải; người dùng chấp nhận rời trận rồi vào lại là không sao. Sau đợt khảo sát, người dùng hỏi có nên "yêu cầu tải asset trước khi vào game"; đã trình bày số liệu và **người dùng chọn hướng thêm timeout cho cổng chờ**.
- Phát hiện mới và bằng chứng:
  - Đọc bundle: scene trận gọi `loading_our_char()` / `loading_your_char()` tạo `new Image` + `.src` cho **mọi** frame rồi `interval_test_our()` / `interval_test_your()` chờ đủ mới start. Tức game **đã preload trước trận sẵn** — "yêu cầu tải asset trước khi vào game" chính là logic gốc, không phải thứ cần thêm.
  - Bộ đếm chỉ tăng trong `onload`, **không có `onerror`** (`MOVE/WAIT/ATTACK/BEATTACK/FIRE` của `LOIMG_CHAR_OUR_NUM`, `LOIMG_ETC_OUR`; tương ứng `..._YOUR`).
  - Vòng chờ tự hẹn lại: `setTimeout(interval_test_our,100)` ở cuối hàm, chỉ thoát khi đủ `cur >= tot` mới set `flag_LOIMG_CHAR_OUR=1`. Cổng start trận (`setInterval` trong `S_GAME`) chờ `flag_LOIMG_CHAR_OUR==1 && flag_LOIMG_CHAR_YOUR==1`.
  - Nguồn 404: `serve.py` (dòng ~4620) — asset thiếu thử đọc đĩa, thử `fetch_and_cache()` từ host gốc, hết cả hai thì `self._respond(404, "", "text/plain")` (thân rỗng).
  - Không phải deadlock server: `serve.py` dùng `ThreadingHTTPServer`. Không có `new Image(` trong bundle (chỉ `createElement("img")`), không có XHR `async:false`.
  - Số đo để quyết định không preload toàn bộ: **12.389 ảnh / 281,2 MB**; riêng `image/char/` là **7.686 ảnh / 130,9 MB** (attack 796, beattack 297, fire 364, move 644, wait 827, effect 102).
- Quyết định đã chốt:
  - **Không** mở rộng preload. Preload toàn bộ là trùng logic game sẵn có và tốn vài trăm request mỗi trận; nó cũng không chặn được ca *tải chậm*.
  - Sửa tận gốc ở server: **ảnh thiếu trả `200` + PNG trong suốt 1×1** thay vì `404`. `onload` luôn bắn → `cur` đạt `tot` → cổng tự mở, game chỉ không vẽ ra frame đó. Chỉ áp dụng cho ảnh; `.js/.css/.woff2` vẫn `404` để lỗi thật còn lộ.
  - Bổ sung **timeout 15 s** cho cổng chờ bằng runtime patch trong HTML: quá hạn thì tự set `flag=1` và **không** gọi hàm gốc (để hàm gốc không hẹn lại). Deadline tính riêng từng cổng và **tự arm lại mỗi wave** vì game reset `flag_LOIMG_CHAR_YOUR=0` rồi gọi lại loader cho từng wave — một hạn dùng chung sẽ chết ở wave đầu.
  - Bọc `interval_test_our` + `interval_test_your` là đủ cho **mọi** loại trận (thường, boss, daydungeon, sky) vì tất cả đi qua cùng một cặp cổng.
  - Bỏ guard cho file 0 byte: đã đo thực tế, dự án có **0** ảnh 0 byte và 0 ảnh <70 byte, nên nhánh đọc đĩa không cần chặn thêm.
  - `fetch_and_cache()` đã an toàn sẵn (`status == 200 and data`, không cache rỗng) nên không sửa.
- File đã thay đổi:
  - `serve.py`: thêm `import base64`, hằng `IMAGE_EXT`, hằng `BLANK_PNG`, và nhánh trả placeholder tại chỗ 404 asset thiếu.
  - `ELDORADO_WEB/source_20240722/index__mobile.html`: thêm khối script "Bỏ đứng máy khi trận chờ ảnh quá lâu"; sửa timer leak của khối sửa mojibake.
  - `TESTS/test_missing_asset_placeholder.py` (mới, 7 test).
  - `TESTS/test_battle_asset_gate_timeout.mjs` (mới, 6 nhóm).
  - `TESTS/test_txt_mojibake_fix.mjs`: thêm nhóm 7 (clear interval).
- Kiểm tra thực sự đã chạy:
  - `TESTS/test_missing_asset_placeholder.py` → **7 OK**. Có test HTTP thật trên `ThreadingHTTPServer` cổng 0 với `fetch_and_cache` bị chặn (giữ test offline, không gọi host gốc): ảnh thiếu trả `200 image/png` và **byte đúng bằng** `BLANK_PNG`; `.js/.css/.woff2` vẫn `404`.
  - `node TESTS/test_battle_asset_gate_timeout.mjs` → **OK** (6 nhóm: hẹn poll rồi tự clear; bọc idempotent; chưa hết hạn thì vẫn gọi hàm gốc; hết hạn thì tự mở cổng và **ngừng** gọi hàm gốc; wave mới phải arm lại hạn; cổng đã mở thì giữ nguyên đường gốc).
  - `node TESTS/test_txt_mojibake_fix.mjs` → **OK** (7 nhóm).
  - Kiểm chứng **test có răng**, không phải test "xanh cho có": vô hiệu hoá hạn (`TIMEOUT_MS = Infinity`) rồi mô phỏng 1.000 vòng chờ (10⁶ ms) → `flag_LOIMG_CHAR_OUR` **vẫn 0**, đúng bệnh đứng giữa trận. Bản vá thật mở cổng ở 15 s.
  - Kiểm chứng PNG bằng **decoder độc lập**, không chỉ validator tự viết: `System.Drawing` (GDI+) giải mã `1x1 Format32bppArgb`.
  - Python full suite → **120 test OK**.
  - JS: 7/8 OK.
- Bẫy đã trải qua (đừng lặp lại):
  - Validator cấu trúc PNG tự viết (`signature`/chunk/CRC) **bỏ sót nội dung pixel**: base64 "1×1 trong suốt" lấy từ mạng thực ra ra pixel `A=127` xanh lá, sẽ bị giãn thành mảng xanh đậm khi vẽ. Phải kiểm tra **pixel** (`IDAT` giải nén = `00 00000000`) và xác nhận bằng decoder thật.
  - `node:vm` không có `setInterval` mặc định — test mô phỏng cổng game bằng `setTimeout(interval_test_our,100)` thì phải truyền `setInterval`/`clearInterval` vào context, và phải **phân biệt** interval của bản vá (`install()`) với vòng hẹn lại của game; gộp hai cái thì test gọi nhầm hàm.
- Giới hạn:
  - **Cần restart server** mới có hiệu lực (thay đổi nằm trong `serve.py`). Không tự restart theo quy tắc dự án — người dùng tự chạy lại.
  - Ảnh thiếu giờ vẽ **vô hình** chứ không phải ô báo lỗi. Muốn thấy ô báo lỗi thì đổi placeholder sang ô màu.
  - Timeout 15 s là hằng số trong HTML. Máy rất yếu hoặc mạng rất lag có thể cần nâng.
  - **Chưa thử bằng trình duyệt thật** — mới xác nhận bằng đọc mã, test mô phỏng và decoder.
  - `TESTS/test_modal_visibility.mjs` **fail vì thiếu `playwright`** (không có `node_modules`/`package.json`). Đây là thiếu môi trường có sẵn từ trước, **không** phải hồi quy của đợt này. Chưa cài Playwright vì cần mất công cài trình duyệt; nói nếu muốn.
  - Vẫn chưa rõ máy đứng lúc đầu có đúng do 404 hay do tải chậm, vì chưa có network trace trình duyệt. Bản vá hiện phủ **cả hai**.
- Việc còn lại và bước tiếp theo:
  1. Người dùng restart `serve.py`, xoá cache trình duyệt một lần, vào trận có nhân vật mới để xác nhận hết đứng.
  2. Nếu vẫn thấy đứng, lấy `console.warn("[GATE] het han ...")` — dòng đó in ra `cur/tot` của từng hành động nên biết chính xác ảnh nào thiếu hoặc mắc.
  3. Cân nhắc log danh sách asset 404 ở server để bổ sung file còn thiếu vào dự án.

### 2026-09-27 — Sửa vòng lặp trận chết vĩnh viễn do `drawImage` (bổ sung đợt trước)

- Mục tiêu: người dùng gửi console F12 lúc bị đứng. Hỏi nguyên nhân thật.
- Bằng chứng mới (khác hẳn kết luận đợt trước):
  - Console cho thấy **`502`**, không phải `404` như dự đoán trước đó, trên `ally_95_*`, `ally_103_*`, `ally_111_*`, `ally_114_*`.
  - Có exception thật, đây mới là nguyên nhân đứng:
    `Uncaught InvalidStateError: Failed to execute 'drawImage' ... 'broken' state` tại `S_GAME.interval_set_your_div` → `S_GAME.move_our_or_enmey` → `S_GAME.interval`.
  - Đọc lại hàm: `S_GAME.interval=function(){ ... S_GAME.move_our_or_enmey(), ... S_GAME.timer_interval=setTimeout(S_GAME.interval,...) }`. Dòng `setTimeout` tự nối lại nằm **cuối** hàm, nên exception ném ra ở `move_our_or_enmey()` khiến dòng hẹn lại **không bao giờ chạy** → vòng lặp chết hẳn, chỉ hồi phục được bằng cách rời trận. Đây là cơ chế khớp 100% với "rời trận vào lại thì ổn".
  - **Đã kiểm tra lại chính các file bị báo lỗi: chúng CÓ trên đĩa** (`ally_95_wait_16.png` = 29.550 byte, `ally_103_attack_12.png` = 23.090 byte, …). Thử request thật vào `127.0.0.1:8029` trả `200 image/png` đúng kích thước; file không tồn tại trả `200 image/png` 70 byte (đúng `BLANK_PNG`) → **bản sửa `serve.py` đã chạy**.
  - `serve.log` cho thấy cùng một URL bị GET lặp lại ở các giây liên tiếp rồi mới `-> static` thành công → các `502` là lần gọi **trước khi restart server**; console F12 chứa log tích luỹ từ lúc mở trang. Vậy `502` **không** phải nguyên nhân còn lại.
- Quyết định đã chốt:
  - Thêm guard ở `CanvasRenderingContext2D.prototype.drawImage`: ảnh `IMG` chưa có pixel thì bỏ qua khung hình đó, **không ném**; mọi lỗi khác (kể cả `drawImage(null)`, canvas khác loại) vẫn ném nguyên vẹn để không che lỗi thật. Chặn ở `drawImage` vì đó là nơi **mọi** lệnh vẽ đi qua — một chỗ, không vá từng call site.
  - Guard phải nuốt **cả hai** ca: `broken` (`complete=true, naturalWidth=0`) **và** `complete=false` (còn đang tải). Nếu chỉ nuốt ca broken thì bản vá timeout 15 s ở đợt trước sẽ tự mở ra một đường treo mới: cổng mở khi ảnh chưa tải xong → `drawImage` ném → loop chết. Cả hai đều là "không có pixel để vẽ".
  - Không bọc `try/catch` quanh `S_GAME.interval`: nuốt lỗi ở mức vòng lặp sẽ che mọi lỗi thật và có thể khiến loop quay vô hạn. Guard `drawImage` đủ hẹp và nêu rõ lý do.
- File đã thay đổi:
  - `ELDORADO_WEB/source_20240722/index__mobile.html`: khối script "Không để một ảnh hỏng giết vĩnh viễn vòng lặp trận".
  - `TESTS/test_broken_image_no_freeze.mjs` (mới, 6 nhóm).
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md`: cột bảng mục 6.
- Kiểm tra thực sự đã chạy:
  - `node TESTS/test_broken_image_no_freeze.mjs` → OK. Nhóm 5 mô phỏng đúng `S_GAME.interval` (vẽ giữa hàm, `setTimeout` hẹn lại ở cuối) và chứng minh 5/5 vòng đều hẹn lại được. Nhóm 6 chứng minh **không có** patch thì vòng lặp chết ngay lần đầu (`armed === 0`).
  - Thử request thật vào server đang chạy: file có thật → `200 image/png`; file không tồn tại → `200 image/png` 70 byte.
  - Xác nhận 9 file bị báo lỗi đều tồn tại trên đĩa, kích thước 21–34 KB; `ally_95` 68 file, `ally_103` 78, `ally_111` 62, `ally_114` 56.
  - Python full suite → **120 test OK**. JS → **8/9 OK**.
- Bẫy đã trải qua (đừng lặp lại):
  - `serve.log` ghi log nhiều thread **không gắn được vào từng request** (`-> static 29550` có thể thuộc request khác), nên phải đối chiếu kích thước file trên đĩa thay vì tin dòng log.
  - Số `StartTime` của process không đủ tin cậy để kết luận server đã restart hay chưa; cách chắc chắn là thử request thật và xem byte trả về.
  - Fake `CanvasContext2D` trong test phải ném cho **mọi** arg không có pixel (kể cả `CANVAS` và `null`), nếu không thì nhánh "lỗi khác vẫn ném" không bao giờ được kiểm tra và test cho đỡ sai.
- Giới hạn:
  - Chỉ cần **F5**, không restart server (thay đổi nằm trong HTML).
  - Guard làm ảnh hỏng **biến mất im lặng** thay vì báo lỗi. Nếu muốn thấy, sẽ phải thêm bộ đếm hoặc `console.warn` khi nuốt lỗi — hiện chưa thêm để không spam console mỗi khung hình.
  - Chưa thử lại bằng trình duyệt thật sau lần sửa này.
  - `TESTS/test_modal_visibility.mjs` vẫn fail vì thiếu `playwright` (môi trường có sẵn, không phải hồi quy).
- Việc còn lại và bước tiếp theo:
  1. Người dùng **F5** rồi vào lại trận có nhân vật mới. Không cần restart server.
  2. Nếu vẫn thấy `Uncaught ... drawImage` hoặc `[GATE] het han`, gửi lại console — nghĩa là còn nguồn lỗi khác ngoài ảnh IMG.

### 2026-09-27 — Truy vết "nhân vật mới lúc hiện lúc không" (đã đóng, không phải lỗi asset)
- Mục tiêu/phạm vi được yêu cầu: tìm nguyên nhân nhân vật mới nhấp nháy, sau khi đã sửa xong đứng máy.
- Phát hiện mới và bằng chứng:
  - **Frame đánh số từ 11, không phải từ 1.** URL sinh bằng `n+10`, nên `ally_*_11..N`. Lần quét đầu báo "THIEU[1..10]" là **sai lầm của regex**, không phải thiếu file. Mọi tập frame `ally` đều liên tục, không lỗ hổng.
  - `ally_95` khớp đúng bảng dữ liệu: `move=14`→11..24, `wait=14`→11..24, `attack=15`→11..25, `beattack=4`→11..14. Thiếu duy nhất là `fire`.
  - Bảng dữ liệu khai `fire_frame_num`: `ally_95`=10, `ally_96/97/98`=3, `boss_1`=7 — nhưng `ally_95_fire_11.png` và `ally_96_fire_11.png` trả **404 ở host gốc** trong khi `ally_95_wait_11.png` (200, 28.955 B) và `ally_49_fire_11.png` (200, 11.874 B) cùng lúc trả 200. **Các art fire này chưa từng tồn tại ở bản gốc**, không tải về được để vá.
  - **15 ảnh 1×1 trên đĩa KHÔNG phải hỏng cục bộ.** `boss_1_fire_11.png` tải từ `game.busidol.com` về cũng đúng **924 byte** — y hệt file local. Không được xóa những file này, xóa là phá hỏng asset gốc.
  - **Giả thuyết timeout 15s bị bác bỏ bằng đo thật:** 68 ảnh / 2,32 MB tải hết trong **0,20 s** ở 6 kết nối (giống hệt giới hạn 6 kết nối HTTP/1.1 của trình duyệt). Cả trận vài trăm ảnh chưa tới 2 giây, nên `[GATE] het han` không bao giờ kịp chạy.
  - **Bằng chứng quyết định — log `MISSING-ASSET`:** trong một trận thật chỉ có **6** dòng, và **không có dòng nào** thuộc `image/char/ally_*/...`. Toàn bộ là ảnh đại diện: `image/ui/4_game/char/ga_ally_{95,101,103,111,114}*.jpg` và `image/ui/21_boss/boss_img1.png`. Nghĩa là **không có sprite trận đấu nào bị thiếu** → giả thuyết "thiếu fire frame" của chính tôi là **sai**, và nếu sửa theo nó thì sửa nhầm.
  - Nguyên nhân thật của chỗ "thiếu 404": trên đĩa chỉ có avatar tên đơn giản `ga_ally_95.jpg`, còn game yêu cầu tên có mã biến thể `ga_ally_951101100026.jpg`. Đây là hệ quả quy ước đường dẫn và áp dụng **đồng đều cho cả 114 nhân vật**, không riêng nhân vật mới → là trạng thái có sẵn của dự án, không phải hồi quy.
  - `ga_ally_50...jpg` (nhân vật gốc) cũng 404 ở host gốc → xác nhận 404 là hệ quả quy ước đường dẫn, không phải thiếu art ngoài đời.
  - `image/ui/21_boss/` có `boss_img2.png` + `boss_img3.png` nhưng **thiếu `boss_img1.png`**; host gốc cũng 404. Thiếu thật, nhưng chỉ ảnh trang trí boss.
  - Quét toàn bộ 7.761 ảnh trong `image/char` bằng header PNG (không decode): 15 file 1×1, không có file 0 byte hay PNG hỏng.
- Quyết định đã chốt / đề xuất còn mở:
  - **Không sửa gì thêm về asset.** Không xóa ảnh 1×1, không tổng hợp frame fire thay art gốc, không mở rộng preload.
  - Các lớp bảo vệ đã thêm (fallback placeholder, gate 15 s, guard `drawImage`) giữ nguyên làm lưới an toàn, không phải là bản sửa đang hoạt động.
  - Còn mở (không chặn, tuỳ chọn): `boss_img1.png` và các avatar biến thể nếu muốn có ảnh đại diện/boss đầy đủ — cần nguồn art, không tự tạo.
- File đã thay đổi:
  - `serve.py` — thêm **1 dòng** `LOG.info("MISSING-ASSET %s", rel_path)` ngay trước khi trả `BLANK_PNG` (khoảng dòng 4638), để lần sau tra đúng tên file thiếu thay vì suy đoán.
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — mục này.
  - Không sửa bundle. Đã xóa 4 script tạm `_tmp_*.py`.
- Kiểm tra đã chạy, kết quả và giới hạn:
  - `python -m py_compile serve.py` → OK.
  - Request thật vào `127.0.0.1:8029`: 68 ảnh `ally_95` trả đủ 2,32 MB, `nho(<1KB)=1`.
  - Probe host gốc cho 9 đường dẫn → kết quả nêu trên.
  - Quét header 7.761 ảnh `image/char`; quét PIL 5 thư mục nhân vật (95/103/111/114/49) về ảnh trống hoàn toàn → `ally_95` chỉ có `ally_95_fire.png` 1×1.
  - Người dùng xác nhận bằng trình duyệt thật: **game chạy mượt, không đứng, không lỗi.**
  - Giới hạn:
    - **Lần đo 15,59 s đầu tiên là sai** — URL của tôi thiếu thư mục con nên đo tốc độ trả placeholder 70 B, không phải ảnh thật. Bài học: luôn kiểm tra kích thước body mẫu trước khi tin phép đo.
    - Regex kết thúc bằng `$` bị PowerShell here-string nuốt thành ký tự literal → script Python chạy sai âm thầm. Khi đo lường bằng PowerShell, viết script ra file thay vì truyền `-c`.
    - `r[2]` trên tuple 2 phần tử → `IndexError`; phải chỉnh chỉ số.
    - Chưa chứng minh được game có vẽ `fire` của 95 hay không; log chỉ cho thấy nó **không** 404 trong trận đã chơi.
    - Dòng log `MISSING-ASSET` hiện vẫn nằm trong `serve.py`; có thể gỡ nếu thấy log nhiễu.
    - `TESTS/test_modal_visibility.mjs` vẫn fail vì thiếu `playwright` (môi trường có sẵn).
- Việc còn lại và bước tiếp theo:
  1. **Không còn việc bắt buộc.** Đứng máy đã xử lý và đã xác nhận trên trình duyệt thật.
  2. Nếu sau này thấy vấn đề hiển thị: dùng `serve.log` lọc `MISSING-ASSET` (phải restart server một lần để có log) thay vì suy đoán từ console.
  3. Tuỳ chọn: gỡ dòng log, hoặc bổ sung art avatar nếu có nguồn. `boss_img1.png` đã xử lý ở mục kế tiếp.

### 2026-09-27 — `boss_img1.png`: không có nguồn art, nguyên nhân là server khai sai stage

- Mục tiêu/phạm vi được yêu cầu: tìm nguồn art hợp lệ cho `image/ui/21_boss/boss_img1.png` (người dùng đã chọn phương án alias, giữ nguyên cân bằng).
- Phát hiện mới và bằng chứng:
  - **`boss_img1.png` không tồn tại ở bất kỳ đâu.** Kiểm tra: `game.busidol.com` → 404; quét **2.928 thư mục** trên `E:\UserData\Desktop` thuộc 4 bản sao dự án (`Travel/busidol_offline`, `busidol_offline12.00`, `TEST ELDORADO/...`, `ELDORADO_WEB` ở gốc Desktop) → chỉ có `boss_img2.png` (27.721 B) và `boss_img3.png` (28.749 B), trùng byte hoàn toàn với host gốc. Game gốc **chỉ phát hành art cho stage 2 và 3**.
  - File được ghép động trong bundle: `utilDrawImage_no_wh_pos("RB_boss_img", ... + "image/ui/21_boss/boss_img" + S_BOSS.stage + ".png", ...)`.
  - `glo.APP_FEATURE.BOSS_2026 = 1` được bật trong khối init → nhánh dùng `S_BOSS.stage` (client), không dùng số boss từ server.
  - `S_BOSS.stage = parseInt(i.BOSS_NUM)` lấy từ **response server**; `serve.py:277 BOSS_ACTIVE_NUM = 1` → `stage = 1` → xin `boss_img1.png` → 404.
  - Stage 1 là World Boss (`BOSS_DESIGN[1].max_hp = 2e12`), client xử lý đầy đủ, kể cả rung màn hình riêng cho `S_BOSS.stage == 1`. **Chỉ mỗi art là chưa từng được phát hành.**
  - Cùng kiểu vậy, `boss_img4..8.png`, `boss_bg5/6/7.jpg`, `boss_bgbox_50_{5,6,7}.png` (tham chiếu trong `S_GUILD_BOSS_LOBBY.get_boss_assets`) cũng không tồn tại ở host gốc lẫn local.
  - **Kết luận: đây không phải "thiếu art" mà là lệch stage** — art có sẵn cho 2/3 còn server khai boss 1.
- Quyết định đã chốt / đề xuất còn mở:
  - Người dùng chọn **alias**: `boss_img1.png` → trả `boss_img2.png`. Giữ nguyên World Boss 2 nghìn tỉ HP, **không đụng cân bằng**, không sửa bundle. Đánh đổi: boss 1 hiển thị hình boss 2.
  - Đã **không** tự tạo art giả, **không** đổi `BOSS_ACTIVE_NUM` (sẽ làm HP rơi từ 2 nghìn tỉ xuống 35 tỉ — thay đổi cân bằng, cần quyết định riêng).
- File đã thay đổi:
  - `serve.py` — thêm `ASSET_ALIAS` (khóa theo **đuôi** đường dẫn để chạy được trên cả hai góc `ELDORADO_WEB/image` và `ELDORADO_WEB/source_20240722/image`, và phục vụ từ đúng gốc client yêu cầu), cùng nhánh xử lý trong khối "missing static asset" **trước** `fetch_and_cache`.
  - `TESTS/test_missing_asset_placeholder.py` — thêm 2 test.
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — mục này; và **sửa cấu trúc**: hai mục nhật ký này trước đó bị đặt nhầm dưới mục 10 (mẫu) thay vì mục 9 (nhật ký).
- Kiểm tra đã chạy, kết quả và giới hạn:
  - `python -m py_compile serve.py` → OK.
  - `python -m unittest TESTS.test_missing_asset_placeholder` → **9 test OK** (trước là 7). Test mới chạy HTTP thật qua handler trên cổng ngẫu nhiên, `fetch_and_cache` bị chặn để không gọi host gốc.
  - Full suite: `python -m unittest discover -s TESTS -p "test_*.py"` → **121 test OK**, 0 lỗi discover. Đếm lại theo module: `test_missing_asset_placeholder` 9, `test_moss_moon_wallet` 20, `test_admin_control` 15, `test_farm_core` 15, `test_pvp_2025` 14, `test_eldorado_hard_mode` 12, `test_security_s1` 11, còn lại 1–6.
  - **Sửa con số cũ:** các mục trước ghi "Python full suite → 120 test OK". Hôm nay đo được **121** với 0 lỗi discover, và file placeholder đúng là 7→9. Nghĩa là con số 120 trước đó lệch 1; lấy **121** làm chuẩn.
  - **Test bắt được lỗi thật của chính lần sửa đầu:** dùng `rel_path[:-len(alias_key)]` đã cắn mất dấu `/` phân tách, ra `.../source_20240722image/ui/...` → nhánh alias im lặng rơi về placeholder. Đã đổi sang `rpartition(alias_key.lstrip("/"))`. Không có test này thì lỗi sẽ không lộ.
  - Giới hạn:
    - **Cần restart `serve.py` một lần** thì alias mới có hiệu lực (thay đổi nằm trong Python, không phải HTML). Chưa kiểm chứng trên server đang chạy vì không tự restart tiến trình của người dùng.
    - Boss 1 sẽ hiện **hình boss 2**. Nếu sau này có art stage 1 thật, chỉ cần xóa dòng trong `ASSET_ALIAS`.
    - `boss_img4..8`, `boss_bg5/6/7`, `boss_bgbox_50_{5,6,7}` vẫn thiếu; chưa alias vì không biết stage nào tương ứng art nào (`get_boss_assets` ánh xạ 5→5, 6→6, còn lại→7).
    - `TESTS/test_modal_visibility.mjs` vẫn fail vì thiếu `playwright` (môi trường có sẵn, không liên quan).
- Việc còn lại và bước tiếp theo:
  1. Người dùng **restart `serve.py`** rồi mở màn xếp hạng boss để thấy ảnh.
  2. Nếu muốn boss 1 có hình riêng hoặc muốn đổi cân bằng, cần quyết định riêng — không tự đoán.

### 2026-09-27 — Hạ ruby quà đăng nhập ruby_farm (điểm danh)

- Mục tiêu/phạm vi được yêu cầu: người dùng yêu cầu xem lại danh sách quà đăng nhập, rồi sửa riêng phần ruby. Giá trị mới theo thứ tự ngày: `100, 150, 150, 250, 150, 400, 400`.
- Phát hiện mới và bằng chứng:
  - Quà đăng nhập của ruby_farm là `CHECKIN_REWARDS` tại `serve.py:2078`, endpoint `wallet/checkin.php` (`serve.py:4100`).
  - **Tính lại tổng, tôi đã cộng sai ở lần trả lời trước:** tổng ruby/tháng là **14.750** (không phải 15.750) và tổng vàng/tháng là **5.750.000** (không phải 6.750.000), BP là **250** (không phải 330). Chỉ ruby, cloud, essence, GTICKET, STICKET là đúng ngay từ đầu.
  - Bảng lưu **số cuối đã bao gồm `REWARD_MULT = 5`**, và mã cộng thẳng `amt` vào `DATA1[2]`. Nên ghi `100` nghĩa là người chơi nhận đúng 100 — không chia thêm 5 lần nữa.
  - Feature này **trước đó không có test nào** (`grep CHECKIN` trong `TESTS/*.py` không khớp).
- Quyết định đã chốt:
  - Ruby mới theo ngày 4, 9, 15, 20, 27, 30, 31 → 100 / 150 / 150 / 250 / 150 / 400 / 400. **Tổng 1.600 ruby/tháng** (từ 14.750).
  - 24 ngày còn lại **không có ruby** — test khoá luôn điều này để lần sửa sau không lỡ tay thêm ruby vào ngày không nên có.
  - Không đụng `REWARD_MULT`, không đổi các loại quà khác.
- File đã thay đổi:
  - `serve.py` — 7 ô `RUBY` trong `CHECKIN_REWARDS`.
  - `TESTS/test_farm_http.py` — thêm 3 test + tách `request_path()` cho path tuỳ ý (trước đó `request()` hardcode `/ELDORADO_WEB/garden/`), thêm `import time`.
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — mục này.
- Kiểm tra đã chạy, kết quả và giới hạn:
  - `python -m py_compile serve.py` → OK.
  - Đọc lại `CHECKIN_REWARDS` từ `serve.py` bằng `ast.literal_eval` → ruby theo thứ tự `[100, 150, 150, 250, 150, 400, 400]`, **khớp** yêu cầu; tổng 1.600.
  - `python -m unittest TESTS.test_farm_http` → **7 test OK** (trước là 4).
    - `test_checkin_ruby_schedule`: khoá 7 ngày có ruby + tổng 1.600 + 24 ngày còn lại không có ruby.
    - `test_checkin_info_serves_the_same_table_the_client_draws`: endpoint `info` phải trả **đúng bảng** `CHECKIN_REWARDS` — trước đây không có gì bảo đảm bảng hiển thị khớp bảng thưởng thật.
    - `test_checkin_claim_credits_exact_ruby_once_per_day`: patch `serve.time.localtime` về ngày 4, claim một lần nhận đúng 100 vào `DATA1[2]`, claim lại trong cùng ngày bị chặn và **không** cộng thêm.
  - Full suite: `python -m unittest discover -s TESTS -p "test_*.py"` → **124 test OK** (trước 121).
  - Giới hạn:
    - **Cần restart `serve.py`** thì bảng mới có hiệu lực (thay đổi nằm trong Python). Chỉ cần restart, không sửa HTML nên không cần F5.
    - Test claim chỉ chạy thật cho **ngày 4**; 6 ngày còn lại được khoá bằng so sánh bảng, không claim thật từng ngày.
    - Người chơi đã điểm danh trong tháng này ở các ngày ruby cũ không bị thay đổi retro — `farm_ci.days` chỉ ghi ngày đã nhận, không ghi số đã nhận. Đã nhận 500 ngày 4 thì vẫn giữ 500.
- Việc còn lại và bước tiếp theo:
  1. Người dùng **restart `serve.py`**.
  2. Tuỳ chọn: muốn kiểm lại lịch quà trên web thì mở `rubyfarm.html` → tab "Điểm danh".

### 2026-09-27 — Hạ tổng vàng quà đăng nhập ruby_farm xuống 3 triệu

- Mục tiêu/phạm vi được yêu cầu: giảm lượng vàng trong `CHECKIN_REWARDS` để tổng/tháng còn **3.000.000** (thay vì 5.750.000).
- Phát hiện mới và bằng chứng:
  - Vàng cũ nằm ở 5 ngày: 1 = 250k, 6 = 500k, 13 = 1tr, 21 = 1,5tr, 29 = 2,5tr.
  - Người dùng chỉ nói **tổng**, không nói cách chia. Đã tự chọn cách giữ **đường cong tăng dần** như cũ nhưng làm tròn số đẹp, và nói rõ để người dùng đổi lại nếu muốn chia khác.
  - Không chia tỉ lệ tuyến tính thuần vì sinh số lẻ (130.435, 260.870, 1.304.348…) — không dùng trong game có số tròn.
- Quyết định đã chốt:
  - Vàng mới: ngày 1 = 150k, 6 = 300k, 13 = 500k, 21 = 750k, 29 = 1,3tr. **Tổng đúng 3.000.000.**
  - 26 ngày còn lại không có vàng — test khoá lại.
  - Ruby giữ nguyên 1.600/tháng. Không đụng BP, cloud, essence, GTICKET, STICKET.
- File đã thay đổi:
  - `serve.py` — 5 ô `GOLD` trong `CHECKIN_REWARDS`.
  - `TESTS/test_farm_http.py` — thêm `CHECKIN_GOLD` + `test_checkin_gold_schedule` (8 test, trước 7).
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — mục này.
- Kiểm tra đã chạy, kết quả và giới hạn:
  - `python -m py_compile serve.py` → OK.
  - `python -m unittest TESTS.test_farm_http` → **8 test OK**.
  - Đọc lại bằng `ast.literal_eval`: vàng `{1:150000, 6:300000, 13:500000, 21:750000, 29:1300000}` tổng **3.000.000**; ruby tổng 1.600; BP 250, cloud 38, essence 23, GTICKET 9, STICKET 8 (không đổi).
  - Full suite → **125 test OK** (trước 124).
  - Test tổng vàng cố tình tính **từ chính chuỗi `CHECKIN_REWARDS`**, không tính từ dict trong test — nếu ai đó thêm/sửa ô vàng thì assert tổng bắt được, không tự khớp với nhau.
  - Giới hạn:
    - **Cần restart `serve.py`** thì mới có hiệu lực (thay đổi trong Python, không phải HTML).
    - Người chơi đã nhận vàng ở tháng này không bị điều chỉnh retro, giống ruby.
- Việc còn lại và bước tiếp theo:
  1. Người dùng **restart `serve.py`**.
  2. Nếu muốn chia vàng khác thì nói rõ từng ngày, sửa lại bảng + `CHECKIN_GOLD` trong test.

### 2026-09-27 — Khảo sát guild để làm guild hoạt động thật (chưa sửa code)

- Mục tiêu: người dùng chọn "làm guild hoạt động thật". Đợt này **chỉ khảo sát protocol**, chưa viết code guild.
- Hiện trạng đúng: `serve.py:3597` chỉ có **một khối stub** cho mọi guild. Không có bảng DB guild nào. Mọi tài khoản đều nhận `"no_guild"`.
- Phân biệt quan trọng: **guild thường ≠ Guild Boss ≠ World Boss**. Câu `update_guild_boss.php` "đã làm thật (`boss_state`/`boss_damage`/`boss_sessions`)" ở bản ghi này là **ghi nhầm, đã đính chính 28/09/2026**: ba bảng đó thuộc **World Boss 2026** (`boss_2026/*.php`, xem `serve.py:215`), không liên quan Guild Boss. `update_guild_boss.php` chưa có handler.
- Phát hiện về transport (tra từ `eldorado_all_20260915.min.js`, không có source map):
  - Hàm duy nhất: `ServerConnection.update_guild(data, type, cb, retry)`.
  - URL = `SERVER_URL + (gAPP_RELEASE=="TEST" ? "Guild_TEST/" : "Guild/")` rồi cộng `.php` theo `type`:
    `guild_inter`→`update_guild_inter.php`, `guild_main`→`update_guild_main.php`, `guild_battle`→`update_guild_battle.php`, `guild_shop`→`update_guild_shop.php`, `guild_boss`→`update_guild_boss.php`.
    **Không có case nào trả `update_guild.php`** — `type` lạ sẽ gửi tới URL `Guild/` trần.
  - Body là `json_obj` (object nếu `ENABLE_CRYPT`, ngược lại là **chuỗi** JSON) + `crypt`. Server đã tự parse cả hai.
  - Server tự gắn `HOST_ID`, `USER_NAME`, `user_level`, `language`, `profile_num`, `VER_DATE` vào mọi request.
  - **Bẫy 1 — chuỗi "error":** `success_fn` kiểm `n.includes("error")` (n là body thô) → hiện popup lỗi mạng và **return sớm**. Mọi response lỗi phải tránh hẳn chuỗi `error` trong body. Scene có `case"error"` nhưng tới không được vì bị chặn ở transport.
  - **Bẫy 2 — `data` không được bằng `"error"`:** ở `check_guild_name`, `result:"duplication"` mà `n.data=="error"` thì hiện popup lỗi.
  - **Bẫy 3 — `result:"CGM_NO_GUILD"`:** client tự đá về main menu kèm `TXT.guild_kick` (nghĩa là admin kick khỏi guild). Chỉ dùng khi thật sự bị kick.
  - **Rate limit phía client:** `GUILD_RL_MIN_INTERVAL_MS = 500` tính theo cặp `type:act`, và khóa in-flight 5s (`GUILD_RL_TIMEOUT_MS`) bằng `setTimeout` an toàn. Hai request cùng `type:act` trong 500ms → request sau **bị client tự bỏ**, không tới server. Test phải ch�u kỹ điều này.
  - Trong khi chờ, `gEnableKey=0` (khoá phím), trả về mới `gEnableKey=1`.
- Bản đồ act (quét 60 call site, gom theo `type`):
  - `guild_inter` (5): `check_guild_name`, `insert_new_guild`, `get_guild_list`, `get_guild_season_ranking_data`, `check_guild_member`.
  - `guild_main` (8): `get_member_list`, `get_approve_list`, `get_guild_chat`, `send_guild_chat`, `update_guild_member`, `update_guild_buff`, `update_member_donate`, `update_guild_mission`.
  - `guild_battle` (11): `get_battle_normal`, `get_defence_deck30`, `get_guild_battle_member_history`, `get_guild_battle_rank_all`, `insert_guild_battle_revive`, `insert_guild_battle_start`, `next_guild_matching`, `next_guild_matching_cloud30`, `update_deck_attack`, `update_deck_defence`, `update_guild_battle_result`.
  - `guild_shop` (1): `guild_shop_purchase`.
  - `guild_boss` (**5**, không phải 3 — đối chiếu client 28/09/2026): `get_lobby`, `check_can_enter`, `enter_battle`, `report_damage`, `get_help` — **đã làm** 28/09/2026. Tài liệu trước đây ghi 3 act là thiếu.
  - Có chuỗi rời lẻ trong bundle nhưng **không** thấy gọi qua `update_guild`: `join_guild`, `join_open_guild`, `join_approve_guild`, `update_leave_guild`, `transfer_guild_master`, `guild_delete`, `sort_guild_free`, `sort_guild_approve` — nhiều khả năng gộp chung vào `update_guild_member` / `get_guild_list`, phải tra tiếp trước khi code.
- Mẫu response đã xác nhận (`check_guild_name`, guild_inter):
  - `result`: `ok` | `duplication` | `str_not_allowed` | `long` | `error`(bị chặn ở transport).
- Quyết định về cách làm:
  - **Không đoán tên field.** Sai tên field là `n.result` undefined → rơi vào `default` → popup lỗi, đúng như comment sẵn có ở `serve.py:3598`.
  - Chia giai đoạn. Chưa chốt phạm vi với người dùng.
- Giới hạn của đợt khảo sát này:
  - Chỉ mới xác nhận chắc transport + act + response của `check_guild_name`. **Còn lại chưa truy tới từng field.**
  - Chưa đọc art `image/ui/49_guild/` và `49_guild_shop` để biết UI cần asset gì.
  - Chưa chạy gì trên server, không sửa file nguồn nào.

### 2026-09-27 — Làm guild hoạt động thật, giai đoạn 1 (Guild, không phải Guild Boss)

- Mục tiêu: người dùng chọn "làm guild hoạt động thật" và chốt luật **tối đa 20 thành viên, mua thêm slot giá 500 Ruby/người**. Đợt này viết code thật, thay stub cũ.
- Phạm vi đã làm: tạo/tìm/join/duyệt, danh sách thành viên, chat, rời/đuổi/chuyển chủ/xoá guild, mua slot, buff, nhiệm vụ, quyên góp, bảng xếp hạng mùa. **Chưa làm:** `guild_shop` (1 act) — vẫn là stub. *(Ghi nhận 27/09/2026; `guild_battle`, `guild_boss`, `guild_shop` đã làm sau đó xem nhật ký 28/09/2026.)*
- File đã thay đổi:
  - `guild_backend.py` (mới): schema + dispatch + 17 act.
  - `serve.py`: import `guild_dispatch`/`init_guild_db`, gọi `init_guild_db` trong `init_db`, route `update_guild_inter.php` và `update_guild_main.php`.
  - `TESTS/test_guild.py` (mới, 40 test), `TESTS/test_guild_http.py` (mới, 8 test).
- DB (cùng SQLite của `--db`): `guilds`, `guild_members`, `guild_applies`, `guild_chat`. Ràng buộc bằng PRIMARY KEY: mỗi người tối đa 1 guild, tên guild là duy nhất.
- Quyết định quan trọng về tiền: **client tự trừ** ruby/cloud/gold sau khi nhận `result:"ok"` (đã đọc trong `update_guild`, `run_buff_upgrade`, `update_member_donate`). Server **không trừ lần hai**, chỉ kiểm tra đủ. Vì vậy test phải tự mô phỏng bước trừ phía client (`spend_ruby`) mới kiểm được nhánh "không đủ" ở lượt gọi sau.
- `guild_money` là quỹ guild, client **không** tự cộng khi quyên góp → server phải cộng. Số tiền lấy từ `S_GUILD_DONATE_VALUE` của client (CLOUD 10, RUBY 10, GOLD 100000).
- Shape bắt buộc đã chốt từ client, sai là màn trắng hoặc popup lỗi:
  - `get_guild_normal`: `switch(result){case"ok": switch(data){case"no_guild":...}}` → trả `result:"ok"` + `data:"no_guild"`, **không** phải `result:"no_guild"`.
  - `check_guild_member`: `switch(result){case"no_guild"/"has_guild"}` → switch thẳng trên `result`, kèm `exit_remain_time`, `exit_time`, `season_data`.
  - `get_guild_list`: `json_secure.set("guild_list", n.data)` rồi lặp `t.length` → `data` là **mảng trực tiếp**, không bọc object.
  - `update_guild_member` ok: `t.guild_data` + `t.member_data` ở top-level; `get_member_list` ok: `data` + `cur_member`/`max_member` ở top-level.
  - `season_data` phải có mặt ở mọi response guild.
  - `cur_member == max_member` thì client chặn mua thêm slot; giá lấy từ `guild_add_member_ruby_value`.
  - `result:"CGM_NO_GUILD"` chỉ trả khi người chơi thật sự bị kick hoặc guild đã xoá; server đánh dấu trong save rồi xoá dấu ở lần `get_guild_normal` sau.
- Bẫy client đã tránh: **không response nào được chứa chuỗi `error`** (kể cả `data`), vì `success_fn` kiểm `n.includes("error")` trên body thô rồi return sớm.
- Luật server tự đặt vì client chỉ hiển thị: tên guild tối đa 12 ký tự, thông báo/chat tối đa 70, buff 5 cấp giá `0/100k/200k/400k/800k/1.6M`, duyệt tối đa 5 hồ sơ, chat giữ 50 dòng. Cấp buff đầu tiên giá 0 (miễn phí).
- Lỗi thật đã phát hiện và sửa trong lúc test (đáng nhớ vì `py_compile` không bắt được):
  - `serve.py` route guild gọi `guild_dispatch(path, ...)` nhưng hàm `offline_stub` nhận tham số tên `rel_path` → **NameError lúc chạy**, guild chết hoàn toàn qua HTTP.
  - Parser body tự viết **không URL-decode**, mà client luôn gửi `application/x-www-form-urlencoded` → `json_obj` không bao giờ parse được, mọi act rơi vào `"act chua lam"`. Đã thay bằng `urllib.parse.parse_qsl` của stdlib.
  - `insert_new_guild` hardcode `symbol_img=''`, vứt mất `symbolImg` client gửi lên.
  - Nhánh không có `--db` của `get_guild_normal` trả sai shape (sẽ bật "Error - GGN e").
  - Đọc DB bằng `row["tên_cột"]` trong khi `sqlite3` mặc định trả **tuple**. Đã thêm `_rows/_one/_scalar` dùng cursor riêng có `row_factory=sqlite3.Row`; **không** set `row_factory` cho cả connection vì `DB_CONN` dùng chung với các feature khác.
- Kiểm tra đã chạy thật:
  - `python -m py_compile serve.py guild_backend.py TESTS/test_guild.py TESTS/test_guild_http.py` → OK.
  - `python -m unittest TESTS.test_guild` → 40 test OK.
  - `python -m unittest TESTS.test_guild_http` → 12 test OK (đi qua `ThreadingHTTPServer` thật, kiểm route, phân quyền theo session, ghi DB qua request mới, 3 request chạy song song: tranh slot cuối, tranh trùng tên guild, join trùng lặp; thêm 2 test khoá hợp đồng `guild_position=MASTER` trên mọi đường client đọc: tạo guild, `get_guild_normal`, `check_guild_member`, `update_guild_mission`, và thành viên thường không bao giờ thấy `MASTER`; thêm 2 test `--wire-identity`: hai cửa sổ dùng chung cookie vẫn ra hai tài khoản, và wire id không phải tài khoản thì lùi về session).
  - `python -m unittest discover -s TESTS -p "test_*.py"` → **177 test OK**.
- Xác minh trình duyệt: **chưa đạt, và phần này trước đây ghi sai**. Người dùng đã restart `serve.py` và tạo được guild, nhưng sau đó báo "đã mở được bang hội, người tạo không có sẵn quyền làm chủ". Mình không tự mở trình duyệt kiểm từng màn.
- Kết quả đào log `serve.log` + đọc `busidol.db` ngày 28/09/2026 (đã thật):
  - Đường HTTP **đúng**: phát lại đúng request tạo guild trong log cho `guild_dispatch` → `data.guild_position = "MASTER"`. `get_guild_normal` và `check_guild_member` của tài khoản chủ cũng trả `MASTER`.
  - DB **đúng**: `ADMIN` (master `huando2007`, `is_master=1`) và `ADMIN2` (master `HUANDO`, `is_master=1`). Không mất `is_master`.
  - Chuỗi request thật của người tạo `huando2007`: `check_guild_name` → `insert_new_guild` → `update_guild_mission` → `get_member_list` → `get_approve_list` (`get_approve_list` chỉ được client gửi khi đã coi là chủ) → nên **ngay sau khi tạo quyền chủ có thật**.
  - 2 phút sau, client `huando2007` lại gửi `check_guild_member` → `get_guild_list` → `join_approve_guild`, tức bị đẩy sang màn hình xin gia nhập bang của chính mình. Cùng lúc đó client `HUANDO` (tài khoản khác, level 108) đang chạy song song trên cùng cổng 8029.
  - Nguyên nhân khớp với mọi bằng chứng: `serve.py:_uid()` lấy identity từ **cookie session đã login**, mà cookie dùng chung cho mọi cửa sổ trình duyệt trên cùng profile. Đăng nhập `HUANDO` ở cửa sổ thứ hai làm cửa sổ `huando2007` gửi request dưới danh `HUANDO` → `check_guild_member` trả `no_guild` → client hiện màn hình gia nhập, không có nút chủ.
  - **Đã sửa mã** sau khi người dùng xác nhận "có" (chơi nhiều tài khoản cùng lúc): thêm cờ `--wire-identity`. Khi bật, một request mà `HOST_ID`/`UNIQ_ID`/`USER_NAME` trong `json_obj` trỏ tới một tài khoản **tồn tại** sẽ chạy dưới tài khoản đó; còn lại lùi về session như cũ. Mặc định **tắt** (giữ nguyên hành vi bảo mật).
  - Bẫy kỹ thuật: client gửi `json_obj` **raw, không url-encode**, nên `HOST_ID` nằm trong JSON chứ không phải field form cấp ngoài — regex `HOST_ID=` cũ ở `serve.py` không bắt được, phải regex dạng `"HOST_ID"\s*:\s*"..."` trên `unquote(body_str)` (thêm `\+?` để chịu cả bản url-encode vì `+` là space).
  - Ràng buộc bảo mật chưa giải quyết: `BAT_TUNNEL.bat` mở cổng 8029 ra internet qua Cloudflare quick tunnel. Bật `--wire-identity` lúc đó thì bất kỳ ai truy cập được cũng chơi được dưới tên bất kỳ tài khoản nào. Vì vậy **chưa** thêm cờ vào `KHOIDONG_TOAN_BO.bat`; cần người dùng tự quyết.
- Giới hạn còn lại:
- **Danh sách chưa làm (xác minh 28/09/2026 bằng grep `serve.py`, không suy đoán):**

  | Tính năng | Endpoint client | Trạng thái |
  |---|---|---|
  | Guild War (bang hội đánh nhau) | `Guild/update_guild_battle.php` | **Đã làm 28/09/2026**, 11/11 act trong `guild_backend._ACT_BATTLE`. Test tự động xanh; **người dùng xác nhận chạy thật 28/09/2026.** |
  | Guild Boss | `Guild/update_guild_boss.php` | **Đã làm + đã chạy thật trên trình duyệt 28/09/2026**, 5/5 act trong `guild_backend._ACT_BOSS`. |
   | Guild Shop | `Guild/update_guild_shop.php` | **Đã làm + đã chạy thật 28/09/2026.** Act `guild_shop_purchase`: 4 card (item ×1/×10 `type_num` 26/27, hero ×1/×10 `type_num = 1000 + char_num*2 (+1)`). Xem nhật ký cuối. |
  | PvP Classic | `PVP_CLS_2026/*.php` (3 endpoint) | Chưa làm, **không có route** → rơi xuống `offline_stub`. |
  | PvP API cũ | `PvP/*.php` (2), `CPvP/*.php` (4) | Chưa làm, không có route. |
  | World Boss — phần còn thiếu | `Boss/*.php` | Mới làm 2/10: `get_boss_tiket_to_server.php`, `update_boss_tiket_to_server.php`. Còn thiếu `get_boss_num_to_server`, `update_boss_to_server`, `get_rank50_from_server_boss`, `get_rankboss_info`, `boss_cur_hp`, `is_boss_run_out_time`, `is_time_init_boss`, `is_time_init_boss_ranking_screen`. |

  Guild Shop **không** dùng stub nữu: route thật đã nối vào `guild_dispatch` và đã chạy thật. Câu "Guild Shop vẫn dùng stub" ở dòng trên **đã lỗi thời, bỏ qua** (ghi 27/09/2026, đính chính 28/09/2026). Đã đính chính những chỗ trong tài liệu trước đây ghi nhầm `update_guild_boss.php` là đã làm (thực chất là World Boss 2026), và sửa comment sai trong `serve.py:3615` và `guild_backend.py:5`.
  - Hai cách chơi nhiều tài khoản: profile/incognito riêng cho từng tài khoản (an toàn, không đổi mã) hoặc bật `--wire-identity` (tiện, **mất an toàn nếu đang mở tunnel**).
  - Giá buff, trần duyệt, giới hạn chat là số do server đặt, chưa đối chiếu với game gốc.
   - Cần chạy lại `python -m unittest discover -s TESTS -p "test_*.py"` sau mỗi lần sửa tiếp; hiện đang xanh 226 test (sau đợt gỡ lọc chat 28/09/2026).
- Bước tiếp theo: người dùng chọn (1) dùng profile/incognito riêng, hoặc (2) bật `--wire-identity` và **tắt `BAT_TUNNEL.bat`** khi chơi nhiều tài khoản. Sau đó người dùng tự restart server (không tự restart giúp).

### 28/09/2026 — Làm Guild War + Guild Boss (sau khi người dùng yêu cầu "sửa guild war/boss trước")

- Mục tiêu/phạm vi được yêu cầu: làm `Guild/update_guild_battle.php` (Guild War) và `Guild/update_guild_boss.php` (Guild Boss). PvP Classic để sau.
- Đã xác nhận (đọc từ `eldorado_all_20260915.min.js`, không đoán):
  - Guild War có **11 act**, Guild Boss có **5 act** — tài liệu cũ ghi Guild Boss 3 act là thiếu (`enter_battle`, `report_damage` bị bỏ sót).
  - `get_battle_normal` trả payload **thẳng** top-level; `update_deck_*` trả trong `guild_battle_normal`; `update_guild_battle_result` trả **lồng** `result.result`.
  - `deck30` là **object** khoá `"1".."30"`. `clear_guild_list`/`week_rank`/`attack_success`/`defence_fail`/member history là mảng **1-based**; Guild Boss `ranking`/`get_help.data` là **0-based**.
  - `damage_mult` là float (0.001 release, 10 TEST) — ép int trước khi nhân là sát thương bằng 0.
  - Client tự trừ `USER.cloud_piece -= 30` mà không báo server → server trừ cho khớp.
  - 9 chuỗi Hán (`GUILD_BT_PERIOD_READY`... `GUILD_BT_BAD_MATCH`) lấy **nguyên byte** từ bundle vì file là mojibake (UTF-8 đọc như latin-1). Không gõ tay Unicode.
- File đã thay đổi:
  - `guild_backend.py`: bảng `guild_bt_guild`/`guild_bt_slot`/`guild_bt_record`, `guild_boss_stage`/`guild_boss_damage`/`guild_boss_token`; 11 handler Guild War; 5 handler Guild Boss; bảng act `_ACT_BATTLE`/`_ACT_BOSS` + `_ACT_BY_GROUP`; helper `_as_float`; sửa `_int_or_zero` nhận tham số default; bỏ cột chết `beaten_num`; thêm `other_slot` + `ALTER TABLE` để chống cộng điểm 2 lần khi client retry; bỏ `_PENDING`; sửa docstring (BẪY 9–12).
  - `serve.py:3610` — route thêm `update_guild_battle.php`/`update_guild_boss.php` vào `guild_dispatch`; sửa comment stub cũ.
  - `TESTS/test_guild_battle_http.py` — **file mới**, 19 test qua HTTP thật.
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — cập nhật bảng trạng thái, sửa "3 act" thành 5.
- Quyết định đã chốt:
  - Chống gian lận bằng state thật, không bằng lịch: ô phòng thủ đã bị đánh trong tuần thì **khoá** không cho đổi deck (tránh sửa phòng thủ sau khi thua). Không phụ thuộc `period == READY` để không chặn nhầm lúc client vẫn cho sửa.
  - `insert_guild_battle_start` **không** tạo ô phòng thủ mới — đánh ô chưa có deck là mục tiêu không hợp lệ, trả `result:"no"`.
  - `get_defence_deck30` chỉ trả deck của đối thủ **đã gép trong tuần**, không xem được guild bất kỳ.
  - Xếp hạng đếm thật từ `guild_bt_record`/`guild_bt_slot` thay vì cột denormalize (`beaten_num` cũ không ai update → xếp hạng sai). `attack_success` gom theo `my_guild_name` (số trận thắng), `defence_fail` gom theo `guild_name` trong `guild_bt_slot` (số ô thủ bị thua) — cả 3 tab render chung một hàng nên đều đọc field `defeated_num`.
  - `update_guild_battle_result` idempotent theo khoá `(vien, o doi phuong, bo deck)`: retry trả `ok` với điểm hiện tại nhưng **không** cộng thêm.
- Kiểm tra đã chạy, kết quả:
  - `python -m py_compile serve.py guild_backend.py` → OK.
  - `python -m unittest TESTS.test_guild_battle_http` → **19 test OK**.
  - `python -m unittest discover -s TESTS -p "test_*.py"` → **196 test OK** (177 trước đợt này).
- Giới hạn (chưa kiểm chứng):
  - **Đã** smoke test trình duyệt: người dùng xác nhận "đã xong" 28/09/2026 sau khi tự restart. `serve.log` ghi `POST /ELDORADO_WEB/Guild/update_guild_boss.php` liên tiếp với body 231/288/418 byte — tức client đã gọi thật `check_can_enter` → `enter_battle` → `get_lobby` và nhận về body bình thường, không rơi vào `act chua lam`. Chưa kiểm chứng riêng Guild War (log lần này chỉ có Guild Boss).
  - Số liệu **tự đặt**, chưa đối chiếu game gốc: lịch tuần Guild War (KST thứ 2 11:00, `READY_LEN=86400`, `ATTACK_LEN=561600`), HP 7 chặng Guild Boss `(300000..4000000)`, trần sát thương `(100,100,50,40,30,20,10)%`, 1 lượt miễn phí/ngày, 10000 vàng/lượt trả phí, bảng thưởng.
  - Guild War giả đấu là "ghép ngẫu nhiên theo tuần", chưa có khung giải đấu/lịch thi đấu thật; `last_week_*` trả `0` chứ chưa tính lịch sử tuần trước.
  - `get_guild_battle_member_history` chỉ gom theo tuần hiện tại.
- Việc còn lại: người dùng restart server và smoke test 2 màn; sau đó mới làm `guild_shop` (1 act) rồi tới PvP Classic.

### 28/09/2026 — Làm Guild Shop (`update_guild_shop.php`, act `guild_shop_purchase`)

- Mục tiêu/phạm vi được yêu cầu: làm `Guild/update_guild_shop.php` (1 act `guild_shop_purchase`) để `HUANDO` mua được item thật bằng vàng guild. Không đụng Guild War/Boss (đã xanh 196 test trước đợt này).
- Trước khi code: cộng `200000` `gold_bar` cho `HUANDO` (từ 32 → 200032) để đủ mua card 40000. Backup trước khi cộng: `busidol.db.bak_goldbar_20260928_033713`; đã xác minh DB commit.
- Đã xác nhận (đọc từ `eldorado_all_20260915.min.js`, không đoán):
  - Card trong `S_GUILD_SHOP.CARDS`: 4 card; **2 card cuối là item gacha** — `type_num=26` (1 lượt, `4000`) và `type_num=27` (10 lượt, `40000`). `price`/`times` trong body **không được tin**; server tự tính.
  - `type_num=28/29` là **hero gacha**, cần `hero_list`; **đã làm 28/09/2026** (xem mục "Bổ sung cùng đợt" bên dưới).
  - Client Guild Shop **chỉ render `reward_info`**, không gọi `STORAGE.add_item`/`update_item_to_server` → server phải tự quyết định nơi lưu phần thưởng.
  - `TXT.random_box_tip` nói rõ item đến từ **mailbox** → lưu item vào `save["mails"]` với `what:"ITEM"`, `what_value` là **item 3 chữ số**. Khi nhận, `S_MAILBOX.reward_get_in_server` case `"ITEM"` **tự random sub-option**: `d==3` thì chọn ngẫu nhiên `DEFINE_ITEM_SUB_OPTION[1..7]` rồi tự roll số theo `S_ITEM.num_apply_item_grade_return_num(item_num)`; ghi **4 chữ số** thì không random được (digit thứ 4 chính là option index). → server **không** cần chọn trước `add_option`.
  - `char_reward` = `S_POPUP_PACKAGE_STORE.checked_num` (1..4) là loại item người chơi chọn; server phải giữ nguyên, không random lại.
  - Xác suất `ITEM_GACHA` của client: item 55%, gold 15% (`1000..10000`), ruby 10% (`10..100`), BP 10% (`50..300`), cloud 10% (`5..50`). Biến thể item theo `DEFINE_ITEM_UPGRADE.probability_sangjungha` = 60/30/10.
  - **Icon ràng buộc mới:** `S_POPUP_GACHA_RESULT.preload` chỉ tải `co_item16/26/36/46.png`, còn `et(n)` trả `"co_item" + floor(item_num/10)` → `item_num` **bắt buộc có tens digit 6** (grade A). Nếu roll 15x/17x thì **icon trống**. Đã cố định `GUILD_SHOP_GRADE = 6`.
  - Đã quét bundle: cả **36** tổ hợp slot×grade×variant (1..4 × 5..7 × 1..3) đều có `DEFINE_ITEM` → item id sinh ra luôn hợp lệ; 12 tổ hợp grade 6 thực sự dùng cũng có. Có test chốt lại điều này.
  - Tiền trong save: `DATA1[1]`=gold, `DATA1[2]`=ruby, `bp`, `cloud_piece`, `mails`; **không** dùng `DATA1[1]` làm guild gold — cần đồng bộ `guild_members.gold_bar` → `guild_data_mine.guild_gold_bar` → `USER.goldbar`.
- File đã thay đổi:
  - `guild_backend.py`: `GUILD_SHOP_CARD = {26: (1, 4000), 27: (10, 40000)}`; `GUILD_SHOP_GRADE = 6`; bảng `guild_shop_buy(user_id, fp, gold_bar_after, created_at, response)`; helper `_shop_mail_sn`, `_shop_roll_item`, `_shop_act_purchase`; `_ACT_SHOP` + map group `guild_shop`; sửa docstring tổng.
  - `serve.py`: route `update_guild_shop.php` vào `guild_dispatch`.
  - `TESTS/test_guild_shop_http.py` — **file mới**, 17 test qua HTTP thật (26 sau phần card hero).
  - `TAI_LIEU_MARKDOWN/FIX_GUILD_SHOP_20260928.md` — **file mới**: tài liệu riêng cho đợt fix này.
  - `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — cập nhật bảng trạng thái và số test.
- Quyết định đã chốt:
  - Server chỉ tin **session UID + membership**; `type_num` là duy nhất tham số mua lấy từ client. `price`/`times`/`user_goldbar` chỉ để hiển thị.
  - Trừ tiền bằng `UPDATE ... WHERE gold_bar>=price` (rowcount phải = 1) để không bao giờ âm.
  - **Idempotency**: client gửi lại nguyên body khi timeout. Khoá `(user_id, fp)` với `fp = type_num|times|slot|user_goldbar`; thêm `gold_bar_after` — chỉ coi là retry khi **số dư hiện tại bằng đúng số dư sau giao dịch cũ**. Nếu user kiếm lại đúng số vừa trừ rồi mua tiếp thì đó là đơn mới, phải thu tiền lại. Dòng cũ hơn 24h được dọn sau mỗi lần mua.
  - Mỗi lượt rút phải có **một entry trong `reward_info`** (kể cả gold/ruby/BP/cloud) — client vẽ card từ `reward_info.length`, không tự cộng tiền.
- Bài học (bug đã tìm ra nhờ test):
  - Lần đầu chỉ append `ITEM` vào `reward_info`, tiền thì chỉ cộng vào save → 10 lượt ra **9 card**, và client không hiện phần tiền. Đã sửa thành append mọi loại.
  - Test concurrency ban đầu đòi "chỉ 1 response ok", nhưng retry đúng là **phải trả cùng một response ok** cho cả 4 request. Đã sửa test: đòi 4 response giống hệt nhau, chỉ trừ tiền 1 lần, và chỉ 1 dòng receipt.
  - Bản đầu còn tính sẵn `add_option`/`add_option_num` rồi `pop` khỏi response — **code chết**, vì client tự random khi nhận mail. Đã **xóa** hẳn `GUILD_SHOP_SUB_OPTION` và đoạn pop. Lý do phải đọc `S_MAILBOX.reward_get_in_server` mới biết, không nên suy từ tên field.
  - Số test 196 → 213 (đợt item); **đã lên 222** sau phần card hero ghi ở mục nhật ký bên dưới.
- Kiểm tra đã chạy, kết quả (tại thời điểm chốt phần item):
  - `python -m py_compile serve.py guild_backend.py` → OK.
  - `python -m unittest TESTS.test_guild_shop_http` → **17 test OK** (26 sau card hero).
  - `python -m unittest discover -s TESTS -p "test_*.py"` → **213 test OK** (222 sau card hero).
- **Đã smoke test thật trên trình duyệt** (người dùng xác nhận "nó hoạt động rồi", 28/09/2026 ~04:23). Bằng chứng:
  - `serve.log` 04:23:24 `POST /ELDORADO_WEB/Guild/update_guild_shop.php` (body 306 byte), ngay sau đó client tải `image/ui/40_package_store/`: `co_item16/26/36/46.png`, `ogong_gacha1..8`, `top_lunar`, `co_bp`, `co_cloud`, `co_ruby` → `S_POPUP_GACHA_RESULT` đã mở, **có icon item** (xác nhận quyết định fix `GUILD_SHOP_GRADE = 6` là đúng).
  - DB `guild_members`: `HUANDO.gold_bar` **200032 → 160032** (trừ đúng 40000 của card 27).
  - DB `guild_shop_buy`: đúng 1 dòng `fp='27|10|4|200032'`, `gold_bar_after=160032` — idempotency ghi đúng, không nhân bản.
  - Save `HUANDO`: **7 mail `why="LUNAR LUCKY PACKAGE"`, `what="ITEM"`**, `what_value` = `461`×3, `462`×3, `463`×1 → đều tens digit 6 (icon có), đều hundreds digit 4 khớp `char_reward=4` mà người chơi chọn. 10 lượt còn lại ra tiền, ghi thẳng vào `DATA1`/`bp`/`cloud_piece`.
  - Chuỗi `why` dùng English uppercase, khớp quy ước sẵn có (`MOSS & MOON CHARACTER SHOP`, `RUBY GARDEN PURCHASE`, `DAILY ATTENDANCE`).
- Còn lại chưa kiểm chứng:
  - **Đã xác minh bằng mắt 28/09/2026** (người dùng xác nhận guild xong 100%): sau khi bấm nhận ở mailbox, item có vào túi với sub-option đúng. Xem mục "Chốt Guild: hoàn tất 100%".
  - Chưa mua card 26 (4000) trên trình duyệt; mới xác nhận card 27.
  - Client vẽ `/60` bằng `get_lunar_lucky_cnt()` nhưng server không có bộ đếm ⇒ **đã quyết định 28/09/2026 là không giới hạn**, xem mục "Chốt Guild: hoàn tất 100%".
  - `GOLD`/`RUBY` không có nhánh riêng trong `S_POPUP_GACHA_RESULT` → client rơi về nhánh mặc định (icon ruby + số) cho cả hai.
  - Card hero `28/29` **không phải** giá trị client dùng: client để `type_num: 0` và lấy `type_num` thật từ `hero_list`. Đợt sau đã làm card hero bằng `type_num = 1000 + char_num*2` (+1 cho ×10) — xem nhật ký "Bổ sung cùng đợt" bên dưới.
  - Tỉ lệ rút (55/15/10/10/10) copy từ `ITEM_GACHA` của client, chưa đối chiếu với game gốc.
- Việc còn lại và bước tiếp theo: **đã xong hết** (xác nhận người dùng 28/09/2026) — xem mục "Chốt Guild: hoàn tất 100%".

### 28/09/2026 — Bổ sung cùng đợt: làm card hero 1/10 của Guild Shop

- Mục tiêu: người dùng yêu cầu "liệt kê ra các gói có thể mua". Khảo sát cho thấy client **hardcode** `S_GUILD_SHOP.CARDS` (4 card), **không có endpoint liệt kê** — server chỉ có thể chọn `type_num` cho card 1/2. Người dùng chọn hướng làm card hero.
- Đã xác nhận:
  - Card 1/2 có `type_num: 0`; client lấy `type_num` thật từ `POPUP_HEROES[i].type_num_1`/`.type_num_10`, mà `POPUP_HEROES` dựng từ `glo.package.get_hero_list()` = **`hero_list` server gửi ở `cnm_exist_host_in_server.php`**. Trước đây `serve.py` trả `[]` ⇒ popup trống.
  - `glo.package.parse_hero_list` **lọc `enable === true`** — thiếu field này thì không entry nào lọt.
  - `refresh_popup_heroes` tự suy `type_num_10 = type_num_1 + 1` khi thiếu entry `times:10` ⇒ chỉ cần **1 entry `times:1` mỗi hero**, không cần bảng 228 dòng.
  - `S_POPUP_GACHA_RESULT.preload` tải `co_ch<value>.png` cho `reward_info` loại `CHAR`.
  - Popup chọn hero vẽ `profile_icon_<char_num>.png`. Cả `co_ch1..114.png` và `profile_icon_1..114.png` đều tồn tại đủ.
  - Hero theo quy ước sẵn có chỉ được **mail** (`what:"CHAR"`); sở hữu = `DATA2` ∪ mail `CHAR` (`_moss_moon_owned_character_ids`).
- Quyết định đã chốt:
  - `type_num` cho card hero = `1000 + char_num*2` (×1) và `+1` (×10) ⇒ `1002..1229`, không đụng `26/27` hay gói random box `19..52`. Giải mã 1-1 nên client tự chọn hero nào cũng hợp lệ; ngoài biên trả `gs-bad-card`.
  - Dùng lại `MOSS_MOON_CHARACTER_CATALOG` (đã validate đủ `1..114`) thay vì viết danh sách mới.
  - Card hero **không random** — người chơi chọn sẵn trong popup; `reward_info` gồm `times` entry `{"type":"CHAR","value":char_num}`.
  - Vàng trả theo `gold_bar_cnt` như card item; giá 4000 (×1) / 40000 (×10).
- File đã thay đổi: `guild_backend.py` (`GUILD_SHOP_HERO_BASE/PRICE/MAX`, `_shop_hero_type_num`, `_shop_hero_spec`, nhánh hero trong `_shop_act_purchase`, mail CHAR), `serve.py` (`_guild_shop_hero_list()` thay `hero_list: []`), `TESTS/test_guild_shop_http.py` (+8 test).
- Kiểm tra đã chạy: `py_compile` OK · `TESTS.test_guild_shop_http` **26 OK** · `unittest discover` **222 OK** (trước đợt 196).
  - Giới hạn: **đã chạy thật 28/09/2026** (người dùng xác nhận). `hero_list` có 114 phần tử nên **tab hero của `S_PACKAGE_STORE` không còn trống**; thanh toán tiền thật vốn đã chết khi offline. Tỉ lệ rút và giá vẫn là số **tự đặt**, chưa đối chiếu game gốc.

### 28/09/2026 — Gỡ bộ lọc từ cấm trong chat bang hội

- Mục tiêu/phạm vi được yêu cầu: người dùng báo gõ chữ bình thường (ví dụ "HELLO") rồi gửi thì bị chặn, yêu cầu bỏ hết. Chỉ đụng chat bang hội.
- Phát hiện mới và bằng chứng:
  - **Server không hề lọc từ.** `guild_backend.py:_act_send_guild_chat` chỉ kiểm rỗng và `len > GUILD_CHAT_MAX` (70). Đã grep toàn bộ `guild_backend.py` + `serve.py`, không có bảng từ cấm.
  - Chặn nằm ở **client**: `S_GUILD_CHAT_KEYBOARD.check_not_allowed(n)` giữ một mảng ~18 KB từ cấm (tiếng Hàn + tiếng Anh, gồm `"ass"`, `"none"`, `"null"`, `"undefined"`, `"busidol"`) rồi so khớp **substring** trên `n.toLowerCase().replace(/\s/gi,"")`. Khớp là báo `"These characters are not allowed."` và **không gửi**.
  - Vì so khớp substring trên chuỗi đã bỏ khoảng trắng, từ ngắn làm từ dài bị chặn oan — đó là lý do "HELLO" (chứa `hell`) và nhiều từ thường bị chặn. Không phải lỗi encoding hay lỗi DB.
  - Hàm này là **điểm chặn duy nhất**, và có đúng **2** nơi gọi: nút OK của bàn phím trong game (`input_ch`) và bàn phím hệ thống/native (`open_chat_input`). `chat_input_result` gọi thẳng `send_chat`, không qua kiểm tra.
  - Client hiển thị tin nhắn bằng `document.createTextNode(...)`, không phải `innerHTML` ⇒ dù bỏ lọc thì ký tự HTML trong chat không thể chèn script.
- Quyết định đã chốt:
  - **Trung tính hoá hàm** (`=function(n){return!1}`) thay vì xoá hàm: giữ nguyên 2 call site, nên nếu sau này thay client bản gốc thì chỉ cần vá lại đúng một chỗ, và test có thể đòi call site còn nguyên.
  - Vá ở **mức byte**, không dùng `read_text`/`write_text` của Python. Lần vá đầu đã làm hỏng file: `read_text` dịch newline, `write_text` ghi LF, biến CRLF thành LF trên **toàn bộ** 6,5 MB (prefix khớp byte chỉ còn 7.608 byte thay vì 2,2 MB). Đã khôi phục từ backup rồi vá lại bằng `read_bytes`/`write_bytes`; lần này prefix và hậu tố **khớp byte tuyệt đối**, chỉ đúng vùng hàm bị thay.
  - Có sẵn backup: `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js.bak_chatfilter_20260928`.
- File đã thay đổi: `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js` (bỏ 24.624 byte), `TESTS/test_client_assets.py` (file mới, 4 test chặn hồi quy).
- Kiểm tra đã chạy, kết quả và giới hạn:
  - `node --check eldorado_all_20260915.min.js` → **SYNTAX OK** (node v24.18.0 có sẵn).
  - So khớp byte backup ↔ file mới: prefix giống 2.244.414 byte, hậu tố giống tới cuối, chỉ vùng hàm khác.
  - `python -m unittest TESTS.test_client_assets` → **4 OK** (bỏ lọc, mảng từ đã mất, 2 call site còn nguyên, JS vẫn parse).
  - `python -m unittest discover -s TESTS -p "test_*.py"` → **226 OK** (trước đợt 222).
  - Giới hạn: **người dùng đã xác nhận chạy thật trên trình duyệt 28/09/2026** (Ctrl+Shift+R xoá cache JS, từ trước đây bị chặn gửi được). Tôi không tự mở trình duyệt kiểm lại. Chưa giới hạn độ dài chat: vẫn còn trần 70 ký tự của client, không xoá.
- Việc còn lại và bước tiếp theo: **đã xong** — người dùng xác nhận 28/09/2026 (xem mục "Chốt Guild: hoàn tất 100%").

### 28/09/2026 — Chốt Guild: hoàn tất 100%

- Mục tiêu/phạm vi được yêu cầu: người dùng xác nhận **guild đã xong 100%** và yêu cầu ghi vào tri thức. Đợt này **không sửa mã**, chỉ cập nhật tài liệu.
- Phát hiện mới và bằng chứng:
  - Xác nhận của người dùng là bằng chứng duy nhất cho phần "chạy thật trên trình duyệt". Tôi **không** tự mở trình duyệt kiểm lại, nên các dòng dưới đây ghi rõ là xác nhận của người dùng, không phải kiểm tra của tôi.
  - Các điểm từng treo đều được người dùng đóng: (a) mất quyền chủ khi chơi 2 tài khoản cùng lúc — nghi do cookie session dùng chung, đã hết triệu chứng; (b) vòng nhận mailbox của Guild Shop; (c) smoke card hero 1/10 vốn còn để ngỏ.
  - Bằng chứng máy còn giữ được: `serve.log` và các bảng `guild_members`/`guild_shop_buy` của lần smoke card 27 trước đó.
- Quyết định đã chốt:
  - Đánh dấu Guild **đã xong** ở mục 8 và trong bảng trạng thái mục 9, thay vì giữ câu "chưa xác minh xong".
  - **Đóng khoảng trống trần 60 lượt/tháng.** Đợt này tôi còn ghi đây là việc chưa làm và hỏi người dùng. Người dùng trả lời: **không muốn giới hạn**. Đã kiểm lại bằng grep `lunar|lucky` trong `guild_backend.py` và `serve.py` — không có bộ đếm, không có chặn, `lunar_lucky_cnt` chỉ là hằng `0` trong response boot. **Không sửa mã.** Đây là quyết định có chủ ý, không phải khoảng trống kỹ thuật.
  - Các con số do server tự đặt (giá buff, trần duyệt, giá card, tỉ lệ rút 55/15/10/10/10) vẫn được đánh dấu chưa đối chiếu game gốc.
  - Đính chính thêm 1 câu cũ đã lỗi thời: "Guild Shop vẫn dùng stub" (ghi ở mục 27/09/2026) — nay đã có route thật.
- File đã thay đổi: chỉ `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md`.
- Kiểm tra đã chạy, kết quả và giới hạn:
  - **Không chạy test trong đợt này** (không đụng mã). Số test đang xanh vẫn là **226**, giữ nguyên từ đợt trước.
  - Chạy `Select-String -Pattern "lunar|lucky"` trên `guild_backend.py` và `serve.py`: chỉ ra `"LUNAR LUCKY PACKAGE"` (nhãn mail), `luckyPatch` (kỹ năng MOSS & MOON, không liên quan) và `lunar_lucky_cnt: 0` ở `serve.py:3586` (hằng trong response boot). **Không có** chỗ nào so sánh với 60 hay từ chối giao dịch.
  - Đã đọc lại các dòng đã sửa để chắc không mất nội dung cũ. Bài học: một lần sửa trước đã cắt cụt dòng 150; lần này thay dòng bằng script có `assert` trước khi ghi.
- Việc còn lại và bước tiếp theo: **Guild đóng hẳn, không còn mục treo nào.** Hướng kế tiếp người dùng có thể chọn: PvP Classic (`PVP_CLS_2026/*.php`, chưa có route) hoặc 8 endpoint World Boss còn thiếu. Không mở lại Guild trừ khi có yêu cầu mới.

### 28/09/2026 — Gacha Item ngoài Guild (TYPE_NUM 26/27): chuyển sang server-authoritative

- Mục tiêu/phạm vi được yêu cầu: người dùng chọn **hướng A — server authoritative** cho gacha item ngoài Guild. Giá `TYPE_NUM 26 = 1000 BP`, `27 = 10000 BP`, hiện giá trên card và trong popup, không giới hạn lượt.
- Quyết định chốt:
  - **Một nơi duy nhất quyết định giá và roll: server.** `_item_gacha_bp_purchase()` trong `serve.py` tự suy giá từ `TYPE_NUM`, tự roll, tự trả thưởng. Client chỉ gửi `TYPE_NUM` / `GACHA_SLOT` / `GACHA_ID` và lập popup từ `reward_info` trả về.
  - **Client không còn roll cục bộ.** Xoá vòng `for` random, `add_item_refactoring()`, `S_ITEM_GACHA_COMPLETE`, các biến `_gold/_bp/_cl/_ruby`, và `RUBY: S_ITEM_GACHA.need_ruby*-1+_ruby`.
  - **`GACHA_ID` là idempotency key** (bảng `item_gacha_bp_ops`), sinh một lần rồi giữ nguyên qua retry. Cùng ID → replay đúng kết quả cũ, không trừ tiền lần hai. Cùng ID nhưng khác `TYPE_NUM` → `GACHA_REQUEST_CONFLICT`.
  - **Chỉ nhận `STATUS === "SUCCESS"`.** Trước đó điều kiện là `if(_t.STATUS=="ERROR")`; nếu server lỗi rồi trả `"{}"` (nhánh `except` ở `serve.py:3404`) thì `Number(undefined)` ra `NaN` và làm hỏng số dư trên thanh trên cùng. Đã đổi thành `if(_t.STATUS!=="SUCCESS")`.
  - **Mua chỉ nằm trong `min.js`.** `item_gacha_bp_runtime.js` trước đây còn chứa *một* đường mua thứ hai (bọc `menuRun_Run`). Đã gỡ, chỉ giữ phần vẽ icon/giá BP lên card.
- Phát hiện mới và bằng chứng:
  - `serve.py:2885` vẫn nạp `runtime_patches/item_gacha_bp_runtime.js` **sau** `min.js`, và nó chặn `menuRun_Run` trước. Nếu giữ nguyên, có **hai** bản mua cùng làm 1 việc; khi runtime patch không cài được (nó `return false` rồi thử lại 20 lần rồi bỏ qua **không báo lỗi**), client rơi về roll cục bộ cũ trong khi server vẫn roll → cấp thưởng **hai lần**. Vì vậy giữ mua ở `min.js` (không phụ thuộc file ngoài) và xoá phần mua khỏi runtime patch.
  - `_item_gacha_bp_purchase` chạy trong `BEGIN IMMEDIATE` + `SAVE_LOCK`, commit một lần, `except` thì `rollback`. Item trúng được **gửi qua mail** (`why = "LUNAR LUCKY PACKAGE"`), không nằm trong `save["item"]` — nên không còn đường "item miễn phí" như lỗi cũ.
  - Guild Shop **không** bị ảnh hưởng: nhánh `if(this._from_guild_shop){` giữ nguyên, vẫn đi qua `update_guild` với `act:"guild_shop_purchase"` và trả giá bằng `USER.goldbar`. Test chặn hồi quy việc này.
  - Giá hiện ra được nhờ `gacha_item_list` vốn rỗng (`[]`); hai bản vá chỉ ghi đè chuỗi hiển thị, không sửa ảnh PNG.
- File đã thay đổi:
  - `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js` — nhánh 26/27 trong `S_POPUP_PACKAGE_STORE.menuRun_Run`: 3.138 → 1.315 ký tự. File 6.557.537 → 6.555.671 byte.
  - `ELDORADO_WEB/runtime_patches/item_gacha_bp_runtime.js` — 211 → 150 dòng, chỉ còn phần vẽ card.
  - `serve.py` — gỡ khối `bp_cost` chết (và dòng `_v -= bp_cost`) trong `item/update_item_to_server.php`; 26/27 đã bị `_item_gacha_bp_purchase` chặn từ trước nên code này không bao giờ chạy, chỉ là **hai chỗ lệch nhau về giá**.
  - `TESTS/test_item_gacha_bp.py` — **viết lại từ đầu** (bản cũ 292 dòng kiểm bốn thứ không còn tồn tại: giá `1000/9000`, `"ITEM_GACHA",_ruby,{...}`, `index__mobile.html`, và phần mua của runtime patch). Nay 26 test.
- Kiểm tra thực sự đã chạy:
  - `node --check` trên `min.js` và `item_gacha_bp_runtime.js` → **SYNTAX OK** (node v24.18.0).
  - `python -m py_compile serve.py` → **OK**.
  - `python -m unittest TESTS.test_item_gacha_bp` → **26 OK**.
  - `python -m unittest discover -s TESTS` → **257 OK** (trước đợt 226).
  - Test mới phủ: giá 26/27 và biên (999 bị từ chối, 1000 được chấp nhận), `bp`/`gold`/`ruby` client tự khai báo bị bỏ qua, item trúng vào mail chứ không vào storage, `GACHA_SLOT` được chuyển xuống roller, slot ngoài 1..4 rơi về 0, replay cùng `GACHA_ID`, xung đột `GACHA_ID`, caller legacy không có `TYPE_NUM` không bị thu tiền, và các kiểm tĩnh trên `min.js` + phạm vi của runtime patch.
- Bài học kỹ thuật (rút ra sau 3 lần vá hỏng):
  - **PowerShell `String.Substring(-1)` là lỗi KHÔNG terminating.** Script chạy tiếp và ghi ra file nửa vá. Phải đặt `$ErrorActionPreference='Stop'` và kiểm tra neo trước khi cắt.
  - **Đừng tự đếm độ dài chuỗi.** Tôi ghi `$g+32` cho một needle dài **31** ký tự, lệch 1 ký tự làm vỡ toàn bộ ternary và làm hỏng 6,5 MB file. Dùng `$needle.Length`.
  - **`.Split()` của PowerShell nhận regex, không nhận chuỗi literal.** Chuỗi neo chứa `{`/`}` bị cắt sai, dẫn tới neo trỏ nhầm vị trí.
  - File đã hỏng thì khôi phục bằng `eldorado_all_20260915.min.js.bak_before_serverauth_20260928` (tạo trước đợt vá, 6.557.537 byte) — và backup đó nay **đã cũ**, chỉ còn giá trị rollback về bản roll cục bộ.
- Giới hạn:
  - **Chưa chạy thử trên trình duyệt.** Mọi khẳng định về giao diện (giá trên card, popup lật thẻ, số dư trên top-bar) là từ mã và test tĩnh, không phải từ trình duyệt.
  - **Chưa restart server.** `serve.py` đã đổi; người dùng cần restart rồi `Ctrl+Shift+R`.
  - Tỉ lệ rút (item 55% / gold 15% / ruby 10% / BP 10% / cloud 10%) và khoảng tiền thưởng vẫn lấy nguyên từ `roll_lunar_lucky_rewards()` dùng chung với Guild Shop, **chưa đối chiếu game gốc**.
  - `GACHA_ID` được giữ qua retry trong cùng một phiên popup; đóng popup rồi mở lại thì sinh ID mới. Chấp nhận được — người dùng bấm lại là một lượt mới.
  - Bảng `item_gacha_bp_ops` không có bước dọn dẹp; cần thêm khi nếu phát sinh nhiều bản ghi.

## 10. Mẫu cập nhật cho đợt tiếp theo

### YYYY-MM-DD — Tên đợt

- Mục tiêu/phạm vi được yêu cầu:
- Phát hiện mới và bằng chứng:
- Quyết định đã chốt / đề xuất còn mở:
- File đã thay đổi:
- Kiểm tra đã chạy, kết quả và giới hạn:
- Việc còn lại và bước tiếp theo:






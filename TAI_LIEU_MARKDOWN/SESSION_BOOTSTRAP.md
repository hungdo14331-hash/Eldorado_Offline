# SESSION_BOOTSTRAP.md
# Bản đồ nhanh dự án Busidol / Eldorado Offline

> Mục tiêu của file này:
> Giúp một AI/agent/session mới hiểu nhanh kiến trúc, trạng thái và các quy tắc quan trọng của dự án trước khi bắt đầu làm việc.
>
> File này KHÔNG thay thế `TRI_THUC_DU_AN.md`.
> Code hiện tại + test thực tế là nguồn chân lý cuối cùng.
> Tài liệu là bản đồ và phải luôn được đối chiếu với code.

---

# 1. MỤC ĐÍCH DỰ ÁN

Dự án xây dựng một server mô phỏng Busidol / Eldorado để:

- chơi offline hoàn toàn;
- chơi một máy với nhiều tài khoản;
- chơi LAN;
- tiến tới chơi cùng bạn bè qua mạng/tunnel;
- phục dựng các API server cũ mà client game gọi;
- bổ sung các hệ thống mới như RubyFarm và multiplayer.

Đây không còn chỉ là bản patch offline đơn giản.

Về mặt kiến trúc, dự án đang dần trở thành một private-server/remake backend cho client Eldorado gốc.

---

# 2. ĐƯỜNG DẪN DỰ ÁN

Đường dẫn gần nhất:

`E:\UserData\Desktop\TEST ELDORADO\busidol_offline`

Windows.

Đường dẫn có dấu cách.

Không được giả định project vẫn ở `C:\busidol_offline`.

Launcher và script mới phải ưu tiên đường dẫn tương đối dựa trên vị trí file.

---

# 3. THỨ TỰ TÀI LIỆU PHẢI ĐỌC

Trước khi sửa code, đọc theo thứ tự:

1. `AGENTS.md`
2. `SESSION_BOOTSTRAP.md` (file này)
3. `TRI_THUC_DU_AN.md`
4. `KE_HOACH_PHAT_TRIEN.md`
5. `LICH_TRINH_DU_AN.md`
6. `MEM_NEXT_SESSION.md`
7. `memory/session_memory.md`

Sau đó PHẢI đối chiếu với source code hiện tại.

Không được coi thông tin lịch sử cũ là đúng nếu code hiện tại khác.

Ví dụ lịch sử từng có:

- `MINIGAME_CD_SEC = 5`
- `DAILY_RUBY_CAP = 300`

nhưng code mới hơn đã dùng:

- `MINIGAME_CD_SEC = 3`
- `DAILY_RUBY_CAP = 500`

Nguyên tắc:

**Code hiện tại + kiểm chứng runtime > tài liệu mới > tài liệu lịch sử.**

---

# 4. QUY TẮC LÀM VIỆC BẮT BUỘC

Tuân thủ `AGENTS.md`.

Các nguyên tắc đặc biệt quan trọng:

- Giao tiếp bằng tiếng Việt.
- Phân biệt rõ:
  - đề xuất;
  - người dùng đã yêu cầu;
  - đã thực sự làm.
- Trình kế hoạch trước khi sửa nhiều file.
- Chốt phạm vi trước khi triển khai lớn.
- Không tự dừng hoặc restart server của người dùng chỉ để khảo sát.
- Test account / money / battle phải dùng dữ liệu riêng.
- Backup trước khi chuyển đổi dữ liệu thật.
- Không ghi password/token/cookie/admin key/hash vào tài liệu.
- Không tuyên bố "đã kiểm tra" nếu chỉ đọc code.
- Không tuyên bố sửa gameplay nếu chỉ sửa UI/tài liệu.
- Cập nhật `TRI_THUC_DU_AN.md` trước khi bàn giao đợt thay đổi lớn.

---

# 5. MỐC KHÔNG ĐƯỢC ĐỤNG

Mốc baseline:

`M0_BASELINE_20260924_014351`

Tuyệt đối:

- không sửa;
- không xoá;
- không dùng làm nơi thử nghiệm.

Môi trường thử từng có:

`M0_TEST_20260924`

Nếu cần test mới, ưu tiên tạo môi trường hoặc dữ liệu test riêng.

---

# 6. KIẾN TRÚC TỔNG QUÁT

Luồng chính:

```text
BUSIDOL / ELDORADO CLIENT
          |
          | HTTP API có tên .php
          v
     serve.py
 Python ThreadingHTTPServer
          |
     +----+------------------+
     |                       |
     v                       v
 JSON save                SQLite
 offline/single          multi-account
     |                       |
     +-----------+-----------+
                 |
                 v
            Game state
                 |
      +----------+-----------+
      |                      |
      v                      v
 Game client             RubyFarm
                            |
                 +----------+----------+
                 |                     |
                 v                     v
             Minigames               Wallet
```

Điểm quan trọng:

Client vẫn gọi endpoint `.php`.

Không có yêu cầu phải sử dụng PHP server thật.

`serve.py` mô phỏng các endpoint đó.

---

# 7. FILE CỐT LÕI

## Server

`serve.py`

- Python stdlib.
- Dùng `ThreadingHTTPServer`.
- Khoảng 2.800+ dòng ở snapshot gần nhất.
- Là trung tâm backend.
- Route phần lớn endpoint `.php`.
- Quản lý save, wallet, garden, login, minigame, v.v.

Đừng rewrite file này chỉ để sửa một chức năng nhỏ.

---

## Game chính

`ELDORADO_WEB/source_20240722/index__mobile.html`

Client/game bundle quan trọng:

`eldorado_all_20260915.min.js`
(hoặc bundle tương ứng trong bản hiện tại)

Bundle client rất lớn và chứa nhiều protocol/game logic.

Cẩn thận khi patch file minified.

---

## RubyFarm

`ELDORADO_WEB/rubyfarm.html`

Đây không chỉ là một trang UI.

RubyFarm là một module game mới xây bên cạnh client Eldorado gốc.

Có:

- ví Ruby riêng;
- điểm danh;
- ticket;
- cooldown;
- giới hạn Ruby/ngày;
- nhiều minigame;
- quy đổi tài nguyên;
- trạng thái kết nối;
- rút Ruby về game.

RubyFarm đã trải qua nhiều vòng UI/UX redesign.

Không tự thêm gameplay chỉ vì đang sửa giao diện.

---

## Minigame

Nằm ở ROOT PROJECT:

`minigame/generator_repair.html`

`minigame/sudoku.html`

`minigame/rubyfarm_bridge.js`

Lưu ý:

**`minigame/` không nằm trong `ELDORADO_WEB`.**

Đừng tìm sai vị trí.

---

# 8. SAVE VÀ DATABASE

Có hai hướng lưu dữ liệu:

## JSON

Ví dụ:

- `offline_save.json`
- `save_*.json`

Dùng cho chơi offline / test / chế độ cũ.

Các mutation quan trọng thường phải đi qua cơ chế lock và helper.

Có:

`SAVE_LOCK`

và các helper dạng:

- `load_save`
- `store_save`
- `mutate_save`

Không bypass các helper này nếu không có lý do kỹ thuật rõ ràng.

---

## SQLite

Ví dụ:

- `busidol.db`
- `busidol_banbe.db`

Dùng cho hướng multi-account.

Server có các option liên quan dạng:

`--db`

`--require-login`

`--host`

`--add-user`

`--add-pass`

Chuyển server thật sang SQLite chưa nên thực hiện tùy tiện.

Phải:

1. backup;
2. dùng dữ liệu test;
3. xác minh login;
4. xác minh save;
5. xác minh nhiều account;
6. mới cân nhắc migrate dữ liệu thật.

---

# 9. RUBYFARM: ECONOMY HIỆN TẠI

Các giá trị phải đọc lại từ code trước khi sử dụng, nhưng snapshot gần nhất có:

`MINIGAME_CD_SEC = 3`

`DAILY_RUBY_CAP = 500`

Ticket miễn phí/ngày:

`TICKET_FREE_DAILY = 3`

cho từng loại liên quan.

Sudoku:

- có thể mua thêm vé;
- giá khoảng `800 GOLD` trong snapshot gần nhất.

Generator Repair:

- vé miễn phí hằng ngày;
- hiện server không bán vé bổ sung;
- request mua có thể trả trạng thái kiểu `daily only`.

Đừng dựa vào text UI hardcode nếu server đã trả dữ liệu.

---

# 10. RUBY WALLET

RubyFarm có ví riêng:

`wallet_ruby`

Ruby kiếm từ minigame không nhất thiết cộng trực tiếp vào Ruby chính của game.

Flow:

```text
Minigame
   |
   v
wallet_ruby
   |
   | người chơi rút
   v
DATA1[2] / Ruby game chính
```

Đây là boundary quan trọng.

Không bỏ qua wallet và cộng trực tiếp vào game chỉ vì đơn giản hơn.

---

# 11. RESOURCE EXCHANGE

Hệ thống quy đổi đã từng được mở rộng cho:

- GOLD
- RUBY
- BP
- CLOUD
- ESSENCE

Một snapshot dùng giá trị chuẩn kiểu:

```text
GOLD     = 1
RUBY     = 2000
BP       = 20000
CLOUD    = 10000
ESSENCE  = 10000
```

Ngoài ra có thể có override tỷ giá.

Không tự cân bằng lại economy trong nhiệm vụ không yêu cầu.

Nếu sửa exchange:

- kiểm tra server trả rate thế nào;
- kiểm tra UI có hardcode rate không;
- kiểm tra rounding;
- kiểm tra negative/overflow;
- kiểm tra account isolation.

---

# 12. LOGIN / MULTI-ACCOUNT

Dự án đã có hướng multi-account qua SQLite.

Tuy nhiên identity/auth hiện chưa được coi là hoàn thiện.

Rủi ro quan trọng:

API từng tin:

`HOST_ID`

hoặc các identifier do client gửi.

Đã có trường hợp bật `REQUIRE_LOGIN` nhưng vẫn đọc được dữ liệu account khác bằng cách thay `HOST_ID`.

Đây là P0 nếu server được mở cho nhiều người.

Nguyên tắc tương lai:

**Identity phải được derive từ authenticated session phía server, không được tin identifier do client tùy ý gửi.**

---

# 13. ADMIN SECURITY

Đã tái hiện lỗi:

request `/admin` thiếu/sai key trả HTTP 401 nhưng nội dung lỗi có thể làm lộ admin key thật.

Đây là lỗi bảo mật nghiêm trọng nếu server mở cho người khác.

Không bao giờ:

- echo secret;
- log secret;
- ghi secret vào `.md`;
- gửi secret trong error body.

---

# 14. SUDOKU SECURITY

Flow có dạng:

`sudoku_start.php`

→ tạo lượt/challenge

sau đó:

`sudoku_claim.php`

→ claim reward.

Snapshot hiện tại từng có lỗ hổng:

server chưa thực sự verify người chơi đã giải đúng Sudoku trước khi claim.

Do đó client có thể có khả năng gọi claim trực tiếp.

Khi sửa sau này:

- server phải sở hữu/biết solution hoặc proof;
- claim phải gắn với session/challenge;
- session phải one-time;
- phải chống replay;
- reward phải do server quyết định.

Không tin client gửi "I won".

---

# 15. CLOUD GARDEN

Cloud từng có `cloud_nonce`.

Nhưng `GAME_END` đã được tái hiện có thể gửi lặp và nhận kết quả lại.

Cần hướng tới:

- session/nonce một lần;
- atomic consume;
- replay protection.

Sky Garden đã đi xa hơn về pattern này và nên được dùng làm tham khảo.

---

# 16. SKY GARDEN

Sky là phần multiplayer tiến xa nhất.

Đã có hướng SQLite cho:

`sky_sessions`

`sky_leaderboard`

Có test:

`test_sky_leaderboard.py`

Mục tiêu kiến trúc:

- nhiều account nhìn cùng bảng xếp hạng;
- restart server không mất kết quả;
- kết quả một trận không claim lại được;
- session một lần;
- thứ hạng lấy từ server/shared DB.

Khi xây PvP/Cloud/Boss:

**ưu tiên reuse pattern Sky thay vì phát minh kiến trúc hoàn toàn mới.**

---

# 17. PVP

Client có protocol kiểu:

`PVP_2025/*`

Nhưng backend snapshot gần nhất chưa có handler hoàn chỉnh.

Probe từng trả:

```json
{}
```

trong khi client cần các field, đáng chú ý có:

`STATE`

Không coi PvP là "đã có" chỉ vì client có menu/UI.

Khi phát triển PvP:

1. map protocol client;
2. ghi lại endpoint;
3. xác định field bắt buộc;
4. tạo state machine;
5. tạo session server-side;
6. test 2 account thật;
7. chống replay;
8. sau đó mới polish UI.

---

# 18. WORLD BOSS

Tương tự PvP.

Client có protocol:

`BOSS_2026/*`

nhưng backend chưa đầy đủ.

Client có thể yêu cầu `STATE` và nhiều state field khác.

Không trả `{}` giả rồi coi là hoàn thành.

---

# 19. RUBYFARM UI

RubyFarm đã qua ít nhất hai nhóm nâng cấp:

## Nhóm bug/UX

Đã từng sửa:

- text ticket;
- lấy cooldown/cap từ server;
- nút "Về game";
- trạng thái mất kết nối;
- retry;
- ticket requirement;
- loading/error state;
- responsive;
- lỗi `NaN`;
- lỗi thứ tự cập nhật `CONN`.

## Nhóm visual redesign / M5

Đã từng redesign:

- sidebar;
- resource HUD;
- hero;
- minigame card;
- daily check-in;
- typography;
- responsive;
- accessibility;
- hover/focus;
- visual hierarchy.

Do đó:

**Không mặc định RubyFarm vẫn là UI nguyên bản.**

Trước khi prompt "redesign toàn bộ", phải xem screenshot/runtime mới nhất.

Ưu tiên visual review theo vấn đề cụ thể.

---

# 20. BUG WALLET_EARNED QUA NGÀY

Có/đã từng có tình huống:

HUD hiển thị:

`Hôm nay +X/500`

nhưng sau khi sang ngày mới, `X` có thể vẫn là số hôm trước cho tới khi thực hiện một action làm reset daily state.

Nguyên nhân có thể do endpoint đọc wallet không normalize ngày trước khi trả.

Đây là bug UX/state đáng sửa, nhưng cần tái hiện trên code/runtime mới nhất trước.

---

# 21. GAMEPLAY MODIFICATIONS ĐÃ TỪNG TỒN TẠI

Codebase không còn hoàn toàn giống client/server nguyên bản.

Các thay đổi lịch sử đã từng bao gồm những thứ như:

- tăng reward gold;
- thay đổi giới hạn upgrade;
- offline mailbox reward;
- sửa chi phí evolution;
- sửa item gacha;
- tăng inventory cap ở trường hợp cụ thể;
- item roll khi kho đầy → mailbox;
- thay một số gacha tiền thật bằng Ruby;
- sửa lựa chọn item gacha;
- thêm resource exchange.

Vì vậy:

Không "khôi phục về mặc định" nếu chưa hiểu vì sao patch tồn tại.

Một đoạn code trông lạ có thể là customization có chủ đích.

---

# 22. LAUNCHER

Có các launcher dạng:

- `KHOIDONG.bat`
- `ELDORADO_OFFLINE.bat`
- `ELDORADO_PROXY.bat`
- `CHOI_*.bat`

Đợt chuyển project sang thư mục mới đã thay launcher để dùng `%~dp0`.

Script Python hỗ trợ cũng đã/đang ưu tiên `__file__`.

Không đưa đường dẫn tuyệt đối cũ trở lại.

---

# 23. PATH HANDLING

Trong `serve.py` đã có/đã từng thêm helper kiểu:

`_proj_path()`

để resolve các đường dẫn tương đối cho:

- `--save-file`
- `--db`
- `--log`
- `--capture`

Giữ khả năng chạy project từ folder có dấu cách.

Không giả định current working directory luôn là project root.

---

# 24. TESTING PROTOCOL

Khi sửa server/gameplay:

## Không dùng save thật trước.

Tạo:

- save riêng;
- DB riêng;
- port riêng.

Ví dụ các lần trước từng dùng server test ở:

8039
8041

Nhưng không hardcode hai port này.
Chọn port chưa dùng.

## Test tối thiểu:

- server boot;
- endpoint trực tiếp;
- gameplay flow;
- reload/restart nếu liên quan persistence;
- multi-account nếu liên quan identity;
- replay request nếu liên quan reward;
- invalid input;
- console/browser error;
- syntax Python;
- syntax JS nếu có thể.

---

# 25. UI TESTING

Khi sửa RubyFarm hoặc web UI, kiểm tra ít nhất các viewport phổ biến:

- 1920×1080
- 1600×900
- 1366×768
- 1280×720
- khoảng 1024 px
- khoảng 768 px

Kiểm tra:

- horizontal overflow;
- text clipping;
- sidebar;
- HUD;
- hero;
- grid;
- modal;
- iframe minigame;
- button click target;
- disabled/loading/error state;
- reconnect state;
- `NaN`;
- `undefined`;
- `[object Object]`.

Không tuyên bố mobile-ready nếu chưa test thiết bị hoặc ít nhất viewport tương ứng.

---

# 26. PHÂN LOẠI "ĐÃ KIỂM TRA"

Phải nói chính xác mức bằng chứng.

## Chỉ đọc code

Nói:

"Đọc code cho thấy..."

KHÔNG nói:

"Đã kiểm tra."

## Static check

Ví dụ:

- py_compile;
- parser;
- tìm reference ID;
- JS syntax.

Nói rõ là static check.

## Runtime API

Nói:

"Đã chạy server test và gọi endpoint..."

## Browser runtime

Nói:

"Đã kiểm tra trên browser..."

## Thiết bị thật

Chỉ nói "đã thử trên điện thoại thật" nếu thực sự đã thử.

---

# 27. BACKLOG RỦI RO ƯU TIÊN CAO

Trước khi mở server cho nhiều người, đặc biệt chú ý:

### P0/P1

1. Client-controlled `HOST_ID` / identity.
2. `/admin` secret leak.
3. Reward replay.
4. Sudoku claim không verify lời giải.
5. Cloud `GAME_END` replay.
6. Input số âm / malformed ở các endpoint economy.
7. Session binding giữa account và game action.

Các item phải tái hiện trên code hiện tại trước khi sửa.

---

# 28. ROADMAP

Roadmap tổng quát:

- M0 — nền
- M1 — tài khoản / DB
- M2 — Sky
- M3 — PvP
- M4 — Cloud / Boss
- M5 — giao diện
- M6 — nhân vật
- M7 — chơi thử / polish

M0 đã có baseline phục hồi.

M1 đã có lát đầu liên quan Sky leaderboard SQLite.

Không mặc định toàn bộ M1 đã hoàn thành.

---

# 29. TRIẾT LÝ PHÁT TRIỂN NÊN GIỮ

## Server authoritative

Đối với:

- currency;
- rewards;
- battle result;
- leaderboard;
- ticket;
- cooldown;
- nonce/session;

server nên là authority.

Client chủ yếu gửi intent/input.

Không tin các giá trị reward/result quan trọng do client tự khai.

---

## One-time action

Các action thưởng cần pattern:

```text
START
  |
  v
SERVER SESSION / NONCE
  |
  v
PLAY
  |
  v
CLAIM / GAME_END
  |
  v
ATOMIC CONSUME
  |
  +--> reward
  |
  +--> reuse => reject
```

Sky là ứng viên reference implementation.

---

# 30. CÁCH LÀM VIỆC VỚI Q / AI AGENT

Khi giao nhiệm vụ cho agent:

Không viết đơn giản:

> "Sửa PvP."

Hãy yêu cầu:

1. đọc tài liệu;
2. đọc protocol/client;
3. map endpoint;
4. xác định backend hiện có;
5. trình kế hoạch;
6. giới hạn file;
7. dùng test data;
8. triển khai;
9. runtime test;
10. regression test;
11. cập nhật tài liệu.

Nếu nhiệm vụ chỉ UI:

ghi rõ:

> Không thay gameplay/API/database/economy.

Nếu nhiệm vụ chỉ backend:

ghi rõ:

> Không redesign UI ngoài phần cần thiết để test.

---

# 31. KHI PHÁT HIỆN BUG NGOÀI PHẠM VI

Không tự tiện sửa.

Ghi:

- vị trí;
- cách tái hiện;
- mức độ;
- ảnh hưởng;
- đề xuất xử lý.

Sau đó để người dùng quyết định scope.

Ngoại lệ:

Bug bắt buộc phải sửa vì trực tiếp chặn nhiệm vụ hiện tại thì phải giải thích trước.

---

# 32. FILE NÀY PHẢI ĐƯỢC DUY TRÌ THẾ NÀO

`SESSION_BOOTSTRAP.md` chỉ chứa:

- kiến trúc;
- invariants;
- trạng thái cấp cao;
- lỗi/rủi ro lớn;
- workflow;
- bản đồ module.

Không biến nó thành nhật ký từng commit.

Nhật ký chi tiết tiếp tục để trong:

`TRI_THUC_DU_AN.md`

Khi kiến trúc thay đổi lớn, cập nhật file này.

Ví dụ cần cập nhật nếu:

- JSON bị loại bỏ;
- SQLite trở thành mặc định;
- auth được redesign;
- PvP hoàn thành;
- Boss hoàn thành;
- RubyFarm đổi kiến trúc;
- server được tách khỏi `serve.py`.

---

# 33. CHECKLIST CHO SESSION AI MỚI

Trước khi làm bất cứ thay đổi lớn nào, tự trả lời:

- [ ] Tôi đã đọc AGENTS.md chưa?
- [ ] Tôi đã đọc SESSION_BOOTSTRAP.md chưa?
- [ ] Tôi đã đọc TRI_THUC_DU_AN.md mới nhất chưa?
- [ ] Tôi đã đối chiếu code hiện tại chưa?
- [ ] Tôi biết file nào thực sự liên quan chưa?
- [ ] Tôi có đang dựa vào thông tin lịch sử lỗi thời không?
- [ ] Tôi có định dùng save thật không?
- [ ] Tôi có cần backup không?
- [ ] Tôi có đang đụng M0 baseline không?
- [ ] Tôi có đang mở rộng scope ngoài yêu cầu không?
- [ ] Tôi đã trình kế hoạch trước khi sửa nhiều file chưa?
- [ ] Tôi có cách test runtime không?
- [ ] Tôi có test replay/identity nếu liên quan reward không?
- [ ] Tôi có cập nhật TRI_THUC_DU_AN.md sau cùng không?

---

# 34. TÓM TẮT 60 GIÂY

Nếu chỉ có 1 phút:

- Đây là private/offline server remake cho Busidol/Eldorado.
- Backend chính là `serve.py`.
- Client gọi endpoint `.php`, Python mô phỏng chúng.
- Có JSON save và hướng SQLite multi-account.
- RubyFarm là module mới có wallet/ticket/minigame/check-in.
- RubyFarm không chỉ là UI.
- Minigame nằm ở root `/minigame`.
- Sky là multiplayer subsystem tiến xa nhất.
- PvP và Boss chưa hoàn thiện backend.
- Identity dựa vào client identifier là rủi ro lớn.
- Admin endpoint từng leak secret.
- Sudoku từng claim reward không cần verify lời giải.
- Cloud từng replay `GAME_END`.
- Không đụng `M0_BASELINE_20260924_014351`.
- Không dùng save thật để thử.
- Luôn kiểm chứng tài liệu bằng code/runtime.
- Cập nhật `TRI_THUC_DU_AN.md` trước khi bàn giao.

---

# 35. NGUYÊN TẮC CUỐI

Khi không chắc:

**Đừng đoán.**

Đọc code.

Khi code và tài liệu khác nhau:

**xác minh runtime trước khi kết luận.**

Khi nhiệm vụ có nguy cơ ảnh hưởng dữ liệu:

**backup + test riêng trước.**

Khi thấy cơ hội "sửa thêm cho tiện":

**giữ scope.**

Mục tiêu là phát triển project có kiểm soát, không phải thay đổi càng nhiều càng tốt.

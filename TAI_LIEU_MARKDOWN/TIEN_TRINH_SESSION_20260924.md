# TIEN_TRINH_SESSION_20260924.md

> Mục đích: lưu nhanh tiến trình hiện tại để một session AI/Qoder khác có thể tiếp tục công việc mà không phải đọc lại toàn bộ hội thoại.
>
> File này là snapshot tiến trình theo cuộc trao đổi hiện tại, KHÔNG thay thế `TRI_THUC_DU_AN.md`, `SESSION_BOOTSTRAP.md` hoặc code/runtime thật.

---

# 1. Bối cảnh dự án

Dự án: Busidol / Eldorado offline/private server.

Mục tiêu tổng quát:
- chơi offline;
- hỗ trợ nhiều tài khoản;
- tiến tới LAN/multiplayer;
- phục dựng API cũ của game;
- bổ sung RubyFarm, minigame, leaderboard và các hệ thống mới.

Các file/tài liệu quan trọng đã biết:
- `AGENTS.md`
- `SESSION_BOOTSTRAP.md`
- `TRI_THUC_DU_AN.md`
- `KE_HOACH_PHAT_TRIEN.md`
- `LICH_TRINH_DU_AN.md`
- `MEM_NEXT_SESSION.md`
- `memory/session_memory.md`
- `serve.py`
- `ELDORADO_WEB/source_20240722/index__mobile.html`
- `ELDORADO_WEB/rubyfarm.html`
- `minigame/`

Mốc không được đụng:
- `M0_BASELINE_20260924_014351`

Nguyên tắc:
- code hiện tại + runtime test là nguồn chân lý cuối cùng;
- không dùng save thật để test nếu có rủi ro;
- không tự dừng server người dùng;
- không mở rộng scope ngoài yêu cầu;
- cập nhật `TRI_THUC_DU_AN.md` khi bàn giao thay đổi lớn.

---

# 2. Vấn đề UX màn game chính — ĐÃ XỬ LÝ

## 2.1. Căn giữa / scale màn game chính

Màn game chính:
`ELDORADO_WEB/source_20240722/index__mobile.html`

Vấn đề cũ:
- game không tự nằm giữa viewport;
- `util4web.screenAdjust()` của game gốc bị lỗi trong môi trường offline;
- nhánh quảng cáo đọc các phần tử không tồn tại như:
  - `#AD_BOX_LEFT`
  - `#GAME_BOX`
  - `.kakao_ad_area`
- dẫn tới `NaN` trong top/scale;
- game bị neo về góc trái-trên;
- patch OpenCode cũ bị race condition và còn vừa đổi width/height vừa transform scale.

Khảo sát của Q đã xác định nhiều writer cùng ghi vào `#div_body`, gồm:
- `Main.init_platform_GLO`
- `util4web.screenAdjust`
- `loader.js`
- patch OpenCode trong `index__mobile.html`
- `Main.toggleSafeZone`

Giải pháp đã chọn:
- phương án wrapper ngoài `#div_body`;
- giữ logical game space 1280×720;
- wrapper chịu trách nhiệm center + uniform scale;
- không để nhiều lớp scaling chồng nhau;
- không sửa bundle/loader nếu không cần.

Trạng thái hiện tại:
**Q đã hoàn thành việc căn lề / scaling.**

---

# 3. Hệ thống tốc độ 1x / 2x — ĐÃ XỬ LÝ

Vấn đề cũ:
OpenCode monkey-patch:
- `window.setTimeout`
- `window.setInterval`

rồi giảm delay của nhiều timer toàn trang.

Hệ quả:
- bật 2x được nhưng tắt không thực sự về 1x;
- UI có thể báo OFF nhưng timer vẫn nhanh;
- ảnh hưởng cả timer ngoài gameplay;
- có nguy cơ làm nhanh network/retry/UI timer.

Khảo sát xác định game gốc có hệ thống tick riêng:
- `TIMER_INTERVAL`
- `S_GAME.interval()`
- các timer riêng cho Boss/Cloud;
- code test cũ từng thay `TIMER_INTERVAL` để mô phỏng 1x/2x.

Phương án đã chọn:
**B — game-speed controller**, tránh global timer patch.

Hướng:
- dùng `TIMER_INTERVAL` để điều khiển simulation;
- 1x khoảng 50ms;
- 2x khoảng 25ms;
- có xem xét:
  - `BOSS_TIMER_INTERVAL`
  - `CLOUD_GARDEN_TIMER_INTERVAL`
- không reload khi đổi tốc độ;
- không tăng tốc toàn bộ website;
- reload mặc định trở về 1x;
- tránh double loop / double wave scheduler;
- kiểm tra wall-clock và ranking.

Trạng thái hiện tại:
**Q đã hoàn thành cơ chế 1x / 2x.**

---

# 4. Lỗi menu thao tác trong kho item — ĐÃ XỬ LÝ

Phạm vi thật:
**chỉ xảy ra trong kho chứa item của game**, không phải mọi màn hình nhân vật.

Hiện tượng cũ:
- chọn một item / đối tượng trong kho;
- hiện menu:
  - Upgrade
  - Sell
  - Item
  - Level Up
- khi di chuột vào menu:
  - menu biến mất;
  - hover/click rơi xuống item phía sau;
  - cảm giác pointer xuyên qua menu.

Các nguyên nhân đã được yêu cầu Q audit:
- `pointer-events`
- `z-index`
- stacking context
- `mouseover/mouseout`
- `mouseenter/mouseleave`
- event bubbling / propagation
- `document.elementFromPoint()`

Phạm vi sửa:
- chỉ interaction của inventory;
- không đụng viewport;
- không đụng 2x;
- không đụng backend/gameplay.

Trạng thái hiện tại:
**vấn đề đã được xử lý xong.**

---

# 5. RubyFarm / UI asset — ĐANG TẠM DỪNG

Người dùng không hài lòng với việc giao diện dùng nhiều icon kiểu mô phỏng/emoji.

Mong muốn mới:
- asset thật;
- thân thiện;
- dễ gần;
- không mang cảm giác “AI-generated”;
- học tinh thần từ các game casual/fantasy nổi tiếng nhưng không sao chép asset;
- ưu tiên asset sheet / sprite atlas thay vì hàng chục ảnh rời.

Đã tạo thử:
1. bộ icon/token/status/minigame asset sheet;
2. bộ panel/button/frame/status chip asset sheet.

Hướng kỹ thuật đã thống nhất:
- có thể dùng sprite sheet / texture atlas;
- không cần tách từng ảnh riêng;
- nên có file JSON mapping:
  - x
  - y
  - width
  - height
- dùng 9-slice cho panel/button/frame co giãn;
- nên có padding/extrude để tránh texture bleeding.

Chưa triển khai vào project.

---

# 6. Các vấn đề kỹ thuật lớn còn được biết

## 6.1. `loader.js` hardcode port 8023

Trong khi offline server chính thường chạy 8029.

Cần audit trước khi sửa vì 8023 có thể liên quan proxy mode.

Hướng mong muốn lâu dài:
- same-origin path;
- hoặc `location.origin`;
- tránh hardcode port nếu có thể.

---

## 6.2. Kết nối server cũ còn sót trong bundle

Bundle có các URL/WebSocket cũ.

Chưa kết luận runtime có thực sự kết nối ra ngoài hay không.

Nên có một đợt audit riêng:
**OFFLINE MODE có request nào thoát khỏi localhost/private server hay không?**

---

## 6.3. Auth / HOST_ID

Đã từng tái hiện:
- API tin `HOST_ID` do client gửi;
- có thể đọc dữ liệu account khác ngay cả khi bật login.

Đây là ưu tiên cao trước multiplayer/public server.

---

## 6.4. `/admin` leak key

Đã từng tái hiện:
- request sai/thiếu key trả 401;
- nội dung lỗi có thể làm lộ admin key thật.

Cần sửa trước khi mở server cho người khác.

---

## 6.5. Sudoku claim

Đã từng có trạng thái:
- server chưa verify lời giải Sudoku;
- có thể claim reward mà không chứng minh solve đúng.

Cần server-authoritative validation.

---

## 6.6. Cloud replay

Đã từng tái hiện:
- `GAME_END` gửi lặp;
- reward có thể được xử lý nhiều lần;
- nonce/session cần one-time consume.

---

## 6.7. `wallet_earned` qua ngày

RubyFarm HUD có thể hiển thị số “Hôm nay” của ngày trước cho tới khi có action reset state.

Cần tái hiện lại trên code/runtime mới nhất trước khi sửa.

---

# 7. Server control / admin

Hiện dự án có:
- `serve.py`
- launcher `.bat`
- `/admin`
- CLI flags
- SQLite / JSON save
- nhiều mode khởi chạy.

Đã thảo luận hướng tương lai:
- biến `/admin` thành Server Control Panel thực sự;
- tách config khỏi code;
- có thể học tư duy từ:
  - Minecraft server
  - WoW/private-server GM tools
  - live-service game backend

Gợi ý tương lai:
`server_config.json`

để quản lý:
- port
- login
- RubyFarm cap
- cooldown
- ticket
- exchange
- event

Nhưng chưa triển khai.

---

# 8. Thứ tự ưu tiên đề xuất tiếp theo

Nếu tiếp tục ưu tiên trải nghiệm chơi:

1. Audit lại hitbox/input sau khi viewport wrapper mới đã ổn.
2. Audit `loader.js` / port 8023 vs 8029.
3. Audit request mạng ngoài localhost khi chạy offline.
4. Tiếp tục RubyFarm asset system.
5. Chuẩn hóa sprite atlas + JSON mapping + 9-slice.
6. Sau đó mới mở rộng polish UI.

Nếu chuẩn bị multiplayer/public server:

1. Sửa identity / `HOST_ID`.
2. Sửa `/admin` secret leak.
3. Sửa replay protection.
4. Verify Sudoku.
5. Sửa Cloud nonce.
6. Migrate/test SQLite thật.

---

# 9. Trạng thái ngắn gọn

ĐÃ XONG:
- căn giữa / scaling màn game chính;
- 1x ⇄ 2x không cần reload;
- lỗi menu action trong kho item.

ĐANG TẠM DỪNG:
- RubyFarm asset redesign.

CHƯA LÀM / CẦN AUDIT:
- loader hardcode 8023;
- outbound connection cũ;
- auth/identity;
- admin leak;
- Sudoku validation;
- Cloud replay;
- wallet daily reset UX.

---

# 10. Nguyên tắc cho session tiếp theo

Trước khi làm tiếp:

1. đọc `AGENTS.md`;
2. đọc `SESSION_BOOTSTRAP.md`;
3. đọc file snapshot này;
4. đọc `TRI_THUC_DU_AN.md`;
5. đối chiếu code hiện tại;
6. không giả định trạng thái trong snapshot vẫn đúng nếu Q đã sửa tiếp sau thời điểm tạo file.

Khi có mâu thuẫn:

**code hiện tại + runtime test > snapshot này.**

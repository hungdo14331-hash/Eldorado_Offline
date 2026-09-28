# Kế hoạch hoàn thiện Eldorado / Busidol Offline

Ngày lập: 24/09/2026. Trạng thái: kế hoạch đề xuất; chưa triển khai thay đổi game hoặc database.

Tài liệu đi kèm: [lịch trình và sơ đồ](LICH_TRINH_DU_AN.md), [tri thức tích lũy sau mỗi đợt](TRI_THUC_DU_AN.md). Bộ skill ưu tiên đã được cài ngày 24/09/2026; nguồn và phiên bản ghi trong file tri thức.

## 1. Phạm vi đã thống nhất

- PvP đợt đầu: đấu với đội hình đã lưu của người chơi khác, không cần hai người cùng online.
- Đợt chơi thử đầu tiên: 5–20 người bạn.
- Mục tiêu cốt lõi: PvP, Sky Garden, Cloud Garden và World Boss có vòng chơi hoàn chỉnh, kết quả được lưu và bảng xếp hạng chung hoạt động trong game.
- Mục tiêu tiếp theo: nâng cấp giao diện, nhân vật, tính năng, sửa lỗi, trải nghiệm, bảo mật tài khoản, database và chuẩn bị mời bạn bè.
- Các luật điểm, mùa giải, phần thưởng và phong cách hình ảnh bên dưới là đề xuất để duyệt khi đến giai đoạn tương ứng.

## 2. Hiện trạng đã kiểm tra từ mã và schema

| Thành phần | Hiện trạng | Phần còn thiếu |
|---|---|---|
| Database | `busidol.db` và `busidol_banbe.db` đều có `accounts(id,pw_hash)` và `saves(id,payload)` | Lịch sử trận, mùa, điểm chung, phiên đăng nhập, giao dịch thưởng |
| Sky Garden | Có API xem bảng, vào trận, gửi kết quả; `sky_wave` lưu trong save cá nhân | Bảng chỉ có người hiện tại, hạng luôn 1; mã trận được tạo nhưng chưa kiểm tra ở bước ghi kết quả |
| Cloud Garden | Có lượt vé/ruby, lưu `cloud_score` và trả Cloud Piece | Bảng chỉ có người hiện tại, hạng luôn 1; `GAME_END` chưa ràng buộc và kết thúc phiên trận để chống nhận lại thưởng |
| PvP | Client gọi `PVP_2025/*`, còn có PvP Classic và các API cũ | Chưa thấy handler riêng tương ứng trong `serve.py`; cần xác định nhánh thực sự đang dùng trước khi nối server |
| World Boss | Client có đường gọi `BOSS_2026/*` và `Boss/*` | Chưa thấy handler riêng; `cur_boss_hp` trong thông tin sự kiện đang trả 0 |
| Tài khoản | Có kiểm tra mật khẩu tại login | Các API vẫn chọn tài khoản theo ID/cookie do client gửi, chưa có phiên xác thực đáng tin cậy |
| Giao diện | Game gốc cộng các phần vá ở HTML và JavaScript nén | Cần gom phần tùy chỉnh, xử lý màn hình nhỏ, trạng thái lỗi và luồng điều hướng |

Các vị trí chính: `serve.py:128` (schema), `:1726` (Sky), `:1839` (Cloud), `:2470` (request/tài khoản); `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js` (giao thức client).

Ghi chú cũ nói hai chế độ Garden đã hoạt động, nhưng điều đó chưa đồng nghĩa có bảng xếp hạng nhiều tài khoản. Kiểm tra lần này là đọc mã và schema; chưa xác nhận toàn bộ gameplay hay phiên bản server đang chạy.

## 3. Thứ tự triển khai

### M0 — Chốt bản nền và môi trường thử

1. Ghi nhận những sửa đổi hiện có; tạo mốc phục hồi gồm mã, cấu hình, save và bản sao SQLite nhất quán.
2. Xác định database nào đang phục vụ người chơi; chọn một database chính cho chế độ nhiều tài khoản.
3. Dựng môi trường thử riêng cổng và dữ liệu. Tạo ít nhất ba tài khoản thử có sức mạnh khác nhau.
4. Lập danh sách API cho từng chế độ: dữ liệu gửi, dữ liệu trả, kiểu dữ liệu, lỗi và các nhánh phiên bản client.
5. Lập sổ lỗi với bước tái hiện, ảnh hoặc log phù hợp, mức ưu tiên và kiểm tra sau sửa.

**Hoàn thành khi:** phục hồi bản sao thành công; môi trường thử không ghi vào dữ liệu thật; xác định được luồng mở bảng → vào trận → kết thúc của từng chế độ.

### M1 — Bảo mật và nền dữ liệu

1. Tạo phiên đăng nhập ngẫu nhiên, có hạn dùng, thu hồi khi đăng xuất/đổi mật khẩu; server xác định tài khoản từ phiên. ID trong request không được cho phép chuyển sang tài khoản khác.
2. Cookie HttpOnly, SameSite phù hợp và Secure khi dùng HTTPS; chống yêu cầu giả mạo cho thao tác thay đổi dữ liệu, giới hạn thử đăng nhập, che mật khẩu/token khỏi log.
3. Chuyển mật khẩu từ SHA-256 đơn sang Argon2id; nâng cấp hash khi đăng nhập hợp lệ, có quy trình quản trị đặt lại mật khẩu cho nhóm bạn. Không cần thêm email ngay ở bản thử.
4. Sửa trang quản trị: không trả khóa trong thông báo lỗi; có quyền quản trị và xác thực riêng; không tin `Host` để xác định người truy cập nội bộ.
5. Kiểm soát đường dẫn file được phục vụ, giới hạn kích thước request và kiểm tra đầu vào cho tiền, vé, ngày, điểm.
6. Thêm migration có phiên bản, giao dịch nguyên tử, ràng buộc duy nhất và chỉ mục; xử lý lỗi SQLite rõ ràng thay vì báo thành công khi lưu thất bại.
7. Tách dần phần tài khoản, dữ liệu, chế độ chơi khỏi hàm xử lý lớn trong `serve.py`; giữ đường API cũ làm lớp tương thích với game.
8. Đặt ra một nguồn dữ liệu chính cho điểm/thưởng. Các API ghi save cũ không được ghi đè số dư hoặc thành tích do server quản lý.

**Hoàn thành khi:** A không đọc/ghi được dữ liệu của B bằng cách đổi ID/cookie; request chưa đăng nhập bị chặn; không còn khóa/mật khẩu trong phản hồi/log; migration và phục hồi được kiểm tra trên bản sao.

### M2 — Bảng xếp hạng chung, làm Sky Garden trước

1. Xây phần lưu mùa, trận và thành tích dùng chung, rồi nối vào API Sky có sẵn.
2. Luồng trận: tạo trận và chốt cấu hình/chi phí → chơi → xác thực kết quả → cập nhật thành tích/thưởng trong cùng giao dịch → trả hạng thật.
3. Ràng buộc mã trận với tài khoản, chế độ, mùa, wave bắt đầu, thời hạn và trạng thái. Gửi lại cùng kết quả phải trả kết quả đã lưu; kết quả mâu thuẫn bị từ chối.
4. Kiểm tra giao thức Sky thực tế: nếu một lượt gửi nhiều wave thì khóa theo `(trận, wave)` và tiến trình hợp lệ; không đóng cả lượt ngay ở wave đầu.
5. Đọc bảng chung, có Top 50 và hạng của tôi dù ngoài Top 50. Người chưa có kết quả hiển thị chưa xếp hạng.
6. Đề xuất xếp Sky theo wave cao nhất; hòa điểm thì người đạt mốc sớm hơn đứng trước, cuối cùng dùng ID ổn định. Lưu thời điểm thật, không lấy ngày mở bảng làm ngày đạt điểm.
7. Tạm giữ thành tích cũ để xem lịch sử, đánh dấu là dữ liệu cũ chưa kiểm chứng. Đề xuất mùa thử mới để mọi người có điều kiện thi đấu rõ ràng, không xóa save cũ.

**Hoàn thành khi:** ba tài khoản thấy cùng thứ tự; thành tích tốt hơn cập nhật, kém hơn không làm mất kỷ lục; F5/đăng nhập lại/khởi động lại server vẫn giữ điểm; gửi trùng hoặc đồng thời không cộng lặp; điểm thiếu trận hợp lệ bị từ chối.

### M3 — PvP đấu đội hình đã lưu

1. Xác định PvP thường đang dùng nhánh nào; triển khai một nhánh đầy đủ trước, PvP Classic đưa vào danh sách sau.
2. Cho lưu đội hình phòng thủ; server lấy nhân vật, trang bị và nâng cấp từ dữ liệu sở hữu hợp lệ. Không tin chỉ số tấn công/phòng thủ tự gửi lên.
3. Ghép đối thủ từ người khác, ưu tiên sức mạnh hoặc điểm gần nhau; không tự đấu mình. Khi quá ít người thì thông báo rõ; nếu dùng đội mẫu phải ghi rõ đó là đội mẫu.
4. Chốt bản sao đội hình và phiên bản cân bằng lúc tạo trận, để thay trang bị giữa trận không đổi đối thủ.
5. Bổ sung mã trận vào giao thức nếu client hiện chưa gửi. Server quyết định điểm và thưởng từ luật đã chốt, không cộng trực tiếp `SCORE` tùy ý từ client.
6. Bản đầu đề xuất điểm thắng/thua đơn giản, lịch sử trận, số lượt/ngày và hạn chế lặp một đối thủ để farm điểm; trị số cụ thể chốt sau khi thử chiến đấu.
7. Hoàn thiện bảng hạng PvP, hạng cá nhân, kết quả thắng/thua và nhận thưởng mùa một lần.

**Hoàn thành khi:** A đấu được đội hình B khi B offline; kết quả đúng tài khoản và lưu sau restart; không cộng lại điểm/thưởng khi gửi trùng; thiếu đối thủ không làm treo game.

**Giới hạn cần giải quyết:** mã trận và kiểm tra điểm hợp lý chỉ ngăn một phần gian lận. Vì chiến đấu hiện ở trình duyệt, muốn xác nhận thắng/thua chắc chắn cần mô phỏng lại hoặc xác minh chiến đấu trên server. Đánh giá khả năng này ngay ở M0–M3; nếu chưa có, bản thử phải ghi nhận đây là giới hạn, không tuyên bố chống gian lận hoàn chỉnh.

### M4 — Cloud Garden và World Boss

**Cloud Garden:** dùng bảng hạng chung theo điểm cao nhất mỗi mùa; hoàn thiện vé miễn phí, phí ruby, thời gian trận và trả Cloud Piece. Máy chủ kiểm tra phiên, thời gian và điểm; xử lý gửi lại kết quả, hết giờ, mất kết nối. Tách điểm xếp hạng khỏi số Cloud Piece có thể chi tiêu. Thay các ngày/mốc thời gian cố định bằng lịch mùa thật.

**World Boss:** đề xuất một boss chung theo đợt, HP và lịch mở/đóng lưu trên server; người chơi đánh riêng rồi đóng góp sát thương hợp lệ vào boss chung. Lưu lịch sử đóng góp, bảng sát thương, lượt vào, thưởng tham gia và thưởng kết thúc đợt. Nối đúng `BOSS_2026` hoặc nhánh thực tế, không chỉ mở nút vào chế độ.

Khi hai người kết thúc cùng lúc, cập nhật HP trong giao dịch, không để âm hoặc trừ lặp. Chốt quy tắc sát thương vượt HP còn lại: đề xuất chỉ tính phần đóng góp thực tế vào HP chung cho bảng hạng của đợt. Trận đang chơi lúc boss chết/hết giờ phải có quy tắc xử lý và thông báo rõ.

**Hoàn thành khi:** Cloud dùng đúng vé/thời gian/thưởng; hai tài khoản góp sát thương vào cùng một boss; HP, bảng hạng và lịch sử còn sau restart; kết thúc mùa/đợt không phát thưởng lặp, kể cả khi server tắt đúng thời điểm kết thúc.

### M5 — Giao diện, tính năng và trải nghiệm

1. Thống nhất phong cách cho đăng nhập, chọn chế độ, bảng hạng, kết quả trận, RubyFarm và cửa hàng; giữ hình ảnh game phù hợp hiện có.
2. Bảng hạng: Top 3, tên, điểm, hạng của tôi, mùa hiện tại, thời điểm kết thúc, luật và phần thưởng. Có trạng thái đang tải, chưa có điểm, lỗi và thử lại.
3. Chọn chế độ: hiển thị lượt còn lại, chi phí và điều kiện tham gia trước khi vào; chế độ chưa sẵn sàng có thông báo rõ.
4. Cải thiện bố cục máy tính/điện thoại, nút bấm, cỡ chữ, thông báo tiếng Việt và đường quay lại game từ trang phụ.
5. Luồng người mới: tạo/nhận tài khoản → đăng nhập → hướng dẫn ngắn → chơi trận đầu → xem điểm/thưởng.
6. Thêm hồ sơ, đổi mật khẩu, đăng xuất, lịch sử trận, trạng thái kết nối và cách báo lỗi. Các tính năng lớn như bang hội/chat/PvP trực tiếp để sau bản thử này.
7. Đồng bộ thời gian trận theo server. Rà soát nút tốc độ 2x hiện đang bọc timer toàn trang; tách timer giao diện/mạng khỏi chiến đấu. Chốt luật tốc độ cho chế độ xếp hạng trước khi mở mùa.

**Hoàn thành khi:** người chơi mới tự vào được một chế độ và hiểu điểm/thưởng; lỗi mạng không tạo trận hoặc thu phí hai lần; giao diện dùng được trên các màn hình thử; không còn điều khiển phát triển lẫn vào giao diện người chơi.

### M6 — Thiết kế và tích hợp nhân vật mới

1. Làm một nhân vật mẫu hoàn chỉnh trước: vai trò, ngoại hình, độ hiếm, kỹ năng, chỉ số, cách sở hữu và nâng cấp.
2. Kiểm tra cách engine đăng ký ID, giới hạn mảng, bộ sưu tập, save, đội hình, trang bị và tiến hóa trước khi mở rộng dữ liệu nhân vật.
3. Tạo đủ tài nguyên: chân dung, icon, hoạt ảnh chờ/di chuyển/tấn công/trúng đòn và hiệu ứng theo định dạng engine yêu cầu.
4. Tích hợp vào trận thật, lưu/tải và đội hình PvP; thử cân bằng với nhân vật hiện có và đo ảnh hưởng tới tốc độ tải.
5. Chốt phiên bản cân bằng khi mở mùa; dữ liệu trận lưu phiên bản để giải thích kết quả sau các lần chỉnh sức mạnh.

**Hoàn thành khi:** nhân vật xuất hiện đúng, chơi được, không thiếu khung hình, lưu được, dùng được ở các chế độ và không tạo lợi thế vượt mức đã thống nhất. Sau đó mới mở rộng bộ nhân vật.

### M7 — Đợt thử kín và mời bạn bè

1. Chuẩn bị bản phát hành có phiên bản, trang hướng dẫn ngắn, hình/clip gameplay và nội dung lời mời để người dùng chia sẻ.
2. Đợt A: 3–5 người thử đăng nhập, trận, bảng hạng và lỗi mạng. Đợt B: mở tới 5–20 người sau khi sửa lỗi nghiêm trọng.
3. Chọn nơi chạy và giờ hoạt động, cấu hình HTTPS, link truy cập, sao lưu, log đã che thông tin nhạy cảm và phương án quay về bản cũ.
4. Kiểm tra tải theo số người chơi đồng thời và tần suất ghi thực tế; không suy ra khả năng phục vụ chỉ từ số tài khoản.
5. Theo dõi tỷ lệ vào game/thành công lưu trận, thời gian tải bảng hạng, lỗi ghi DB, giao dịch thưởng trùng và phản hồi người chơi.
6. Có cách gửi phản hồi, danh sách lỗi đã biết và thông báo cập nhật. Không tự gửi lời mời hoặc công khai máy chủ trong giai đoạn lập kế hoạch.

**Hoàn thành khi:** không còn lỗi chặn đăng nhập, mất save, truy cập nhầm tài khoản hoặc cộng thưởng trùng trong bộ kiểm tra và đợt thử; sao lưu phục hồi được; bạn bè truy cập và hoàn thành trận bằng hướng dẫn đã chuẩn bị.

## 4. Thiết kế database đề xuất

Giữ SQLite cho bản thử trên một máy chủ, đánh giá lại khi có số liệu tải. SQLite chỉ có một lượt ghi đồng thời trên mỗi database; ưu tiên giao dịch ngắn và kiểm tra tranh chấp ghi. Đây là lựa chọn thiết kế cho dự án này, không phải cam kết đủ tải chỉ dựa trên mốc 20 người. [Tài liệu SQLite](https://www.sqlite.org/whentouse.html)

| Bảng/nhóm | Vai trò và ràng buộc chính |
|---|---|
| `accounts`, `sessions` | Tài khoản, hash mật khẩu, quyền, phiên có hạn và thu hồi; không lưu token nguyên văn nếu có thể dùng hash |
| `saves`, `player_profiles` | Giữ dữ liệu game cũ để tương thích; hồ sơ công khai tách khỏi dữ liệu tài khoản riêng |
| `seasons` | Chế độ, thời gian mở/đóng, trạng thái, phiên bản luật |
| `battle_sessions`, `battle_results` | Người chơi, đối thủ, đội hình chốt, thời điểm, trạng thái, khóa kết quả duy nhất; Sky có thể cần kết quả từng wave |
| `leaderboard_entries` | Một thành tích mỗi `(mode, season, account)`; điểm, thời điểm đạt, trận nguồn; chỉ mục cho thứ tự hiển thị |
| `defense_teams` | Đội hình phòng thủ và phiên bản dữ liệu PvP |
| `boss_events`, `boss_contributions` | Boss theo đợt, HP, sát thương đã chấp nhận; một đóng góp hợp lệ cho mỗi kết quả trận |
| `reward_claims`, `currency_ledger` | Khóa thưởng duy nhất theo người/nguồn/mùa; nhật ký cộng/trừ với nguyên nhân và nguồn trận |
| `schema_migrations` | Phiên bản chuyển đổi dữ liệu đã áp dụng |

Kết quả trận là dữ liệu nguồn; bảng hạng là tổng hợp có thể tính lại. Ghi kết quả, điểm, thưởng và trạng thái trận phải thành công cùng nhau. Chốt thứ tự khóa và giao dịch; không giữ lock trong khi gọi mạng hoặc tải tài nguyên.

Khi chuyển từ save JSON sang bảng riêng: chọn nguồn chính cho từng trường, chuyển dữ liệu có kiểm tra, lớp tương thích chỉ đọc/ghi qua nguồn đó. Tránh giữ hai số dư độc lập rồi đồng bộ tùy lúc. Backup trước migration, kiểm tra số tài khoản/tiền/đội hình sau migration và thử khôi phục trước khi áp dụng thật.

## 5. Luật xếp hạng cần chốt

| Chế độ | Đề xuất bản đầu | Cần quyết định trước khi mở mùa |
|---|---|---|
| Sky Garden | Wave cao nhất | Mùa thử, luật tiếp tục wave, vé/phí, thưởng |
| PvP | Điểm theo kết quả đã xác nhận | Điểm thắng/thua, giới hạn lượt và lặp đối thủ, cách ghép |
| Cloud Garden | Điểm cao nhất trong mùa | Thời lượng, lượt, phí, tỷ lệ Cloud Piece |
| World Boss | Tổng đóng góp sát thương hợp lệ mỗi đợt | HP, thời gian đợt, giới hạn lượt, thưởng khi boss chết/hết giờ |

Đề xuất hòa điểm: đạt mốc trước đứng trước, sau đó ID ổn định. Đề xuất mùa xếp hạng 7 ngày để dễ thử reset/thưởng; boss dùng lịch đợt riêng. Lưu thời gian UTC, hiển thị và tính mốc ngày/mùa theo Asia/Ho_Chi_Minh. Mùa cũ được lưu lịch sử, mùa mới có bản ghi mới. Đây là các mặc định đề xuất, chưa phải luật đã được người dùng chốt.

## 6. Danh sách lỗi ưu tiên xuyên suốt

- P0: giả mạo tài khoản, lộ khóa quản trị, mất/ghi đè save, gửi lại nhận thưởng hoặc cộng điểm lần nữa.
- P1: hạng luôn 1; PvP/Boss thiếu handler; autoplay nhận số ngày âm; Sudoku hết hạn 15 phút dù mức khó cho 20/25 phút; claim minigame chưa xác minh kết quả chơi.
- P1: các API cập nhật save/tiền cũ có thể vượt qua luật mới; cần rà soát toàn bộ đường thay đổi số dư và kết quả.
- P1: timer 2x có thể ảnh hưởng thời gian chế độ thi đấu; cần tái hiện và kiểm tra cách bật/tắt trước khi quyết định sửa.
- P2: bố cục, cỡ chữ, thông báo chưa rõ, ảnh thiếu, liên kết phụ và điều hướng.

Mỗi mốc xử lý lỗi thuộc phạm vi của nó. Các thay đổi bảo mật, giao dịch tiền và bảng hạng cần kiểm tra tự động có ý nghĩa; giao diện cần thử tương tác thực tế.

## 7. Cửa kiểm tra trước khi phát hành

- Đăng nhập đúng/sai, hết phiên, đổi mật khẩu, giả ID và tài khoản không có quyền.
- Hai người cùng ghi kết quả; gửi trùng, sai trận, sai chế độ, quá hạn, điểm âm hoặc bất hợp lý.
- Mất mạng sau khi server đã ghi nhưng client chưa nhận; thử lại không thu phí/thưởng hai lần.
- Tắt và khởi động lại môi trường thử, đóng/mở mùa, server vắng mặt ở mốc reset, nhận thưởng mùa nhiều lần.
- Người chưa xếp hạng, hòa điểm, ngoài Top 50; bảng của các tài khoản phải thống nhất.
- Save cũ, migration, phục hồi backup; tài sản người chơi vẫn đúng.
- Nhân vật/đội hình thay đổi sau khi trận bắt đầu; trận phải dùng bản đã chốt.
- Máy tính/điện thoại, tải asset thiếu, tên có ký tự đặc biệt, thông báo lỗi và thử lại.

## 8. Mốc bàn giao đầu tiên và quyết định còn mở

**Mốc đầu tiên:** hoàn thành M0, phần M1 cần cho định danh và giao dịch, rồi M2 Sky Garden. Bàn giao một bảng xếp hạng thật trong game, có dữ liệu nhiều tài khoản, lưu bền và chống ghi kết quả trùng. Sau đó dùng nền này cho PvP, Cloud Garden và World Boss.

Chưa chốt lịch ngày cứng: khối lượng lớn nhất chưa rõ là định dạng/giao thức client nén, xác minh chiến đấu và khả năng mở rộng nhân vật. Theo yêu cầu bổ sung, `LICH_TRINH_DU_AN.md` đưa khoảng dự kiến 22–40 ngày công cho toàn bộ các mốc; phải hiệu chỉnh sau M0 bằng đầu việc và tiêu chí đã kiểm chứng.

Các quyết định hỏi khi cần: lịch mùa và thưởng; xử lý tài khoản đã tăng tài nguyên để thử; phong cách giao diện và nhân vật mẫu; máy chủ/giờ mở/ngân sách vận hành. Mặc định đề xuất là giữ save cũ và tách mùa hoặc tài khoản thử sạch cho thi đấu.

Tham chiếu bảo mật khi triển khai: [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) cho vòng đời phiên/cookie; [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) cho hash mật khẩu. Các tài liệu này hướng dẫn triển khai, không thay thế kiểm tra các luồng game hiện có.

# Giao thức Cloud Garden, PvP và World Boss — môi trường M0

Ngày kiểm tra: 24/09/2026. Dùng server tạm `127.0.0.1:8049`, SQLite và tài khoản giả trong `M0_TEST_20260924`. Server thật không bị thay đổi.

## Cloud Garden

Một endpoint xử lý mọi hành động:

`POST /ELDORADO_WEB/cloud_garden/cloud_garden_ranking.php`

Client gửi `ID`, `VER_DATE`, `MODE`, `LANG`, `ID_PLATFORM`, `TEAM`, `NAME`, `LEVEL`, `SCORE`, `RUBY`, `DECK`, `ITEM`, `GAME_NONCE`. Server hiện dựa vào cookie hoặc `HOST_ID` để chọn save; trường `ID` của client không được bộ định tuyến tài khoản đọc trực tiếp.

Các mode trong handler:

- `RANKING_GET`: trả `RANKING_ARR`, `MY_SCORE`, `MY_RANKING`, vé, chi phí, thời gian và cấu hình mùa.
- `GAME_TICKET`: dùng lượt miễn phí và tạo `cloud_nonce`.
- `GAME_RUBY`: trừ ruby và tạo `cloud_nonce`.
- `GAME_END`: nhận `SCORE`, cập nhật điểm tốt nhất và cộng Cloud Piece.

Kết quả chạy thật trên tài khoản giả:

- Bảng chỉ có một dòng của chính người gọi, `MY_RANKING=1`.
- Gửi thẳng `GAME_END`, không mở lượt trước, với nonce giả và score 400 vẫn thành công.
- Số Cloud Piece tăng `4245 → 4265`; gửi lại đúng kết quả/nonce giả lần hai tăng tiếp `4265 → 4285`.
- Điểm tốt nhất lưu thành 400.

Như vậy `GAME_END` chưa xác thực/tiêu thụ phiên trận và chưa chống phát thưởng lặp.

## PvP 2025

Client đang gọi:

1. `PVP_2025/get_pvp_ranking.php`
2. `PVP_2025/enter_pvp_game.php`
3. `PVP_2025/update_pvp_result.php`

Request bảng/vào trận chứa `HOST_ID`, ngôn ngữ, tên, level, đội hình, item, HP/level tháp, sức mạnh/level/tick tên lửa, phiên bản và `MODE` khi vào trận. Request kết quả chứa `HOST_ID`, đội hình, `SCORE`, `RESULT`, phiên bản và `ETC`.

Cả ba endpoint trả `{}` trong môi trường offline không có capture. Client lại đọc `STATE`, nên nhánh PvP 2025 chưa có hợp đồng phản hồi tối thiểu và chưa thể coi là hoạt động.

## World Boss 2026

Client chọn thư mục `BOSS_2026/` và gọi:

1. `get_boss_ranking.php`
2. `enter_boss_game.php`
3. `update_boss_result.php`

Request bảng chứa `HOST_ID`, `BOSS_NUM`, ngôn ngữ, tên, đội hình, item và phiên bản. Request vào trận thêm `MODE`. Request kết quả gửi `SCORE` là lượng HP boss giảm, `RESULT` và thống kê sát thương trong `ETC`.

Cả ba endpoint cũng trả `{}` trong môi trường offline không có capture. Client mong đợi `STATE` và dữ liệu boss; server hiện chưa có vòng đời boss chung, vé, HP, bảng đóng góp hoặc kết quả.

## Ưu tiên triển khai rút ra từ M0

1. Dùng một lớp phiên trận và kết quả dùng chung cho Sky, PvP, Cloud và Boss.
2. Mỗi kết quả có khóa duy nhất, chỉ dùng một lần; ghi kết quả, bảng hạng và thưởng trong cùng giao dịch.
3. Giữ các URL client hiện có để giảm thay đổi JavaScript nén.
4. Sky là chế độ đầu tiên vì client/server đã có luồng gần hoàn chỉnh; sau đó tái sử dụng nền này cho PvP, Cloud và Boss.

Tệp kiểm tra `remaining_protocol_probe.py` tái hiện các phản hồi hiện tại. Nó chỉ dùng dữ liệu giả.

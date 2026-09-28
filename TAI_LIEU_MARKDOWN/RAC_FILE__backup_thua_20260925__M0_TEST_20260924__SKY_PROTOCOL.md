# Giao thức Sky Garden hiện tại — môi trường M0

Ngày kiểm tra: 24/09/2026. Server thử: `127.0.0.1:8049`, SQLite riêng `m0_test.db`, ba tài khoản giả. Server thật ở cổng 8029 và `offline_save.json` không bị thay đổi.

## Luồng client–server đã chạy

```text
login_auth.php
  → SKY_2026/get_sky_ranking.php
  → SKY_2026/enter_sky_game.php
  → SKY_2026/update_sky_result.php
  → SKY_2026/get_sky_ranking.php
```

### 1. Đọc bảng

`POST /ELDORADO_WEB/SKY_2026/get_sky_ranking.php`

Trường dùng trong bài kiểm tra: `HOST_ID`.

Phản hồi client đang nhận gồm: `STATE`, `ranking_list`, `my_ranking`, `CLEAR_WAVE`, `CLEAR_DATE`, `entry_fee_ruby`, `PLATFORM_NAME_COM`.

Hiện tại `ranking_list` được dựng từ save của chính người gọi, luôn có một dòng; `ranking=1` và `my_ranking=1` ngay cả khi ba tài khoản có wave khác nhau.

### 2. Mở lượt

`POST /ELDORADO_WEB/SKY_2026/enter_sky_game.php`

Trường đã chạy: `HOST_ID`, `MODE`, `CHALLENGE_WAVE`.

- `MODE=ENTRY_TICKET`: phí ruby bằng 0 trong handler hiện tại.
- `MODE=ENTRY_RUBY`: phí được tính từ wave.
- Phản hồi thành công gồm `STATE`, `GAME_NONCE`, `s_add_ruby`, `ENTRY_FEE_RUBY`.
- Server lưu `sky_nonce` vào JSON save của tài khoản.

### 3. Ghi kết quả

`POST /ELDORADO_WEB/SKY_2026/update_sky_result.php`

Client thực tế gửi các trường gồm `HOST_ID`, `LANG`, `TEAM`, `ITEM`, `CHALLENGE_WAVE`, `RESULT`, `VER_DATE`, `GAME_NONCE`, `ETC`. Bài kiểm tra tối thiểu dùng `HOST_ID`, `CHALLENGE_WAVE`, `RESULT`, `GAME_NONCE`.

- `RESULT=W` làm `sky_wave = max(sky_wave, CHALLENGE_WAVE)`.
- Phản hồi gồm `STATE`, `CLEAR_WAVE`, `CLEAR_DATE`, `my_ranking`, `s_add_ruby`.
- Handler hiện không đối chiếu `GAME_NONCE`, không đóng phiên sau khi dùng và không ràng buộc wave báo cáo với lượt đã mở.

## Kết quả đã tái hiện

| Tài khoản thử | Wave hợp lệ đã gửi | Bảng nhìn thấy | Hạng trả về |
|---|---:|---:|---:|
| M0_A | 12 | 1 dòng — M0_A | 1 |
| M0_B | 25 | 1 dòng — M0_B | 1 |
| M0_C | 18 | 1 dòng — M0_C | 1 |

Sau đó M0_A gửi wave 99 với `GAME_NONCE=forged-not-issued-by-server`; server trả thành công và lưu wave 99. Khởi động lại server thử vẫn đọc được 99/25/18, chứng minh điểm cá nhân được lưu bền nhưng bảng chung và kiểm tra phiên trận chưa tồn tại.

## Kết luận cho thiết kế M2

Giữ ba đường API trên để không phải sửa client nhiều. Thêm bảng thành tích chung và phiên trận ở SQLite; `update_sky_result` phải xác thực phiên, chống dùng lại và cập nhật kết quả trong một giao dịch. `get_sky_ranking` đọc Top N chung cùng hạng thật của người gọi.

## Tệp kiểm tra

- `sky_protocol_probe.py`: bài kiểm tra HTTP có hai pha `mutate` và `verify`.
- `server.log`: log request từ hai lần khởi động server thử.
- `m0_test.db`: dữ liệu giả; không dùng làm database phát hành.

Lưu ý Windows: helper `with_server.py` đã dừng shell cha nhưng để lại tiến trình Python con. Hai tiến trình thử được xác định bằng đúng dòng lệnh/cổng 8049 rồi dừng thủ công; cổng 8029 vẫn thuộc PID 17160.

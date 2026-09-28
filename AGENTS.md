# Hướng dẫn làm việc với dự án Busidol Offline

## Tri thức và bàn giao

- Khi bắt đầu công việc, đọc `TRI_THUC_DU_AN.md`. Đọc `KE_HOACH_PHAT_TRIEN.md` và `LICH_TRINH_DU_AN.md` khi công việc liên quan tới lộ trình.
- Theo yêu cầu của người dùng, sau mỗi đợt làm việc có phát hiện, thay đổi hoặc quyết định đáng kể, cập nhật `TRI_THUC_DU_AN.md` trước khi bàn giao.
- Ghi ngày, mục tiêu, điều đã xác nhận, file liên quan, kiểm tra thực sự đã chạy, kết quả, giới hạn và bước tiếp theo. Không ghi là đã kiểm tra nếu chỉ suy luận từ mã.
- Cập nhật phần hiện trạng khi có thay đổi; nối thêm nhật ký theo đợt. Gộp thông tin trùng, giữ lại quyết định quan trọng và ghi rõ thông tin nào đã bị thay thế.
- Không lưu mật khẩu, token, cookie phiên, khóa quản trị, hash mật khẩu hoặc nội dung save riêng tư vào tài liệu.
- `MEM_NEXT_SESSION.md` và `memory/session_memory.md` là tư liệu lịch sử; đối chiếu mã hiện tại và yêu cầu mới trước khi dựa vào các ghi chú cũ.

## Phạm vi và bảo toàn dữ liệu

- Trao đổi với người dùng bằng tiếng Việt, dùng cách diễn đạt dễ hiểu.
- Phân biệt rõ đề xuất, việc đã được yêu cầu và việc đã làm. Lộ trình không tự động cho phép triển khai mọi mốc.
- Tôn trọng thay đổi sẵn có. Thử các thao tác tài khoản/tiền/trận trên dữ liệu riêng; chuẩn bị và kiểm tra bản sao trước khi chuyển đổi dữ liệu thật.
- Không tự khởi động lại server hoặc dừng tiến trình người dùng khi chỉ đang khảo sát/lập kế hoạch.
- Các skill mới chỉ được dùng khi phù hợp công việc; cài skill không đồng nghĩa đã cài các thư viện hoặc trình duyệt mà skill sử dụng.

## Tiêu chí bàn giao

- Với tài khoản, tiền, trận và xếp hạng: kiểm tra quyền truy cập, lưu bền, giao dịch đồng thời, gửi lại kết quả và khả năng phục hồi phù hợp phạm vi thay đổi.
- Báo rõ điều đã thay đổi, bằng chứng kiểm tra và việc còn thiếu. Không tuyên bố đã sửa game khi chỉ cập nhật tài liệu.

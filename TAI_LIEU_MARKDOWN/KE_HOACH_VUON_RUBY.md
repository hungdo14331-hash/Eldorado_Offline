# Kế hoạch triển khai mini game Vườn Ruby

Ngày bắt đầu: 25/09/2026. Người dùng đã duyệt mockup góc nhìn đảo vườn 2.5D và yêu cầu bắt đầu code. Mốc P0–P4 của web Ruby Farm chính đã hoàn thành ở phạm vi local/offline. Tài liệu này theo dõi riêng phần mini game mới.

## Luật MVP dùng để triển khai

- Bản đồ có 12 ô đất; 6 ô đầu mở sẵn. 6 ô còn lại hiển thị khóa; cơ chế mở khóa sẽ được thiết kế sau MVP.
- Người dùng đã chọn **xu vườn riêng**. Gói khởi đầu thử nghiệm v1 cho tổng 250 xu, 2 kim cương, 3 lục bảo, 1 phân bón, 1 thuốc tăng tốc, 3 hạt cà rốt, 2 hạt khoai tây và 1 hạt dâu; farm cũ nhận phần cộng thêm đúng một lần qua `starter_pack_version`. Không cộng/trừ `wallet_ruby` hoặc tiền game chính. Mua hạt ở cửa hàng, trồng, tưới, thu hoạch nông sản vào kho rồi bán để lấy xu. Kho giữ số lượng hạt và nông sản theo loại; MVP chưa giới hạn sức chứa.
- Cây lớn theo **ngày của server**, gần vòng chơi Stardew Valley: tưới một lần trong ngày cho ô đang lớn; khi sang ngày tiếp theo, ô đã tưới tăng một ngày sinh trưởng. Bỏ tưới thì cây đứng yên, không chết. Sáu lượt tưới được cấp lại mỗi ngày, không cộng dồn.
- Mua hạt 1–99 hạt mỗi lần, giá do server tính. Trồng tiêu một hạt; thu hoạch thêm một nông sản vào kho; bán tiêu nông sản và cộng xu. Cây không tự trả hạt. Chưa có mùa vụ hoặc cây thu hoạch nhiều lần trong MVP.
- Trình duyệt chỉ gửi hành động, ô, loại cây và số lượng. Giá, số xu, tiến độ cây, kho và ngày đều do server kiểm soát. Mỗi hành động ghi dữ liệu cần mã yêu cầu để retry trả kết quả cũ; cùng tài khoản được serialize, tài khoản khác không đọc/ghi chéo.

## Mở rộng kinh tế và tiến trình đã yêu cầu

| Nguồn lực | Nhận từ đâu | Dùng vào đâu |
|---|---|---|
| Xu vườn | Bán nông sản trong kho | Hạt giống, mở ô đất, nâng cấp bình tưới, mua nhân vật game gốc |
| Lục bảo | Bán bí ngô/dưa lưới; nhiệm vụ trồng 3 cây hoặc bán 2 nông sản | Mua phân bón |
| Kim cương | Bán hoa ruby; nhiệm vụ thu hoạch 2 nông sản | Mua buff tốc độ |
| XP / điểm kỹ năng | Trồng +1 XP, tưới +1 XP, thu hoạch +5 XP; đủ `10 × cấp hiện tại` XP lên cấp và nhận 1 điểm | Chọn nhánh kỹ năng, tối đa 3 bậc mỗi nhánh |

- Phân bón tốn 1 lục bảo, dùng một lần trên một lứa cây để giảm 1 ngày cần phát triển (tối thiểu 1 ngày). Buff tốc độ tốn 1 kim cương; lần chuyển ngày đã tưới tiếp theo tăng thêm 1 ngày tiến độ. Vật phẩm nằm trong kho cho đến khi dùng.
- Sáu nhánh kỹ năng ban đầu: giảm giá hạt 10%/bậc; tăng giá bán 10%/bậc; thêm 1 ngày tiến độ mỗi lần tưới/bậc; giảm 1 ngày cần phát triển/bậc; thêm 1 lượt tưới mỗi ngày/bậc; thêm 1 nông sản mỗi lần thu hoạch/bậc. Phần giảm thời gian luôn chặn tối thiểu 1 ngày, không cho thu hoạch ngay khi vừa trồng.
- Mở lần lượt sáu ô khóa bằng xu; giá ban đầu 150/225/300/400/525/675 xu. Nâng cấp bình tưới ba bậc giá 120/220/350 xu, mỗi bậc thêm 2 lượt tưới mỗi ngày. Mở khóa và nâng cấp là giao dịch server, không phải thay đổi chỉ ở trình duyệt.
- Cửa hàng nhân vật bước đầu chào ACE (ID 1, 350 xu), ECHO (ID 2, 450 xu), SMARTY (ID 3, 600 xu). Người dùng đã chọn **gửi qua thư trong game**; server hiện có hợp đồng thư `WHAT="CHAR"`, `WHAT_VALUE=<ID>`. Danh sách này là catalog khởi đầu để thử, không tự mở bán toàn bộ 114 nhân vật. Khi nối server, trừ xu và tạo thư phải cùng một giao dịch, gửi lại cùng mã yêu cầu không tạo thư thứ hai.
- Ba nhiệm vụ hằng ngày: trồng 3 cây → 1 lục bảo; bán 2 nông sản → 1 lục bảo; thu hoạch 2 nông sản → 1 kim cương. Claim một lần/ngày, tiến độ và trạng thái nhận làm mới theo ngày server. Nguồn đá quý và giá đang là cân bằng thử, có thể chỉnh trước khi phát hành.

Giá cân bằng ban đầu (xu vườn, có thể chỉnh trước R4/R5):

| Cây | Giá hạt | Giá bán | Ngày tưới đủ để chín |
|---|---:|---:|---:|
| Cà rốt | 10 | 17 | 1 |
| Khoai tây | 18 | 31 | 2 |
| Hướng dương | 20 | 37 | 2 |
| Cà chua | 25 | 43 | 3 |
| Dâu tây | 30 | 55 | 3 |
| Bắp | 35 | 62 | 4 |
| Bí ngô | 60 | 115 | 5 |
| Dưa lưới | 70 | 135 | 5 |
| Hoa ruby | 90 | 180 | 6 |

### Đề xuất catalog cây trồng v2 — chờ người dùng duyệt

Các giá trị dưới đây chưa được đưa vào mã. Chín cây có ghi “đang có” giữ nguyên giá hiện tại để không làm hỏng save và kiểm thử; chín cây “mới” mở dần theo cấp độ. “Thời gian lớn” là số ngày cây được tưới đủ, không phải số ngày lịch nếu người chơi bỏ tưới.

| Cấp mở | Cây trồng | Giá 1 hạt | Giá bán 1 nông sản | Thời gian lớn | Lãi cơ bản | Trạng thái |
|---:|---|---:|---:|---:|---:|---|
| 1 | Cà rốt | 10 | 17 | 1 ngày | 7 | Đang có |
| 1 | Khoai tây | 18 | 31 | 2 ngày | 13 | Đang có |
| 2 | Hướng dương | 20 | 37 | 2 ngày | 17 | Đang có |
| 3 | Củ cải đỏ | 14 | 24 | 1 ngày | 10 | Mới |
| 4 | Cà chua | 25 | 43 | 3 ngày | 18 | Đang có |
| 5 | Dâu tây | 30 | 55 | 3 ngày | 25 | Đang có |
| 6 | Hành tây | 28 | 49 | 2 ngày | 21 | Mới |
| 7 | Bắp | 35 | 62 | 4 ngày | 27 | Đang có |
| 8 | Ớt chuông | 42 | 78 | 4 ngày | 36 | Mới |
| 9 | Bắp cải | 50 | 94 | 4 ngày | 44 | Mới |
| 10 | Bí ngô | 60 | 115 | 5 ngày | 55 | Đang có; cây lục bảo |
| 11 | Dưa lưới | 70 | 135 | 5 ngày | 65 | Đang có; cây lục bảo |
| 12 | Cà tím | 68 | 130 | 5 ngày | 62 | Mới |
| 14 | Nho | 95 | 190 | 6 ngày | 95 | Mới |
| 16 | Hoa ruby | 90 | 180 | 6 ngày | 90 | Đang có; cây kim cương |
| 18 | Dứa | 125 | 260 | 7 ngày | 135 | Mới |
| 21 | Khế sao | 175 | 380 | 8 ngày | 205 | Mới |
| 25 | Sen pha lê | 260 | 590 | 10 ngày | 330 | Mới |

Định hướng cân bằng đề xuất:

- Cây 1–3 ngày phục vụ người chơi vào thường xuyên; vốn thấp, quay vòng nhanh.
- Cây 4–6 ngày là nguồn thu chính; lợi nhuận tuyệt đối tốt nhưng giữ vốn lâu hơn.
- Cây 7–10 ngày dành cho đầu tư dài hạn và người chơi ít đăng nhập; mở ở cấp cao để không phá giai đoạn đầu.
- Bí ngô, dưa lưới và hoa ruby nên thưởng đá quý theo mốc bán tích lũy thay vì mỗi nông sản đều trả một viên. Đề xuất ban đầu: 5 bí ngô hoặc 4 dưa lưới đổi 1 lục bảo; 6 hoa ruby đổi 1 kim cương. Cần thêm bộ đếm riêng nếu chốt luật này.
- Cà chua, dâu tây và nho phù hợp để trở thành cây thu hoạch nhiều lần ở bản sau, nhưng MVP hiện tại vẫn phải trồng lại sau mỗi lần thu hoạch.

## Mốc và điều kiện nghiệm thu

| Mốc | Đầu ra cụ thể | Điều kiện nghiệm thu | Trạng thái |
|---|---|---|---|
| R0 — Luật và hợp đồng | Luật trên; trạng thái ô `locked/empty/growing/ready`; catalog cây/vật phẩm/kỹ năng/nhân vật; mã lỗi rõ ràng | Cùng trạng thái và ngày server cho cùng kết quả; không lấy giá hoặc thưởng từ client | Đã ghi bản thử, giá còn có thể cân bằng |
| R1 — Asset runtime | Nền đảo nổi chỉ là cảnh; đất, chín cây theo giai đoạn, hạt/kho, phân bón, buff, đá quý là các lớp ảnh riêng do ImageGen tạo | Không lấy icon máy tính; asset trong workspace, tên ổn định; ô/cây không bị vẽ chết vào nền | Bản đầu: có nền đảo, strip cây và raw growth sheet; growth sheet chưa đạt QC nền trong suốt |
| R2 — Màn chơi | Trang Vườn Ruby 2.5D với 12 ô, cửa hàng hạt, kho/bán hàng, nhiệm vụ, cấp độ/cây kỹ năng, nâng cấp và catalog nhân vật bằng chữ | Chuột, bàn phím, màn nhỏ; thấy xu/đá quý, tồn kho, tiến độ, buff và lý do nút bị khóa | Bản đầu: shell + API + fallback; đã có mua vật phẩm, mở đất, nâng bình tưới và hiển thị starter pack; nhiệm vụ/nhân vật còn cần hoàn thiện |
| R3 — Lõi luật | `farm_core.py`: nông nghiệp, xu/đá quý, nhiệm vụ, vật phẩm tăng tốc, XP/kỹ năng, mở đất/nâng bình và sự kiện mua nhân vật | Test ngày cố định, điều kiện thiếu tài nguyên, không nhận lặp, state đầu vào bất biến, 14 test lõi | Đã viết lõi thuần và kiểm thử riêng; chưa lưu server |
| R4a — Lưu server | API đọc/ghi trạng thái farm theo tài khoản, `ACTION_ID` cho retry, transaction xu/kho/ô/nhiệm vụ | Hai tài khoản riêng, restart, đồng thời, gửi lại, lỗi ghi/rollback trên DB/save thử | Đã có bản đầu: `/ELDORADO_WEB/garden/state.php` và `action.php`, kiểm thử DB riêng |
| R4b — Thư nhân vật | Khi mua nhân vật, trừ xu và chèn thư `CHAR` bằng một transaction, dùng ID catalog server | Một mã yêu cầu chỉ tạo một thư; thiếu xu/ID sai không tạo thư; sau restart vẫn nhận đúng tài khoản | Đã có bản đầu trong route farm, kiểm thử đồng thời/retry/rollback |
| R5 — Tích hợp Ruby Farm | Thêm điều hướng/thẻ Vườn Ruby, số xu/đá quý riêng và đường trở về game chính; đồng bộ sau thao tác | 8 mini game cũ còn hoạt động; luồng cửa hàng → vườn → kho → bán → thư nhân vật chạy trên server thử | Đang làm: đã có liên kết hai chiều sidebar/hero ↔ Vườn Ruby; chưa hiện số dư farm trên web chính và chưa smoke test toàn luồng bằng phiên đăng nhập |
| R6 — QA và phát hành thử | Kiểm tra desktop/mobile, ảnh, ngày đổi, mất kết nối, tài khoản thử và log; triển khai khi được yêu cầu | Không tràn ngang/icon hỏng, không bán/nhận thư lặp hoặc nhầm tài khoản; ghi rõ kiểm tra live nếu có | Chưa làm |

## Thứ tự thực hiện

R0 và R3 cung cấp luật kiểm tra được trước. Sau đó tạo asset R1, dựng trang R2, nối R4a/R4b, tích hợp R5 và QA R6. R2 có thể đọc dữ liệu giả trên môi trường phát triển để duyệt hình ảnh; giá và số dư thật chỉ được ghi qua API R4a. Giao dịch thư nhân vật phải chờ R4b.

## Trạng thái hiện tại và giới hạn

`farm_core.py` hiện là lõi thuần: nhận trạng thái và ngày, trả trạng thái mới cùng sự kiện. Kho có `seeds`, `produce`, `items`; số dư có xu/lục bảo/kim cương; nhân vật có catalog thử. `serve.py` đã có bản đầu của API `/ELDORADO_WEB/garden/state.php` và `/ELDORADO_WEB/garden/action.php`: DB mode lưu theo session account, `ACTION_ID` replay cache, giao dịch mua nhân vật tạo thư `CHAR` cùng save. Chưa có trang chơi/asset runtime và chưa mở route trên server live. Quy tắc ba cây nhận Ruby trực tiếp của bản kế hoạch đầu ngày 25/09/2026 đã được yêu cầu mới này thay thế.

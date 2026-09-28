# HƯỚNG DẪN VẬN HÀNH BUSIDOL / ELDORADO LOCAL SERVER

> Dành cho project `busidol_offline` trên Windows / PowerShell.  
> Mục tiêu: khởi động server, restart server an toàn, đăng nhập game, mở Admin Control, tạo/quản lý tài khoản và xử lý các lỗi thường gặp.

---

## 1. Thư mục project

Project hiện được dùng tại dạng đường dẫn:

```powershell
E:\UserData\Desktop\TEST ELDORADO\busidol_offline
```

Mở PowerShell rồi chuyển vào thư mục:

```powershell
cd "E:\UserData\Desktop\TEST ELDORADO\busidol_offline"
```

Kiểm tra các file quan trọng:

```powershell
dir serve.py
dir busidol.db
dir admin_control_backend.py
dir admin_control
```

Cấu trúc Admin Control mong muốn:

```text
busidol_offline/
├─ serve.py
├─ busidol.db
├─ admin_control_backend.py
└─ admin_control/
   ├─ admin_control.html
   ├─ admin.css
   └─ admin.js
```

---

# 2. KHỞI ĐỘNG SERVER

## Bước 1 — mở PowerShell trong project

```powershell
cd "E:\UserData\Desktop\TEST ELDORADO\busidol_offline"
```

## Bước 2 — đặt mật khẩu Admin Control

Mỗi cửa sổ PowerShell mới cần đặt lại biến môi trường này trước khi chạy server:

```powershell
$env:BUSIDOL_ADMIN_PASSWORD="MAT_KHAU_ADMIN_CUA_BAN"
```

Ví dụ:

```powershell
$env:BUSIDOL_ADMIN_PASSWORD="MyStrongAdminPassword"
```

Không nên dùng mật khẩu đã từng gửi công khai trong chat hoặc log.

## Bước 3 — chạy server

```powershell
python .\serve.py `
  --port 8029 `
  --admin-port 8030 `
  --db .\busidol.db `
  --require-login
```

Giữ cửa sổ PowerShell này mở.

Nếu chạy thành công, hai listener phải là:

```text
GAME  127.0.0.1:8029
ADMIN 127.0.0.1:8030
```

Cổng `8029` chỉ phục vụ game. Cổng `8030` chỉ phục vụ Admin Control và luôn
bind trực tiếp vào `127.0.0.1`, bất kể giá trị `--host` của game.

---

# 3. CÁC URL QUAN TRỌNG

## Trang đăng nhập game

```text
http://127.0.0.1:8029/ELDORADO_WEB/login_page.php
```

Server hiện dùng trang login riêng để xác thực account trong database.

## Game chính

```text
http://127.0.0.1:8029/ELDORADO_WEB/source_20240722/index__mobile.html#sign=offline&time=0
```

Không nên mở URL game trực tiếp sau khi vừa restart server nếu chưa đăng nhập lại, vì game cần session `dol_session`.

## Admin Control

```text
http://127.0.0.1:8030/admin-control
```

Nếu hệ thống redirect sang:

```text
/admin-control/
```

thì đây là hành vi bình thường.

## Admin login

```text
http://127.0.0.1:8030/admin-control/login
```

Admin sử dụng session riêng với game.

---

# 4. MỞ ADMIN CONTROL

1. Server phải được chạy trong cùng PowerShell mà bạn đã đặt `BUSIDOL_ADMIN_PASSWORD`.
2. Mở:

```text
http://127.0.0.1:8030/admin-control
```

3. Nhập đúng mật khẩu Admin.

Admin session và game session là hai session khác nhau:

```text
Đăng nhập Admin ≠ Đăng nhập game
Đăng nhập game  ≠ Đăng nhập Admin
```

Đây là thiết kế đúng.

---

# 5. SAU KHI RESTART SERVER

Sau mỗi lần restart server:

1. Admin session có thể mất.
2. Game session `dol_session` cũ có thể mất.
3. Tab game đang mở từ trước có thể hiện lỗi authentication.

Quy trình nên dùng:

```text
Restart server
    ↓
Đăng nhập game lại
    ↓
Mở game
    ↓
Đăng nhập Admin lại
```

Nếu game hiện popup có:

```text
check_black_list_db()
1: null
```

thì trước tiên hãy đăng nhập game lại.

---

# 6. RESTART SERVER AN TOÀN

## Cách an toàn nhất nếu server đang chạy trong PowerShell của bạn

Trong cửa sổ server:

```text
Ctrl + C
```

Chờ server dừng hoàn toàn.

Sau đó:

```powershell
$env:BUSIDOL_ADMIN_PASSWORD="MAT_KHAU_ADMIN_CUA_BAN"
python .\serve.py `
  --port 8029 `
  --admin-port 8030 `
  --db .\busidol.db `
  --require-login
```

---

# 7. KIỂM TRA PORT 8029 ĐANG DO PROCESS NÀO GIỮ

Không kill process theo cảm tính.

```powershell
netstat -ano | findstr :8029
```

Ví dụ:

```text
TCP    0.0.0.0:8029    0.0.0.0:0    LISTENING    8772
```

Số cuối là PID.

Kiểm tra process:

```powershell
Get-Process -Id 8772
```

Xem command line chi tiết:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = 8772" |
Select-Object ProcessId, Name, CommandLine
```

Chỉ dừng PID khi đã xác nhận đó là `serve.py` của project này:

```powershell
Stop-Process -Id 8772
```

Sau đó:

```powershell
netstat -ano | findstr :8029
```

Nếu không còn dòng `LISTENING` thì port đã được giải phóng.

---

# 8. KHÔNG NÊN LÀM KHI RESTART

Không dùng:

```powershell
taskkill /F /IM python.exe
```

vì có thể kill mọi Python process khác.

Không chạy hai server cùng dùng `busidol.db` đồng thời.

---

# 9. TẠO TÀI KHOẢN MỚI

## Điều đã xác minh

Server có bảng `accounts` và endpoint login `login_auth.php`.

Login nhận:

```text
acc
pw
```

và chỉ cho vào nếu account/password trong database hợp lệ.

## Lưu ý quan trọng

Source snapshot hiện có chỉ xác nhận cơ chế đăng nhập, chưa đủ để khẳng định chính xác schema hash/password của bảng `accounts` hoặc lệnh tạo account hiện tại.

Vì vậy:

```text
KHÔNG tự INSERT password thô trực tiếp vào SQLite.
KHÔNG tự đoán thuật toán hash.
```

Nếu project hiện có công cụ/script tạo account thì phải dùng công cụ đó.

### Cách tìm công cụ tạo account

```powershell
Get-ChildItem -Recurse -File |
Where-Object {
    $_.Name -match "account|user|register|create"
} |
Select-Object FullName
```

Tìm các đoạn xử lý account:

```powershell
Get-ChildItem -Recurse -Filter *.py |
Select-String -Pattern "accounts|verify_account|password|hash"
```

Nếu chưa biết cách chính xác, dùng Codex với prompt:

```text
Hãy xác định chính xác cách tạo account mới trong project hiện tại.

Chỉ đọc code hiện tại:
- serve.py
- các script account/user
- schema SQLite busidol.db

Không thay đổi production.

Trả về:
1. schema bảng accounts;
2. thuật toán hash password;
3. công cụ/lệnh chính thức để tạo account;
4. một lệnh copy-paste để tạo account TEST_ACCOUNT;
5. cách xác minh account đăng nhập được.

Không tự phát minh schema hoặc hash.
```

Sau khi xác minh được lệnh tạo account chính thức, hãy cập nhật mục này.

---

# 10. ĐĂNG NHẬP GAME

Mở:

```text
http://127.0.0.1:8029/ELDORADO_WEB/login_page.php
```

Nhập account/password.

Nếu vừa restart server, hãy login lại ngay cả khi tab game cũ vẫn đang mở.

---

# 11. ADMIN CONTROL — CHỨC NĂNG

Admin Control hiện hỗ trợ:

```text
- tìm account
- xem Gold
- xem Ruby
- xem BP
- xem Cloud Piece
- xem Celestial Essence
- grant Gold/Ruby/BP/Cloud/Essence
- gửi Character qua mailbox
- gửi Item qua mailbox
- xem Audit Log
```

Admin Control chỉ dành cho localhost.

---

# 12. GỬI TÀI NGUYÊN BẰNG ADMIN

Quy trình:

```text
Admin Control
    ↓
Tìm account
    ↓
Kiểm tra đúng account
    ↓
Chọn currency
    ↓
Nhập số lượng
    ↓
Confirm
    ↓
Kiểm tra balance
    ↓
Kiểm tra Audit Log
```

Các currency:

```text
GOLD
RUBY
BP
CLOUD
ESSENCE
```

Không nhập số âm.

---

# 13. GỬI NHÂN VẬT

Character được gửi qua mailbox, không chèn trực tiếp DATA2.

Ví dụ:

```text
Target account: TEST_ACCOUNT
Character ID: 114
```

Sau khi gửi:

1. vào game bằng account đó;
2. mở mailbox;
3. claim character;
4. kiểm tra roster.

Backend dùng:

```text
WHAT = CHAR
WHAT_VALUE = Character ID
```

---

# 14. GỬI ITEM

Item cũng được gửi qua mailbox.

Backend xác minh Item ID từ catalog hiện tại.

Nếu quantity > 1, hệ thống hiện tạo nhiều mail ITEM.

---

# 15. AUDIT LOG

Sau mọi grant, kiểm tra tab `Audit Log`.

Audit nên có:

```text
time
target
action
detail
result
```

Ví dụ:

```text
HUANDO
GRANT_RUBY
amount=5000 before=10000 after=15000
SUCCESS
```

Audit không được chứa password, cookie, token hoặc secret.

---

# 16. BACKUP DATABASE

Trước thay đổi lớn:

```powershell
Copy-Item ".\busidol.db" ".\busidol_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

Không ghi đè backup cũ.

---

# 17. KIỂM TRA SERVER ĐANG SỐNG

```powershell
Test-NetConnection localhost -Port 8029
```

Nếu:

```text
TcpTestSucceeded : True
```

thì port đang mở.

Kiểm tra HTTP:

```powershell
Invoke-WebRequest "http://127.0.0.1:8029/ELDORADO_WEB/login_page.php" -UseBasicParsing
```

---

# 18. LỖI: PORT 8029 ĐÃ ĐƯỢC DÙNG

Nếu Python báo `Address already in use`:

```powershell
netstat -ano | findstr :8029
```

Xác minh PID:

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = PID" |
Select-Object ProcessId, Name, CommandLine
```

Nếu đúng server cũ, dừng nó rồi chạy lại.

---

# 19. LỖI: ADMIN BÁO CHƯA CÓ PASSWORD

Nếu bạn set password ở PowerShell A nhưng chạy server ở PowerShell B, server sẽ không thấy biến môi trường.

Phải chạy trong cùng cửa sổ:

```powershell
$env:BUSIDOL_ADMIN_PASSWORD="MAT_KHAU"
python .\serve.py --port 8029 --admin-port 8030 --db .\busidol.db --require-login
```

---

# 20. LỖI: GAME KHÔNG VÀO SAU RESTART

Nếu thấy popup liên quan `check_black_list_db`, nguyên nhân thường gặp là `dol_session` cũ đã mất.

Cách xử lý:

1. đóng tab game cũ;
2. mở login page;
3. đăng nhập lại;
4. vào lại game.

Admin session không dùng thay game session.

---

# 21. ADMIN VÀ GAME CÙNG MỞ

Admin và game đã được test chạy đồng thời.

Bình thường:

```text
Admin tab mở + Game tab mở = hoạt động cùng lúc
```

Nếu game lỗi auth, login game lại trước khi debug backend.

---

# 22. SAU KHI SỬA CODE SERVER

Mỗi lần sửa `serve.py` hoặc `admin_control_backend.py`, server đang chạy sẽ không tự nạp code mới.

Phải restart:

```text
Ctrl+C
↓
set BUSIDOL_ADMIN_PASSWORD
↓
python .\serve.py --port 8029 --admin-port 8030 --db .\busidol.db --require-login
↓
login game lại
↓
login Admin lại
↓
smoke test
```

---

# 23. SMOKE TEST SAU RESTART

## Game

```text
[ ] Login thành công
[ ] vào main menu
[ ] balance tải được
[ ] mailbox tải được
```

## Admin

```text
[ ] Admin login
[ ] tìm account
[ ] balance hiển thị
[ ] Audit Log tải được
```

Nếu vừa thay đổi Admin, gửi thử `+1 Gold` hoặc `+1 Ruby` vào account test.

---

# 24. KHÔNG TEST TRÊN BASELINE

Baseline:

```text
M0_BASELINE_20260924_014351
```

Không sửa, xóa, test trực tiếp hoặc dùng làm working directory.

---

# 25. TEST CODE MỚI

Khi nhờ Codex/Qoder test:

```text
- dùng port riêng
- dùng DB riêng
- dùng account test
- không stop 8029
- không dùng save thật
```

Ví dụ port test:

```text
18055
18056
```

Không cho test instance dùng cùng `busidol.db` với production server.

---

# 26. LỆNH NHANH — CHEAT SHEET

## Vào project

```powershell
cd "E:\UserData\Desktop\TEST ELDORADO\busidol_offline"
```

## Đặt Admin password

```powershell
$env:BUSIDOL_ADMIN_PASSWORD="MAT_KHAU_ADMIN"
```

## Start server

```powershell
python .\serve.py --port 8029 --admin-port 8030 --db .\busidol.db --require-login
```

## Kiểm tra port

```powershell
netstat -ano | findstr :8029
```

## Xem process

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId = PID" |
Select-Object ProcessId, Name, CommandLine
```

## Stop đúng process

```powershell
Stop-Process -Id PID
```

## Login game

```text
http://127.0.0.1:8029/ELDORADO_WEB/login_page.php
```

## Admin

```text
http://127.0.0.1:8030/admin-control
```

## Backup DB

```powershell
Copy-Item ".\busidol.db" ".\busidol_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').db"
```

---

# 27. QUY TRÌNH HÀNG NGÀY KHUYẾN NGHỊ

```text
1. Mở PowerShell.
2. cd vào busidol_offline.
3. Set BUSIDOL_ADMIN_PASSWORD.
4. Start `serve.py --port 8029 --admin-port 8030 --db busidol.db --require-login`.
5. Login game.
6. Mở Admin nếu cần.
7. Chơi / quản trị.
8. Khi dừng: Ctrl+C server.
```

Nếu server crash:

```text
1. kiểm tra port 8029;
2. xác minh PID;
3. backup DB nếu cần;
4. restart;
5. login game lại;
6. login Admin lại.
```

---

# 28. GHI CHÚ BẢO MẬT

- Không gửi Admin password lên GitHub.
- Không hardcode Admin password trong HTML/JS/Python.
- Không đưa `busidol.db` thật lên repo public.
- Cloudflare Tunnel chỉ được trỏ vào game: `http://127.0.0.1:8029`.
- Tuyệt đối không trỏ tunnel vào cổng Admin `8030`.
- Game port trả `404` cho `/admin-control*` và legacy `/admin`, kể cả khi giả mạo header proxy.
- Không chia sẻ session cookie.
- Sau khi mật khẩu bị gửi trong chat/log, nên đổi mật khẩu.
- Không tin `Host`, `X-Forwarded-For` để xác định localhost.

Lệnh quick tunnel đúng đích game:

```powershell
cloudflared tunnel --url http://127.0.0.1:8029
```

---

# 29. TRẠNG THÁI ADMIN CONTROL HIỆN TẠI

Theo vòng test gần nhất:

```text
GOLD                PASS
RUBY                PASS
BP                  PASS
CLOUD               PASS
ESSENCE             PASS
Character mailbox   PASS
Item mailbox        PASS
Audit               PASS
Account isolation   PASS
Persistence         PASS
Concurrent grants   PASS
Admin + Game        PASS
```

---

# 30. GHI NHỚ QUAN TRỌNG NHẤT

```text
1. Không kill PID nếu chưa xác minh command line.
2. Sau restart, login game và Admin lại.
3. Trước thay đổi lớn, backup busidol.db.
```

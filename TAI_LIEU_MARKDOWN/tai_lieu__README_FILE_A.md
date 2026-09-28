# file_A — Mã nguồn rút gọn dự án Busidol Offline

Bản trích ngày **24/09/2026** từ workspace `busidol_offline`, chỉ gồm **mã nguồn, tài liệu, test, launcher, config** và vài asset đại diện (78 file, ~7,9 MB).
Mục đích: để một AI khác đọc và hiểu sâu kiến trúc + luồng hoạt động mà không cần toàn bộ ~586 MB asset.

Đây **không phải bản chạy được đầy đủ**: thiếu ảnh/âm thanh/asset game và toàn bộ dữ liệu tài khoản.

## Nên đọc theo thứ tự

1. `TRI_THUC_DU_AN.md` — tri thức dự án: kiến trúc, API, quyết định, nhật ký từng đợt (mục §9 mới nhất).
2. `serve.py` — toàn bộ máy chủ: HTTP server + API giả lập đuôi `.php`. Đây là "backend" thật của bản offline.
3. `ELDORADO_WEB/rubyfarm.html` — trang RubyFarm; HTML + CSS + JS **nằm chung một file** (đã redesign 24/09/2026).
4. `AGENTS.md` → `KE_HOACH_PHAT_TRIEN.md` → `LICH_TRINH_DU_AN.md` — quy tắc làm việc, lộ trình.
5. `M0_TEST_20260924/SKY_PROTOCOL.md`, `OTHER_MODES_PROTOCOL.md` — protocol các chế độ chưa mở.
6. `ELDORADO_WEB/javascript_min/eldorado_all_20260915.min.js` — logic client gốc, 6,5 MB đã nén; chỉ tra cứu khi cần.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| `serve.py` | Máy chủ chính (offline + proxy), API tài khoản/save/ví/điểm danh/minigame |
| `TRI_THUC_DU_AN.md` | Tài liệu tri thức & nhật ký bàn giao — **đọc trước tiên** |
| `AGENTS.md`, `KE_HOACH_PHAT_TRIEN.md`, `LICH_TRINH_DU_AN.md`, `MEM_NEXT_SESSION.md` | Quy tắc làm việc, kế hoạch, lộ trình, ghi chú phiên cũ |
| `ITEMS.md`, `CHARACTERS.md` | Dữ liệu tham chiếu vật phẩm / nhân vật |
| `ELDORADO_WEB/rubyfarm.html` | Trang RubyFarm (8 minigame, ví ruby, điểm danh, vé) |
| `ELDORADO_WEB/convert.html` | Trang đổi tiền/tài nguyên |
| `ELDORADO_WEB/javascript_min/` | `eldorado_all_20260915.min.js` (bundle chính), `aes.js`, `ovr_gold_x5.js` |
| `ELDORADO_WEB/javascript/app_test.js` | JS phụ trợ phía client |
| `ELDORADO_WEB/source_20240722/` | `index__mobile.html`, `loader.js`, `css/Main.css`, `lib/jquery-2.1.3.min.js` — khung trang game gốc |
| `ELDORADO_WEB/get_app_file.php`, `pwsmart.1.3.js`, `GoogleAnalytics/`, `javascript_leveling/` | Điểm cuối & script nhỏ phía web |
| `minigame/` | `generator_repair.html`, `sudoku.html`, `rubyfarm_bridge.js` — 2 minigame nhúng iframe + cầu nối ví |
| `KR_INPUT/kr_input_with_mouse_email.js` | Bàn phím ảo tiếng Hàn |
| `capture/*.json` | Mẫu request/response thật của server gốc (chỉ path/status/body, không có dữ liệu tài khoản) |
| `M0_TEST_20260924/` | Đợt khảo sát M0: script dò protocol + 2 tài liệu protocol |
| `*.bat`, `get_tunnel_url.ps1` | Launcher: chạy offline/proxy, nhiều tài khoản, tunnel, đổi tài khoản |
| `*.js` (gốc), `*.py` (gốc) | Công cụ hỗ trợ: `autocapture.js`, `walk.js`, `sweep.js`, `stage.js`, `pause.js`, `evalstate.js`, `console.js`, `shot.js`, `jsx.js`, `_rf_check.js`; `patch.py`, `resedit.py`, `warmup.py`, `inspect3.py`, `tao_huando.py` |
| `test_*.py`, `verify_convert*`, `_REG_TEST/rf_viewport_test.html` | Test/kiểm chứng |
| `ELDORADO_WEB/image/ui/0_common/`, `1_mainmenu/mm_bg.jpg` | Vài asset đại diện (nền main menu + thanh ruby/bp, checkbox, khung số) |
| `.gitignore`, `config.yml` | Cấu hình |

## Đã loại trừ (và lý do)

- `ELDORADO_WEB/image/` (~38 MB, 11.129 png), `sound/` (70 mp3), `source_20240722/image|sound` (~214 MB) → asset nặng; chỉ giữ vài file đại diện.
- `cloudflared.exe` (53 MB) → công cụ bên ngoài.
- `archive/`, `M0_BASELINE_20260924_014351/`, `serve - Copy.py`, `ACCT_*`, `TRAI_TAIKHOAN_CU_GIU_LAI`, `*_BACKUP_*`, `*.bak` → bản sao lưu.
- `*.log`, `__pycache__/`, `cls_pycdc_serve.marshal`, `_c` → log/rác tạm.
- `busidol.db`, `busidol_banbe.db`, `offline_save.json`, `save_*.json`, `_REG_TEST/rf_test_save.json` → **dữ liệu riêng tư** (hash mật khẩu, save người chơi), cố ý không đưa vào.

## Lưu ý kỹ thuật khi đọc

- `serve.py` không chạy PHP thật: nó chặn các đường dẫn đuôi `.php` và trả JSON. `--mode offline` (mặc định) dùng save JSON cục bộ; `--proxy` chuyển tiếp ra server thật; `--mode solo`/nhiều tài khoản dùng SQLite.
- `ELDORADO_WEB/javascript_min/angular.min.js` là file **0 byte** trong bản gốc — không phải lỗi khi sao chép.
- `rubyfarm.html` nhúng 2 minigame qua iframe; ví ruby nằm tách khỏi ruby trong save (`wallet_ruby`) để trang minigame không sửa được ruby thật.
- Hạn mức/cooldown do server quyết định: `MINIGAME_CD_SEC = 3`, `DAILY_RUBY_CAP = 500`, giá vé 2000/800, tặng 3 vé/ngày mỗi loại.

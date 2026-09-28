# Busidol Offline — Session Memory

> Tổng hợp thông tin đã biết/đã làm trong session này (generated 2026-09-22).

## Dự án
- **busidol_offline**: server Eldorado/offline (Python `serve.py`) + SQLite multiplayer, login, rewards, minigames.
- Repo git: `C:\busidol_offline`, nhánh mặc định duy nhất, 1 commit `c06c731` ("Initial commit ...").
- OS: Windows (PowerShell 5.1).
- DB chính: `busidol.db` (và `busidol_banbe.db`, `busidol_moi.db`...).

## Serve & Truy cập
- `serve.py` chạy static server. Đã sửa file `.html` thì **có hiệu lực ngay, không cần restart** — serve.py đọc file tĩnh mỗi request.
- Tunnel cloudflare dump: file `.bat` (`CHOI_*.bat`, `AUTOCAPTURE.bat`), `cloudflared.exe` nằm tại root.
- Tunnel gần nhất: `https://hills-upc-eligibility-going.trycloudflare.com` — đã test OK.
- Login test hợp lệ: `HUANDO` / `HUAN123` → `{"ok":1,"uid":"HUANDO"}`.

## Quy tắc không đổi
- **KHÔNG sửa `serve.py`** — server đã chặn mua generator từ phía server (trả `"daily only"`); generator chỉ nhận vé miễn phí 1 lần/ngày khi đăng nhập.
- Tài khoản/backup: hạn chế đụng DB; có sẵn các thư mục backup (`BACKUP_*`, `ACCT_*`, `TRAI_TAIKHOAN_CU_GIU_LAI`).

## RubyFarm (`ELDORADO_WEB\rubyfarm.html`)
- `renderTickets()` dùng `mk(id, label, buyable)`.
- Vé generator: `mk("gen", ..., false)` → **không có nút mua**; hiện "🎁 Chỉ nhận miễn phí mỗi ngày khi đăng nhập".
- Vé sudoku: `mk("sud", ..., true)` → vẫn mua được.

## Minigame Sudoku (`minigame\sudoku.html`)
- Đã xóa sạch 4 button HTML + 4 listener cũ (`matrixBtn`/`solveBtn`/`saveBtn`/`openBtn`) — trước đây gây crash vì `$('matrixBtn')` = null.
- Còn đúng 5 nút/listener: `generateBtn`, `loadBtn`, `checkBtn`, `undoBtn`, `clearBtn`.

## Minigame Generator (`minigame\generator_repair.html`) — đổi trong session này
- Request: *"nâng cấp game generator — khi bắt đầu chế độ full (repair) generator: mặc định progress 50% thay vì 0; nếu progress tụt về 0 hoặc miss quá số lần → bị loại."*
- **Bắt đầu repair = 50%**: `begin()` repair — nhánh SUCCESS (paidRun=true) và nhánh NETERR fallback đều `state.progress = 50; updateProgressUI();` (dòng ~526, ~537). Drill mode vẫn bắt đầu ở 0.
- **Luật loại (miss block, `resolveHit`)**: miss → `state.runMiss++`, trừ progress bằng `DIFFS[diff].missPenalty` (nightmare ×1.6). Bị loại khi `state.mode==='repair' && (state.runMiss >= GENREP_MISS[diff] || state.progress <= 0)` — dòng ~434.
- Callout khi bị loại: `'Bị loại — hết progress'` (khi progress ≤0) / `'Thua — N misses'` (khi miss quá mức).
- Hằng số: `GENREP_FEE = {easy:1,normal:1,hard:1,nightmare:1}`, `GENREP_MISS = {easy:3,normal:3,hard:5,nightmare:10}`.
- Progress: +7 great, +4 good; clamp 0..100; win ở ≥100 → `genrep_claim.php` trả thưởng ruby.

## Lưu ý kỹ thuật khi edit HTML ở repo này
- File dùng **indent 2 space** (có cả 4/6/8 tùy hàm lồng nhau). Lần đầu edit `generator_repair.html` fail nhiều lần vì oldString sai indent/keyboard dash (`—`); cách xử lý: **đọc lại đúng phạm vi dòng rồi copy nguyên xi**, edit từng block nhỏ.
- Trước khi edit luôn xem `state`, `DIFFS`, `GENREP_*` để khỏi đoán tên biến.

## Endpoint đã gặp
- `ELDORADO_WEB/wallet/genrep_start.php` (body `{DIFF}`) → mở lượt repair, trả `ticket`, `tickets`.
- `ELDORADO_WEB/wallet/genrep_claim.php` (body `{DIFF, GREAT}`) → nhận thưởng ruby.
## Bổ sung session này (tunnel / stage 245 / gacha select)
- **Lỗi tunnel** (gốc): `findstr /r ":8029 .*LISTENING"` trong `CHOI_BANBE_TUNNEL.bat` match mọi dòng LISTENING vì tách theo space → bat tưởng server đã chạy, không start gì. Đã sửa 3 dòng bằng `findstr /r /c:"..."`.
- **Stage 245..300 (boss)**: client gate `count_arr[stage].count < 5` = "hết lượt". serve.py `cnm_exist_host_in_server.php` trả chuỗi `"0"` → theo PHƯƠNG ÁN B đã đổi thành `{"count":0,"max":5}`; `cnm_update_user_to_server_cry.php` mode=stage → trả `{"STATE":"SUCCESS","STAGE_COUNT":"0"}` (bỏ giới hạn lượt).
- **Gacha select (ITEM x1=26, x10=27)**: vốn là IAP real-money (S_PAYMENT_CNM/S_INPUT_PAY) → không mua được offline. ĐÃ VÁ `eldorado_all_20260915.min.js` (backup: `archive\eldorado_all_20260915.min.js.bak_20260922`): trong `S_POPUP_PACKAGE_STORE.menuRun_Run`, nhánh mới trước guild-shop:
  `if(!this._from_guild_shop&&this.from_gacha&&(this.type_num===26||this.type_num===27)){this.from_gacha=!1;var _cn=this.type_num===26?1:10,_n=0,_ec="";S_ITEM_GACHA.need_ruby=this.type_num===26?1000:9000;for(_n=0;_n<_cn;_n++){S_ITEM_GACHA.focus=2;S_ITEM_GACHA_COMPLETE.init_ITEM_GACHARESULT();S_ITEM_GACHA_COMPLETE.calculate();S_ITEM_GACHA_COMPLETE.add_item_refactoring();_ec+=(_ec?",":"")+ITEM_GACHARESULT[1].item_num+":0:"+ITEM_GACHARESULT[1].add_option+"-"+ITEM_GACHARESULT[1].add_option_num+":0:0"}S_ITEM_GACHA.gacha_etc="("+this.type_num+"번 항목)아이템 뽑기 "+_cn+"개|"+_ec;this.end();ServerConnection.update_item_to_server(S_ITEM_GACHA.gacha_etc,function(n){var _t=n||{};gEnableKey=1;if(_t.STATUS=="ERROR"){glo.fun.show_s_error_network("아이템 뽑기에서 실패:"+(_t.ERROR_CODE||""));return}if(_t.STATUS&&(_t.STATUS+"").search("mysql_error")>=0){glo.fun.show_s_error_network("아이템 뽑기에서 오류:"+(_t.ERROR_MESSAGE||""));return}USER.ruby=Number(_t.after_ruby);S_MAINMENU.remount_mm_top(S_GACHA,TXT.gacha);utilNotice("아이템 "+_cn+"개 획득!",1.5)},"ITEM_GACHA",S_ITEM_GACHA.need_ruby*-1,null);return}`
  → mua x1 = 1000 ruby / x10 = 9000 ruby: tự rút ITEM hợp lệ bằng đúng công thức native get_gacha2 (AP/PS/HP/SP tùy xác suất, grade + tier random), x1 = 1 món, x10 = 10 món THẬT, mỗi món add vào STORAGE qua add_item_refactoring, rồi UPDATE_ITEM POST với RUBY=-giá. KHÔNG dùng gacha_item_yes (đường đó TREO: confirm YES → STORAGE.make_item()/aniRun chạy nhưng không POST, ruby không trừ, không lỗi console, không vào log server — item gacha offline vốn chưa từng chạy vì pool gacha_item_list=[] server rỗng, tab ?3 chỉ hiện 2 card package, không có card item gacha).
  Node `--check` syntax OK. Server: serve.py item/update_item_to_server.php giờ trừ RUBY<0 khỏi DATA1 và trả after_ruby mới (giống save_UserInfo_after_PAY).
- Live hiện tại: server python PID 6944 @0.0.0.0:8029; cloudflared PID 18300, tunnel `https://fraction-knife-hepatitis-drives.trycloudflare.com`.

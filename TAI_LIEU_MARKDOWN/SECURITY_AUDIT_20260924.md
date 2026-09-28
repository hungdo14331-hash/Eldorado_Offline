# Security S0 — Security Audit & Threat Model

Ngày audit: 25/09/2026  
Phạm vi: code hiện tại của Busidol/Eldorado offline-private server; **chỉ đọc**, không thử mutation trên save/DB thật, không restart server 8029, không đọc nội dung `busidol.db`/save thật và không scan `M0_BASELINE_20260924_014351`.

## 1. Executive summary

Server hiện phù hợp nhất với mô hình **solo localhost có giới hạn**. Cấu hình đang chạy thực tế lại là `0.0.0.0:8029`, SQLite và `--require-login`; launcher còn hỗ trợ LAN, NAT và Cloudflare tunnel. Trong mô hình đó, lớp login hiện không tạo ra identity đáng tin cậy: request vẫn có thể tự khai `HOST_ID`/`UNIQ_ID`, cookie chỉ chứa account id không ký, và phần lớn route không thực hiện authorization riêng.

Rủi ro cao nhất là chuỗi: **kết nối được tới server → chọn identity tùy ý → đọc/ghi save hoặc gọi endpoint economy của account khác**. `/admin` còn trả key thật trong lỗi 401 và kiểm tra “localhost” bằng `Host` header do client kiểm soát. Cloud Garden đã trả nonce khi bắt đầu nhưng `GAME_END` không kiểm tra/consume nonce, nên reward có thể replay.

Kết quả: **1 Critical, 5 High, 7 Medium, 2 Low**. Không có bằng chứng code hiện tại đủ an toàn để mở public Internet.

### Trạng thái sau Security S1 (25/09/2026)

S1 đã vá và kiểm tra cô lập hai finding ưu tiên. Khi chạy SQLite với `--require-login`, server phát cookie phiên opaque ngẫu nhiên sau login và derive identity chỉ từ session server-side; `HOST_ID`, `UNIQ_ID`, `ID` hoặc `uid` từ client không còn chọn account. `/admin` kiểm tra địa chỉ socket loopback thay vì `Host`, so key bằng `compare_digest`, không echo secret và log chỉ ghi path không có query. Kết quả hiện tại: **SEC-001 CLOSED, SEC-002 CLOSED trong phạm vi S1**.

Giới hạn còn lại: session nằm trong RAM, hết hạn sau 7 ngày và mất khi server restart; người dùng phải login lại. Solo mode không bật `--require-login` vẫn giữ identity wire-format để tương thích một người chơi và không được xem là ranh giới multi-account. Admin vẫn dùng key trong query nên browser history là rủi ro còn lại; không expose admin qua tunnel/public. Các finding SEC-003 đến SEC-015 chưa được S1 xử lý.

## 2. Deployment và trust boundaries

### Deployment hiện tại

- Snapshot đầu audit thấy PID 20348; lần xác minh cuối thấy PID 3220, vẫn bind `0.0.0.0:8029` với cùng command `--db busidol.db --require-login`. S0 không gọi lệnh stop/start; thay đổi PID xảy ra ngoài thao tác audit.
- `CHOI_BANBE.bat:12` mở LAN trên `0.0.0.0`.
- `CHOI_BANBE_TUNNEL.bat:21,45` mở cùng server qua Cloudflare quick tunnel.
- Default CLI của `serve.py:3866` là `127.0.0.1`, nhưng launcher bạn bè chủ động mở rộng boundary.

### Luồng tin cậy

```text
Browser/client (không tin cậy)
  HOST_ID, UNIQ_ID, Cookie, TEAM, SCORE, RESULT, DATA1/2/3,
  reward delta, filename/path, Content-Length
        |
        v
ThreadingHTTPServer / Handler
  parse path + body, chọn _tl.uid, không enforce method
        |
        v
offline_stub / game handler
  validation không đồng đều; nhiều endpoint tin client
        |
        +--> JSON save + sidecar
        |      SAVE_LOCK, temp + os.replace cho save chính
        |
        +--> SQLite
               SAVE_LOCK, transaction tốt ở PvP/Boss; các route khác commit riêng
        |
        v
JSON/text response -> client DOM/runtime
```

### Phân loại dữ liệu

- **Client-controlled:** toàn bộ request body/query/header; `HOST_ID`, `UNIQ_ID`, cookie `dol_uid`, `DATA1/2/3`, `BP`, reward delta, `SCORE`, `RESULT`, `TEAM`, `AUTO_DAY`, `FREE_TICKET_NUM`.
- **Server-controlled:** key admin ngẫu nhiên khi boot; nonce PvP/Sky/Cloud; state session PvP/Boss/Sky trong DB; bảng giá/check-in; save/DB sau khi đã persist.
- **Authenticated thực sự:** chỉ lần POST `login_auth.php` kiểm tra password. Các request sau không có session token được ký/server-side.
- **Trusted nhưng không nên trusted:** account id trong body/cookie, full save client gửi, reward mailbox client gửi, kết quả minigame/battle client tự báo.

## 3. Findings

### SEC-001 — Identity/authentication và authorization có thể bị bypass

- **Trạng thái sau S1:** **CLOSED** cho cấu hình multi-account `--db ... --require-login`. Bằng chứng mới: `serve.py:69-94` phát/xác minh session opaque; `serve.py:878-884` chỉ lấy `_uid()` từ request context đã authenticate; `serve.py:1934-1941` chỉ phát session sau password đúng; `serve.py:3739-3750,3803-3811` bỏ qua identity wire và chặn API account-sensitive chưa login. `test_security_s1.py:144-209` chứng minh session A không đọc/ghi save, wallet/economy hoặc game state của B dù body/query khai B.
- **Severity:** CRITICAL
- **Component:** request identity, SQLite multi-account
- **Evidence:** `serve.py:3684-3713` ưu tiên `HOST_ID`/`UNIQ_ID` từ body/query rồi mới lấy cookie; `_uid()` tại `851-855` dùng trực tiếp giá trị này; `load_save`/`store_save` tại `79-96` route save theo `_uid()`. `--require-login` chỉ kiểm tra account tồn tại tại `1886-1896`, không chứng minh request đã login. Cookie tại `3843-3847` chỉ là account id không ký.
- **Attack prerequisite:** kết nối được tới port 8029 và biết/đoán account id.
- **Impact:** đọc state, ghi tiến trình/economy và dùng nonce/session dưới identity account khác. Khi tunnel/public, đây là account takeover ở cấp game.
- **Severity nếu LAN/friends:** CRITICAL.
- **Recommended fix:** session id ngẫu nhiên server-side sau login; lưu mapping session→account; derive `_uid()` chỉ từ session; bỏ identity từ body/query khỏi authorization; kiểm tra owner ở mọi mutation/read.

### SEC-002 — `/admin` làm lộ key và kiểm tra localhost bằng `Host` header

- **Trạng thái sau S1:** **CLOSED** trong phạm vi leak/Host-header. Bằng chứng mới: `serve.py:3688-3700` dùng peer IP trực tiếp và từ chối forwarded/tunnel headers; `serve.py:3816-3829` trả lỗi generic, không phản chiếu key/Host và dùng constant-time comparison; `serve.py:3688-3690` log path đã bỏ query; trang admin không render key. `test_security_s1.py:211-229` kiểm tra no/wrong/correct key, fake `Host`, response và log.
- **Severity:** HIGH
- **Component:** admin
- **Evidence:** `serve.py:3771-3775` quyết định localhost từ `_tl.host`, vốn lấy trực tiếp header `Host` tại `3677`; `3779-3780` trả key thật trong body lỗi; `1777` render key trong trang; `3941` in URL chứa key. Query string và full path được ghi log tại `3658-3659`.
- **Attack prerequisite:** kết nối được tới server; raw HTTP client có thể tự đặt `Host`.
- **Impact:** lộ key, danh sách account và tài nguyên/mail trong dashboard; kết hợp SEC-001 để chọn account mục tiêu.
- **Severity nếu LAN/friends:** HIGH; public/tunnel: CRITICAL theo chuỗi với SEC-001.
- **Recommended fix:** kiểm tra socket peer address thay vì `Host`; không echo/in key; không truyền credential bằng query; admin session riêng, constant-time token comparison, log redaction.

### SEC-003 — Nhiều mutation/economy vẫn client-authoritative

- **Severity:** HIGH
- **Component:** save sync, BP, gacha, mailbox, DayDungeon
- **Evidence:** full `DATA1/2/3` ghi last-write-wins tại `serve.py:2169-2195`; BP delta tùy client tại `1937-1953` và `2524-2547`; mailbox claim cộng trực tiếp các `ADD_*` tại `2552-2584`; client tự tạo mail tại `2609-2650`; DayDungeon cộng delta client gửi tại `3632-3648`.
- **Attack prerequisite:** gọi được endpoint dưới một identity; SEC-001 cho phép chọn identity khác.
- **Impact:** tạo tiền/vật phẩm/ticket, ghi đè save, xoá/thêm mail, phá economy hoặc dữ liệu account.
- **Severity nếu LAN/friends:** HIGH; public: CRITICAL khi kết hợp SEC-001.
- **Recommended fix:** server nhận intent nhỏ và tự tính delta; allowlist mode/item; reward id server-side, one-time claim; không nhận full currency/save từ client; giới hạn miền và kích thước mọi số/string.

### SEC-004 — Cloud Garden `GAME_END` không dùng/consume nonce

- **Severity:** HIGH
- **Component:** Cloud Garden replay protection
- **Evidence:** entry tạo `GAME_NONCE` tại `serve.py:3087-3117`; `GAME_END` tại `3118-3138` không đọc nonce, không kiểm tra ACTIVE/owner/TTL và mỗi lần đều cộng `cloud_piece`.
- **Attack prerequisite:** gọi được `cloud_garden_ranking.php` với `MODE=GAME_END`.
- **Impact:** replay reward không giới hạn và submit result không cần bắt đầu run hợp lệ.
- **Severity nếu LAN/friends:** HIGH.
- **Recommended fix:** session Cloud server-side có nonce, owner, TTL, ACTIVE/CONSUMED và cached response; consume + reward trong cùng transaction/save critical section.

### SEC-005 — Static handler có thể phục vụ save JSON và không chặn path traversal

- **Severity:** HIGH
- **Component:** static file serving
- **Evidence:** `serve.py:3715-3724` ghép `BASE_DIR / rel_path.lstrip('/')` rồi phục vụ mọi file có extension trong `STATIC_EXT`; `.json` nằm trong allowlist tại `39-42`. Không `resolve()` và không kiểm tra path còn nằm trong web root. Vì vậy JSON ở root/capture có thể được phục vụ nếu biết đường dẫn; `..` cũng không bị từ chối ở cấp server.
- **Attack prerequisite:** kết nối được tới HTTP server và biết/đoán path.
- **Impact:** lộ save JSON/capture hoặc file JSON/HTML/JS ngoài `ELDORADO_WEB`; dữ liệu có thể chứa thông tin account/request.
- **Severity nếu LAN/friends:** HIGH.
- **Recommended fix:** chỉ serve từ một web root đã resolve; reject `..`, backslash và path thoát root; deny root save/capture/log/config; tách asset allowlist khỏi extension allowlist.

### SEC-006 — Credential mặc định hard-code và password bị ghi log

- **Severity:** HIGH
- **Component:** launcher, login logging
- **Evidence:** `CHOI_BANBE.bat:9-10` và `CHOI_BANBE_TUNNEL.bat:12-13,63-66` chứa/hiển thị credential mẫu cố định (**giá trị đã redacted trong report**). `serve.py:3680-3682` log 400 ký tự đầu của mọi body trước khi `login_auth.php` parse, nên `acc` và `pw` có thể nằm trong `serve_banbe.log`.
- **Attack prerequisite:** đọc project/log hoặc biết launcher mặc định; account DB được tạo từ launcher.
- **Impact:** chiếm account mẫu/đang dùng, password tồn tại trong log và lịch sử file.
- **Severity nếu LAN/friends:** HIGH.
- **Recommended fix:** không tạo password mặc định; prompt/biến môi trường khi bootstrap; buộc đổi password; redaction theo endpoint/field trước log; rotate credential đã từng dùng.

### SEC-007 — Sudoku/Generator và một số gameplay result không có proof server-side

- **Severity:** MEDIUM
- **Component:** RubyFarm minigame
- **Evidence:** `sudoku_start` chỉ lưu difficulty+timestamp tại `serve.py:3468-3487`; `sudoku_claim` tại `3495-3524` chỉ kiểm tra session/difficulty/TTL, không có puzzle/solution/proof. `genrep_claim` tại `3431-3464` nhận `GREAT` từ client rồi clamp. `wallet/award` tại `3351-3401` nhận score client nhưng có cooldown/cap và reward cap.
- **Attack prerequisite:** có ticket/session hợp lệ.
- **Impact:** claim reward mà không chơi/giải đúng; Generator có thể tự báo mức tốt nhất trong giới hạn.
- **Severity nếu LAN/friends:** MEDIUM (HIGH nếu economy được dùng cạnh tranh).
- **Recommended fix:** server sinh challenge/puzzle seed, lưu expected solution/progress proof và consume one-time; Generator dùng server-verifiable event transcript hoặc hạ trust classification rõ ràng.

### SEC-008 — Route mutation không enforce HTTP method/CSRF/origin

- **Severity:** MEDIUM
- **Component:** HTTP boundary
- **Evidence:** `do_GET` và `do_POST` cùng gọi `_handle` tại `serve.py:3661-3665`; `offline_stub` không nhận/enforce method; response luôn gửi `Access-Control-Allow-Origin: *` tại `3842`; mutation dùng form-urlencoded đơn giản và không có CSRF token/origin check.
- **Attack prerequisite:** nạn nhân mở trang độc hại hoặc attacker truy cập trực tiếp port LAN.
- **Impact:** cross-site request có thể kích hoạt mutation; GET cũng có thể làm thay đổi state; SEC-001 cho phép kẻ gửi tự chọn identity mà không cần cookie.
- **Severity nếu LAN/friends:** HIGH khi ghép SEC-001/003.
- **Recommended fix:** route table có method cố định; reject GET cho mutation; validate `Origin`/`Host`; CSRF token nếu tiếp tục cookie auth; CORS allowlist hoặc không bật CORS cho game same-origin.

### SEC-009 — Không giới hạn request body và payload lưu trữ

- **Severity:** MEDIUM
- **Component:** availability/input validation
- **Evidence:** `serve.py:3670-3672` tin `Content-Length` và đọc toàn bộ vào RAM; không có global maximum, timeout hoặc size limit. Nhiều string (`DATA1/2/3`, quest, item, mail) được ghi nguyên dạng.
- **Attack prerequisite:** kết nối được tới server.
- **Impact:** RAM exhaustion, thread starvation, DB/save/log phình lớn; malformed Content-Length có thể làm thread lỗi.
- **Severity nếu LAN/friends:** MEDIUM; public: HIGH.
- **Recommended fix:** giới hạn body nhỏ theo route, validate Content-Length trước read, socket/read timeout, field length/count limits và 413 response.

### SEC-010 — Sky replay/session không đồng nhất giữa SQLite và JSON

- **Severity:** MEDIUM
- **Component:** Sky Garden
- **Evidence:** DB mode bind owner và consume tại `serve.py:173-198`, nhưng không kiểm tra TTL; `update_sky_result` chỉ gọi validation khi `DB_CONN` tồn tại (`2960-2963`). JSON mode vì vậy chấp nhận update không cần nonce/session và có thể replay; response consumed không được cache để retry idempotent.
- **Attack prerequisite:** JSON mode hoặc nonce Sky cũ chưa bị thay bởi run mới.
- **Impact:** score/ranking client-reported có thể replay/submit ngoài run; retry sau mất response không có replay cache chuẩn.
- **Severity nếu LAN/friends:** MEDIUM.
- **Recommended fix:** dùng cùng session state machine cho JSON/SQLite: owner, TTL, ACTIVE/CONSUMED, cached response, atomic consume.

### SEC-011 — Offline mode vẫn có outbound network chủ động/conditional

- **Severity:** MEDIUM
- **Component:** legacy client/server networking
- **Evidence:** missing asset tự gọi `game.busidol.com` và cache xuống disk tại `serve.py:1805-1837`, kể cả offline mode. Bundle còn request JSONP tới `ipinfo.io`, remote Google ad script trong `index__mobile.html:66`, YouTube iframe API, Facebook image, CDN ping/IP cũ và WebSocket cũ (một số phụ thuộc platform/feature flags). `proxy` mode chủ động forward tại `1701-1722` là hành vi có chủ đích.
- **Attack prerequisite:** client mở feature/branch tương ứng hoặc asset local bị thiếu; máy có Internet.
- **Impact:** rò metadata/IP, phụ thuộc server cũ, tải code/content ngoài không cố định, offline không hoàn toàn deterministic.
- **Severity nếu LAN/friends:** MEDIUM.
- **Recommended fix:** S1 chỉ audit runtime egress bằng browser/network log; sau đó allowlist same-origin cho offline mode, disable auto-fetch/JSONP/ads/WSS legacy hoặc đặt sau opt-in rõ ràng.

### SEC-012 — jQuery 2.1.3 và thiếu browser security headers/CSP

- **Severity:** MEDIUM
- **Component:** frontend/supply-chain defense
- **Evidence:** `index__mobile.html:32` nạp `lib/jquery-2.1.3.min.js`; bản này cũ hơn các mốc vá prototype pollution/XSS của jQuery 3.4/3.5. Không thấy CSP; `_respond` tại `serve.py:3833-3848` không gửi `X-Content-Type-Options`, frame protection hay `Referrer-Policy`. Trang còn remote script không SRI tại `index__mobile.html:66`.
- **Attack prerequisite:** cần một đường đưa input không tin cậy tới jQuery/DOM sink hoặc third-party bị compromise.
- **Impact:** tăng blast radius XSS/supply-chain; không phải exploit độc lập đã chứng minh trong audit này.
- **Severity nếu LAN/friends:** MEDIUM.
- **Recommended fix:** inventory compatibility trước khi nâng jQuery; tự host/remove third-party; CSP triển khai dần; thêm `nosniff`, frame policy và referrer policy. Không bật CSP phá game trong một lần.

### SEC-013 — Password hash nhanh và session cookie thiếu thuộc tính/phân tách session

- **Severity:** MEDIUM
- **Component:** authentication storage
- **Evidence:** `serve.py:857-883` dùng salted SHA-256 một vòng; cookie `dol_uid` tại `3845-3847` không `HttpOnly`, không `Secure`, không random, không expiry server-side/revocation và không rotate sau login.
- **Attack prerequisite:** đọc được DB/hash hoặc có XSS/local access.
- **Impact:** password yếu dễ brute-force offline; account id cookie có thể sửa trực tiếp và không đại diện phiên đăng nhập.
- **Severity nếu LAN/friends:** MEDIUM; phần sửa cookie là điều kiện bắt buộc của SEC-001.
- **Recommended fix:** `scrypt`/Argon2id/PBKDF2 có work factor và migration-on-login; opaque session cookie `HttpOnly`, `SameSite`, `Secure` khi TLS, expiry/revocation server-side.

### SEC-014 — Validation Auto Play cho phép ngày âm/không hợp lệ

- **Severity:** LOW
- **Component:** Auto Play
- **Evidence:** `serve.py:1977-1991` parse `AUTO_DAY` nhưng không yêu cầu miền dương/hợp lệ; request âm vẫn trừ 1000 BP rồi tạo pass đã hết hạn. `ON_OFF` tại `1971` không giới hạn enum.
- **Attack prerequisite:** user/client tự gửi request malformed.
- **Impact:** mất BP hoặc state kỳ lạ; không tạo lợi ích tài chính rõ ràng.
- **Severity nếu LAN/friends:** LOW.
- **Recommended fix:** allowlist package/day server-side và `ON_OFF ∈ {0,1}`; thêm idempotency key cho purchase retry.

### SEC-015 — World Boss không có wire nonce và JSON mode có cross-file crash window

- **Severity:** LOW
- **Component:** World Boss 2026
- **Evidence:** session owner/TTL/consume tồn tại, nhưng retry dựa fingerprint tại `serve.py:496-533`; hai trận khác nhau có RESULT/SCORE/TEAM/ITEM/ETC giống nhau có thể collision trong retry window. `_boss_persist` ghi sidecar rồi save ở hai file khác nhau trong JSON mode tại `428-453`, không thể transaction chéo file.
- **Attack prerequisite:** payload hai trận trùng hoàn toàn hoặc crash đúng cửa sổ ghi JSON.
- **Impact:** replay/collision response hoặc state/save tạm lệch; SQLite mode tránh được transaction gap.
- **Severity nếu LAN/friends:** LOW. Đây là known limitation đã được chấp nhận, không phải blocker PvP.
- **Recommended fix:** không sửa trong S0; dài hạn chỉ protocol nonce thật mới loại bỏ ambiguity. Ưu tiên chạy Boss bằng SQLite nếu mở nhiều người.

## 4. Endpoint inventory

Code có **71 top-level route groups** trong `offline_stub`; sau khi mở rộng ba operation PvP và ba operation Boss, inventory có **75 gameplay/API operations**, cộng `/admin`, static serving và proxy/capture fallback. Server hiện không enforce method nên cột method thực tế đều là `GET/POST`.

| Nhóm | Endpoint/route | Mutation | Identity/auth | Replay/session | Persistence/output nhạy cảm |
|---|---|---:|---|---|---|
| Boot/static | `get_app_file`, static extensions, login page, time/day/connect/notice/counter routes | Có ở asset cache | Không | Không | Có thể đọc/cache file; trả boot URLs |
| Login | `check_black_list_db`, `login_auth` | Cookie login | Password chỉ ở login; request sau tin id | Không | accounts/saves; uid trả client |
| BP/AutoPlay | `bonuspoint/get/add/reset`, `autoplay/get/set/update/insert` | Có | `_uid()` không đáng tin | Không/idempotency thiếu | save/DB economy |
| Core save | `cnm_exist`, `cnm_insert_new_user`, `cnm_update_user_to_server_cry`, `cnm_update_quest` | Có | `_uid()` | Không | full save/quest |
| Hardmode/item/pay | `hardmode/get/update`, `item/update_item`, `item/update_data2_item` (+ alias), `save_userinfo_after_pay` | Có | `_uid()` | Không | save/DB |
| Charbook | `get_ally_list`, ally/enemy list+reward add/remove/delete (có alias legacy) | Có | `_uid()` | Deduplicate chuỗi một phần | save/DB |
| Gacha/BP | `gacha/gacha_char` | Có | `_uid()` | Không | client BP delta |
| Mailbox | `put_mailbox_reward`, `get_reward2_mailbox`, `check_reward_sn_i`, `del_reward_sn_i`, `del_reward_sn_all_n_save` | Có | `_uid()` | first-clear guard hạn chế; claim delta không bind reward | save/DB, reward/mail |
| Events/guild/log | `get_event_info`, `attendance_event`, `update_guild_*`/`guild/*`, client error/hacking/debug log | Có nhẹ/log | `_uid()` hoặc không | Không | event data/log injection giới hạn 200 ký tự |
| Four Gods | `temple/update_dragon_info`, `dragon_info_cheat` | Có | `_uid()` | Lock, không nonce | Cloud Piece/gauge |
| PvP 2025 | ranking, enter, update result | Có | `_uid()` yếu | **Nonce 128-bit**, owner, TTL, ACTIVE/CONSUMED, cached retry, DB/JSON persistence | save + pvp tables/JSON |
| Sky 2026 | ranking, enter, update result (+ legacy ranking alias) | Có | `_uid()` yếu | DB one-time nonce; thiếu TTL/cache; JSON bỏ validation | save + sky tables |
| Boss 2026 | ranking, enter, update result; legacy ticket get/update | Có | `_uid()` yếu | Session/owner/TTL/consume; fingerprint retry, không wire nonce | save + boss sidecar/tables |
| Cloud Garden | ranking/start/end cùng route; edit/evolution (+ alias) | Có | `_uid()` yếu | Entry nonce nhưng GAME_END không dùng | Ruby/Cloud Piece/score |
| Toolshop | balances, convert | Có | `_uid()` yếu | Lock, validation amount tốt hơn | currencies trong save |
| RubyFarm wallet | checkin, mywallet, award, genrep start/claim, sudoku start/claim, tickets, withdraw | Có | `_uid()` yếu | Daily markers/session một lần; gameplay proof yếu | wallet + currencies |
| DayDungeon | get day, get/update ticket | Có | `_uid()` yếu | Không | ticket client delta |
| Admin | `/admin` | Read-only | key query + Host-header “localhost” | Không | account/resource/mail metadata |
| Proxy/capture | mọi `.php`, `APP_VALIDATE`, `APP_ANALYSIS`, `KR_INPUT` chưa handle | Có thể forward | Không | Không | outbound live host + capture/replay |

## 5. Session/replay comparison

| System | Entropy/identity | TTL | Consume/cache | Restart | Authority |
|---|---|---|---|---|---|
| PvP 2025 | `token_hex(16)`; owner check nhưng owner dựa `_uid()` yếu | 1800s | ACTIVE→CONSUMED, cached response, transaction | Có, DB và JSON | Client-reported result được validate/bound, **không server-authoritative** |
| Sky | `token_hex(8)`; DB owner check | Không enforce | DB consume một lần, không cache; JSON không enforce | DB có | Client-reported wave/result |
| World Boss | Server session; wire không nonce, fingerprint | Có | ACTIVE/CONSUMED + retry fingerprint | Có | Client score/result được validate; không server-authoritative |
| Cloud | `token_hex(8)` lúc start | Không | Không consume/check ở GAME_END | Nonce lưu save nhưng vô hiệu | Client-reported score/reward calculation |

## 6. Persistence/transaction assessment

- JSON save chính dùng same-directory temp + `os.replace` (`serve.py:93-109`): ghi một file nguyên tử.
- `SAVE_LOCK` bảo vệ phần lớn read-modify-write trong một process.
- PvP SQLite dùng `BEGIN IMMEDIATE`, session/save/leaderboard commit cùng transaction.
- Boss SQLite đưa save, state, damage và session vào cùng DB transaction; JSON sidecar + save không atomic chéo file.
- Generic SQLite `db_store_save` commit theo từng call; không có transaction xuyên nhiều endpoint.
- Lock/process hiện không bảo vệ nếu chạy hai process cùng trỏ một JSON save.

## 7. Legacy outbound network inventory

| Loại | Ví dụ | Phân loại |
|---|---|---|
| Server live host | `game.busidol.com` qua `proxy_forward`/`fetch_and_cache` | **ACTIVE** trong proxy; **ACTIVE khi thiếu asset** cả offline |
| Client IP geolocation | `ipinfo.io` JSONP | **POTENTIALLY ACTIVE** trên platform WEB |
| Ads/third-party script | Google ads trong HTML | **ACTIVE/POTENTIAL** khi trình duyệt không chặn |
| YouTube/Facebook images | iframe API/profile image | **FEATURE-CONDITIONAL** |
| CDN ping và IP traffic cũ | nhiều IP HTTP cũ | **CONDITIONAL/UNKNOWN**, cần runtime egress capture |
| WebSocket cũ | hai host/IP WS | **FEATURE/FLAG-CONDITIONAL** |
| Honeygain policy links | chuỗi text | **DEAD/CONTENT STRING** theo code-read |
| Internal TV/platform endpoints | IP private, KT/Tizen/LG/payment | **PLATFORM-CONDITIONAL**, không thấy active trong flow WEB thường |

## 8. Secret scan (redacted)

- Không scan baseline, DB/save thật, capture hay `.git`.
- Có credential mẫu hard-code trong `CHOI_BANBE.bat:9-10` và `CHOI_BANBE_TUNNEL.bat:12-13,63-66`; giá trị không được ghi vào report.
- `ADMIN_KEY` được tạo ngẫu nhiên lúc boot, không hard-code, nhưng bị lộ qua response/query/log như SEC-002.
- Không xác nhận thấy bearer/API key/private key hard-code trong source hiện tại. Các hit “password/token” trong bundle/library phần lớn là tên API/string thư viện, không đủ bằng chứng là secret.

## 9. Positive controls đã có

- PvP nonce có entropy tốt, ownership, TTL, persisted session, transaction và cached retry.
- Boss có owner/session/TTL/consume và SQLite transaction; fingerprint limitation được document đúng.
- JSON save chính đã atomic ở cấp file.
- Economy mới như Toolshop/withdraw/check-in dùng server-side rate/reward, positive bounds và `SAVE_LOCK` tốt hơn các endpoint legacy.
- Admin HTML escape dữ liệu account trước khi render (`serve.py:1732-1800`).

## 10. Recommended S1 scope

S1 nên rất hẹp và theo thứ tự:

1. **Identity/session foundation:** opaque session server-side, derive uid, authorization middleware, test hai account/cross-account.
2. **Admin containment:** bỏ key leak/query key, peer-IP check, log redaction; tạm disable admin ngoài loopback.
3. **HTTP boundary:** method table, body limits, static web-root containment, Origin/CORS policy.
4. Sau khi nền trên pass mới harden economy legacy và Cloud nonce; không gộp tất cả vào một patch.

Mỗi bước phải dùng DB/save/port riêng, có test cross-account, replay, concurrent mutation và restart persistence. Không triển khai fix trong Round S0.

## 11. Final assessment

- **Threat model:** COMPLETE ở mức code audit; chưa chạy runtime egress capture và chưa penetration-test server thật.
- **Safe for solo localhost:** **WITH LIMITATIONS** — vẫn có save exposure, browser cross-site risk và client-trusted economy.
- **Safe for LAN/friends:** **NO** — identity/authz và admin boundary chưa đủ.
- **Safe for public Internet/tunnel:** **NO**.
- **Server 8029:** **UNCHANGED BY AUDIT** — không có lệnh restart/stop từ S0. Tuy nhiên PID quan sát đã đổi 20348→3220 trong thời gian audit; command line cuối vẫn giữ nguyên cấu hình DB/login/host/port/log/capture.

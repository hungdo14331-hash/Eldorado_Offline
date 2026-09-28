# ============================================================
#  HANDOFF / NEXT-SESSION MEMORY  —  busidol (Eldorado) offline
#  Ghi luc: 20260921 (sang) | NGON NGU: tieng Viet
#  ============================================================
#  === 1) HE THONG / BAN CANH  ===
#  Game: Eldorado (busidol) — private/offline server do serve.py mo.
#  NGUOI DUNG tu chay server TUY TAY trong PowerShell (AI KHONG restart duoc).
#  Port: 8029. Client: http://localhost:8029/ELDORADO_WEB/source_20240722/index__mobile.html
#  Restart = kill port 8029 -> cd C:\busidol_offline
#    -> & python serve.py --mode offline --port 8029
#
#  === 2) MUC TIEU (da chot) ===
#  Xu ly offline rewards ON DINH (khong trung lap, khong stub):
#    - Diem danh / thu offline / first-clear stage: quy ve MAILBOX that (mail->claim).
#    - ToolShop: shop quy doi tien te cho cac mode chua mo (tien): vang/ruby->BP/cloud/essence.
#    - CHAR_EVO_9: tru dung 1000 essence (khong con "essence khong doi").
#    - RubyFarm: web mini-game kiem ruby (vi rieng) + nut "rút" chuyen ruby ve tai khoan game.
#  Duong loi: sua serve.py (khong dong min.js). Trang web: ELDORADO_WEB/convert.html + rubyfarm.html (static).
#
#  === 3) DA LAM / VERIFIED (session gan nhat) ===
#  - serve.py hien tai MD5 = 57CAB1281B94C3CB5643079FAE8B5E29 ; SIZE = 107500 ; py_compile OK.
#  - "CHOI NHIEU TAI KHOAN" (DA XONG, chay song song duoc): serve.py them 3 CLI moi — 
#      --save-file <path> (dinh nghia save instance), --uniq-id <id> (tra trong check_black_list_db,
#      phai khop USER_NAME + DATA1 field dau cua save), --log <file> (log rieng, delay=True). 
#      UNIQ_ID goc la global o dau file (khong con hardcode stub). Luu y: moi file save can 
#      _norm_save, cap quyen ghi inline; CAPTURE cung nen rieng (--capture capture_<ten>).
#      Save lam viec hien co: save_anh.json (ELDORADO_OFFLINE_0001, luu LIVE level 29),
#      save_em.json (0002, nguon TRAI_TAIKHOAN_CU_GIU_LAI/offline_save_GIU_LAI.json level 100),
#      save_moi.json (0003, nguon offline_save.json.preserve seed level 1). Bat: CHOI_ANH.bat
#      (port 8029) / CHOI_EM.bat (8031) / CHOI_MOI.bat (8033). MOI instance = 1 tai khoan rieng.
#      Test verified: 3 server chay dong thoi, moi port tra USER_NAME + bp rieng (43526/100125/0),
#      log tach rieng (serve_anh/em/moi.log). NGUOI DUNG: mo 3 tab, moi tab 1 port de choi song song.
#  - "MAY CHU NHIEU NGUOI CHOI (SQLite + login)" (DA XONG): chay 1 phien duy nhat, moi account
#      co save rieng trong SQLite, co mat khau. CLI moi:
#        --db <file>          bat che do multi-account: save route theo HOST_ID/UNIQ_ID request
#                             (thread-local), luu vao bang `saves` (id,payload); bang `accounts`
#                             (id,pw_hash; sha256 salt+pw).
#        --require-login      (kem --db) chi account co trong bang `accounts` vao duoc; id khong
#                             ton tai -> check_black_list_db tra "BLACK_LIST" (chan vao game).
#        --host 0.0.0.0       bind ra LAN/internet cho ban be truy cap.
#        --add-user TEN --add-pass MK --db file   tao/cap nhat account roi thoat.
#      FLOW: ban be mo /ELDORADO_WEB/login_page.php (stub HTML), dang nhap -> set localStorage
#      eldorado_fb_temp_id = account id -> nhay vao game; client GLO doc dung key do lam host_id,
#      nen HOST_ID moi sau do = account id -> save rieng. Stub: login_page.php (HTML form) +
#      login_auth.php (POST acc,pw -> json {ok,uid}). NGUOI DUNG: RU ban be can 1 ID + MAT KHAU do
#      --add-user tao ra; mo port 8029 / NAT / tunnel de ban be o xa vao duoc.
#      BASE-URL KHÔNG CON hardcode localhost: gan nhat trang thai rewrite dung Host header cua
#      request (base_url(): _tl.host) nen chay qua IP/domain cung tu chinh JS. Bat: CHOI_BANBE.bat
#      (--db busidol.db --require-login --host 0.0.0.0 --port 8029).
#      Test verified (python -m py_compile + chay 8039/8041): login sai/đúng, black-list chan
#      intruder, cnm_exist "NEW" cho account moi, insert+reload tra DATA1 cua dung account,
#      cnp update chi anh huong account do, get_app_file/static/min.js rewrite theo custom Host.
#      FIX "HACKING DETECTED" khi F5/reload: init_platform_GLO doc eldorado_fb_temp_id roi XOA
#      ngay, nen lan reload UNIQ_ID=null -> --require-login tra BLACK_LIST -> client GLO mo
#      S_EXITPOPUP.start(2) = "HACKING DETECTED". Da sua: login_auth ok => server Set-Cookie
#      dol_uid=<account> (Path=/, Max-Age=400ngay, SameSite=Lax trong _respond); _handle khi
#      body/query khong co HOST_ID/UNIQ_ID hop le thi doc Cookie dol_uid lam identity (reload
#      xai duoc, check_black_list tra NONE+UNIQ_ID=account). MUON DOI ACCOUNT: login lai qua
#      login page (cookie bi ghi de). Da test: login BM -> cookie=1 -> reload check_black NONE/BM
#      -> insert BM -> reload cnm_exist USER=BM DATA1=BM,9999 -> login EM -> reload NONE/EM.
#  - "X5 VANG KHI DANH MOI BAN (stage clear)": get_app_file.php noi them entry thu 6
#      ovr_gold_x5.js (sau eldorado_all bundle, loader split theo "|" chay tuan tu).
#      File wrapt CAL.get_wingold x5 (stage thuong + hard, vi 2 loai deu goi CAL.get_wingold)
#      va CAL.get_wingold_npc x5 (PVP/NVN win, = USER.score*10). KHONG sua min.js.
#      Luu y: get_rankinggold goi CAL.get_wingold roi tu cap min(t,9900) -> khong doi;
#      vang nhat tu quai/vat trong tran (pickup) khong thuoc get_wingold, van nhu cu.
#      Client tua nap lai bundle khi re-load (khong can xoa cache, file moi).
#  - "BO GIOI HAN NANG CAP = LEVEL NGUOI CHOI" : get_event_info (EVENT_TYPE=999) tra
#      event_arr=[13] -> client set AUTO_EVENT_FLAG[13]=1 -> 4 chot cap-level trong
#      S_UPGRADE.onClick (`AUTO_EVENT_FLAG[13]!=1 && (u>=USER.level | 80>USER.level)`)
#      bi bo qua. Flag 13 KHONG duoc doc noi khac trong min.js (da grep). Cac hard-max
#      theo loai (USER_STORAGE_MAX, ITEM_STORAGE_MAX, UPGRADE_MAX...) van giu nguyen.
#  - "VANG + RUBY x5 CHO MOI PHAN THUONG" (DA BAKED VAO HANG SO, REWARD_MULT=5 dau serve.py):
#      CHECKIN_REWARDS GOLD: 250K/500K/1M/1.5M/2.5M (ngay 1/6/13/21/28);
#      CHECKIN_REWARDS RUBY: 500/750/1K/1.5K/2K/4K/5K (ngay 4/9/15/20/27/30/31);
#      MAILBOX_GIFTS GOLD 1.000.000 + RUBY 500 (mail quà hằng ngày);
#      OFFLINE GIFT GOLD 25.000.000 + RUBY 5.000 (1 lần).
#      (BP/cloud/essence GIU NGUYEN khong x5; cac gia tri nay la gia BAKED, neu doi
#      REWARD_MULT phai nhan lai cac o GOLD/RUBY bang tay.)
#      LUU Y: thuong RUBY tu minigame (wallet ruby qua award/genrep/sudoku) KHONG x5 —
#      chi cac phan thuong "gift/reward" o tren. Neu muon x5 do thuong minigame thi bao.
#  - HE VE TICKET (mau tieu da chot, DA XONG — can user restart serve.py + F5 rubyfarm):
#      - 2 loai ve: generator (⚙️ "ve may phat") va sudoku (🧩). Moi ngay free 3 ve/loai,
#        cap lazy qua ensure_ticket_grant(s) (marker s["ticket_free_day"]="YYYYMMDD");
#        goi o mywallet.php / start / tickets.php (idempotent theo ngay).
#      - Mua ve bang VANG: TICKET_PRICES = {generator:2000, sudoku:1000} /cai (x1..99),
#        endpoint wallet/tickets.php ACTION=info|buy&TYPE&AMOUNT (x-www-form-urlencoded).
#      - Luu tru: s["tickets"] = {"generator":N,"sudoku":M}; helper add_tickets/spend_tickets/
#        ticket_count. Spend phai goi ensure_ticket_grant truoc.
#      - Choi bang ve KHONG count vao (va KHONG bi) gioi han 300/ngay va khong co cap moi/luot.
#  - Generator Repair = game VE (1 ve/luot, KHONG con phi ruby / gioi han 3-luot-24h):
#      start  : wallet/genrep_start.php POST DIFF -> spend 1 "generator" ticket;
#                loi "need ticket" kem tickets; luu genrep_session {diff,ts}
#      claim  : wallet/genrep_claim.php POST DIFF,GREAT -> session con han (TTL 900s),
#                thuong = prize + min(GREAT,25)*great, cong wallet_ruby + wallet_earned.
#      miss thua (client): easy3/normal3/hard5/nightmare10 ; GENREP_GREAT_CAP=25.
#      phan thuong: prize easy10/normal20/hard50/nightmare150 ; great +1/+2/+3/+7.
#      Cong thuc nam o GENREP_DIFFS (dau serve.py), client anh xa GENREP_FEE=1 ve / GENREP_MISS.
#    Sudoku = game VE (1 ve/luot, tinh gio): SUDOKU_DIFFS easy/medium/hard/expert
#      prize 10/20/35/50, time 600/900/1200/1500s ; SUDOKU_SESSION_TTL=900.
#      start: wallet/sudoku_start.php POST DIFF -> spend "sudoku" ticket (loi "need ticket"),
#             tra prize/time, luu sudoku_session. claim: wallet/sudoku_claim.php POST DIFF
#             -> +prize vao wallet. Het gio (client) = thua, mat ve (khong claim).
#    Client (iframe) goi truc tiep fetch('/ELDORADO_WEB/wallet/...') qua rubyfarm_bridge.rfApi();
#    sau claim/lose/thua goi rfRefresh() -> parent loadWallet() (HUD ve va ruby). Khi mo game
#    doc lap KHONG co server: rfApi tra NETERR -> game van choi duoc (practice, khong ve/thuong).
#    rubri thưởng luon vao WALLET (khong phai DATA1[2]).
#  - mywallet.php tra them: tgen, tsud, tfree={gen,sud}, tprices={gen,sud}.
#  - checkin.php claim them nhanh GTICKET->add_tickets("generator"), STICKET->add_tickets("sudoku")
#    (CHECKIN_REWARDS co ve o ngay 3,7,10,14,17,21,22,24,28). Client: rwIcon() hien 🎫/🧩 khi
#    khong co icon, typLabel booth ve viet "ve máy phát"/"ve sudoku".
#  - rubyfarm.html: chip HUD 🎫 ⚙️n · 🧩n (chi hien khi >0), tbox mua ve trong pageWallet
#    (renderTickets/buyTicket), bảng fee_tbl genrep (1 ve) + sudoku (Mức/Giờ/Phí/Thưởng).
#  - RACE CONDITION da fix: moi load->sua->ghi phai bao trong "with SAVE_LOCK:" (cry/quest/
#    mailbox/gacha/item/cloud_garden/temple). Root cause cu: thư diem danh/clear "bien mat"
#    vi 2 handler ghi de save dong thoi.
#  - ToolShop:
#      GET  ELDORADO_WEB/toolshop/get_balances.php  -> {gold,ruby,bp,cloud,essence}
#      POST ELDORADO_WEB/toolshop/convert.php (FROM/TO/COUNT=so nguon bo ra)
#      -> CONVERT_RATES[(from,to)]=(cost,gain); COUNT*target = COUNT*gain//cost; leftover khong mat.
#      Ti gia hien tai (de doi o dau file, gan MAILBOX_GIFTS):
#        120000 GOLD=5 BP | 500 RUBY=50 BP | 120000 GOLD=12 CLOUD | 100000 GOLD=10 ESSENCE
#        100 BP=5000 RUBY | 100 BP=2000000 GOLD
#      Trang: http://localhost:8029/ELDORADO_WEB/convert.html
#      LUU Y: client phai POST dang x-www-form-urlencoded (parse_body KHONG hieu multipart).
#  - Offline gift mot lan: stamp "20260921" -> mail GOLD 5M/RUBY 1000/BP 1500 + char 96/97/99.
#    Da nhan. Khong respawn (co "offline_gift_sent").
#  - CHAR_EVO_9 fix: client KHONG gui CEL_PIECE (edit_cloud_garden chi forward MODE/ADD_PIECE/ETC).
#    Server tu tru CELESTIAL_PIECE_EVO_9=1000 khi MODE=CHAR_EVO_9, tra "cel_essn" moi.
#    cnm_exist cung day "celestial_piece_evo_9"="1000" de client hien thi dung chi phi.
#  - Backup cu (noi bo): serve.py.bak_f72a10c, offline_save.json.bak_reseed.
#    ACCT_BACKUP_20260919_211218\, BACKUP_DAILY_REWARD_20260919_*. (CU, da lac hau).
#  - RubyFarm wallet (muc tieu moi — DA XONG, can user restart + reload):
#      Trang: http://localhost:8029/ELDORADO_WEB/rubyfarm.html
#      5 game: catch(click, 30s) / memory(8 cap) / guess(1-100) / simon / rps(3 tran).
#      Server tinh thuong TU SCORE (page chi la front-end; khong tin client):
#        catch score//10 cap30 | memory so cap cap20 | guess max(0,8-moves) cap15
#        simon level-1 cap25 | rps wins*5 cap15  (MINIGAME_CD_SEC=5s, DAILY_RUBY_CAP=300).
#      Vi rubi rieng luu trong save: s["wallet_ruby"], s["wallet_last"][game]=ts,
#      s["wallet_day"], s["wallet_earned"]. Khong bao gio chuyen thang vao gâme ruby.
#      Endpoint (x-www-form-urlencoded, bo "with SAVE_LOCK:"):
#        GET/POST wallet/mywallet.php -> {wallet,ruby,gold,day,earned,cap}
#        POST wallet/award.php (GAME,SCORE) -> +wallet; loi: cooldown(waits), daily cap, no reward
#        POST wallet/withdraw.php (AMOUNT) -> tru wallet, cong DATA1[2] (ruby gâme).
#      Da test tren save temp: award/cap/cooldown/wait/withdraw/nhu deu dung; rubyfarm.html HTTP 200.
#  - RubyFarm DIEM DANH hang ngay (web): CHECKIN_REWARDS = 31 ngay (danh sach da chot,
#    ngay N = CHECKIN_REWARDS[N-1]); endpoint wallet/checkin.php ACTION=info|claim; trang thai
#    lưu s["farm_ci"]={"ym","days"} (moi thang tu reset). claim 1 lan/ngay, cong thang vao
#    account (GOLD/RUBY->DATA1; BP/cloud/essence->keys). Tra loi: already / no reward for today.
#    Da test: info 31 entries -> claim day21 +500K gold -> already -> reset day -> claim lai OK.
#
#  === 4) CON LAI (chua lam) ===
#  - Charbook enemy/ally book; guild; achievements; tower gold (8* evo da on);
#    auto_event_system/get_event_info (EVENT_TYPE 999) DA ON event 13 (bo cap nang cap theo
#    level — xem muc 3); attendance da on.
#  - RubyFarm da co SPA moi (sidebar nav, HUD icon chuân game, 5 minigame dang len
#    GAMES registry trong rubyfarm.html). De THEM minigame moi: them 1 muc vao GAMES
#    (id/title/em/desc/rwd/page) o dau script + them game key vao _minigame_ruby() serve.py.
#  - 2 game CU cua user (thu muc C:\busidol_offline\minigame) da ghep vao RubyFarm bang IFRAME:
#      - generator_repair.html (doi ten tu "Generator Repair Trainer.html" vi ky tu cach gay 404)
#      - sudoku.html
#    Co che: file game hoc <script src="rubyfarm_bridge.js"></script>; can tien te / claim bang
#    window.rfApi('/ELDORADO_WEB/wallet/...'); cap nhat HUD bang window.rfRefresh().
#    Bridge chi hoat dong khi nhung iframe, mo doc lap van choi binh thuong.
#      genrep: KHI bat dau repair goi genrep_start (tru 1 ve); done ("Generator repaired!" 100%,
#              progress repair) goi genrep_claim (DIFF,GREAT=tong greats - greatsAtStart) -> +ruby;
#              miss du -> thua, mat ve (khong claim); doi mode/do kho khong duoc khi dang chay,
#              doi mode reset stats; da bo nut "Reset stats".
#      sudoku: "Tạo mới" goi sudoku_start (tru 1 ve, tra time cho countdown - timer hien so phut
#              con lai, .low khi <=60s); checkSolution goi sudoku_claim -> +ruby; het gio = thua;
#              "Tao ma tran"/"Nhap"/"Mo save" = practice (khong ve, khong thuong). Da BO nut Goi y.
#    LUU Y: file game o C:\busidol_offline\minigame -> URL goc /minigame/... (KHONG nam trong ELDORADO_WEB).
#    genrep/sudoku KHONG con di qua award.php / rfAward (da xoa khoi _minigame_ruby).
#  - MINIGAME_COST = {} (o dau serve.py): phi vang de choi (user muon sau nay 1 so game tôn vang).
#    Dang khau tru NGUYEN TU trong award.php khi nhan thuong (gold < cost -> ERROR "need gold").
#    Bat tinh nang: gan MINIGAME_COST['game'] = so vang (vd 20000). Neu muon tinh phi tai luc
#    BAT DAU choi (khong phai luc nhan thuong) can them endpoint play.php — CHUA lam.
#  - HUD can 5 tai nguyen: mywallet.php da tra them bp/cloud/essence.
#  - Icon game (lau lai can dung, khong thay emoji):
#      image/ui/0_common/co_goldbar.png | co_rubybar.png | co_bpbar.png | co_cloudbar.png | co_celestialbar.png
#      nen: image/ui/1_mainmenu/mm_bg.jpg (1280x720) ; logo: image/bg/introLogo_en.png
#  - Tinh (neu muon) thêm mini-game khac / dieu chinh ti le thuong: sua _minigame_ruby()
#    va DAILY_RUBY_CAP o dau serve.py (canh MINIGAME_CD_SEC=5).
#
#  === 5) LUU Y KY THUAT ===
#  - Bo doc lonely truoc khi edit file (Edit tool yeu cau Read gan day).
#  - Test ky thuong chay temp: copy offline_save.json -> temp dir, set serve.SAVE_FILE,
#    khoi dong ThreadingHTTPServer tren port 0 -> POST that -> so sanh save. KHONG dung save that.
#  - LOG: serve.log ghi moi request; tim "ToolShop", "cloud_garden edit", "->" de debug.
#  - Khi sua CONVERT_RATES / them endpoint PHP: bat buoc bo "with SAVE_LOCK:" neu chuyen doi tien.
# ============================================================
#  === 6) 20260922: GARDEN MODES (SKY + CLOUD) DA FIX ===
#  - SKY GARDEN (card 7, S_RANKING): SKY_2026/get_sky_ranking.php, enter_sky_game.php,
#    update_sky_result.php da implement (save keys: sky_wave, sky_nonce).
#    get_sky_ranking tra STATE=SUCCESS + ranking_list + entry_fee_ruby=1; enter ENTRY_RUBY
#    tru phi 1+wave//10 ruby; update RESULT=W moi cap nhat best wave.
#  - CLOUD GARDEN (card 6, S_RANKING_CLOUD_GARDEN): cloud_garden/cloud_garden_ranking.php
#    MODE RANKING_GET / GAME_TICKET / GAME_RUBY / GAME_END (save keys: cloud_score,
#    cloud_score_day, cloud_ticket_day, cloud_ticket_left, cloud_nonce). Free ticket 3/ngay,
#    ENTER_RUBY 100, win_piece=score//20 (cap 500). RANKING_SHOW=0/PLAY=2200000000 de
#    get_cur_ms()=0 (GLO khong co timestamp) luon roi vao cua so choi.
#  - MOI endpoint test ok tren --db busidol.db tu post truc tiep; da ROL LAI save HUANDO
#    ve ruby=3968/cloud_piece=5664 (do test da tru + cong). USER tu chay server lai de check.
#  - Mobile_Link/get_cur_run_count.php: tra plain "1" (client parse parseInt).
#    LUU Y: lp la lowercased path -> substring trong dieu kien phai viet thuong.
#  - CON TON: ITEM tab gacha (update_item_to_server MODE=ITEM_GACHA) van chua xu ly
#    "bam mua lan 2 khong duoc, phai ra sanh" — can log lan bam thu 2 tu USER.
# ============================================================
#  === 7) 20260922: ITEM GACHA "khong nhan duoc item" — DA FIX ===
#  CAN NGUYEN: slot do = DATA1 segment[15] upgrade list, gia tri thu 9 (upgrade[9])
#  -> client set DEFINE.USER_ITEM_MAX khi boot. HUANDO dang co 120 items == cap 120
#  -> STORAGE.add_item() het slot, fail im lang -> item roll khong vao STORAGE ->
#  khong co trong ITEM POST -> server (replace semantic) khong bao gio thay -> mat.
#  FIX (server-only):
#  1) Nang upgrade[9] 120->160 trong busidol.db (HUANDO) = cap native USER_STORAGE_MAX:160.
#     Khong can dong min.js; client tu doc upgrade[9] tu DATA1 (STORAGE.load_n_parse_cnm, k=t[15]).
#  2) serve.py update_item_to_server MODE=ITEM_GACHA: parse ETC (gacha_etc) "|" sau la
#     ds item "num:0:OPT-N:0:0"; item nao cu count trong POST ITEM <= count trong OLD save
#     (tuc client khong giu duoc) -> tao MAIL what=ITEM what_value=<item_num> (1 mail/1 item).
#     Mail claim native: client check space_lack truoc khi claim, ADD_ITEM echo tu server
#     -> STORAGE.add_item khi co slot. Vay item khong the mat.
#  TEST: post truc tiep full-save + ETC 2 item la -> 2 mail; claim -> mail het + ADD_ITEM
#  echo; item co trong POST -> khong mail; resources-only -> khong mail. py_compile OK.
#  LUU Y: cap lai day (>= upgrade[9]) -> user phai ban bot do (dung luat game). Mail la
#  "kho chua" an toan, khong load lai cung ton tai (sua trong s["mails"] cung save).
# ============================================================
#  === 8) 20260922: RUBYFARM UPGRADE + CONVERT FULL MATRIX ===
#  serve.py MD5=0912EB4B0DDAA0B682791AACE44600D7 (DANG GHI; khac 3) se thay doi
#  moi lan sua). DA TEST tren port 8032 + save temp, OK.
#  1) CONVERT FULL MATRIX (20 cap, any->any cua vang/ruby/BP/cloud/essence):
#     - Gia tri chuan _CUR_VALUE = {GOLD:1, RUBY:2000, BP:20000, CLOUD:10000, ESSENCE:10000}.
#     - CONVERT_RATES sinh tu bang goc (cost=g[to], gain=g[from] tuc 1BP=20000 vang
#       1ruby=2000 vang 1cloud=1essence=10000 vang) ROI update() 6 cap CU GIU NGUYEN:
#       GOLD->BP 120000=5 | RUBY->BP 500=50 | GOLD->CLOUD 120000=12 | GOLD->ESSENCE
#       100000=10 | BP->RUBY 100=5000 | BP->GOLD 100=2000000. Sinh cung cap CLOUD<->ESSENCE
#       1:1, RUBY<->CLOUD 5:1, BP<->CLOUD 2:1... (xem bay loi). Rat linh hoat.
#     - toolshop/get_balances.php tra them 'rates' = [{from,to,cost,gain}] -> frontend
#       KHONG hardcode nua (convert.html + rubyfarm tab deu ve row tu day).
#  2) RUBYFARM THEM TAB 'QUY DOI' (nav 💱 'Quy doi tai nguyen'): pageConvert() goi
#     get_balances + convert.php, hien 5 balance bang RES_IMG + row doi + estimate.
#  3) GAME MOI '2048' (id=slide): score = o toi dai, award = score//128 cap 30.
#     Di chuyen: phim mui ten + swipe. Board render bang grid 4x4, compress() gop o.
#  4) CAN KINH TE: MINIGAME_CD_SEC 5->3, DAILY_RUBY_CAP 300->500,
#     TICKET_PRICES sudoku 1000->800 (generator giu 2000).
#  5) convert.html: bo RATES hardcode -> doc tu server (loadAll()). Van chay doc lap.
#  TEST da chay: convert RUBY->CLOUD 500 = -500 ruby +100 cloud OK; award slide 512=4r;
#  wallet tra cap 500 + tprices sudu 800. Client JS node --check OK ca 2 trang.
#  LUU Y: user can RESTART serve.py + F5. Doi tiep de sua ti gia: sua _CUR_VALUE hoac
#  CONVERT_RATES.update() dau file.

#  === GACHA ITEM-SELECT loai (type 26/27 Ruby) — DA SUA (20260923) ===
#  - 2 mua gacha trong package store (type_num 26 = 1 luot 1000 ruby, 27 = 10 luot 9000 ruby)
#    ban dau la mua tien that -> da doi sang ruby (client only).
#  - BUG: roll item khong theo 4 o checkbox (clock/sword/shield/wings) — _r2 hardcode
#    Math.random()<0.5?2:4; va grade chay tu 2 (duoi B) trong khi server chan >=B.
#  - FIX trong min.js (block from_gacha type 26/27): _r2 = this.checked_num (1-4 = item type),
#    fallback random 1-4 neu khong tick; _t2 chi roll grade 5/6/7 (B=40%, A=35%, S=25%).
#  - Checkbox chon loai: focus 1=clock(x1xx), 2=sword(2xx), 3=shield(3xx), 4=wings(4xx).
#  - Server serve.py da san chan _item_grade>=5 (B..S) o ITEM_GACHA -> khop voi client.
#  - TY LE roll: 55% item / 15% gold / 10% ruby / 10% BP / 10% cloud (giu nguyen).
#  - TEST IN-GAME: DA OK (user xac nhan 20260923) — chon loai theo checkbox + chi ra B..S.

#  === DAILY DUNGEON "loop loading" — DA FIX (20260923) ===
#  TRIEU CHUNG: bam vao Daily Dungeon -> quay loading mai khong vao.
#  CAN NGUYEN: DayDungeon/{get_cur_day,get_daydungeon_cur_ticket,update_daydungeon_cur_ticket}
#  .php khong co stub -> offline_stub tra "{}". Client JSON.parse("{}") -> OBJECT, roi
#  get_cur_day success_fn goi .split(",") tren object -> tisked -> callback chet, khong bao
#  gio vao duoc (loading treo). FIX: them 3 stub trong serve.py (truoc # fallback), format:
#    - get_cur_day.php  -> "cur_day,cur_week_num,next_day_timestamp" (role txt; next la
#      epoch giay cua nua dem mai, client *1000 roi tru timestamp_start+timestamp_due).
#      cur_day 1..7 = Mon..Sun (khop TXT.daydungeon_day1..7). chu y: client chay "Sunday
#      mission" (drawMission_sunday) khi cur_day==2 (Thu) — chi la cosmetic, khong can sua.
#      cur_week_num = int(now // 7d) (tang dan, client mod 11 chon nhan vat thuong).
#    - get_daydungeon_cur_ticket.php -> plain so = free ticket con lai hom nay.
#    - update_daydungeon_cur_ticket.php -> POST FREE_TICKET_NUM (am = tieu thu, 0 = login),
#      tra plain so = free ticket moi (luu save: dd_free_day YYYYMMDD, dd_free_ticket).
#  Free ticket moi ngay = DAYDUNGEON_FREE_TICKET_DAY=30 (dau serve.py; cost moi muc
#  need_ticket=[0,1,3,7]). Ruby mua them do save_userinfo_after_pay.php xu ly san.
#  TEST: py_compile OK + post truc tiep: get_cur_day "3,2959,1790182800", ticket 30 ->
#  update -3 -> 27 -> -1 -> 26 -> 0 -> 26 (khong am). User can restart serve.py + F5.
#  LUU Y: khong co image/bg/mapDD*_bg(.jpg/_cover.png) -> map nen trong tranh trong/mau den,
#  van choi duoc. Neu can nen dep: tim mapDD<day>_bg.jpg trong capture cua server LIVE.

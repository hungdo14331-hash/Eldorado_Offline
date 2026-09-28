# Fix Guild Shop — `Guild/update_guild_shop.php` (28/09/2026)

Tài liệu riêng cho một đợt sửa lỗi: làm cho Guild Shop mua được item thật bằng vàng guild.
Bản tri thức tổng vẫn nằm ở `tai_lieu__TRI_THUC_DU_AN.md` (mục 9, đợt 28/09/2026).

---

## 1. Triệu chứng

`HUANDO` mở được màn Guild Shop nhưng **không mua được gì**: route `update_guild_shop.php`
chưa có, mọi request rơi vào stub guild chung `{"result":"ok","data":"no_guild"}`.
Trước đợt này Guild Shop là mục duy nhất trong `update_guild_*.php` còn là stub.

## 2. Nguyên nhân gốc — ba lỗi riêng biệt

Ba lỗi dưới đây đều **không hiện ra lúc viết code**, chỉ lộ ra khi chạy test.
Đây là lý do phải test trước khi tin là xong.

### Lỗi 1 — `reward_info` thiếu phần thưởng tiền → popup thiếu card

Bản đầu chỉ append entry cho loại `ITEM` vào `reward_info`; gold/ruby/BP/cloud thì chỉ
cộng vào save, không append:

```python
if r <= 55:
    reward_info.append(_shop_roll_item(slot))
elif r <= 70:
    gold += 1000 + secrets.randbelow(9001)     # <-- không vào reward_info
```

Hậu quả: mua card 10 lượt ra **9 card** thay vì 10, và client **không hiện** phần tiền.

Lý do: `S_POPUP_GACHA_RESULT` vẽ card từ `reward_info.length`
(`o = Math.min(h.length, 10)`), không tự cộng tiền từ đâu khác. Client Guild Shop cũng
**không** gọi `STORAGE.add_item` / `update_item_to_server` trong path này.

Sửa: mỗi lượt rút phải có đúng một entry, không phân biệt loại.

```python
if r <= 55:
    reward_info.append(_shop_roll_item(slot))
elif r <= 70:
    reward_info.append({"type": "GOLD", "value": 1000 + secrets.randbelow(9001)})
elif r <= 80:
    reward_info.append({"type": "RUBY", "value": 10 + secrets.randbelow(91)})
elif r <= 90:
    reward_info.append({"type": "BP", "value": 50 + secrets.randbelow(251)})
else:
    reward_info.append({"type": "CLOUD", "value": 5 + secrets.randbelow(46)})

gold  = sum(x["value"] for x in reward_info if x["type"] == "GOLD")
ruby = sum(x["value"] for x in reward_info if x["type"] == "RUBY")
bp   = sum(x["value"] for x in reward_info if x["type"] == "BP")
cloud = sum(x["value"] for x in reward_info if x["type"] == "CLOUD")
```

### Lỗi 2 — Idempotency nhận nhầm đơn hợp lệ là retry → không thu tiền

Client gửi lại **nguyên body** khi timeout, nên cần chống mua 2 lần. Khoá ban đầu chỉ dùng
`fp = type_num|times|slot|user_goldbar` (`user_goldbar` là số dư **trước** lúc mua).

Nhưng nếu user kiếm lại đúng số vừa trừ rồi mua tiếp (ví dụ nhận thưởng guild khác),
body sẽ **y hệt** → server nhầm là retry → **trả lại kết quả cũ mà không thu tiền**.

Sửa: lưu thêm số dư sau giao dịch, chỉ coi là retry khi số dư hiện tại **bằng đúng** số dư
sau giao dịch cũ. Số dư đã đổi ⇒ đơn mới.

```python
gold_now = _int_or_zero(_member(db, uid)["gold_bar"])
fp = "%d|%d|%d|%d" % (type_num, times, slot, _as_int(data.get("user_goldbar"), 0))
dup = _one(db, "SELECT gold_bar_after, response FROM guild_shop_buy "
               "WHERE user_id=? AND fp=?", (uid, fp))
if dup is not None and _int_or_zero(dup["gold_bar_after"]) == gold_now:
    return 200, dup["response"]     # retry thật -> trả lại kết quả cũ
```

Bảng: `guild_shop_buy(user_id, fp, gold_bar_after, created_at, response)`,
khoá chính `(user_id, fp)`, dọn dòng cũ hơn 24h sau mỗi lần mua.

### Lỗi 3 — Test concurrency viết sai, dễ "vá" nhầm vào code

Test ban đầu đòi *"chỉ 1 response `ok` trong 4 request"*. Nhưng retry đúng nghĩa là **cả 4
request đều phải trả `ok` với payload giống hệt nhau** — chỉ thu tiền một lần. Test sai
khiến ta sửa ngược lại thành bug thật.

Sửa test: đòi 4 response giống hệt, `gold_bar` trừ đúng 1 lần, và bảng chỉ có 1 dòng receipt.

```python
for _, r in out:
    self.assertEqual("ok", r.get("result"), out)
self.assertEqual(1, len({json.dumps(r, sort_keys=True) for _, r in out}), out)
self.assertEqual(50000 - 4000, self.gold_bar())
self.assertEqual(1, len(self.rows(
    "SELECT fp FROM guild_shop_buy WHERE user_id=?", ("g_sh_a",))))
```

## 3. Hai ràng buộc phải đọc bundle mới biết

Hai điểm này **suy đoán từ tên field là ra sai**. Phải đọc code client.

### 3.1 Item phải có tens digit 6, nếu không icon trống

`S_POPUP_GACHA_RESULT.preload` chỉ tải **4 ảnh**:

```
image/ui/40_package_store/co_item16.png
image/ui/40_package_store/co_item26.png
image/ui/40_package_store/co_item36.png
image/ui/40_package_store/co_item46.png
```

nhưng hàm dựng icon lại là:

```js
function et(n){ var t = "co_item" + Math.floor(n/10); ... }
```

Tức `floor(item_num/10)` buộc phải thuộc `{16, 26, 36, 46}` ⇒ **tens digit phải là 6**
(grade A). Nếu roll grade 5 hoặc 7 thì `co_item15/17` không tồn tại ⇒ **icon trống**.

Bản đầu roll grade ngẫu nhiên 5/6/7 như `ITEM_GACHA` → 40% số item ra icon trống.
Sửa: cố định `GUILD_SHOP_GRADE = 6`.

### 3.2 Ghi item 3 chữ số, để client tự random sub-option

`S_MAILBOX.reward_get_in_server`, case `"ITEM"`:

```js
r = window.g.REWARD[t].what_value;
d = String(r).length;
d == 3 ? s = Math.floor(Math.random()*(DEFINE_ITEM_SUB_OPTION.length-1)+1)   // random option 1..7
       : d == 4 && (s = String(r).charAt(3), r = Math.floor(r/10));          // option cố định
// rồi tự roll số theo S_ITEM.num_apply_item_grade_return_num(r)
```

- `what_value` **3 chữ số** → client tự chọn option ngẫu nhiên và tự roll giá trị theo
  grade suy ra từ chính `item_num`.
- `what_value` **4 chữ số** → digit thứ 4 chính là option index, **không random được**.

Bản đầu còn tính sẵn `add_option` / `add_option_num` rồi `pop` khỏi response trước khi trả
client — **code chết hoàn toàn**, vì client tự tính lại. Đã **xoá hẳn** bảng
`GUILD_SHOP_SUB_OPTION` và đoạn `pop`.

> Bài học: đừng suy hành vi client từ tên field. `add_option` nghe như phải server gửi,
> nhưng thật ra client tự random.

## 4. Nơi lưu phần thưởng

| Loại | Nơi lưu | Ghi chú |
|---|---|---|
| Gold | `save["DATA1"][1]` | `USER.gold` |
| Ruby | `save["DATA1"][2]` | |
| BP | `save["bp"]` | |
| Cloud | `save["cloud_piece"]` | |
| Item | `save["mails"]`, `what:"ITEM"`, `what_value` 3 chữ số | `TXT.random_box_tip`: "The item will be delivered to your mailbox." |
| Hero | `save["mails"]`, `what:"CHAR"`, `what_value` = `char_num` | Mailbox case `"CHAR"` gọi `STORAGE.add_char`. Quy ước sẵn có: `serve.py` cũng chỉ cấp hero qua mail, sở hữu = `DATA2` ∪ mail `CHAR` |

`why` dùng English uppercase, khớp quy ước sẵn có trong `serve.py`
(`MOSS & MOON CHARACTER SHOP`, `RUBY GARDEN PURCHASE`, `DAILY ATTENDANCE`).

## 5. Bốn gói có thể mua

Client **hardcode** 4 card trong `S_GUILD_SHOP.CARDS` — không có endpoint nào để server
đổi danh sách, cũng không có endpoint để "liệt kê gói". Server chỉ chọn `type_num` cho
card 1/2 (card 3/4 client đã ghi sẵn 26/27).

| # | Giá (vàng guild) | Lượt | Loại | `type_num` | Ảnh nút | Nội dung |
|---|---|---|---|---|---|---|
| 1 | 4000 | 1 | hero | `1000 + char_num*2` | `guild_shopbt_heroselect` | 1 bản hero được chọn |
| 2 | 40000 | 10 | hero | `1000 + char_num*2 + 1` | `guild_shopbt_heroselectx10` | 10 bản hero được chọn |
| 3 | 4000 | 1 | item | `26` | `guild_shopbt_aitemselect` | 1 lượt rút ngẫu nhiên |
| 4 | 40000 | 10 | item | `27` | `guild_shopbt_aitemselectx10` | 10 lượt rút ngẫu nhiên |

Card 1/2: `char_num` chạy 1..114 (114 hero), nên `type_num` chạy `1002`..`1229`.
Card 3/4 đã dùng `26`/`27` — không đụng vùng `1000+`.

### Vì sao server phải cấp `type_num` cho card hero

`S_GUILD_SHOP.CARDS` để `type_num: 0` cho card hero. Client lấy `type_num` thật từ
`S_GUILD_SHOP.POPUP_HEROES[i].type_num_1` / `.type_num_10`, mà `POPUP_HEROES` dựng từ
`glo.package.get_hero_list()` — tức từ **`hero_list` server gửi ở
`cnm_exist_host_in_server.php`**. Trước đợt này `serve.py` trả `[]` ⇒ popup trống,
người chơi không chọn được hero.

Ràng buộc bắt buộc của `hero_list` (đọc từ `glo.package.parse_hero_list` và
`S_GUILD_SHOP.refresh_popup_heroes`):

| Field | Bắt buộc vì |
|---|---|
| `enable: true` | `parse_hero_list` chỉ nhận entry có `enable === true` |
| `char_num` | khoá gom nhóm; cũng là `profile_icon_<n>.png` + `co_ch<n>.png` |
| `times` | `1` hoặc `10`; thiếu `10` thì client tự suy `type_num_10 = type_num_1 + 1` |
| `num` | chính là `type_num` client gửi lên khi mua |
| `id` | `S_PACKAGE_STORE` đọc khi mở tab hero |

Nhờ quy tắc tự suy, chỉ cần **một entry `times:1` mỗi hero** — không phải bảng 228 dòng.

### Chọn danh sách hero

Dùng lại `MOSS_MOON_CHARACTER_CATALOG` (đã validate đủ `1..114` từ
`Wiki/data/characters.js`). Ràng buộc ảnh khớp tuyệt đối:
`profile_icon_1..114.png` và `co_ch1..114.png` đều tồn tại trong
`ELDORADO_WEB/source_20240722/image/ui/52_profile/` và `.../0_common/`. Thiếu ảnh ⇒ ô trống.

### Xác suất rút (chỉ card 3/4)

Copy từ `ITEM_GACHA` của client: item 55% · gold 15% (`1000..10000`) ·
ruby 10% (`10..100`) · BP 10% (`50..300`) · cloud 10% (`5..50`).
Biến thể item theo `DEFINE_ITEM_UPGRADE.probability_sangjungha` = 60/30/10.
Card hero **không random** — người chơi chọn sẵn hero trong popup.

## 6. An toàn dữ liệu

- Chỉ tin **session UID + membership**; `type_num` là tham số mua lấy từ client.
- Trừ tiền bằng `UPDATE ... WHERE gold_bar>=price` và kiểm `rowcount == 1` ⇒ không bao giờ âm.
- Không có member trong guild ⇒ `gs-not-in-guild`; `type_num` lạ ⇒ `gs-bad-card`;
  `times` sai ⇒ `gs-bad-times`; thiếu tiền ⇒ `not_enough`.
- Với card hero, `type_num` được **giải mã ngược** thành `char_num` + số lượt rồi mới
  tính giá. Client gửi `char_num` trong `type_num` không kiểm soát được ⇒ nhưng công
  thức là **giải mã 1-1**, nên client tự chọn hero nào cũng hợp lệ, không vượt biên
  (`char_num` 114 × 10 ⇒ `type_num` 1229, ngoài đó trả `gs-bad-card`).

## 7. Kiểm tra đã chạy

```
python -m py_compile serve.py guild_backend.py        → OK
python -m unittest TESTS.test_guild_shop_http          → 26 test OK
python -m unittest discover -s TESTS -p "test_*.py"   → 222 test OK (trước đợt: 196)
```

26 test gồm: route có thật, shape response, spoof `price` bị bỏ qua, thiếu tiền,
không phải member, session giả, `char_reward` giữ đúng slot, slot ngoài 1..4 fallback,
item có icon + có `DEFINE_ITEM`, item vào mailbox, retry không trừ 2 lần,
đơn mới sau khi số dư đổi, 4 request đồng thời chỉ trừ 1 lần.

8 test mới cho card hero: `hero_list` có `enable` + `type_num` hợp lệ, đủ 114 icon
(`profile_icon_` + `co_ch`), công thức `type_num_1`/`type_num_10` khớp giá,
card ×1 (1 CHAR, trừ 4000), card ×10 (10 CHAR, trừ 40000), `price` giả bị bỏ qua,
`type_num` ngoài biên bị từ chối, `times` sai bị từ chối, và một test móc vòng trọn
(endpoint → `parse_hero_list` → `refresh_popup_heroes` → 114 hero với `type_num` hợp lệ).


## 8. Smoke test thật (đã thành công)

Người dùng xác nhận *"nó hoạt động rồi"* (~04:23 28/09/2026). Bằng chứng:

- `serve.log` 04:23:24 `POST /ELDORADO_WEB/Guild/update_guild_shop.php` (body 306 byte),
  ngay sau đó client tải `co_item16/26/36/46.png` + `ogong_gacha1..8` + `top_lunar`
  ⇒ `S_POPUP_GACHA_RESULT` mở và **có icon item** (xác nhận mục 3.1 đúng).
- DB `guild_members`: vàng guild của `HUANDO` **200032 → 160032** — trừ đúng 40000.
- DB `guild_shop_buy`: đúng 1 dòng `fp='27|10|4|200032'`, `gold_bar_after=160032`.
- Save `HUANDO`: **7 mail** `why="LUNAR LUCKY PACKAGE"`, `what_value` =
  `461`×3, `462`×3, `463`×1 — đều tens digit 6 (có icon), đều hundreds digit 4 khớp
  `char_reward=4`. 10 lượt còn lại ra tiền, ghi thẳng `DATA1`/`bp`/`cloud_piece`.

## 9. Chưa làm / giới hạn

| Việc | Trạng thái |
|---|---|
| Card hero 1/10 trên trình duyệt | Code + test xong, **chưa smoke test thật** — cần restart rồi mua thử |
| Vòng nhận mailbox (item/hero vào túi) | Logic client đã đọc kỹ, **chưa xác minh bằng mắt** |
| Card 26 (4000) trên trình duyệt | Mới xác nhận card 27 |
| Trần 60 lượt/tháng | Client hiện `get_lunar_lucky_cnt()` = `/60`, server **chưa** đếm/trần ⇒ mua vô hạn |
| Tab hero của Package Store | `hero_list` giờ có 114 phần tử, tab hero ở `S_PACKAGE_STORE` sẽ không còn trống. Thanh toán tiền thật vốn đã không dùng được khi offline — **cần xác nhận với người dùng** nếu thấy tab này xuất hiện |
| Hiển thị `GOLD`/`RUBY` trong popup | Không có nhánh riêng trong `S_POPUP_GACHA_RESULT`, client rơi về nhánh mặc định (icon ruby + số) cho cả hai |
| Tỉ lệ rút 55/15/10/10/10 | Copy từ `ITEM_GACHA` của client, **chưa** đối chiếu game gốc |

## 10. File đã đổi

- `guild_backend.py` — `GUILD_SHOP_CARD`, `GUILD_SHOP_GRADE`, `GUILD_SHOP_HERO_BASE/HERO_PRICE/HERO_MAX`,
  `_shop_hero_type_num`, `_shop_hero_spec`, bảng `guild_shop_buy`, `_shop_mail_sn`,
  `_shop_roll_item`, `_shop_act_purchase`, `_ACT_SHOP`, map group `guild_shop`, cập nhật docstring tổng.
- `serve.py` — route `update_guild_shop.php` vào `guild_dispatch`; `_guild_shop_hero_list()`
  thay cho `hero_list: []` trong response `cnm_exist_host_in_server.php`.
- `TESTS/test_guild_shop_http.py` — file mới, 26 test qua HTTP thật.
- `TAI_LIEU_MARKDOWN/FIX_GUILD_SHOP_20260928.md` — file này.
- `TAI_LIEU_MARKDOWN/tai_lieu__TRI_THUC_DU_AN.md` — bảng trạng thái, mục 8, số test, nhật ký.

> Repo git đặt ở cấp `Desktop` và thư mục dự án **chưa được track**, nên không có
> `git diff` để review và chưa commit gì cho đợt này.


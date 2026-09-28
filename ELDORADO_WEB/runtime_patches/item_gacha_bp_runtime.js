// Item gacha (Package Store / Lunar Lucky, TYPE_NUM 26/27) — DISPLAY ONLY.
//
// The purchase itself lives in `eldorado_all_20260915.min.js`
// (`S_POPUP_PACKAGE_STORE.menuRun_Run`) so it cannot be lost if this file
// fails to load. Do NOT add a second purchase path here: two of them would
// let a silent install failure fall back to the old client-side roll while
// the server still rolls, granting the reward twice.
//
// This file only paints the BP icon and price on gacha cards 1 and 2.
(function (root) {
    "use strict";

    function assetUrl(path) {
        var base = "";
        try {
            if (root.glo && root.glo.fun &&
                    typeof root.glo.fun.get_ser_img_url === "function") {
                base = root.glo.fun.get_ser_img_url("NEW_UI_2025");
            }
        } catch (e) {
            base = "";
        }
        return base + path;
    }

    function paintBpCard(n, typeNum) {
        var card = root.document.getElementById("GC_card_" + n);
        if (!card) return false;

        // The min.js card renderer already prints the price into Txt_bp_<n>.
        // Keep whichever one shows; do not stack two price labels.
        var oldPrice = root.document.getElementById("Txt_bp_" + n) ||
            root.document.getElementById("Txt_3_GC_card_" + n);
        if (oldPrice) oldPrice.style.display = "none";

        var coverId = "Busidol_bp_card_cover_" + n;
        var cover = root.document.getElementById(coverId);
        if (!cover) {
            cover = root.document.createElement("div");
            cover.id = coverId;
            card.appendChild(cover);
        }
        cover.style.cssText = "position:absolute;left:68px;top:334px;" +
            "width:84px;height:54px;z-index:4;pointer-events:none;" +
            "background:#9b501e;";

        var iconId = "Busidol_bp_card_icon_" + n;
        var icon = root.document.getElementById(iconId);
        if (!icon) {
            icon = root.document.createElement("img");
            icon.id = iconId;
            card.appendChild(icon);
        }
        icon.src = assetUrl("image/ui/40_package_store/co_bp.png");
        icon.alt = "BP";
        icon.style.cssText = "position:absolute;left:78px;top:340px;" +
            "height:42px;width:auto;z-index:6;pointer-events:none;";

        var priceId = "Busidol_bp_card_price_" + n;
        var price = root.document.getElementById(priceId);
        if (!price) {
            price = root.document.createElement("div");
            price.id = priceId;
            card.appendChild(price);
        }
        var amount = typeNum === 26 ? 1000 : 10000;
        var formatted = typeof root.utilGetNumber_withComma === "function" ?
            root.utilGetNumber_withComma(String(amount)) : String(amount);
        price.textContent = formatted + " BP";
        price.style.cssText = "position:absolute;left:0;top:337px;" +
            "width:289px;height:53px;z-index:5;pointer-events:none;" +
            "display:flex;align-items:center;justify-content:center;" +
            "box-sizing:border-box;padding-left:46px;color:#ffffff;" +
            "line-height:53px;font-size:23rem;text-align:center;" +
            "text-shadow:1px 1px 1px #000;";
        return true;
    }

    function paintBpCards() {
        var gacha = root.S_GACHA;
        if (!gacha || !gacha.data) return false;
        var painted = false;
        for (var n = 1; n <= 2; n++) {
            var data = gacha.data[n];
            var typeNum = Number(data && data.type_num);
            if ((typeNum === 26 || typeNum === 27) &&
                    paintBpCard(n, typeNum)) {
                painted = true;
            }
        }
        return painted;
    }

    function installCardDisplay() {
        var gacha = root.S_GACHA;
        if (!gacha || typeof gacha.make_screen_bottom_item !== "function") {
            return false;
        }
        if (!gacha.make_screen_bottom_item.__busidolBpCards) {
            var original = gacha.make_screen_bottom_item;
            var wrapped = function () {
                var result = original.apply(this, arguments);
                root.setTimeout(paintBpCards, 0);
                return result;
            };
            wrapped.__busidolBpCards = true;
            gacha.make_screen_bottom_item = wrapped;
        }
        return paintBpCards();
    }

    if (!installCardDisplay()) {
        var attempts = 0;
        var retry = function () {
            if (installCardDisplay() || ++attempts >= 20) return;
            root.setTimeout(retry, 100);
        };
        root.setTimeout(retry, 0);
    }
}(window));

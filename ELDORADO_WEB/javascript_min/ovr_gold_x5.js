(function () {
  if (typeof CAL === "undefined" || typeof CAL.get_wingold !== "function") return;
  var _og = CAL.get_wingold;
  CAL.get_wingold = function (n) {
    var v = _og.call(CAL, n);
    return typeof v === "number" ? Math.floor(v * 5) : v;
  };
  if (typeof CAL.get_wingold_npc === "function") {
    var _on = CAL.get_wingold_npc;
    CAL.get_wingold_npc = function () {
      var v = _on.call(CAL);
      return typeof v === "number" ? Math.floor(v * 5) : v;
    };
  }
})();
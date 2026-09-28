(function () {
  // RubyFarm bridge: lets a standalone mini-game report a finished run to the
  // RubyFarm page that embeds it in an <iframe>. When the game is opened
  // directly (not embedded) this does nothing, so it stays a normal game.
  // Usage: window.rfAward('game_id', scoreNumber)
  function rfAward(game, score) {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ rubyfarm: "award", game: game, score: Number(score) || 0 }, "*");
      }
    } catch (e) { /* ignore */ }
  }
  window.rfAward = rfAward;

  // Server call from inside the iframe (same-origin). Post key=value form body.
  // Returns the parsed JSON; on a network failure returns {STATE:"NETERR"}.
  function rfApi(path, data) {
    const b = new URLSearchParams();
    for (const k in (data || {})) b.append(k, data[k]);
    return fetch(path, { method: "POST", body: b.toString() })
      .then(function (r) { return r.json(); })
      .catch(function () { return { STATE: "NETERR" }; });
  }
  window.rfApi = rfApi;

  // Ask the RubyFarm page to refresh wallet HUD (fee paid / prize claimed).
  function rfRefresh() {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ rubyfarm: "refresh" }, "*");
      }
    } catch (e) { /* ignore */ }
  }
  window.rfRefresh = rfRefresh;
})();
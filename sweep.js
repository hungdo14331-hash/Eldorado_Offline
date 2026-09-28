const CDP_PORT = process.env.CDP_PORT || 9223;
const TARGET_URL = process.env.SHOT_URL;

async function getWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json`);
      const list = await r.json();
      const t = list.find((x) => x.type === "page" && x.url && x.url !== "about:blank") || list.find((x) => x.type === "page");
      if (t && t.webSocketDebuggerUrl) return t.webSocketDebuggerUrl;
    } catch (e) {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("no target");
}

(async () => {
  const ws = new WebSocket(await getWsUrl());
  let id = 0;
  const pending = new Map();
  const send = (m, pa) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { res, rej });
      ws.send(JSON.stringify({ id: mid, method: m, params: pa || {} }));
    });
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  const errors = [];
  let excBase = 0;
  let paused = false;
  ws.onmessage = async (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const q = pending.get(m.id);
      pending.delete(m.id);
      m.error ? q.rej(Error(JSON.stringify(m.error))) : q.res(m.result);
      return;
    }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params && m.params.exceptionDetails;
      if (d) {
        const st = d.stackTrace && d.stackTrace.callFrames && d.stackTrace.callFrames[0];
        errors.push({
          text: (d.exception && d.exception.description || d.text || "").split("\n")[0].slice(0, 200),
          fn: st ? st.functionName : "-",
          line: st ? st.lineNumber + 1 : -1,
        });
      }
    }
    if (m.method === "Debugger.paused") {
      paused = true;
      const f = m.params.callFrames && m.params.callFrames[0];
      console.log("PAUSED(uncaught) " + (f ? f.functionName + "@" + f.location.lineNumber : "?"));
      try {
        await send("Debugger.evaluateOnCallFrame", {
          callFrameId: m.params.callFrames[0].callFrameId,
          expression: `({n: String(typeof n!=='undefined'?n:'n/a').slice(0,200), scene: (typeof g_sceneinfo!=='undefined')?g_sceneinfo.cur_scene:'?', s1: String((typeof arguments!=='undefined'&&arguments[1])!=='undefined'?arguments[1]:'').slice(0,200)})`,
          returnByValue: true,
        }).then((r) => console.log("  ctx => " + JSON.stringify(r && r.result && r.result.value)));
      } catch (e) {}
      await send("Debugger.resume");
      paused = false;
    }
  };
  const RECORDER = `(()=>{
    window.__reqs = [];
    const O = XMLHttpRequest.prototype.open, S = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(m, u, a){ this.__u = u; return O.apply(this, arguments); };
    XMLHttpRequest.prototype.send = function(b){
      const self = this;
      this.addEventListener("load", function(){
        try{ window.__reqs.push({ u: self.__u, s: self.status, r: String(self.responseText||"").slice(0,200) }); if (window.__reqs.length > 200) window.__reqs.shift(); }catch(e){}
      });
      return S.apply(this, arguments);
    };
  })();`;
  await send("Runtime.enable");
  await send("Debugger.enable");
  await send("Debugger.setPauseOnExceptions", { state: "uncaught" });
  await send("Page.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", { source: RECORDER });
  const U = new URL(TARGET_URL);
  U.searchParams.set("v", String(Date.now()));
  await send("Page.navigate", { url: U.toString() });

  const evalExpr = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
    if (r.exceptionDetails) return { e: (r.exceptionDetails.exception && r.exceptionDetails.exception.description || "eval-err").slice(0, 140) };
    return { v: r.result && r.result.value };
  };
  const key = async (code) => {
    await send("Input.dispatchKeyEvent", { type: "rawKeyDown", windowsVirtualKeyCode: code, nativeVirtualKeyCode: code });
    await send("Input.dispatchKeyEvent", { type: "keyUp", windowsVirtualKeyCode: code, nativeVirtualKeyCode: code });
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const scene = async () => {
    const s = await evalExpr(`(function(){try{return g_sceneinfo&&g_sceneinfo.cur_scene||''}catch(e){return 'ERR:'+e.message}})()`);
    return s.e || String(s.v);
  };

  const T0 = Date.now();
  const tS = () => `[t+${((Date.now() - T0) / 1000).toFixed(1)}s]`;

  // 1) boot -> main menu (auto-skip language/synopsis)
  let lastScene = "";
  let lastBump = 0;
  let mainSeen = 0;
  while (Date.now() - T0 < 90000) {
    const sc = await scene();
    if (sc !== lastScene) { console.log(`${tS()} scene -> ${sc}`); lastScene = sc; }
    if (sc === "S_LANG_SELECT" || sc === "S_SYNOPSIS" || sc === "S_LANGUAGE" || sc === "S_ATTENDANCE" || sc === "S_EVENT" || sc === "S_EVENT_LIST") {
      if (Date.now() - lastBump > 900) { await key(13); lastBump = Date.now(); }
    }
    if (sc === "S_MAINMENU") { mainSeen++; if (mainSeen > 3 && Date.now() - T0 > 6000) break; }
    await sleep(300);
  }
  if (!mainSeen) { console.log("NOT-AT-MAINMENU last=" + lastScene); }
  else console.log(`${tS()} @ main menu`);

  // 2) sweep every _BTN_NUM entry
  const btns = await evalExpr(`(function(){
    var out = []; var seen = {};
    for (var k in S_MAINMENU) if (/_BTN_NUM$/.test(k) && typeof S_MAINMENU[k]==="number") {
      var v = S_MAINMENU[k];
      if (seen[v]) continue; seen[v] = 1;
      out.push({ name: k, val: v });
    }
    return out; })()`);
  for (const b of (btns.v || [])) {
    const excBefore = errors.length;
    const reqsBefore = await evalExpr(`(window.__reqs?window.__reqs.length:0)`);
    await evalExpr(`(function(){try{S_MAINMENU.focus=${b.val}; S_MAINMENU.menuRun_Run(); return "ok";}catch(e){return "tryerr:"+e.message}})()`);
    await sleep(1800);
    const sc = await scene();
    const reqs = await evalExpr(`(function(){var a=window.__reqs.slice(${parseInt(reqsBefore.v||0,10)}); return a.map(function(q){return q.u;});})()`);
    console.log(`BTN ${b.name}=${b.val} -> scene=${sc} xhr=${(reqs.v||[]).join(" | ")} exc=${errors.length - excBefore}`);
    // back out
    let back = 0;
    while ((await scene()) !== "S_MAINMENU" && back < 4) { await key(8); await sleep(700); back++; }
    if ((await scene()) !== "S_MAINMENU") console.log(`  !! stuck after back (scene=${await scene()})`);
  }

  // 3) START -> S_MODE_SELECT, then try entering story stage -> team -> battle
  let deep = [];
  await evalExpr(`(function(){try{S_MAINMENU.focus=S_MAINMENU.START_BTN_NUM; S_MAINMENU.menuRun_Run(); return "ok";}catch(e){return "err:"+e.message}})()`);
  await sleep(1500);
  deep.push(await scene());
  const modeScene = await scene();
  if (modeScene === "S_MODE_SELECT") {
    await key(13); await sleep(2000); deep.push(await scene());
    const s2 = await scene();
    if (/S_STAGE/.test(s2)) {
      await key(13); await sleep(2500); deep.push(await scene());
      const s3 = await scene();
      if (/TEAM/.test(s3) || /S_MODE/.test(s3)) { await key(13); await sleep(3500); deep.push(await scene()); }
      const s4 = await scene();
      if (/GAME|BATTLE/.test(s4)) {
        await sleep(8000); deep.push(await scene());
        const g = await evalExpr(`(function(){try{return {scene:g_sceneinfo.cur_scene, gKey:gEnableKey, our:(typeof OUR_TEAM_ARRAY!=='undefined')?OUR_TEAM_ARRAY.length:'-', st:(typeof S_GAME!=='undefined')?S_GAME.scene_status:'-'}}catch(e){return {err:e.message}}})()`);
        console.log(`${tS()} BATTLE state => ` + JSON.stringify(g));
        await key(13); await sleep(500); // end-turn / win handling
        await sleep(6000);
        deep.push(await scene());
      }
    }
  }
  console.log("DEEP scene path: " + deep.join(" -> "));

  await send("Debugger.setPauseOnExceptions", { state: "none" });
  // 4) dump all xhr endpoint samples
  const reqs = await evalExpr(`JSON.stringify(window.__reqs||[])`);
  const seen = new Map();
  if (reqs.v) for (const q of JSON.parse(reqs.v)) {
    const base = q.u.replace(/\?.*/, "");
    if (!seen.has(base)) seen.set(base, { s: q.s, r: q.r });
  }
  console.log("=== ENDPOINTS (" + seen.size + ") ===");
  for (const [u, info] of seen) console.log(JSON.stringify({ u, s: info.s, r: info.r.slice(0, 160) }));
  console.log("=== JS EXCEPTIONS (" + errors.length + ") ===");
  for (const e of errors) console.log(JSON.stringify(e));
  ws.close();
  process.exit(0);
})().catch((e) => { console.error("ERR " + e.message); process.exit(1); });
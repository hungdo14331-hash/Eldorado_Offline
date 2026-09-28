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
  const send = (m, pa) => new Promise((res, rej) => {
    const mid = ++id; pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method: m, params: pa || {} }));
  });
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  const errors = [];
  ws.onmessage = async (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const q = pending.get(m.id); pending.delete(m.id);
      m.error ? q.rej(Error(JSON.stringify(m.error))) : q.res(m.result);
      return;
    }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params && m.params.exceptionDetails;
      if (d) {
        const st = d.stackTrace && d.stackTrace.callFrames && d.stackTrace.callFrames[0];
        errors.push({
          text: (d.exception && d.exception.description || d.text || "").split("\n")[0].slice(0, 200),
          fn: st ? st.functionName : "-", line: st ? st.lineNumber + 1 : -1,
        });
      }
    }
    if (m.method === "Debugger.paused") {
      const f = m.params.callFrames && m.params.callFrames[0];
      console.log("PAUSED(uncaught) " + (f ? f.functionName + "@" + f.location.lineNumber : "?"));
      try {
        await send("Debugger.evaluateOnCallFrame", {
          callFrameId: m.params.callFrames[0].callFrameId,
          expression: `({n: String(typeof n!=='undefined'?n:'n/a').slice(0,200), scene:(typeof g_sceneinfo!=='undefined')?g_sceneinfo.cur_scene:'?'})`,
          returnByValue: true,
        }).then((r) => console.log("  ctx => " + JSON.stringify(r && r.result && r.result.value)));
      } catch (e) {}
      await send("Debugger.resume");
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
  const path = [];
  const logScene = async (tag) => {
    const sc = await scene();
    path.push(tag + "=" + sc);
    console.log(`${tS()} ${tag} -> ${sc}`);
    return sc;
  };

  // boot to main menu
  let lastScene = "", lastBump = 0, mainSeen = 0;
  while (Date.now() - T0 < 90000) {
    const sc = await scene();
    if (sc !== lastScene) { console.log(`${tS()} scene -> ${sc}`); lastScene = sc; }
    if (["S_LANG_SELECT", "S_SYNOPSIS", "S_ATTENDANCE", "S_EVENT", "S_EVENT_LIST"].includes(sc) && Date.now() - lastBump > 900) { await key(13); lastBump = Date.now(); }
    if (sc === "S_MAINMENU") { mainSeen++; if (mainSeen > 3 && Date.now() - T0 > 6000) break; }
    await sleep(300);
  }
  await evalExpr(`(function(){S_MAINMENU.focus=S_MAINMENU.START_BTN_NUM; S_MAINMENU.menuRun_Run(); return "ok"})()`);
  await sleep(1500);
  let sc = await logScene("start");

  // S_MODE_SELECT -> enter story
  if (sc === "S_MODE_SELECT") {
    await key(13); await sleep(2000); sc = await logScene("modeEnter");
  }
  // S_SELECTMAP -> enter
  if (sc === "S_SELECTMAP") {
    await key(13); await sleep(2500); sc = await logScene("mapEnter");
  }
  // generic deeper navigation: up a few times then enter repeatedly if still in selects
  for (let i = 0; i < 6; i++) {
    sc = await scene();
    if (/S_GAME|S_RESULT|S_STAGE_RESULT/.test(sc)) break;
    if (sc === "S_MAINMENU") break;
    await key(13);
    await sleep(2500);
    const n = await logScene("push" + i);
    if (n === sc) break;
  }
  sc = await scene();
  if (/S_GAME/.test(sc)) {
    const g = await evalExpr(`(function(){try{return {scene:g_sceneinfo.cur_scene, gKey:gEnableKey, st:S_GAME.scene_status, our:(typeof OUR_TEAM_ARRAY!=='undefined')?OUR_TEAM_ARRAY.length:'-', your:(typeof YOUR_TEAM_ARRAY!=='undefined')?YOUR_TEAM_ARRAY.length:'-'}}catch(e){return {err:e.message}}})()`);
    console.log(`${tS()} BATTLE => ` + JSON.stringify(g));
    // let some combat frames run, watch for exceptions
    for (let i = 0; i < 6; i++) { await sleep(3000); await logScene("battleF" + i); }
    // try victory via V key a few times
    await key(86); await sleep(3500);
    await logScene("afterV");
    // try leaving via backspace
    await key(8); await sleep(1200);
    await logScene("afterEsc");
  } else if (sc === "S_RESULT" || /RESULT/.test(sc)) {
    await key(13); await sleep(3000);
    await logScene("resultContinue");
  }
  await send("Debugger.setPauseOnExceptions", { state: "none" });
  // dump endpoints
  const reqs = await evalExpr(`JSON.stringify(window.__reqs||[])`);
  const seen = new Map();
  if (reqs.v) for (const q of JSON.parse(reqs.v)) {
    const base = q.u.replace(/\?.*/, "");
    if (!seen.has(base)) seen.set(base, { s: q.s, r: q.r });
  }
  console.log("=== PATH ===");
  console.log(path.join(" -> "));
  console.log("=== ENDPOINTS (" + seen.size + ") ===");
  for (const [u, info] of seen) console.log(JSON.stringify({ u, s: info.s, r: info.r.slice(0, 160) }));
  console.log("=== JS EXCEPTIONS (" + errors.length + ") ===");
  for (const e of errors) console.log(JSON.stringify(e));
  ws.close();
  process.exit(0);
})().catch((e) => { console.error("ERR " + e.message); process.exit(1); });
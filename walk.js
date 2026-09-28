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
  let errors = [];
  let scenes = [];
  let keyDelay = 900;
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
          text: (d.exception && d.exception.description || d.text || "").split("\n")[0].slice(0, 160),
          col: st ? (st.columnNumber + 1) : -1,
          line: st ? (st.lineNumber + 1) : -1,
          fn: st ? st.functionName : "-",
        });
      }
    }
    if (m.method === "Debugger.paused") {
      const d = m.params;
      console.log("=== PAUSED: " + d.reason);
      for (const f of d.callFrames.slice(0, 3)) {
        console.log("  frame: " + f.functionName + " (" + f.url.split("/").pop() + ":" + f.location.lineNumber + ":" + f.location.columnNumber + ")");
      }
      const frame = d.callFrames[0];
      try {
        const r = await send("Debugger.evaluateOnCallFrame", {
          callFrameId: frame.callFrameId,
          expression: `({t_n: typeof n, s_n: String(n).slice(0,140), j_n: (function(){try{return JSON.stringify(n)}catch(e){return 'n/a'}})(), cur: (typeof g_sceneinfo!=='undefined'&&g_sceneinfo.cur_scene)||'?', before: (typeof g_sceneinfo!=='undefined'&&g_sceneinfo.before_scene)||'?', gKey: typeof gEnableKey!=='undefined'?gEnableKey:'?', retry: (typeof ServerConnection!=='undefined')?ServerConnection.RETRY_count:'?', geiType: (typeof ServerConnection!=='undefined'&&ServerConnection.gei_event_type!==undefined)?ServerConnection.gei_event_type:'?'})`,
          returnByValue: true,
        });
        console.log("  n => " + JSON.stringify(r.result ? r.result.value : r));
      } catch (e) {
        console.log("  eval n => ERR " + e.message);
      }
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
        try{
          window.__reqs.push({ u: self.__u, s: self.status, r: String(self.responseText||"").slice(0,220) });
          if (window.__reqs.length > 60) window.__reqs.shift();
        }catch(e){}
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
    if (r.exceptionDetails) return { e: (r.exceptionDetails.exception && r.exceptionDetails.exception.description || "eval-err").slice(0, 120) };
    return { v: r.result && r.result.value };
  };
  const pressEnter = async () => {
    await send("Input.dispatchKeyEvent", { type: "rawKeyDown", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
    await send("Input.dispatchKeyEvent", { type: "keyUp", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  };
  const pressBackspace = async () => {
    await send("Input.dispatchKeyEvent", { type: "rawKeyDown", windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
    await send("Input.dispatchKeyEvent", { type: "keyUp", windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
  };

  let lastScene = "";
  let lastmm = 0;
  const T0 = Date.now();
  const bump = async (scene) => {
    if (scene === "S_LANG_SELECT" || scene === "S_SYNOPSIS" || scene === "S_LANGUAGE" || scene === "S_ATTENDANCE" || scene === "S_EVENT" || scene === "S_EVENT_LIST") {
      if (Date.now() - lastmm > keyDelay) { await pressEnter(); lastmm = Date.now(); }
    }
  };
  let gachaDone = true;
  let gachaDraw = false;
  let playDone = false;
  let exitLogged = false;
  while (Date.now() - T0 < 100000) {
    const s = await evalExpr(`(function(){try{return g_sceneinfo&&g_sceneinfo.cur_scene||''}catch(e){return 'ERR:'+e.message}})()`);
    const scene = s.e || String(s.v);
    if (scene !== lastScene) {
      console.log(`[t+${(Date.now() - T0) / 1000}s] scene -> ${scene}`);
      scenes.push(scene);
      lastScene = scene;
    }
    await bump(scene);
    if (scene === "S_MAINMENU" && !playDone && Date.now() - T0 > 6000) {
      playDone = true;
      const g = await evalExpr(`(function(){try{var k=S_MAINMENU.START_BTN_NUM; S_MAINMENU.focus=k; S_MAINMENU.menuRun_Run(); return {startNum:k, now:g_sceneinfo.cur_scene};}catch(e){return {err:e.message}}})()`);
      console.log(`>>> PLAY click @t+${(Date.now() - T0) / 1000}s => ` + JSON.stringify(g));
    }
    if (scene === "S_GACHA" && !gachaDraw && Date.now() - lastmm > 2000) {
      gachaDraw = true;
      lastmm = Date.now();
      const g = await evalExpr(`(function(){try{var rb=USER&&USER.ruby; var foc=S_GACHA.focus; S_GACHA.focus=1; S_GACHA.tab_focus=1; S_GACHA.menuRun_Run(); return {ruby:rb, focus:foc, tryFocus:1, now:g_sceneinfo.cur_scene};}catch(e){return {err:e.message, now:g_sceneinfo.cur_scene}}})()`);
      console.log(`>>> DRAW#1 @t+${(Date.now() - T0) / 1000}s => ` + JSON.stringify(g));
    }
    if (scene === "S_POPUPYN" && Date.now() - lastmm > 700) {
      lastmm = Date.now();
      await pressEnter();
      console.log(`>>> POPUP Yes @t+${(Date.now() - T0) / 1000}s`);
    }
    if (scene === "S_EXITPOPUP" && !exitLogged) {
      exitLogged = true;
      const g = await evalExpr(`(function(){try{return {type:S_EXITPOPUP.type, focus:S_EXITPOPUP.focus, gKey:gEnableKey};}catch(e){return {err:e.message}}})()`);
      console.log(`>>> S_EXITPOPUP (no action) => ` + JSON.stringify(g));
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  await send("Debugger.setPauseOnExceptions", { state: "none" });

  const fin = await evalExpr(`(function(){
    var o = { scene: (g_sceneinfo&&g_sceneinfo.cur_scene)||'', flagcount: (typeof S_LOGO!=='undefined')?S_LOGO.flag_count:'-',
      attFolder: (typeof S_ATTENDANCE_EVENT!=='undefined')?S_ATTENDANCE_EVENT.folder_name:'-',
      autoPlugin: (typeof glo!=='undefined'&&glo.APP_FEATURE)?glo.APP_FEATURE.PACKAGE_STORE:'-',
      gEnableKey: typeof gEnableKey!=='undefined'?gEnableKey:'-',
      ruby: (typeof STORAGE!=='undefined'&&STORAGE.data1)?STORAGE.data1.ruby:'-',
      gold: (typeof STORAGE!=='undefined'&&STORAGE.data1)?STORAGE.data1.gold:'-',
      level: (typeof STORAGE!=='undefined'&&STORAGE.data1)?STORAGE.data1.level:'-',
      userName: (typeof gEntrix!=='undefined')?gEntrix.user_name:'-' };
    return o; })()`);
  console.log("=== FINAL state ===");
  console.log(JSON.stringify(fin, null, 1));
  console.log("=== SCENE HISTORY ===");
  console.log(scenes.join(" -> "));
  const reqs = await evalExpr(`JSON.stringify(window.__reqs||[])`);
  console.log("=== XHR LOG (" + (reqs.v ? JSON.parse(reqs.v).length : "?") + ") ===");
  if (reqs.v) for (const q of JSON.parse(reqs.v)) console.log(JSON.stringify(q));
  console.log("=== JS EXCEPTIONS (" + errors.length + ") ===");
  for (const e of errors) console.log(JSON.stringify(e));
  ws.close();
  process.exit(0);
})().catch((e) => { console.error("ERR " + e.message); process.exit(1); });
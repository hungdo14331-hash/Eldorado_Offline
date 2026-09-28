const CDP_PORT = process.env.CDP_PORT || 9223;
const URL = process.env.SHOT_URL;

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
  ws.onmessage = async (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const q = pending.get(m.id);
      pending.delete(m.id);
      m.error ? q.rej(Error(JSON.stringify(m.error))) : q.res(m.result);
      return;
    }
    if (m.method === "Debugger.paused") {
      const d = m.params;
      console.log("=== PAUSED on: " + d.reason);
      for (const f of d.callFrames.slice(0, 4)) {
        console.log("  frame: " + f.functionName + " (" + f.url.split("/").pop() + ":" + f.location.lineNumber + ":" + f.location.columnNumber + ")");
      }
      const frame = d.callFrames[0];
      try {
        const r = await send("Debugger.evaluateOnCallFrame", {
          callFrameId: frame.callFrameId,
          expression: `({t_n: typeof n, s_n: String(n).slice(0,120), j_n: (function(){try{return JSON.stringify(n)}catch(e){return 'n/a'}})()})`,
          returnByValue: true,
        });
        console.log("  n => " + JSON.stringify(r.result ? r.result.value : r));
      } catch (e) {
        console.log("  eval n => ERR " + e.message);
      }
      await send("Debugger.resume");
    }
  };
  await send("Debugger.enable");
  await send("Debugger.setPauseOnExceptions", { state: "uncaught" });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url: URL });
  await new Promise((r) => setTimeout(r, 20000));
  await send("Debugger.setPauseOnExceptions", { state: "none" });
  ws.close();
  process.exit(0);
})().catch((e) => { console.error("ERR " + e.message); process.exit(1); });
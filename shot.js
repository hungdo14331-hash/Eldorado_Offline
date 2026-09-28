const CDP_PORT = process.env.CDP_PORT || 9223;
const WAIT_MS = parseInt(process.env.WAIT_MS || "15000", 10);
const OUT = process.env.OUT || "shot.png";
const URL = process.env.SHOT_URL;
const fs = require("fs");

async function getWsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${CDP_PORT}/json`);
      const list = await r.json();
      const page = list.find((t) => t.type === "page" && t.url && t.url !== "about:blank");
      const target = page || list.find((t) => t.type === "page");
      if (target && target.webSocketDebuggerUrl) return target.webSocketDebuggerUrl;
    } catch (e) {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error("no CDP target");
}

(async () => {
  const wsUrl = await getWsUrl();
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params) =>
    new Promise((resolve, reject) => {
      const mid = ++id;
      pending.set(mid, { resolve, reject });
      ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
    });
  await new Promise((res, rej) => {
    ws.onopen = res;
    ws.onerror = rej;
  });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id);
      pending.delete(m.id);
      if (m.error) p.reject(new Error(JSON.stringify(m.error)));
      else p.resolve(m.result);
    }
  };
  await send("Page.enable");
  if (URL) {
    await send("Page.navigate", { url: URL });
  }
  await new Promise((r) => setTimeout(r, WAIT_MS));
  const res = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(OUT, Buffer.from(res.data, "base64"));
  console.log("saved " + OUT + " (" + fs.statSync(OUT).size + " bytes)");
  ws.close();
  process.exit(0);
})().catch((e) => {
  console.error("ERR " + e.message);
  process.exit(1);
});

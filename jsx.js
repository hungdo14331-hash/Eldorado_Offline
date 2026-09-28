const expr = process.env.JSX;
(async () => {
  try {
    const port = process.env.CDP_PORT;
    const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
    const t = list.find((x) => x.type === "page");
    if (!t) throw new Error("no page target");
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === 1) {
        const rv = m.result && m.result.result;
        const val = rv && rv.value !== undefined ? rv.value : rv;
        console.log(typeof val === "string" ? val : JSON.stringify(val, null, 1));
        process.exit(0);
      }
    };
    ws.send(JSON.stringify({
      id: 1, method: "Runtime.evaluate",
      params: { expression: expr, returnByValue: true, awaitPromise: true },
    }));
  } catch (e) {
    console.log("ERR " + e.message);
    process.exit(1);
  }
})();
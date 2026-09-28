// AUTOCAPTURE - tu dong lay #sign/#time cua game (khong can DevTools)
// Yeu cau: chrome da chay voi --remote-debugging-port=9222, dang login duoc tren game.busidol.com
const PROMISE = 'http://127.0.0.1:9222';
const NEEDLE = 'index__mobile';
const LOCAL_BASE = 'http://localhost:8023/ELDORADO_WEB/source_20240722/index__mobile.html';

function log(m){ process.stdout.write('[' + new Date().toISOString().slice(11,19) + '] ' + m + '\n'); }

async function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

async function getTargets(){
  const r = await fetch(PROMISE + '/json');
  return await r.json();
}

function findGameTarget(targets){
  return targets.find(t => t.type === 'page' && t.url && t.url.indexOf('game.busidol.com') >= 0);
}

function getFrameUrl(tree){
  function walk(n){
    if (n.frame && n.frame.url && n.frame.url.indexOf(NEEDLE) >= 0) return n.frame.url;
    if (n.childFrames) for (const c of n.childFrames){ const u = walk(c); if (u) return u; }
    return null;
  }
  return walk(tree);
}

async function wsEval(wsUrl, method, params){
  return new Promise((resolve, reject) => {
    let ws;
    try { ws = new WebSocket(wsUrl); } catch(e){ return reject(e); }
    const timer = setTimeout(() => { try{ws.close()}catch(_){} reject(new Error('ws timeout ' + method)); }, 15000);
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method, params: params || {} }));
    ws.onerror = (e) => { clearTimeout(timer); reject(new Error('ws error ' + method)); };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === 1){ clearTimeout(timer); try{ws.close()}catch(_){} resolve(m); }
    };
  });
}

async function openTab(url){
  const enc = encodeURIComponent(url);
  const r = await fetch(PROMISE + '/json/new?' + enc, { method: 'PUT' });
  const t = await r.json();
  return t;
}

async function main(){
  log('Cho Chrome dau cuoi (port 9222)...');
  let up = false;
  for (let i=0;i<120;i++){
    try { await fetch(PROMISE + '/json/version', { signal: AbortSignal.timeout(1500) }); up = true; break; }
    catch(e){ await sleep(1000); }
  }
  if (!up){ log('LOI: khong ket noi duoc Chrome tai 9222.'); process.exit(1); }
  log('Da ket noi Chrome. Gio vui long DANG NHAP GOOGLE tren cua so Chrome vua mo, cho den khi thay logo game.');

  let wsUrl = null;
  let foundHash = null;
  for (let i=0;i<900;i++){
    let targets = [];
    try { targets = await getTargets(); } catch(e){ await sleep(1000); continue; }
    const gt = findGameTarget(targets);
    if (!gt){ await sleep(1000); continue; }
    wsUrl = gt.webSocketDebuggerUrl;
    const res = await wsEval(wsUrl, 'Page.getFrameTree').catch(() => null);
    if (res && res.result && res.result.frameTree){
      const upper = findGameTarget(targets) ? res.result.frameTree : null;
      const url = getFrameUrl(res.result.frameTree);
      if (url){
        const s = url.split(NEEDLE + '.html')[1] || '';
        if (s.indexOf('sign=') >= 0){
          foundHash = s;
          break;
        }
      }
    }
    await sleep(1000);
  }

  if (!foundHash){
    log('LOI: khong thay frame game sau 15 phut. Kiem tra da dang nhap Google chua?');
    process.exit(1);
  }

  const mSign = foundHash.match(/#sign=([^#]+)/);
  const mTime = foundHash.match(/#time=([^#]+)/);
  const sign = mSign ? mSign[1].trim() : null;
  const time = mTime ? mTime[1].trim() : null;
  if (!sign || !time){ log('LOI: hash khong hop le: ' + foundHash); process.exit(1); }

  log('Tim thay sign len=' + sign.length + ', time=' + time);
  const local = LOCAL_BASE + '#sign=' + sign + '#time=' + time;
  const tab = await openTab(local).catch(e => { log('LOI mo tab local: ' + e.message); process.exit(1); });
  log('Da mo tab capture. GIO CHOI 1-2 PHUT o tab moi (data se ghi vao thu muc capture/ cua server).');
  log('Choi xong: dong cua so server minimised (hoac bam phim bat ky de dong lap tuc va dung).');
  await sleep(2000);
}

main();
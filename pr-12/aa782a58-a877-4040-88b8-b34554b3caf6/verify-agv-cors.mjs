import { appendFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const OUT = 'C:/Users/tianj/AppData/Local/Temp/opencode/verify-out.txt';
const say = (...a) => { const line = a.join(' '); console.log(line); try { appendFileSync(OUT, line + '\n'); } catch {} };
const fail = (e) => { say('ERROR:', e && e.stack || e); try { appendFileSync(OUT, 'ERROR: ' + (e && e.stack || e) + '\n'); } catch {} process.exit(1); };

process.env.AGV_API_PORT = '18901';

try {
  await import(pathToFileURL('C:/Users/tianj/.codeden/wt/rjvn/aa782a58/smt-factory-system/services/api/agv-api.js').href);
  say('imported agv-api.js');
  for (let i = 0; i < 30; i++) {
    try { await fetch('http://127.0.0.1:18901/health'); break; } catch { await new Promise((r) => setTimeout(r, 500)); }
  }

  const base = 'http://127.0.0.1:18901';
  const h = (r) => ({ acao: r.headers.get('access-control-allow-origin'), acac: r.headers.get('access-control-allow-credentials') });

  const ok = await fetch(base + '/health', { headers: { Origin: 'http://localhost:5178' } });
  say('allowed-origin GET /health      :', ok.status, JSON.stringify(h(ok)));

  const ok2 = await fetch(base + '/health', { headers: { Origin: 'http://127.0.0.1:5178' } });
  say('allowed-origin(2) GET /health   :', ok2.status, JSON.stringify(h(ok2)));

  const bad = await fetch(base + '/health', { headers: { Origin: 'http://evil.example' } });
  say('evil-origin GET /health         :', bad.status, JSON.stringify(h(bad)));

  const pre = await fetch(base + '/agv/fleet', { method: 'OPTIONS', headers: { Origin: 'http://evil.example', 'Access-Control-Request-Method': 'GET' } });
  say('evil-origin OPTIONS /agv/fleet  :', pre.status, JSON.stringify(h(pre)));

  const preOk = await fetch(base + '/agv/fleet', { method: 'OPTIONS', headers: { Origin: 'http://localhost:5178', 'Access-Control-Request-Method': 'GET' } });
  say('allowed-origin OPTIONS /agv/fleet:', preOk.status, JSON.stringify(h(preOk)));

  say('DONE');
} catch (e) { fail(e); }
process.exit(0);

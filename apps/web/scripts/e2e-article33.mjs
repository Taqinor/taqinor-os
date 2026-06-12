/**
 * Outil de session — vérifie le mini-formulaire Article 33 dans Chrome :
 * le lien WhatsApp se remplit en direct, jamais de blancs « ___ ».
 *
 *   node scripts/e2e-article33.mjs [url]
 */
import { execFile } from 'node:child_process';

const url = process.argv[2] ?? 'http://127.0.0.1:8788/regularization-article-33';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9227;
const chrome = execFile(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`, '--window-size=800,900', '--no-first-run', 'about:blank']);
await new Promise((r) => setTimeout(r, 2500));
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) pending.get(m.id)(m); };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
await new Promise((r) => (ws.onopen = r));
await send('Page.enable');
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 6000));
const out = await (async () => (await send('Runtime.evaluate', { returnByValue: true, awaitPromise: true, expression: `(async () => {
  const res = [];
  const set = (sel, v) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
  const href = () => decodeURIComponent(document.getElementById('rg33-go').href);
  res.push(['repli initial complet, sans blancs', href().includes('wa.me/212661850410') && !href().includes('___') && href().includes('à déterminer ensemble')]);
  set('#rg33-kwc', '7.5'); set('#rg33-ville', 'El Jadida');
  res.push(['kWc + ville intégrés au message', href().includes('Puissance approximative : 7.5 kWc') && href().includes('Ville : El Jadida.')]);
  const unk = document.getElementById('rg33-unknown'); unk.checked = true; unk.dispatchEvent(new Event('input', { bubbles: true }));
  res.push(['« je ne sais pas » désactive le champ et adapte le message', document.getElementById('rg33-kwc').disabled && href().includes('à déterminer ensemble') && href().includes('Ville : El Jadida.')]);
  res.push(['aucun blanc dans tous les cas', !href().includes('___')]);
  return res;
})()` })).result?.result?.value)();
let fail = 0;
for (const [label, okv] of out ?? [['eval failed', false]]) { console.log((okv ? 'OK   ' : 'ÉCHEC') + ' ' + label); if (!okv) fail++; }
chrome.kill();
process.exit(fail ? 1 : 0);

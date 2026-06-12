/**
 * Outil de session — audits de parcours :
 *  1. Diagnostic SOUS LE SEUIL (800-1000 MAD) de bout en bout dans le
 *     navigateur — l'extrait d'étude doit s'afficher quand même.
 *  2. prefers-reduced-motion : la vidéo du héros ne doit JAMAIS démarrer.
 *
 *   node scripts/audit-flows.mjs
 */
import { execFile } from 'node:child_process';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9226;
const chrome = execFile(CHROME, [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`,
  '--window-size=800,900', '--no-first-run', 'about:blank',
]);
await new Promise((r) => setTimeout(r, 2500));
const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) pending.get(msg.id)(msg);
};
const send = (method, params = {}) =>
  new Promise((resolve) => {
    const i = ++id;
    pending.set(i, resolve);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
const evaluate = async (expression) =>
  (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result?.result?.value;

await new Promise((r) => (ws.onopen = r));
await send('Page.enable');

// --- 1. Sous le seuil ---
await send('Page.navigate', { url: 'http://127.0.0.1:8788/contact' });
await new Promise((r) => setTimeout(r, 6000));
const sub = await evaluate(`(async () => {
  const out = [];
  const visible = (sel) => { const el = document.querySelector(sel); return !!el && el.offsetParent !== null; };
  const set = (sel, v) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  set('#lf-bill', '800-1000'); set('#lf-roof', 'autre');
  document.getElementById('diag-next').click(); await sleep(150);
  set('#lf-city', 'Settat');
  out.push(['signal soleil (repli national)', document.getElementById('diag-sun').textContent.includes('2 800')]);
  document.getElementById('diag-next').click(); await sleep(150);
  set('#lf-name', 'Test Seuil'); set('#lf-phone', '0612345678');
  document.querySelector('input[name="consent"]').click();
  document.getElementById('lf-submit').click(); await sleep(3500);
  out.push(['extrait affiché sous le seuil', visible('#lf-success')]);
  out.push(['bande = ' + document.getElementById('lf-kwc').textContent, document.getElementById('lf-kwc').textContent.includes('kWc')]);
  return out;
})()`);

// --- 2. prefers-reduced-motion sur l'accueil ---
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
await send('Page.navigate', { url: 'http://127.0.0.1:8788/' });
await new Promise((r) => setTimeout(r, 4500));
const rm = await evaluate(`(async () => {
  scrollTo(0, 600); document.dispatchEvent(new Event('pointerdown'));
  await new Promise((r) => setTimeout(r, 3500));
  const v = document.getElementById('hero-video');
  return [['reduced-motion : vidéo jamais démarrée', !v.src && v.paused]];
})()`);

let fail = 0;
for (const [label, okv] of [...(sub ?? []), ...(rm ?? [])]) {
  console.log((okv ? 'OK   ' : 'ÉCHEC') + ' ' + label);
  if (!okv) fail++;
}
chrome.kill();
process.exit(fail ? 1 : 0);

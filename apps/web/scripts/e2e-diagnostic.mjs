/**
 * Outil de session : parcours E2E réel du Diagnostic solaire en 3 étapes
 * dans Chrome headless (CDP) — étape 1 → 2 (signal ville) → 3 → soumission
 * → extrait d'étude. Vérifie aussi qu'un parcours incomplet ne soumet rien.
 *
 *   node scripts/e2e-diagnostic.mjs [url] [nomDuLead]
 */
import { execFile } from 'node:child_process';

const url = process.argv[2] ?? 'http://127.0.0.1:8788/contact';
const leadName = process.argv[3] ?? 'Test Parcours';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9225;

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
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 6000));

const results = await evaluate(`(async () => {
  const out = [];
  const visible = (sel) => { const el = document.querySelector(sel); return !!el && el.offsetParent !== null; };
  const set = (sel, v) => { const el = document.querySelector(sel); el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  out.push(['étape 1 visible au chargement', visible('fieldset[data-step="1"]') && !visible('fieldset[data-step="2"]')]);

  // Garde-fou : Continuer sans rien remplir → on reste à l'étape 1, erreur affichée
  document.getElementById('diag-next').click(); await sleep(150);
  out.push(['étape 1 invalide bloque', visible('fieldset[data-step="1"]') && visible('#lf-err')]);

  set('#lf-bill', '1500-3000'); set('#lf-roof', 'villa');
  document.getElementById('diag-next').click(); await sleep(150);
  out.push(['étape 2 atteinte', visible('fieldset[data-step="2"]')]);

  set('#lf-city', 'Casablanca'); await sleep(150);
  out.push(['signal ensoleillement affiché', visible('#diag-sun') && document.getElementById('diag-sun').textContent.includes('littoral')]);

  document.getElementById('diag-next').click(); await sleep(150);
  out.push(['étape 3 atteinte + bouton soumettre', visible('fieldset[data-step="3"]') && visible('#lf-submit')]);

  set('#lf-name', ${JSON.stringify(leadName)}); set('#lf-phone', '0661850410');
  document.querySelector('input[name="consent"]').click();
  document.getElementById('lf-submit').click();
  await sleep(3500);
  const kwc = document.getElementById('lf-kwc').textContent;
  const wa = document.getElementById('lf-wa').href;
  out.push(['extrait d\\'étude affiché', visible('#lf-success') && kwc.length > 0]);
  out.push(['kWc = ' + kwc + ' · ROI = ' + document.getElementById('lf-roi').textContent, true]);
  out.push(['deeplink WhatsApp prêt', wa.startsWith('https://wa.me/212661850410')]);
  return out;
})()`);

let fail = 0;
for (const [label, ok] of results ?? [['evaluation failed', false]]) {
  console.log((ok ? 'OK   ' : 'ÉCHEC') + ' ' + label);
  if (!ok) fail++;
}
chrome.kill();
process.exit(fail ? 1 : 0);

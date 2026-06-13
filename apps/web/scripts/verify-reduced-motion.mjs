/**
 * Outil de session : vérifie qu'en prefers-reduced-motion: reduce, la
 * prévisualisation v2 n'a AUCUN mouvement — contenu visible (révélations
 * neutralisées) et chiffres affichés à leur valeur finale (pas de count-up).
 *
 *   node scripts/verify-reduced-motion.mjs [url]
 */
import { execFile } from 'node:child_process';

const url = process.argv[2] ?? 'http://127.0.0.1:8788/v2';
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9224;

const chrome = execFile(CHROME, [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`,
  '--window-size=1280,900', '--no-first-run', 'about:blank',
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
await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 4000));

const result = await evaluate(`(async () => {
  const out = [];
  const rises = [...document.querySelectorAll('.v2-rise')];
  const allVisible = rises.length > 0 && rises.every((el) => parseFloat(getComputedStyle(el).opacity) === 1);
  out.push(['sections .v2-rise visibles (' + rises.length + ')', allVisible]);

  const tallies = [...document.querySelectorAll('[data-tally]')];
  const noZero = tallies.every((el) => {
    const t = el.textContent.trim();
    return t === '0 MAD' || !/^0(\\D|$)/.test(t);
  });
  out.push(['chiffres à leur valeur finale, ' + tallies.length + ' (pas de count-up)', noZero]);

  const media = document.querySelector('.v2-hero-media');
  const t = media ? getComputedStyle(media).transform : 'none';
  out.push(['héros sans parallaxe JS (transform=' + t + ')', t === 'none']);
  return out;
})()`);

let fail = 0;
for (const [label, ok] of result ?? [['évaluation échouée', false]]) {
  console.log((ok ? 'OK   ' : 'ÉCHEC') + ' ' + label);
  if (!ok) fail++;
}
chrome.kill();
process.exit(fail ? 1 : 0);

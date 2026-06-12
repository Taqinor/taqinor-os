/**
 * Outil de session : capture d'écran pleine page à largeur RÉELLEMENT
 * émulée (Emulation.setDeviceMetricsOverride) — contourne la largeur
 * minimale de fenêtre de Chrome headless (~467 px) qui faussait les
 * captures mobiles.
 *
 *   node scripts/shot.mjs <url> <largeur> <sortie.png> [hauteurMax]
 */
import { execFile } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const [url, widthArg, out, maxHArg] = process.argv.slice(2);
const width = Number(widthArg ?? 375);
const maxH = Number(maxHArg ?? 9000);
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9224;

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

await new Promise((r) => (ws.onopen = r));
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', {
  width, height: 900, deviceScaleFactor: 1, mobile: width < 700,
});
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 6000));
const metrics = await send('Page.getLayoutMetrics');
const height = Math.min(maxH, Math.ceil(metrics.result.cssContentSize.height));
await send('Emulation.setDeviceMetricsOverride', {
  width, height, deviceScaleFactor: 1, mobile: width < 700,
});
await new Promise((r) => setTimeout(r, 1200));
const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
console.log(out, `${width}x${height}`);
chrome.kill();
process.exit(0);

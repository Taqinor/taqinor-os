/**
 * Outil de session : détecte les débordements horizontaux mobiles.
 * Pilote Chrome headless via CDP (WebSocket natif de Node) et liste les
 * éléments plus larges que le viewport.
 *
 *   node scripts/find-overflow.mjs <url> [largeur]
 */
import { execFile } from 'node:child_process';

const url = process.argv[2] ?? 'http://127.0.0.1:8788/contact';
const width = Number(process.argv[3] ?? 375);
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const PORT = 9223;

const chrome = execFile(CHROME, [
  '--headless=new', '--disable-gpu', `--remote-debugging-port=${PORT}`,
  `--window-size=${width},900`, '--no-first-run', 'about:blank',
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
await send('Page.navigate', { url });
await new Promise((r) => setTimeout(r, 5000));
const res = await send('Runtime.evaluate', {
  returnByValue: true,
  expression: `(() => {
    const vw = document.documentElement.clientWidth;
    const out = ['viewport=' + vw, 'docScrollWidth=' + document.documentElement.scrollWidth];
    for (const el of document.querySelectorAll('*')) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 || r.left < -1) {
        out.push(\`\${el.tagName.toLowerCase()}.\${String(el.className).slice(0, 90)} left=\${Math.round(r.left)} right=\${Math.round(r.right)} w=\${Math.round(r.width)}\`);
      }
      if (out.length > 40) break;
    }
    return out.join('\\n');
  })()`,
});
console.log(res.result?.result?.value ?? JSON.stringify(res).slice(0, 500));
chrome.kill();
process.exit(0);

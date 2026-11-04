#!/usr/bin/env node
/**
 * WAUD44 — sonde bidi : sur 4 pages arabes, « 82-21 » et les montants à milliers se
 * lisent de gauche à droite à l'écran (position du 1er caractère < position du dernier),
 * et une police arabe auto-hébergée est bien chargée.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/bidi-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const ROUTES = ['/ar/', '/ar/garanties/', '/ar/loi-82-21/', '/ar/prix-panneaux-solaires-maroc/'];
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

const MESURE = `(async () => {
  await document.fonts.ready;
  const inversions = [];
  let vus = 0;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const motif = /82-21|\\d{1,3}(?:[ \\u00a0\\u202f]\\d{3})+/g;
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const e = n.parentElement;
    if (!e || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(e.tagName) || !e.getClientRects().length) continue;
    for (const m of n.data.matchAll(motif)) {
      const r = document.createRange();
      r.setStart(n, m.index); r.setEnd(n, m.index + 1);
      const a = r.getBoundingClientRect();
      r.setStart(n, m.index + m[0].length - 1); r.setEnd(n, m.index + m[0].length);
      const b = r.getBoundingClientRect();
      if (!a.width || !b.width || Math.abs(a.top - b.top) > 2) continue;
      vus += 1;
      if (a.left > b.left) inversions.push(m[0]);
    }
  }
  const polices = [...document.fonts].filter((f) => f.family.includes('Noto Sans Arabic') && f.status === 'loaded').length;
  return JSON.stringify({ vus, inversions, polices });
})()`;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
  let echec = false;
  for (const route of ROUTES) {
    const c = await connecter(chrome.port);
    await c.envoyer('Page.enable');
    await c.envoyer('Runtime.enable');
    await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
    await c.envoyer('Page.navigate', { url: base + route });
    await pause(2500);
    const { result } = await c.envoyer('Runtime.evaluate', { expression: MESURE, awaitPromise: true });
    const m = JSON.parse(result.value);
    const ok = m.inversions.length === 0 && m.polices > 0;
    echec ||= !ok;
    console.log(`${ok ? 'OK ' : 'KO '} ${route}  ${m.vus} suites, inversions=[${m.inversions.slice(0, 5)}], polices arabes=${m.polices}`);
    c.fermer();
  }
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(echec ? 1 : 0);
}

#!/usr/bin/env node
/**
 * WAUD84 — longueur de l'accueil à 390 px : hauteur du document (≤ 11 000 px), nombre
 * d'estimateurs (≤ 1), libellés distincts de CTA vers le devis (≤ 3), hauteur de chaque bloc.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/home-length-probe.mjs --base-url=http://127.0.0.1:4321 [--route=/]
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const HAUTEUR_MAX_PX = 11000;
export const LIBELLES_MAX = 3;
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

const MESURE = `JSON.stringify((() => {
  const blocs = [...document.querySelectorAll('main section, main > div > section, .v2 > section')]
    .filter((s, i, t) => t.indexOf(s) === i && s.getClientRects().length)
    .map((s) => [Math.round(s.getBoundingClientRect().height), (s.querySelector('h1,h2,h3,p') || s).textContent.trim().slice(0, 50)]);
  const cta = [...document.querySelectorAll('a[href*="/devis/mon-toit"]')]
    .filter((a) => !a.closest('header, footer, #sticky-cta, nav') && a.getClientRects().length)
    .map((a) => a.textContent.trim().replace(/\\s+/g, ' '));
  return {
    docH: document.documentElement.scrollHeight,
    estimateurs: document.querySelectorAll('[data-instant-estimator]').length,
    libelles: [...new Set(cta)],
    blocs,
  };
})())`;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const route = (process.argv.find((a) => a.startsWith('--route=')) ?? '--route=/').split('=')[1];
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost'] });
  const c = await connecter(chrome.port);
  await c.envoyer('Page.enable');
  await c.envoyer('Runtime.enable');
  await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await c.envoyer('Page.navigate', { url: base + route });
  await pause(3000);
  const { result } = await c.envoyer('Runtime.evaluate', { expression: MESURE });
  const m = JSON.parse(result.value);
  const ok = m.docH <= HAUTEUR_MAX_PX && m.estimateurs <= 1 && m.libelles.length <= LIBELLES_MAX;
  console.log(`${ok ? 'OK ' : 'KO '} ${route} docH=${m.docH} estimateurs=${m.estimateurs} libellés=${m.libelles.length}`);
  for (const l of m.libelles) console.log(`  CTA: ${l}`);
  for (const [h, t] of m.blocs) console.log(`  ${String(h).padStart(5)} ${t}`);
  c.fermer();
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(ok ? 0 : 1);
}

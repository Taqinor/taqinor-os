#!/usr/bin/env node
/**
 * WAUD64 — sonde des cibles tactiles à 390 px : 0 lien/bouton < 24 px de haut (hors lien dans du texte
 * courant, WCAG 2.5.8) ; liens fléchés « … → », puces de filtre et CTA devis/WhatsApp ≥ 44 px.
 * Hôtes non locaux bloqués (aucune requête Meta / analytics).
 *
 * USAGE : servir apps/web/dist/client (astro preview), puis
 *   node scripts/target-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const ROUTES = ['/', '/realisations/', '/installation-solaire-casablanca/', '/en/', '/ar/'];
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

const MESURE = `(() => {
  const petites = [], grandes = [];
  const visible = (a, r) => r.width && r.height && getComputedStyle(a).visibility !== 'hidden' && !a.closest('[hidden], .sr-only, .skip-link') && r.top + scrollY >= 0;
  for (const a of document.querySelectorAll('a[href], button')) {
    const r = a.getBoundingClientRect();
    if (!visible(a, r) || a.closest('.maplibregl-ctrl')) continue;
    const cs = getComputedStyle(a);
    const p = a.parentElement;
    const enLigne = cs.display === 'inline' && p && /^(P|LI|TD|DD|SPAN|BLOCKQUOTE)$/.test(p.tagName) && (p.textContent || '').trim().length > (a.textContent || '').trim().length + 20;
    const txt = (a.textContent || a.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 40);
    if (!enLigne && r.height < 24) petites.push(Math.round(r.height) + 'px «' + txt + '»');
    const fleche = /→|←/.test(a.textContent || '') && !enLigne && !a.closest('header') && !a.classList.contains('ribbon-link');
    const puce = a.classList.contains('gallery-filter-chip');
    const cta = a.closest('main') && /\\/devis\\/mon-toit|wa\\.me/.test(a.getAttribute('href') || '') && cs.display !== 'inline' && !enLigne;
    if ((fleche || puce || cta) && r.height < 44) grandes.push(Math.round(r.height) + 'px «' + txt + '»');
  }
  return JSON.stringify({ petites, grandes });
})()`;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost'] });
  let echec = false;
  for (const route of ROUTES) {
    const c = await connecter(chrome.port);
    await c.envoyer('Page.enable');
    await c.envoyer('Runtime.enable');
    await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
    await c.envoyer('Page.navigate', { url: encodeURI(base + route) });
    await pause(2500);
    const { result } = await c.envoyer('Runtime.evaluate', { expression: MESURE });
    const m = JSON.parse(result.value);
    const ok = m.petites.length === 0 && m.grandes.length === 0;
    echec ||= !ok;
    console.log(`${ok ? 'OK ' : 'KO '} ${route}  < 24 px : ${m.petites.length} ${m.petites.slice(0, 4).join(' ')} ; fléchés/puces/CTA < 44 px : ${m.grandes.length} ${m.grandes.slice(0, 4).join(' ')}`);
    c.fermer();
  }
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(echec ? 1 : 0);
}

#!/usr/bin/env node
/**
 * WAUD3 — sonde du premier écran : à la PREMIÈRE visite (bandeau de consentement
 * affiché), le CTA du héros est entièrement dans l'écran et rien ne le recouvre,
 * à 360×740 et 390×844, en FR/EN/AR. Mesure aussi la hauteur du bandeau (≤ 72 px).
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/fold-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const ECRANS = [[360, 740], [390, 844]];
export const ROUTES = ['/', '/en/', '/ar/'];
export const BANDEAU_MAX_PX = 72;
export const PREMIER_CTA_MAX_PX = 2500;
export const ROUTES_LECTURE = [
  '/installation-solaire-casablanca/',
  '/realisations/el-jadida-17-kwc/',
  '/garanties/',
  '/prix-panneaux-solaires-maroc/',
];

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

// CTA : le premier lien vers le parcours devis du premier <section>.
const MESURE = `(() => {
  const cta = document.querySelector('#hero-cta-magnetic') || document.querySelector('section a[href*="/devis/mon-toit"]');
  const bandeau = document.getElementById('tq-consent-banner');
  const rB = bandeau && !bandeau.classList.contains('hidden') ? bandeau.getBoundingClientRect() : null;
  if (!cta) return JSON.stringify({ absent: true });
  const r = cta.getBoundingClientRect();
  const points = [[r.left + 4, r.top + 4], [r.right - 4, r.top + 4], [r.left + 4, r.bottom - 4], [r.right - 4, r.bottom - 4]];
  const couvert = points.some(([x, y]) => {
    const e = document.elementFromPoint(x, y);
    return !e || !(e === cta || cta.contains(e));
  });
  return JSON.stringify({ haut: r.top, bas: r.bottom, h: innerHeight, couvert, bandeau: rB ? rB.height : null });
})()`;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
  let echec = false;
  for (const [largeur, hauteur] of ECRANS) {
    for (const route of ROUTES) {
      const c = await connecter(chrome.port);
      await c.envoyer('Page.enable');
      await c.envoyer('Runtime.enable');
      await c.envoyer('Emulation.setDeviceMetricsOverride', { width: largeur, height: hauteur, deviceScaleFactor: 2, mobile: true });
      await c.envoyer('Page.navigate', { url: base + route });
      await pause(2500);
      const { result } = await c.envoyer('Runtime.evaluate', { expression: MESURE });
      const m = JSON.parse(result.value);
      const ok = !m.absent && m.haut >= 0 && m.bas <= m.h && !m.couvert && m.bandeau !== null && m.bandeau <= BANDEAU_MAX_PX;
      echec ||= !ok;
      console.log(`${ok ? 'OK ' : 'KO '} ${largeur}x${hauteur} ${route}  CTA ${Math.round(m.haut)}-${Math.round(m.bas)} / ${m.h}  couvert=${m.couvert}  bandeau=${m.bandeau === null ? 'absent' : Math.round(m.bandeau)} px`);
      c.fermer();
    }
  }
  // WAUD35 — premier CTA devis dans le contenu (hors en-tête, barre et pied) ≤ 2 500 px.
  for (const route of ROUTES_LECTURE) {
    const c = await connecter(chrome.port);
    await c.envoyer('Page.enable');
    await c.envoyer('Runtime.enable');
    await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
    await c.envoyer('Page.navigate', { url: encodeURI(base + route) });
    await pause(2500);
    const { result } = await c.envoyer('Runtime.evaluate', {
      expression: `(() => { const l = [...document.querySelectorAll('a[href*="/devis/mon-toit"]')].find((a) => !a.closest('header, footer, #sticky-cta, nav')); return l ? Math.round(l.getBoundingClientRect().top + scrollY) : -1; })()`,
    });
    const y = result.value;
    const ok = y >= 0 && y <= PREMIER_CTA_MAX_PX;
    echec ||= !ok;
    console.log(`${ok ? 'OK ' : 'KO '} 390x844 ${route}  premier CTA à ${y} px`);
    c.fermer();
  }
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(echec ? 1 : 0);
}

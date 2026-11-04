#!/usr/bin/env node
/**
 * WAUD12 / WAUD66 — sonde de consentement, UA MOBILE (un UA headless par défaut
 * ne voit aucun /tr de Meta : faux vert). Avant tout choix, sur 24 pages : 0 cookie
 * traceur, 0 requête vers Meta/Google. Après « Accepter » : fbevents.js chargé et
 * PageView en réseau ; tout traceur posé doit figurer au tableau de la politique.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/consent-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { readFileSync } from 'node:fs';
import { connecter } from './idle-probe.mjs';

const UA_MOBILE =
  'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36';
const TIERS = /facebook\.(net|com)|googletagmanager|google-analytics|doubleclick/;
const COOKIES_TRACEURS = /^(_fbp|_fbc|fr|_ga|_ga_.*|_gcl_.*|tq_appareil)$/;
export const ROUTES = process.env.CONSENT_PROBE_RAPIDE ? ['/'] : [
  '/', '/en/', '/ar/', '/résidentiel/', '/professionnel/', '/agricole/', '/nos-solutions/', '/realisations/',
  '/contact/', '/en/contact/', '/ar/contact/', '/garanties/', '/a-propos/', '/blog/', '/loi-82-21/',
  '/prix-panneaux-solaires-maroc/', '/en/prix-panneaux-solaires-maroc/', '/ar/prix-panneaux-solaires-maroc/',
  '/installation-solaire-casablanca/', '/installation-solaire-marrakech/', '/pompage-solaire/',
  '/devis/mon-toit/', '/en/devis/mon-toit/', '/politique-de-confidentialite/',
];

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function ouvrir(port) {
  const c = await connecter(port);
  const requetes = [];
  await c.envoyer('Network.enable');
  await c.envoyer('Page.enable');
  await c.envoyer('Runtime.enable');
  await c.envoyer('Emulation.setUserAgentOverride', { userAgent: UA_MOBILE });
  await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  c.sur('Network.requestWillBeSent', (p) => requetes.push(p.request.url));
  return { c, requetes };
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const tableau = readFileSync(new URL('../src/components/TableauTraceurs.astro', import.meta.url), 'utf-8');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox', '--disable-blink-features=AutomationControlled'] });
  let echecs = 0;
  const { c, requetes } = await ouvrir(chrome.port);
  await c.envoyer('Network.clearBrowserCookies');
  for (const route of ROUTES) {
    requetes.length = 0;
    await c.envoyer('Page.navigate', { url: encodeURI(base + route) });
    await pause(2500);
    const { cookies } = await c.envoyer('Network.getAllCookies');
    const poses = cookies.map((x) => x.name).filter((n) => COOKIES_TRACEURS.test(n));
    const tiers = requetes.filter((u) => TIERS.test(u));
    const ok = poses.length === 0 && tiers.length === 0;
    if (!ok) echecs += 1;
    console.log(`${ok ? 'OK ' : 'KO '} avant choix ${route}  cookies=[${poses}] tiers=${tiers.length}`);
  }
  requetes.length = 0;
  await c.envoyer('Page.navigate', { url: `${base}/` });
  await pause(2500);
  await c.envoyer('Runtime.evaluate', { expression: "document.querySelector('[data-consent-accept]').click()" });
  await pause(8000);
  const { cookies } = await c.envoyer('Network.getAllCookies');
  const pixel = requetes.some((u) => u.includes('fbevents.js'));
  const pageView = requetes.some((u) => /facebook\.com\/tr.*PageView/.test(u));
  console.log(`${pixel ? 'OK ' : 'KO '} après Accepter : fbevents.js chargé`);
  console.log(`${pageView ? 'OK ' : 'KO '} après Accepter : PageView en réseau (exige Internet)`);
  if (!pixel || !pageView) echecs += 1;
  console.log(requetes.filter((u) => TIERS.test(u)).map((u) => `   ${u.slice(0, 140)}`).join('\n'));
  for (const n of cookies.map((x) => x.name).filter((x) => COOKIES_TRACEURS.test(x))) {
    const present = tableau.includes(n.replace(/^(_ga_).*/, '$1*'));
    if (!present) echecs += 1;
    console.log(`${present ? 'OK ' : 'KO '} traceur posé ${n} ${present ? 'au tableau' : 'ABSENT du tableau'}`);
  }
  c.fermer();
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(echecs ? 1 : 0);
}

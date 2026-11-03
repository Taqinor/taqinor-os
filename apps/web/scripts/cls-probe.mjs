#!/usr/bin/env node
/**
 * WAUD79 — sonde CLS (téléphone émulé, réseau ralenti pour que le repli de police
 * s'affiche vraiment) : médiane de 3 chargements sur /, /en/, /ar/. Seuil < 0,02.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/cls-probe.mjs --base-url=http://127.0.0.1:4321
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const ROUTES_CLS = ['/', '/en/', '/ar/'];
export const SEUIL_CLS = 0.02;

const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const OBSERVATEUR = `window.__cls=0;new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)window.__cls+=e.value}).observe({type:'layout-shift',buffered:true});`;

async function clsUneFois(port, url) {
  const c = await connecter(port);
  await c.envoyer('Page.enable');
  await c.envoyer('Runtime.enable');
  await c.envoyer('Network.enable');
  await c.envoyer('Network.setCacheDisabled', { cacheDisabled: true });
  await c.envoyer('Network.emulateNetworkConditions', {
    offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8,
  });
  await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 412, height: 823, deviceScaleFactor: 1.75, mobile: true });
  await c.envoyer('Page.addScriptToEvaluateOnNewDocument', { source: OBSERVATEUR });
  await c.envoyer('Page.navigate', { url });
  await pause(9000);
  const r = await c.envoyer('Runtime.evaluate', { expression: 'window.__cls' });
  c.fermer();
  return r.result?.value ?? 0;
}

const arg = process.argv.find((a) => a.startsWith('--base-url='));
const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
let echec = false;
for (const route of ROUTES_CLS) {
  const mesures = [];
  for (let i = 0; i < 3; i += 1) mesures.push(await clsUneFois(chrome.port, base + route));
  const mediane = [...mesures].sort((a, b) => a - b)[1];
  const ok = mediane < SEUIL_CLS;
  echec ||= !ok;
  console.log(`${ok ? 'OK ' : 'KO '} ${route}  CLS médiane ${mediane.toFixed(4)}  (${mesures.map((m) => m.toFixed(4)).join(', ')})`);
}
try { await chrome.kill(); } catch { /* EPERM Windows */ }
process.exit(echec ? 1 : 0);

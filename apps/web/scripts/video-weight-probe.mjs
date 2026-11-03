#!/usr/bin/env node
/**
 * WAUD54 — sonde « octets de l'accueil sur téléphone en 3G » : UA + viewport
 * mobile, réseau slow-3G émulé, défilement jusqu'en bas, puis somme des octets
 * reçus et liste des .mp4 demandés. Seuil : < 1,8 Mo et aucun .mp4.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/video-weight-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';
import { connecter } from './idle-probe.mjs';

export const SEUIL_OCTETS = 1.8 * 1024 * 1024;
const UA_MOBILE =
  'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36';
const SLOW_3G = { offline: false, latency: 400, downloadThroughput: 50_000, uploadThroughput: 50_000, connectionType: 'cellular3g' };

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function mesurer(port, url) {
  const c = await connecter(port);
  let octets = 0;
  const videos = [];
  await c.envoyer('Network.enable');
  await c.envoyer('Page.enable');
  await c.envoyer('Runtime.enable');
  await c.envoyer('Network.emulateNetworkConditions', SLOW_3G);
  await c.envoyer('Emulation.setUserAgentOverride', { userAgent: UA_MOBILE });
  await c.envoyer('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  c.sur('Network.dataReceived', (p) => { octets += p.encodedDataLength || p.dataLength || 0; });
  c.sur('Network.requestWillBeSent', (p) => { if (/\.mp4(\?|$)/.test(p.request.url)) videos.push(p.request.url); });
  await c.envoyer('Page.navigate', { url });
  await pause(8000);
  for (let i = 0; i < 25; i += 1) {
    await c.envoyer('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight)' });
    await pause(600);
  }
  await pause(4000);
  c.fermer();
  return { octets, videos };
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
  const { octets, videos } = await mesurer(chrome.port, `${base}/`);
  const ok = octets < SEUIL_OCTETS && videos.length === 0;
  console.log(`${ok ? 'OK ' : 'KO '} / : ${(octets / 1024 / 1024).toFixed(2)} Mo reçus, ${videos.length} .mp4 ${videos.join(' ')}`);
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(ok ? 0 : 1);
}

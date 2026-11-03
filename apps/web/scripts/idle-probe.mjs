#!/usr/bin/env node
/**
 * WAUD8 — sonde « processeur au repos » : combien de temps le fil principal
 * travaille sur une page qu'on ne touche pas (une animation sur `filter` force
 * une peinture à chaque image et garde les téléphones à 100 %).
 *
 * Mesure `TaskDuration` (Performance.getMetrics, CDP) sur 10 s, après 5 s de
 * stabilisation. Seuil : < 0,3 s par 10 s. Sortie 1 si une page dépasse.
 *
 * USAGE : servir apps/web/dist/client, puis
 *   node scripts/idle-probe.mjs --base-url=http://127.0.0.1:4321
 * ENV : CHROME_PATH (chrome-launcher).
 */
import { launch } from 'chrome-launcher';

export const ROUTES_REPOS = [
  '/',
  '/ar/',
  '/installation-solaire-casablanca/',
  '/guides/loi-82-21-expliquee/',
  '/devis/mon-toit/',
];
export const SEUIL_TACHES_S = 0.3;
const FENETRE_MS = 10_000;
const STABILISATION_MS = 5_000;

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

/** Client CDP minimal (WebSocket natif de Node ≥ 22). */
export async function connecter(port) {
  const cibles = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(cibles.webSocketDebuggerUrl);
  await new Promise((ok, ko) => { ws.onopen = ok; ws.onerror = ko; });
  let id = 0;
  const attente = new Map();
  const ecouteurs = new Map();
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && attente.has(d.id)) {
      attente.get(d.id)(d.result ?? {});
      attente.delete(d.id);
    } else if (d.method && ecouteurs.has(d.method)) {
      ecouteurs.get(d.method).forEach((f) => f(d.params));
    }
  };
  return {
    envoyer: (method, params = {}) => new Promise((ok) => {
      id += 1;
      attente.set(id, ok);
      ws.send(JSON.stringify({ id, method, params }));
    }),
    sur: (method, f) => ecouteurs.set(method, [...(ecouteurs.get(method) ?? []), f]),
    fermer: () => ws.close(),
  };
}

async function tachesAuRepos(port, url) {
  const c = await connecter(port);
  await c.envoyer('Performance.enable');
  await c.envoyer('Page.enable');
  await c.envoyer('Page.navigate', { url });
  await pause(STABILISATION_MS);
  const lire = async () => {
    const { metrics } = await c.envoyer('Performance.getMetrics');
    return metrics.find((m) => m.name === 'TaskDuration')?.value ?? 0;
  };
  const avant = await lire();
  await pause(FENETRE_MS);
  const apres = await lire();
  c.fermer();
  return apres - avant;
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop())) {
  const arg = process.argv.find((a) => a.startsWith('--base-url='));
  const base = (arg ? arg.split('=')[1] : process.env.BASE_URL || 'http://127.0.0.1:4321').replace(/\/$/, '');
  const chrome = await launch({ chromeFlags: ['--headless=new', '--no-sandbox'] });
  let echec = false;
  for (const route of ROUTES_REPOS) {
    const s = await tachesAuRepos(chrome.port, base + route);
    const ok = s < SEUIL_TACHES_S;
    echec ||= !ok;
    console.log(`${ok ? 'OK ' : 'KO '} ${route}  TaskDuration ${s.toFixed(3)} s / 10 s`);
  }
  try { await chrome.kill(); } catch { /* EPERM Windows */ }
  process.exit(echec ? 1 : 0);
}

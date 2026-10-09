#!/usr/bin/env node
/**
 * Tour design (YBW42 → YBW43) — captures des trois accueils candidats sur le
 * BUILD servi localement (`astro preview` : le vrai Worker, ses en-têtes et sa
 * CSP), pour la critique visuelle YBW43 et le choix de Reda (YBWM12).
 *
 * Pour chaque candidat (`/_design/a|b|c/`), chaque langue (FR, EN), chaque
 * largeur (375 et 1440 px par défaut) et chaque schéma rendu (A et B : clair
 * et sombre ; C : clair seulement) : une capture PLEINE PAGE en JPEG dans
 * `design-round/` (`<candidat>-<langue>-<largeur>-<schema>.jpg`) + `index.json`.
 *
 * Prérequis : `npm run build`. Usage :
 *   node scripts/capture-design-round.mjs [--largeurs 320,375,768,1440]
 * Local seulement : le serveur est lancé sur 127.0.0.1 et arrêté à la fin.
 */
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const RACINE = fileURLToPath(new URL('../', import.meta.url));
const SORTIE = fileURLToPath(new URL('../design-round/', import.meta.url));
const PORT = 4331;
const BASE = `http://127.0.0.1:${PORT}`;

/** Schémas rendus par candidat — même source que src/styles/candidates/candidats.ts. */
const CANDIDATS = { a: ['clair', 'sombre'], b: ['clair', 'sombre'], c: ['clair'] };
const LANGUES = ['fr', 'en'];

const arg = process.argv.indexOf('--largeurs');
const LARGEURS = arg > 0 ? process.argv[arg + 1].split(',').map(Number) : [375, 1440];

/**
 * @param {string} url
 * @param {number} [delaiMs]
 */
async function attendre(url, delaiMs = 60_000) {
  const fin = Date.now() + delaiMs;
  while (Date.now() < fin) {
    try {
      const r = await fetch(url);
      if (r.ok) return;
    } catch {
      /* pas encore prêt */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`serveur local injoignable : ${url}`);
}

const serveur = spawn('npx', ['astro', 'preview', '--host', '127.0.0.1', '--port', String(PORT)], {
  cwd: RACINE,
  shell: true,
  stdio: 'ignore',
});

try {
  await attendre(`${BASE}/robots.txt`);
  mkdirSync(SORTIE, { recursive: true });
  const navigateur = await chromium.launch();
  const index = [];
  for (const [id, schemas] of Object.entries(CANDIDATS)) {
    for (const langue of LANGUES) {
      const chemin = langue === 'en' ? `/_design/${id}/en/` : `/_design/${id}/`;
      for (const schema of schemas) {
        for (const largeur of LARGEURS) {
          const contexte = await navigateur.newContext({
            viewport: { width: largeur, height: largeur < 768 ? 812 : 900 },
            deviceScaleFactor: 1,
            colorScheme: schema === 'sombre' ? 'dark' : 'light',
            reducedMotion: 'reduce',
          });
          const page = await contexte.newPage();
          await page.goto(BASE + chemin, { waitUntil: 'networkidle' });
          await page.evaluate(() => document.fonts.ready);
          const fichier = `${id}-${langue}-${largeur}-${schema}.jpg`;
          await page.screenshot({ path: SORTIE + fichier, fullPage: true, type: 'jpeg', quality: 72 });
          index.push({ candidat: id, langue, largeur, schema, chemin, fichier });
          await contexte.close();
          console.log(`capture : ${fichier}`);
        }
      }
    }
  }
  await navigateur.close();
  writeFileSync(SORTIE + 'index.json', JSON.stringify({ largeurs: LARGEURS, captures: index }, null, 2) + '\n');
} finally {
  serveur.kill();
  if (process.platform === 'win32' && serveur.pid) spawn('taskkill', ['/pid', String(serveur.pid), '/t', '/f'], { stdio: 'ignore' });
}

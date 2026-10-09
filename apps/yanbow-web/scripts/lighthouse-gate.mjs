#!/usr/bin/env node
/**
 * YBW16 — porte Lighthouse ≥ 97 (performance, accessibilité, bonnes pratiques,
 * SEO), mobile, sur chaque URL du registre `src/i18n/pages.ts` présente dans
 * `dist/client/` (+ la page sonde tant qu'elle existe). LCP borné ; CLS borné
 * dans une seconde passe où les polices sont bloquées.
 *
 * Prérequis : `npm run build`. Le script démarre lui-même `astro preview`
 * (le vrai Worker : en-têtes, CSP, porte de lancement) puis lance Chromium —
 * celui de Playwright (`npx playwright install chromium`), ou `CHROME_PATH`.
 *
 * Usage : `npm run lighthouse` (ou `node scripts/lighthouse-gate.mjs
 *         [--urls=/a/,/b/] [--base-url=http://127.0.0.1:4329]`).
 * `--urls` remplace la liste (utile pour prouver qu'une page alourdie échoue).
 * Code de sortie non nul si une URL passe sous un seuil. Durée totale affichée.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { launch } from 'chrome-launcher';
import lighthouse from 'lighthouse';
import ts from 'typescript';
import {
  AUDITS_IGNORES,
  CATEGORIES,
  CLS_MAX_POLICES_BLOQUEES,
  LCP_MAX_MS,
  MOTIFS_POLICES,
  SCORE_FLOOR,
} from './lighthouse.config.mjs';

const RACINE = new URL('../', import.meta.url);
const DIST_CLIENT = fileURLToPath(new URL('dist/client/', RACINE));
const PORT = 4329;

/** @param {string[]} argv */
function lireArguments(argv) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const a of argv) {
    const m = /^--([\w-]+)=(.*)$/.exec(a);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

/**
 * Charge le registre TypeScript `src/i18n/pages.ts` sans dépendance de plus :
 * transpilation par `typescript` (devDependency) puis import d'une data-URL.
 * Le fichier n'importe que des TYPES, effacés à la transpilation.
 * @returns {Promise<{ PAGES: Record<string, Record<string, string>> }>}
 */
async function chargerRegistre() {
  const source = readFileSync(new URL('src/i18n/pages.ts', RACINE), 'utf-8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
}

/** @param {string} url chemin avec barre finale */
function construite(url) {
  const fichier = url === '/' ? 'index.html' : url.replace(/^\//, '') + 'index.html';
  return existsSync(DIST_CLIENT + fichier);
}

/** @param {string} base */
async function attendreServeur(base) {
  for (let i = 0; i < 120; i++) {
    try {
      const r = await globalThis.fetch(base + '/robots.txt');
      if (r.ok) return;
    } catch {
      /* pas encore prêt */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`serveur ${base} injoignable après 60 s`);
}

async function cheminChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  try {
    const { chromium } = await import('@playwright/test');
    const p = chromium.executablePath();
    if (p && existsSync(p)) return p;
  } catch {
    /* Playwright absent : chrome-launcher cherchera un Chrome installé */
  }
  return undefined;
}

/**
 * @param {string} url
 * @param {number} port
 * @param {string[]} [bloques]
 */
async function mesurer(url, port, bloques = []) {
  const res = await lighthouse(url, {
    port,
    output: 'json',
    logLevel: 'error',
    onlyCategories: CATEGORIES,
    skipAudits: AUDITS_IGNORES,
    blockedUrlPatterns: bloques,
  });
  if (!res) throw new Error(`Lighthouse n'a rien rendu pour ${url}`);
  return res.lhr;
}

async function principal() {
  const debut = Date.now();
  const args = lireArguments(process.argv.slice(2));
  if (!existsSync(DIST_CLIENT)) throw new Error('dist/client/ absent — lancer `npm run build` d’abord');

  let urls;
  if (args.urls) {
    urls = args.urls.split(',').filter(Boolean);
  } else {
    const { PAGES } = await chargerRegistre();
    const candidates = Object.values(PAGES).flatMap((p) => Object.values(p));
    urls = [...new Set(candidates)].filter(construite);
  }
  if (urls.length === 0) {
    console.log('[lighthouse] aucune URL du registre n’est construite — rien à mesurer.');
    return 0;
  }

  let serveur = null;
  const base = args['base-url'] || `http://127.0.0.1:${PORT}`;
  if (!args['base-url']) {
    serveur = spawn('npx', ['astro', 'preview', '--host', '127.0.0.1', '--port', String(PORT)], {
      cwd: fileURLToPath(RACINE),
      stdio: 'ignore',
      shell: process.platform === 'win32',
      // Groupe de processus propre (Linux/macOS) : tuer npx ET astro preview.
      detached: process.platform !== 'win32',
    });
  }
  const chrome = await launch({
    chromePath: await cheminChrome(),
    chromeFlags: ['--headless=new', '--no-sandbox', '--disable-gpu'],
  });
  let echecs = 0;
  try {
    await attendreServeur(base);
    for (const chemin of urls) {
      const url = new URL(chemin, base).href;
      const lhr = await mesurer(url, chrome.port);
      const scores = Object.fromEntries(CATEGORIES.map((c) => [c, Math.round((lhr.categories[c]?.score ?? 0) * 100)]));
      const lcp = Math.round(lhr.audits['largest-contentful-paint']?.numericValue ?? Infinity);
      const sansPolices = await mesurer(url, chrome.port, MOTIFS_POLICES);
      const cls = sansPolices.audits['cumulative-layout-shift']?.numericValue ?? Infinity;

      const fautes = CATEGORIES.filter((c) => scores[c] < SCORE_FLOOR).map((c) => {
        // Audits pondérés non réussis de la catégorie : dit QUOI corriger.
        const rates = (lhr.categories[c]?.auditRefs ?? [])
          .filter((ref) => ref.weight > 0 && (lhr.audits[ref.id]?.score ?? 1) < 1)
          .map((ref) => ref.id);
        return `${c} ${scores[c]} < ${SCORE_FLOOR} (${rates.join(', ')})`;
      });
      if (lcp > LCP_MAX_MS) fautes.push(`LCP ${lcp} ms > ${LCP_MAX_MS} ms`);
      if (cls >= CLS_MAX_POLICES_BLOQUEES) fautes.push(`CLS (polices bloquées) ${cls.toFixed(3)} ≥ ${CLS_MAX_POLICES_BLOQUEES}`);

      const ligne = `${chemin}  ${CATEGORIES.map((c) => `${c}=${scores[c]}`).join(' ')}  LCP=${lcp}ms  CLS(polices bloquées)=${cls.toFixed(3)}`;
      if (fautes.length) {
        echecs++;
        console.log(`ÉCHEC  ${ligne}\n       → ${fautes.join(' ; ')}`);
      } else {
        console.log(`OK     ${ligne}`);
      }
    }
  } finally {
    await chrome.kill();
    if (serveur?.pid) {
      try {
        if (process.platform === 'win32') spawnSync('taskkill', ['/pid', String(serveur.pid), '/T', '/F'], { stdio: 'ignore' });
        else process.kill(-serveur.pid, 'SIGTERM');
      } catch {
        /* déjà arrêté */
      }
    }
  }
  console.log(`[lighthouse] ${urls.length} URL mesurée(s), ${echecs} échec(s), durée ${Math.round((Date.now() - debut) / 1000)} s`);
  return echecs ? 1 : 0;
}

principal().then(
  (code) => process.exit(code),
  (e) => {
    console.error(`[lighthouse] erreur : ${e instanceof Error ? e.message : e}`);
    process.exit(1);
  },
);

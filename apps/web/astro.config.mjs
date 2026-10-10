// @ts-check
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { defineConfig } from 'astro/config';
import { dossierClient, retirerPreviewToiture } from './scripts/retirer-preview-toiture.mjs';

import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

/**
 * SEO (10/10/2026, T2_seo_site §3) — `<lastmod>` dans le sitemap.
 *
 * Le sitemap n'avait aucune date : Google ne voit pas quelles pages ont changé.
 * La date d'une URL = date du dernier commit qui a touché son fichier source
 * (page .astro ou article de contenu). Lue en UNE passe `git log --name-only`
 * sur src/pages + src/content, puis chaque URL est rapprochée de son fichier :
 * route statique → `src/pages/<route>.astro` (ou `/index.astro`), article →
 * `src/content/blog/<slug>.md`, route dynamique (`[city]`, `[...slug]`) → le
 * gabarit. Sans correspondance, ou si le dépôt est un clone superficiel (une
 * seule date pour tout — ce serait une fausse fraîcheur), AUCUN lastmod n'est
 * émis : un sitemap sans date vaut mieux qu'un sitemap qui ment.
 */
function datesDeDernierCommit() {
  const racine = path.dirname(fileURLToPath(import.meta.url));
  try {
    const peuProfond = execSync('git rev-parse --is-shallow-repository', { cwd: racine, encoding: 'utf8' }).trim();
    if (peuProfond === 'true') return new Map();
    const journal = execSync('git log --format=%cI --name-only -- src/pages src/content', {
      cwd: racine, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024
    });
    const dates = new Map();
    let dateCourante = null;
    for (const ligne of journal.split(/\r?\n/)) {
      const l = ligne.trim();
      if (!l) continue;
      if (/^\d{4}-\d{2}-\d{2}T/.test(l)) { dateCourante = l; continue; }
      // `git log` liste les chemins relatifs au dépôt ; on les ramène à apps/web.
      const rel = l.replace(/^apps\/web\//, '');
      if (dateCourante && !dates.has(rel)) dates.set(rel, dateCourante);   // 1er vu = le plus récent
    }
    return dates;
  } catch {
    return new Map();
  }
}

function lastmodPour(dates, urlTexte) {
  if (!dates.size) return undefined;
  let chemin;
  try { chemin = decodeURI(new URL(urlTexte).pathname); } catch { return undefined; }
  chemin = chemin.replace(/\/+$/, '') || '/';
  const candidats = [];
  if (chemin === '/') candidats.push('src/pages/index.astro');
  else {
    candidats.push(`src/pages${chemin}.astro`, `src/pages${chemin}/index.astro`);
    const m = chemin.match(/^(\/(?:en|ar))?\/blog\/([^/]+)$/);
    if (m) candidats.push(`src/content/blog/${m[2]}.md`, `src/pages${m[1] || ''}/blog/[...slug].astro`);
    const c = chemin.match(/^(\/(?:en|ar))?\/installation-solaire-[^/]+$/);
    if (c) candidats.push(`src/pages${c[1] || ''}/installation-solaire-[city].astro`);
  }
  for (const f of candidats) if (dates.has(f)) return dates.get(f);
  return undefined;
}
const DATES_SITEMAP = datesDeDernierCommit();

/**
 * Redirection canonique workers.dev → taqinor.ma.
 *
 * L'adaptateur Cloudflare génère dist/server/{entry.mjs,wrangler.json} à
 * chaque build ; ce hook copie notre wrapper committé (apps/web/worker/) à
 * côté, pointe le wrangler.json généré vers lui, et active run_worker_first
 * sur les routes HTML (les dossiers d'assets lourds restent servis
 * directement par la couche assets, sans invocation Worker). Vivre dans le
 * build Astro (et non dans un script npm séparé) garantit que le patch
 * s'applique quelle que soit la commande lancée par Workers Builds.
 */
const workersDevRedirect = () => ({
  name: 'taqinor:workers-dev-redirect',
  hooks: {
    'astro:build:done': async () => {
      const serverDir = new URL('./dist/server/', import.meta.url);
      const wranglerUrl = new URL('wrangler.json', serverDir);

      // L'ordre des hooks build:done entre intégrations et adaptateur n'est
      // pas contractuel : on attend (brièvement) le wrangler.json généré.
      let cfg = null;
      for (let i = 0; i < 40; i++) {
        try {
          cfg = JSON.parse(await readFile(wranglerUrl, 'utf-8'));
          break;
        } catch {
          await new Promise((r) => setTimeout(r, 250));
        }
      }
      if (!cfg) throw new Error('workers-dev-redirect: dist/server/wrangler.json introuvable après le build');

      await copyFile(new URL('./worker/canonical.mjs', import.meta.url), new URL('canonical.mjs', serverDir));
      await copyFile(new URL('./worker/redirects.mjs', import.meta.url), new URL('redirects.mjs', serverDir));
      await copyFile(new URL('./worker/cache.mjs', import.meta.url), new URL('cache.mjs', serverDir));
      await copyFile(new URL('./worker/headers.mjs', import.meta.url), new URL('headers.mjs', serverDir));
      await copyFile(new URL('./worker/deadLetter.mjs', import.meta.url), new URL('deadLetter.mjs', serverDir)); // QJR663
      await copyFile(new URL('./worker/redirect-entry.mjs', import.meta.url), new URL('redirect-entry.mjs', serverDir));

      cfg.main = 'redirect-entry.mjs';
      cfg.assets = {
        ...cfg.assets,
        // Les pages HTML passent par le Worker (et donc par la redirection
        // 301 sur *.workers.dev) ; les médias restent asset-first (gratuit).
        run_worker_first: ['/*', '!/_astro/*', '!/photos/*', '!/videos/*', '!/fonts/*', '!/og/*'],
      };
      await writeFile(wranglerUrl, JSON.stringify(cfg));
      console.log('[workers-dev-redirect] entrée Worker enveloppée (301 workers.dev → taqinor.ma)');
    },
  },
});

/**
 * ACAL332 — les pages /preview/toiture* (générations 1 à 3 et pro-11) restent
 * une galerie interne servie par `astro dev`, mais ne sont PAS publiées : ce
 * hook les retire du dossier client construit. Pages et scripts sources sont
 * gardés (D-ACAL-19) ; /preview/diagnostic et le sitemap sont inchangés.
 */
const previewToitureHorsBuild = () => ({
  name: 'taqinor:retirer-preview-toiture',
  hooks: {
    'astro:build:done': async ({ dir }) => {
      const retirees = await retirerPreviewToiture(dossierClient(dir));
      console.log(`[retirer-preview-toiture] retiré du build : ${retirees.join(', ') || 'rien'}`);
    },
  },
});

// https://astro.build/config
export default defineConfig({
  site: 'https://taqinor.ma',
  adapter: cloudflare(),

  // i18n — FR par défaut servi à la racine (sans préfixe), EN sous /en/, AR
  // sous /ar/ (rtl). Additif : les routes FR existantes restent inchangées ;
  // les pages EN/AR s'ajoutent au fil des incréments.
  i18n: {
    defaultLocale: 'fr',
    locales: ['fr', 'en', 'ar'],
    routing: { prefixDefaultLocale: false },
  },

  vite: {
    plugins: [tailwindcss()]
  },

  integrations: [
    sitemap({
      // Pages de travail privées (comparatifs typo/média, prévisualisations) —
      // jamais indexées. Les prévisualisations /v2 et /v3 ont été promues en
      // production puis supprimées ; /preview/* est la zone de revue privée
      // actuelle (diagnostic enrichi + schéma), exclue tant qu'elle n'est pas promue.
      // W245 — /devis/ (capture « Mon toit ») est devenue le CTA principal du
      // site : retirée de l'exclusion + noindex retiré des pages elles-mêmes.
      // L'atelier interne Meriem (/internal/), la proposition client
      // tokenisée (/proposition/) et le marquage d'appareil équipe (/equipe —
      // QJ-EQUIPE 09/09/2026, utilitaire SSR noindex) restent des tunnels
      // privés hors sitemap — jamais destinés à l'indexation.
      // /status et /confiance (NTOBS1/NTOBS10, 12/09/2026) sont des pages SSR
      // (prerender=false, contenu lu au vol depuis l'API) : aucun fichier
      // statique dans dist/, donc hors sitemap comme /equipe.
      filter: (page) => !/type-test|media-test|variants-test|craft-|\/preview\/|\/internal\/|\/proposition\/|\/embed\/|\/equipe\/?$|\/confiance\/?$|\/status(\/|$)/.test(page),
      // SEO (10/10/2026) — lastmod depuis git, voir `datesDeDernierCommit` en tête.
      serialize: (item) => {
        const d = lastmodPour(DATES_SITEMAP, item.url);
        if (d) item.lastmod = d;
        return item;
      }
    }),
    workersDevRedirect(),
    previewToitureHorsBuild()
  ]
});

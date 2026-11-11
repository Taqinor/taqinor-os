// @ts-check
import { copyFile, readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { defineConfig } from 'astro/config';
import { dossierClient, retirerPreviewToiture } from './scripts/retirer-preview-toiture.mjs';
import { maplibreWorker } from './scripts/maplibre-worker.mjs';

import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';
import { datesDuDepot, lastmodPour } from './scripts/sitemap-dates.mjs';

// WAUD85 — `<lastmod>` : vraies dates du dépôt (scripts/sitemap-dates.mjs), jamais git.
const DATES_SITEMAP = datesDuDepot();

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

/**
 * WAUD93 — aucun commentaire de développement dans le HTML public : les `<!-- … -->`
 * des gabarits (identifiants de tâche, notes internes) sont retirés des pages
 * construites. Le contenu des <script>, <style>, <textarea> et <pre> n'est pas touché.
 */
const PROTEGES = /(<script\b[\s\S]*?<\/script>|<style\b[\s\S]*?<\/style>|<textarea\b[\s\S]*?<\/textarea>|<pre\b[\s\S]*?<\/pre>)/gi;
/** @param {string} html */
const retirerCommentairesHtml = (html) =>
  html
    .split(PROTEGES)
    .map((bout, i) => (i % 2 === 1 ? bout : bout.replace(/<!--[\s\S]*?-->/g, '')))
    .join('');

const commentairesHorsBuild = () => ({
  name: 'taqinor:retirer-commentaires-html',
  hooks: {
    'astro:build:done': async ({ dir }) => {
      const racine = dossierClient(dir);
      const fichiers = (await readdir(racine, { recursive: true })).filter((f) => String(f).endsWith('.html'));
      let n = 0;
      for (const f of fichiers) {
        const chemin = join(racine, f);
        const avant = await readFile(chemin, 'utf-8');
        const apres = retirerCommentairesHtml(avant);
        if (apres !== avant) {
          await writeFile(chemin, apres);
          n++;
        }
      }
      console.log(`[retirer-commentaires-html] ${n} page(s) nettoyée(s)`);
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
    // WAUD1 — publie le worker MapLibre 6 (404 depuis WEBERR2).
    plugins: [tailwindcss(), maplibreWorker()]
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
      filter: (page) => !/type-test|media-test|variants-test|craft-|\/preview\/|\/internal\/|\/proposition\/|\/embed\/|\/equipe\/?$|\/liens\/?$|\/confiance\/?$|\/status(\/|$)/.test(page),
      // WAUD85 — lastmod pour les seules pages qui ont une vraie date.
      serialize: (item) => {
        const d = lastmodPour(DATES_SITEMAP, item.url);
        if (d) item.lastmod = d;
        return item;
      }
    }),
    workersDevRedirect(),
    previewToitureHorsBuild(),
    commentairesHorsBuild()
  ]
});

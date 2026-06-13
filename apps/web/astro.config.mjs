// @ts-check
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { defineConfig } from 'astro/config';

import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';

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

// https://astro.build/config
export default defineConfig({
  site: 'https://taqinor.ma',
  adapter: cloudflare(),

  vite: {
    plugins: [tailwindcss()]
  },

  integrations: [
    sitemap({
      // Pages de travail privées (comparatifs typo/média, prévisualisations) —
      // jamais indexées. Les prévisualisations /v2 et /v3 ont été promues en
      // production puis supprimées ; /preview/* est la zone de revue privée
      // actuelle (diagnostic enrichi + schéma), exclue tant qu'elle n'est pas promue.
      filter: (page) => !/type-test|media-test|variants-test|craft-|\/preview\//.test(page)
    }),
    workersDevRedirect()
  ]
});

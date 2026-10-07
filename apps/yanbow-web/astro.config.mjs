// @ts-check
import { existsSync } from 'node:fs';
import { copyFile, readFile, rm, writeFile } from 'node:fs/promises';
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';
import { ORIGINE_CANONIQUE } from './src/lib/site.ts';
import { sourcesCsp } from './src/lib/subprocessors.ts';
import { LOCALES_ACTIVES } from './src/i18n/config.ts';

const EN_ACTIVE = /** @type {readonly string[]} */ (LOCALES_ACTIVES).includes('en');

/**
 * Page sonde « bonjour » (YBW10) : les fichiers `src/pages/_*.astro` ne sont pas
 * routés par Astro ; on injecte donc la sonde sous `/bonjour/` tant que son
 * fichier existe. YBW61 supprime le fichier → l'injection disparaît d'elle-même.
 * La sonde porte `noindex` et n'est liée nulle part.
 */
const sondeBonjour = () => ({
  name: 'yanbow:sonde-bonjour',
  hooks: {
    /** @param {{ injectRoute: (r: { pattern: string; entrypoint: string; prerender?: boolean }) => void }} p */
    'astro:config:setup': ({ injectRoute }) => {
      if (existsSync(new URL('./src/pages/_bonjour.astro', import.meta.url))) {
        injectRoute({ pattern: '/bonjour', entrypoint: './src/pages/_bonjour.astro', prerender: true });
      }
      if (EN_ACTIVE && existsSync(new URL('./src/pages/en/_bonjour.astro', import.meta.url))) {
        injectRoute({ pattern: '/en/bonjour', entrypoint: './src/pages/en/_bonjour.astro', prerender: true });
      }
    },
  },
});

/**
 * Langues actives (YBW13) : tant que `en` n'est pas dans LOCALES_ACTIVES
 * (src/i18n/config.ts), aucune route `/en/*` n'est publiée — le dossier
 * construit `dist/client/en/` est retiré après le build.
 */
const localesActives = () => ({
  name: 'yanbow:locales-actives',
  hooks: {
    /** @param {{ dir: URL }} p */
    'astro:build:done': async ({ dir }) => {
      if (EN_ACTIVE) return;
      await rm(new URL('en/', dir), { recursive: true, force: true });
      console.log('[yanbow:locales-actives] anglais inactif : aucune route /en/ publiée');
    },
  },
});

/**
 * Enveloppe Worker (YBW11). L'adaptateur Cloudflare génère
 * dist/server/{entry.mjs,wrangler.json} ; ce hook copie le Worker committé
 * (worker/) à côté, écrit `site-config.mjs` (origine canonique de
 * src/lib/site.ts + sources CSP de src/lib/subprocessors.ts), pointe le
 * wrangler.json généré vers `redirect-entry.mjs` et fait passer TOUTES les
 * requêtes par le Worker sauf `/_astro/*` (CSS/JS hachés) — y compris
 * `/fonts`, `/brand`, `/og`, pour que la porte de lancement (YBW12) et le cache
 * immuable s'y appliquent. Vivre dans le build garantit le patch quelle que
 * soit la commande lancée par Workers Builds.
 */
const WORKER_FILES = ['canonical.mjs', 'redirects.mjs', 'cache.mjs', 'headers.mjs', 'pipeline.mjs', 'launchGate.mjs', 'redirect-entry.mjs'];

const workersDevRedirect = () => ({
  name: 'yanbow:workers-dev-redirect',
  hooks: {
    'astro:build:done': async () => {
      const serverDir = new URL('./dist/server/', import.meta.url);
      const wranglerUrl = new URL('wrangler.json', serverDir);
      let cfg = null;
      for (let i = 0; i < 40; i++) {
        try {
          cfg = JSON.parse(await readFile(wranglerUrl, 'utf-8'));
          break;
        } catch {
          await new Promise((r) => setTimeout(r, 250));
        }
      }
      if (!cfg) throw new Error('yanbow:workers-dev-redirect : dist/server/wrangler.json introuvable (aucune route serveur ?)');

      for (const f of WORKER_FILES) {
        await copyFile(new URL(`./worker/${f}`, import.meta.url), new URL(f, serverDir));
      }
      await writeFile(
        new URL('site-config.mjs', serverDir),
        `// Généré au build depuis src/lib/site.ts et src/lib/subprocessors.ts — ne pas éditer.\n` +
          `export const CANONICAL_ORIGIN = ${JSON.stringify(ORIGINE_CANONIQUE)};\n` +
          `export const CSP_SOURCES = ${JSON.stringify(sourcesCsp())};\n` +
          // YBW12 — routes juridiques déclarées complètes (rempli par YBW28 depuis legal.ts).
          `export const ROUTES_JURIDIQUES_COMPLETES = [];\n`,
      );
      cfg.main = 'redirect-entry.mjs';
      cfg.assets = { ...cfg.assets, run_worker_first: ['/*', '!/_astro/*'] };
      await writeFile(wranglerUrl, JSON.stringify(cfg));
      console.log('[yanbow:workers-dev-redirect] entrée Worker enveloppée');
    },
  },
});

// https://astro.build/config
export default defineConfig({
  // Aucun `site` : le domaine final n'est pas encore choisi (YBWM10). Tant qu'il
  // ne l'est pas, aucune URL canonique absolue n'est émise.
  adapter: cloudflare(),
  trailingSlash: 'ignore',
  build: { format: 'directory' },
  i18n: {
    defaultLocale: 'fr',
    locales: ['fr', 'en'],
    routing: { prefixDefaultLocale: false },
  },
  vite: {
    plugins: [tailwindcss()],
    // Aucun script en ligne : la CSP est `script-src 'self'` (worker/headers.mjs).
    build: { assetsInlineLimit: 0 },
  },
  integrations: [sondeBonjour(), localesActives(), workersDevRedirect()],
});

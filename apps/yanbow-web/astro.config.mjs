// @ts-check
import { existsSync } from 'node:fs';
import { defineConfig } from 'astro/config';
import cloudflare from '@astrojs/cloudflare';
import tailwindcss from '@tailwindcss/vite';

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
  },
  integrations: [sondeBonjour()],
});

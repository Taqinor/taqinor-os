/// <reference types="vitest/config" />
import { getViteConfig } from 'astro/config';

/**
 * Banc vitest (YBW13/YBW14).
 * - `getViteConfig` permet de rendre les composants `.astro` (API Container).
 * - `tests/setup.ts` installe un `fetch` global qui LÈVE sur tout appel non simulé.
 * - `tests/builtHtml.ts` lit les pages construites dans `dist/` : on teste le
 *   HTML RENDU, jamais le source par regex quand le rendu existe.
 */
export default getViteConfig(
  {
    test: {
      include: ['tests/**/*.test.ts'],
      setupFiles: ['tests/setup.ts'],
    },
  },
  // Sans astro.config.mjs : l'adaptateur Cloudflare (plugin Vite Worker) est
  // incompatible avec vitest ; le rendu de composants n'en a pas besoin.
  { configFile: false },
);

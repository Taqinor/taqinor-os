/// <reference types="vitest/config" />
import { getViteConfig } from 'astro/config';

/**
 * Banc vitest (YBW13/YBW14). `getViteConfig` permet de rendre les composants
 * `.astro` dans les tests (API Container) — on teste le HTML RENDU, jamais le
 * source par regex quand le rendu existe.
 */
export default getViteConfig(
  {
    test: {
      include: ['tests/**/*.test.ts'],
    },
  },
  // Sans astro.config.mjs : l'adaptateur Cloudflare (plugin Vite Worker) est
  // incompatible avec vitest ; le rendu de composants n'en a pas besoin.
  { configFile: false },
);

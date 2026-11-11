// ATOT34 — deux projets vitest. Les tests historiques gardent la config par
// défaut (aucun plugin) ; les tests qui RENDENT un composant `.astro` par
// `experimental_AstroContainer` (`astro/container`) ont besoin du pipeline Vite
// d'Astro (`getViteConfig`) : ils sont listés dans `TESTS_RENDU` ci-dessous.
import { defineConfig } from 'vitest/config';
import { getViteConfig } from 'astro/config';

/** Tests qui rendent un composant `.astro` (pipeline Astro, sans l'adaptateur). */
const TESTS_RENDU = ['tests/propositionChaineTotauxATOT.test.ts', 'tests/propositionMontantsRendus.test.ts'];

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: 'unit',
          // Bancs lourds de l'estimateur sous jsdom : 5 s cassent sur un runner chargé (CI #1247).
          testTimeout: 30_000,
          include: ['**/*.{test,spec}.?(c|m)[jt]s?(x)'],
          exclude: ['**/node_modules/**', '**/dist/**', ...TESTS_RENDU],
        },
      },
      getViteConfig({
        test: {
          name: 'astro-rendu',
          include: TESTS_RENDU,
        },
      }, { configFile: false }) as never,
    ],
  },
});

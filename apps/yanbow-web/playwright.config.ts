import { defineConfig, devices } from '@playwright/test';
import { CLE_E2E, SECRET_E2E, URL_FAUX_ERP } from './tests-e2e/fauxErp';

/**
 * Gardes navigateur (YBW15) sur le BUILD servi localement.
 *
 * `astro preview` exécute le vrai Worker (workerd, via l'adaptateur
 * Cloudflare) avec notre enveloppe `redirect-entry.mjs` : en-têtes de
 * sécurité, CSP, porte de lancement (fermée) — exactement ce que reçoit un
 * visiteur. Prérequis : `npm run build` (la CI l'exécute avant `test:e2e`).
 */
const PORT = 4329;

export default defineConfig({
  testDir: 'tests-e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [['list']] : [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx astro preview --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/robots.txt`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // YBW56 : le Worker relaie les demandes de rendez-vous vers le FAUX ERP
    // local (tests-e2e/fauxErp.ts) — valeurs de TEST seulement.
    env: {
      CLOUDFLARE_INCLUDE_PROCESS_ENV: 'true',
      YANBOW_RDV_URL: URL_FAUX_ERP,
      YANBOW_RDV_CLE_ID: CLE_E2E,
      YANBOW_RDV_SECRET: SECRET_E2E,
    },
  },
});

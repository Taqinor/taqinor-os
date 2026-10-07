import { defineConfig, devices } from '@playwright/test';

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
  },
});

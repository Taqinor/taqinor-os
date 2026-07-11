import { defineConfig, devices } from '@playwright/test'

// ── Taqinor OS — E2E (Playwright) ──────────────────────────────────────────
// The suite drives the REAL built app (vite preview, same-origin proxy to a
// throwaway Django + Postgres + Redis + MinIO stack — never production). See
// .github/workflows/ci.yml (job `e2e`) for how the stack is brought up in CI
// and `e2e/README.md` for running it locally.
//
// One shared, freshly-seeded database (manage.py seed_demo) backs the whole
// run, so the suite is SERIAL (workers: 1, fullyParallel: false) — that keeps
// the mutating flows (create lead, move stage, merge doublons…) deterministic
// instead of racing each other over the same rows.

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:4173'
const AUTH_FILE = 'e2e/.auth/admin.json'

export default defineConfig({
  testDir: './e2e',
  // Each spec is independent but they share one seeded DB → run them in order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  // No retries: with one shared mutable DB, a silent retry would re-run a
  // mutation against already-changed data. Specs lean on Playwright's
  // auto-waiting instead. A genuine failure should be seen, not papered over.
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI
    ? [['github'], ['list'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    // 1) Log in once through the real login UI, save the cookie jar.
    { name: 'setup', testMatch: /auth\.setup\.js/ },

    // 2) Desktop flows, pre-authenticated via the saved storage state.
    //    (login.spec.js opts back out to an empty state to test the UI cold.)
    {
      name: 'chromium',
      testIgnore: /(auth\.setup|mobile\.spec)\.js/,
      dependencies: ['setup'],
      use: { ...devices['Desktop Chrome'], storageState: AUTH_FILE },
    },

    // 3) Mobile pass at an iPhone viewport (E16). Chromium with isMobile so we
    //    don't need to install a second browser engine — the FAST smoke path.
    {
      name: 'mobile',
      testMatch: /mobile\.spec\.js/,
      dependencies: ['setup'],
      use: {
        browserName: 'chromium',
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        userAgent:
          'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) ' +
          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 ' +
          'Mobile/15E148 Safari/604.1',
        storageState: AUTH_FILE,
      },
    },

    // 4) VX68 — Safari RÉEL : le projet `mobile` ci-dessus est Chromium déguisé
    //    en iPhone (aucun moteur WebKit), donc rien de ce qui ne casse QUE sur
    //    Safari (window.open post-await de VX48, sticky, backdrop-blur…) n'y est
    //    jamais capté. Ce projet exécute le MÊME spec mobile sur WebKit réel
    //    (iPhone 13). PR-only/matrice complète — jamais dans le smoke par-merge.
    {
      name: 'mobile-safari',
      testMatch: /mobile\.spec\.js/,
      dependencies: ['setup'],
      use: {
        ...devices['iPhone 13'],
        storageState: AUTH_FILE,
      },
    },

    // 5) VX68 — Tablette (iPad gen 7 paysage, WebKit) : viewport 768-1024 jamais
    //    couvert. Le spec tablet vérifie l'absence de débordement + que les
    //    affordances tri/actions restent atteignables SANS survol (pas de hover
    //    sur écran tactile). PR-only/matrice complète.
    {
      name: 'tablet',
      testMatch: /tablet\.spec\.js/,
      dependencies: ['setup'],
      use: {
        ...devices['iPad (gen 7) landscape'],
        storageState: AUTH_FILE,
      },
    },
  ],

  // Serve the built app. E2E_PROXY makes vite preview forward /api/django to
  // Django (started separately in CI), so everything is one origin.
  webServer: {
    command: 'npm run preview -- --port 4173 --strictPort',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      E2E_PROXY: '1',
      E2E_API_TARGET: process.env.E2E_API_TARGET || 'http://127.0.0.1:8000',
    },
  },
})

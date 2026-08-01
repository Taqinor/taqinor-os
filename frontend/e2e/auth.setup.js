// Logs in once through the real login UI and saves the cookie jar. Every other
// spec reuses it (playwright.config.js storageState), so the suite logs in once
// instead of per-test — fewer logins, no rate-limit pressure, less flake.
import { test as setup, expect } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { dirname } from 'node:path'
import { uiLogin, ADMIN, AUTH_FILE } from './helpers'

setup('authenticate', async ({ page }) => {
  await mkdir(dirname(AUTH_FILE), { recursive: true })
  await uiLogin(page, ADMIN)
  // ODY3 — a successful login lands on the HOME MENU (`/apps`), the grid of the
  // apps this company has installed and this role may open. It used to be
  // `/dashboard`; that route is still perfectly valid (the « Tableau de bord »
  // app), it is simply no longer the front door. This admin sees many apps, so
  // the mono-app shortcut (exactly one visible app enters it directly) does not
  // apply here.
  await expect(page).toHaveURL(/\/apps/, { timeout: 30_000 })
  // 30s to match the URL assert above: a cold CI runner can take >15s (the
  // default) to paint — this exact flake failed a whole e2e run on 2026-07-09
  // (run 29044779596). The home menu itself fires NO blocking request (ODY2:
  // everything comes from the bootstrap + the module registry).
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible({ timeout: 30_000 })
  // La bannière d'installation PWA iOS (PwaPrompts.jsx `InstallBanner`) est un
  // encart promotionnel `position: fixed` collé en bas — PAS une partie de l'ERP
  // testé. Un utilisateur qui revient (ce que simule ce storageState partagé) l'a
  // déjà fermée une fois : on persiste ce rejet dans l'état partagé pour qu'elle
  // n'occulte pas le bas de page dans les projets iPhone (mobile / mobile-safari,
  // viewport 664 px → la bannière couvrait ~y563-652). MB6 continue de garder le
  // vrai « chrome » de l'app (en-tête collant + barre d'onglets basse), pas ce
  // promo. Miroir du forçage de thème via localStorage dans visual.spec.js.
  await page.evaluate(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await page.context().storageState({ path: AUTH_FILE })
})

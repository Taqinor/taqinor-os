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
  // The router redirects a successful login straight into the app.
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 })
  // 30s to match the URL assert above: the dashboard fires its KPI requests on
  // mount and a cold CI runner can take >15s (the default) to paint the heading
  // — this exact flake failed a whole e2e run on 2026-07-09 (run 29044779596).
  await expect(page.getByRole('heading', { name: 'Tableau de bord' })).toBeVisible({ timeout: 30_000 })
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

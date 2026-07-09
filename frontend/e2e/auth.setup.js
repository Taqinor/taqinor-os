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
  await page.context().storageState({ path: AUTH_FILE })
})

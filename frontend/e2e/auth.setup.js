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
  await expect(page.getByRole('heading', { name: 'Tableau de bord' })).toBeVisible()
  await page.context().storageState({ path: AUTH_FILE })
})

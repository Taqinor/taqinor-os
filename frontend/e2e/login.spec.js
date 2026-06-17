// E2 — Login is the app entry point: valid login lands in the app; invalid
// login is rejected. Runs COLD (no shared auth state) to exercise the real UI.
import { test, expect } from '@playwright/test'
import { uiLogin, ADMIN } from './helpers'

test.use({ storageState: { cookies: [], origins: [] } })

test('E2: invalid login is rejected', async ({ page }) => {
  await uiLogin(page, { username: ADMIN.username, password: 'definitely-wrong' })
  await expect(page.getByText(/Identifiants incorrects/)).toBeVisible()
  // Stayed on the login screen — never reached the app.
  await expect(page).not.toHaveURL(/\/dashboard/)
})

test('E2: valid login lands in the app', async ({ page }) => {
  await uiLogin(page, ADMIN)
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByRole('heading', { name: 'Tableau de bord' })).toBeVisible()
})

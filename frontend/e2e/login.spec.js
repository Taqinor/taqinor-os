// E2 — Login is the app entry point: valid login lands in the app; invalid
// login is rejected. Runs COLD (no shared auth state) to exercise the real UI.
import { test, expect } from '@playwright/test'
import { uiLogin, ADMIN } from './helpers'

test.use({ storageState: { cookies: [], origins: [] } })

test('E2: invalid login is rejected', async ({ page }) => {
  await uiLogin(page, { username: ADMIN.username, password: 'definitely-wrong' })
  // The login error box appears; the exact text is the backend `detail`, so
  // assert on the box, not a specific wording.
  // VX45 — the box no longer opens with a raw ⚠️ emoji: it is a lucide
  // component (`<AlertCircle>` in Login.jsx → `svg.lucide-circle-alert`), the
  // product rule pinned in /ui ("toujours un composant lucide, jamais un emoji
  // brut"). We target the box through that icon and assert its message slot is
  // non-empty — same proof as before (the error box is shown, carrying the
  // server's message), independent of the wording.
  const errorMessage = page.locator('div:has(> svg.lucide-circle-alert) > span')
  await expect(errorMessage).toBeVisible()
  await expect(errorMessage).not.toBeEmpty()
  // Stayed on the login screen — never reached the app (ODY3: the app now
  // opens on the home menu `/apps`, not `/dashboard`).
  await expect(page).toHaveURL(/\/login/)
  await expect(page).not.toHaveURL(/\/apps/)
})

test('E2: valid login lands in the app', async ({ page }) => {
  await uiLogin(page, ADMIN)
  // ODY3 — the front door is the home menu: the grid of MY apps.
  await expect(page).toHaveURL(/\/apps/)
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible()
})

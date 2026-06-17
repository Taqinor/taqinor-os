// E16 — Mobile pass (iPhone viewport, see the `mobile` project in the config):
// no horizontal overflow on key pages, and the full nav menu is reachable
// (verifies the C1 cut-off-menu fix).
import { test, expect } from '@playwright/test'

const PAGES = ['/dashboard', '/crm/leads', '/ventes/factures', '/parametres']

test('E16: no horizontal overflow on key pages', async ({ page }) => {
  for (const path of PAGES) {
    await page.goto(path)
    await expect(page.locator('.header-title')).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1)
  }
})

test('E16: the full navigation menu is reachable on mobile', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.locator('.header-title')).toBeVisible()

  // Open the drawer (hamburger only shows at mobile widths).
  await page.getByRole('button', { name: 'Ouvrir le menu' }).click()

  // The last items (admin-only, at the very bottom) must be reachable, i.e. the
  // menu scrolls inside the safe area instead of clipping them.
  const settings = page.getByRole('link', { name: 'Paramètres' })
  await settings.scrollIntoViewIfNeeded()
  await expect(settings).toBeVisible()

  const logout = page.getByRole('button', { name: 'Déconnexion' })
  await logout.scrollIntoViewIfNeeded()
  await expect(logout).toBeVisible()
})

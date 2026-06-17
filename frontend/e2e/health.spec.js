// E15 — Cross-cutting health: no broken images and no uncaught console errors
// (page errors) on the key pages.
import { test, expect } from '@playwright/test'

const PAGES = [
  '/dashboard',
  '/crm/leads',
  '/ventes/devis',
  '/ventes/factures',
  '/stock',
  '/admin/users',
  '/parametres',
]

test('E15: key pages have no broken images and no uncaught errors', async ({ page }) => {
  for (const path of PAGES) {
    const pageErrors = []
    const onError = (err) => pageErrors.push(`${err.message}`)
    page.on('pageerror', onError)

    await page.goto(path)
    // Every authenticated page renders the app shell header title.
    await expect(page.locator('.header-title')).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})

    // Broken image = loaded but zero intrinsic size.
    const broken = await page.evaluate(() =>
      Array.from(document.images)
        .filter((img) => img.complete && img.naturalWidth === 0)
        .map((img) => img.currentSrc || img.src),
    )
    expect(broken, `broken images on ${path}`).toEqual([])
    expect(pageErrors, `uncaught console errors on ${path}`).toEqual([])

    page.off('pageerror', onError)
  }
})

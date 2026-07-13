// VX180 — Le seuil DOCUMENTÉ du repli DataTable/ListShell est 768px, mais le
// code utilisait l'utilitaire Tailwind `sm:` par défaut (640px) : entre 640
// et 767px (petite tablette portrait, Android paysage, fenêtre
// redimensionnée), la table DESKTOP s'affichait à la place des cartes que le
// code croyait garantir. `jsdom` (vitest) n'applique AUCUNE media query — il
// ne peut structurellement pas détecter ce genre de régression, d'où ce spec
// Playwright RÉEL à un viewport de 700px (entre 640 et 768) : les 42 pages
// `ListShell` héritent de ce composant, donc une seule page riche (factures)
// suffit à couvrir le composant partagé.
import { test, expect } from '@playwright/test'

test.describe('VX180 — 700px (entre 640 et 768, la bande jamais couverte avant)', () => {
  test.use({ viewport: { width: 700, height: 900 } })

  test('à 700px réels, les cartes sont visibles et la table desktop ne l\'est pas', async ({ page }) => {
    await page.goto('/ventes/factures')
    await expect(page.getByRole('heading', { name: 'Factures' })).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})

    const cards = page.locator('[data-dt-cards]')
    const table = page.locator('[data-dt-table]')
    await expect(cards).toBeVisible()
    await expect(table).toBeHidden()
  })
})

test.describe('VX180 — 1024px (desktop, non régressé)', () => {
  test.use({ viewport: { width: 1024, height: 900 } })

  test('à 1024px réels, c\'est l\'inverse — table visible, cartes masquées', async ({ page }) => {
    await page.goto('/ventes/factures')
    await expect(page.getByRole('heading', { name: 'Factures' })).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})

    const cards = page.locator('[data-dt-cards]')
    const table = page.locator('[data-dt-table]')
    await expect(table).toBeVisible()
    await expect(cards).toBeHidden()
  })
})

// VX180 — Le seuil DOCUMENTÉ du repli DataTable/ListShell est 768px, mais le
// code utilisait l'utilitaire Tailwind `sm:` par défaut (640px) : entre 640
// et 767px (petite tablette portrait, Android paysage, fenêtre
// redimensionnée), la table DESKTOP s'affichait à la place des cartes que le
// code croyait garantir. `jsdom` (vitest) n'applique AUCUNE media query — il
// ne peut structurellement pas détecter ce genre de régression, d'où ce spec
// Playwright RÉEL à un viewport de 700px (entre 640 et 768) : toutes les pages
// bâties sur `DataTable`/`ListShell` héritent de ce composant, donc une seule
// page suffit à couvrir le composant partagé.
//
// PAGE TÉMOIN — la liste CLIENTS (`/crm`, ClientList.jsx), et surtout PAS la
// liste des factures utilisée à l'écriture de ce spec : `FactureList.jsx` passe
// `renderRow` à DataTable, ce qui DÉSACTIVE le repli en cartes (ARC49 —
// `!(customRow || hideMobileCards || groupModeActive)`, DataTable.jsx). La page
// factures ne peut donc structurellement pas rendre `[data-dt-cards]` : elle ne
// prouvait rien du seuil. La liste clients consomme DataTable nu (ni
// `renderRow`, ni `hideMobileCards`, ni `groupBy`) — c'est exactement le repli
// que VX180 verrouille, sur une page seedée (seed_demo crée des clients).
import { test, expect } from '@playwright/test'

test.describe('VX180 — 700px (entre 640 et 768, la bande jamais couverte avant)', () => {
  test.use({ viewport: { width: 700, height: 900 } })

  test('à 700px réels, les cartes sont visibles et la table desktop ne l\'est pas', async ({ page }) => {
    await page.goto('/crm')
    // Le titre porte le compteur (« Clients 5 ») : préfixe, jamais nom exact.
    await expect(page.getByRole('heading', { name: /^Clients/ }).first()).toBeVisible()
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
    await page.goto('/crm')
    await expect(page.getByRole('heading', { name: /^Clients/ }).first()).toBeVisible()
    await page.waitForLoadState('networkidle').catch(() => {})

    const cards = page.locator('[data-dt-cards]')
    const table = page.locator('[data-dt-table]')
    await expect(table).toBeVisible()
    await expect(cards).toBeHidden()
  })
})

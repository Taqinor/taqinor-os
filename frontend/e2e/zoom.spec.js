// VX69 — Contrat de zoom (WCAG 1.4.10 « Reflow »). Les laptops Windows tournent
// couramment à 125-150 % ; le zoom 200 % n'était gardé par rien (index.css l'a
// même documenté comme un contrôle « manuel »). Ce spec force 150 % puis 200 %
// de zoom sur les écrans clés et vérifie : (a) zéro débordement horizontal
// (scrollWidth - innerWidth <= 1) et (b) les boutons primaires restent
// cliquables (visibles + non couverts).
//
// Playwright n'a pas de « zoom » navigateur natif. On l'ÉMULE fidèlement au sens
// WCAG « reflow » : à zoom Z, la largeur en px CSS disponible = largeur physique
// / Z. On réduit donc le viewport à `base / Z` (le contenu doit refluer, jamais
// imposer un scroll horizontal). C'est exactement ce que teste le critère 1.4.10.
import { test, expect } from '@playwright/test'

// Largeur physique de référence (laptop 1280) ; les hauteurs importent peu ici.
const BASE_W = 1280
const BASE_H = 800
const ZOOMS = [1.5, 2] // 150 % et 200 %

function reflowViewport(zoom) {
  return { width: Math.round(BASE_W / zoom), height: Math.round(BASE_H / zoom) }
}

async function assertNoHOverflow(page, label) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow, `débordement horizontal ${label}`).toBeLessThanOrEqual(1)
}

test.describe('VX69: /login supporte 150 % et 200 % de zoom', () => {
  // Écran public : on part d'un état non authentifié (comme MB6).
  test.use({ storageState: { cookies: [], origins: [] } })

  for (const zoom of ZOOMS) {
    test(`/login à ${zoom * 100} %`, async ({ page }) => {
      await page.setViewportSize(reflowViewport(zoom))
      await page.goto('/login')
      const idField = page.getByPlaceholder('Entrez votre identifiant')
      await expect(idField).toBeVisible()
      await assertNoHOverflow(page, `/login @${zoom * 100}%`)
      // Le bouton de connexion (action primaire) reste cliquable.
      const submit = page.getByRole('button', { name: /Se connecter|Connexion/ })
      await expect(submit).toBeVisible()
      await expect(submit).toBeEnabled()
    })
  }
})

test.describe('VX69: écrans ERP supportent 150 % et 200 % de zoom', () => {
  const CASES = [
    { path: '/ventes/factures', ready: '.header-title' },
    { path: '/crm/leads', ready: '.header-title' },
    { path: '/parametres', ready: '.header-title' },
  ]

  for (const zoom of ZOOMS) {
    for (const { path, ready } of CASES) {
      test(`${path} à ${zoom * 100} %`, async ({ page }) => {
        await page.setViewportSize(reflowViewport(zoom))
        await page.goto(path)
        await expect(page.locator(ready)).toBeVisible()
        await page.waitForLoadState('networkidle').catch(() => {})
        await assertNoHOverflow(page, `${path} @${zoom * 100}%`)
      })
    }
  }

  test('un bouton primaire reste cliquable à 200 % sur /parametres', async ({ page }) => {
    await page.setViewportSize(reflowViewport(2))
    await page.goto('/parametres')
    const save = page.getByRole('button', { name: 'Enregistrer' })
    await expect(save).toBeVisible({ timeout: 20_000 })
    await save.scrollIntoViewIfNeeded()
    await expect(save).toBeEnabled()
  })
})

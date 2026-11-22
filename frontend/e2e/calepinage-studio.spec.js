// ACAL402 — disposition « studio » de l'atelier de calepinage. Coque (maquettes 22/11) : l'atelier
// est PLEIN ÉCRAN (ni barre latérale ni en-tête de l'ERP) : bandeau 56 px, rail 96 px (72 px en
// pictogrammes sous 1 280 px, maquette Tablette), la carte au centre, le panneau d'étape à droite
// (360 px) dont le corps défile seul. Hooks : `#rp9-studio-scene` / `#rp9-studio-inspecteur`
// (contrat DOM `rp9-*`), `cal-coque`, `cal-barre-projet`, `cal-rail-etapes`.
import { test, expect } from '@playwright/test'
import { uniq, gotoLeads, createLead } from './helpers'

async function ouvrirAtelier(page) {
  await gotoLeads(page)
  const nomLead = await createLead(page, {
    nom: uniq('ACAL402 Lead'), facture: 900, ville: 'Casablanca',
  })
  await page.goto('/calepinage/nouveau')
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('ACAL402 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.locator('#rp9-studio-scene')).toBeAttached()
}

test('ACAL402: à 1 440 × 900 la page ne défile plus, carte et bouton d’enregistrement restent visibles', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await ouvrirAtelier(page)

  const hauteurs = await page.evaluate(() => ({
    document: document.scrollingElement.scrollHeight, fenetre: window.innerHeight,
  }))
  expect(hauteurs.document).toBeLessThanOrEqual(hauteurs.fenetre + 1)
  await expect(page.locator('#rp9-map')).toBeVisible()
  await expect(page.getByTestId('cal-enregistrer-calepinage')).toBeVisible()
  // Coque : aucune mise en page de l'ERP ; bandeau, rail et panneau aux mesures de la maquette Main.
  await expect(page.locator('.layout')).toHaveCount(0)
  const barre = await page.getByTestId('cal-barre-projet').boundingBox()
  expect(Math.round(barre.height)).toBe(56)
  const rail = await page.getByTestId('cal-rail-etapes').boundingBox()
  expect(Math.round(rail.width)).toBe(96)
  const panneau = await page.locator('#rp9-studio-inspecteur').boundingBox()
  expect(Math.round(panneau.width)).toBe(360)
  await expect(page.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')

  // L'inspecteur défile seul : la carte garde sa position pendant le défilement.
  const avant = await page.locator('#rp9-map').boundingBox()
  await page.locator('#rp9-studio-inspecteur .cal-panneau-etape-corps').evaluate((el) => { el.scrollTop = el.scrollHeight })
  const apres = await page.locator('#rp9-map').boundingBox()
  expect(Math.round(apres.y)).toBe(Math.round(avant.y))
})

test('Coque : à 1 180 × 820 le rail se replie en pictogrammes, la carte reste entre le rail et le panneau', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 820 })
  await ouvrirAtelier(page)

  const rail = await page.getByTestId('cal-rail-etapes').boundingBox()
  expect(Math.round(rail.width)).toBe(72)
  const scene = await page.locator('#rp9-studio-scene').boundingBox()
  const inspecteur = await page.locator('#rp9-studio-inspecteur').boundingBox()
  expect(scene.x).toBeGreaterThanOrEqual(rail.x + rail.width - 1)
  expect(inspecteur.x).toBeGreaterThanOrEqual(scene.x + scene.width - 1)
})

test('Coque : une étape pleine (Résultats) masque la carte sans la démonter, et la carte revient', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await ouvrirAtelier(page)
  await page.getByTestId('cal-etape-resultats').click()
  await expect(page.getByTestId('cal-coque')).toHaveAttribute('data-cadre', 'plein')
  await expect(page.locator('#rp9-map')).toBeAttached()
  await expect(page.locator('#rp9-studio-scene')).toBeHidden()
  await expect(page.locator('#rp9-studio-inspecteur')).toBeHidden()
  await page.getByTestId('cal-etape-toit').click()
  await expect(page.locator('#rp9-map')).toBeVisible()
  const carte = await page.locator('#rp9-map canvas').first().boundingBox()
  expect(carte?.width ?? 0).toBeGreaterThan(400) // la carte s'est recalée sur sa boîte (resize)
})

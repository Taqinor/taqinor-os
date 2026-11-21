// ACAL402 — disposition « studio » de l'atelier de calepinage à partir de 1 280 px :
// la carte à gauche (collée, pleine hauteur), l'inspecteur à droite qui défile seul ;
// sous 1 280 px la page reste empilée. Hooks : `#rp9-studio-scene` / `#rp9-studio-inspecteur`
// (contrat DOM `rp9-*`, jamais un texte traduit). Mutant : retirer la classe `rp9-studio`
// ⇒ la page redevient une colonne et le premier test échoue.
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

  // L'inspecteur défile seul : la carte garde sa position pendant le défilement.
  const avant = await page.locator('#rp9-map').boundingBox()
  await page.locator('#rp9-studio-inspecteur').evaluate((el) => { el.scrollTop = el.scrollHeight })
  const apres = await page.locator('#rp9-map').boundingBox()
  expect(Math.round(apres.y)).toBe(Math.round(avant.y))
})

test('ACAL402: à 1 024 × 768 la page reste empilée (carte puis inspecteur, aucune colonne)', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await ouvrirAtelier(page)

  const scene = await page.locator('#rp9-studio-scene').boundingBox()
  const inspecteur = await page.locator('#rp9-studio-inspecteur').boundingBox()
  expect(inspecteur.y).toBeGreaterThanOrEqual(scene.y + scene.height - 1)
})

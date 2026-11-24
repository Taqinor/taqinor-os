// ACAL402 — disposition « studio » de l'atelier de calepinage. Coque v2 (ACAL1801, maquettes du 23/11) : l'atelier
// est PLEIN ÉCRAN (ni barre latérale ni en-tête de l'ERP) ; au bureau la CARTE couvre toute la fenêtre et le bandeau
// (16,16 · 56 px), le rail (76 px ; 68 px en pictogrammes sur tablette) et le panneau d'étape (384 px ; 344 px sur
// tablette, à 16 px du bord) flottent dessus ; le corps du panneau défile seul ; au téléphone (< 640 px) seulement le
// panneau devient le TIROIR du bas (ACAL1835, maquette v2 Tablette). Hooks : `#rp9-studio-scene` / `#rp9-studio-inspecteur`
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
  expect([Math.round(barre.x), Math.round(barre.y), Math.round(barre.width)]).toEqual([16, 16, 1408])
  const rail = await page.getByTestId('cal-rail-etapes').boundingBox()
  expect(Math.round(rail.width)).toBe(76)
  const panneau = await page.locator('#rp9-studio-inspecteur').boundingBox()
  expect(Math.round(panneau.width)).toBe(384)
  expect([Math.round(panneau.x), Math.round(panneau.y)]).toEqual([1040, 88])
  // ACAL1801 — la carte est le décor : 1 440 × 900, sous les pièces.
  const decor = await page.locator('#rp9-map').boundingBox()
  expect([Math.round(decor.width), Math.round(decor.height)]).toEqual([1440, 900])
  await expect(page.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')

  // L'inspecteur défile seul : la carte garde sa position pendant le défilement.
  const avant = await page.locator('#rp9-map').boundingBox()
  await page.locator('#rp9-studio-inspecteur .cal-panneau-etape-corps').evaluate((el) => { el.scrollTop = el.scrollHeight })
  const apres = await page.locator('#rp9-map').boundingBox()
  expect(Math.round(apres.y)).toBe(Math.round(avant.y))
})

// ACAL1835 — maquette v2 Tablette : plus de tiroir sur tablette ; la coque flottante du bureau à ses mesures.
test('Coque : à 1 180 × 820 (tablette) le panneau d’étape flotte à droite, la carte reste pleine hauteur', async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 820 })
  await ouvrirAtelier(page)
  await page.getByTestId('cal-etape-panneaux').click()

  const barre = await page.getByTestId('cal-barre-projet').boundingBox()
  expect([barre.x, barre.y, barre.width, barre.height].map(Math.round)).toEqual([16, 16, 1148, 60])
  const rail = await page.getByTestId('cal-rail-etapes').boundingBox()
  expect([rail.x, rail.y, rail.width].map(Math.round)).toEqual([16, 92, 68])
  const panneau = page.locator('#rp9-studio-inspecteur')
  await expect(panneau).not.toHaveAttribute('data-tiroir', '1')
  await expect(page.getByRole('button', { name: 'Agrandir ou réduire le panneau du bas' })).toHaveCount(0)
  const boite = await panneau.boundingBox()
  expect([boite.x, boite.y, boite.width, boite.height].map(Math.round)).toEqual([820, 92, 344, 712])
  // La carte est le décor : toute la fenêtre, sous les pièces.
  const decor = await page.locator('#rp9-map').boundingBox()
  expect([decor.width, decor.height].map(Math.round)).toEqual([1180, 820])
  // K6 — au plus 19 contrôles visibles dans le panneau de l'étape Panneaux.
  const controles = await panneau.evaluate((el) => [...el.querySelectorAll('button, a[href], input, select, textarea, [role=tab]')]
    .filter((c) => { const r = c.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(c).visibility !== 'hidden' }).length)
  expect(controles).toBeLessThanOrEqual(19)
})

test('Coque : à 390 × 844 (téléphone) l’atelier tient dans l’écran, rail en barre du bas, aucun défilement horizontal', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await ouvrirAtelier(page)
  const largeur = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(largeur).toBeLessThanOrEqual(390)
  const rail = await page.getByTestId('cal-rail-etapes').boundingBox()
  expect(Math.round(rail.y + rail.height)).toBe(844)
  for (const b of await page.getByTestId('cal-rail-etapes').getByRole('button').all()) {
    const r = await b.boundingBox()
    expect(Math.min(r.width, r.height), 'cible ≥ 44 px').toBeGreaterThanOrEqual(44)
  }
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

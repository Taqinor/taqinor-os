// ACAL521 — le relevé de l'horizon AU TÉLÉPHONE, rejoué sous WebKit avec des capteurs SIMULÉS.
// Playwright ne fournit aucun capteur d'orientation : un script d'initialisation expose
// `DeviceOrientationEvent.requestPermission` et émet des `deviceorientation` (cap iOS
// `webkitCompassHeading`, téléphone debout : beta 90, gamma 0 → hauteur 0°). La boussole réelle
// d'un appareil reste à essayer sur un vrai iPhone (hors CI). Aucune attente à durée fixe.
import { test, expect, devices } from '@playwright/test'
import { gotoLeads, createLead, uniq, ouvertureGuideeCalepinage } from './helpers'

// Appareil WebKit (iPhone 13) pour TOUT le fichier : lance WebKit même sous le projet `chromium`
// (même mécanisme que `calepinage-atelier-telephone.spec.js`, ACAL482).
test.use({ ...devices['iPhone 13'] })

const API = '/api/django/calepinage'
const CAPS = Array.from({ length: 12 }, (_, i) => i * 30) // 0 à 330°, pas de 30°

/** Capteurs simulés : `permission` = réponse de `requestPermission` ; `window.__viser(cap)` émet un cap. */
const simulerCapteurs = (page, permission) => page.addInitScript((reponse) => {
  window.DeviceOrientationEvent = class extends Event {
    static requestPermission() { return Promise.resolve(reponse) }
  }
  window.__viser = (cap) => {
    const evt = new Event('deviceorientation')
    Object.assign(evt, { webkitCompassHeading: cap, beta: 90, gamma: 0, alpha: 0 })
    window.dispatchEvent(evt)
  }
}, permission)

/** Un lead, un calepinage créé comme dans `calepinage-onglets.spec.js`, l'onglet `horizon` ouvert. */
async function ouvrirHorizon(page) {
  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('ACAL521 Lead'), facture: 700, ville: 'Casablanca' })
  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('ACAL521 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  const id = /\/calepinage\/(\d+)/.exec(new URL(page.url()).pathname)[1]
  await page.goto(`/calepinage/${id}?onglet=horizon`)
  await page.getByTestId(`cal-onglet-${ouvertureGuideeCalepinage('horizon')}`).click()
  await expect(page.getByTestId('cal-horizon')).toBeVisible()
  return id
}

const debordement = (page) => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)

test('ACAL521 : le navigateur joué est bien WebKit', async ({ browserName }) => {
  expect(browserName, 'la surcharge d’appareil n’a pas lancé WebKit').toBe('webkit')
})

test('ACAL521 : douze visées simulées donnent un profil enregistré avec son relevé', async ({ page }) => {
  await simulerCapteurs(page, 'granted')
  const id = await ouvrirHorizon(page)

  await page.getByText('Relever au téléphone').click()
  await page.getByTestId('horizon-tel-demarrer').click()
  await page.getByTestId('horizon-tel-precision').fill('10')
  const viser = page.getByTestId('horizon-tel-viser')
  for (const cap of CAPS) {
    await page.evaluate((c) => window.__viser(c), cap)
    await expect(viser, `visée ${cap}° : bouton inactif`).toBeEnabled()
    await viser.click()
  }
  await expect(page.getByTestId('cal-horizon-points').locator('li')).toHaveCount(CAPS.length)
  expect(await debordement(page), 'défilement horizontal (px)').toBeLessThanOrEqual(0)

  await page.getByRole('button', { name: 'Enregistrer le profil' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Profil d’horizon enregistré' })).toBeVisible()

  const detail = await page.request.get(`${API}/calepinages/${id}/`)
  expect(detail.ok(), `GET calepinage (${detail.status()})`).toBeTruthy()
  const profil = (await detail.json())?.roof_layout?.horizonProfile
  expect(profil?.points, 'points enregistrés').toHaveLength(CAPS.length)
  expect(profil.source).toBe('saisie')
  expect(profil.releve).toMatchObject({ mode: 'telephone', precisionDeg: 10 })
})

test('ACAL521 : une permission refusée bascule en saisie manuelle', async ({ page }) => {
  await simulerCapteurs(page, 'denied')
  await ouvrirHorizon(page)

  await page.getByText('Relever au téléphone').click()
  await page.getByTestId('horizon-tel-demarrer').click()
  await expect(page.getByRole('status').filter({ hasText: /saisissez l.azimut et la hauteur à la main/ })).toBeVisible()

  // L'ajout manuel reste utilisable.
  await page.getByTestId('cal-horizon-champ-azimut').locator('input').fill('45')
  await page.getByTestId('cal-horizon-champ-hauteur').locator('input').fill('8')
  await page.getByRole('button', { name: 'Ajouter le point' }).click()
  await expect(page.getByTestId('cal-horizon-points').locator('li')).toContainText('45')
  expect(await debordement(page), 'défilement horizontal (px)').toBeLessThanOrEqual(0)
})

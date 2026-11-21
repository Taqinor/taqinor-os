// ACAL423 — l'atelier de calepinage (`.rp9-host`) doit rester utilisable au téléphone
// (390 × 844) : aucun défilement horizontal de la page, aucune cible tactile (bouton ou
// puce visible) sous 44 px de haut. Même méthode que `mobile.spec.js` (VNT81) :
// `scrollWidth - innerWidth`. La carte peut être absente (ERR121, aucune clé MapTiler) :
// `#rp9-map` reste un conteneur, la mesure porte sur le DOM du builder.
import { test, expect, devices } from '@playwright/test'
import { gotoLeads, createLead, uniq } from './helpers'

// ACAL482 — appareil WebKit réel (iPhone 13) pour TOUT le fichier : la surcharge `test.use`
// fait lancer WebKit même sous le projet `chromium` (qui garde son `storageState`).
test.use({ ...devices['iPhone 13'], viewport: { width: 390, height: 844 } })

// Rend l'écart de largeur ET les éléments qui dépassent (diagnostic lisible dans l'échec).
const sansDebordement = (page) =>
  page.evaluate(() => {
    const de = document.documentElement
    const ecart = de.scrollWidth - window.innerWidth
    if (ecart > 0) {
      const noms = [...document.querySelectorAll('body *')]
        .filter((n) => n.getBoundingClientRect().right > window.innerWidth + 0.5)
        .slice(0, 6).map((n) => `${n.tagName}#${n.id}.${String(n.className).slice(0, 50)} r=${n.getBoundingClientRect().right}`)
      console.log(`DEBORDEMENT sw=${de.scrollWidth} iw=${window.innerWidth} bodysw=${document.body.scrollWidth} ${noms.join(' | ')}`)
    }
    return ecart
  })

test('ACAL482 : le navigateur joué est bien WebKit', async ({ browserName }) => {
  expect(browserName, 'la surcharge d’appareil n’a pas lancé WebKit').toBe('webkit')
})

test.beforeEach(({ page }) => { page.on('console', (m) => { if (m.text().startsWith('DEBORDEMENT')) console.log(m.text()) }) })

test('ACAL482 : liste, fiche et onglet releve à 390 px — sans défilement horizontal', async ({ page }) => {
  const erreurs = []
  page.on('pageerror', (err) => erreurs.push(err))
  await gotoLeads(page)
  const nomLead = await createLead(page, { nom: uniq('Tel ACAL482'), facture: 700, ville: 'Casablanca' })

  await page.goto('/calepinage')
  await expect(page.getByRole('heading', { name: 'Calepinages' })).toBeVisible()
  expect(await sansDebordement(page), 'liste : défilement horizontal (px)').toBeLessThanOrEqual(0)

  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible()
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
  await page.locator('#cal-nouveau-nom').fill(uniq('Tel ACAL482 Toiture'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible()
  expect(await sansDebordement(page), 'fiche : défilement horizontal (px)').toBeLessThanOrEqual(0)

  const url = new URL(page.url())
  url.searchParams.set('onglet', 'releve')
  await page.goto(url.toString())
  await page.getByTestId('cal-onglet-releve').click()
  const panneau = page.getByTestId('cal-onglet-panneau')
  await expect(panneau).toBeVisible()
  expect(await sansDebordement(page), 'releve : défilement horizontal (px)').toBeLessThanOrEqual(0)
  const larges = await panneau.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .filter((n) => n.getBoundingClientRect().right > window.innerWidth + 1)
      .map((n) => `${n.tagName}.${n.className}`.slice(0, 80)))
  expect(larges, 'contrôles du panneau dépassant 390 px').toEqual([])
  expect(erreurs, 'erreurs de page').toEqual([])
})

test('ACAL423 : atelier à 390 px — pas de défilement horizontal, cibles ≥ 44 px', async ({ page }) => {
  await gotoLeads(page)
  const name = await createLead(page, { nom: uniq('Atelier tel ACAL423'), facture: 650, ville: 'Casablanca' })
  const res = await page.request.get(`/api/django/crm/leads/?search=${encodeURIComponent(name)}&page_size=1`)
  expect(res.ok(), `GET /crm/leads/?search= (${res.status()})`).toBeTruthy()
  const body = await res.json()
  const rows = Array.isArray(body) ? body : body.results
  expect(rows?.length, `lead "${name}" introuvable via l'API`).toBeGreaterThan(0)

  await page.goto(`/devis-design/${rows[0].id}`)
  await expect(page.locator('.rp9-host').first()).toBeVisible({ timeout: 20_000 })

  const debordement = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(debordement, 'défilement horizontal de la page (px)').toBeLessThanOrEqual(0)

  const petites = await page.evaluate(() => {
    const out = []
    for (const el of document.querySelectorAll('.rp9-host button, .rp9-host .rp9-chip')) {
      const r = el.getBoundingClientRect()
      if (r.width === 0 || r.height === 0) continue // non visible
      if (r.height < 44) out.push(`${el.id || el.className || el.tagName} (${Math.round(r.height)} px)`)
    }
    return out
  })
  expect(petites, 'boutons et puces de moins de 44 px de haut').toEqual([])
})

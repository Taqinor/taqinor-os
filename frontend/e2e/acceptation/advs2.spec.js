// ADVS10 — remise demandée au devis automatique commercial et agricole : par la route et par la fiche lead C&I (« Remise %… »).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'
import { API, T, marque, catalogueCi, pompesTarifees, retablirCatalogueApresTout, leadCi, devisAuto, devisRelu } from './_ci.js'

const etape = groupe('ADVS', ['ADVS10'])
fermerDjangoApresTout()
retablirCatalogueApresTout()
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const idDe = (x) => x.id ?? x.devis?.id ?? x.devis_id

etape('PA3-01.remise_auto_ci', ['ADVS10'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const sans = await devisRelu(r, idDe(await devisAuto(r, (await leadCi(r, `ADVS10 ${m} Sans`)).id)))
  expect(Number(sans.remise_globale), 'sans remise : devis inchangé').toBe(0)
  const avec = await devisRelu(r, idDe(await devisAuto(r, (await leadCi(r, `ADVS10 ${m} Avec`)).id, { remise_globale: '10' })))
  expect(Number(avec.remise_globale), 'persistance : remise 10,00').toBe(10)
  // Totaux remisés par le noyau : même composition, même prix, 10 % de moins.
  expect(Number(avec.total_ttc) / Number(sans.total_ttc), `totaux ${avec.total_ttc} / ${sans.total_ttc}`).toBeCloseTo(0.9, 2)
})

etape('PA3-01.remise_auto_fiche', ['ADVS10'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const lead = await leadCi(r, `ADVS10 Fiche ${m}`)
  await page.goto(`/crm/leads/${lead.id}`)
  await page.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click({ timeout: 60_000 })
  await page.getByRole('button', { name: /Devis modifiable/ }).click()
  await page.getByRole('menuitem', { name: /Remise %/ }).click()
  await page.getByLabel('Remise (%)').or(page.locator('.ldp-center input[type="number"]')).first().fill('10')
  const [rep] = await Promise.all([
    page.waitForResponse((x) => /\/ventes\/devis\/auto\/$/.test(new URL(x.url()).pathname) && x.request().method() === 'POST', T),
    page.getByRole('button', { name: 'Créer le devis' }).click(),
  ])
  expect(rep.status(), (await rep.text()).slice(0, 300)).toBe(201)
  expect(rep.request().postDataJSON().remise_globale, 'la remise part avec').toBe('10')
  const relu = await devisRelu(r, idDe(await rep.json()))
  expect(Number(relu.remise_globale), 'persistance : remise 10,00').toBe(10)
})

etape('PA3-05.remise_auto_agricole', ['ADVS10'], async ({ page }) => {
  const r = page.request
  await pompesTarifees(r)
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, {
    ...T,
    data: {
      nom: `ADVS10 Ferme ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'agricole', raccordement: 'triphase', ville: 'Taroudant',
      gps_lat: '30.47', gps_lng: '-8.88', pompe_hmt_m: '60', besoin_eau_m3j: '135', niveau_statique_m: '35', debit_forage_m3h: '50',
    },
  }), 'lead agricole')
  const rep = await r.post(`${API}/ventes/devis/auto/`, { ...T, data: { lead: lead.id, remise_globale: '10' } })
  const corps = await rep.json()
  expect(rep.status(), JSON.stringify(corps).slice(0, 400)).toBe(201)
  expect(Number((await devisRelu(r, idDe(corps))).remise_globale), 'persistance : remise 10,00').toBe(10)
})

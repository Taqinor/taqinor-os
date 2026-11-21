// ACAL440 — Fluidité de l'atelier Calepinage : pire interaction pendant un glissé sur 500 modules.
// Complète `perf.test.ts` (coût pur, sans GPU) par une mesure réelle (Event Timing). Plafond :
// 200 ms en local ; sur un runner de CI le seuil « mauvais » de `vitals.js` (INP[1]), lu à la source.
// Fond de repli (comme acceptation/acal6.spec.js::carteRefusee) ; rien n'est écrit hors du calepinage jetable.
import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { API_DJANGO, assurerSessionPage, lireJson, uniq, telephoneMobileUnique } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const NB = 500
const SCHEMA = join(here, '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json')
const [INP_BON, INP_MAUVAIS] = /INP:\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]/
  .exec(readFileSync(join(here, '../src/lib/vitals.js'), 'utf8')).slice(1).map(Number)
const PLAFOND = process.env.CI ? INP_MAUVAIS : INP_BON

test.describe.configure({ timeout: 600_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

function consigner(nom, valeur, cible) {
  const ligne = `${nom} = ${valeur} ms (${cible})`
  test.info().annotations.push({ type: 'budget', description: ligne })
  console.log(`[ACAL440] ${ligne}`)
}

/** Document de 500 modules : l'`exemple` du schéma, sommets élargis, `geometry.panels` à 500 entrées. */
function documentA500() {
  const doc = JSON.parse(readFileSync(SCHEMA, 'utf8')).exemple
  const zone = doc.zones[0]
  zone.vertices = [[0, 0], [30, 0], [30, 40], [0, 40]]
  zone.obstacles = []
  zone.geometry.panels = Array.from({ length: NB }, (_, i) => ({
    cx: (i % 25) * 1.2, cy: Math.floor(i / 25) * 2, n: i + 1, rangee: String.fromCharCode(65 + Math.floor(i / 25)),
  }))
  zone.geometry.count = NB
  zone.neededPanels = NB
  return doc
}

async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal440', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

async function calepinageA500(request) {
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T,
    data: { nom: uniq('ACAL440 Perf'), ville: 'Casablanca', telephone: telephoneMobileUnique(),
      type_installation: 'residentiel', facture_hiver: '800' },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, {
    ...T, data: { lead: lead.id, titre: uniq('ACAL440') },
  }), 'calepinage')
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
  await lireJson(await request.post(`${CAL}/calepinages/${cal.id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: documentA500() },
  }), 'écriture du layout')
  return cal
}

async function mesurerGlisse(page, id) {
  await page.goto(`/calepinage/${id}`)
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  const scene = page.locator('#rp9-map')
  await expect(scene).toBeVisible()
  await page.evaluate(() => {
    window.__acal440 = []
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__acal440.push(Math.round(e.duration)) })
      .observe({ type: 'event', durationThreshold: 16, buffered: false })
  })
  const b = await scene.boundingBox()
  const [x0, y0] = [b.x + b.width / 2, b.y + b.height / 2]
  await page.mouse.move(x0, y0)
  await page.mouse.down()
  for (let i = 1; i <= 20; i += 1) await page.mouse.move(x0 + i * 6, y0 + i * 3)
  await page.mouse.up()
  // Event Timing publie ses entrées au prochain rendu : on attend deux frames, pas un délai fixe.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))))
  const durees = await page.evaluate(() => window.__acal440)
  return durees.length ? Math.max(...durees) : 0
}

test('ACAL440: glissé de panneaux sur 500 modules — pire interaction sous le plafond', async ({ page, context }) => {
  await carteRefusee(context)
  const pire = await mesurerGlisse(page, (await calepinageA500(page.request)).id)
  consigner('Atelier 500 modules — pire interaction', pire,
    `plafond ${PLAFOND} ms, ${process.env.CI ? 'CI = seuil mauvais' : 'local = seuil bon'} de vitals.js`)
  expect(pire, 'la pire interaction du glissé reste sous le plafond').toBeLessThanOrEqual(PLAFOND)
})

test('ACAL440: mode bas de gamme (deviceMemory 4) — mesure consignée sans plafond', async ({ page, context }) => {
  await context.addInitScript(() => Object.defineProperty(navigator, 'deviceMemory', { get: () => 4 }))
  await carteRefusee(context)
  const pire = await mesurerGlisse(page, (await calepinageA500(page.request)).id)
  consigner('Atelier 500 modules, deviceMemory 4 — pire interaction', pire, 'sans plafond')
})

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
// Version mesurée (avant/après ACAL431 et ACAL433 : le runner rejoue la spec sur le code sans leurs deux commits).
const VERSION = process.env.ACAL440_VERSION || 'code courant'
// Épingle de l'exemple ; toit de 68 m × 56 m centré dessus, 25 × 20 modules au pas de 2,5 m (sans chevauchement
// quelle que soit l'orientation du module de 2 384 × 1 134 mm), posés VERBATIM en placement libre (PV30).
const ORIGINE = [-7.6, 33.5]
const DEG2M = (Math.PI / 180) * 6378137
const versLngLat = (cx, cy) => [ORIGINE[0] + cx / (DEG2M * Math.cos((ORIGINE[1] * Math.PI) / 180)), ORIGINE[1] + cy / DEG2M]
const [O, N] = [versLngLat(-34, -28), versLngLat(34, 28)]
const centre = (i) => [((i % 25) - 12) * 2.5, (Math.floor(i / 25) - 9.5) * 2.5]

test.describe.configure({ timeout: 600_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(sondeCarte)
  await assurerSessionPage(page)
})

/** Capte la carte MapLibre de l'atelier (même sonde que `acceptation/acal10.spec.js::sondes`). */
function sondeCarte() {
  window.__cartes440 = []
  Object.defineProperty(Object.prototype, '_maxTileCacheSize', {
    configurable: true,
    get() { return undefined },
    set(v) {
      Object.defineProperty(this, '_maxTileCacheSize', { value: v, writable: true, configurable: true, enumerable: true })
      if (typeof this.project === 'function' && typeof this.getContainer === 'function') window.__cartes440.push(this)
    },
  })
  window.__carte440 = () => window.__cartes440.filter((m) => m.getContainer()?.isConnected && m.getContainer().id === 'rp9-map').pop()
}

function consigner(nom, valeur, cible) {
  const ligne = `${nom} = ${valeur} ms (${cible})`
  test.info().annotations.push({ type: 'budget', description: ligne })
  console.log(`[ACAL440] ${ligne}`)
}

/** Document de 500 modules : l'`exemple` du schéma, sommets élargis (lng/lat autour de l'épingle), `geometry.panels` à 500. */
function documentA500() {
  const doc = JSON.parse(readFileSync(SCHEMA, 'utf8')).exemple
  const zone = doc.zones[0]
  zone.vertices = [O, [N[0], O[1]], N, [O[0], N[1]]]
  zone.obstacles = []
  const { solarAccess, ...geometrie } = zone.geometry // l'accès solaire de l'exemple ne vaut que pour ses 2 modules
  zone.geometry = { ...geometrie, mode: 'free', origin: ORIGINE, count: NB, panels: Array.from({ length: NB }, (_, i) => ({
    cx: centre(i)[0], cy: centre(i)[1], n: i + 1, rangee: String.fromCharCode(65 + Math.floor(i / 25)),
  })) }
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
  await expect(page.getByTestId('cal-resume-panneaux'), '500 modules posés avant la mesure').toHaveText(`${NB} panneaux`, T)
  // « Déplacer les panneaux » : hors mode disposition, `beginLayoutDrag` refuse et le glissé déplacerait la CARTE.
  const bascule = page.locator('#rp9-layout-toggle')
  await bascule.click()
  await expect(bascule).toHaveAttribute('aria-pressed', 'true')
  await page.evaluate(() => document.getElementById('rp9-map').scrollIntoView({ block: 'center' }))
  await expect(page.locator('#rp9-map')).toBeInViewport({ ratio: 0.9 })
  await expect.poll(() => page.evaluate(() => { const m = window.__carte440(); return !!m && m.getPitch() < 0.5 && !m.isMoving() }),
    { timeout: 30_000, message: 'vue de dessus, carte immobile' }).toBe(true)
  // Le dernier module (coin nord-est) : son pixel par la projection de la carte, après cadrage du toit entier.
  const cible = await page.evaluate(([bornes, ll]) => {
    const m = window.__carte440()
    m.fitBounds(bornes, { padding: 60, duration: 0 })
    const [p, r, c] = [m.project(ll), m.getContainer().getBoundingClientRect(), m.getCenter()]
    return { x: r.left + p.x, y: r.top + p.y, centre: [c.lng, c.lat], dedans: p.x > 0 && p.y > 0 && p.x < r.width && p.y < r.height }
  }, [[O, N], versLngLat(...centre(NB - 1))])
  expect(cible.dedans, 'le module visé est dans la carte').toBe(true)
  await page.evaluate(() => {
    window.__acal440 = []
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__acal440.push(Math.round(e.duration)) })
      .observe({ type: 'event', durationThreshold: 16, buffered: false })
  })
  await page.mouse.move(cible.x, cible.y)
  await page.mouse.down()
  for (let i = 1; i <= 20; i += 1) await page.mouse.move(cible.x + i, cible.y)
  const note = await page.locator('#rp9-layout-note').innerText()
  await page.mouse.up()
  // Event Timing publie ses entrées au prochain rendu : on attend deux frames, pas un délai fixe.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))))
  const apres = await page.evaluate(() => { const c = window.__carte440().getCenter(); return [c.lng, c.lat] })
  expect(note, 'aperçu du glissé d’un PANNEAU (note du mode disposition)').toMatch(/Relâchez pour poser|Ici :/)
  expect(apres, 'la carte n’a pas bougé : le geste a glissé un panneau, pas la vue').toEqual(cible.centre)
  const durees = await page.evaluate(() => window.__acal440)
  return durees.length ? Math.max(...durees) : 0
}

test('ACAL440: glissé de panneaux sur 500 modules — pire interaction sous le plafond', async ({ page, context }) => {
  await carteRefusee(context)
  const pire = await mesurerGlisse(page, (await calepinageA500(page.request)).id)
  consigner(`Atelier 500 modules (${VERSION}) — pire interaction`, pire,
    `plafond ${PLAFOND} ms, ${process.env.CI ? 'CI = seuil mauvais' : 'local = seuil bon'} de vitals.js`)
  expect(pire, 'la pire interaction du glissé reste sous le plafond').toBeLessThanOrEqual(PLAFOND)
})

test('ACAL440: mode bas de gamme (deviceMemory 4) — mesure consignée sans plafond', async ({ page, context }) => {
  await context.addInitScript(() => Object.defineProperty(navigator, 'deviceMemory', { get: () => 4 }))
  await carteRefusee(context)
  const pire = await mesurerGlisse(page, (await calepinageA500(page.request)).id)
  consigner(`Atelier 500 modules (${VERSION}), deviceMemory 4 — pire interaction`, pire, 'sans plafond')
})

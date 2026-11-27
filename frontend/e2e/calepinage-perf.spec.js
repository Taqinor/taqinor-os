// ACAL440 — Fluidité de l'atelier Calepinage : pire interaction pendant un glissé sur 500 modules.
// Complète `perf.test.ts` (coût pur, sans GPU) par une mesure réelle (Event Timing). Plafond :
// 200 ms en local ; sur un runner de CI le seuil « mauvais » de `vitals.js` (INP[1]), lu à la source.
// Fond de repli (comme acceptation/acal6.spec.js::carteRefusee) ; rien n'est écrit hors du calepinage jetable.
import { test, expect } from '@playwright/test'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { API_DJANGO, assurerSessionPage, lireJson, uniq, telephoneMobileUnique, sondeCarte } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const NB = 500
// ACAL890 — trois tailles mesurées UNE fois ; `CAL_PERF_ECRIRE=1` écrit la limite (jamais tapée à la main).
const TAILLES = [2000, 5000, 10000]
const LIMITE = join(here, 'calepinage-perf.limite.json')
const ECRIRE = process.env.CAL_PERF_ECRIRE === '1'
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
// ACAL890 — grille paramétrée : à 500 elle redonne EXACTEMENT 25 × 20 et le toit de 68 m × 56 m.
const grille = (nb) => {
  const cols = nb === NB ? 25 : Math.ceil(Math.sqrt(nb))
  const rows = Math.ceil(nb / cols)
  const [dx, dy] = [cols * 1.25 + 2.75, rows * 1.25 + 3]
  return { cols, rows, O: versLngLat(-dx, -dy), N: versLngLat(dx, dy),
    centre: (i) => [((i % cols) - (cols - 1) / 2) * 2.5, (Math.floor(i / cols) - (rows - 1) / 2) * 2.5] }
}
const NB_MESURES = 3
const mediane = (v) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)]
const nombreLu =(nb) => new RegExp(`${String(nb).replace(/\B(?=(\d{3})+(?!\d))/g, '[\\s\\u00a0\\u202f]?')} posés`)

test.describe.configure({ timeout: 600_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(sondeCarte)
  await assurerSessionPage(page)
})

function consigner(nom, valeur, cible) {
  const ligne = `${nom} = ${valeur} ms (${cible})`
  test.info().annotations.push({ type: 'budget', description: ligne })
  console.log(`[ACAL440] ${ligne}`)
}

/** Document de 500 modules : l'`exemple` du schéma, sommets élargis (lng/lat autour de l'épingle), `geometry.panels` à 500. */
function documentA500(nb = NB) {
  const g = grille(nb)
  const doc = JSON.parse(readFileSync(SCHEMA, 'utf8')).exemple
  const zone = doc.zones[0]
  zone.vertices = [g.O, [g.N[0], g.O[1]], g.N, [g.O[0], g.N[1]]]
  zone.obstacles = []
  delete zone.geometry.solarAccess // l'accès solaire de l'exemple ne vaut que pour ses 2 modules
  const rangee = (r) => (r < 26 ? String.fromCharCode(65 + r) : `R${r + 1}`)
  zone.geometry = { ...zone.geometry, mode: 'free', origin: ORIGINE, count: nb, panels: Array.from({ length: nb }, (_, i) => ({
    cx: g.centre(i)[0], cy: g.centre(i)[1], n: i + 1, rangee: rangee(Math.floor(i / g.cols)),
  })) }
  zone.neededPanels = nb
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

async function calepinageA500(request, nb = NB) {
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
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: documentA500(nb) },
  }), 'écriture du layout')
  return cal
}

async function mesurerGlisse(page, id, nb = NB) {
  const { O, N, centre } = grille(nb)
  await page.goto(`/calepinage/${id}`)
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await expect(page.locator('#rp9-need-note'), `${nb} modules posés avant la mesure`).toContainText(nombreLu(nb), T)
  console.log(`[ACAL440-diag] barre de résumé : « ${await page.getByTestId('cal-resume-panneaux').innerText()} »`)
  // « Déplacer les panneaux » : hors mode disposition, `beginLayoutDrag` refuse et le glissé déplacerait la CARTE.
  // Coque (22/11) : les contrôles du constructeur (`#rp9-layout-*`, `#rp9-need-*`, `#rp9-results`, rangées sous
  // la carte) sont ceux du mode EXPERT (« Avancé » en guidé est une feuille à part, sans eux).
  if (!(await page.getByTestId('cal-mode-expert').isChecked())) {
    await page.getByTestId('cal-barre-projet').getByRole('button', { name: 'Expert' }).click()
  }
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
  }, [[O, N], versLngLat(...centre(nb - 1))])
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
  // ACAL1347 — trois mesures sur le même calepinage (rechargé à chaque fois) ; la MÉDIANE est comparée au plafond
  // et reportée avec les trois valeurs : une mesure isolée sur un poste chargé ne tranche rien.
  const id = (await calepinageA500(page.request)).id
  const mesures = []
  for (let i = 0; i < NB_MESURES; i += 1) mesures.push(await mesurerGlisse(page, id))
  const pire = mediane(mesures)
  consigner(`Atelier 500 modules (${VERSION}) — pire interaction, médiane de ${NB_MESURES} (${mesures.join(' / ')})`, pire,
    `plafond ${PLAFOND} ms, ${process.env.CI ? 'CI = seuil mauvais' : 'local = seuil bon'} de vitals.js`)
  expect(pire, `la médiane des pires interactions (${mesures.join(', ')} ms) reste sous le plafond`).toBeLessThanOrEqual(PLAFOND)
})

test('ACAL440: mode bas de gamme (deviceMemory 4) — mesure consignée sans plafond', async ({ page, context }) => {
  await context.addInitScript(() => Object.defineProperty(navigator, 'deviceMemory', { get: () => 4 }))
  await carteRefusee(context)
  const pire = await mesurerGlisse(page, (await calepinageA500(page.request)).id)
  consigner(`Atelier 500 modules (${VERSION}), deviceMemory 4 — pire interaction`, pire, 'sans plafond')
})

// ACAL890 — la limite publiée est une MESURE datée : `CAL_PERF_ECRIRE=1` l'écrit, sinon chaque taille déjà
// tracée ne doit pas devenir plus lente que sa trace committée (le fichier ne baisse qu'à la main).
test('ACAL890: trois tailles (2 000, 5 000, 10 000 modules) — limite mesurée', async ({ page, context }) => {
  test.setTimeout(3_600_000)
  // Une limite jamais relevée n'est pas une régression : le cas saute, en disant quoi lancer.
  test.skip(!ECRIRE && !existsSync(LIMITE), 'calepinage-perf.limite.json absent : lancer une fois sur une pile '
    + 'qui tourne avec CAL_PERF_ECRIRE=1 (npx playwright test e2e/calepinage-perf.spec.js -g ACAL890), puis committer le JSON')
  const trace = ECRIRE ? null : JSON.parse(readFileSync(LIMITE, 'utf8'))
  await carteRefusee(context)
  const mesures = []
  for (const nb of TAILLES) {
    const pire = await mesurerGlisse(page, (await calepinageA500(page.request, nb)).id, nb)
    consigner(`Atelier ${nb} modules (${VERSION}) — pire interaction`, pire, `seuil ${PLAFOND} ms`)
    mesures.push({ modules: nb, inp_ms: pire })
    const tracee = trace?.mesures.find((m) => m.modules === nb)
    if (tracee) expect(pire, `${nb} modules : ${pire} ms, plus lent que la trace ${tracee.inp_ms} ms`).toBeLessThanOrEqual(tracee.inp_ms)
  }
  if (!ECRIRE) return
  const sous = mesures.filter((m) => m.inp_ms <= PLAFOND).map((m) => m.modules)
  writeFileSync(LIMITE, `${JSON.stringify({
    date: new Date().toISOString().slice(0, 10),
    commit: execSync('git rev-parse --short HEAD', { cwd: here }).toString().trim(),
    seuil_ms: PLAFOND,
    seuil_source: `vitals.js INP[${process.env.CI ? 1 : 0}] (${process.env.CI ? 'CI = seuil mauvais' : 'local = seuil bon'})`,
    mesures,
    limite_modules: sous.length ? Math.max(...sous) : null,
  }, null, 2)}\n`)
})

// Acceptation en direct — groupe ACAL, dixième lot (runner GitHub, ACAL490) : les preuves d'ÉCRAN du complément L5
// qu'une première passe avait déclarées « non automatisables » (geste sur la carte 3D, ciel, texture, calage, OSM).
// Moyens (tous réels, aucun écran simulé) :
//  • Carte : montage ACAL377 d'acal6 (clé factice servie par `design-context`, imagerie MapTiler refusée 403, déclarée
//    à l'oracle) → l'atelier boote sur son fond de repli LOCAL ; WebGL = Chromium du runner (SwiftShader). Aucune
//    preuve de ce lot n'a besoin de l'imagerie.
//  • Gestes : `page.mouse` sur la carte, aux pixels calculés par la VRAIE projection de la carte (`map.project`). La
//    carte MapLibre est captée à sa construction (accesseur posé sur `_maxTileCacheSize`, assigné par le constructeur
//    de `Map`) ; le document vivant est relu par `builderApi.serializeLayout()` (API publique de l'atelier, retrouvée
//    sur l'arbre React) — lecture seule, jamais un geste remplacé, sauf là où l'étape le DIT (ACAL472 : la pose d'un
//    organe par clic n'est reliée à aucun geste — l'organe est posé par `builderApi.electrique.poser`).
//  • OSM (ACAL421) : le bâtiment est choisi par une requête Overpass faite DEPUIS le runner (service public), son
//    centroïde devient l'épingle du lead ; le serveur relit ensuite Overpass lui-même. Injoignable ⇒ NON JOUABLE.
//  • Calage (ACAL424) : JPEG + fichier monde .jgw générés au test.
// Données propres à chaque étape (lead + calepinage au shell Django), nettoyées.
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { RACINE, aujourdHui } from './_enregistrement.js'
import { API_DJANGO, assurerSessionPage, lireJson } from '../helpers.js'

// Rejeu ciblé (`--grep`) : `ACAL10_TACHES` (ids séparés par des virgules) restreint ce que l'enregistrement COUVRE aux
// tâches des étapes rejouées ; chaque id couvert exige toujours son étape PASS (`_enregistrement.js::composer`).
const etape = groupe('ACAL', process.env.ACAL10_TACHES ? process.env.ACAL10_TACHES.split(',') : ['ACAL401', 'ACAL402',
  'ACAL411', 'ACAL418', 'ACAL421', 'ACAL424', 'ACAL425', 'ACAL431', 'ACAL433', 'ACAL459', 'ACAL460', 'ACAL472'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1440, height: 900 }, actionTimeout: 60_000 })

/** Sondes de lecture posées AVANT le code de la page (aucun comportement modifié) :
 *  - `__carteAtelier()` : la carte MapLibre de `#rp9-map` (captée à sa construction) ;
 *  - `__ciel` : chaque `map.setSky(...)` reçu (ACAL431) ;
 *  - `__toiles2d` : chaque toile 2D créée (dimensions des textures de verre, ACAL433) ;
 *  - `__builderApi()` : l'API publique de l'atelier (`onApiReady`), retrouvée sur l'arbre React ;
 *  - matériel : `acal10-bas-de-gamme` = '1' ⇒ deviceMemory 4 (bas de gamme) ; sinon 16 Go / 8 cœurs, pour que le
 *    runner (≤ 4 cœurs) ne bascule pas seul en bas de gamme. */
function sondes() {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  let bas = false
  try { bas = localStorage.getItem('acal10-bas-de-gamme') === '1' } catch { /* mode privé */ }
  Object.defineProperty(navigator, 'deviceMemory', { configurable: true, get: () => (bas ? 4 : 16) })
  Object.defineProperty(navigator, 'hardwareConcurrency', { configurable: true, get: () => (bas ? 4 : 8) })
  window.__cartes = []
  window.__ciel = []
  window.__toiles2d = []
  Object.defineProperty(Object.prototype, '_maxTileCacheSize', {
    configurable: true,
    get() { return undefined },
    set(v) {
      Object.defineProperty(this, '_maxTileCacheSize', { value: v, writable: true, configurable: true, enumerable: true })
      try {
        if (typeof this.getCanvas === 'function' && typeof this.project === 'function' && !window.__cartes.includes(this)) {
          window.__cartes.push(this)
          const carte = this
          const setSky = this.setSky
          if (typeof setSky === 'function') {
            this.setSky = function (ciel) {
              window.__ciel.push(JSON.parse(JSON.stringify(ciel ?? null)))
              return setSky.call(carte, ciel)
            }
          }
        }
      } catch { /* sonde : jamais bloquante */ }
    },
  })
  const getContext = HTMLCanvasElement.prototype.getContext
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    if (type === '2d' && !window.__toiles2d.includes(this)) window.__toiles2d.push(this)
    return getContext.call(this, type, ...rest)
  }
  window.__carteAtelier = () => {
    const vivantes = window.__cartes.filter((m) => {
      try { return m.getContainer()?.isConnected && m.getContainer().id === 'rp9-map' } catch { return false }
    })
    return vivantes[vivantes.length - 1] || null
  }
  window.__builderApi = () => {
    const el = document.getElementById('rp9-map')
    if (!el) return null
    const cle = Object.keys(el).find((k) => k.startsWith('__reactFiber$'))
    let f = cle ? el[cle] : null
    const estApi = (x) => x && typeof x === 'object' && typeof x.serializeLayout === 'function'
    while (f) {
      const p = f.memoizedProps
      if (p && estApi(p.builderApi?.current)) return p.builderApi.current
      if (p && estApi(p.builderApi)) return p.builderApi
      let h = f.memoizedState
      let n = 0
      while (h && typeof h === 'object' && n < 400) {
        const v = h.memoizedState
        if (v && typeof v === 'object' && estApi(v.current)) return v.current
        if (estApi(v)) return v
        h = h.next
        n += 1
      }
      f = f.return
    }
    return null
  }
}

test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(sondes)
  await assurerSessionPage(page)
})

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const DEG2M = (Math.PI / 180) * 6378137
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const chiffres = (s) => Number(String(s).replace(/[^\d]/g, '')) || 0
const pan = (doc, id) => (doc?.zones || []).find((z) => z.id === id)
const actif = (doc) => pan(doc, doc?.activeAreaId) || doc?.zones?.[0]

// Pan d'environ 18,5 m × 22 m (Casablanca), centré sur PIN.
const PIN = { lat: 33.5731, lng: -7.5898 }
const PAN = [[-7.5899, 33.5732], [-7.5897, 33.5732], [-7.5897, 33.5730], [-7.5899, 33.5730]]
const ORIGINE = [PIN.lng, PIN.lat]
const zonePentue = (extra = {}) => ({
  id: 'z1', label: 'Pan sud', vertices: PAN, roofType: 'pitched', pitchDeg: 15, facingAzimuthDeg: 180, facingManual: true,
  ...extra,
})
const docPentu = (extra = {}, zone = {}) => ({ version: 2, pin: PIN, activeAreaId: 'z1', zones: [zonePentue(zone)], ...extra })
/** Placement LIBRE : `panels` = centres ENU (m) autour du centre du pan (`geometry.origin`), rechargés VERBATIM (PV30). */
const docLibre = (centres) => docPentu({}, {
  geometry: { mode: 'free', origin: ORIGINE, panels: centres.map(([cx, cy], i) => ({ cx, cy, n: i + 1 })), count: centres.length },
})

// ───────────────────────────── shell Django ─────────────────────────────
async function calepinageAvec(tag, layout, { roofPoint = null } = {}) {
  const m = marque()
  return py(`import json
from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC ${tag} ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('3000'))
rp = json.loads(${JSON.stringify(JSON.stringify(roofPoint))})
if rp:
    lead.roof_point = rp
    lead.save(update_fields=['roof_point'])
lay = json.loads(${JSON.stringify(JSON.stringify(layout))})
kw = {'roof_layout': lay, 'layout_hash': layout_hash(lay)} if lay else {}
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ${tag} ${m}', **kw)
sortie({'id': c.pk, 'lead': lead.pk})`)
}

async function nettoyer(...cals) {
  const ids = cals.filter(Boolean)
  if (!ids.length) return
  await py(`from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk__in=${JSON.stringify(ids.map((c) => Number(c.id)))}).delete()
Lead.objects.filter(pk__in=${JSON.stringify(ids.map((c) => Number(c.lead)))}).delete()
sortie(1)`)
}

const lireLayout = async (request, id) => lireJson(await request.get(`${CAL}/calepinages/${id}/layout/`, T), 'layout')

// ───────────────────────────── atelier ─────────────────────────────
/** Montage ACAL377 : clé carte factice servie par `design-context`, style d'imagerie refusé (403, déclaré). */
async function carteRefusee(context, suivi) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal10', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

/** Ouvre l'atelier et attend la scène HYDRATÉE, la carte captée et l'API publique. */
async function ouvrirAtelier(page, id, onglet = null, { pret = true } = {}) {
  await page.goto(`/calepinage/${id}${onglet ? `?onglet=${onglet}` : ''}`)
  const bouton = page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ })
  if (pret) {
    try {
      await expect(bouton, '« Enregistrer le calepinage » actif (scène hydratée)').toBeEnabled({ timeout: 240_000 })
    } catch (e) {
      console.log(`[atelier] scène non hydratée ; #rp9-status : « ${await page.locator('#rp9-status').innerText().catch(() => '?')} »`)
      throw e
    }
    await expect(page.locator('#rp9-status'), '`#rp9-status` n’est plus « Chargement… »').not.toHaveText(/^Chargement/, T)
  }
  await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' }), 'jamais « Carte indisponible »').toHaveCount(0)
  await expect.poll(() => page.evaluate(() => !!window.__carteAtelier?.()), { ...T, message: 'carte MapLibre de l’atelier captée' }).toBe(true)
  await expect.poll(() => page.evaluate(() => !!window.__builderApi?.()), { ...T, message: 'API publique de l’atelier joignable' }).toBe(true)
  await attendreCarteImmobile(page)
  return bouton
}

const attendreCarteImmobile = (page) => expect.poll(() => page.evaluate(() => {
  const m = window.__carteAtelier?.()
  return !!m && !m.isMoving() && !m.isEasing?.()
}), { timeout: 30_000, message: 'carte immobile' }).toBe(true)

/** ADEP24 — N images rendues (requestAnimationFrame) : on attend le rendu, jamais un délai fixe. */
const images = (page, n = 20) => page.evaluate((k) => new Promise((r) => {
  let i = 0
  const f = () => { i += 1; if (i >= k) r(); else requestAnimationFrame(f) }
  requestAnimationFrame(f)
}), n)

/** ADEP24 — attend qu'une valeur lue cesse de changer entre deux relevés (défilement, animation). */
async function stable(lire, message) {
  let avant = Symbol('jamais')
  await expect.poll(async () => { const v = JSON.stringify(await lire()); const ok = v === avant; avant = v; return ok }, { timeout: 15_000, message }).toBe(true)
}

/** Le document VIVANT (serializeLayout) — lecture seule. */
const docVivant = (page) => page.evaluate(() => JSON.parse(JSON.stringify(window.__builderApi()?.serializeLayout?.() ?? null)))

/** Centres ENU (m) d'un pan du document → lng/lat (même projection que l'atelier, `screenToENU`). */
const versLngLat = (origine, cx, cy) => {
  const cos = Math.cos((origine[1] * Math.PI) / 180)
  return [origine[0] + cx / (DEG2M * cos), origine[1] + cy / DEG2M]
}

/** Pixel PAGE d'un point lng/lat, par la projection de la carte. */
const pixel = (page, lngLat) => page.evaluate((ll) => {
  const m = window.__carteAtelier()
  const p = m.project(ll)
  const r = m.getContainer().getBoundingClientRect()
  return { x: r.left + p.x, y: r.top + p.y }
}, lngLat)

/** Panneaux posés du pan actif, chacun avec son pixel. */
async function panneauxEcran(page) {
  const doc = await docVivant(page)
  const g = actif(doc)?.geometry || {}
  const o = g.origin
  expect(Array.isArray(o) && Array.isArray(g.panels), `géométrie du pan actif relue (${JSON.stringify(g).slice(0, 200)})`).toBeTruthy()
  const out = []
  for (const p of g.panels) out.push({ ...p, px: await pixel(page, versLngLat(o, p.cx, p.cy)) })
  return out
}

/** « Personnaliser la disposition » : mode disposition, vue de dessus (pitch 0, déprojection exacte). */
async function modeDisposition(page) {
  // Coque (22/11) : les contrôles du constructeur (`#rp9-layout-*`, `#rp9-need-*`, `#rp9-results`, rangées sous
  // la carte) sont ceux du mode EXPERT (« Avancé » en guidé est une feuille à part, sans eux).
  if (!(await page.getByTestId('cal-mode-expert').isChecked())) {
    await page.getByTestId('cal-barre-projet').getByRole('button', { name: 'Expert' }).click()
  }
  const bascule = page.locator('#rp9-layout-toggle')
  await expect(bascule, '« Personnaliser la disposition » visible').toBeVisible(T)
  if ((await bascule.getAttribute('aria-pressed')) !== 'true') await bascule.click()
  await expect(bascule).toHaveAttribute('aria-pressed', 'true')
  await expect.poll(() => page.evaluate(() => window.__carteAtelier().getPitch()), { timeout: 20_000, message: 'vue de dessus' }).toBeLessThan(0.5)
  await centrerCarte(page)
}

/** Vue EMPILÉE (< 1 280 px) pour les gestes sur la carte : en studio, la carte et les commandes du constructeur
 *  partagent une colonne à débordement masqué (voir ACAL402) ; empilée, la page défile normalement. */
const vueEmpilee = (page) => page.setViewportSize({ width: 1200, height: 1000 })

/** Ramène la carte au centre de la fenêtre (la bascule « Déplacer les panneaux » l'a fait défiler hors vue). */
async function centrerCarte(page) {
  await page.evaluate(() => document.getElementById('rp9-map').scrollIntoView({ block: 'center' }))
  await expect(page.locator('#rp9-map')).toBeInViewport({ ratio: 0.95 })
  await attendreCarteImmobile(page)
}

/** ACAL398 — la simulation automatique repart après chaque enregistrement ; sur la pile d'essai (matériel non
 *  désigné) le serveur la REFUSE en 409 en nommant le champ (réponse documentée, retenue sans toast par
 *  `simulationAuto.js`). Déclarée à l'oracle ; son motif est consigné. */
function simulationAutoAttendue(page, suivi) {
  suivi.attendre(/\/calepinages\/\d+\/simuler\//, 409)
  page.on('response', async (r) => {
    if (r.status() === 409 && /\/simuler\/$/.test(new URL(r.url()).pathname)) {
      console.log(`[ACAL398] simulation auto refusée (409) : ${(await r.text().catch(() => '?')).slice(0, 300)}`)
    }
  })
}

/** Maj + clic sur chaque panneau désigné (sélection additive, PV29). */
async function selectionner(page, cibles) {
  await page.keyboard.down('Shift')
  for (const c of cibles) await page.mouse.click(c.px.x, c.px.y)
  await page.keyboard.up('Shift')
}

/** « Enregistrer le calepinage » (écriture COMPLÈTE, If-Match) puis relecture du document stocké. */
async function enregistrer(page, id, bouton) {
  const ecrit = page.waitForResponse((x) => x.request().method() !== 'GET'
    && new URL(x.url()).pathname.endsWith(`/calepinages/${id}/layout/`), T)
  await bouton.click()
  const r = await ecrit
  expect(r.status(), `Enregistrer le calepinage → ${(await r.text()).slice(0, 300)}`).toBeLessThan(300)
  await expect(bouton).toBeEnabled({ timeout: 60_000 })
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0)
  return (await lireLayout(page.request, id)).roof_layout
}

/** Quitte un atelier aux retouches NON enregistrées sans passer par la garde de sortie (`beforeunload`, qui
 *  annulerait la navigation) : l'onglet est fermé, un nouvel onglet de la même session est surveillé. */
async function repartir(context, suivi, ancienne) {
  const vue = ancienne.viewportSize()
  await ancienne.close()
  const p = await context.newPage()
  suivi.surveiller(p)
  if (vue) await p.setViewportSize(vue)
  return p
}

/** Capture supplémentaire d'une étape (à côté de la capture finale du harnais). */
async function capture(cible, id, suffixe) {
  const rel = `docs/qa-explorer/captures/${aujourdHui()}/ACCEPTATION-ACAL-${id}-${suffixe}.jpg`
  const abs = join(RACINE, rel)
  mkdirSync(dirname(abs), { recursive: true })
  await cible.screenshot({ path: abs, type: 'jpeg', quality: 70 })
  console.log(`[capture] ${rel}`)
  return rel
}

const fermer = (a, b, tol) => Math.abs(a - b) <= tol

// ════════════════════════════════════════════════════════════════════════════
// ACAL401 — PA2.5 : la barre de résumé (panneaux · kWc · production) suit l'édition en moins de 2 s, production
// « estimation » ; après la simulation serveur (le VRAI service, aucun worker Celery sur le runner) « P50 … (simulation) ».
// NOTE : DÉPLACER un panneau ne peut pas changer le NOMBRE de panneaux ; le geste qui change les trois chiffres est
// « − » des « Panneaux nécessaires » (inspecteur) — joué ici, chronométré.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL401-resume-vivant', ['ACAL401'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  const cal = await calepinageAvec('ACAL401', docPentu())
  const meteo = await reglerMeteo()
  try {
    let bouton = await ouvrirAtelier(page, cal.id)
    const resume = page.getByTestId('cal-resume-atelier')
    // Coque (22/11) : le résumé vit dans le volet « Avancé » du panneau d'étape (le bandeau n'a plus de place).
    await page.getByTestId('cal-rail-avance').click()
    await expect(resume, 'résumé dans le volet Avancé').toBeVisible(T)
    await expect(page.locator('#rp9-studio-inspecteur').getByTestId('cal-resume-atelier')).toHaveCount(1)
    await expect(page.getByTestId('cal-resume-panneaux')).toHaveText(/^\d+ panneaux$/, T)
    // T4-X8-013 — sans simulation fraîche, « — » : jamais l'estimation du constructeur (un second chiffre de la pose).
    await expect(page.getByTestId('cal-resume-production')).toHaveText('—', T)
    const lire = async () => ({
      panneaux: chiffres(await page.getByTestId('cal-resume-panneaux').innerText()),
      kwc: await page.getByTestId('cal-resume-kwc').innerText(),
      production: await page.getByTestId('cal-resume-production').innerText(),
    })
    const avant = await lire()
    const vivant = (await docVivant(page)).result
    expect(avant.panneaux, 'nombre lu sur le document sérialisé').toBe(vivant.panels)
    console.log(`[ACAL401] avant : ${JSON.stringify(avant)} (document : ${JSON.stringify({ p: vivant.panels, kwc: vivant.kwc, kwh: vivant.annualKwh })})`)

    // Coque (22/11) : les contrôles du constructeur (`#rp9-layout-*`, `#rp9-need-*`, `#rp9-results`, rangées sous
    // la carte) sont ceux du mode EXPERT (« Avancé » en guidé est une feuille à part, sans eux).
    if (!(await page.getByTestId('cal-mode-expert').isChecked())) {
      await page.getByTestId('cal-barre-projet').getByRole('button', { name: 'Expert' }).click()
    }
    const moins = page.locator('#rp9-need-minus')
    await expect(moins, '« − » des panneaux nécessaires (inspecteur) actif').toBeEnabled(T)
    const t0 = Date.now()
    await moins.click()
    await expect.poll(async () => {
      const a = await lire()
      return a.panneaux !== avant.panneaux && a.kwc !== avant.kwc
    }, { timeout: 2_000, intervals: [100], message: 'panneaux et kWc changent en moins de 2 s' }).toBe(true)
    const apres = await lire()
    console.log(`[ACAL401] après « − » (${Date.now() - t0} ms) : ${JSON.stringify(apres)}`)
    expect(apres.panneaux).toBe(avant.panneaux - 1)
    expect(apres.production).toBe('—')
    await capture(page.getByTestId('cal-resume-atelier'), 'PA2.5-ACAL401', 'sans-simulation')

    // Enregistrer, simulation serveur ENREGISTRÉE (ACAL398 = calcul automatique ; sans worker on appelle son service).
    await enregistrer(page, cal.id, bouton)
    await designerMateriel(cal.id)
    const sim = await simulationServeur(cal.id)
    expect(sim?.p50, `simulation chiffrée (${JSON.stringify(sim)})`).toBeGreaterThan(0)
    const res = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/resultat/`, T), 'resultat')
    expect(res.simule, 'GET resultat/ : simule').toBe(true)
    expect(res.simulation_perimee, 'GET resultat/ : frais').toBe(false)
    bouton = await ouvrirAtelier(page, cal.id)
    await page.getByTestId('cal-rail-avance').click()
    const p50 = Math.round(res.production?.total?.p50_kwh)
    await expect(page.getByTestId('cal-resume-production'), 'production « simulation » une fois la simulation fraîche')
      .toHaveText(/^P50 [\d\s  ]+ kWh\/an \(simulation\)$/, T)
    const affiche = (await page.getByTestId('cal-resume-production').innerText()).replace(/^P50/, '')
    expect(chiffres(affiche), 'P50 affiché = P50 servi').toBe(p50)
    await capture(page.getByTestId('cal-resume-atelier'), 'PA2.5-ACAL401', 'simulation')
  } finally {
    await restaurerMeteo(meteo)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL402 — PA2.5 : à 1 440 × 900 l'atelier est en « studio » : la page ne défile plus, on règle un contrôle en bas de
// l'inspecteur, la carte reste en vue (même position).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL402-studio-1440', ['ACAL402'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL402', docLibre([[-5, -6], [0, -1.5], [5, 3.5]]))
  try {
    await ouvrirAtelier(page, cal.id)
    expect(page.viewportSize()).toEqual({ width: 1440, height: 900 })
    await expect(page.locator('#rp9-studio-scene')).toBeVisible()
    await expect(page.locator('#rp9-studio-inspecteur')).toBeVisible()
    const h = await page.evaluate(() => ({ doc: document.scrollingElement.scrollHeight, fen: window.innerHeight }))
    expect(h.doc, `la page ne défile plus (${JSON.stringify(h)})`).toBeLessThanOrEqual(h.fen + 1)
    const scene = await page.locator('#rp9-studio-scene').boundingBox()
    const insp = await page.locator('#rp9-studio-inspecteur').boundingBox()
    expect(insp.x, 'deux colonnes : inspecteur à droite de la carte').toBeGreaterThanOrEqual(scene.x + scene.width - 1)
    const carte0 = await page.locator('#rp9-map').boundingBox()
    // Régler un contrôle EN BAS de l'inspecteur : le dernier champ/bouton actif de l'inspecteur.
    const dernier = page.locator('#rp9-studio-inspecteur').locator('input:visible:enabled, select:visible:enabled').last()
    await dernier.scrollIntoViewIfNeeded()
    const nom = await dernier.evaluate((el) => `${el.tagName.toLowerCase()}#${el.id || el.getAttribute('data-testid') || el.name || '?'}`)
    await dernier.focus()
    // Coque (22/11) : c'est le CORPS du panneau d'étape qui défile (en-tête et pied restent en place).
    const scroll = await page.locator('#rp9-studio-inspecteur .cal-panneau-etape-corps').evaluate((el) => ({ top: el.scrollTop, max: el.scrollHeight - el.clientHeight }))
    expect(scroll.top, `l’inspecteur a défilé seul jusqu’au contrôle ${nom} (${JSON.stringify(scroll)})`).toBeGreaterThan(0)
    const carte1 = await page.locator('#rp9-map').boundingBox()
    expect(Math.round(carte1.y), 'la carte n’a pas bougé').toBe(Math.round(carte0.y))
    expect(carte1.y + carte1.height, 'carte entièrement en vue').toBeLessThanOrEqual(900 + 1)
    expect(carte1.y, 'carte entièrement en vue').toBeGreaterThanOrEqual(0)
    await expect(page.getByTestId('cal-enregistrer-calepinage'), 'barre d’enregistrement en vue').toBeInViewport()
    console.log(`[ACAL402] contrôle réglé : ${nom} ; inspecteur scrollTop ${scroll.top}/${scroll.max} ; carte y ${carte0.y}→${carte1.y}`)
    // « le reste de la page » défile : les commandes du constructeur (sous la carte, dans la colonne scène) restent
    // atteignables à la molette — sinon « Déplacer les panneaux » ne s'atteint plus qu'au clavier.
    // Coque (22/11) : les commandes de pose (`BuilderPose`) sont dans le panneau de l'étape Panneaux, dont le corps défile.
    await page.getByTestId('cal-etape-panneaux').click()
    const carte = page.locator('#rp9-studio-inspecteur .cal-panneau-etape-corps')
    const debord = await carte.evaluate((el) => ({ scrollH: el.scrollHeight, clientH: el.clientHeight, overflowY: getComputedStyle(el).overflowY }))
    const cb = await carte.boundingBox()
    await page.mouse.move(cb.x + cb.width / 2, cb.y + cb.height - 30)
    await page.mouse.wheel(0, 3000)
    await stable(() => carte.evaluate((el) => el.scrollTop), 'défilement de la colonne scène terminé')
    const bascule = page.locator('#rp9-layout-toggle')
    const visible = await bascule.isVisible()
    const bb = visible ? await bascule.boundingBox() : null
    const atteinte = !!bb && bb.y >= cb.y && bb.y + bb.height <= cb.y + cb.height && bb.y + bb.height <= 900
    console.log(`[ACAL402] colonne scène : ${JSON.stringify(debord)} ; « Déplacer les panneaux » ${visible ? `en ${JSON.stringify(bb)}` : 'masqué'} ; colonne ${JSON.stringify(cb)} ; atteinte à la molette : ${atteinte}`)
    await capture(page, 'PA2.5-ACAL402', 'apres-molette-scene')
    expect(debord.scrollH <= debord.clientH + 1 || atteinte,
      `les commandes sous la carte restent atteignables (colonne scène ${debord.scrollH} px de contenu pour ${debord.clientH} px visibles, overflow-y ${debord.overflowY})`).toBe(true)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL411 — atelier, placement libre, 3 panneaux NON alignés sélectionnés (Maj + clic), « Aligner en rangée » puis
// « Répartir » ; Répartir à 2 refuse ; Pivoter lit un angle saisi libre.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL411-aligner-repartir', ['ACAL411'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  await vueEmpilee(page)
  // Trois panneaux libres, ni en rangée ni en colonne (v différents, u différents).
  const cal = await calepinageAvec('ACAL411', docLibre([[-5, -6], [0, -1.5], [5, 3.5], [-5, 7]]))
  try {
    await ouvrirAtelier(page, cal.id)
    await modeDisposition(page)
    const barre = page.locator('#rp9-barre-selection')
    let pans = await panneauxEcran(page)
    expect(pans.length, 'placement libre rechargé verbatim (4 panneaux)').toBe(4)
    const trois = pans.slice(0, 3)
    const cyAvant = trois.map((p) => p.cy)
    expect(Math.max(...cyAvant) - Math.min(...cyAvant), 'au départ, non alignés').toBeGreaterThan(1)
    await selectionner(page, trois)
    await expect(barre, 'barre de sélection affichée en placement libre').toBeVisible()
    await expect(barre.getByRole('button', { name: 'Aligner en rangée' })).toBeVisible()
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL411', 'selection')

    await barre.getByRole('button', { name: 'Aligner en rangée' }).click()
    await expect(page.locator('#rp9-layout-note'), 'note « Aligné — 3 panneaux »').toContainText('Aligné — 3 panneaux', T)
    pans = await panneauxEcran(page)
    const cyAligne = pans.slice(0, 3).map((p) => p.cy)
    console.log(`[ACAL411] cy avant ${JSON.stringify(cyAvant)} → alignés ${JSON.stringify(cyAligne)}`)
    expect(Math.max(...cyAligne) - Math.min(...cyAligne), 'les 3 centres partagent la même coordonnée v').toBeLessThanOrEqual(0.011)
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL411', 'aligne')

    // UN seul pas d'historique : Ctrl + Z rend les positions d'avant.
    await page.evaluate(() => document.activeElement?.blur?.())
    await page.keyboard.press('Control+z')
    await expect.poll(async () => (await panneauxEcran(page)).slice(0, 3).map((p) => Math.round(p.cy * 100)),
      { timeout: 10_000, message: 'Ctrl + Z annule l’alignement en un pas' }).toEqual(cyAvant.map((v) => Math.round(v * 100)))

    // Répartir avec 2 panneaux : refus nommé.
    await page.keyboard.press('Escape')
    pans = await panneauxEcran(page)
    await selectionner(page, pans.slice(0, 2))
    await expect(barre).toBeVisible()
    await barre.getByRole('button', { name: 'Répartir' }).click()
    await expect(page.locator('#rp9-status'), 'Répartir à 2 refuse en nommant la raison')
      .toContainText('Répartir : sélectionnez au moins 3 panneaux.', T)

    // Répartir avec 3 panneaux : écarts égaux le long de la rangée après alignement.
    await page.keyboard.press('Escape')
    pans = await panneauxEcran(page)
    await selectionner(page, pans.slice(0, 3))
    await barre.getByRole('button', { name: 'Répartir' }).click()
    await expect(page.locator('#rp9-layout-note'), 'Répartir appliqué').toContainText(/Distribu/, T)
    const rep = (await panneauxEcran(page)).slice(0, 3)
    console.log(`[ACAL411] après Répartir : ${JSON.stringify(rep.map((p) => [p.cx, p.cy]))} ; note « ${await page.locator('#rp9-layout-note').innerText()} »`)
    const note = await page.locator('#rp9-layout-note').innerText()
    expect(note, 'Répartir agit (note de l’éditeur, jamais un refus muet)').not.toMatch(/^$/)

    // Pivoter : champ texte, step="any", jamais borné.
    const angle = barre.getByRole('textbox', { name: 'Angle de rotation en degrés' })
    await expect(angle).toHaveAttribute('step', 'any')
    expect(await angle.getAttribute('min')).toBeNull()
    expect(await angle.getAttribute('max')).toBeNull()
    await angle.fill('12,5')
    await barre.getByRole('button', { name: 'Pivoter' }).click()
    await expect.poll(async () => (await panneauxEcran(page)).slice(0, 3).map((p) => p.angleDeg ?? null),
      { timeout: 10_000, message: 'Pivoter applique l’angle saisi (12,5°) aux 3 panneaux' })
      .toEqual([12.5, 12.5, 12.5])
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL411', 'pivote')
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL418 — sélectionner 3 panneaux, « Retirer la sélection » (UN pas), Ctrl + Z les rend ; en emplacements validés,
// retirer tout le pan est refusé ; l'aide liste « Alt + clic sur un panneau ».
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL418-retirer-selection', ['ACAL418'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  await vueEmpilee(page)
  const libre = await calepinageAvec('ACAL418 libre', docLibre([[-5, -6], [0, -1.5], [5, 3.5], [-5, 7], [3, 8]]))
  const valide = await calepinageAvec('ACAL418 valide', docPentu())
  try {
    await ouvrirAtelier(page, libre.id)
    await modeDisposition(page)
    const barre = page.locator('#rp9-barre-selection')
    const pans = await panneauxEcran(page)
    expect(pans.length).toBe(5)
    const nb0 = chiffres(await page.getByTestId('cal-resume-panneaux').innerText())
    await selectionner(page, pans.slice(0, 3))
    await barre.getByRole('button', { name: 'Retirer la sélection' }).click()
    await expect(page.locator('#rp9-status')).toContainText('3 panneau(x) retiré(s) — Ctrl + Z les rend.', T)
    await expect.poll(async () => (await panneauxEcran(page)).length, { timeout: 5_000 }).toBe(2)
    await expect.poll(async () => chiffres(await page.getByTestId('cal-resume-panneaux').innerText()),
      { timeout: 3_000, message: 'le compteur suit' }).toBe(nb0 - 3)
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL418', 'retires')
    await page.evaluate(() => document.activeElement?.blur?.())
    await page.keyboard.press('Control+z')
    await expect.poll(async () => (await panneauxEcran(page)).length, { timeout: 10_000, message: 'Ctrl + Z rend les 3' }).toBe(5)
    await expect.poll(async () => chiffres(await page.getByTestId('cal-resume-panneaux').innerText()), { timeout: 3_000 }).toBe(nb0)

    // L'aide liste le geste caché (F1 : annonce de l'aide de l'atelier ; sinon l'aide-mémoire « ? »).
    await page.keyboard.press('F1')
    const annonce = await page.locator('#rp9-annonces').textContent().catch(() => '')
    let aide = annonce || ''
    if (!aide.includes('Alt + clic sur un panneau')) {
      await page.getByTestId('cal-raccourcis-bouton').click()
      aide = `${aide} | ${await page.getByTestId('cal-raccourcis-aide').innerText()}`
    }
    console.log(`[ACAL418] aide : ${aide.slice(0, 600)}`)
    expect(aide, 'l’aide liste « Alt + clic sur un panneau : le retirer »').toContain('Alt + clic sur un panneau')

    // Emplacements validés : sélectionner TOUT le pan (cadre Maj + glissé sur toute la carte) puis Retirer ⇒ refus.
    // Un document sans pose enregistrée n'offre pas « Déplacer les panneaux » (fenêtre de disposition masquée, constaté
    // runs 44862353552 et 44863910518) : on enregistre la pose optimale d'abord, puis on rouvre (pose validée rechargée).
    page = await repartir(context, suivi, page)
    let boutonValide = await ouvrirAtelier(page, valide.id)
    const masquee = await page.locator('#rp9-layout-window').evaluate((el) => el.hidden)
    console.log(`[ACAL418] document sans pose enregistrée : fenêtre « Personnaliser la disposition » ${masquee ? 'MASQUÉE' : 'affichée'}`)
    await enregistrer(page, valide.id, boutonValide)
    boutonValide = await ouvrirAtelier(page, valide.id)
    await modeDisposition(page)
    const tous = await panneauxEcran(page)
    const xs = tous.map((p) => p.px.x)
    const ys = tous.map((p) => p.px.y)
    await page.keyboard.down('Shift')
    await page.mouse.move(Math.min(...xs) - 40, Math.min(...ys) - 40)
    await page.mouse.down()
    await page.mouse.move(Math.max(...xs) + 40, Math.max(...ys) + 40, { steps: 12 })
    await page.mouse.up()
    await page.keyboard.up('Shift')
    const barreValide = page.locator('#rp9-barre-selection') // onglet neuf : nouveau localisateur
    console.log(`[ACAL418] emplacements validés, cadre Maj + glissé : note « ${await page.locator('#rp9-layout-note').innerText().catch(() => '?')} »`)
    await expect(barreValide).toBeVisible()
    await expect(barreValide.getByRole('button', { name: 'Aligner en rangée' }), 'en emplacements validés, seul « Retirer »').toBeHidden()
    await barreValide.getByRole('button', { name: 'Retirer la sélection' }).click()
    await expect(page.locator('#rp9-status'), 'retirer tout le pan est refusé').toContainText('gardez au moins un panneau', T)
    expect((await panneauxEcran(page)).length, 'aucun panneau retiré').toBe(tous.length)
  } finally {
    await nettoyer(libre, valide)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL421 — calepinage d'un lead épinglé sur un VRAI bâtiment (OSM), « Conception automatique » : contour du bâtiment
// et toit rempli, rien d'enregistré avant « Enregistrer le calepinage ».
// ════════════════════════════════════════════════════════════════════════════
/** Un bâtiment OSM réel de Casablanca (Overpass, depuis le runner) : son centroïde. */
async function batimentCasablanca() {
  const centres = [[33.5890, -7.6110], [33.5731, -7.5898], [33.5950, -7.6190], [33.5770, -7.6300]]
  const erreurs = []
  for (const [lat, lng] of centres) {
    const q = `[out:json][timeout:25];way(around:300,${lat},${lng})["building"];out geom;`
    try {
      const r = await fetch('https://overpass-api.de/api/interpreter', {
        method: 'POST', body: new URLSearchParams({ data: q }), signal: AbortSignal.timeout(40_000),
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', Accept: 'application/json', 'User-Agent': 'taqinor-acceptation-e2e/1.0' },
      })
      if (!r.ok) { erreurs.push(`${lat},${lng} → HTTP ${r.status}`); continue }
      const d = await r.json()
      for (const w of d.elements || []) {
        const g = (w.geometry || []).slice(0, -1)
        if (g.length < 4 || g.length > 12) continue
        const cos = Math.cos((lat * Math.PI) / 180)
        const xy = g.map((n) => [n.lon * DEG2M * cos, n.lat * DEG2M])
        let a = 0
        for (let i = 0; i < xy.length; i += 1) {
          const [x1, y1] = xy[i]
          const [x2, y2] = xy[(i + 1) % xy.length]
          a += x1 * y2 - x2 * y1
        }
        a = Math.abs(a) / 2
        if (a < 150 || a > 1500) continue
        return { way: w.id, aire: Math.round(a), lat: g.reduce((s, n) => s + n.lat, 0) / g.length, lng: g.reduce((s, n) => s + n.lon, 0) / g.length }
      }
      erreurs.push(`${lat},${lng} : aucun bâtiment de 150-1500 m²`)
    } catch (e) {
      erreurs.push(`${lat},${lng} → ${e.message}`)
    }
  }
  // Overpass injoignable DEPUIS LA SPEC (instable sur le runner, run 44866838249) : repli sur le bâtiment réel trouvé par
  // cette même recherche aux runs 44863910518 et 44865072703 (way 417968795, 735 m², centroïde ci-dessous). Le serveur
  // relit Overpass lui-même : la preuve reste celle du serveur.
  console.log(`[ACAL421] Overpass injoignable depuis la spec (${erreurs.join(' ; ')}) : repli sur le bâtiment way 417968795`)
  return { way: 417968795, aire: 735, lat: 33.58955554444444, lng: -7.6100877777777765 }
}

etape('PA2.5-ACAL421-conception-auto', ['ACAL421'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  const bat = await batimentCasablanca()
  console.log(`[ACAL421] bâtiment OSM way ${bat.way}, ${bat.aire} m², épingle ${bat.lat},${bat.lng}`)
  const cal = await calepinageAvec('ACAL421', null, { roofPoint: { lat: bat.lat, lng: bat.lng } })
  try {
    await ouvrirAtelier(page, cal.id, null, { pret: false })
    const auto = page.getByTestId('cal-conception-auto')
    await expect(auto, '« Conception automatique » offert (lead épinglé, aucun pan tracé)').toBeVisible({ timeout: 240_000 })
    const avant = await docVivant(page)
    expect((avant?.zones || []).filter((z) => (z.vertices || []).length >= 3), 'aucun pan tracé au départ').toHaveLength(0)
    // Décision fondateur du 21/11 : la recherche est une TÂCHE DE FOND — POST (202) puis statut relu par l'atelier.
    // Chaque statut servi est journalisé ; le contour attendu est celui du dernier statut `pret`.
    const statuts = []
    page.on('response', async (x) => {
      if (!/\/crm\/leads\/(\d+\/)?roof-footprint\/recherche\//.test(x.url())) return
      const corps = await x.json().catch(() => null)
      if (corps) statuts.push(corps)
    })
    const msg = page.getByTestId('cal-conception-auto-message')
    let message = ''
    for (let essai = 1; essai <= 3; essai += 1) {
      const lancement = page.waitForResponse((x) => /\/crm\/leads\/\d+\/roof-footprint\/recherche\/$/.test(x.url()), T)
      await auto.click()
      const recu = await lancement
      console.log(`[ACAL421] POST recherche (essai ${essai}) : HTTP ${recu.status()} ${JSON.stringify(await recu.json().catch(() => null)).slice(0, 300)}`)
      await expect(msg).toBeVisible(T)
      // La vraie condition : le message quitte « en cours » (l'atelier borne lui-même son attente à 90 s).
      await expect(msg).not.toHaveText(/en cours/i, { timeout: 150_000 })
      message = await msg.innerText()
      console.log(`[ACAL421] statuts servis (essai ${essai}) : ${statuts.map((s) => s.statut).join(' → ')} ; dernier : ${JSON.stringify(statuts.at(-1)).slice(0, 400)}`)
      if (message.includes('Contour posé')) break
      console.log(`[ACAL421] essai ${essai} : « ${message} »`)
      if (!/indisponible|Aucune emprise|réseau|n'a pas répondu|trop de temps|n'a pas abouti/i.test(message)) break // Overpass injoignable est nommé, on réessaie
    }
    if (!message.includes('Contour posé')) {
      // Le serveur appelle-t-il Overpass avec succès DEPUIS ce runner (même requête que `roof_detect`) ?
      const diag = await py(`import requests
from apps.crm import roof_detect as rd
q = rd._build_query(${bat.lat}, ${bat.lng}, rd.DELAI_TACHE_S)
try:
    r = requests.post(rd._OVERPASS_URL, data={'data': q}, headers={'User-Agent': getattr(rd, '_USER_AGENT', '')}, timeout=(10, rd.DELAI_TACHE_S))
    sortie({'status': r.status_code, 'ua': r.request.headers.get('User-Agent'), 'corps': r.text[:300]})
except Exception as e:
    import time
    t = time.time()
    try:
        r2 = requests.post(rd._OVERPASS_URL, data={'data': q}, headers={'User-Agent': getattr(rd, '_USER_AGENT', '')}, timeout=(5, 90))
        lent = {'status': r2.status_code, 'secondes': round(time.time() - t, 1)}
    except Exception as e2:
        lent = {'erreur': repr(e2)[:120], 'secondes': round(time.time() - t, 1)}
    sortie({'erreur': repr(e)[:300], 'meme_requete_delai_90s': lent})`)
      console.log(`[ACAL421] appel Overpass du serveur (même requête) : ${JSON.stringify(diag)}`)
      test.info().annotations.push({ type: 'diagnostic', description: `Overpass côté serveur : ${JSON.stringify(diag).slice(0, 400)}` })
    }
    expect(message, 'contour posé, toit rempli').toBe('Contour posé : le toit est rempli.')
    // Le contour servi par la tâche de fond (dernier statut `pret`), relu tel que l'atelier l'a reçu.
    await expect.poll(() => statuts.some((s) => s.statut === 'pret'), T).toBe(true)
    const fp = statuts.filter((s) => s.statut === 'pret').at(-1)
    expect(fp?.polygon?.length || 0, 'la tâche de fond a servi un contour (statut pret)').toBeGreaterThanOrEqual(3)
    const doc = await docVivant(page)
    const poses = (doc.zones || []).filter((z) => (z.vertices || []).length >= 3)
    expect(poses, 'un seul pan : le contour du bâtiment (le pan vide de départ n’est pas gardé)').toHaveLength(1)
    expect(doc.zones.length, 'aucun pan vide gardé').toBe(1)
    const z = poses[0]
    const attendu = fp.polygon.map((p) => [p.lng, p.lat])
    const sansFermeture = (r) => (r.length > 3 && r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1] ? r.slice(0, -1) : r)
    const zv = sansFermeture(z.vertices)
    const at = sansFermeture(attendu)
    console.log(`[ACAL421] contour ${zv.length} sommets (OSM ${at.length}) ; panneaux ${z.geometry?.panels?.length}`)
    expect(zv.length, 'autant de sommets que l’emprise OSM').toBe(at.length)
    zv.forEach(([lng, lat], i) => {
      expect(fermer(lng, at[i][0], 1e-7) && fermer(lat, at[i][1], 1e-7), `sommet ${i} = emprise [lng, lat]`).toBe(true)
    })
    expect(z.geometry?.panels?.length || 0, 'l’optimiseur a rempli le toit').toBeGreaterThan(0)
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL421', 'toit-rempli')
    const stocke = (await lireLayout(page.request, cal.id)).roof_layout
    expect((stocke?.zones || []).filter((x) => (x.vertices || []).length >= 3), 'rien n’est enregistré avant « Enregistrer »').toHaveLength(0)
    const bouton = page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ })
    await expect(bouton).toBeEnabled(T)
    const ecrit = await enregistrer(page, cal.id, bouton)
    expect(ecrit.zones.filter((x) => (x.vertices || []).length >= 3), 'enregistré : le pan du bâtiment').toHaveLength(1)
    await expect(page.getByTestId('cal-conception-auto'), 'pan tracé : bouton absent (jamais écrasé)').toHaveCount(0)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL424 — Photos du site : orthophoto d'essai + .jgw (degrés WGS84) → 4 poignées posées, « Enregistrer le calage »,
// la photo calée sous le tracé ; un .jgw en mètres est refusé (« exportez l'orthophoto en WGS84 »).
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL424-calage-monde', ['ACAL424'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL424', docPentu({ outline: [[33.5732, -7.5899], [33.5732, -7.5897], [33.5730, -7.5897], [33.5730, -7.5899]] }))
  try {
    await page.goto('/calepinage')
    const L = 240
    const H = 180
    const b64 = await page.evaluate(([w, h]) => {
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const x = c.getContext('2d')
      x.fillStyle = '#5a6e3a'
      x.fillRect(0, 0, w, h)
      x.fillStyle = '#c8c8c8'
      x.fillRect(w * 0.25, h * 0.2, w * 0.5, h * 0.6)
      return c.toDataURL('image/jpeg', 0.9).split(',')[1]
    }, [L, H])
    const ajout = await page.request.post(`${CAL}/calepinages/${cal.id}/photos/`, {
      ...T,
      multipart: {
        photo: { name: 'ortho-acal424.jpg', mimeType: 'image/jpeg', buffer: Buffer.from(b64, 'base64') },
        genre: 'drone', prise_le: '2026-11-20', legende: 'Orthophoto ACAL424',
      },
    })
    expect(ajout.status(), `dépôt de la photo → ${(await ajout.text()).slice(0, 300)}`).toBeLessThan(300)
    // Fichier monde : pixel ≈ 0,1 m ; coin haut-gauche (centre du pixel 0,0) au NO du pan.
    const A = 0.0000012
    const E = -0.0000009
    const C = -7.58995
    const F = 33.57325
    const monde = [A, 0, 0, E, C, F].join('\n')
    const pt = (col, ligne) => [E * ligne + F, A * col + C] // [lat, lng] (D = B = 0)
    const attendus = [pt(-0.5, -0.5), pt(L - 0.5, -0.5), pt(L - 0.5, H - 0.5), pt(-0.5, H - 0.5)]

    await ouvrirAtelier(page, cal.id, 'photos', { pret: false })
    await expect(page.getByTestId('cal-photo-calage')).toBeVisible(T)
    if (!(await page.getByTestId('cal-photo-calage-monde').count())) {
      await page.getByTestId('cal-photo-calage-select').click()
      await page.getByRole('option', { name: /ACAL424|ortho/i }).first().click()
    }
    await expect(page.getByTestId('cal-photo-calage-carte')).toBeVisible(T)
    await page.waitForFunction(() => [...document.querySelectorAll('img')].some((i) => i.complete && i.naturalWidth === 240), null, T)
    // Refus : projection en mètres (UTM), puis fichier incomplet.
    const champ = page.getByTestId('cal-photo-calage-monde')
    await champ.setInputFiles({ name: 'ortho-utm.jgw', mimeType: 'text/plain', buffer: Buffer.from('0.1\n0\n0\n-0.1\n330000\n3715000\n') })
    await expect(page.getByTestId('cal-photo-calage-erreur'), 'mètres refusés').toContainText('exportez l’orthophoto en WGS84')
    await champ.setInputFiles({ name: 'court.jgw', mimeType: 'text/plain', buffer: Buffer.from('0.1\n0\n0\n') })
    await expect(page.getByTestId('cal-photo-calage-erreur'), 'moins de 6 nombres refusé').toContainText('6 nombres attendus')
    // Fichier en degrés : poignées posées, RIEN d'enregistré avant le clic.
    let patchs = 0
    page.on('request', (r) => { if (r.method() === 'PATCH' && /\/photos\/\d+\/calage\//.test(r.url())) patchs += 1 })
    await champ.setInputFiles({ name: 'ortho-acal424.jgw', mimeType: 'text/plain', buffer: Buffer.from(monde) })
    await expect(page.getByTestId('cal-photo-calage-erreur')).toHaveCount(0)
    await page.waitForLoadState('networkidle') // aucune requête en vol : un PATCH parti se compterait
    expect(patchs, 'rien n’est enregistré avant « Enregistrer le calage »').toBe(0)
    await capture(page.getByTestId('cal-photo-calage'), 'PA2.5-ACAL424', 'poignees')
    const req = page.waitForRequest((r) => r.method() === 'PATCH' && /\/photos\/\d+\/calage\//.test(r.url()), T)
    const rep = page.waitForResponse((r) => r.request().method() === 'PATCH' && /\/photos\/\d+\/calage\//.test(r.url()), T)
    await page.getByTestId('cal-photo-calage-enregistrer').click()
    const corps = (await req).postDataJSON()
    expect((await rep).status(), 'calage enregistré').toBeLessThan(300)
    const coins = corps?.calage?.coins
    console.log(`[ACAL424] coins envoyés ${JSON.stringify(coins)} ; attendus ${JSON.stringify(attendus)}`)
    expect(coins, '4 coins').toHaveLength(4)
    coins.forEach((c, i) => {
      const [lat, lng] = Array.isArray(c) ? c : [c.lat, c.lng]
      expect(fermer(lat, attendus[i][0], 1e-9) && fermer(lng, attendus[i][1], 1e-9), `coin ${i} = fichier monde`).toBe(true)
    })
    await expect(page.getByTestId('cal-photo-calage-message')).toContainText('Calage enregistré.')
    const photos = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/photos/`, T), 'photos')
    const liste = Array.isArray(photos) ? photos : (photos.photos || photos.results || [])
    expect(liste.some((p) => Array.isArray(p.calage?.coins) && p.calage.coins.length === 4), 'calage relu par l’API').toBe(true)
    await capture(page.getByTestId('cal-photo-calage'), 'PA2.5-ACAL424', 'calee-sous-trace')
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL425 — placement libre : glisser un panneau près d'un voisin ⇒ ligne repère + collage ; touche A ⇒ plus rien.
// Joué deux fois : (1) marges PAR DÉFAUT de l'atelier (la clause telle quelle) ; (2) « Écart entre panneaux » à 0 cm
// (geste utilisateur du panneau libre) — pour situer un échec éventuel de (1) : la cible de collage au voisin est le
// bord JOINTIF, que l'écart minimal (contrainte relâchable) peut refuser.
// ════════════════════════════════════════════════════════════════════════════
const lignesRepere = (page) => page.evaluate(() => {
  const s = document.getElementById('rp9-reperes-svg')
  return s && s.style.display !== 'none' ? s.querySelectorAll('line').length : 0
})

/** Maintient B saisi et le glisse vers A pixel par pixel ; s'arrête au premier repère (ou à `jusqua`, ou presque sur A). */
async function glisserVersVoisin(page, { jusqua = null, capturer = false } = {}) {
  const [a, b] = await panneauxEcran(page)
  await page.mouse.move(b.px.x, b.px.y)
  await page.mouse.down()
  const pas = a.px.x < b.px.x ? -1 : 1
  const fin = jusqua ?? a.px.x + (b.px.x - a.px.x) * 0.1
  let x = b.px.x
  let premier = null
  let cumul = 0
  while (pas < 0 ? x > fin : x < fin) {
    x += pas
    await page.mouse.move(x, b.px.y)
    const n = await lignesRepere(page)
    cumul += n
    if (n > 0 && premier === null) {
      premier = { x, n }
      if (capturer) await capture(page.locator('#rp9-map'), 'PA2.5-ACAL425', 'repere')
      if (jusqua === null) break
    }
  }
  const pe = premier ? await page.evaluate(() => getComputedStyle(document.getElementById('rp9-reperes-svg')).pointerEvents) : null
  const note = await page.locator('#rp9-layout-note').innerText().catch(() => '?')
  await page.mouse.up()
  console.log(`[ACAL425] glissé : A px ${a.px.x.toFixed(1)}, B px ${b.px.x.toFixed(1)} → ${x.toFixed(1)} ; premier repère ${JSON.stringify(premier)} ; repères cumulés ${cumul} ; note « ${note} »`)
  return { a, b, x, premier, cumul, pe }
}

async function ouvrirLibreZoome(page, id) {
  await ouvrirAtelier(page, id)
  await modeDisposition(page)
  await page.evaluate(() => window.__carteAtelier().jumpTo({ zoom: 21.5 }))
  await attendreCarteImmobile(page)
}

etape('PA2.5-ACAL425-reperes-glisse', ['ACAL425'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  await vueEmpilee(page)
  const cal = await calepinageAvec('ACAL425', docLibre([[-3, 0], [4, 0]]))
  try {
    // (1) Marges par défaut.
    await ouvrirLibreZoome(page, cal.id)
    const ecartDefaut = await page.locator('#rp9-free-gap').inputValue().catch(() => '?')
    const defaut = await glisserVersVoisin(page)
    // (2) Écart entre panneaux à 0 cm, même geste (onglet neuf : rien n'a été enregistré).
    page = await repartir(context, suivi, page)
    await ouvrirLibreZoome(page, cal.id)
    await page.locator('#rp9-free-gap').fill('0')
    await page.locator('#rp9-free-gap').press('Tab')
    await centrerCarte(page)
    const on = await glisserVersVoisin(page, { capturer: true })
    const posOn = (await panneauxEcran(page))[1]
    // Ctrl + Z, touche A (aimantation coupée), même geste jusqu'au même pixel : ni repère ni collage.
    await page.evaluate(() => document.activeElement?.blur?.())
    await page.keyboard.press('Control+z')
    await expect.poll(async () => Math.round((await panneauxEcran(page))[1].cx * 100), { timeout: 10_000 }).toBe(Math.round(on.b.cx * 100))
    await page.keyboard.press('a')
    await expect(page.locator('#rp9-status')).toContainText(/aimantation/i, T)
    const off = await glisserVersVoisin(page, { jusqua: on.x ?? undefined })
    const posOff = (await panneauxEcran(page))[1]
    console.log(`[ACAL425] écart par défaut « ${ecartDefaut} » cm ; A ${JSON.stringify([on.a.cx, on.a.cy])} ; B collé ${JSON.stringify([posOn.cx, posOn.cy])} ; B sans aimant ${JSON.stringify([posOff.cx, posOff.cy])}`)
    expect(on.premier, 'écart 0 cm : ligne repère (SVG) pendant le glissé près du voisin').not.toBeNull()
    expect(on.pe, 'repère sans pointer-events').toBe('none')
    expect(off.cumul, 'aimantation coupée : aucun repère').toBe(0)
    const ecart = Math.hypot(posOn.cx - posOff.cx, posOn.cy - posOff.cy)
    expect(ecart, 'aimantation allumée : la position s’est collée (≠ point lâché sans aimant)').toBeGreaterThan(0.005)
    expect(ecart, 'collage sous le seuil existant (10 cm + 1 cm de pas)').toBeLessThanOrEqual(0.111)
    // La clause telle quelle : marges par défaut.
    expect(defaut.premier, `marges par défaut (écart entre panneaux ${ecartDefaut} cm) : ligne repère et collage au voisin`).not.toBeNull()
  } finally {
    // ACAL400 : le brouillon serveur part au sondage (≤ 4 s) après le dernier geste ; effacer le calepinage avant cet
    // envoi rendait un PUT brouillon/ → 404 relevé par l'oracle 2 — on laisse partir l'envoi en cours, puis on nettoie.
    await page.waitForResponse((r) => r.request().method() === 'PUT' && /\/brouillon\/$/.test(r.url()), { timeout: 10_000 }).catch(() => undefined)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL431 — PA2.3 : atelier incliné au maximum à 7 h puis 12 h (captures) ; sous l'horizon (20 h) ciel sombre ; bas de
// gamme (deviceMemory 4) : `setSky` jamais appelé.
// ════════════════════════════════════════════════════════════════════════════
const rgb = (hex) => [1, 3, 5].map((i) => parseInt(String(hex).slice(i, i + 2), 16))
const ETE = 172
const HIVER = 355

/** Remplace le document stocké (l'atelier ERP n'a pas de curseur d'heure : l'instant de scène vient du document,
 *  `scene{sunDay, sunHour}` — contrat CALX88, relu par `hydratation.ts`). */
async function poserDocument(id, layout) {
  return py(`import json
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
lay = json.loads(${JSON.stringify(JSON.stringify(layout))})
c = Calepinage.objects.get(pk=${Number(id)})
c.roof_layout = lay
c.layout_hash = layout_hash(lay)
c.save(update_fields=['roof_layout', 'layout_hash'])
sortie(1)`)
}

/** Ouvre l'atelier à l'instant (jour, heure), l'incline au maximum, rend le dernier ciel reçu par `setSky`. */
async function cielA(page, id, jour, heure) {
  await poserDocument(id, docPentu({ scene: { sunDay: jour, sunHour: heure } }))
  await ouvrirAtelier(page, id)
  await page.evaluate(() => { const m = window.__carteAtelier(); m.jumpTo({ pitch: m.getMaxPitch() }) })
  await attendreCarteImmobile(page)
  await images(page)
  const relu = (await docVivant(page))?.scene
  expect(relu, 'instant de scène hydraté').toEqual({ sunDay: jour, sunHour: heure })
  return page.evaluate(() => ({ n: window.__ciel.length, dernier: window.__ciel[window.__ciel.length - 1] ?? null }))
}

etape('PA2.3-ACAL431-ciel', ['ACAL431'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL431', docPentu())
  try {
    // 12 h (hiver, défaut de l'atelier) : ciel clair, horizon non chaud.
    const midi = await cielA(page, cal.id, HIVER, 12)
    console.log(`[ACAL431] 12 h hiver : ${JSON.stringify(midi)}`)
    expect(midi.n, '`setSky` appelé par le rendu (atelier ERP, non bas de gamme)').toBeGreaterThan(0)
    const [rs, , bs] = rgb(midi.dernier['sky-color'])
    expect(bs, '12 h : ciel bleu').toBeGreaterThan(rs)
    const [r12, , b12] = rgb(midi.dernier['horizon-color'])
    expect(b12, '12 h : horizon clair (bleu ≥ rouge)').toBeGreaterThanOrEqual(r12)
    expect(await page.evaluate(() => window.__carteAtelier().isMoving()), 'aucune animation').toBe(false)
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL431', '12h')
    // 7 h (été) : soleil bas ⇒ teinte chaude près de l'horizon.
    const matin = await cielA(page, cal.id, ETE, 7)
    console.log(`[ACAL431] 7 h été : ${JSON.stringify(matin)}`)
    const [r7, , b7] = rgb(matin.dernier['horizon-color'])
    expect(r7, '7 h : teinte chaude près de l’horizon (rouge > bleu)').toBeGreaterThan(b7)
    expect(matin.dernier['sky-color'], '7 h en été : soleil levé').not.toBe('#0b1226')
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL431', '7h')
    // 20 h (hiver) : soleil sous l'horizon ⇒ ciel sombre.
    const soir = await cielA(page, cal.id, HIVER, 20)
    console.log(`[ACAL431] 20 h hiver : ${JSON.stringify(soir)}`)
    expect(soir.dernier['sky-color'], '20 h : sous l’horizon ⇒ sombre').toBe('#0b1226')
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL431', '20h')
    // Bas de gamme : deviceMemory 4 ⇒ aucun ciel.
    await page.evaluate(() => localStorage.setItem('acal10-bas-de-gamme', '1'))
    const bas = await cielA(page, cal.id, ETE, 7)
    expect(await page.evaluate(() => navigator.deviceMemory)).toBe(4)
    console.log(`[ACAL431] bas de gamme 7 h été : ${JSON.stringify(bas)}`)
    expect(bas.n, 'bas de gamme : `setSky` JAMAIS appelé').toBe(0)
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL431', 'bas-de-gamme')
  } finally {
    await page.evaluate(() => localStorage.removeItem('acal10-bas-de-gamme')).catch(() => undefined)
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL433 — PA2.3 : même pan posé en paysage puis en portrait : la texture du verre suit le rapport du panneau,
// cellules carrées (captures de la scène 3D).
// ════════════════════════════════════════════════════════════════════════════
/** Grille d'une toile de texture (w × h) : même règle que celle déclarée par la tâche (cellule carrée, écart ≤ 5 %). */
function ecartCellule(w, h) {
  const W = w - 28
  const Hh = (h - 34) / 2
  let best = Infinity
  for (let cols = 6; cols <= 32; cols += 1) {
    const rowsHalf = Math.max(1, Math.round((Hh * cols) / W))
    best = Math.min(best, Math.abs(W / cols / (Hh / rowsHalf) - 1))
  }
  return best
}
const toiles = (page) => page.evaluate(() => window.__toiles2d.map((c) => [c.width, c.height]))
/** Exporte la toile de texture (w × h) telle que dessinée par l'atelier : la preuve visuelle des cellules. */
async function captureToile(page, w, h, suffixe) {
  const b64 = await page.evaluate(([W, H]) => {
    const c = window.__toiles2d.find((x) => x.width === W && x.height === H)
    return c ? c.toDataURL('image/png').split(',')[1] : null
  }, [w, h])
  expect(b64, `toile ${w} × ${h} exportable`).toBeTruthy()
  const rel = `docs/qa-explorer/captures/${aujourdHui()}/ACCEPTATION-ACAL-PA2.3-ACAL433-${suffixe}.png`
  mkdirSync(dirname(join(RACINE, rel)), { recursive: true })
  writeFileSync(join(RACINE, rel), Buffer.from(b64, 'base64'))
  console.log(`[capture] ${rel}`)
}

etape('PA2.3-ACAL433-texture', ['ACAL433'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL433', docPentu())
  try {
    await ouvrirAtelier(page, cal.id)
    // Vue de dessus, centrée sur les panneaux posés (le verre et ses cellules lisibles sur la capture).
    const vue = async () => {
      const pans = await panneauxEcran(page)
      const g = actif(await docVivant(page))?.geometry
      const ll = pans.map((p) => versLngLat(g.origin, p.cx, p.cy))
      const centre = [ll.reduce((t, p) => t + p[0], 0) / ll.length, ll.reduce((t, p) => t + p[1], 0) / ll.length]
      await page.evaluate((c) => window.__carteAtelier().jumpTo({ center: c, zoom: 20.5, pitch: 0, bearing: 0 }), centre)
      await attendreCarteImmobile(page)
      await images(page)
    }
    const paysage = page.locator('[data-orient="landscape"]').first()
    const portrait = page.locator('[data-orient="portrait"]').first()
    await expect(paysage, 'choix de pose paysage').toBeVisible(T)
    console.log(`[ACAL433] toiles au démarrage : ${JSON.stringify(await toiles(page))} ; pose ${await page.locator('[data-orient][aria-pressed="true"]').first().getAttribute('data-orient').catch(() => '?')}`)
    await paysage.click()
    await expect(paysage).toHaveAttribute('aria-pressed', 'true')
    await stable(() => toiles(page), 'toiles de texture stables après la bascule')
    await images(page)
    await vue()
    const t1 = await toiles(page)
    console.log(`[ACAL433] toiles après paysage : ${JSON.stringify(t1)}`)
    expect(t1.some(([w, h]) => w === 512 && h === 280), 'paysage (rapport 1,83) : EXACTEMENT 512 × 280').toBe(true)
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL433', 'paysage')
    await captureToile(page, 512, 280, 'texture-paysage-512x280')
    await portrait.click()
    await expect(portrait).toHaveAttribute('aria-pressed', 'true')
    await stable(() => toiles(page), 'toiles de texture stables après la bascule')
    await images(page)
    await vue()
    const t2 = await toiles(page)
    console.log(`[ACAL433] toiles après portrait : ${JSON.stringify(t2)}`)
    const portraitToile = t2.find(([w, h]) => h === 512 && w < 512)
    expect(portraitToile, 'portrait : une toile au rapport du panneau (hauteur 512, largeur < 512)').toBeTruthy()
    expect(ecartCellule(...portraitToile), `portrait ${portraitToile.join(' × ')} : cellules carrées (≤ 5 %)`).toBeLessThanOrEqual(0.05)
    const doc = await docVivant(page)
    console.log(`[ACAL433] orientation relue : ${JSON.stringify(actif(doc)?.geometry?.orientation ?? actif(doc)?.orientation ?? null)}`)
    await capture(page.locator('#rp9-map'), 'PA2.3-ACAL433', 'portrait')
    await captureToile(page, portraitToile[0], portraitToile[1], `texture-portrait-${portraitToile.join('x')}`)
  } finally {
    await nettoyer(cal)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL459 + ACAL460 — pile d'essai : atelier avec une ombre tracée / un arbre voisin, enregistrer, recharger, relire
// le document par l'API : même table d'ombrage ; facteur de vue du ciel < 1 ; sans obstruction : clés absentes.
// (L'atelier ERP n'a pas d'outil « Tracer une ombre » — voir acal6 : l'ombre est posée au format qu'écrit l'atelier.)
// ════════════════════════════════════════════════════════════════════════════
const OMBRE = {
  id: 'shade-1', kind: 'ombre_tracee', centre: [-7.5898, 33.57296], bout: [-7.58975, 33.57296], rayonM: 2, hauteurM: 12, source: 'ombre_tracee',
}
const ARBRE = { id: 'env-1', kind: 'arbre', label: 'Arbre voisin', centerLng: -7.5898, centerLat: 33.57296, heightM: 10, crownDiameterM: 6, evergreen: true }

etape('PA2.5-ACAL459-table-ombrage', ['ACAL459'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  const ombre = await calepinageAvec('ACAL459', docPentu({ shadeObstructions: [OMBRE] }))
  const nu = await calepinageAvec('ACAL459 nu', docPentu())
  try {
    let bouton = await ouvrirAtelier(page, ombre.id)
    const d1 = await enregistrer(page, ombre.id, bouton)
    const t1 = actif(d1)?.geometry?.shadeTable
    expect(t1, `table d’ombrage écrite au document (${JSON.stringify(actif(d1)?.geometry || {}).slice(0, 200)})`).toBeTruthy()
    expect(t1.methode, 'approximation dite').toBe('centres_de_modules')
    expect(Array.isArray(t1.azimutsDeg) && Array.isArray(t1.hauteursDeg) && Array.isArray(t1.facteurs)).toBe(true)
    const tous = t1.facteurs.flat()
    expect(tous.every((f) => f >= 0 && f <= 1), 'chaque case dans [0, 1]').toBe(true)
    expect(tous.some((f) => f < 1), 'l’ombre masque au moins une direction').toBe(true)
    console.log(`[ACAL459] table : ${t1.azimutsDeg.length} azimuts × ${t1.hauteursDeg.length} hauteurs, min ${Math.min(...tous)}`)
    bouton = await ouvrirAtelier(page, ombre.id)
    const d2 = await enregistrer(page, ombre.id, bouton)
    expect(actif(d2)?.geometry?.shadeTable, 'recharger + enregistrer : même table').toEqual(t1)
    const relu = (await lireLayout(page.request, ombre.id)).roof_layout
    expect(actif(relu)?.geometry?.shadeTable, 'relue par l’API : même table').toEqual(t1)
    bouton = await ouvrirAtelier(page, nu.id)
    const d3 = await enregistrer(page, nu.id, bouton)
    expect(actif(d3)?.geometry?.shadeTable, 'sans obstruction : aucune table écrite').toBeUndefined()
  } finally {
    await nettoyer(ombre, nu)
  }
})

etape('PA2.5-ACAL460-vue-du-ciel', ['ACAL460'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  const arbre = await calepinageAvec('ACAL460', docPentu({ environment: [ARBRE] }))
  const nu = await calepinageAvec('ACAL460 nu', docPentu())
  try {
    let bouton = await ouvrirAtelier(page, arbre.id)
    await enregistrer(page, arbre.id, bouton)
    const relu = (await lireLayout(page.request, arbre.id)).roof_layout
    const svf = actif(relu)?.geometry?.skyViewFactor
    console.log(`[ACAL460] skyViewFactor : ${JSON.stringify(svf)}`)
    expect(svf, 'facteur de vue du ciel écrit').toBeTruthy()
    expect(svf.facteur, 'arbre voisin : facteur < 1').toBeLessThan(1)
    expect(svf.facteur).toBeGreaterThan(0)
    expect(svf.methode).toEqual({ diffus: 'isotrope', horizon: false, resolution: 'centres_de_modules' })
    expect(typeof svf.signature).toBe('string')
    bouton = await ouvrirAtelier(page, nu.id)
    await enregistrer(page, nu.id, bouton)
    const reluNu = (await lireLayout(page.request, nu.id)).roof_layout
    expect(actif(reluNu)?.geometry?.skyViewFactor, 'sans obstruction : clé absente').toBeUndefined()
  } finally {
    await nettoyer(arbre, nu)
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL472 — PA2.5 : poser un onduleur, proposer le tracé, enregistrer ; `GET troncons/` en mesure la longueur.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.5-ACAL472-trace-propose', ['ACAL472'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  simulationAutoAttendue(page, suivi)
  await vueEmpilee(page)
  const coffret = { id: 'eq1', type: 'coffret_dc', label: 'Coffret DC', lng: -7.58985, lat: 33.57315, source: 'plan' }
  const cal = await calepinageAvec('ACAL472', docPentu({ electrical: { equipements: [coffret], cheminements: [] } }))
  try {
    let bouton = await ouvrirAtelier(page, cal.id, 'equipements-electriques')
    await expect(page.getByTestId('calx222-panneau')).toBeVisible(T)
    await page.getByTestId('calx222-type').selectOption('onduleur')
    await page.getByTestId('calx222-armer').click()
    await expect(page.getByTestId('calx222-armement-motif')).toHaveCount(0)
    // Geste : un clic sur le plan, à l'angle SE du toit.
    const cible = [-7.58974, 33.57304]
    await centrerCarte(page)
    const px = await pixel(page, cible)
    await page.mouse.click(px.x, px.y)
    // CALX222 (corrigé) : le clic sur la carte pose l'organe armé — plus de repli par l'API publique.
    await expect.poll(async () => ((await docVivant(page))?.electrical?.equipements || []).some((e) => e.type === 'onduleur'),
      { ...T, message: '« Armer la pose » + clic sur la carte : onduleur posé par le geste' }).toBe(true)
    const eqs = (await docVivant(page))?.electrical?.equipements || []
    console.log(`[ACAL472] onduleur posé par le geste (armer + clic) : ${JSON.stringify(eqs.find((e) => e.type === 'onduleur'))}`)
    const ond = eqs.find((e) => e.type === 'onduleur')
    expect(ond, 'onduleur posé').toBeTruthy()
    let doc = await enregistrer(page, cal.id, bouton)
    expect((doc.electrical?.equipements || []).map((e) => e.type).sort()).toEqual(['coffret_dc', 'onduleur'])

    bouton = await ouvrirAtelier(page, cal.id, 'cheminement-cables')
    await expect(page.getByTestId('acal472-bloc')).toBeVisible(T)
    await page.getByTestId('acal472-cote').selectOption('dc')
    await page.getByTestId('acal472-de').selectOption('eq1')
    await page.getByTestId('acal472-vers').selectOption(ond.id)
    await page.getByTestId('acal472-proposer').click()
    await expect(page.getByTestId('acal472-resultat')).toContainText(/Tracé proposé : \d+ points/, T)
    const txt = await page.getByTestId('acal472-resultat').innerText()
    console.log(`[ACAL472] ${txt} ; pans : le sélecteur « De/Vers » ne liste que les organes (${JSON.stringify(await page.getByTestId('acal472-de').locator('option').allInnerTexts())})`)
    await capture(page.locator('#rp9-map'), 'PA2.5-ACAL472', 'trace')
    doc = await enregistrer(page, cal.id, bouton)
    const ch = (doc.electrical?.cheminements || []).find((c) => c.de === 'eq1' && c.vers === ond.id)
    expect(ch, `cheminement enregistré (${JSON.stringify(doc.electrical?.cheminements)})`).toBeTruthy()
    expect(ch.origine, 'tracé du plan').toBe('plan')
    expect(ch.points.length, 'points calculés').toBeGreaterThanOrEqual(2)
    const tr = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/troncons/`, T), 'troncons')
    const t = (tr.troncons || []).find((x) => x.id === ch.id)
    console.log(`[ACAL472] tronçon ${JSON.stringify(t)}`)
    expect(t, 'GET troncons/ publie le tronçon').toBeTruthy()
    expect(t.longueur_m, 'longueur mesurée').toBeGreaterThan(0)
    expect(t.longueur_origine).toBe('plan')
  } finally {
    await nettoyer(cal)
  }
})

// ───────────────────────────── simulation serveur (acal6) ─────────────────────────────
async function simulationServeur(id) {
  let r
  try {
    r = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import simuler_calepinage, SimulationRefusee
c = Calepinage.objects.get(pk=${Number(id)})
try:
    r = simuler_calepinage(c, forcer=True, enregistrer=True)
    t = ((r.get('blocs') or {}).get('production') or {}).get('total') or {}
    sortie({'p50': t.get('p50_kwh'), 'complete': t.get('complete')})
except SimulationRefusee as refus:
    sortie({'refus': str(refus), 'champ': getattr(refus, 'champ', '')})`)
  } catch (e) {
    const m = String(e.message)
    if (/pvgis|ConnectionError|Timeout|Max retries|NameResolution|resolve|unreachable|injoignable/i.test(m)) {
      throw new Error(`NON JOUABLE sur ce runner — PVGIS injoignable pour la simulation serveur : ${m.slice(-500)}`)
    }
    throw new Error(`simulation serveur en erreur : ${m.slice(-700)}`)
  }
  if (r?.refus) throw new Error(`simulation serveur REFUSÉE (${r.champ}) : ${r.refus}`)
  return r
}

async function reglerMeteo() {
  return py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
avant = None if p is None else dict(p.simulation or {})
if p is None:
    p = ParametresCalepinage.objects.create(company=co)
sim = dict(p.simulation or {})
sim['mode_meteo'] = {'valeur': 'pluriannuel', 'source': 'societe', 'reference': 'acceptation ACAL10'}
sim['fenetre_annees'] = {'valeur': '2020-2020', 'source': 'societe', 'reference': 'acceptation ACAL10'}
p.simulation = sim
p.save(update_fields=['simulation'])
sortie({'cree': avant is None, 'avant': avant})`)
}

async function restaurerMeteo(etat) {
  if (!etat) return
  await py(`import json
from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
if p is not None:
    if ${etat.cree ? 'True' : 'False'}:
        p.delete()
    else:
        p.simulation = json.loads(${JSON.stringify(JSON.stringify(etat.avant || {}))})
        p.save(update_fields=['simulation'])
sortie(1)`)
}

async function designerMateriel(id) {
  const r = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.chaines import CHAMPS_MODULE, CHAMPS_ONDULEUR
from apps.calepinage.services.electrique import enregistrer_entree
from apps.stock.selectors import produits_par_type_fiche_qs
from apps.stock.selectors_fiche_technique import produits_modules_qs, specs_for_produit
c = Calepinage.objects.get(pk=${Number(id)})
def premier(qs, champs):
    for p in qs:
        s = specs_for_produit(p) or {}
        if all(s.get(cle) not in (None, '') for cle, _ in champs):
            return {'id': p.pk, 'nom': p.nom}
    return None
module = premier(produits_modules_qs(c.company), CHAMPS_MODULE)
onduleur = premier(produits_par_type_fiche_qs(c.company, 'onduleur'), CHAMPS_ONDULEUR)
if module and onduleur:
    enregistrer_entree(c, {'module_produit': module['id'], 'onduleur_produit': onduleur['id']},
                       user=U.objects.get(username='demo_admin'))
sortie({'module': module, 'onduleur': onduleur})`)
  if (!r?.module || !r?.onduleur) throw new Error(`NON JOUABLE sur ce runner — matériel non désignable : ${JSON.stringify(r)}`)
  return r
}

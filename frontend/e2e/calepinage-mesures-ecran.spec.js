// ACAL385 — Mesures de l'atelier Calepinage, avec cliquet sur une base committée.
// Mesure : (a) contrôles visibles au premier écran, (b) tailles de texte
// distinctes, (c) cibles interactives < 44 px, (d) gestes lead -> production.
// `CAL_MESURES_ECRIRE=1` écrit calepinage-mesures-ecran.baseline.json ; sinon
// la spec échoue si une mesure dépasse la base (la base ne remonte qu'à la main).
// Sans base committée la spec est rouge (voulu : test rouge d'abord).
import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { uniq, API_DJANGO, lireJson, telephoneMobileUnique } from './helpers'

const here = dirname(fileURLToPath(import.meta.url))
const BASE = join(here, 'calepinage-mesures-ecran.baseline.json')
const ECRIRE = process.env.CAL_MESURES_ECRIRE === '1'
// ACAL1286/ACAL1293 — plafonds de la MAQUETTE (Main.dc.html, étape Toit en guidé) : constantes du plan, jamais lues de la base
// (la base est un cliquet qui ne peut que descendre ; elle ne doit pas non plus rester au-dessus de la maquette).
const PLAFOND_MAQUETTE = { controles: 33, tailles_texte: 6 }
const CLES = ['controles_visibles', 'tailles_texte_distinctes', 'cibles_sous_44px', 'gestes_lead_production']

// Atelier mesuré sur le FOND DE REPLI (ACAL377), comme acceptation/acal6.spec.js::carteRefusee :
// le runner n'a pas de clé MapTiler, la base est donc `carte_disponible: false`.
async function carteRefusee(context) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal385', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

// ── ACAL478 : mesure du premier écran, partagée par les deux cas ──
async function mesurerPremierEcran(page) {
  return page.evaluate(() => {
    const SEL = 'button, a[href], input, select, textarea, [role=tab]'
    const vw = window.innerWidth
    const vh = window.innerHeight
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw
    }
    return [...document.querySelectorAll(SEL)].filter(visible).length
  })
}

// La base se met à jour par FUSION : chaque cas n'écrit que sa part.
function lireBase() {
  return existsSync(BASE) ? JSON.parse(readFileSync(BASE, 'utf8')) : {}
}
function fusionnerBase(part) {
  writeFileSync(BASE, `${JSON.stringify({ ...lireBase(), ...part }, null, 2)}
`)
}

// ── ACAL1189 : mesure par étape du mode guidé, partagée par le test et sa garde ──
const SEL_CONTROLES = 'button, a[href], input, select, textarea, [role=tab]'
// Onglets visibles du rail et contrôles visibles du panneau ouvert (sans limite de hauteur : on compte
// des éléments, jamais des pixels — la mesure ne dépend d'aucune police).
async function mesurerEtapeOuverte(page) {
  return page.evaluate((sel) => {
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
    }
    const rail = document.querySelector('[data-testid="cal-rail-onglets"]')
    // Coque (22/11) : l'écran d'une étape guidée est le PANNEAU D'ÉTAPE (`cal-panneau-etape`, absent des étapes
    // pleines) et/ou l'écran monté dans l'hôte `cal-onglet-panneau` (`display: contents`, sans boîte propre) :
    // on compte l'UNION des contrôles visibles des deux, sans double compte.
    const regions = [
      document.querySelector('[data-testid="cal-panneau-etape"]'),
      document.querySelector('[data-testid="cal-onglet-panneau"]'),
    ].filter(Boolean)
    const controles = new Set()
    for (const region of regions) for (const el of region.querySelectorAll(sel)) if (visible(el)) controles.add(el)
    return {
      onglets: rail ? [...rail.querySelectorAll('[role=tab]')].filter(visible).length : 0,
      controles_panneau: controles.size,
    }
  }, SEL_CONTROLES)
}

// Réseau « calme » : aucune requête en vol depuis `calmeMs`. Un panneau d'étape charge son code puis ses
// données en plusieurs temps après le clic : `networkidle` seul rendrait la main avant le premier appel.
function suivreReseau(page) {
  const etat = { enCours: 0, dernier: Date.now() }
  const fin = () => { etat.enCours = Math.max(0, etat.enCours - 1); etat.dernier = Date.now() }
  page.on('request', () => { etat.enCours += 1; etat.dernier = Date.now() })
  page.on('requestfinished', fin)
  page.on('requestfailed', fin)
  return etat
}
async function attendreCalme(etat, calmeMs = 1500) {
  await expect.poll(() => etat.enCours === 0 && Date.now() - etat.dernier >= calmeMs,
    { intervals: [250], timeout: 90_000 }).toBe(true)
}

// Lit la même valeur quatre fois de suite (2 s) avant de la retenir : un panneau charge ses données après le
// clic (le réseau peut être lent) et une lecture trop tôt compterait un squelette, pas l'écran.
async function lireStable(lire) {
  let precedent = null
  let egales = 0
  await expect.poll(async () => {
    const v = JSON.stringify(await lire())
    egales = v === precedent ? egales + 1 : 0
    precedent = v
    return egales
  }, { intervals: [500], timeout: 60_000 }).toBeGreaterThanOrEqual(4)
  return JSON.parse(precedent)
}

// Étapes du rail : lues de la page (boutons `cal-etape-<cle>`, hors `-etat` / `-ecran`), jamais recopiées.
async function clesEtapesDuRail(page) {
  return page.evaluate(() => [...document.querySelectorAll('[data-testid="cal-rail-etapes"] [data-testid^="cal-etape-"]')]
    .map((el) => el.getAttribute('data-testid').replace('cal-etape-', ''))
    .filter((cle) => !/-(etat|ecran)$/.test(cle)))
}

// Écarts à la base : une ligne par grandeur au-dessus de sa valeur, qui NOMME l'étape et la grandeur.
function ecartsParEtape(mesure, basePar) {
  const ecarts = []
  for (const [cle, valeurs] of Object.entries(mesure)) {
    for (const [grandeur, v] of Object.entries(valeurs)) {
      const ref = basePar?.[cle]?.[grandeur]
      if (ref === undefined) ecarts.push(`étape « ${cle} » : ${grandeur} absente de la base (CAL_MESURES_ECRIRE=1)`)
      else if (v > ref) ecarts.push(`étape « ${cle} » : ${grandeur} ${v} dépasse la base ${ref}`)
    }
  }
  return ecarts
}

// ── ACAL989 : matrice de visibilité des six éléments d'action, par appareil et par moment ──
const APPAREILS = [
  { cle: '1440x900', largeur: 1440, hauteur: 900 },
  { cle: '390x844', largeur: 390, hauteur: 844 },
]
const testid = (id) => `[data-testid="${id}"]`
// Liste de données : élément -> sélecteur -> moments où il sert (« Générer » devient « Resynchroniser » une fois le devis lié).
const ELEMENTS_ACTION = [
  { cle: 'consigne', nom: 'consigne de tracé', css: '#rp9-etat-vide', moments: ['avant_trace'] },
  { cle: 'terminer', nom: '« Terminer le tracé »', css: '#rp9-finish', moments: ['avant_trace'] },
  { cle: 'resume', nom: 'résumé kWc / production', css: testid('cal-resume-atelier'), moments: ['apres_fermeture', 'apres_generer'] },
  { cle: 'enregistrer', nom: '« Enregistrer le calepinage »', css: testid('cal-enregistrer-calepinage'), moments: ['apres_fermeture', 'apres_generer'] },
  { cle: 'generer', nom: '« Générer le devis »', css: testid('cal-generer-devis-haut'), // Coque (22/11) : le bouton doré de la barre du haut (il relaie le bouton du devis, resté sous « Avancé »)
    moments: ['apres_fermeture', 'apres_generer'] },
  { cle: 'rail', nom: 'rail d’étapes', css: testid('cal-rail-etapes'), moments: ['avant_trace', 'apres_fermeture', 'apres_generer'] },
]

// 1 = la boîte de l'élément n'est PAS entièrement dans la fenêtre sans défiler (0 = entièrement visible).
// Un booléen par cellule : un nombre de pixels dépendrait de la police du poste ; la base est un cliquet.
async function mesurerVisibilite(page, moment) {
  const attendus = ELEMENTS_ACTION.filter((e) => e.moments.includes(moment))
  const brut = await page.evaluate((elements) => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    return elements.map(({ cle, css }) => {
      const el = document.querySelector(css)
      if (!el) return { cle, absent: true }
      const r = el.getBoundingClientRect()
      const entier = r.width > 0 && r.height > 0 && r.top >= 0 && r.left >= 0 && r.bottom <= vh && r.right <= vw
      return { cle, hors_ecran: entier ? 0 : 1, haut: Math.round(r.top), gauche: Math.round(r.left) }
    })
  }, attendus.map(({ cle, css }) => ({ cle, css })))
  const absents = brut.filter((b) => b.absent).map((b) => b.cle)
  expect(absents, `moment « ${moment} » : élément(s) absent(s) de la page`).toEqual([])
  const haut = Object.fromEntries(brut.map((b) => [b.cle, b.haut]))
  const gauche = Object.fromEntries(brut.map((b) => [b.cle, b.gauche]))
  if (haut.enregistrer !== undefined) {
    // Coque (22/11) : « Enregistrer » et « Générer le devis » sont dans la MÊME barre du haut : l'ordre de lecture
    // est alors la gauche (même rangée à 24 px près) ; sur deux rangées, le haut.
    const memeRangee = Math.abs(haut.enregistrer - haut.generer) < 24
    const precede = memeRangee ? gauche.enregistrer < gauche.generer : haut.enregistrer < haut.generer
    expect(precede, `« Enregistrer » (${gauche.enregistrer}, ${haut.enregistrer} px) doit précéder « Générer » (${gauche.generer}, ${haut.generer} px) — moment « ${moment} »`)
      .toBe(true)
  }
  return Object.fromEntries(brut.map((b) => [b.cle, b.hors_ecran]))
}

// Écarts à la base : nomme l'élément, l'appareil et le moment.
function ecartsVisibilite(mesure, base) {
  const ecarts = []
  for (const [appareil, moments] of Object.entries(mesure)) {
    for (const [moment, elements] of Object.entries(moments)) {
      for (const [cle, v] of Object.entries(elements)) {
        const ref = base?.[appareil]?.[moment]?.[cle]
        const nom = ELEMENTS_ACTION.find((e) => e.cle === cle)?.nom ?? cle
        if (ref === undefined) ecarts.push(`${nom} à ${appareil}, moment « ${moment} » : absent de la base (CAL_MESURES_ECRIRE=1)`)
        else if (v > ref) ecarts.push(`${nom} à ${appareil}, moment « ${moment} » : hors de la première hauteur d’écran (base : visible)`)
      }
    }
  }
  return ecarts
}

// Lead + calepinage créés par l'API (plus fiable que le formulaire sous charge). `layout` = document du
// contrat roof_layout_v2 : le toit est posé PAR L'API, jamais tracé à la souris — sur le fond de repli
// (carte sans position GPS) un tracé à la souris ne pose aucun panneau (« Surface trop petite pour une
// rangée »), or cette garde juge la visibilité des éléments de l'atelier, pas le geste de tracé.
const CAL = `${API_DJANGO}/calepinage`
const SCHEMA_LAYOUT = join(here, '../../backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json')
async function calepinageParApi(request, prefixe, { layout = false } = {}) {
  const T = { timeout: 120_000 }
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T,
    data: { nom: uniq(prefixe), ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '800' },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq(prefixe) } }), 'calepinage')
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  if (layout) {
    const lu = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
    const document = JSON.parse(readFileSync(SCHEMA_LAYOUT, 'utf8')).exemple
    await lireJson(await request.post(`${CAL}/calepinages/${cal.id}/layout/`, {
      ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: document },
    }), 'écriture du layout')
  }
  return cal.id
}

// Les appels d'API partent des cookies du contexte : on charge d'abord une page de l'application, qui renouvelle
// un jeton expiré (le formulaire de leads n'a rien à faire dans ce rôle).
async function amorcerSession(page) {
  await page.goto('/apps')
  await expect(page.getByRole('heading', { name: 'Mes applications' })).toBeVisible({ timeout: 30_000 })
}

async function ouvrirAtelier(page, id, appareil) {
  await page.setViewportSize({ width: appareil.largeur, height: appareil.hauteur })
  await page.goto(`/calepinage/${id}`)
  await expect.poll(() => page.evaluate(() => Boolean(window.__taqinorRoofBooted)), { timeout: 240_000 }).toBe(true)
  await expect(page.getByTestId('cal-rail-etapes')).toBeVisible() // Coque (22/11) : le rail des étapes
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await page.waitForLoadState('networkidle').catch(() => {})
}

// ACAL1824 — K-COUCHE-FIXE (docs/audits/l5-calepinage/T2/classes/K-COUCHE-FIXE.md) : aucune pièce fixe ou flottante ne
// recouvre une réponse, une consigne ou une commande. `document.elementFromPoint` au centre de l'élément rend l'élément
// lui-même ou un descendant ; un centre hors de la fenêtre (null) est lui aussi refusé : la réponse doit être EN VUE.
const TAILLES_COUCHE = [
  { cle: '1440x900', largeur: 1440, hauteur: 900 },
  { cle: '1180x820', largeur: 1180, hauteur: 820 },
  { cle: '390x664', largeur: 390, hauteur: 664 },
]
// Les éléments visibles de `css` dont le centre est recouvert (ou hors fenêtre) : une ligne par élément, qui le NOMME,
// et le nombre d'éléments réellement mesurés (une garde qui ne mesure rien ne prouve rien : le test exige au moins un).
async function recouverts(page, css, { defiler = false } = {}) {
  const cibles = page.locator(css)
  const n = await cibles.count()
  const fautes = []
  let mesures = 0
  for (let i = 0; i < n; i += 1) {
    const el = cibles.nth(i)
    if (!(await el.isVisible())) continue
    mesures += 1
    if (defiler) await el.scrollIntoViewIfNeeded()
    const lecture = await el.evaluate((node) => {
      const r = node.getBoundingClientRect()
      const x = r.left + r.width / 2
      const y = r.top + r.height / 2
      const dessus = document.elementFromPoint(x, y)
      return {
        ok: Boolean(dessus) && (dessus === node || node.contains(dessus)),
        y: Math.round(y),
        vh: window.innerHeight,
        dessus: dessus ? `${dessus.tagName.toLowerCase()}${dessus.dataset?.testid ? `[${dessus.dataset.testid}]` : ''}` : 'hors fenêtre',
      }
    })
    if (!lecture.ok) fautes.push(`${css} #${i + 1} : centre à y ${lecture.y} sur ${lecture.vh}, recouvert par ${lecture.dessus}`)
  }
  return { fautes, mesures }
}

test('ACAL1824: la garde K-COUCHE-FIXE nomme l’élément recouvert', async ({ page }) => {
  await page.setContent('<button id="a" style="position:fixed;top:10px;left:10px;width:80px;height:40px">A</button>'
    + '<div style="position:fixed;top:0;left:0;width:200px;height:100px"></div>'
    + '<button id="b" style="position:fixed;top:300px;left:10px;width:80px;height:40px">B</button>')
  const a = await recouverts(page, '#a')
  const b = await recouverts(page, '#b')
  expect(a.fautes).toHaveLength(1)
  expect(a.mesures).toBe(1)
  expect(b.fautes).toEqual([])
  expect(b.mesures).toBe(1)
  expect((await recouverts(page, '#absent')).mesures).toBe(0)
})

// Tout ce qui suit joue sur la pile : en série, un test rouge fait sauter les suivants. Les plafonds de la maquette
// (sans pile) sont dans un groupe à part, en fin de fichier, pour qu'un plafond rouge n'éteigne aucune autre garde.
test.describe('sur la pile (série)', () => {
test.describe.configure({ mode: 'serial' })

test('ACAL385: mesures de l’atelier ≤ base committée', async ({ page }) => {
  test.setTimeout(240_000) // le démarrage de l'atelier attend jusqu'à 240 s (voir ci-dessous) : le plafond par défaut de 60 s le coupait avant
  await carteRefusee(page.context())
  let gestes = 0
  const geste = async (action) => { gestes += 1; return action() }

  // Lead créé par l'API (le formulaire dépasse 15 s dès que la liste des leads grossit : instable en CI comme ici) ;
  // les gestes comptés commencent APRÈS, à l'ouverture du calepinage.  await amorcerSession(page)
  const nomLead = uniq('ACAL385 Lead')
  await lireJson(await page.request.post(`${API_DJANGO}/crm/leads/`, {
    timeout: 120_000,
    data: { nom: nomLead, ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: 'residentiel', facture_hiver: '900' },
  }), 'lead')

  // ── gestes : du lead à la production lue ──
  await page.goto('/calepinage/nouveau')
  await geste(() => page.getByRole('tab', { name: 'Lead' }).click())
  await geste(() => page.locator('#cal-nouveau-lead').getByRole('combobox').click())
  await geste(() => page.getByRole('searchbox').fill(nomLead))
  await geste(() => page.getByRole('option', { name: new RegExp(nomLead) }).first().click())
  await geste(() => page.locator('#cal-nouveau-nom').fill(uniq('ACAL385 Toiture')))
  await geste(() => page.getByRole('button', { name: 'Créer le calepinage' }).click())
  await expect(page).toHaveURL(/\/calepinage\/\d+/)
  await expect(page.getByTestId('cal-rail-etapes')).toBeVisible() // Coque (22/11) : le rail des étapes
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })
  await expect(page.locator('#rp9-status')).not.toHaveText(/^Chargement/)
  await page.waitForLoadState('networkidle').catch(() => {})

  const carte = false // fond de repli forcé (cf. carteRefusee)

  // ── (a)(b)(c) : premier écran de l'atelier, sans scroll ──
  const mesures = await page.evaluate(() => {
    const SEL = 'button, a[href], input, select, textarea, [role=tab]'
    const vw = window.innerWidth
    const vh = window.innerHeight
    const visible = (el) => {
      const r = el.getBoundingClientRect()
      const cs = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'
        && r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw
    }
    const ctrls = [...document.querySelectorAll(SEL)].filter(visible)
    const tailles = new Set()
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.nodeValue.trim() || !n.parentElement || !visible(n.parentElement)) continue
      tailles.add(getComputedStyle(n.parentElement).fontSize)
    }
    const petits = ctrls.filter((el) => {
      const r = el.getBoundingClientRect()
      return Math.min(r.width, r.height) < 44
    })
    return { controles_visibles: ctrls.length, tailles_texte_distinctes: tailles.size, cibles_sous_44px: petits.length }
  })

  // ── (d) production lue ──
  // Coque (22/11) : l'étape Résultats ouvre elle-même la production (plus de rail d'onglets en guidé) — un geste de moins.
  await geste(() => page.getByTestId('cal-etape-resultats').click())
  await expect(page).toHaveURL(/onglet=production/)
  await expect(page.getByTestId('cal-onglet-panneau')).toBeAttached()

  const actuel = { carte_disponible: carte, ...mesures, gestes_lead_production: gestes }

  if (ECRIRE) {
    fusionnerBase(actuel) // fusion : les sections des autres cas (mode_guide, visibilite) sont gardées
    return
  }
  expect(existsSync(BASE), 'base absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  const base = JSON.parse(readFileSync(BASE, 'utf8'))
  test.skip(base.carte_disponible !== carte,
    `base mesurée avec carte_disponible=${base.carte_disponible}, cet environnement l’a à ${carte} : mesures non comparables`)
  for (const cle of CLES) {
    expect(actuel[cle], `${cle} : ${actuel[cle]} dépasse la base ${base[cle]}`).toBeLessThanOrEqual(base[cle])
  }
})

// ACAL989 — l'action suivante et le chiffre résultat restent dans la PREMIÈRE hauteur d'écran, à 1440×900
// et 390×844, aux moments où ils servent : avant le tracé, après la fermeture du toit (posé par l'API), après
// « Générer le devis ». La base `visibilite` est un cliquet : un élément visible ne peut plus sortir de l'écran.
test('ACAL989: les six éléments d’action restent dans la première hauteur d’écran', async ({ page }) => {
  test.setTimeout(600_000)
  await carteRefusee(page.context())
  await amorcerSession(page)
  const vide = await calepinageParApi(page.request, 'ACAL989 Vide')

  const mesure = {}
  for (const appareil of APPAREILS) {
    const m = {}
    // Un calepinage neuf par appareil : « Générer » y part du même état (aucun devis lié).
    const trace = await calepinageParApi(page.request, 'ACAL989 Toit', { layout: true })
    await ouvrirAtelier(page, vide, appareil)
    await expect(page.locator('#rp9-etat-vide')).toBeVisible()
    m.avant_trace = await mesurerVisibilite(page, 'avant_trace')

    await ouvrirAtelier(page, trace, appareil)
    await expect(page.getByTestId('cal-resume-panneaux')).toHaveText(/^[1-9]\d*\s+panneau/)
    await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
      .toBeEnabled({ timeout: 240_000 })
    m.apres_fermeture = await mesurerVisibilite(page, 'apres_fermeture')

    // « Générer le devis » : on attend la RÉPONSE du serveur (devis créé ou refus qui nomme le champ ; son statut
    // est noté en annotation), puis on rouvre l'atelier depuis le serveur : l'état mesuré ne dépend pas de ce que
    // le catalogue a répondu.
    const generer = page.getByTestId('cal-generer-devis-haut')
    if (await generer.count() > 0) {
      const reponse = page.waitForResponse((r) => /generer-devis/.test(r.url()) && r.request().method() === 'POST', { timeout: 60_000 })
        .then((r) => r.status(), () => 'sans réponse')
      await generer.scrollIntoViewIfNeeded()
      await generer.click()
      test.info().annotations.push({ type: `generer_${appareil.cle}`, description: String(await reponse) })
    }
    await ouvrirAtelier(page, trace, appareil)
    m.apres_generer = await mesurerVisibilite(page, 'apres_generer')
    mesure[appareil.cle] = m
  }

  if (ECRIRE) {
    fusionnerBase({ visibilite: mesure })
    return
  }
  const base = lireBase().visibilite
  expect(base, 'section visibilite absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  expect(ecartsVisibilite(mesure, base), 'élément(s) hors de la première hauteur d’écran').toEqual([])
})

// ACAL989/ACAL1189 — la garde elle-même : sans pile, une valeur au-dessus de la base DOIT être refusée en nommant
// l'élément (ou l'étape) et la grandeur — sinon la garde ne garderait rien.
test('ACAL989+ACAL1189: la comparaison à la base échoue en nommant élément, appareil, étape et grandeur', () => {
  const base = { '390x844': { avant_trace: { terminer: 0, rail: 1 } } }
  const ecarts = ecartsVisibilite({ '390x844': { avant_trace: { terminer: 1, rail: 1 } } }, base)
  expect(ecarts).toHaveLength(1)
  expect(ecarts[0]).toContain('« Terminer le tracé » à 390x844')
  expect(ecarts[0]).toContain('avant_trace')
  expect(ecartsVisibilite({ '390x844': { avant_trace: { terminer: 0, rail: 1 } } }, base)).toEqual([])
  const basePar = { resultats: { onglets: 3, controles_panneau: 20 } }
  const ecartsEtape = ecartsParEtape({ resultats: { onglets: 4, controles_panneau: 20 } }, basePar)
  expect(ecartsEtape).toEqual(['étape « resultats » : onglets 4 dépasse la base 3'])
  expect(ecartsParEtape({ resultats: { onglets: 3, controles_panneau: 20 } }, basePar)).toEqual([])
})

// ACAL478 — budget de simplicité du MODE GUIDÉ (mode expert éteint, par défaut).
// Seuls les « 5 étapes » viennent du squelette du complément ; tous les autres
// seuils sont LUS dans `mode_guide` de la base (mesurés, jamais tapés ici).
test('ACAL478: budget du mode guidé', async ({ page }) => {
  test.setTimeout(240_000)
  await carteRefusee(page.context())
  await amorcerSession(page)
  // Lead + calepinage par l'API (le formulaire de lead dépasse parfois 15 s sous charge : ce n'est pas ce que
  // ce cas mesure ; le chemin par formulaire reste joué par ACAL385).
  const id = await calepinageParApi(page.request, 'ACAL478')
  await ouvrirAtelier(page, id, { largeur: 1280, hauteur: 720 })
  await expect(page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }))
    .toBeEnabled({ timeout: 240_000 })

  // Le mode expert est éteint (état d'un utilisateur neuf).
  await expect(page.getByTestId('cal-mode-expert')).not.toBeChecked()

  // Coque (22/11) : le rail porte aussi « Avancé » (feuille, pas une étape) : on ne compte que les boutons `cal-etape-<cle>`.
  const etapes = (await clesEtapesDuRail(page)).length
  const controles = await mesurerPremierEcran(page)

  // ACAL1189 — chaque étape du rail, ouverte tour à tour : onglets visibles + contrôles du panneau ouvert.
  const cles = await clesEtapesDuRail(page)
  expect(cles, 'étapes du rail (budget : 5)').toHaveLength(5)
  const parEtape = {}
  const reseau = suivreReseau(page)
  for (const cle of cles) {
    await page.getByTestId(`cal-etape-${cle}`).click()
    await expect(page.getByTestId(`cal-etape-${cle}`)).toHaveAttribute('aria-current', 'step')
    await attendreCalme(reseau)
    parEtape[cle] = await lireStable(() => mesurerEtapeOuverte(page))
  }

  if (ECRIRE) {
    let commit = process.env.GITHUB_SHA || ''
    if (!commit) { try { commit = execSync('git rev-parse HEAD').toString().trim() } catch { commit = 'inconnu' } }
    fusionnerBase({
      mode_guide: {
        ...lireBase().mode_guide,
        mesure_le: new Date().toISOString().slice(0, 10),
        commit_mesure: commit,
        etapes,
        controles_premier_ecran: controles,
        par_etape: parEtape,
      },
    })
  }

  // Chemin lead -> production : AUCUNE saisie, aucun détour par `fiches`/`reglages`.
  // Coque (22/11) : l'étape Résultats ouvre elle-même la production (plus de rail d'onglets en guidé).
  await page.getByTestId('cal-etape-resultats').click()
  await expect(page).toHaveURL(/onglet=production/)
  await expect(page.getByTestId('cal-onglet-panneau')).toBeAttached()
  for (const cle of ['fiches', 'reglages']) {
    await expect(page.locator(`[data-testid="cal-onglet-${cle}"][aria-selected="true"]`),
      `l'onglet ${cle} ne doit pas être requis avant un premier résultat`).toHaveCount(0)
  }

  expect(etapes, `le mode guidé compte ${etapes} étapes (budget : 5)`).toBeLessThanOrEqual(5)
  const base = lireBase().mode_guide
  expect(base, 'section mode_guide absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  expect(controles, `contrôles du premier écran : ${controles} dépasse la base ${base.controles_premier_ecran}`)
    .toBeLessThanOrEqual(base.controles_premier_ecran)
  expect(base.par_etape, 'mode_guide.par_etape absente : lancer une fois avec CAL_MESURES_ECRIRE=1 puis committer le JSON').toBeTruthy()
  expect(ecartsParEtape(parEtape, base.par_etape), 'étape(s) du mode guidé au-dessus de leur base').toEqual([])
})

// ACAL1442 — panneau Expert de l'étape Toit : étiquettes au-dessus des champs, boutons d'environnement DANS le
// panneau, totaux et boutons de la liste des pans sans chevauchement (≥ 44 px de cible). Mesure DOM, jamais de pixel.
const rectsSeChevauchent = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1
function chevauchements(boites) {
  const noms = Object.keys(boites)
  const ecarts = []
  for (let i = 0; i < noms.length; i += 1) {
    for (let j = i + 1; j < noms.length; j += 1) {
      if (rectsSeChevauchent(boites[noms[i]], boites[noms[j]])) ecarts.push(`${noms[i]} chevauche ${noms[j]}`)
    }
  }
  return ecarts
}

test('ACAL1442: la garde de chevauchement nomme les deux boîtes qui se recouvrent', () => {
  const a = { left: 0, top: 0, right: 100, bottom: 44 }
  expect(chevauchements({ totaux: a, bouton: { left: 50, top: 20, right: 150, bottom: 64 } })).toEqual(['totaux chevauche bouton'])
  expect(chevauchements({ totaux: a, bouton: { left: 100, top: 0, right: 200, bottom: 44 } })).toEqual([])
})

test('ACAL1442: panneau Expert de l’étape Toit à 1440 × 900 — rien ne se chevauche, rien ne déborde', async ({ page }) => {
  test.setTimeout(600_000)
  await carteRefusee(page.context())
  await amorcerSession(page)
  const id = await calepinageParApi(page.request, 'ACAL1442 Toit', { layout: true })
  await ouvrirAtelier(page, id, APPAREILS[0])
  await page.getByTestId('cal-barre-projet').getByRole('button', { name: 'Expert' }).click()
  await page.locator('#rp9-setback-parapet').scrollIntoViewIfNeeded()
  const mesure = await page.evaluate(() => {
    const boite = (el) => {
      const r = el.getBoundingClientRect()
      return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, h: r.height, w: r.width }
    }
    const champ = document.getElementById('rp9-setback-parapet')
    const etiquette = champ?.closest('label')
    const panneauEnv = document.getElementById('rp9-env-panel')
    const lignes = [...document.querySelectorAll('#rp9-areas-list [data-area-row]')]
    return {
      etiquetteAuDessus: Boolean(champ && etiquette) && etiquette.getBoundingClientRect().top <= champ.getBoundingClientRect().top - 8,
      env: panneauEnv ? [...panneauEnv.querySelectorAll('.rp9-btn')].map((b) => ({ ...boite(b), panneauDroite: panneauEnv.getBoundingClientRect().right })) : [],
      totaux: [...document.querySelectorAll('#rp9-areas-window dd')].map(boite),
      lignes: lignes.map((l) => [...l.querySelectorAll('button')].map(boite)),
    }
  })
  expect(mesure.etiquetteAuDessus, '« Retrait d’acrotère » doit être au-dessus de son champ').toBe(true)
  for (const b of mesure.env) expect(b.right, 'bouton d’environnement hors du panneau').toBeLessThanOrEqual(b.panneauDroite + 1)
  expect(chevauchements(Object.fromEntries(mesure.totaux.map((b, i) => [`total ${i + 1}`, b]))), 'totaux de la liste des pans').toEqual([])
  for (const [i, boutons] of mesure.lignes.entries()) {
    expect(chevauchements(Object.fromEntries(boutons.map((b, j) => [`pan ${i + 1} bouton ${j + 1}`, b]))), `boutons du pan ${i + 1}`).toEqual([])
    for (const b of boutons) expect(b.h, `cible du pan ${i + 1}`).toBeGreaterThanOrEqual(44)
  }
})

// ACAL1818 — le curseur « Heure du soleil » de l'étape Panneaux se touche sur 44 px (pointeur grossier, 390 × 844). Mesure
// DOM : la zone du champ, jamais sa piste dessinée (6 px). Écrit pour la CI ; la vue client a le même curseur (58-telephone.css).
test('ACAL1818: curseur « Heure du soleil » ≥ 44 px de haut à 390 × 844 (pointeur grossier)', async ({ browser }) => {
  test.setTimeout(600_000)
  const contexte = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, deviceScaleFactor: 3 })
  try {
    const page = await contexte.newPage()
    await carteRefusee(contexte)
    await amorcerSession(page)
    const id = await calepinageParApi(page.request, 'ACAL1818 Soleil', { layout: true })
    await ouvrirAtelier(page, id, APPAREILS[1])
    await page.getByTestId('cal-etape-panneaux').click()
    const curseur = page.locator('.cal-pan-heure[aria-label="Heure du soleil"]').first()
    await curseur.scrollIntoViewIfNeeded()
    const boite = await curseur.boundingBox()
    expect(boite, 'curseur Heure du soleil monté').toBeTruthy()
    expect(boite.height, 'zone tactile du curseur').toBeGreaterThanOrEqual(44)
  } finally {
    await contexte.close()
  }
})

// ACAL1817 — le relevé de visite occupe la tablette (1180 × 820, tactile) : la carte du toit et les photos dans la colonne
// de gauche, les mesures dans celle de droite, la barre du bas sur toute la largeur ; à 390 px le relevé reste une seule
// colonne (la feuille du bas). Mesure DOM des boîtes : aucune moitié de l'écran n'est vide.
test('ACAL1817: relevé à 1180 × 820 — deux colonnes, barre du bas pleine largeur ; à 390 px une seule colonne', async ({ browser }) => {
  test.setTimeout(300_000)
  const contexte = await browser.newContext({ viewport: { width: 1180, height: 820 }, hasTouch: true, isMobile: true })
  try {
    const page = await contexte.newPage()
    await amorcerSession(page)
    const id = await calepinageParApi(page.request, 'ACAL1817 Relevé', { layout: true })
    const boites = () => page.evaluate(() => {
      const b = (sel) => {
        const r = document.querySelector(sel)?.getBoundingClientRect()
        return r ? { x: Math.round(r.x), y: Math.round(r.y), l: Math.round(r.width), h: Math.round(r.height) } : null
      }
      return {
        carte: b('[data-testid="releve-carte-toit"]'), photos: b('[data-testid="releve-photos"]'),
        mesures: b('[data-testid="releve-mesures"]'), pied: b('.cal-tel-pied'),
        vw: window.innerWidth, debordement: document.documentElement.scrollWidth - window.innerWidth,
      }
    })
    await page.goto(`/calepinage/${id}/releve`)
    await expect(page.getByTestId('releve-mesures')).toBeVisible({ timeout: 120_000 })
    const t = await boites()
    expect(t.carte.x, 'carte du toit : colonne de gauche').toBe(0)
    expect(t.carte.l, 'carte du toit : la moitié gauche').toBeGreaterThanOrEqual(t.vw / 2 - 2)
    expect(t.photos.x + t.photos.l, 'photos : dans la colonne de gauche').toBeLessThanOrEqual(t.vw / 2 + 2)
    expect(t.mesures.x, 'mesures : colonne de droite').toBeGreaterThanOrEqual(t.vw / 2 - 2)
    expect(t.pied.x, 'barre du bas : depuis le bord gauche').toBe(0)
    expect(t.pied.l, 'barre du bas : toute la largeur').toBe(t.vw)
    expect(t.debordement, 'défilement horizontal').toBeLessThanOrEqual(0)
    // À 390 px rien ne change : la feuille du bas, une colonne.
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByTestId('releve-poignee')).toBeVisible()
    const m = await boites()
    expect(m.mesures.x, 'mesures à 390 px : colonne unique').toBeLessThan(40)
    expect(m.debordement, 'défilement horizontal à 390 px').toBeLessThanOrEqual(0)
  } finally {
    await contexte.close()
  }
})

test('ACAL1824: K-COUCHE-FIXE — rien ne recouvre consigne, réponse, commande, à 1440 × 900, 1180 × 820 et 390 × 664', async ({ page }) => {
  test.setTimeout(900_000)
  await carteRefusee(page.context())
  await amorcerSession(page)
  const vide = await calepinageParApi(page.request, 'ACAL1824 Vide')
  const trace = await calepinageParApi(page.request, 'ACAL1824 Toit', { layout: true })
  const fautes = []
  const noter = (ecran, taille, { fautes: liste, mesures }) => {
    if (mesures < 1) fautes.push(`${ecran} à ${taille.cle} — aucun élément mesuré : la garde n'a rien vérifié`)
    fautes.push(...liste.map((f) => `${ecran} à ${taille.cle} — ${f}`))
  }
  for (const taille of TAILLES_COUCHE) {
    // Atelier, étape Toit, avant le tracé : la consigne et « Terminer le tracé ».
    await ouvrirAtelier(page, vide, taille)
    await expect(page.locator('#rp9-etat-vide')).toBeVisible()
    noter('atelier Toit (avant le tracé)', taille, await recouverts(page, '#rp9-etat-vide, #rp9-finish'))

    // Atelier, toit posé : résumé, barre d'enregistrement, « Générer le devis », bouton de pied de l'étape.
    await ouvrirAtelier(page, trace, taille)
    await expect(page.getByTestId('cal-resume-panneaux')).toHaveText(/^[1-9]\d*\s+panneau/)
    const commandes = '[data-testid="cal-enregistrer-calepinage"] button, [data-testid="cal-generer-devis-haut"], [data-testid="cal-action-etape-suivante"]'
    noter('atelier Toit (toit posé)', taille, await recouverts(page, `[data-testid="cal-resume-atelier"], ${commandes}`, { defiler: true }))
    await page.getByTestId('cal-etape-panneaux').click()
    await expect(page.getByTestId('cal-etape-panneaux')).toHaveAttribute('aria-current', 'step')
    noter('atelier Panneaux', taille, await recouverts(page, commandes, { defiler: true }))

    // Horizon (Expert) : le message d'enregistrement ne recouvre pas la commande.
    await page.goto(`/calepinage/${trace}?onglet=horizon&mode=expert`)
    await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 120_000 })
    noter('Horizon', taille, await recouverts(page, '[data-testid="cal-horizon"] button, [data-testid="cal-horizon"] [role="status"]', { defiler: true }))

    // Relevé de visite : « Terminer le relevé » puis sa réponse, qui doit rester au-dessus de la barre du bas.
    await page.goto(`/calepinage/${trace}/releve`)
    await expect(page.getByTestId('releve-mesures')).toBeVisible({ timeout: 120_000 })
    const terminer = page.getByTestId('releve-terminer')
    await expect(terminer, 'le bouton « Terminer le relevé » est toujours dans le pied du relevé').toBeVisible()
    await terminer.click()
    await expect(page.getByTestId('releve-message')).toBeVisible({ timeout: 60_000 })
    noter('relevé après Terminer', taille, await recouverts(page, '[data-testid="releve-message"], [data-testid="releve-terminer"]'))

    // Vue client : messages et commandes de la page.
    await page.goto(`/calepinage/${trace}/client`)
    await expect(page.locator('[data-testid^="client-"]').first()).toBeVisible({ timeout: 120_000 })
    noter('vue client', taille, await recouverts(page, '[data-testid^="client-"] button, [data-testid^="client-"][role="status"], [data-testid="client-lien-raison"]', { defiler: true }))
  }
  expect(fautes, 'pièce fixe ou flottante qui recouvre une réponse, une consigne ou une commande').toEqual([])
})

// ACAL1819 — liste des calepinages au téléphone (390 × 664) : titre + « + » 44 × 44 sur une ligne, pastilles d'état derrière
// « Filtres », le nom de la première carte dans le premier écran. Mesure DOM des boîtes, jamais un pixel. Écrit pour la CI.
test('ACAL1819: liste à 390 × 664 — le nom de la première carte est dans le premier écran', async ({ page }) => {
  test.setTimeout(300_000)
  await amorcerSession(page)
  await calepinageParApi(page.request, 'ACAL1819 Liste')
  await page.setViewportSize({ width: 390, height: 664 })
  await page.goto('/calepinage')
  const nom = page.locator('.cliste-carte .cliste-nom').first()
  await expect(nom).toBeVisible({ timeout: 120_000 })
  const boite = await nom.boundingBox()
  expect(boite.y + boite.height, 'bas du nom de la première carte sur 664').toBeLessThanOrEqual(664)
  const plus = await page.getByRole('button', { name: /Nouveau calepinage/ }).boundingBox()
  expect(plus.width, '« + » : largeur').toBeGreaterThanOrEqual(44)
  expect(plus.width, '« + » : pas pleine largeur').toBeLessThan(80)
  const titre = await page.locator('.cliste-titre').boundingBox()
  expect(Math.abs((plus.y + plus.height / 2) - (titre.y + titre.height / 2)), '« + » et titre sur la même ligne').toBeLessThan(24)
  await expect(page.getByTestId('cal-liste-filtres-etat')).toBeHidden()
  await page.getByTestId('acal957-filtres-basculer').click()
  await expect(page.getByTestId('cal-liste-filtres-etat')).toBeVisible()
})
})

test.describe('plafond de la maquette (sans pile, hors série)', () => {
// ACAL1286/ACAL1293 — la base committée elle-même tient sous la maquette (sans pile : lit le JSON). Rouge tant que la base
// relevée sur l'ancienne coque dit 34 / 36 contrôles ; l'orchestrateur la relève (`CAL_MESURES_ECRIRE=1`) sur la pile.
test('ACAL1286+ACAL1293: la base de mesures tient sous la maquette (≤ 33 contrôles, ≤ 6 tailles de texte)', () => {
  const base = lireBase()
  expect(base.controles_visibles, 'base : contrôles visibles à l’arrivée').toBeLessThanOrEqual(PLAFOND_MAQUETTE.controles)
  expect(base.mode_guide?.controles_premier_ecran, 'base : contrôles du premier écran guidé').toBeLessThanOrEqual(PLAFOND_MAQUETTE.controles)
  expect(base.tailles_texte_distinctes, 'base : tailles de texte').toBeLessThanOrEqual(PLAFOND_MAQUETTE.tailles_texte)
})
})

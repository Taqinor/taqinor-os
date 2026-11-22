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

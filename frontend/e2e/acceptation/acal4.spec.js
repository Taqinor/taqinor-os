// ACAL — 4e spec d'acceptation en direct : ACAL366 (PA2.3 — une pente écrite par l'onglet Pente est appliquée au pan
// VIVANT de l'atelier et gardée par « Enregistrer le calepinage ») et ACAL367 (PA2.3 + PA2.5 — un calepinage rouvert AVEC
// sa production enregistrée, puis ombré par l'onglet Horizon, enregistre la production DÉRATÉE). Format : `_format.md`.
// Les deux preuves exigent le CONSTRUCTEUR 3D, qui ne boote qu'avec une clé carte servie par le backend
// (`ventes.selectors_calepinage.config_carte` ← `PUBLIC_MAPTILER_KEY`) : sans elle, l'étape lève NON JOUABLE (FAIL).
// Données propres à chaque étape (lead + calepinage par l'API, noms uniques) ; aucun shell Django.
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import { API_DJANGO, assurerSessionPage, lireJson, telephoneMobileUnique, uniq } from '../helpers.js'

test.describe.configure({ timeout: 900_000 })
// WebGL logiciel (SwiftShader) : la carte MapLibre et la scène 3D en ont besoin sur un hôte sans GPU.
test.use({
  viewport: { width: 1600, height: 1000 },
  actionTimeout: 60_000,
  launchOptions: { args: ['--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--use-angle=swiftshader'] },
})
const etape = groupe('ACAL', ['ACAL366', 'ACAL367'])
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const nonJouable = (raison) => { throw new Error(`NON JOUABLE : ${raison}`) }
const chiffres = (s) => Number(String(s).replace(/[^\d]/g, ''))

// Épingle A au centre d'un contour R d'environ 20 m × 18 m (Casablanca).
const A = { lat: 33.5731, lng: -7.5898 }
const R = [[-7.5899, 33.5732], [-7.5897, 33.5732], [-7.5897, 33.5730], [-7.5899, 33.5730]]

async function creerCalepinage(request, tag) {
  const lead = await lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T,
    data: {
      nom: uniq(tag), ville: 'Casablanca', telephone: telephoneMobileUnique(),
      type_installation: 'residentiel', facture_hiver: '3000', facture_ete: '3000',
    },
  }), 'lead')
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, { ...T, data: { lead: lead.id, titre: uniq(tag) } }), 'calepinage')
  // Premier design-context d'un calepinage neuf lent sur une pile froide : lu une fois ici (délai 120 s).
  const ctx = await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  if (!(ctx.carte?.available && ctx.carte?.maptilerKey)) {
    nonJouable('le backend ne publie aucune clé carte (design-context.carte.available=false) : le constructeur 3D ne boote pas')
  }
  return cal
}

const lireLayout = async (request, id) => lireJson(await request.get(`${CAL}/calepinages/${id}/layout/`, T), 'layout')

/** Écrit le document entier avec le jeton If-Match lu juste avant (ACAL22). */
async function ecrireLayout(request, id, roofLayout) {
  const lu = await lireLayout(request, id)
  return lireJson(await request.post(`${CAL}/calepinages/${id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: roofLayout },
  }), 'écriture du layout')
}

/** Statuts des requêtes MapTiler (clé masquée) : la carte est-elle réellement servie à cette origine ? */
function suivreCarte(page) {
  const statuts = []
  // Diagnostic seulement (les oracles restent ceux du harnais) : avertissements et erreurs hors tuiles refusées.
  page.on('console', (m) => {
    if (!['warning', 'error'].includes(m.type()) || /status of 403/.test(m.text())) return
    console.log(`[console ${m.type()}] ${m.text().replace(/(key|access_token|token)=[^&\s]+/g, '$1=…').slice(0, 300)}`)
  })
  page.on('response', (r) => {
    if (/api\.maptiler\.com|api\.mapbox\.com/.test(r.url())) {
      statuts.push({ url: r.url().replace(/(key|access_token)=[^&]+/g, '$1=…').slice(0, 120), statut: r.status() })
    }
  })
  return statuts
}

/** Ouvre l'atelier et attend la scène HYDRATÉE (bouton d'enregistrement actif, carte servie, production affichée). */
async function ouvrirAtelier(page, id, statutsCarte, onglet = null) {
  await page.goto(`/calepinage/${id}${onglet ? `?onglet=${onglet}` : ''}`)
  await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' }), 'jamais « Carte indisponible »').toHaveCount(0)
  await expect(page.locator('#rp9-map canvas').first(), 'canvas de la carte').toBeVisible({ timeout: 120_000 })
  const bouton = page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ })
  try {
    await expect(bouton, 'scène hydratée').toBeEnabled({ timeout: 240_000 })
  } catch (e) {
    const statut = await page.locator('#rp9-status').innerText().catch(() => '?')
    console.log(`[atelier] scène non hydratée ; #rp9-status : « ${statut} » ; requêtes carte : ${statutsCarte.length}, `
      + `statuts : ${JSON.stringify([...new Set(statutsCarte.map((s) => s.statut))])}`)
    throw e
  }
  await expect(page.locator('#rp9-reco-prod'), 'carte Production chiffrée').toHaveText(/\d/, { timeout: 120_000 })
  const servies = statutsCarte.filter((s) => s.statut < 300)
  const refusees = statutsCarte.filter((s) => s.statut >= 400)
  console.log(`[carte] ${statutsCarte.length} requêtes MapTiler/Mapbox, ${servies.length} < 300, refus : ${JSON.stringify(refusees.slice(0, 5))}`)
  // Les refus de tuiles ne sont PAS excusés : ils restent jugés par l'oracle 3 (console.error), jamais déclarés attendus.
  return bouton
}

/** « Enregistrer le calepinage » (POST layout/, If-Match) puis relecture du document stocké. */
async function enregistrer(page, id, bouton) {
  const ecrit = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${id}/layout/`)
    && x.request().method() === 'POST', T)
  await bouton.click()
  const r = await ecrit
  expect(r.status(), `Enregistrer le calepinage → ${(await r.text()).slice(0, 300)}`).toBeLessThan(300)
  await expect(bouton).toBeEnabled({ timeout: 60_000 })
  return (await lireLayout(page.request, id)).roof_layout
}

const z1 = (doc) => (doc?.zones || []).find((z) => z.id === 'z1')

// ════════════════════════════════════════════════════════════════════════════
// ACAL366 — PA2.3 : pente 35° écrite par l'onglet Pente → pan vivant → « Enregistrer » la garde
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3', ['ACAL366'], async ({ page, suivi }) => {
  const statutsCarte = suivreCarte(page)
  const cal = await creerCalepinage(page.request, 'ACC ACAL366 Pente')
  await ecrireLayout(page.request, cal.id, {
    version: 2, pin: A, activeAreaId: 'z1',
    zones: [{ id: 'z1', label: 'Pan sud', vertices: R, roofType: 'pitched', pitchDeg: 15, facingAzimuthDeg: 180, facingManual: true }],
  })
  // Given : un calepinage enregistré par l'atelier à 15°, puis rouvert.
  let bouton = await ouvrirAtelier(page, cal.id, statutsCarte)
  const doc15 = await enregistrer(page, cal.id, bouton)
  expect(z1(doc15)?.pitchDeg, 'pan z1 enregistré à 15°').toBe(15)
  const prod15 = doc15?.result?.annualKwh
  console.log(`[PA2.3/366] 15° : result.annualKwh=${prod15} zones[z1].result=${JSON.stringify(z1(doc15)?.result)} carte=${await page.locator('#rp9-reco-prod').innerText()}`)

  bouton = await ouvrirAtelier(page, cal.id, statutsCarte, 'pente')
  const carte15 = chiffres(await page.locator('#rp9-reco-prod').innerText())
  // When : l'onglet Pente enregistre 35° (POST layout/section/, cle 'zones').
  await expect(page.getByTestId('cal-pente')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('cal-pente-pan').selectOption('z1')
  await page.getByTestId('cal-pente-mode-degres').click()
  await page.locator('#cal-pente-degres').fill('35')
  await expect(page.getByTestId('cal-pente-valeur')).toContainText('35.0 °')
  const section = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByTestId('cal-pente-enregistrer').click()
  const rs = await section
  expect(rs.status(), `section zones → ${(await rs.text()).slice(0, 300)}`).toBe(200)
  const envoye = rs.request().postDataJSON()
  expect(envoye.cle).toBe('zones')
  expect(envoye.champs.pitchDeg, 'pente envoyée').toBe(35)
  const pitchSource = envoye.champs.pitchSource
  expect(pitchSource, 'provenance de la pente envoyée').toBeTruthy()
  await expect(page.getByTestId('cal-pente-message')).toContainText('Pente enregistrée sur le pan')
  // Le pan VIVANT repart sur 35° : la production affichée est recalculée.
  await expect.poll(async () => chiffres(await page.locator('#rp9-reco-prod').innerText()),
    { message: 'carte Production recalculée sur 35°', timeout: 60_000 }).not.toBe(carte15)
  const carte35 = chiffres(await page.locator('#rp9-reco-prod').innerText())
  console.log(`[PA2.3/366] carte Production 15° → 35° : ${carte15} → ${carte35} ; Pente fine affichée : ${await page.locator('#rp9-pitch-value').innerText().catch(() => '?')}`)

  // Then : « Enregistrer le calepinage » garde 35° et la provenance écrite (jamais l'ancienne pente, sans 409).
  const doc35 = await enregistrer(page, cal.id, bouton)
  expect(z1(doc35)?.pitchDeg, 'zones[z1].pitchDeg après l’enregistrement complet').toBe(35)
  expect(z1(doc35)?.pitchSource, 'zones[z1].pitchSource après l’enregistrement complet').toEqual(pitchSource)
  console.log(`[PA2.3/366] 35° : result.annualKwh=${doc35?.result?.annualKwh} zones[z1].result=${JSON.stringify(z1(doc35)?.result)}`)
  expect(doc35?.result?.annualKwh, 'production enregistrée recalculée sur 35°').not.toBe(prod15)

  // Persistance : rouvrir ⇒ 35° affiché (onglet Pente) et relu ; un nouvel enregistrement sans geste le garde.
  bouton = await ouvrirAtelier(page, cal.id, statutsCarte, 'pente')
  await expect(page.locator('#cal-pente-degres'), 'saisie relue du pan z1').toHaveValue('35')
  await expect(page.getByTestId('cal-pente-valeur'), 'pente retenue affichée').toContainText('35.0 °')
  const relu = await lireLayout(page.request, cal.id)
  expect(z1(relu.roof_layout)?.pitchDeg).toBe(35)
  expect(z1(relu.roof_layout)?.pitchSource).toEqual(pitchSource)
  const docBis = await enregistrer(page, cal.id, bouton)
  expect(z1(docBis)?.pitchDeg, 'rouvert puis enregistré sans geste : 35° gardé').toBe(35)
  expect(z1(docBis)?.pitchSource).toEqual(pitchSource)
  await expect(page.getByTestId('cal-pente-valeur')).toContainText('35.0 °')
  suivi.verifie(5)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL367 — PA2.3 + PA2.5 : rouvert AVEC sa production, horizon 25° → production enregistrée DÉRATÉE
// ════════════════════════════════════════════════════════════════════════════
const HORIZON_25 = [0, 45, 90, 135, 180, 225, 270, 315]

etape('PA2.5', ['ACAL367'], async ({ page, suivi }) => {
  const statutsCarte = suivreCarte(page)
  const cal = await creerCalepinage(page.request, 'ACC ACAL367 Horizon')
  await ecrireLayout(page.request, cal.id, {
    version: 2, pin: A, activeAreaId: 'z1',
    zones: [{ id: 'z1', label: 'Toit plat', vertices: R, roofType: 'flat', pitchDeg: 15, facingAzimuthDeg: 180 }],
  })
  // Given : toit plat enregistré AVEC sa production par l'atelier, puis rouvert depuis ce document.
  let bouton = await ouvrirAtelier(page, cal.id, statutsCarte)
  const doc0 = await enregistrer(page, cal.id, bouton)
  const s0 = doc0?.result?.annualKwh
  const zs0 = z1(doc0)?.result?.annualKwh
  console.log(`[PA2.5/367] enregistré sans horizon : result.annualKwh=${s0} zones[z1].result=${JSON.stringify(z1(doc0)?.result)} signature=${doc0?.result?.signatureOmbrage}`)
  expect(s0, 'production enregistrée (sans ombrage)').toBeGreaterThan(0)

  bouton = await ouvrirAtelier(page, cal.id, statutsCarte, 'horizon')
  const carte0 = chiffres(await page.locator('#rp9-reco-prod').innerText())
  // When : l'onglet Horizon enregistre un horizon de 25° sur le tour complet (8 directions).
  await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 60_000 })
  for (const az of HORIZON_25) {
    await page.getByTestId('cal-horizon-champ-azimut').locator('input').fill(String(az))
    await page.getByTestId('cal-horizon-champ-hauteur').locator('input').fill('25')
    await page.getByRole('button', { name: 'Ajouter le point' }).click()
  }
  await expect(page.getByTestId('cal-horizon-hauteur-max')).toHaveText('25.0°')
  const section = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByRole('button', { name: 'Enregistrer le profil' }).click()
  const rs = await section
  expect(rs.status(), `section horizonProfile → ${(await rs.text()).slice(0, 300)}`).toBe(200)
  expect(rs.request().postDataJSON().cle).toBe('horizonProfile')
  await expect(page.getByText('Profil d’horizon enregistré')).toBeVisible()
  // La carte Production du pan vivant baisse (dérate horizon).
  await expect.poll(async () => chiffres(await page.locator('#rp9-reco-prod').innerText()),
    { message: 'carte Production dératée par l’horizon', timeout: 60_000 }).toBeLessThan(carte0)
  const carte1 = chiffres(await page.locator('#rp9-reco-prod').innerText())
  const totalZones = await page.locator('#rp9-areas-total-prod').innerText().catch(() => '—')
  console.log(`[PA2.5/367] carte Production ${carte0} → ${carte1} ; total « Zones » : ${totalZones}`)

  // Then : l'enregistrement complet émet la production DÉRATÉE (racine et pan), du facteur de la carte.
  const doc1 = await enregistrer(page, cal.id, bouton)
  const s1 = doc1?.result?.annualKwh
  const zs1 = z1(doc1)?.result?.annualKwh
  console.log(`[PA2.5/367] enregistré avec horizon : result.annualKwh=${s1} zones[z1].result.annualKwh=${zs1} signature=${doc1?.result?.signatureOmbrage}`)
  expect(doc1?.horizonProfile?.points?.length, 'horizon enregistré').toBe(8)
  expect(s1, 'result.annualKwh dératé (≠ production relue)').toBeLessThan(s0)
  const facteurCarte = carte1 / carte0
  expect(Math.abs(s1 / s0 - facteurCarte), `facteur du document ${(s1 / s0).toFixed(4)} = facteur de la carte ${facteurCarte.toFixed(4)}`).toBeLessThan(0.01)
  expect(zs1, 'zones[z1].result.annualKwh présent après l’enregistrement').toBeGreaterThan(0)
  if (typeof zs0 === 'number') {
    expect(Math.abs(zs1 / zs0 - facteurCarte), 'pan z1 baissé du même facteur').toBeLessThan(0.01)
  } else {
    expect(Math.abs(zs1 - s1) / s1, 'un seul pan : sa production = la racine').toBeLessThan(0.01)
  }
  expect(doc1?.result?.signatureOmbrage, 'production signée par son dérate (D-ACAL-VER2-1)').toBeTruthy()

  // Persistance : rouvrir ⇒ production enregistrée dératée relue identique ; un enregistrement sans geste la garde.
  bouton = await ouvrirAtelier(page, cal.id, statutsCarte, 'horizon')
  await expect(page.getByTestId('cal-horizon-hauteur-max'), 'horizon relu').toHaveText('25.0°')
  const carteRelue = chiffres(await page.locator('#rp9-reco-prod').innerText())
  console.log(`[PA2.5/367] rouvert : carte Production ${carteRelue}`)
  expect(Math.abs(carteRelue - carte1) / carte1, 'carte rouverte = carte dératée').toBeLessThan(0.01)
  const relu = (await lireLayout(page.request, cal.id)).roof_layout
  expect(relu?.result?.annualKwh).toBe(s1)
  const doc2 = await enregistrer(page, cal.id, bouton)
  expect(doc2?.result?.annualKwh, 'rouvert puis enregistré sans geste : production dératée gardée').toBe(s1)
  expect(doc2?.result?.signatureOmbrage).toBe(doc1.result.signatureOmbrage)
  suivi.verifie(5)
})

// D-ACAL-VER2-1 — document stocké DÉJÀ ombré (horizon écrit par section) mais production jamais dératée (sans signature) :
// le prochain « Enregistrer le calepinage » dérate.
etape('PA2.5-signature', ['ACAL367'], async ({ page, suivi }) => {
  const statutsCarte = suivreCarte(page)
  const cal = await creerCalepinage(page.request, 'ACC ACAL367 Signature')
  await ecrireLayout(page.request, cal.id, {
    version: 2, pin: A, activeAreaId: 'z1',
    zones: [{ id: 'z1', label: 'Toit plat', vertices: R, roofType: 'flat', pitchDeg: 15, facingAzimuthDeg: 180 }],
  })
  let bouton = await ouvrirAtelier(page, cal.id, statutsCarte)
  const doc0 = await enregistrer(page, cal.id, bouton)
  const s0 = doc0?.result?.annualKwh
  expect(s0, 'production enregistrée (sans ombrage)').toBeGreaterThan(0)
  // Horizon écrit PAR SECTION hors atelier (API) : la production stockée reste celle sans horizon, sans signature.
  const lu = await lireLayout(page.request, cal.id)
  const ecr = await page.request.post(`${CAL}/calepinages/${cal.id}/layout/section/`, {
    ...T,
    data: {
      cle: 'horizonProfile',
      valeur: { source: 'saisie', points: HORIZON_25.map((a) => ({ azimuthDeg: a, heightDeg: 25 })), hauteurMaxDeg: 25 },
      base_empreinte: lu.empreinte_document,
    },
  })
  expect(ecr.status(), `section horizon (API) → ${(await ecr.text()).slice(0, 200)}`).toBe(200)
  const stocke = (await lireLayout(page.request, cal.id)).roof_layout
  expect(stocke?.result?.annualKwh, 'production stockée non dératée').toBe(s0)
  expect(stocke?.result?.signatureOmbrage ?? null, 'aucune signature stockée').toBeNull()
  // Rouvrir puis « Enregistrer » sans geste : la production émise est dératée et signée.
  bouton = await ouvrirAtelier(page, cal.id, statutsCarte)
  const carte = chiffres(await page.locator('#rp9-reco-prod').innerText())
  const doc1 = await enregistrer(page, cal.id, bouton)
  console.log(`[PA2.5-signature/367] stocké ${s0} → enregistré ${doc1?.result?.annualKwh} (carte ${carte}) signature=${doc1?.result?.signatureOmbrage}`)
  expect(doc1?.result?.annualKwh, 'production dératée au prochain enregistrement').toBeLessThan(s0)
  expect(Math.abs(doc1.result.annualKwh - carte) / carte, 'document = carte affichée').toBeLessThan(0.01)
  expect(doc1?.result?.signatureOmbrage, 'signature posée').toBeTruthy()
  suivi.verifie(5)
})

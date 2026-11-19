// Acceptation en direct — groupe ACAL, sixième lot (runner GitHub) : preuves en direct dues de six tâches de l'atelier
// `/calepinage/:id` dont le code est sur main mais qui n'ont jamais été jouées faute de carte :
//   ACAL355 (production de CHAQUE pan relue telle quelle), ACAL356 (dérate vivant horizon × ombrage),
//   ACAL357 (« + Ajouter une zone » garde ombres et matrice), ACAL364 (moitié ÉCRAN : l'allée par la section
//   `alleeTechnique` — la moitié serveur a PASSÉ le 26/10, trace ACAL/traces/2026-10-26/ACAL364-PA2.3-serveur.txt),
//   ACAL366 (section « zones » appliquée au pan vivant), ACAL367 (rouvert AVEC sa production puis ombré ⇒ dératé).
// Montage carte : celui d'acal4/acal5 (ACAL377, PASS 18/11) — la réponse réelle de `design-context` est relue puis sa
// `carte` surchargée d'une clé factice ; `https://api.maptiler.com/**` répond 403 (style d'imagerie refusé, déclaré à
// l'oracle) : l'atelier boote sur son fond de repli local. Tout le reste est réel (vrai constructeur, vraie hydratation,
// vrais enregistrements serveur). Données propres à chaque étape (lead + calepinage au shell Django), nettoyées.
// Limites du runner, dites dans les étapes : l'atelier ERP n'a PAS d'outil « Tracer une ombre » (`#rp9-shade-add` absent
// de `BuilderDom.jsx` — le test vitest d'ACAL357 l'ajoute lui-même au DOM) : l'ombre « tracée » shade-1 est posée dans le
// document (format `ombre_tracee` écrit par l'atelier) ; l'écart atelier ↔ simulation (PA2.5) est mesuré par le VRAI
// service serveur `simuler_calepinage` appelé au shell (aucun worker Celery sur le runner) : s'il refuse ou si PVGIS est
// injoignable, l'étape TOMBE avec le motif (NON JOUABLE), jamais un faux vert.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { RACINE } from './_enregistrement.js'
import { API_DJANGO, assurerSessionPage, lireJson } from '../helpers.js'

const etape = groupe('ACAL', ['ACAL355', 'ACAL356', 'ACAL357', 'ACAL364', 'ACAL366', 'ACAL367'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()
const chiffres = (s) => Number(String(s).replace(/[^\d]/g, '')) || 0
const copie = (x) => JSON.parse(JSON.stringify(x))
const pan = (doc, id) => (doc?.zones || []).find((z) => z.id === id)

// Repère au centre de deux pans adjacents d'environ 18 m × 22 m (Casablanca).
const PIN = { lat: 33.5731, lng: -7.5898 }
const PAN_A = [[-7.5899, 33.5732], [-7.5897, 33.5732], [-7.5897, 33.5730], [-7.5899, 33.5730]]
const PAN_B = [[-7.5896, 33.5732], [-7.5894, 33.5732], [-7.5894, 33.5730], [-7.5896, 33.5730]]
const HORIZON_25 = [0, 45, 90, 135, 180, 225, 270, 315]
const MATRICE_08 = Array.from({ length: 12 }, () => Array(24).fill(0.8))

const zonePentue = (id, label, vertices, pitchDeg, facingAzimuthDeg) => ({
  id, label, vertices, roofType: 'pitched', pitchDeg, facingAzimuthDeg, facingManual: true,
})
const toitPlat = () => ({
  version: 2, pin: PIN, activeAreaId: 'z1',
  zones: [{ id: 'z1', label: 'Toit plat', vertices: PAN_A, roofType: 'flat', pitchDeg: 15, facingAzimuthDeg: 180 }],
})

/** Lead (facture 3 000) + calepinage portant `layout`, posés au shell Django (même patron qu'acal4). */
async function calepinageAvec(tag, layout) {
  const m = marque()
  return py(`import json
from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC ${tag} ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('3000'))
lay = json.loads(${JSON.stringify(JSON.stringify(layout))})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ${tag} ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk, 'lead': lead.pk})`)
}

/** Remplace le document stocké (préparation d'un « document ancien » : aucune route publique ne le fait). */
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

/** Montage ACAL377 : clé carte factice servie par `design-context`, style d'imagerie refusé (403, déclaré). */
async function carteRefusee(context, suivi) {
  await context.route(/\/calepinage\/calepinages\/\d+\/design-context\//, async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: 'cle-factice-acal6', mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => route.fulfill({
    status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}',
  }))
}

/** Ouvre l'atelier (fond de repli) et attend la scène HYDRATÉE + la production chiffrée du pan ACTIF.
 *  `production: false` seulement quand le pan actif relu est un pan VIDE (sans contour) : la carte Production
 *  est celle du pan actif, elle reste « — » (ACAL357, la zone ajoutée devient le pan actif). */
async function ouvrirAtelier(page, id, onglet = null, { production = true } = {}) {
  await page.goto(`/calepinage/${id}${onglet ? `?onglet=${onglet}` : ''}`)
  const bouton = page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ })
  try {
    await expect(bouton, '« Enregistrer le calepinage » actif (scène hydratée)').toBeEnabled({ timeout: 240_000 })
  } catch (e) {
    console.log(`[atelier] scène non hydratée ; #rp9-status : « ${await page.locator('#rp9-status').innerText().catch(() => '?')} »`)
    throw e
  }
  await expect(page.locator('#rp9-status'), '`#rp9-status` n’est plus « Chargement… »').not.toHaveText(/^Chargement/, T)
  await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' }), 'jamais « Carte indisponible »').toHaveCount(0)
  if (production) await expect(page.locator('#rp9-reco-prod'), 'carte Production chiffrée').toHaveText(/\d/, T)
  return bouton
}

/** Rouvre l'atelier dans un NOUVEL onglet (même session) : l'onglet quitté garde sa scène, sans garde de sortie. */
async function nouvelOnglet(context, suivi) {
  const p = await context.newPage()
  await p.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  suivi.surveiller(p)
  return p
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

const lireCarte = async (page) => chiffres(await page.locator('#rp9-reco-prod').innerText())
const lireTotalZones = async (page) => chiffres(await page.locator('#rp9-areas-total-prod').textContent())
/** Économies affichées « bas – haut/an » : [bas, haut] en MAD. */
async function lireEconomies(page) {
  const t = await page.locator('#rp9-reco-savings').innerText()
  const [bas, haut] = t.split('–').map(chiffres)
  return [bas, haut ?? bas]
}

/** Onglet Horizon : 8 directions à 25°, « Enregistrer le profil » (POST layout/section/, cle horizonProfile). */
async function saisirHorizon25(page, id) {
  await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 60_000 })
  for (const az of HORIZON_25) {
    await page.getByTestId('cal-horizon-champ-azimut').locator('input').fill(String(az))
    await page.getByTestId('cal-horizon-champ-hauteur').locator('input').fill('25')
    await page.getByRole('button', { name: 'Ajouter le point' }).click()
  }
  await expect(page.getByTestId('cal-horizon-hauteur-max')).toHaveText('25.0°')
  const section = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByRole('button', { name: 'Enregistrer le profil' }).click()
  const rs = await section
  expect(rs.status(), `section horizonProfile → ${(await rs.text()).slice(0, 300)}`).toBe(200)
  expect(rs.request().postDataJSON().cle).toBe('horizonProfile')
  await expect(page.getByText('Profil d’horizon enregistré').first()).toBeVisible()
  return rs
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL355 — PA2.3 : document à deux pans, on retouche A sans visiter B, « Enregistrer » ⇒ B garde SA production,
// la production du document (celle du devis) = somme des deux pans ; enregistrer sans geste ⇒ octet-identique.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL355-production-par-pan', ['ACAL355'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  // L'atelier ne pave QUE le pan ACTIF (run 44626834471 : le pan non actif est enregistré sans `geometry` ni
  // `result`). Préparation du document à deux pans pavés : B actif → enregistrer (B pavé) ; puis A actif →
  // enregistrer (A pavé, B garde sa géométrie enregistrée — ACAL28).
  const cal = await calepinageAvec('ACAL355', {
    version: 2, pin: PIN, activeAreaId: 'z2',
    zones: [zonePentue('z1', 'Pan A sud', PAN_A, 15, 180), zonePentue('z2', 'Pan B est', PAN_B, 15, 90)],
  })
  let bouton = await ouvrirAtelier(page, cal.id)
  const docB = await enregistrer(page, cal.id, bouton)
  expect(pan(docB, 'z2')?.geometry?.panels?.length, 'pan B (actif) pavé par l’atelier').toBeGreaterThan(0)
  await poserDocument(cal.id, { ...docB, activeAreaId: 'z1' })
  bouton = await ouvrirAtelier(page, cal.id)
  const doc0 = await enregistrer(page, cal.id, bouton)
  const [a0, b0] = [pan(doc0, 'z1'), pan(doc0, 'z2')]
  expect(a0?.geometry?.panels?.length, 'pan A pavé par l’atelier').toBeGreaterThan(0)
  expect(b0?.geometry?.panels?.length, 'pan B (non actif) garde sa géométrie enregistrée').toBeGreaterThan(0)
  const watt = Number(doc0.panelWatt) || 710
  const kwcDe = (z) => (Number.isFinite(z.geometry.kwc) ? z.geometry.kwc : (z.geometry.panels.length * watt) / 1000)
  const [kwcA, kwcB] = [kwcDe(a0), kwcDe(b0)]
  expect(kwcA > 0 && kwcB > 0, `kWc par pan lisibles (A ${kwcA}, B ${kwcB})`).toBeTruthy()

  // Given : le document porte la production de CHAQUE pan (A 1 700 kWh/kWc, B 1 400 kWh/kWc : jamais un prorata du kWc).
  const prodA = Math.round(kwcA * 1700)
  const prodB = Math.round(kwcB * 1400)
  const given = copie(doc0)
  pan(given, 'z1').result = { annualKwh: prodA }
  pan(given, 'z2').result = { annualKwh: prodB }
  given.result = { ...(given.result || {}), annualKwh: prodA + prodB }
  await poserDocument(cal.id, given)
  const prorataB = ((prodA + prodB) * kwcB) / (kwcA + kwcB)
  expect(Math.abs(prorataB - prodB), `la part au prorata de B (${prorataB.toFixed(0)}) diffère de SA production (${prodB}) : le test discrimine`).toBeGreaterThan(50)
  const stocke = (await lireLayout(page.request, cal.id)).roof_layout

  // When : rouvrir, retoucher A (sa pente : 30° par l'onglet Pente, section « zones » sur z1 seul), B jamais visité,
  // « Enregistrer ». Les puces « ~30° » du constructeur ne s'affichent pas pour un pan EN PENTE rouvert (run
  // 44628892881 : `#rp9-pitched-controls` hidden sur tous les instantanés) : l'hydratation pose `roofType = a.roofType`
  // (roof-tool-pro11.ts l.2053) sans basculer le bloc, et `setRoofType` sort tôt quand le type ne change pas (l.2235).
  bouton = await ouvrirAtelier(page, cal.id, 'pente')
  expect((await lireLayout(page.request, cal.id)).roof_layout, 'ouvrir ne réécrit aucun document stocké').toEqual(stocke)
  await expect(page.getByTestId('cal-pente')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('cal-pente-pan').selectOption('z1')
  await page.getByTestId('cal-pente-mode-degres').click()
  await page.locator('#cal-pente-degres').fill('30')
  const sectionA = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByTestId('cal-pente-enregistrer').click()
  const rsA = await sectionA
  expect(rsA.status(), `retouche de A (section zones) → ${(await rsA.text()).slice(0, 300)}`).toBe(200)
  expect(rsA.request().postDataJSON().zone_id, 'la retouche ne vise que A').toBe('z1')
  await expect(page.getByTestId('cal-pente-message')).toContainText('Pente enregistrée sur le pan')
  const doc1 = await enregistrer(page, cal.id, bouton)
  console.log(`[ACAL355] A ${JSON.stringify(pan(doc1, 'z1')?.result)} B ${JSON.stringify(pan(doc1, 'z2')?.result)} total ${doc1?.result?.annualKwh}`)
  expect(pan(doc1, 'z1')?.pitchDeg, 'la retouche de A est enregistrée (30°)').toBe(30)
  // Then : B garde SA production, la racine = Σ pans.
  expect(pan(doc1, 'z2')?.result, 'zones[B].result = la production enregistrée de B, telle quelle').toStrictEqual({ annualKwh: prodB })
  const somme = doc1.zones.reduce((s, z) => s + (Number(z?.result?.annualKwh) || 0), 0)
  expect(Math.abs(doc1.result.annualKwh - somme), `result.annualKwh ${doc1.result.annualKwh} = Σ pans ${somme}`).toBeLessThan(1)
  expect(Math.abs(doc1.result.annualKwh - (pan(doc1, 'z1').result.annualKwh + prodB)), 'racine = A recalculé + B gardé').toBeLessThan(1)

  // Persistance : rouvrir → enregistrer sans geste ⇒ chaque zones[i].result octet-identique.
  bouton = await ouvrirAtelier(page, cal.id)
  const doc2 = await enregistrer(page, cal.id, bouton)
  expect(JSON.stringify(doc2.zones.map((z) => z.result)), 'zones[i].result octet-identiques').toBe(JSON.stringify(doc1.zones.map((z) => z.result)))
  expect(doc2.result.annualKwh, 'production du document inchangée').toBe(doc1.result.annualKwh)
  await nettoyer(cal)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL356 + ACAL367 — PA2.3 : toit plat (facture 3 000) enregistré AVEC sa production, rouvert, horizon 25° saisi dans
// l'onglet Horizon ⇒ carte, total « Zones » et production enregistrée baissent du MÊME facteur ; économies recalculées
// (plafonnées à la facture) ; sans geste ⇒ chiffres strictement inchangés ; persistance du dératé.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL356-ACAL367-horizon', ['ACAL356', 'ACAL367'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL356', toitPlat())
  let bouton = await ouvrirAtelier(page, cal.id)
  const doc0 = await enregistrer(page, cal.id, bouton)
  const s0 = doc0?.result?.annualKwh
  const zs0 = pan(doc0, 'z1')?.result?.annualKwh
  expect(s0, 'production enregistrée sans ombrage').toBeGreaterThan(0)

  // Sans horizon ni ombre (facteurs = 1) : rouvert, la carte affiche exactement la production enregistrée.
  bouton = await ouvrirAtelier(page, cal.id, 'horizon')
  const carte0 = await lireCarte(page)
  const zones0 = await lireTotalZones(page)
  const [, eco0] = await lireEconomies(page)
  expect(Math.abs(carte0 - s0), `sans horizon : carte ${carte0} = production enregistrée ${s0}`).toBeLessThanOrEqual(1)
  expect(zones0, 'total « Zones » chiffré').toBeGreaterThan(0)

  // When : horizon 25° sur le tour complet, par l'onglet Horizon.
  await saisirHorizon25(page, cal.id)
  await expect.poll(() => lireCarte(page), { message: 'carte Production dératée par l’horizon', timeout: 60_000 }).toBeLessThan(carte0)
  const carte1 = await lireCarte(page)
  const zones1 = await lireTotalZones(page)
  const [, eco1] = await lireEconomies(page)
  const facteurCarte = carte1 / carte0
  console.log(`[ACAL356/367] carte ${carte0} → ${carte1} ; Zones ${zones0} → ${zones1} ; économies (haut) ${eco0} → ${eco1}`)
  expect(Math.abs(zones1 / zones0 - facteurCarte), 'total « Zones » baissé du facteur de la carte').toBeLessThan(0.01)
  expect(eco1, 'économies recalculées depuis le kWh dératé (jamais plus hautes)').toBeLessThanOrEqual(eco0)
  expect(eco1, 'économies plafonnées à la facture (12 × 3 000 MAD)').toBeLessThanOrEqual(12 * 3000)

  // Then : l'enregistrement complet émet la production DÉRATÉE (racine et pan), du facteur de la carte.
  const doc1 = await enregistrer(page, cal.id, bouton)
  const s1 = doc1?.result?.annualKwh
  const zs1 = pan(doc1, 'z1')?.result?.annualKwh
  console.log(`[ACAL356/367] enregistré : ${s0} → ${s1} ; zones[z1] ${zs0} → ${zs1} ; signature ${doc1?.result?.signatureOmbrage}`)
  expect(doc1?.horizonProfile?.points?.length, 'horizon enregistré').toBe(8)
  expect(s1, 'result.annualKwh dératé (≠ production relue)').toBeLessThan(s0)
  expect(Math.abs(s1 / s0 - facteurCarte), `facteur du document ${(s1 / s0).toFixed(4)} = facteur de la carte ${facteurCarte.toFixed(4)}`).toBeLessThan(0.01)
  expect(zs1, 'zones[z1].result.annualKwh présent').toBeGreaterThan(0)
  if (typeof zs0 === 'number') expect(Math.abs(zs1 / zs0 - facteurCarte), 'pan z1 baissé du même facteur').toBeLessThan(0.01)
  else expect(Math.abs(zs1 - s1) / s1, 'un seul pan : sa production = la racine').toBeLessThan(0.01)
  expect(doc1?.result?.signatureOmbrage, 'production signée par son dérate (D-ACAL-VER2-1)').toBeTruthy()

  // Persistance : rouvrir ⇒ dératé relu identique ; enregistrer sans geste le garde.
  bouton = await ouvrirAtelier(page, cal.id, 'horizon')
  await expect(page.getByTestId('cal-horizon-hauteur-max'), 'horizon relu').toHaveText('25.0°')
  expect(Math.abs((await lireCarte(page)) - carte1), 'carte rouverte = carte dératée').toBeLessThanOrEqual(1)
  expect((await lireLayout(page.request, cal.id)).roof_layout?.result?.annualKwh).toBe(s1)
  const doc2 = await enregistrer(page, cal.id, bouton)
  expect(doc2?.result?.annualKwh, 'rouvert puis enregistré sans geste : production dératée gardée').toBe(s1)
  expect(doc2?.result?.signatureOmbrage).toBe(doc1.result.signatureOmbrage)
  await nettoyer(cal)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL356 — matrice `shading12x24` à 0,8 relue : carte, total « Zones » et document à 0,8 × la référence (même toit sans
// matrice, documents sans production stockée) ; persistance du dératé.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL356-matrice', ['ACAL356'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const ref = await calepinageAvec('ACAL356 ref', toitPlat())
  const ombre = await calepinageAvec('ACAL356 ombre', { ...toitPlat(), shading12x24: MATRICE_08 })
  let bouton = await ouvrirAtelier(page, ref.id)
  const reference = { carte: await lireCarte(page), zones: await lireTotalZones(page) }
  reference.doc = (await enregistrer(page, ref.id, bouton))?.result?.annualKwh
  bouton = await ouvrirAtelier(page, ombre.id)
  const ombre1 = { carte: await lireCarte(page), zones: await lireTotalZones(page) }
  const docOmbre = await enregistrer(page, ombre.id, bouton)
  ombre1.doc = docOmbre?.result?.annualKwh
  console.log(`[ACAL356 matrice] référence ${JSON.stringify(reference)} ; matrice 0,8 ${JSON.stringify(ombre1)}`)
  for (const k of ['carte', 'zones', 'doc']) {
    expect(reference[k], `référence ${k} chiffrée`).toBeGreaterThan(0)
    expect(Math.abs(ombre1[k] / reference[k] - 0.8), `${k} : matrice 0,8 ⇒ × 0,8 (${(ombre1[k] / reference[k]).toFixed(4)})`).toBeLessThan(0.01)
  }
  expect(docOmbre.shading12x24, 'la matrice relue est réémise').toEqual(MATRICE_08)
  // Persistance : rouvrir ⇒ dératé relu identique.
  bouton = await ouvrirAtelier(page, ombre.id)
  expect(Math.abs((await lireCarte(page)) - ombre1.carte), 'carte rouverte identique').toBeLessThanOrEqual(1)
  const relu = await enregistrer(page, ombre.id, bouton)
  expect(relu?.result?.annualKwh, 'production dératée relue identique').toBe(ombre1.doc)
  await nettoyer(ref, ombre)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL367 — D-ACAL-VER2-1 : document stocké DÉJÀ ombré (horizon écrit par section) mais production jamais dératée (sans
// signature) ⇒ le prochain « Enregistrer le calepinage » dérate et signe.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL367-signature', ['ACAL367'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL367 sig', toitPlat())
  let bouton = await ouvrirAtelier(page, cal.id)
  const s0 = (await enregistrer(page, cal.id, bouton))?.result?.annualKwh
  expect(s0, 'production enregistrée sans ombrage').toBeGreaterThan(0)
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
  bouton = await ouvrirAtelier(page, cal.id)
  const carte = await lireCarte(page)
  const doc1 = await enregistrer(page, cal.id, bouton)
  console.log(`[ACAL367 signature] stocké ${s0} → enregistré ${doc1?.result?.annualKwh} (carte ${carte}) signature ${doc1?.result?.signatureOmbrage}`)
  expect(doc1?.result?.annualKwh, 'production dératée au prochain enregistrement').toBeLessThan(s0)
  expect(Math.abs(doc1.result.annualKwh - carte) / carte, 'document = carte affichée').toBeLessThan(0.01)
  expect(doc1?.result?.signatureOmbrage, 'signature posée').toBeTruthy()
  // Persistance : rouvert, la production dératée est relue telle quelle.
  bouton = await ouvrirAtelier(page, cal.id)
  expect((await enregistrer(page, cal.id, bouton))?.result?.annualKwh).toBe(doc1.result.annualKwh)
  await nettoyer(cal)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL356 + ACAL367 — PA2.5 : l'écart atelier ↔ simulation serveur se resserre (ne s'ouvre plus) quand l'horizon est
// appliqué. Simulation = le VRAI service `simuler_calepinage` (sans écriture) au shell : aucun worker sur le runner.
// ════════════════════════════════════════════════════════════════════════════
async function simulationServeur(id) {
  try {
    return await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.simulation import simuler_calepinage
r = simuler_calepinage(Calepinage.objects.get(pk=${Number(id)}), forcer=True, enregistrer=False)
t = ((r.get('blocs') or {}).get('production') or {}).get('total') or {}
sortie({'p50': t.get('p50_kwh'), 'complete': t.get('complete')})`)
  } catch (e) {
    throw new Error(`NON JOUABLE sur ce runner — la simulation serveur (simuler_calepinage) a refusé ou PVGIS est injoignable : ${String(e.message).slice(-500)}`)
  }
}

/** Réglage société de la pile d'essai (pas un défaut produit) : la simulation refuse sans `mode_meteo` saisi
 *  (`chaine_pertes.decision_meteo`). `tmy` est refusé sans fichier météo déposé (`verifier_simulable`,
 *  MOTIF_TMY_HORIZONTAL) : mode `pluriannuel` + `fenetre_annees`, la forme lue par `etapes.reglage`
 *  (`{valeur, source}`), celle des tests `test_calx193_serie_persistee.py::reglages`. Rend l'état d'avant. */
async function reglerMeteo() {
  return py(`from apps.calepinage.models import ParametresCalepinage
co = U.objects.get(username='demo_admin').company
p = ParametresCalepinage.objects.filter(company=co).order_by('id').first()
avant = None if p is None else dict(p.simulation or {})
if p is None:
    p = ParametresCalepinage.objects.create(company=co)
sim = dict(p.simulation or {})
sim['mode_meteo'] = {'valeur': 'pluriannuel', 'source': 'societe', 'reference': 'acceptation ACAL6'}
sim['fenetre_annees'] = {'valeur': '2020-2020', 'source': 'societe', 'reference': 'acceptation ACAL6'}
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

etape('PA2.5-ACAL356-ACAL367-ecart-simulation', ['ACAL356', 'ACAL367'], async ({ page, context, suivi }) => {
  const meteo = await reglerMeteo()
  try {
    await ecartSimulation({ page, context, suivi })
  } finally {
    await restaurerMeteo(meteo)
  }
})

/** Désigne le module PV du calepinage comme l'onglet « Matériel électrique » (`enregistrer_entree`,
 *  `module_produit`) : sans lui, `bloc_pose` n'a pas de puissance crête et la simulation refuse
 *  (MOTIF_SANS_PAN_EQUIPE). Module = un produit RÉEL du catalogue de la société (`produits_modules_qs`) dont la
 *  fiche porte tous les champs que le chaînage exige (`chaines.CHAMPS_MODULE` : Vmp, Voc, Isc, Imp, Pmax). */
async function designerModule(id) {
  const r = await py(`from apps.calepinage.models import Calepinage
from apps.calepinage.services.chaines import CHAMPS_MODULE
from apps.calepinage.services.electrique import enregistrer_entree
from apps.stock.selectors_fiche_technique import produits_modules_qs, specs_for_produit
c = Calepinage.objects.get(pk=${Number(id)})
choix = None
for p in produits_modules_qs(c.company):
    s = specs_for_produit(p) or {}
    if all(s.get(cle) not in (None, '') for cle, _ in CHAMPS_MODULE):
        choix = (p.pk, p.nom, s.get('pmax_wc'))
        break
if choix:
    enregistrer_entree(c, {'module_produit': choix[0]}, user=U.objects.get(username='demo_admin'))
sortie({'produit': choix and choix[0], 'nom': choix and choix[1], 'pmax_wc': choix and choix[2]})`)
  if (!r?.produit) {
    throw new Error('NON JOUABLE sur ce runner — aucun module PV du catalogue de la société ne porte une fiche complète '
      + '(Vmp, Voc, Isc, Imp, Pmax) : impossible de désigner le module que la simulation exige.')
  }
  console.log(`[PA2.5] module désigné : #${r.produit} ${r.nom} (${r.pmax_wc} Wc)`)
  return r
}

async function ecartSimulation({ page, context, suivi }) {
  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL367 sim', toitPlat())
  await designerModule(cal.id)
  let bouton = await ouvrirAtelier(page, cal.id)
  const s0 = (await enregistrer(page, cal.id, bouton))?.result?.annualKwh
  const sim0 = await simulationServeur(cal.id)
  expect(sim0?.p50, `simulation serveur sans horizon chiffrée (${JSON.stringify(sim0)})`).toBeGreaterThan(0)
  bouton = await ouvrirAtelier(page, cal.id, 'horizon')
  await saisirHorizon25(page, cal.id)
  const s1 = (await enregistrer(page, cal.id, bouton))?.result?.annualKwh
  const sim1 = await simulationServeur(cal.id)
  const ecart0 = Math.abs(s0 - sim0.p50) / sim0.p50
  const ecart1 = Math.abs(s1 - sim1.p50) / sim1.p50
  console.log(`[PA2.5] atelier ${s0} → ${s1} ; simulation ${sim0.p50} → ${sim1.p50} ; écart ${(ecart0 * 100).toFixed(1)} % → ${(ecart1 * 100).toFixed(1)} %`)
  expect(sim1.p50, 'la simulation serveur applique l’horizon').toBeLessThan(sim0.p50)
  expect(s1, 'l’atelier applique l’horizon').toBeLessThan(s0)
  expect(ecart1, 'l’écart atelier ↔ simulation ne s’ouvre plus avec l’horizon').toBeLessThanOrEqual(ecart0 + 0.01)
  await nettoyer(cal)
}

// ════════════════════════════════════════════════════════════════════════════
// ACAL357 — PA2.3 : ombres du site (tracée shade-1 + relues sh-1, sh-2) et matrice 0,8 ; « + Ajouter une zone » puis
// « Enregistrer » ⇒ 3 zones, ombres et matrice identiques ; rouvrir ⇒ toujours là.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL357-ombres-ajout-zone', ['ACAL357'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  // L'atelier ERP n'a pas d'outil « Tracer une ombre » : shade-1 est posée au format qu'écrit l'atelier (`ombre_tracee`,
  // pied/bout/hauteur/demi-largeur) ; sh-1/sh-2 = les ombres du contrat roof_layout_v2 (`exemple`), relues verbatim.
  const contrat = JSON.parse(readFileSync(join(RACINE,
    'backend/django_core/apps/calepinage/contract_samples/roof_layout_v2.schema.json'), 'utf8'))
  const ombresContrat = contrat.exemple.shadeObstructions
  expect(ombresContrat.map((o) => o.id), 'ombres du contrat').toEqual(['sh-1', 'sh-2'])
  const shade1 = {
    id: 'shade-1', kind: 'ombre_tracee', centre: [-7.58985, 33.57318], bout: [-7.58985, 33.57314],
    rayonM: 1, hauteurM: 3, source: 'ombre_tracee',
  }
  const cal = await calepinageAvec('ACAL357', {
    version: 2, pin: PIN, activeAreaId: 'z1',
    zones: [zonePentue('z1', 'Pan A sud', PAN_A, 15, 180), zonePentue('z2', 'Pan B est', PAN_B, 15, 90)],
    shadeObstructions: [shade1, ...ombresContrat], shading12x24: MATRICE_08,
  })
  let bouton = await ouvrirAtelier(page, cal.id)
  const avant = await enregistrer(page, cal.id, bouton)
  expect((avant.shadeObstructions || []).map((o) => o.id), 'ombres relues et réémises').toEqual(['shade-1', 'sh-1', 'sh-2'])
  expect(avant.shading12x24, 'matrice réémise').toBeTruthy()
  expect(avant.zones, 'deux pans au départ').toHaveLength(2)

  // When : rouvrir, « + Ajouter une zone », « Enregistrer ».
  bouton = await ouvrirAtelier(page, cal.id)
  const ajouter = page.locator('#rp9-add-area')
  await expect(ajouter, '« + Ajouter une zone » actif').toBeEnabled(T)
  await ajouter.click()
  const apres = await enregistrer(page, cal.id, bouton)
  // Then : 3 zones, ombres [shade-1, sh-1, sh-2] et matrice identiques.
  expect(apres.zones, 'trois zones').toHaveLength(3)
  expect(apres.shadeObstructions, 'ombres gardées par l’ajout d’un pan').toEqual(avant.shadeObstructions)
  expect(apres.shading12x24, 'matrice gardée par l’ajout d’un pan').toEqual(avant.shading12x24)

  // Persistance : rouvrir ⇒ ombres et matrice relues identiques. La zone ajoutée (sans contour) est le pan ACTIF
  // enregistré (run 44626834471 : activeAreaId 'area-1', 0 sommet) : la carte Production du pan actif reste « — ».
  const ajoutee = pan(apres, apres.activeAreaId)
  expect(['z1', 'z2'], 'la zone ajoutée est le pan actif enregistré').not.toContain(apres.activeAreaId)
  expect(ajoutee?.vertices || [], 'zone ajoutée encore sans contour').toHaveLength(0)
  bouton = await ouvrirAtelier(page, cal.id, null, { production: false })
  const relu = await enregistrer(page, cal.id, bouton)
  expect(relu.shadeObstructions, 'ombres relues identiques').toEqual(apres.shadeObstructions)
  expect(relu.shading12x24, 'matrice relue identique').toEqual(apres.shading12x24)
  await nettoyer(cal)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL364 (moitié écran) — PA2.3 : horizon saisi dans l'onglet Horizon, puis allée 0,9 m par le panneau Allées ⇒ UNE
// section `alleeTechnique` (jamais le document entier) ; l'horizon reste ; jeton périmé ⇒ 409, message mot pour mot.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL364-allee-section', ['ACAL364'], async ({ page, context, suivi }) => {
  // Clause statique : plus aucun écrivain du document entier hors de l'atelier, allowlist de la garde vide.
  const allees = readFileSync(join(RACINE, 'frontend/src/features/calepinage/PanneauAllees.jsx'), 'utf8')
  expect(allees, 'PanneauAllees.jsx n’appelle plus enregistrerLayoutCalepinage(').not.toMatch(/enregistrerLayoutCalepinage(?:Conditionnel)?\s*\(/)
  const garde = readFileSync(join(RACINE, 'scripts/check_calepinage_ecrivains_layout.py'), 'utf8')
  expect(garde, 'ALLOWLIST de la garde vide').toMatch(/^ALLOWLIST: dict = \{\}\s*$/m)

  await carteRefusee(context, suivi)
  const cal = await calepinageAvec('ACAL364', toitPlat())
  const ecrituresCompletes = []
  page.on('request', (r) => {
    if (r.method() !== 'GET' && new URL(r.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/`)) ecrituresCompletes.push(r.url())
  })
  await ouvrirAtelier(page, cal.id, 'horizon')
  // Given : un horizonProfile écrit par l'onglet Horizon APRÈS l'ouverture de l'atelier.
  await saisirHorizon25(page, cal.id)
  const docH = await lireLayout(page.request, cal.id)
  expect(docH.roof_layout?.horizonProfile?.points?.length, 'horizon stocké').toBe(8)

  // When : allée de 0,9 m (saisie) « Enregistrer pour ce calepinage ».
  await expect(page.getByTestId('cal-allees-calepinage')).toBeVisible(T)
  await page.locator('#cal-allees-largeur-calepinage').fill('0.9')
  const section = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByTestId('cal-allees-enregistrer-calepinage').click()
  const rs = await section
  expect(rs.status(), `section alleeTechnique → ${(await rs.text()).slice(0, 300)}`).toBe(200)
  const corps = rs.request().postDataJSON()
  expect(corps.cle).toBe('alleeTechnique')
  expect(corps.valeur).toEqual({ largeurM: 0.9, source: 'saisie' })
  expect(corps.base_empreinte, 'jeton = celui du document vivant après la section Horizon').toBe(docH.empreinte_document)
  await expect(page.getByTestId('cal-allees-message-calepinage')).toHaveText('Allée de 0.9 m enregistrée pour ce calepinage.')
  expect(ecrituresCompletes, 'aucune écriture du document entier par le panneau Allées').toEqual([])

  // Then : relu, l'horizon reste, l'allée est là, toutes les autres clés octet-identiques.
  const docA = await lireLayout(page.request, cal.id)
  expect(docA.roof_layout.alleeTechnique).toEqual({ largeurM: 0.9, source: 'saisie' })
  expect(docA.roof_layout.horizonProfile, 'horizonProfile gardé').toEqual(docH.roof_layout.horizonProfile)
  const sansAllee = (d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== 'alleeTechnique'))
  expect(JSON.stringify(sansAllee(docA.roof_layout)), 'autres clés octet-identiques').toBe(JSON.stringify(sansAllee(docH.roof_layout)))

  // Jeton périmé : le document change ailleurs (section API), le panneau répond 409 et affiche le message serveur.
  const ailleurs = await page.request.post(`${CAL}/calepinages/${cal.id}/layout/section/`, {
    ...T, data: { cle: 'alleeTechnique', valeur: { largeurM: 1.2, source: 'saisie' }, base_empreinte: docA.empreinte_document },
  })
  expect(ailleurs.status(), `écriture ailleurs → ${(await ailleurs.text()).slice(0, 200)}`).toBe(200)
  suivi.attendre(new RegExp(`/calepinages/${cal.id}/layout/section/`), 409)
  const refus = page.waitForResponse((x) => new URL(x.url()).pathname.endsWith(`/calepinages/${cal.id}/layout/section/`)
    && x.request().method() === 'POST', T)
  await page.getByTestId('cal-allees-enregistrer-calepinage').click()
  const r409 = await refus
  expect(r409.status(), 'jeton périmé ⇒ 409').toBe(409)
  const motif = await r409.json()
  expect(motif.code).toBe('document_modifie')
  await expect(page.getByTestId('cal-allees-message-calepinage'), 'message du serveur, mot pour mot').toHaveText(motif.detail)
  expect((await lireLayout(page.request, cal.id)).roof_layout.alleeTechnique, '409 : rien n’est écrit').toEqual({ largeurM: 1.2, source: 'saisie' })
  expect(ecrituresCompletes).toEqual([])

  // Persistance : rouvrir ⇒ l'horizon est toujours là. Rouvert dans un NOUVEL onglet : après le 409, l'onglet quitté
  // porte l'allée 0,9 appliquée localement que le serveur a refusée (le document dit 1,2) — sa garde de sortie
  // (ACAL85, `beforeunload`) est alors légitime ; la recharger dans le même onglet ouvrait ce dialogue, que le
  // harnais referme, ce qui annulait la navigation (run 44626834471 : net::ERR_ABORTED, dialogue `beforeunload`).
  const rouvert = await nouvelOnglet(context, suivi)
  await ouvrirAtelier(rouvert, cal.id, 'horizon')
  await expect(rouvert.getByTestId('cal-horizon-hauteur-max'), 'horizon relu après rouverture').toHaveText('25.0°')
  expect((await lireLayout(page.request, cal.id)).roof_layout.horizonProfile).toEqual(docH.roof_layout.horizonProfile)
  await nettoyer(cal)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL366 — PA2.3 : l'onglet Pente enregistre 35° sur z1 (section « zones ») ⇒ le pan VIVANT repart sur 35° ;
// « Enregistrer le calepinage » garde 35° et la pitchSource ; z2 et les autres clés intacts ; rouvrir ⇒ 35°.
// ════════════════════════════════════════════════════════════════════════════
etape('PA2.3-ACAL366-pente-section', ['ACAL366'], async ({ page, context, suivi }) => {
  await carteRefusee(context, suivi)
  const allee = { largeurM: 0.6, source: 'saisie' }
  const cal = await calepinageAvec('ACAL366', {
    version: 2, pin: PIN, activeAreaId: 'z1', alleeTechnique: allee,
    zones: [zonePentue('z1', 'Pan sud', PAN_A, 15, 180), zonePentue('z2', 'Pan est', PAN_B, 20, 90)],
  })
  let bouton = await ouvrirAtelier(page, cal.id)
  const doc15 = await enregistrer(page, cal.id, bouton)
  expect(pan(doc15, 'z1')?.pitchDeg, 'pan z1 enregistré à 15°').toBe(15)
  const z2Avant = pan(doc15, 'z2')
  const prod15 = doc15?.result?.annualKwh

  bouton = await ouvrirAtelier(page, cal.id, 'pente')
  const carte15 = await lireCarte(page)
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
  expect(envoye.zone_id).toBe('z1')
  expect(envoye.champs.pitchDeg, 'pente envoyée').toBe(35)
  const pitchSource = envoye.champs.pitchSource
  expect(pitchSource, 'provenance de la pente envoyée').toBeTruthy()
  await expect(page.getByTestId('cal-pente-message')).toContainText('Pente enregistrée sur le pan')
  // Le pan VIVANT repart sur 35° : la production affichée est recalculée.
  await expect.poll(() => lireCarte(page), { message: 'carte Production recalculée sur 35°', timeout: 60_000 }).not.toBe(carte15)

  // Then : l'enregistrement complet garde 35° et la provenance (jamais l'ancienne pente, sans 409).
  const doc35 = await enregistrer(page, cal.id, bouton)
  expect(pan(doc35, 'z1')?.pitchDeg, 'zones[z1].pitchDeg après « Enregistrer le calepinage »').toBe(35)
  expect(pan(doc35, 'z1')?.pitchSource, 'zones[z1].pitchSource écrite').toEqual(pitchSource)
  expect(doc35?.result?.annualKwh, 'production enregistrée recalculée sur 35°').not.toBe(prod15)
  expect(pan(doc35, 'z2')?.pitchDeg, 'pan absent de la section : non touché').toBe(z2Avant.pitchDeg)
  expect(pan(doc35, 'z2')?.facingAzimuthDeg).toBe(z2Avant.facingAzimuthDeg)
  expect(pan(doc35, 'z2')?.vertices).toEqual(z2Avant.vertices)
  expect(doc35.alleeTechnique, 'clé d’une autre section octet-identique').toEqual(allee)

  // Persistance : rouvrir ⇒ 35° affiché (onglet Pente) et relu ; enregistrer sans geste le garde.
  bouton = await ouvrirAtelier(page, cal.id, 'pente')
  await expect(page.locator('#cal-pente-degres'), 'saisie relue du pan z1').toHaveValue('35')
  await expect(page.getByTestId('cal-pente-valeur'), 'pente retenue affichée').toContainText('35.0 °')
  const docBis = await enregistrer(page, cal.id, bouton)
  expect(pan(docBis, 'z1')?.pitchDeg, 'rouvert puis enregistré sans geste : 35° gardé').toBe(35)
  expect(pan(docBis, 'z1')?.pitchSource).toEqual(pitchSource)
  await nettoyer(cal)
})

// Acceptation en direct — groupe ACAL (calepinage) : ACAL250, ACAL251, ACAL279,
// ACAL280, ACAL282, ACAL284, ACAL289. Format : `_format.md`. Parcours et scénarios
// du dossier `docs/audits/2026-10-04-calepinage.md` (P1-P8, S-A..S-H).
//
// Données PROPRES à chaque étape, posées par l'API (`page.request` = demo_admin) :
// leads, calepinages, produits à fiche, devis — noms uniques (`uniq`), jamais les
// fiches démo, jamais la prod. Deux écritures passent par `manage.py shell`
// (`executerDansDjango`, variable `E2E_DJANGO_EXEC` quand le backend n'est pas le
// conteneur `django_core` du compose) parce qu'AUCUNE route ne les écrit :
//   - `Lead.roof_point` / `roof_outline` (lecture seule côté API : seuls le tunnel
//     public et l'import les posent) — l'épingle A dans le contour R ;
//   - le lien calepinage → devis par `services.liens.lier_devis` (le seul écrivain).
// Réglages société touchés (feu vert, approbation exigée, versions conservées,
// sections du rapport) : relus AVANT et RESTAURÉS en `finally`.
//
// « Non jouable » : une étape dont la preuve exige ce que la pile n'a pas (clé
// carte MapTiler absente du serveur) lève `nonJouable(...)` : FAIL, raison en
// notes — jamais un PASS.
import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, assurerSessionPage, executerDansDjango, lireJson, listeDe, textePdf, uniq, telephoneMobileUnique,
} from '../helpers.js'

test.describe.configure({ timeout: 900_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
const etape = groupe('ACAL', ['ACAL250', 'ACAL251', 'ACAL279', 'ACAL280', 'ACAL282', 'ACAL284', 'ACAL289', 'ACAL311'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const CAL = `${API_DJANGO}/calepinage`
const T = { timeout: 120_000 }
const nonJouable = (raison) => { throw new Error(`NON JOUABLE : ${raison}`) }

// Épingle A au centre du contour R (≈ 20 m × 18 m) ; GPS corrigé B à ~1,4 km, hors de R.
const A = { lat: 33.5731, lng: -7.5898 }
const R = [
  { lat: 33.5732, lng: -7.5899 }, { lat: 33.5732, lng: -7.5897 },
  { lat: 33.5730, lng: -7.5897 }, { lat: 33.5730, lng: -7.5899 },
]
const B = { lat: 33.58, lng: -7.6 }

// ── Montage ─────────────────────────────────────────────────────────────────
async function creerLead(request, tag, extra = {}) {
  return lireJson(await request.post(`${API_DJANGO}/crm/leads/`, {
    ...T,
    data: {
      nom: uniq(tag), ville: 'Casablanca', telephone: telephoneMobileUnique(),
      type_installation: 'residentiel', facture_hiver: '800', ...extra,
    },
  }), 'lead')
}

function shell(code) {
  try {
    // `manage.py shell` démarre en ~3 min sur cette pile chargée (mesuré le 29/10) :
    // au-delà des 120 s d'`executerDansDjango`, d'où un délai propre quand
    // E2E_DJANGO_EXEC désigne le conteneur.
    const surmesure = process.env.E2E_DJANGO_EXEC
    if (!surmesure) return executerDansDjango(code)
    const [cmd, ...args] = surmesure.split(' ')
    return execFileSync(cmd, [...args, 'python', 'manage.py', 'shell', '-c', code],
      { stdio: 'pipe', timeout: 400_000 }).toString()
  } catch (e) {
    return nonJouable(`écriture serveur impossible (manage.py shell, E2E_DJANGO_EXEC) — ${String(e.message).slice(0, 200)}`)
  }
}

/** S-H : lead à l'épingle A dans son contour R, GPS corrigé B hors de R. */
async function leadGpsHorsContour(request) {
  const lead = await creerLead(request, 'ACC CAL Repere', { gps_lat: String(B.lat), gps_lng: String(B.lng) })
  shell(`from apps.crm.models import Lead; Lead.objects.filter(pk=${lead.id}).update(`
    + `roof_point=${JSON.stringify(A).replace(/"/g, "'")}, roof_outline=${JSON.stringify(R).replace(/"/g, "'")})`)
  const relu = await lireJson(await request.get(`${API_DJANGO}/crm/leads/${lead.id}/`, T), 'lead relu')
  expect(relu.roof_point, 'épingle A posée').toEqual(A)
  expect(relu.repere_toit, 'repère servi = GPS corrigé, contour inutilisable')
    .toEqual({ pin: B, source: 'gps', contour_utilisable: false })
  return relu
}

async function creerCalepinage(request, leadId, tag = 'ACC CAL') {
  const cal = await lireJson(await request.post(`${CAL}/calepinages/`, {
    ...T, data: { lead: leadId, titre: uniq(tag) },
  }), 'calepinage')
  // Constaté au rejeu du 29/10 : le PREMIER GET design-context d'un calepinage neuf
  // prend ~31 s sur cette pile (le suivant 0,3 s) — au-delà du délai axios de 20 s de
  // l'atelier (« La connexion a expiré »). Lu une fois ici (délai 120 s) pour que
  // l'étape juge son geste, pas cette latence (signalée au rapport).
  await lireJson(await request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context (amorce)')
  return cal
}

/** Écrit le document entier avec le jeton If-Match lu juste avant (ACAL22). */
async function ecrireLayout(request, id, roofLayout) {
  const lu = await lireJson(await request.get(`${CAL}/calepinages/${id}/layout/`, T), 'layout')
  return lireJson(await request.post(`${CAL}/calepinages/${id}/layout/`, {
    ...T, headers: { 'If-Match': `"${lu.empreinte_document || ''}"` }, data: { roof_layout: roofLayout },
  }), 'écriture du layout')
}

async function lireParametres(request) {
  return lireJson(await request.get(`${CAL}/parametres/`, T), 'réglages calepinage')
}

async function ecrireParametres(request, corps) {
  return lireJson(await request.put(`${CAL}/parametres/`, { ...T, data: corps }), 'PUT réglages calepinage')
}

/** `documents` tel que stocké (le catalogue est DÉRIVÉ, refusé en écriture). */
const documentsStockes = (p) => {
  const { catalogue_rapport: _c, ...reste } = p.documents || {}
  return reste
}

async function avecPresets(request, presets, corps) {
  const avant = (await lireParametres(request)).presets || {}
  await ecrireParametres(request, { presets: { ...avant, ...presets } })
  try {
    await corps()
  } finally {
    await ecrireParametres(request, { presets: avant })
  }
}

/** Ouvre l'écran Nouveau calepinage et choisit le lead dans l'onglet Lead. */
async function choisirLeadSurNouveau(page, nomLead) {
  await page.goto('/calepinage/nouveau')
  await expect(page.getByRole('heading', { name: 'Nouveau calepinage' })).toBeVisible({ timeout: 30_000 })
  await page.getByRole('tab', { name: 'Lead' }).click()
  await page.locator('#cal-nouveau-lead').getByRole('combobox').click()
  await page.getByRole('searchbox').fill(nomLead)
  await page.getByRole('option', { name: new RegExp(nomLead) }).first().click()
}

const ongletOuvert = (page) => expect(page.getByTestId('cal-onglet-panneau')).toBeVisible({ timeout: 240_000 })
const alerteCarte = (page) => page.getByRole('alert').filter({ hasText: 'clé MapTiler' })

// ════════════════════════════════════════════════════════════════════════════
// ACAL250 / ACAL251 — le repère toit servi par le serveur (S-H)
// ════════════════════════════════════════════════════════════════════════════

etape('P1.1', ['ACAL250'], async ({ page }) => {
  // Lead → calepinage (porte lead) : design-context et contexte devis publient le
  // drapeau ; aucune graine éditable sur R ; R reste servi en calque ; pin = B.
  const lead = await leadGpsHorsContour(page.request)
  const cal = await creerCalepinage(page.request, lead.id)
  const ctx = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  const g = ctx.geometrie
  expect(g.contour_utilisable, 'contour_utilisable').toBe(false)
  expect(g.source_repere, 'source_repere').toBe('gps')
  expect(g.outline, 'aucune graine éditable tant qu’aucun pan n’est dessiné').toEqual([])
  expect(g.contour_client, 'contour client R servi en calque').toEqual(R)
  expect(g.pin, 'épingle = GPS corrigé B').toEqual(B)
  expect(g.roof_layout ?? null, 'aucun document semé sur R').toBeNull()

  // Contexte de conception DEVIS du même lead : même jugement (ventes/selectors).
  const devis = await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis/`, {
    ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis du lead')
  const ctxDevis = await lireJson(await page.request.get(`${API_DJANGO}/ventes/devis/${devis.id}/design-context/`, T),
    'design-context devis')
  expect(ctxDevis.geometrie.outline ?? [], 'devis : aucune graine éditable sur R').toEqual([])
  expect(ctxDevis.geometrie.pin, 'devis : épingle = B').toEqual(B)

  // L'atelier s'ouvre (persistance : rouvrir → même contexte, rien n'a été écrit).
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible({ timeout: 30_000 })
  await page.reload()
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible({ timeout: 30_000 })
  const relu = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context relu')
  expect(relu.geometrie.outline).toEqual([])
  expect(relu.geometrie.roof_layout ?? null).toBeNull()
})

etape('P1.2', ['ACAL250', 'ACAL251'], async ({ page }) => {
  // /calepinage/nouveau depuis le lead : « Coordonnées GPS corrigées » (ACAL251),
  // créer → atelier sans zone éditable sur l'ancien toit (ACAL250, côté serveur).
  const lead = await leadGpsHorsContour(page.request)
  await choisirLeadSurNouveau(page, lead.nom)
  await expect(page.getByText('Source du repère').locator('..')).toContainText('Coordonnées GPS corrigées')
  await page.locator('#cal-nouveau-nom').fill(uniq('ACC CAL Nouveau'))
  await page.getByRole('button', { name: 'Créer le calepinage' }).click()
  await expect(page).toHaveURL(/\/calepinage\/\d+/, { timeout: 60_000 })
  const id = /\/calepinage\/(\d+)/.exec(new URL(page.url()).pathname)[1]
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible({ timeout: 30_000 })
  const ctx = await lireJson(await page.request.get(`${CAL}/calepinages/${id}/design-context/`, T), 'design-context')
  expect(ctx.calepinage.lead).toBe(lead.id)
  expect(ctx.geometrie.contour_utilisable).toBe(false)
  expect(ctx.geometrie.outline, 'aucune zone éditable sur R').toEqual([])
  expect(ctx.geometrie.contour_client, 'calque client servi').toEqual(R)
  expect(ctx.geometrie.pin).toEqual(B)
})

etape('P1.1-atelier', ['ACAL250'], async ({ page }) => {
  // Atelier : « aucune zone éditable sur l'ancien toit, calque client visible » — à l'ÉCRAN.
  const lead = await leadGpsHorsContour(page.request)
  const cal = await creerCalepinage(page.request, lead.id)
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible({ timeout: 30_000 })
  const ctx = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  if (!ctx.carte?.available) {
    await expect(alerteCarte(page)).toBeVisible()
    nonJouable('le serveur ne publie aucune clé carte (PUBLIC_MAPTILER_KEY vide) : le constructeur 3D ne boote pas, '
      + 'le calque client et l’absence de pan éditable ne sont pas observables à l’écran (le jugement serveur est prouvé en P1.1/P1.2)')
  }
  await expect(page.locator('#rp9-map')).toBeVisible({ timeout: 30_000 })
})

etape('P1.1-devis-design', ['ACAL251'], async ({ page }) => {
  // /devis-design/<lead> (ToitureDesign mode lead) centré sur B.
  const lead = await leadGpsHorsContour(page.request)
  await page.goto(`/devis-design/${lead.id}`)
  const cfg = await lireJson(await page.request.get(`${API_DJANGO}/ventes/roof-config/`, T), 'roof-config')
  if (!cfg.available) {
    await expect(alerteCarte(page)).toBeVisible({ timeout: 30_000 })
    nonJouable('le serveur ne publie aucune clé carte : l’atelier mode lead s’arrête sur « Carte indisponible » avant '
      + 'l’hydratation — le centrage sur B (roof_point du payload) n’est pas observable')
  }
  await expect(page.locator('#rp9-map')).toBeVisible({ timeout: 30_000 })
})

etape('P2.5', ['ACAL251'], async ({ page }) => {
  // Calepinage neuf issu du lead (document SANS épingle) : Horizon et Course du soleil
  // prennent la latitude du repère servi par le détail (contexte_geographique.pin = B).
  const lead = await leadGpsHorsContour(page.request)
  const cal = await creerCalepinage(page.request, lead.id)
  // Un pan tracé SANS épingle dans le document (Course du soleil exige un pan) : la
  // latitude ne peut venir que du repère servi par le détail.
  await ecrireLayout(page.request, cal.id, {
    zones: [{ id: 'z1', label: 'Sud', result: { count: 6 }, facingAzimuthDeg: 180.0, pitchDeg: 15.0 }],
  })
  const lu = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')
  expect(lu.roof_layout?.pin ?? null, 'aucune épingle dans le document').toBeNull()
  const detail = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/`, T), 'détail')
  expect(detail.contexte_geographique.pin, 'repère servi par le détail').toEqual(B)
  await page.goto(`/calepinage/${cal.id}?onglet=horizon`)
  await ongletOuvert(page)
  await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('cal-horizon-diagramme')).toBeVisible()
  await expect(page.getByText(/Latitude du site inconnue/)).toHaveCount(0)
  await page.goto(`/calepinage/${cal.id}?onglet=course-soleil`)
  await ongletOuvert(page)
  await expect(page.getByTestId('cal-course-soleil')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('cal-course-soleil-scene')).toBeVisible()
  await expect(page.getByTestId('cal-course-soleil').getByText(/Latitude du site inconnue/)).toHaveCount(0)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL279 — un seul décodeur des refus serveur (S-D)
// ════════════════════════════════════════════════════════════════════════════

etape('P6.1', ['ACAL279'], async ({ page, suivi }) => {
  // Retenir refusé par le serveur (400 {feu_vert:[…]}) : le motif serveur s'affiche,
  // jamais « Impossible de retenir cette variante ». NB : depuis la décision fondateur
  // du 07/10/2026 (services/feu_vert.py), « approbation exigée » ne refuse plus la
  // RETENUE — seul le feu vert (et le verdict électrique) le peut : c'est lui qui est joué.
  const lead = await creerLead(page.request, 'ACC CAL Retenir')
  const cal = await creerCalepinage(page.request, lead.id)
  await lireJson(await page.request.post(`${CAL}/calepinages/${cal.id}/variantes/`, {
    ...T, data: { nom: uniq('ACC Variante'), parametres: {} },
  }), 'variante')
  await avecPresets(page.request, { feu_vert_bureau_etudes: true }, async () => {
    await page.goto(`/calepinage/${cal.id}/variantes`)
    const tableau = page.getByTestId('cal-tableau-variantes')
    await expect(tableau).toBeVisible({ timeout: 30_000 })
    const rep = page.waitForResponse((r) => /\/variantes\/\d+\/retenir\/$/.test(r.url()), T)
    // Refus INJECTÉ par l'étape (réglage feu vert) : le seul 400 excusé.
    suivi.attendre(/\/variantes\/\d+\/retenir\/$/, 400)
    await tableau.getByRole('button', { name: 'Retenir' }).first().click()
    const corps = await (await rep).json()
    expect(corps.feu_vert?.[0], 'refus serveur feu vert').toMatch(/feu vert/)
    // Le bandeau de l'écran (role=alert) — le toast global répète le même texte.
    await expect(page.getByRole('alert').filter({ hasText: corps.feu_vert[0] }).first()).toBeVisible()
    await expect(page.getByText('Impossible de retenir cette variante.')).toHaveCount(0)
    await page.reload()
    await expect(page.getByTestId('cal-tableau-variantes')).toBeVisible({ timeout: 30_000 })
    await expect(page.locator('[data-testid^="cal-retenue-"]'), 'rien n’a été retenu').toHaveCount(0)
  })
})

etape('P6.3', ['ACAL279'], async ({ page, suivi }) => {
  // Onglet Approbation : la DÉCISION refusée en 404 (corps RÉEL du handler, lu sur le
  // serveur puis rejoué sur le POST de l'onglet) affiche le `detail`, jamais l'enveloppe
  // `error` rendue telle quelle (« Objects are not valid as a React child »).
  const lead = await creerLead(page.request, 'ACC CAL Approbation')
  const cal = await creerCalepinage(page.request, lead.id)
  const reel = await page.request.post(`${CAL}/calepinages/999999999/approbation/`, {
    ...T, data: { decision: 'approuve', motif: '' },
  })
  expect(reel.status(), 'forme réelle du 404').toBe(404)
  const corps404 = await reel.json()
  expect(corps404.error, 'enveloppe `error` du handler présente').toBeTruthy()
  expect(corps404.detail, '`detail` du 404').toBeTruthy()
  suivi.attendre(new RegExp(`/calepinages/${cal.id}/approbation/`), 404)
  await page.route(new RegExp(`/calepinages/${cal.id}/approbation/$`), (route) => (route.request().method() === 'POST'
    ? route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify(corps404) })
    : route.continue()))
  await page.goto(`/calepinage/${cal.id}?onglet=approbation`)
  await ongletOuvert(page)
  await expect(page.getByTestId('calx349-decider')).toBeVisible({ timeout: 60_000 })
  await page.getByTestId('calx349-approuver').click()
  const refus = page.getByTestId('calx349-refus')
  await expect(refus).toBeVisible()
  await expect(refus).toContainText(corps404.detail)
  await expect(page.getByTestId('calx349-panneau')).toBeVisible()
  await expect(page.getByText(/Objects are not valid as a React child/)).toHaveCount(0)
  await expect(page.getByTestId('calx349-bandeau'), 'la clé `error` n’est jamais un champ').toHaveCount(0)
})

etape('P6.3-devis', ['ACAL279'], async ({ page, suivi }) => {
  // Approbation exigée → « Générer le devis » (BoutonDevis) : le motif « approbation »
  // nommé. Le bouton ENREGISTRE d'abord la conception de l'écran (constructeur 3D) :
  // sans carte, il s'arrête sur « La conception à l'écran n'a pas pu être enregistrée »
  // sans appeler le serveur (constaté au rejeu du 29/10).
  const lead = await creerLead(page.request, 'ACC CAL Approbation devis')
  const cal = await creerCalepinage(page.request, lead.id)
  const ctx = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  if (!ctx.carte?.available) {
    nonJouable('Générer le devis enregistre d’abord la conception du constructeur 3D, qui ne boote pas sans clé '
      + 'carte : aucun appel generer-devis/ n’atteint le serveur, le refus « approbation » n’est pas affichable '
      + '(la forme 400 {approbation:[…]} est servie par le serveur, vérifiée par API)')
  }
  await avecPresets(page.request, { approbation_exigee: true }, async () => {
    await page.goto(`/calepinage/${cal.id}`)
    await expect(page.getByTestId('cal-bouton-devis')).toBeVisible({ timeout: 30_000 })
    // Le refus « approbation » EST le résultat attendu de l'étape (400 servi).
    suivi.attendre(new RegExp(`/calepinages/${cal.id}/generer-devis/`), 400)
    const rep = page.waitForResponse((r) => r.url().includes(`/calepinages/${cal.id}/generer-devis/`), T)
    await page.getByTestId('cal-generer-devis').click()
    const reponse = await rep
    expect(reponse.status(), 'generer-devis refusé').toBe(400)
    const corps = await reponse.json()
    await expect(page.getByTestId('cal-devis-refus')).toContainText(corps.approbation[0])
  })
})

etape('P2.3', ['ACAL279'], async ({ page, suivi }) => {
  // Relevé terrain envoyé sans date : 400 {releve_le: '…'} rendu SOUS le champ date.
  const lead = await creerLead(page.request, 'ACC CAL Releve')
  const cal = await creerCalepinage(page.request, lead.id)
  await page.goto(`/calepinage/${cal.id}?onglet=releve`)
  await ongletOuvert(page)
  await expect(page.getByTestId('cal-releve-panel')).toBeVisible({ timeout: 30_000 })
  // La chaîne vide proposée par défaut est refusée AVANT envoi (validation locale) :
  // retirée, le relevé part sans date et c'est le SERVEUR qui refuse.
  while (await page.getByTestId('cal-releve-chaine-0-retirer').count()) {
    await page.getByTestId('cal-releve-chaine-0-retirer').click()
  }
  suivi.attendre(new RegExp(`/calepinages/${cal.id}/releve/`), 400)
  const rep = page.waitForResponse((r) => r.url().includes(`/calepinages/${cal.id}/releve/`)
    && r.request().method() !== 'GET', T)
  await page.getByTestId('cal-releve-envoyer').click()
  const r = await rep
  expect(r.status()).toBe(400)
  const corps = await r.json()
  expect(corps.releve_le, 'refus serveur nommant releve_le').toMatch(/date du relevé est obligatoire/)
  const sousLeChamp = page.getByTestId('cal-releve-erreur-releve_le')
  await expect(sousLeChamp).toBeVisible()
  await expect(sousLeChamp).toContainText('La date du relevé est obligatoire')
  // Jamais le bandeau de clés brutes : la clé `error` du handler n'est pas un champ.
  await expect(page.getByTestId('cal-releve-erreur-error')).toHaveCount(0)
  // Rien n'est écrit sur refus : l'historique reste vide après rechargement.
  await page.reload()
  await expect(page.getByTestId('cal-releve-panel')).toBeVisible({ timeout: 30_000 })
  const releve = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/releve/`, T), 'relevés')
  expect(releve.releves ?? [], 'aucun relevé écrit').toEqual([])
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL280 — onglets Site : le motif serveur d'un refus (S-C)
// ════════════════════════════════════════════════════════════════════════════

etape('P2.5+P6.4+P7.6', ['ACAL280'], async ({ page, suivi }) => {
  // Devis lié ACCEPTÉ → onglet Horizon → Enregistrer : 409 « Devis accepté : révisez-le ».
  const lead = await creerLead(page.request, 'ACC CAL Verrou')
  const cal = await creerCalepinage(page.request, lead.id)
  const produit = await lireJson(await page.request.post(`${API_DJANGO}/stock/produits/`, {
    ...T, data: { nom: uniq('ACC CAL Produit'), prix_vente: '1000.00' },
  }), 'produit')
  const devis = await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis/`, {
    ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis')
  shell(`from apps.calepinage.models import Calepinage; from apps.calepinage.services.liens import lier_devis; `
    + `lier_devis(Calepinage.objects.get(pk=${cal.id}), ${devis.id})`)
  await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis/${devis.id}/replace-lines/`, {
    ...T,
    data: {
      lignes: [{
        produit: produit.id, designation: produit.nom, quantite: '2.00', prix_unitaire: '1000.00',
        remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0,
      }],
    },
  }), 'lignes du devis')
  await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis/${devis.id}/accepter/`, {
    ...T, data: { nom: 'Client ACC CAL' },
  }), 'acceptation du devis')
  const ctx = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  expect(ctx.calepinage.devis, 'devis lié').toBe(devis.id)
  expect(ctx.modifiable, 'calepinage verrouillé par le devis accepté').toBe(false)
  const avant = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout avant')

  await page.goto(`/calepinage/${cal.id}?onglet=horizon`)
  await ongletOuvert(page)
  await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 30_000 })
  suivi.attendre(new RegExp(`/calepinages/${cal.id}/layout/section/`), 409)
  const rep = page.waitForResponse((r) => r.url().includes(`/calepinages/${cal.id}/layout/section/`), T)
  await page.getByRole('button', { name: 'Enregistrer le profil' }).click()
  const r = await rep
  expect(r.status(), 'écriture refusée par le verrou').toBe(409)
  const corps = await r.json()
  const motif = corps.roof_layout?.[0]
  expect(motif, 'motif serveur').toMatch(/accepté : révisez-le/)
  await expect(page.getByTestId('cal-horizon').getByRole('status')).toContainText(motif)
  await expect(page.getByText(/n’a pas pu être enregistré|n'a pas pu être enregistré/)).toHaveCount(0)
  // Rien n'est écrit sur refus : rouvrir → document inchangé.
  await page.reload()
  await expect(page.getByTestId('cal-horizon')).toBeVisible({ timeout: 30_000 })
  const apres = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout après')
  expect(apres.empreinte_document ?? null).toBe(avant.empreinte_document ?? null)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL282 — une seule lecture de la clé carte (S-A)
// ════════════════════════════════════════════════════════════════════════════

etape('P3.1', ['ACAL282'], async ({ page }) => {
  // Les trois portes rendent la MÊME réponse ; sans clé : « Carte indisponible ».
  const lead = await creerLead(page.request, 'ACC CAL Carte')
  const cal = await creerCalepinage(page.request, lead.id)
  const devis = await lireJson(await page.request.post(`${API_DJANGO}/ventes/devis/`, {
    ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: 'residentiel' },
  }), 'devis')
  const roofConfig = await lireJson(await page.request.get(`${API_DJANGO}/ventes/roof-config/`, T), 'roof-config')
  const ctxCal = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/design-context/`, T), 'design-context')
  const ctxDevis = await lireJson(await page.request.get(`${API_DJANGO}/ventes/devis/${devis.id}/design-context/`, T),
    'design-context devis')
  expect(ctxCal.carte, 'design-context calepinage = roof-config').toEqual(roofConfig)
  expect(ctxDevis.carte, 'contexte devis = roof-config').toEqual(roofConfig)
  expect(Object.keys(roofConfig).sort()).toEqual(['available', 'mapboxToken', 'maptilerKey'])
  if (roofConfig.available) return
  expect(roofConfig.available).toBe(false)
  expect(roofConfig.mapboxToken).toBeNull()
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByTestId('cal-rail-onglets')).toBeVisible({ timeout: 30_000 })
  await expect(alerteCarte(page)).toBeVisible({ timeout: 30_000 })
  await expect(alerteCarte(page)).toContainText('Carte indisponible')
})

etape('P3.1-cle', ['ACAL282'], async ({ page }) => {
  // Branche « avec clé : carte chargée par les trois portes ».
  const cfg = await lireJson(await page.request.get(`${API_DJANGO}/ventes/roof-config/`, T), 'roof-config')
  if (!cfg.available) {
    nonJouable('aucune clé PUBLIC_MAPTILER_KEY sur le backend de cette pile (roof-config : available=false) : '
      + 'la branche « carte chargée » ne se joue qu’avec une clé, posée au démarrage du conteneur')
  }
  const lead = await creerLead(page.request, 'ACC CAL Carte cle')
  const cal = await creerCalepinage(page.request, lead.id)
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.locator('#rp9-map')).toBeVisible({ timeout: 30_000 })
  await expect(alerteCarte(page)).toHaveCount(0)
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL284 — dérogation d'une alerte électrique (S-F)
// ════════════════════════════════════════════════════════════════════════════

etape('P4.6', ['ACAL284'], async ({ page }) => {
  // Module 710 Wc (Imp 17,59 A) sur un onduleur 1 MPPT à 15 A : alerte NON bloquante
  // « courant par entrée MPPT ». Passer outre avec motif → rechargée, elle reste.
  const fiche = async (nom, champs) => {
    const p = await lireJson(await page.request.post(`${API_DJANGO}/stock/produits/`, {
      ...T, data: { nom: uniq(nom), prix_vente: '1500.00' },
    }), 'produit')
    await lireJson(await page.request.post(`${API_DJANGO}/stock/fiches-techniques/`, {
      ...T, data: { produit: p.id, ...champs },
    }), `fiche ${nom}`)
    return p
  }
  const module = await fiche('ACC CAL Module 710', {
    type_fiche: 'module', vmp_v: 41.4, voc_v: 49.3, isc_a: 18.59, imp_a: 17.59, pmax_wc: 710,
    longueur_mm: 2384, largeur_mm: 1303,
  })
  const onduleur = await fiche('ACC CAL Onduleur 1 MPPT', {
    type_fiche: 'onduleur', ond_n_mppt: 1, ond_mppt_v_min: 160, ond_mppt_v_max: 950, ond_v_max_abs: 1100,
    ond_i_max_mppt_a: 15, ond_ac_kw: 10, ond_phases: 3,
  })
  const lead = await creerLead(page.request, 'ACC CAL Verdict')
  const cal = await creerCalepinage(page.request, lead.id)
  await ecrireLayout(page.request, cal.id, {
    pin: B, zones: [{ id: 'z1', label: 'Sud', result: { count: 12 }, facingAzimuthDeg: 180.0, pitchDeg: 15.0 }],
  })
  await lireJson(await page.request.post(`${CAL}/calepinages/${cal.id}/entree-electrique/`, {
    ...T,
    data: {
      module_produit: module.id, onduleur_produit: onduleur.id,
      temperature_min_c: -5, temperature_max_c: 70, phases: 3,
    },
  }), 'saisie électrique')
  const res = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/resultat/`, T), 'résultat')
  const alerte = (res.electrique?.verdicts ?? []).find((v) => v.conforme === false && !v.bloquant)
  if (!alerte) throw new Error(`aucune alerte non bloquante servie : ${JSON.stringify(res.electrique?.verdicts)}`)
  expect(res.derogations, 'aucune dérogation avant le geste').toEqual([])

  await page.goto(`/calepinage/${cal.id}?onglet=verdict-electrique`)
  await ongletOuvert(page)
  const ligne = page.getByTestId(`acal284-alerte-${alerte.code}`)
  await expect(ligne).toBeVisible({ timeout: 30_000 })
  await page.getByTestId(`acal284-passer-outre-${alerte.code}`).click()
  const confirmer = page.getByTestId(`acal284-confirmer-${alerte.code}`)
  await expect(confirmer, 'inactif tant que le motif est vide').toBeDisabled()
  const motif = uniq('Validé avec le client ACC')
  await page.locator(`#acal284-motif-${alerte.code}`).fill(motif)
  await expect(confirmer).toBeEnabled()
  const posts = []
  page.on('request', (rq) => {
    if (rq.method() === 'POST' && rq.url().includes(`/calepinages/${cal.id}/entree-electrique/`)) posts.push(rq.postDataJSON())
  })
  const rep = page.waitForResponse((r) => r.url().includes(`/calepinages/${cal.id}/entree-electrique/`)
    && r.request().method() === 'POST', T)
  await confirmer.dblclick()
  const r = await rep
  expect(r.status(), `dérogation acceptée : ${await r.text()}`).toBe(200)
  expect(posts[0], 'corps envoyé').toEqual({ derogations: [{ code: alerte.code, motif }] })
  const phrase = page.getByTestId(`acal284-derogation-${alerte.code}`)
  await expect(phrase).toContainText('Passée outre par')
  await expect(phrase).toContainText(motif)
  // Persistance : recharger relit le même fil ; un double clic n'en écrit qu'UNE.
  await page.reload()
  await ongletOuvert(page)
  await expect(page.getByTestId(`acal284-derogation-${alerte.code}`)).toContainText(motif, { timeout: 30_000 })
  const relu = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/resultat/`, T), 'résultat relu')
  expect(relu.derogations.filter((d) => d.code === alerte.code), 'une seule dérogation écrite').toHaveLength(1)
  expect(relu.derogations[0].motif).toBe(motif)
  expect(relu.derogations[0].auteur).toBeTruthy()
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL289 — Réglages › Calepinage : versions conservées + sections du rapport
// ════════════════════════════════════════════════════════════════════════════

etape('P5.1+P6.2+P8.1', ['ACAL289'], async ({ page }) => {
  const avant = await lireParametres(page.request)
  const presetsAvant = avant.presets || {}
  const documentsAvant = documentsStockes(avant)
  const section = (avant.documents?.catalogue_rapport || []).find((s) => !s.obligatoire)
  const obligatoire = (avant.documents?.catalogue_rapport || []).find((s) => s.obligatoire)
  expect(section, 'une section facultative au catalogue').toBeTruthy()
  try {
    // P5.1 — saisir 2 versions conservées, décocher une section, par l'écran.
    await page.goto('/calepinage/reglages')
    const historique = page.getByTestId('acal289-historique')
    await expect(historique).toBeVisible({ timeout: 30_000 })
    const boutonHist = page.getByTestId('acal289-enregistrer-historique')
    await page.locator('#acal289-versions-conservees').fill('')
    await page.locator('#acal289-versions-conservees').fill('2')
    const putHist = page.waitForRequest((rq) => rq.method() === 'PUT' && rq.url().includes('/calepinage/parametres/'), T)
    await boutonHist.click()
    expect((await putHist).postDataJSON(), 'PUT de la seule section presets')
      .toEqual({ presets: { versions_conservees: 2 } })
    await expect(historique.getByRole('status')).toContainText('2 versions conservées')

    await expect(page.getByTestId(`acal289-section-${obligatoire.code}`), 'obligatoire non décochable').toBeDisabled()
    const caseSection = page.getByTestId(`acal289-section-${section.code}`)
    if (!(await caseSection.isChecked())) {
      await caseSection.check()
      await page.getByTestId('acal289-enregistrer-rapport').click()
      await expect(page.getByTestId('acal289-rapport').getByRole('status')).toBeVisible()
    }
    await expect(page.getByTestId('acal289-enregistrer-rapport'), 'inactif tant que rien n’a changé').toBeDisabled()
    await caseSection.uncheck()
    const putRap = page.waitForRequest((rq) => rq.method() === 'PUT' && rq.url().includes('/calepinage/parametres/'), T)
    await page.getByTestId('acal289-enregistrer-rapport').click()
    const corpsRap = (await putRap).postDataJSON()
    expect(Object.keys(corpsRap), 'PUT de la seule section documents').toEqual(['documents'])
    expect(corpsRap.documents.rapport_etude.sections).not.toContain(section.code)
    expect(corpsRap.documents.catalogue_rapport, 'le catalogue n’est jamais renvoyé').toBeUndefined()
    await expect(page.getByTestId('acal289-rapport').getByRole('status')).toBeVisible()
    // Persistance : rouvrir relit les mêmes valeurs.
    await page.reload()
    await expect(page.locator('#acal289-versions-conservees')).toHaveValue('2', { timeout: 30_000 })
    await expect(page.getByTestId(`acal289-section-${section.code}`)).not.toBeChecked()
    await expect(page.getByTestId('acal289-enregistrer-historique')).toBeDisabled()

    // P6.2 — la borne purge les versions les plus anciennes à chaque enregistrement.
    const lead = await creerLead(page.request, 'ACC CAL Versions')
    const cal = await creerCalepinage(page.request, lead.id)
    for (const n of [4, 6, 8, 10]) {
      await ecrireLayout(page.request, cal.id, {
        pin: B, zones: [{ id: 'z1', label: 'Sud', result: { count: n }, facingAzimuthDeg: 180.0, pitchDeg: 15.0 }],
      })
    }
    // Le rapport d'étude exige un résultat moteur enregistré (409 sinon) : saisie électrique.
    await lireJson(await page.request.post(`${CAL}/calepinages/${cal.id}/entree-electrique/`, {
      ...T, data: { phases: 3 },
    }), 'saisie électrique')
    const versions = listeDe(await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/versions/`, T), 'versions'))
    expect(versions.length, `versions conservées (${versions.length})`).toBe(2)
    await page.goto(`/calepinage/${cal.id}?onglet=versions`)
    await ongletOuvert(page)

    // P8.1 — le rapport d'étude livré ne porte plus la section décochée.
    const pdf = await page.request.get(`${CAL}/calepinages/${cal.id}/rapport-etude.pdf`, T)
    expect(pdf.ok(), `rapport-etude.pdf → ${pdf.status()}`).toBeTruthy()
    const texte = await textePdf(await pdf.body())
    const sommaire = texte.slice(texte.indexOf('Sommaire'), texte.indexOf('Sommaire') + 600)
    expect(sommaire, 'sommaire lu').toContain('Système')
    expect(sommaire, `section « ${section.titre} » absente du rapport`).not.toContain(section.titre)
  } finally {
    await ecrireParametres(page.request, { presets: presetsAvant, documents: documentsAvant })
  }
})

// ════════════════════════════════════════════════════════════════════════════
// ACAL311 — « Affiner ma consommation » : kWh au barème société (P5.5, S-E)
// ════════════════════════════════════════════════════════════════════════════

etape('P5.5', ['ACAL311'], async ({ page }) => {
  // Lead démo à factures → calepinage (mode `/calepinage/<pk>`), toit dessiné : le panneau
  // « Affiner ma consommation » lit « estimation (barème indicatif) » ; « Reprendre du lead »
  // → POST consommation/proposer/ {source:'lead'} → 200, le panneau affiche « N kWh/an —
  // barème société » (N = kwh_annuel servi) ; Enregistrer, F5, Enregistrer sans toucher →
  // roof_layout.consumption identique, source.bareme = 'societe'.
  const cfg = await lireJson(await page.request.get(`${API_DJANGO}/ventes/roof-config/`, T), 'roof-config')
  if (!cfg.available) nonJouable('aucune clé carte servie : le constructeur 3D ne boote pas')
  const lead = await creerLead(page.request, 'ACC CAL Conso', { facture_hiver: '900', facture_ete: '700' })
  const cal = await creerCalepinage(page.request, lead.id)
  await ecrireLayout(page.request, cal.id, {
    pin: A, version: 2, zones: [{ id: 'z1', label: 'Sud', vertices: R.map((p) => [p.lng, p.lat]), result: { count: 10 }, facingAzimuthDeg: 180.0, pitchDeg: 15.0 }],
  })
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.locator('#rp9-map')).toBeVisible({ timeout: 60_000 })
  await expect(page.getByTestId('cal-enregistrer-calepinage')).toBeVisible({ timeout: 120_000 })
  const bascule = page.locator('#rp9-cons-toggle')
  try {
    await expect(bascule, 'bouton « Affiner ma consommation » à l’écran').toBeVisible({ timeout: 90_000 })
  } catch (e) {
    const ids = await page.locator('[id^="rp9-cons"], [data-cons-bareme]').count()
    const texte = await page.getByText('Affiner ma consommation').count()
    throw new Error(`« Affiner ma consommation » absent de l'atelier /calepinage/${cal.id} (éléments rp9-cons* / data-cons-bareme dans le DOM : ${ids} ; texte « Affiner ma consommation » : ${texte}). `
      + 'Condition : consumption.ts::renderConsumption ne montre `#rp9-cons-window` qu’avec un plan de production '
      + '(ctx.prodScaled et ctx.prodPanels > 0) — dans l’ERP, posé par prodWindow.ts::syncProductionSansFenetre via '
      + 'l’option `productionAtelier` (useAtelierBoot.js) ; 0 élément rp9-cons* = gabarit CONS_WINDOW_HTML absent de ToitureDesign.jsx. '
      + `Attendu : panneau « estimation (barème indicatif) » puis « Reprendre du lead ». (${String(e.message).split('\n')[0]})`)
  }
  if ((await bascule.getAttribute('aria-expanded')) !== 'true') await bascule.click()
  const note = page.locator('[data-cons-bareme]')
  await expect(note).toHaveText('estimation (barème indicatif)', { timeout: 30_000 })
  const rep = page.waitForResponse((r) => r.url().includes(`/consommation/proposer/`) && r.request().method() === 'POST', T)
  await page.locator('[data-cons-action="lead"]').click()
  const r = await rep
  expect(r.request().postDataJSON(), 'corps envoyé').toEqual({ source: 'lead' })
  expect(r.status(), `proposer → ${(await r.text()).slice(0, 300)}`).toBe(200)
  const servi = await r.json()
  const n = Math.round(servi.kwh_annuel)
  const chiffres = (s) => Number(String(s).replace(/[^\d]/g, ''))
  await expect(note).toContainText('kWh/an — barème société', { timeout: 30_000 })
  expect(chiffres(await note.innerText()), 'N affiché = kwh_annuel servi').toBe(n)
  await expect(note).toHaveAttribute('data-bareme', 'societe')
  const kwhAn = page.locator('#rp9-bill-kwh')
  if (await kwhAn.count()) expect(chiffres(await kwhAn.innerText()), '« ≈ N kWh par an »').toBe(n)

  const enregistrer = async () => {
    const ecrit = page.waitForResponse((x) => x.url().includes(`/calepinages/${cal.id}/`) && x.request().method() !== 'GET'
      && x.status() < 300, T)
    await page.getByTestId('cal-enregistrer-calepinage').getByRole('button', { name: /Enregistrer le calepinage/ }).click()
    await ecrit
    const d = await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/`, T), 'calepinage relu')
    return (d.roof_layout ?? (await lireJson(await page.request.get(`${CAL}/calepinages/${cal.id}/layout/`, T), 'layout')).roof_layout)?.consumption
  }
  const c1 = await enregistrer()
  expect(c1?.source?.bareme, 'source.bareme persisté').toBe('societe')
  await page.reload()
  await expect(page.getByTestId('cal-enregistrer-calepinage')).toBeVisible({ timeout: 120_000 })
  const c2 = await enregistrer()
  expect(c2, 'consumption identique après F5 + enregistrer sans toucher').toEqual(c1)
  console.log(`[P5.5] kwh_annuel ${servi.kwh_annuel} ; consumption.source ${JSON.stringify(c1?.source)}`)
})

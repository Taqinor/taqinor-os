// Rejeu en direct du groupe ACNC (parcours PF9 « doubles clics, gestes rejoués, courses », dossier
// docs/audits/2026-11-11-parcours-PF9.md) sur l'ARGENT : ACNC1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 15
// (PLAN_AUDIT_FACTURATION.md) et ACNC13 (PLAN_AUDIT_DEVIS.md). Décisions D-ACNC-1/D-ACNC-2.
//
// Règle de preuve (METHODE §C.4 point 7) : chaque étape joue VRAIMENT deux gestes et constate UN SEUL
// effet — (1) à l'écran, deux clics rapides (`dblclick`) pendant que la requête est TENUE (le bouton est
// affirmé désactivé pendant l'envoi), puis la coupure réseau APRÈS l'envoi (la requête atteint le serveur,
// la réponse est perdue : `route.fetch()` puis `abort`) et un nouveau clic ; (2) au réseau, deux requêtes
// identiques lancées EN PARALLÈLE (`Promise.all`) avec la même clé quand la tâche en prévoit une, puis sans ;
// puis la BASE est relue par le shell Django (un paiement, un avoir, une note, un mouvement…).
// Les courses sont servies par 4 workers gunicorn synchrones (workflow d'essai) : deux requêtes parallèles
// sont réellement traitées en même temps par deux processus (pids dans le journal d'accès du run).
//
// Rôles : comptes d'essai de rôles SYSTÈME du registre (`permissions_registre.py`, relus par leur nom dans la
// société démo) — Commercial (porte `encaisser`) pour les gestes d'encaissement, Directeur (seul palier
// `IsAdminRole`, porte `encaisser`) pour la note de débit, la suppression, l'annulation, le montant de
// tranche, « marquer payée » et le formulaire de facture. Données propres créées par l'API à chaque étape ;
// les factures, avoirs et notes à numéro LÉGAL ne se suppriment pas (règle des numéros) : ils restent dans la
// base jetable du runner.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ACNC', ['ACNC1', 'ACNC2', 'ACNC3', 'ACNC5', 'ACNC6', 'ACNC7', 'ACNC8', 'ACNC9', 'ACNC10',
  'ACNC11', 'ACNC12', 'ACNC13', 'ACNC15'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const AUJ = () => new Date().toISOString().slice(0, 10)
const f2 = (v) => Number(v).toFixed(2)
const cents = (v) => Math.round(Number(v) * 100)
const plat = (s) => String(s).replace(/\s+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
const statuts = (reps) => reps.map((x) => x.status()).sort((a, b) => a - b)
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await (c.dispose ? c.dispose() : c.close()).catch(() => undefined) })
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[ACNC] ${type} : ${description}`)
}
// ÉCART ACCEPTÉ (écrans joués sous le rôle Commercial, avant midi) : défaut ANTÉRIEUR et hors des Files des tâches ACNC.
const ECART_TOURNEE = {
  base: 'FAIL',
  raison: "GET installations/interventions/ma-tournee/ → 403 pour le rôle Commercial : le pré-chargement matinal de la tournée "
    + '(frontend/src/features/offlinesync/PrechargementTournee.jsx, NTMOB28 du 13/08/2026, monté par Layout sur TOUT écran '
    + "authentifié avant 12 h) interroge une route que le rôle Commercial ne lit pas — 403 + console.error à chaque écran ; présent "
    + "avant les commits ACNC (13/11/2026), hors de leurs Files (facturation / ventes) ; à ouvrir chez le propriétaire installations/offlinesync",
}
const IMPORTS = `from apps.ventes.models import Facture, Paiement, Avoir, RelanceLog, Devis, BonCommande, LigneFacture
from apps.ventes.models_facturation import NoteDebit, FactureActivity, ProformaDocument, RemiseEncaissement
from apps.stock.models import MouvementStock, Produit
`
const bd = (code) => py(`${IMPORTS}${code}`)

// ── comptes, contextes, écrans ───────────────────────────────────────────────────────────────

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {id, encaisser, admin, systeme}. */
async function compteDuRole(nom, nomRole) {
  return py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nomRole)})
u = compte(${JSON.stringify(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'encaisser': 'encaisser' in (r.permissions or []), 'admin': 'roles_gerer' in (r.permissions or []), 'systeme': r.est_systeme})`)
}
/** Compte du rôle + contexte API connecté par la vraie route /token/. */
async function acteur(testInfo, prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  const role = await compteDuRole(nom, nomRole)
  expect([role.systeme, role.encaisser], `${nomRole} : rôle système du registre qui porte encaisser`).toEqual([true, true])
  if (nomRole === 'Directeur') expect(role.admin, 'Directeur : palier IsAdminRole (roles_gerer)').toBe(true)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(ctx)
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { nom, ctx }
}
/** Contexte navigateur neuf connecté sous `nom` (accueil et visites guidées vus, SW bloqué). */
async function navigateur(page, testInfo, nom) {
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  ouverts.push(ctx)
  await ctx.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1'); localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await connexionApi(ctx.request, { username: nom, password: MDP_ESSAI })
  const visites = await ctx.request.get(`${API}/onboarding/tours/`, T)
  if (visites.ok()) {
    for (const v of await visites.json()) {
      if (!v.vu) await ctx.request.post(`${API}/onboarding/tours/${v.tour_key}/vu/`, T)
    }
  }
  return ctx
}
/** Un onglet observé (oracles) du contexte ; la page demo_admin de l'étape est refermée (capture = rôle joué). */
async function onglet(page, suivi, ctx) {
  if (!page.isClosed()) await page.close()
  return suivi.surveiller(await ctx.newPage())
}

/** Tient les POST qui matchent `rx` jusqu'à `liberer()` (le bouton est affirmé désactivé entre-temps). */
async function tenir(p, rx) {
  const envois = []
  let ouvrir
  const tenu = new Promise((r) => { ouvrir = r })
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    envois.push(route.request().postDataJSON())
    await tenu
    return route.continue()
  })
  return { envois, liberer: () => ouvrir(), fin: () => p.unroute(rx) }
}
/** Coupe la réponse du 1er POST qui matche `rx` APRÈS l'avoir livré au serveur ; les suivants passent. */
async function couper(p, rx, suivi) {
  suivi.attendre(rx, 'reseau')
  const envois = []
  let coupe = true
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    envois.push(route.request().postDataJSON())
    if (coupe) {
      coupe = false
      await route.fetch()
      return route.abort('failed')
    }
    return route.continue()
  })
  return envois
}
const reponse = (p, rx, methode = 'POST') => p.waitForResponse((x) => x.request().method() === methode && rx.test(new URL(x.url()).pathname), T)

// ── données ──────────────────────────────────────────────────────────────────────────────────

/** Vente ACCEPTÉE : lead + devis portés par `cree`, produit + acceptation par demo_admin (`r`). */
async function venteAcceptee(r, cree, m, { prixHt = '5000.00', qte = '1', stock = null, echeancier = null, email = true, client = null } = {}) {
  let leadId = null
  if (!client) {
    leadId = (await lireJson(await cree.post(`${API}/crm/leads/`, {
      ...T, data: { nom: `ACNC ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), ...(email ? { email: `acnc-${m}@example.invalid` } : {}) },
    }), 'lead')).id
  }
  const p = await lireJson(await r.post(`${API}/stock/produits/`, {
    ...T, data: { nom: `Panneau ACNC ${m}`, prix_vente: prixHt, prix_achat: '111.11', ...(stock !== null ? { quantite_stock: stock } : {}) },
  }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, {
    ...T,
    data: {
      taux_tva: '20.00', remise_globale: '0', ...(client ? { client } : { lead: leadId }),
      lignes: [{ produit: p.id, designation: p.nom, quantite: qte, prix_unitaire: prixHt, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis')
  if (echeancier) await lireJson(await r.put(`${API}/ventes/devis/${d.id}/echeancier/`, { ...T, data: { tranches: echeancier } }), 'échéancier')
  await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ACNC' } }), 'accepter')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { devisId: d.id, reference: relu.reference, leadId, produitId: p.id, produitNom: p.nom, client: relu.client, ttc: relu.total_ttc, liees: relu.factures_liees || [] }
}
const lireF = async (ctx, id) => lireJson(await ctx.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)
/** Facture COMPLÈTE émise du devis par `c` (créée par lui : portée du rôle). */
async function factureEmise(c, v) {
  const rep = await lireJson(await c.post(`${API}/ventes/devis/${v.devisId}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facturer-complet')
  const f = await lireF(c, rep.facture_id)
  expect(f.statut, `facture ${f.reference} émise`).toBe('emise')
  return f
}
const payer = async (c, id, montant, mode = 'virement') => lireJson(await c.post(`${API}/ventes/factures/${id}/enregistrer-paiement/`, {
  ...T, data: { montant: f2(montant), date_paiement: AUJ(), mode, reference: `PAY-${marque()}` },
}), 'paiement')
/** Le brouillon d'acompte provisoire posé à l'acceptation (VNT62). */
async function brouillonAcompte(r, v) {
  const d = await lireJson(await r.get(`${API}/ventes/devis/${v.devisId}/`, T), 'devis relu')
  const b = (d.factures_liees || []).find((x) => x.statut === 'brouillon')
  expect(b, 'un brouillon d\'acompte posé à l\'acceptation').toBeTruthy()
  return lireF(r, b.id)
}
const etatFacture = (id) => bd(`f = Facture.objects.filter(pk=${id}).first()
sortie(None if f is None else {'statut': f.statut, 'reference': f.reference, 'ttc': str(f.total_ttc), 'du': str(f.montant_du)})`)
const LEGALE = /^FAC-/

/** Ligne de la facture dans /ventes/factures. */
async function ligneFacture(p, ref, id) {
  await p.goto('/ventes/factures')
  await p.getByPlaceholder('Référence, client').fill(ref, { timeout: 60_000 })
  const ligne = p.locator(`#facture-row-${id}`).first()
  await expect(ligne, `ligne ${ref}`).toBeVisible({ timeout: 60_000 })
  return ligne
}

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC1 — « Enregistrer un paiement » rejouable par clé
// ════════════════════════════════════════════════════════════════════════════════════════════
const etatPaiements = (id) => bd(`f = Facture.objects.get(pk=${id})
sortie({'paiements': [[str(p.montant), p.idempotency_key] for p in Paiement.objects.filter(facture=f).order_by('pk')],
        'journal': f.activites.filter(field='paiement').count(), 'du': str(f.montant_du), 'ttc': str(f.total_ttc), 'statut': f.statut})`)

etape('PF9.1-reseau', ['ACNC1'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc1', 'Commercial')
  const m = marque()
  const v = await venteAcceptee(r, c, m, { prixHt: '8333.33' })
  const f = await factureEmise(c, v)
  note(testInfo, 'Given', `facture ${f.reference} émise, TTC ${f.total_ttc}`)
  const url = `${API}/ventes/factures/${f.id}/enregistrer-paiement/`
  const corps = { montant: '5000.00', mode: 'virement', reference: `VIR-889-${m}`, date_paiement: AUJ(), idempotency_key: `acnc1-${m}` }
  // Deux envois IDENTIQUES en parallèle (même clé) : 201 + 200 rejoué, un seul paiement.
  const reps = await Promise.all([1, 2].map(() => c.post(url, { ...T, data: corps })))
  expect(statuts(reps), `deux envois parallèles même clé : ${await reps[0].text()} | ${await reps[1].text()}`).toEqual([200, 201])
  const tiers = await c.post(url, { ...T, data: corps })
  expect(tiers.status(), '3e envoi séquentiel même clé : 200 rejoué').toBe(200)
  const e = await etatPaiements(f.id)
  expect(e.paiements, 'UN paiement de 5 000 portant la clé').toEqual([['5000.00', corps.idempotency_key]])
  expect(e.journal, 'UNE ligne « Paiement » au journal de la facture').toBe(1)
  expect(cents(e.du), 'reste dû = TTC − 5 000').toBe(cents(e.ttc) - 500000)
  // Sans clé : chemin inchangé ; deux envois parallèles de 6 000 sur une facture de ~10 000 ⇒ le verrou de la
  // facture n'en laisse passer qu'UN (le 2e dépasse le reste dû : 409), jamais deux.
  const v2 = await venteAcceptee(r, c, `${m}b`, { prixHt: '8333.33' })
  const g = await factureEmise(c, v2)
  const sans = { montant: '6000.00', mode: 'virement', reference: `VIR-SANS-${m}`, date_paiement: AUJ() }
  const reps2 = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/factures/${g.id}/enregistrer-paiement/`, { ...T, data: sans })))
  expect(statuts(reps2), `sans clé, 2 × 6 000 parallèles : ${await reps2[0].text()} | ${await reps2[1].text()}`).toEqual([201, 409])
  const e2 = await etatPaiements(g.id)
  expect(e2.paiements.length, 'sans clé : un seul paiement écrit').toBe(1)
  expect(cents(e2.du)).toBe(cents(e2.ttc) - 600000)
})

etape('PF9.1-ecran', ['ACNC1'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc1e', 'Commercial')
  const m = marque()
  const fa = await factureEmise(c, await venteAcceptee(r, c, `${m}a`, { prixHt: '8333.33' }))
  const fb = await factureEmise(c, await venteAcceptee(r, c, `${m}b`, { prixHt: '8333.33' }))
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const rx = /\/enregistrer-paiement\/$/
  const ouvrir = async (f) => {
    const ligne = await ligneFacture(p, f.reference, f.id)
    await ligne.getByRole('button', { name: /Encaisser/ }).first().click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.locator('#pay-montant').fill('5000.00')
    await dlg.locator('#pay-ref').fill(`VIR-889-${marque()}`)
    return dlg
  }
  // (a) Double clic pendant que l'envoi est TENU : bouton désactivé (aria-busy), une seule clé envoyée.
  let dlg = await ouvrir(fa)
  const t = await tenir(p, rx)
  let btn = dlg.getByRole('button', { name: 'Enregistrer', exact: true })
  await btn.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btn, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  await expect(btn).toHaveAttribute('aria-busy', 'true')
  t.liberer()
  await expect(dlg, 'dialogue refermé au succès').toBeHidden({ timeout: 60_000 })
  await t.fin()
  expect(new Set(t.envois.map((x) => x.idempotency_key)).size, `${t.envois.length} envoi(s), une seule clé`).toBe(1)
  expect(t.envois[0].idempotency_key, 'clé envoyée').toBeTruthy()
  let e = await etatPaiements(fa.id)
  expect(e.paiements.length, 'double clic ⇒ UN paiement').toBe(1)
  // (b) Réseau coupé APRÈS l'envoi : le serveur a enregistré, l'écran n'a pas de réponse ; le reste dû est
  // relu et réaffiché ; nouveau clic ⇒ même clé ⇒ 200 rejoué, toujours UN paiement.
  dlg = await ouvrir(fb)
  btn = dlg.getByRole('button', { name: 'Enregistrer', exact: true })
  const envois = await couper(p, rx, suivi)
  await btn.click()
  await expect(dlg.getByRole('alert'), 'échec sans réponse affiché').toBeVisible({ timeout: 60_000 })
  await expect(dlg, 'saisie gardée').toBeVisible()
  const du = f2(Number(fb.total_ttc) - 5000)
  await expect.poll(async () => (plat(await dlg.innerText()).match(/Dû(\d+\.\d{2})/) || [])[1], { timeout: 30_000, message: 'reste dû relu et réaffiché avant tout renvoi' }).toBe(du)
  const [rep] = await Promise.all([reponse(p, rx), btn.click()])
  expect(rep.status(), `renvoi : ${(await rep.text()).slice(0, 200)}`).toBe(200)
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await p.unroute(rx)
  expect(envois.length).toBe(2)
  expect(envois[0].idempotency_key, 'la clé est GARDÉE entre les deux clics').toBe(envois[1].idempotency_key)
  e = await etatPaiements(fb.id)
  expect(e.paiements.length, 'coupure + renvoi ⇒ UN paiement').toBe(1)
  expect(f2(e.du)).toBe(du)
  // Persistance : rechargé, le dialogue de la facture liste UN paiement.
  await p.reload()
  const ligne = await ligneFacture(p, fb.reference, fb.id)
  await ligne.getByRole('button', { name: /Encaisser/ }).first().click()
  const relu = p.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${fb.reference}` })
  await expect(relu).toBeVisible({ timeout: 30_000 })
  await expect(relu.getByText('Paiements encaissés').locator('xpath=..').locator('li'), 'un seul paiement listé').toHaveCount(1)
}, { ecart: ECART_TOURNEE })

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC2 — note de débit rejouable par clé (Directeur)
// ════════════════════════════════════════════════════════════════════════════════════════════
const etatNotes = (id) => bd(`f = Facture.objects.get(pk=${id})
sortie({'notes': [[n.pk, n.reference] for n in NoteDebit.objects.filter(facture=f).order_by('pk')], 'du': str(f.montant_du), 'ttc': str(f.total_ttc)})`)

etape('PF9.2-reseau', ['ACNC2'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await acteur(testInfo, 'acnc2', 'Directeur')
  const m = marque()
  const f = await factureEmise(r, await venteAcceptee(r, r, m, { prixHt: '8333.33' }))
  const url = `${API}/ventes/factures/${f.id}/creer-note-debit/`
  const corps = { motif: 'pénalité', montant: '500', taux_tva: '20', idempotency_key: `acnc2-${m}` }
  const reps = await Promise.all([1, 2].map(() => d.post(url, { ...T, data: corps })))
  const corpsReps = await Promise.all(reps.map(async (x) => ({ s: x.status(), j: await x.json() })))
  for (const x of corpsReps) {
    expect(x.s === 201 || (x.s === 409 && x.j.code === 'idempotency_en_cours'), `envoi parallèle : ${x.s} ${JSON.stringify(x.j).slice(0, 200)}`).toBe(true)
  }
  const crees = corpsReps.filter((x) => x.s === 201)
  expect(new Set(crees.map((x) => x.j.id)).size, 'les 201 rendent la MÊME note').toBe(1)
  note(testInfo, 'course même clé', corpsReps.map((x) => x.s).join(' + '))
  const tiers = await d.post(url, { ...T, data: corps })
  expect(tiers.status()).toBe(201)
  const tj = await tiers.json()
  expect([tj.id, tj.reference], '3e envoi : même id, même référence').toEqual([crees[0].j.id, crees[0].j.reference])
  const autre = await d.post(url, { ...T, data: { ...corps, montant: '700' } })
  expect(autre.status(), 'corps différent sous la même clé').toBe(409)
  let e = await etatNotes(f.id)
  expect(e.notes.length, 'UNE note de débit').toBe(1)
  expect(cents(e.du), 'dû majoré une fois (+600)').toBe(cents(e.ttc) + 60000)
  // Sans clé : chemin inchangé (chaque envoi crée) — deux envois parallèles prennent deux numéros DISTINCTS.
  const g = await factureEmise(r, await venteAcceptee(r, r, `${m}b`, { prixHt: '8333.33' }))
  const sans = await Promise.all([1, 2].map(() => d.post(`${API}/ventes/factures/${g.id}/creer-note-debit/`, { ...T, data: { motif: 'pénalité', montant: '500', taux_tva: '20' } })))
  expect(statuts(sans), 'sans clé : deux créations').toEqual([201, 201])
  e = await etatNotes(g.id)
  expect(new Set(e.notes.map((x) => x[1])).size, 'sans clé : deux numéros ND distincts').toBe(2)
})

etape('PF9.2-ecran', ['ACNC2'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc2e', 'Directeur')
  const m = marque()
  const fa = await factureEmise(r, await venteAcceptee(r, r, `${m}a`, { prixHt: '8333.33' }))
  const fb = await factureEmise(r, await venteAcceptee(r, r, `${m}b`, { prixHt: '8333.33' }))
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const rx = /\/creer-note-debit\/$/
  const ouvrir = async (f) => {
    const ligne = await ligneFacture(p, f.reference, f.id)
    await ligne.getByRole('button', { name: /Actions/ }).click()
    await p.getByRole('menuitem', { name: 'Note de débit' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Notes de débit — ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.locator('#nd-motif').fill('pénalité')
    await dlg.locator('#nd-montant').fill('500')
    return dlg
  }
  let dlg = await ouvrir(fa)
  let btn = dlg.getByRole('button', { name: 'Créer la note de débit' })
  const t = await tenir(p, rx)
  await btn.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btn, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  t.liberer()
  await expect(dlg.locator('li').filter({ hasText: /ND-/ }), 'une note listée').toHaveCount(1, { timeout: 60_000 })
  await t.fin()
  expect(new Set(t.envois.map((x) => x.idempotency_key)).size, `${t.envois.length} envoi(s), une seule clé`).toBe(1)
  expect((await etatNotes(fa.id)).notes.length, 'double clic ⇒ UNE note').toBe(1)
  await p.keyboard.press('Escape')
  // Réseau coupé après « Créer » : la liste des notes est RELUE (la note créée y paraît) ; nouveau clic ⇒ rejeu.
  dlg = await ouvrir(fb)
  btn = dlg.getByRole('button', { name: 'Créer la note de débit' })
  const envois = await couper(p, rx, suivi)
  await btn.click()
  await expect(dlg.getByRole('alert'), 'échec sans réponse affiché').toBeVisible({ timeout: 60_000 })
  await expect(dlg.locator('li').filter({ hasText: /ND-/ }), 'liste relue après l\'échec : la note créée paraît').toHaveCount(1, { timeout: 60_000 })
  const [rep] = await Promise.all([reponse(p, rx), btn.click()])
  expect(rep.status(), 'renvoi : rejeu 201').toBe(201)
  await expect(dlg.locator('li').filter({ hasText: /ND-/ }), 'toujours UNE note').toHaveCount(1, { timeout: 60_000 })
  await p.unroute(rx)
  expect(envois.length).toBe(2)
  expect(envois[0].idempotency_key, 'clé gardée entre les deux clics').toBe(envois[1].idempotency_key)
  const e = await etatNotes(fb.id)
  expect(e.notes.length, 'coupure + renvoi ⇒ UNE note').toBe(1)
  expect(cents(e.du), 'montant_du majoré une fois').toBe(cents(e.ttc) + 60000)
  await p.reload()
  const ligne = await ligneFacture(p, fb.reference, fb.id)
  await ligne.getByRole('button', { name: /Actions/ }).click()
  await p.getByRole('menuitem', { name: 'Note de débit' }).click()
  await expect(p.getByRole('dialog').filter({ hasText: `Notes de débit — ${fb.reference}` }).locator('li').filter({ hasText: /ND-/ }), 'rechargé : une note').toHaveCount(1, { timeout: 60_000 })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC3 — avoir partiel et retour client rejouables par clé (Commercial : `encaisser`)
// ════════════════════════════════════════════════════════════════════════════════════════════
const etatAvoirs = (id, produit) => bd(`f = Facture.objects.get(pk=${id})
avs = list(Avoir.objects.filter(facture=f).order_by('pk'))
refs = [a.reference for a in avs]
sortie({'avoirs': [[a.pk, a.reference, a.type] for a in avs],
        'avances': [[str(p.montant), p.reference] for p in Paiement.objects.filter(facture__isnull=True, client_id=f.client_id, reference__in=refs).order_by('pk')],
        'entrees': [[m.reference, m.quantite] for m in MouvementStock.objects.filter(produit_id=${produit}, type_mouvement='entree', reference__in=refs).order_by('pk')],
        'stock': Produit.objects.get(pk=${produit}).quantite_stock})`)
/** Facture PAYÉE de 3 panneaux (stock 10), créée et soldée par `c`. */
async function facturePayee3(r, c, m) {
  const v = await venteAcceptee(r, c, m, { prixHt: '1000.00', qte: '3', stock: 10 })
  const f = await factureEmise(c, v)
  await payer(c, f.id, f.total_ttc)
  const fp = await lireF(c, f.id)
  expect(fp.statut, 'Given : facture payée').toBe('payee')
  return { v, f: fp, ligne: fp.lignes.find((l) => l.produit === v.produitId) }
}
const enCours = (x) => x.s === 409 && x.j.code === 'idempotency_en_cours'

etape('PF9.3-reseau', ['ACNC3'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc3', 'Commercial')
  const m = marque()
  const { v, f, ligne } = await facturePayee3(r, c, m)
  const rejouer = async (chemin, corps) => {
    const reps = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/factures/${f.id}/${chemin}/`, { ...T, data: corps })))
    const x = await Promise.all(reps.map(async (y) => ({ s: y.status(), j: await y.json() })))
    for (const y of x) expect(y.s === 201 || enCours(y), `${chemin} parallèle : ${y.s} ${JSON.stringify(y.j).slice(0, 200)}`).toBe(true)
    const crees = x.filter((y) => y.s === 201)
    expect(new Set(crees.map((y) => y.j.id)).size, `${chemin} : les 201 rendent le MÊME avoir`).toBe(1)
    const tiers = await c.post(`${API}/ventes/factures/${f.id}/${chemin}/`, { ...T, data: corps })
    expect(tiers.status()).toBe(201)
    const tj = await tiers.json()
    expect([tj.id, tj.reference], `${chemin} : 3e envoi = même id, même référence`).toEqual([crees[0].j.id, crees[0].j.reference])
    note(testInfo, `course ${chemin}`, x.map((y) => y.s).join(' + '))
    return tj
  }
  // Geste commercial d'1 panneau (partiel : le corps publié n'a pas de `montant`, la clause l'écrit en montant).
  const avoir = await rejouer('creer-avoir', {
    type: 'geste_commercial', motif: 'geste ACNC3', idempotency_key: `acnc3a-${m}`,
    lignes: [{ produit: ligne.produit, designation: ligne.designation, quantite: '1', prix_unitaire: ligne.prix_unitaire, remise: '0', taux_tva: ligne.taux_tva }],
  })
  let e = await etatAvoirs(f.id, v.produitId)
  const stockAvant = e.stock
  expect(e.avoirs.length, 'UN avoir geste commercial').toBe(1)
  expect(e.avances.length, 'UNE avance (facture déjà payée)').toBe(1)
  expect(f2(e.avances[0][0]), 'avance = TTC de l\'avoir').toBe(f2(avoir.total_ttc))
  await rejouer('retour-client', { motif: 'retour ACNC3', restocker: true, lignes: [{ produit: v.produitId, quantite: '1' }], idempotency_key: `acnc3r-${m}` })
  e = await etatAvoirs(f.id, v.produitId)
  expect(e.avoirs.length, 'deux avoirs (un par geste)').toBe(2)
  expect(e.entrees.length, 'UN mouvement d\'entrée de stock').toBe(1)
  expect(e.entrees[0][1]).toBe(1)
  expect(e.stock, 'stock + 1').toBe(stockAvant + 1)
  // Sans clé (chemin inchangé) : deux retours parallèles d'1 panneau — chaque avoir de retour créé porte
  // EXACTEMENT son entrée de stock (jamais deux entrées pour un avoir, jamais d'entrée orpheline).
  const sans = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/factures/${f.id}/retour-client/`, { ...T, data: { motif: 'retour sans clé', restocker: true, lignes: [{ produit: v.produitId, quantite: '1' }] } })))
  for (const y of sans) expect(y.status(), `sans clé : ${(await y.text()).slice(0, 200)}`).toBeLessThan(500)
  const nCrees = sans.filter((y) => y.status() === 201).length
  const e2 = await etatAvoirs(f.id, v.produitId)
  note(testInfo, 'sans clé', `statuts ${statuts(sans).join(' + ')} ; avoirs ${e2.avoirs.length}, entrées ${e2.entrees.length}`)
  expect(e2.avoirs.length, 'un avoir par retour accepté').toBe(2 + nCrees)
  expect(e2.entrees.length, 'une entrée par avoir de retour').toBe(1 + nCrees)
  expect(e2.stock).toBe(stockAvant + 1 + nCrees)
})

etape('PF9.3-ecran', ['ACNC3'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc3e', 'Commercial')
  const { v, f } = await facturePayee3(r, c, marque())
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const base = await etatAvoirs(f.id, v.produitId)
  // (a) Avoir partiel : double clic tenu.
  let ligne = await ligneFacture(p, f.reference, f.id)
  await ligne.getByRole('button', { name: 'Avoir', exact: true }).click()
  const dlgA = p.getByRole('dialog').filter({ hasText: `Créer un avoir — ${f.reference}` })
  await expect(dlgA).toBeVisible({ timeout: 30_000 })
  await dlgA.locator('input[type=number]').first().fill('1')
  const rxA = /\/creer-avoir\/$/
  const ta = await tenir(p, rxA)
  const btnA = dlgA.getByRole('button', { name: 'Avoir partiel' })
  await btnA.dblclick()
  await expect.poll(() => ta.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btnA, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  ta.liberer()
  await expect(dlgA).toBeHidden({ timeout: 60_000 })
  await ta.fin()
  expect(new Set(ta.envois.map((x) => x.idempotency_key)).size, `${ta.envois.length} envoi(s), une seule clé`).toBe(1)
  let e = await etatAvoirs(f.id, v.produitId)
  expect(e.avoirs.length, 'double clic ⇒ UN avoir').toBe(base.avoirs.length + 1)
  // (b) Retour client : double clic tenu (1 panneau, remis en stock).
  const ouvrirRetour = async () => {
    ligne = await ligneFacture(p, f.reference, f.id)
    await ligne.getByRole('button', { name: /Actions/ }).click()
    await p.getByTestId('retour-client').click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Retour client — ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.locator('#retour-motif').fill('retour ACNC3 écran')
    await dlg.getByRole('checkbox', { name: 'Remettre en stock' }).click()
    await dlg.locator('input[type=number]').first().fill('1')
    return dlg
  }
  const rxR = /\/retour-client\/$/
  let dlg = await ouvrirRetour()
  const tr = await tenir(p, rxR)
  const btnR = dlg.getByRole('button', { name: 'Enregistrer le retour' })
  await btnR.dblclick()
  await expect.poll(() => tr.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btnR, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  await expect(btnR).toHaveAttribute('aria-busy', 'true')
  tr.liberer()
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await tr.fin()
  expect(new Set(tr.envois.map((x) => x.idempotency_key)).size).toBe(1)
  e = await etatAvoirs(f.id, v.produitId)
  expect(e.entrees.length, 'double clic ⇒ UN retour, UNE entrée de stock').toBe(1)
  expect(e.stock).toBe(base.stock + 1)
  // (c) Retour d'1 panneau, réseau coupé après l'envoi, nouveau clic ⇒ un seul avoir de plus, stock + 1.
  dlg = await ouvrirRetour()
  const envois = await couper(p, rxR, suivi)
  await btnR.click()
  await expect.poll(async () => (await etatAvoirs(f.id, v.produitId)).entrees.length, { timeout: 60_000, message: 'le serveur a reçu le 1er envoi' }).toBe(2)
  await expect(dlg, 'dialogue gardé après l\'échec sans réponse').toBeVisible()
  const [rep] = await Promise.all([reponse(p, rxR), btnR.click()])
  expect(rep.status(), 'renvoi : rejeu 201').toBe(201)
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await p.unroute(rxR)
  expect(envois[0].idempotency_key, 'clé gardée entre les deux clics').toBe(envois[1].idempotency_key)
  e = await etatAvoirs(f.id, v.produitId)
  expect(e.avoirs.length, 'un avoir par geste (partiel + 2 retours)').toBe(base.avoirs.length + 3)
  expect(e.entrees.length, 'deux entrées (une par retour)').toBe(2)
  expect(e.stock, 'stock + 2 au total (+1 par retour)').toBe(base.stock + 2)
  // Persistance : rechargée, la facture porte ses 3 avoirs.
  await p.reload()
  const relue = await lireF(c, f.id)
  expect(cents(relue.avoirs_total), 'avoirs relus').toBeGreaterThan(0)
  await ligneFacture(p, f.reference, f.id)
}, { ecart: ECART_TOURNEE })

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC5 — « Supprimer » qui croise « Émettre » : 409, facture émise numérotée gardée (Directeur)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.5-reseau', ['ACNC5'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await acteur(testInfo, 'acnc5', 'Directeur')
  const m = marque()
  // (a) Séquentiel : brouillon chargé, émis par un collègue, puis supprimé ⇒ 409, émise gardée.
  const b = await brouillonAcompte(r, await venteAcceptee(r, r, `${m}a`))
  expect(b.reference, 'Given : BROUILLON-').toMatch(/^BROUILLON-/)
  expect((await d.post(`${API}/ventes/factures/${b.id}/emettre/`, { ...T, data: {} })).status(), 'émission').toBe(200)
  const sup = await d.delete(`${API}/ventes/factures/${b.id}/`, T)
  expect(sup.status(), `supprimer après émission : ${(await sup.text()).slice(0, 200)}`).toBe(409)
  expect(String((await sup.json()).detail)).toContain('Seule une facture brouillon')
  const e = await etatFacture(b.id)
  expect([e.statut, LEGALE.test(e.reference)], 'facture émise, numéro légal, en base').toEqual(['emise', true])
  // (b) Course réelle : « Émettre » et « Supprimer » partent en même temps (deux comptes Directeur).
  const { ctx: d2 } = await acteur(testInfo, 'acnc5b', 'Directeur')
  for (const tour of [1, 2]) {
    const c = await brouillonAcompte(r, await venteAcceptee(r, r, `${m}c${tour}`))
    const [em, de] = await Promise.all([d.post(`${API}/ventes/factures/${c.id}/emettre/`, { ...T, data: {} }), d2.delete(`${API}/ventes/factures/${c.id}/`, T)])
    const apres = await etatFacture(c.id)
    note(testInfo, `course ${tour}`, `émettre ${em.status()}, supprimer ${de.status()}, base ${JSON.stringify(apres)}`)
    expect(em.status() === 200 && de.status() === 204, 'jamais émise ET supprimée').toBe(false)
    if (apres) expect([apres.statut, LEGALE.test(apres.reference), de.status()], 'en base : émise numérotée, suppression refusée').toEqual(['emise', true, 409])
    else expect([de.status(), em.status() >= 400], 'supprimée : l\'émission a échoué').toEqual([204, true])
  }
})

etape('PF9.5-ecran', ['ACNC5'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc5e', 'Directeur')
  const m = marque()
  const ctx = await navigateur(page, testInfo, nom)
  // (a) Panneau de vente (fiche lead) : pendant « Émettre » en vol, les autres gestes de la facture sont grisés.
  const v = await venteAcceptee(r, r, `${m}a`)
  const b = await brouillonAcompte(r, v)
  const p = await onglet(page, suivi, ctx)
  await p.goto(`/crm/leads/${v.leadId}`)
  await p.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  const li = p.getByRole('region', { name: `Vente du devis ${v.reference}` }).getByTestId(`facture-vente-${b.id}`)
  await expect(li).toBeVisible({ timeout: 60_000 })
  const rxE = new RegExp(`/ventes/factures/${b.id}/emettre/$`)
  const t = await tenir(p, rxE)
  const emettre = li.getByRole('button', { name: 'Émettre' })
  await emettre.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(emettre, '« Émettre » en vol').toHaveAttribute('aria-busy', 'true')
  await expect(li.getByRole('button', { name: 'Supprimer' }), '« Supprimer » grisé pendant le geste').toBeDisabled()
  await expect(li.getByRole('button', { name: 'Modifier le montant' }), '« Modifier le montant » grisé').toBeDisabled()
  t.liberer()
  await expect(li.getByRole('button', { name: 'Supprimer' }), 'émise : plus de « Supprimer »').toHaveCount(0, { timeout: 60_000 })
  await t.fin()
  expect(t.envois.length, 'double clic ⇒ une émission envoyée').toBe(1)
  let e = await etatFacture(b.id)
  expect([e.statut, LEGALE.test(e.reference)]).toEqual(['emise', true])
  // (b) Deux onglets /ventes/factures : Émettre dans l'un, Supprimer dans l'autre ⇒ 409, facture émise listée.
  const c = await brouillonAcompte(r, await venteAcceptee(r, r, `${m}b`))
  const pB = suivi.surveiller(await ctx.newPage())
  const ligneB = await ligneFacture(pB, c.reference, c.id)
  const ligneA = await ligneFacture(p, c.reference, c.id)
  await ligneA.getByRole('button', { name: /Émettre/ }).first().click()
  const [rep] = await Promise.all([reponse(p, new RegExp(`/ventes/factures/${c.id}/emettre/$`)), p.getByRole('alertdialog').getByRole('button', { name: 'Confirmer' }).click()])
  expect(rep.status(), 'onglet A : émise').toBe(200)
  const rxD = new RegExp(`/ventes/factures/${c.id}/$`)
  suivi.attendre(rxD, 409) // le refus PROUVÉ par l'étape
  await ligneB.getByRole('button', { name: /Actions/ }).click()
  await pB.getByTestId('supprimer-brouillon').click()
  const [del] = await Promise.all([reponse(pB, rxD, 'DELETE'), pB.getByTestId('supprimer-brouillon-confirmer').click()])
  expect(del.status(), 'onglet B : supprimer ⇒ 409').toBe(409)
  await expect(pB.getByText(/Seule une facture brouillon peut être supprimée/).first(), 'refus affiché dans l\'onglet B').toBeVisible({ timeout: 30_000 })
  e = await etatFacture(c.id)
  expect([e.statut, LEGALE.test(e.reference)], 'en base : émise, numéro légal').toEqual(['emise', true])
  await pB.reload()
  await ligneFacture(pB, e.reference, c.id)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC6 — montant de tranche croisé avec « Émettre » ; remise clôturée ni supprimée ni rouverte
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.6-reseau', ['ACNC6'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await acteur(testInfo, 'acnc6', 'Directeur')
  const { ctx: d2 } = await acteur(testInfo, 'acnc6b', 'Directeur')
  const m = marque()
  // Brouillon de TRANCHE (l'acompte posé à l'acceptation : `cle_tranche`, montant en MAD).
  const b = await brouillonAcompte(r, await venteAcceptee(r, r, `${m}a`))
  expect((await d.post(`${API}/ventes/factures/${b.id}/emettre/`, { ...T, data: {} })).status()).toBe(200)
  const mt = await d2.post(`${API}/ventes/factures/${b.id}/montant-tranche/`, { ...T, data: { montant_ttc: f2(b.total_ttc) } })
  expect(mt.status(), `montant inchangé après émission : ${(await mt.text()).slice(0, 200)}`).toBe(409)
  let e = await etatFacture(b.id)
  expect([e.statut, LEGALE.test(e.reference), e.ttc], 'émise, numérotée, montant intact').toEqual(['emise', true, f2(b.total_ttc)])
  // Course réelle : « Émettre » et « Modifier le montant » (même montant) en même temps.
  for (const tour of [1, 2]) {
    const c = await brouillonAcompte(r, await venteAcceptee(r, r, `${m}c${tour}`))
    const [em, mo] = await Promise.all([
      d.post(`${API}/ventes/factures/${c.id}/emettre/`, { ...T, data: {} }),
      d2.post(`${API}/ventes/factures/${c.id}/montant-tranche/`, { ...T, data: { montant_ttc: f2(c.total_ttc) } }),
    ])
    e = await etatFacture(c.id)
    note(testInfo, `course tranche ${tour}`, `émettre ${em.status()}, montant ${mo.status()}, base ${JSON.stringify(e)}`)
    expect(em.status(), 'émission').toBe(200)
    expect([200, 409], 'montant : appliqué avant ou refusé après').toContain(mo.status())
    expect([e.statut, LEGALE.test(e.reference), e.ttc], 'jamais repassée en brouillon').toEqual(['emise', true, f2(c.total_ttc)])
  }
  // Remise d'encaissement : clôturée ⇒ DELETE et PATCH 409 ; course clôturer / supprimer.
  const remise = async (suffixe) => {
    const f = await factureEmise(r, await venteAcceptee(r, r, `${m}${suffixe}`))
    await payer(r, f.id, 1000, 'especes')
    const pid = (await lireF(r, f.id)).paiements.at(-1).id
    return lireJson(await d.post(`${API}/ventes/remises-encaissement/`, { ...T, data: { date_collecte: AUJ(), montant_declare: '1000.00', lignes: [{ paiement: pid }] } }), 'remise')
  }
  const etatRemise = (id) => bd(`x = RemiseEncaissement.objects.filter(pk=${id}).first()
sortie(None if x is None else x.statut)`)
  const r1 = await remise('r1')
  expect((await d.post(`${API}/ventes/remises-encaissement/${r1.id}/cloturer/`, { ...T, data: {} })).status(), 'clôture').toBe(200)
  const statutClos = await etatRemise(r1.id)
  expect(statutClos).not.toBe('ouverte')
  const [del, pat] = await Promise.all([
    d2.delete(`${API}/ventes/remises-encaissement/${r1.id}/`, T),
    d2.patch(`${API}/ventes/remises-encaissement/${r1.id}/`, { ...T, data: { note: 'rouverte ?' } }),
  ])
  expect([del.status(), pat.status()], 'remise clôturée : DELETE et PATCH refusés').toEqual([409, 409])
  expect(await etatRemise(r1.id), 'toujours clôturée').toBe(statutClos)
  const r2 = await remise('r2')
  const [clo, sup] = await Promise.all([
    d.post(`${API}/ventes/remises-encaissement/${r2.id}/cloturer/`, { ...T, data: {} }),
    d2.delete(`${API}/ventes/remises-encaissement/${r2.id}/`, T),
  ])
  const apres = await etatRemise(r2.id)
  note(testInfo, 'course remise', `clôturer ${clo.status()}, supprimer ${sup.status()}, base ${apres}`)
  expect(clo.status() === 200 && sup.status() === 204, 'jamais clôturée ET supprimée').toBe(false)
  if (apres) expect([apres, sup.status()], 'en base : clôturée, suppression refusée').toEqual([statutClos, 409])
  else expect(clo.status()).toBeGreaterThanOrEqual(400)
})

etape('PF9.6-ecran', ['ACNC6'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc6e', 'Directeur')
  const v = await venteAcceptee(r, r, marque())
  const b = await brouillonAcompte(r, v)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const panneau = async (p) => {
    await p.goto(`/crm/leads/${v.leadId}`)
    await p.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
    const li = p.getByRole('region', { name: `Vente du devis ${v.reference}` }).getByTestId(`facture-vente-${b.id}`)
    await expect(li).toBeVisible({ timeout: 60_000 })
    return li
  }
  const liB = await panneau(pB)
  await liB.getByRole('button', { name: 'Modifier le montant' }).click()
  await expect(liB.getByLabel(`Montant TTC de ${b.reference}`), 'montant prérempli').toHaveValue(/\d/)
  const liA = await panneau(pA)
  const [em] = await Promise.all([reponse(pA, new RegExp(`/ventes/factures/${b.id}/emettre/$`)), liA.getByRole('button', { name: 'Émettre' }).click()])
  expect(em.status(), 'onglet A : émise').toBe(200)
  const rxM = new RegExp(`/ventes/factures/${b.id}/montant-tranche/$`)
  suivi.attendre(rxM, 409)
  const [mo] = await Promise.all([reponse(pB, rxM), liB.getByRole('button', { name: 'Enregistrer' }).click()])
  expect(mo.status(), 'onglet B : montant inchangé enregistré ⇒ 409').toBe(409)
  await expect(liB.getByRole('alert'), 'refus affiché sur la ligne').toContainText('Seul un brouillon change de montant')
  const e = await etatFacture(b.id)
  expect([e.statut, LEGALE.test(e.reference)], 'en base : émise numérotée').toEqual(['emise', true])
  await pB.reload()
  await pB.getByTestId('lw-context-rail').getByRole('tab', { name: /devis/i }).click()
  await expect(pB.getByTestId(`facture-vente-${b.id}`), 'rechargé : facture émise').toContainText(e.reference, { timeout: 60_000 })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC7 — rejet, BC confirmé / annulé / facturé, « marquer payée » relus sous verrou
// ════════════════════════════════════════════════════════════════════════════════════════════
const reglerSociete = (champ, valeur) => py(`import decimal
from authentication.models import Company
from apps.parametres.models import CompanyProfile
pr = CompanyProfile.get(company=Company.objects.get(pk=${SOC}))
avant = getattr(pr, ${JSON.stringify(champ)})
setattr(pr, ${JSON.stringify(champ)}, ${valeur})
pr.save()
sortie(str(avant))`)
/** BC en attente d'une vente (produit en stock 20, 5 unités) + chantier lié (réservation U9/YDOCF7). */
async function bcEnAttente(r, m) {
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00', qte: '5', stock: 20 })
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${v.devisId}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
d = Devis.objects.get(pk=${v.devisId})
if not Installation.objects.filter(devis=d).exists():
    Installation.objects.create(company_id=d.company_id, reference='CHT-ACNC7-${m}', client_id=d.client_id, devis=d, statut=Installation.Statut.SIGNE)
sortie(1)`)
  return { v, bc }
}
const reservations = (v) => py(`from apps.installations.models import StockReservation
sortie([[x.quantite, x.active] for x in StockReservation.objects.filter(installation__devis_id=${v.devisId}, produit_id=${v.produitId})])`)

etape('PF9.7-reseau', ['ACNC7'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await acteur(testInfo, 'acnc7', 'Directeur')
  const { ctx: d2 } = await acteur(testInfo, 'acnc7b', 'Directeur')
  const m = marque()
  // (a) Deux « Confirmer » parallèles d'un BC en attente : 200 + 409, UNE réservation.
  const avant = await reglerSociete('reserver_stock_bc', 'True')
  try {
    const { v, bc } = await bcEnAttente(r, `${m}a`)
    const reps = await Promise.all([d, d2].map((x) => x.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} })))
    expect(statuts(reps), `confirmer ×2 : ${await reps[0].text()} | ${(await reps[1].text()).slice(0, 200)}`).toEqual([200, 409])
    expect(await reservations(v), 'UNE réservation de 5').toEqual([[5, true]])
  } finally {
    await reglerSociete('reserver_stock_bc', avant === 'True' ? 'True' : 'False')
  }
  // (b) « Créer la facture » et « Annuler » d'un BC confirmé en même temps : jamais BC annulé ET facture vivante.
  const { bc: bc2 } = await bcEnAttente(r, `${m}b`)
  await lireJson(await d.post(`${API}/ventes/bons-commande/${bc2.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  const [cf, an] = await Promise.all([
    d.post(`${API}/ventes/bons-commande/${bc2.id}/creer-facture/`, { ...T, data: {} }),
    d2.post(`${API}/ventes/bons-commande/${bc2.id}/annuler/`, { ...T, data: {} }),
  ])
  const e2 = await bd(`b = BonCommande.objects.get(pk=${bc2.id})
sortie({'bc': b.statut, 'vivantes': Facture.objects.filter(bon_commande_id=b.pk).exclude(statut='annulee').count()})`)
  note(testInfo, 'course BC', `creer-facture ${cf.status()}, annuler ${an.status()}, base ${JSON.stringify(e2)}`)
  expect(e2.bc === 'annule' && e2.vivantes > 0, 'jamais BC annulé avec une facture vivante').toBe(false)
  expect([cf.status() < 300, an.status() < 300], 'un seul des deux gestes aboutit').not.toEqual([true, true])
  // BC annulé puis « Créer la facture » (séquentiel) ⇒ 409.
  const { bc: bc3 } = await bcEnAttente(r, `${m}c`)
  await lireJson(await d.post(`${API}/ventes/bons-commande/${bc3.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  await lireJson(await d.post(`${API}/ventes/bons-commande/${bc3.id}/annuler/`, { ...T, data: {} }), 'annuler BC')
  expect((await d2.post(`${API}/ventes/bons-commande/${bc3.id}/creer-facture/`, { ...T, data: {} })).status(), 'BC annulé ⇒ creer-facture 409').toBe(409)
  // (c) Deux rejets parallèles du même paiement : 200 + 409, UN « Paiement rejeté » au journal.
  const f = await factureEmise(r, await venteAcceptee(r, r, `${m}d`))
  await payer(r, f.id, 2000, 'cheque')
  const pid = (await lireF(r, f.id)).paiements[0].id
  const rej = await Promise.all([d, d2].map((x) => x.post(`${API}/ventes/paiements/${pid}/rejeter/`, { ...T, data: { motif: 'chèque impayé' } })))
  expect(statuts(rej), `rejeter ×2 : ${(await rej[1].text()).slice(0, 200)}`).toEqual([200, 409])
  expect(await bd(`sortie(FactureActivity.objects.filter(facture_id=${f.id}, field='paiement_rejete').count())`), 'UN paiement_rejete').toBe(1)
  // (d) Deux « marquer payée » parallèles : 200 + 200, UNE ligne de journal (tolérance société élargie le temps
  // du geste : sans elle le reste dû d'une facture neuve renvoie vers « abandonner le solde »).
  const g = await factureEmise(r, await venteAcceptee(r, r, `${m}e`))
  const tol = await reglerSociete('tolerance_ecart_reglement', 'decimal.Decimal("50000")')
  try {
    const mp = await Promise.all([d, d2].map((x) => x.post(`${API}/ventes/factures/${g.id}/marquer-payee/`, { ...T, data: { motif: 'réglé au guichet' } })))
    expect(statuts(mp), `marquer payée ×2 : ${(await mp[0].text()).slice(0, 200)}`).toEqual([200, 200])
  } finally {
    await reglerSociete('tolerance_ecart_reglement', tol === 'None' ? 'None' : `decimal.Decimal("${tol}")`)
  }
  const eg = await bd(`f = Facture.objects.get(pk=${g.id})
sortie({'statut': f.statut, 'traces': f.activites.filter(field_label='Marquée payée (manuel)').count()})`)
  expect(eg, 'payée, UNE trace').toEqual({ statut: 'payee', traces: 1 })
})

etape('PF9.7-ecran', ['ACNC7'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc7e', 'Directeur')
  const avant = await reglerSociete('reserver_stock_bc', 'True')
  try {
    const { v, bc } = await bcEnAttente(r, marque())
    const ctx = await navigateur(page, testInfo, nom)
    const pA = await onglet(page, suivi, ctx)
    const pB = suivi.surveiller(await ctx.newPage())
    const ligne = async (p) => {
      await p.goto('/ventes/bons-commande')
      await p.getByPlaceholder('Référence, client…').fill(bc.reference, { timeout: 60_000 })
      const l = p.getByRole('row').filter({ hasText: bc.reference })
      await expect(l).toBeVisible({ timeout: 60_000 })
      return l
    }
    const lB = await ligne(pB)
    const lA = await ligne(pA)
    const rx = new RegExp(`/ventes/bons-commande/${bc.id}/confirmer/$`)
    const [a] = await Promise.all([reponse(pA, rx), lA.getByRole('button', { name: 'Confirmer' }).click()])
    expect(a.status(), 'onglet A : confirmé').toBe(200)
    suivi.attendre(rx, 409)
    const [b] = await Promise.all([reponse(pB, rx), lB.getByRole('button', { name: 'Confirmer' }).click()])
    expect(b.status(), 'onglet B : 2e « Confirmer » ⇒ 409').toBe(409)
    await expect(pB.getByRole('alert').filter({ hasText: 'Seul un BC en attente peut être confirmé' }).first(), 'refus affiché').toBeVisible({ timeout: 30_000 })
    expect(await reservations(v), 'UNE réservation').toEqual([[5, true]])
    await pB.reload()
    const relu = await ligne(pB)
    await expect(relu.getByRole('button', { name: 'Confirmer' }), 'rechargé : BC confirmé').toHaveCount(0)
  } finally {
    await reglerSociete('reserver_stock_bc', avant === 'True' ? 'True' : 'False')
  }
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC8 — deux annulations simultanées (acompte et solde) ⇒ UN retour de stock
// ════════════════════════════════════════════════════════════════════════════════════════════
const mouvements = (v) => bd(`sortie({'mvts': [[x.type_mouvement, x.quantite] for x in MouvementStock.objects.filter(produit_id=${v.produitId}, reference=${JSON.stringify(v.reference)}).order_by('pk')], 'stock': Produit.objects.get(pk=${v.produitId}).quantite_stock})`)
async function venteAcompteSolde(r, m) {
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00', qte: '3', stock: 20, echeancier: [
    { type: 'acompte', libelle: 'Acompte', pct_or_montant: 30 }, { type: 'solde', libelle: 'Solde', pct_or_montant: 70 }] })
  const ids = []
  for (const tranche of ['acompte', 'solde']) {
    let f = await lireJson(await r.post(`${API}/ventes/devis/${v.devisId}/generer-facture/`, { ...T, data: {} }), `facture ${tranche}`)
    if (f.statut === 'brouillon') await lireJson(await r.post(`${API}/ventes/factures/${f.id}/emettre/`, { ...T, data: {} }), `émission ${tranche}`)
    f = await lireF(r, f.id)
    expect(f.statut, `${tranche} émis`).toBe('emise')
    ids.push(f.id)
  }
  return { v, ids }
}

etape('PF9.8-reseau', ['ACNC8'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await acteur(testInfo, 'acnc8', 'Directeur')
  const { ctx: d2 } = await acteur(testInfo, 'acnc8b', 'Directeur')
  const m = marque()
  for (const tour of [1, 2]) {
    const { v, ids } = await venteAcompteSolde(r, `${m}${tour}`)
    const avant = await mouvements(v)
    expect(avant.mvts, 'Given : 3 panneaux sortis une fois').toEqual([['sortie', 3]])
    const reps = await Promise.all([d.post(`${API}/ventes/factures/${ids[0]}/annuler/`, { ...T, data: {} }), d2.post(`${API}/ventes/factures/${ids[1]}/annuler/`, { ...T, data: {} })])
    expect(statuts(reps), `annulations croisées : ${(await reps[0].text()).slice(0, 200)} | ${(await reps[1].text()).slice(0, 200)}`).toEqual([200, 200])
    const apres = await mouvements(v)
    note(testInfo, `course annulations ${tour}`, JSON.stringify(apres))
    expect(apres.mvts, 'UN retour de 3 panneaux').toEqual([['sortie', 3], ['entree', 3]])
    expect(apres.stock, 'stock revenu à sa valeur d\'avant la vente').toBe(avant.stock + 3)
    expect((await etatFacture(ids[0])).statut).toBe('annulee')
    expect((await etatFacture(ids[1])).statut).toBe('annulee')
  }
  // Non-régression séquentielle (Preuve en direct) : acompte puis solde ⇒ un retour.
  const { v, ids } = await venteAcompteSolde(r, `${m}s`)
  for (const id of ids) await lireJson(await d.post(`${API}/ventes/factures/${id}/annuler/`, { ...T, data: {} }), 'annulation')
  expect((await mouvements(v)).mvts, 'séquentiel : un retour').toEqual([['sortie', 3], ['entree', 3]])
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC9 / ACNC10 — encaissement groupé rejouable ; lot entièrement soldé refusé
// ════════════════════════════════════════════════════════════════════════════════════════════
const etatGroupe = (ids, client) => bd(`sortie({'paiements': [[p.facture_id, str(p.montant)] for p in Paiement.objects.filter(facture_id__in=${JSON.stringify(ids)}).order_by('pk')],
        'avances': Paiement.objects.filter(facture__isnull=True, client_id=${client}).count(),
        'statuts': [Facture.objects.get(pk=i).statut for i in ${JSON.stringify(ids)}]})`)
/** Deux factures émises d'un même client (6 000 et 3 600 TTC), créées par `c`. */
async function deuxFactures(r, c, m) {
  const v1 = await venteAcceptee(r, c, `${m}x`)
  const a = await factureEmise(c, v1)
  const v2 = await venteAcceptee(r, c, `${m}y`, { prixHt: '3000.00', client: v1.client })
  const b = await factureEmise(c, v2)
  expect(b.client, 'même client').toBe(a.client)
  return { a, b, client: a.client, nomClient: `ACNC ${m}x`, total: f2(Number(a.total_ttc) + Number(b.total_ttc)) }
}

etape('PF9.9-reseau', ['ACNC9'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc9', 'Commercial')
  const m = marque()
  const { a, b, client, total } = await deuxFactures(r, c, m)
  const url = `${API}/ventes/factures/encaissement-groupe/`
  const corps = { client, montant: total, mode: 'virement', date: AUJ(), reference: `VIR-G-${m}`, factures: [a.id, b.id], idempotency_key: `acnc9-${m}` }
  const reps = await Promise.all([1, 2].map(() => c.post(url, { ...T, data: corps })))
  const x = await Promise.all(reps.map(async (y) => ({ s: y.status(), j: await y.json() })))
  for (const y of x) expect(y.s === 201 || enCours(y), `groupé parallèle : ${y.s} ${JSON.stringify(y.j).slice(0, 200)}`).toBe(true)
  note(testInfo, 'course même clé', x.map((y) => y.s).join(' + '))
  const premier = x.find((y) => y.s === 201).j
  const tiers = await c.post(url, { ...T, data: corps })
  expect(tiers.status()).toBe(201)
  expect((await tiers.json()).map((p) => p.id).sort(), '3e envoi = la même répartition rejouée').toEqual(premier.map((p) => p.id).sort())
  expect((await c.post(url, { ...T, data: { ...corps, montant: '1.00' } })).status(), 'corps différent sous la même clé').toBe(409)
  const e = await etatGroupe([a.id, b.id], client)
  expect(e.paiements.length, 'deux paiements au total').toBe(2)
  expect(e.avances, 'aucune avance').toBe(0)
  expect(e.statuts).toEqual(['payee', 'payee'])
})

etape('PF9.9-ecran', ['ACNC9'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc9e', 'Commercial')
  const m = marque()
  const lot1 = await deuxFactures(r, c, `${m}1`)
  const lot2 = await deuxFactures(r, c, `${m}2`)
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const rx = /\/encaissement-groupe\/$/
  const ouvrir = async (lot) => {
    await p.goto('/ventes/factures')
    await p.getByPlaceholder('Référence, client').fill(lot.nomClient, { timeout: 60_000 })
    for (const f of [lot.a, lot.b]) {
      await expect(p.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 60_000 })
      await p.getByRole('checkbox', { name: `Sélectionner la facture ${f.reference}` }).check()
    }
    await p.getByRole('region', { name: 'Actions factures en masse' }).getByRole('button', { name: 'Encaissement groupé' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: 'Encaissement groupé' })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await expect(dlg.locator('#eg-montant'), 'montant prérempli = somme des restes dus').toHaveValue(new RegExp(`^${Number(lot.total)}`))
    await dlg.locator('#eg-reference').fill(`VIR-G-${marque()}`)
    return dlg
  }
  let dlg = await ouvrir(lot1)
  let btn = dlg.getByRole('button', { name: 'Encaisser', exact: true })
  const t = await tenir(p, rx)
  await btn.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btn, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  await expect(btn).toHaveAttribute('aria-busy', 'true')
  t.liberer()
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await t.fin()
  expect(new Set(t.envois.map((x) => x.idempotency_key)).size, `${t.envois.length} envoi(s), une seule clé`).toBe(1)
  let e = await etatGroupe([lot1.a.id, lot1.b.id], lot1.client)
  expect([e.paiements.length, e.avances], 'double clic ⇒ 2 paiements, 0 avance').toEqual([2, 0])
  // Réseau coupé après l'envoi : la liste est relue ; nouveau clic ⇒ aucune avance créée.
  dlg = await ouvrir(lot2)
  btn = dlg.getByRole('button', { name: 'Encaisser', exact: true })
  const envois = await couper(p, rx, suivi)
  await btn.click()
  await expect.poll(async () => (await etatGroupe([lot2.a.id, lot2.b.id], lot2.client)).paiements.length, { timeout: 60_000, message: 'le serveur a reçu le 1er envoi' }).toBe(2)
  await expect(dlg, 'dialogue gardé après l\'échec sans réponse').toBeVisible()
  suivi.attendre(rx, 409) // un renvoi dont le lot relu a changé est refusé (jamais rejoué en avance)
  const [rep] = await Promise.all([reponse(p, rx), btn.click()])
  note(testInfo, 'renvoi après coupure', `${rep.status()} ${(await rep.text()).slice(0, 200)}`)
  expect([201, 409], 'renvoi : rejoué ou refusé').toContain(rep.status())
  await p.unroute(rx)
  expect(envois[0].idempotency_key, 'clé gardée entre les deux clics').toBe(envois[1].idempotency_key)
  e = await etatGroupe([lot2.a.id, lot2.b.id], lot2.client)
  expect([e.paiements.length, e.avances], 'coupure + renvoi ⇒ 2 paiements, AUCUNE avance').toEqual([2, 0])
  expect(e.statuts).toEqual(['payee', 'payee'])
  await p.reload()
  await ligneFacture(p, lot2.a.reference, lot2.a.id)
}, { ecart: ECART_TOURNEE })

etape('PF9.10', ['ACNC10'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc10', 'Commercial')
  const m = marque()
  const url = `${API}/ventes/factures/encaissement-groupe/`
  // (a) Lot dont toutes les factures sont déjà soldées (sans clé) ⇒ 409 « déjà soldées », rien écrit.
  const l1 = await deuxFactures(r, c, `${m}1`)
  for (const f of [l1.a, l1.b]) await payer(c, f.id, f.total_ttc)
  const avant = await etatGroupe([l1.a.id, l1.b.id], l1.client)
  const ref = await c.post(url, { ...T, data: { client: l1.client, montant: '10000.00', mode: 'virement', factures: [l1.a.id, l1.b.id] } })
  expect(ref.status(), 'lot soldé ⇒ 409').toBe(409)
  expect(String((await ref.json()).detail)).toMatch(/déjà soldées/)
  expect(await etatGroupe([l1.a.id, l1.b.id], l1.client), 'aucun paiement, aucune avance').toEqual(avant)
  // (b) Le même lot dû envoyé deux fois EN PARALLÈLE (sans clé, deux onglets) ⇒ 201 + 409, aucune avance.
  const l2 = await deuxFactures(r, c, `${m}2`)
  const corps = { client: l2.client, montant: l2.total, mode: 'virement', factures: [l2.a.id, l2.b.id] }
  const reps = await Promise.all([1, 2].map(() => c.post(url, { ...T, data: corps })))
  expect(statuts(reps), `parallèle sans clé : ${(await reps[1].text()).slice(0, 200)}`).toEqual([201, 409])
  let e = await etatGroupe([l2.a.id, l2.b.id], l2.client)
  expect([e.paiements.length, e.avances], '2 paiements, 0 avance').toEqual([2, 0])
  // (c) Écran, deux onglets : le même encaissement groupé envoyé de chaque onglet ⇒ 409 affiché sur le 2e.
  const l3 = await deuxFactures(r, c, `${m}3`)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const ouvrir = async (p) => {
    await p.goto('/ventes/factures')
    await p.getByPlaceholder('Référence, client').fill(l3.nomClient, { timeout: 60_000 })
    for (const f of [l3.a, l3.b]) {
      await expect(p.locator(`#facture-row-${f.id}`)).toBeVisible({ timeout: 60_000 })
      await p.getByRole('checkbox', { name: `Sélectionner la facture ${f.reference}` }).check()
    }
    await p.getByRole('region', { name: 'Actions factures en masse' }).getByRole('button', { name: 'Encaissement groupé' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: 'Encaissement groupé' })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    return dlg
  }
  const dB = await ouvrir(pB)
  const dA = await ouvrir(pA)
  const rx = /\/encaissement-groupe\/$/
  const [a] = await Promise.all([reponse(pA, rx), dA.getByRole('button', { name: 'Encaisser', exact: true }).click()])
  expect(a.status(), 'onglet A : encaissé').toBe(201)
  suivi.attendre(rx, 409)
  const [b] = await Promise.all([reponse(pB, rx), dB.getByRole('button', { name: 'Encaisser', exact: true }).click()])
  expect(b.status(), 'onglet B : lot désormais soldé ⇒ 409').toBe(409)
  await expect(pB.getByText(/déjà soldées/).first(), 'message serveur affiché tel quel').toBeVisible({ timeout: 30_000 })
  e = await etatGroupe([l3.a.id, l3.b.id], l3.client)
  expect([e.paiements.length, e.avances], 'onglets : 2 paiements, aucune avance').toEqual([2, 0])
  await pB.reload()
  await ligneFacture(pB, l3.a.reference, l3.a.id)
}, { ecart: ECART_TOURNEE })

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC11 — « Relancer » rejouable le même jour au même niveau (Commercial)
// ════════════════════════════════════════════════════════════════════════════════════════════
const relancesBd = (id) => bd(`sortie([[x.niveau, str(x.date)[:10]] for x in RelanceLog.objects.filter(facture_id=${id}).order_by('pk')])`)

etape('PF9.11-reseau', ['ACNC11'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc11', 'Commercial')
  const m = marque()
  const f = await factureEmise(c, await venteAcceptee(r, c, `${m}a`, { email: false }))
  const g = await factureEmise(c, await venteAcceptee(r, c, `${m}b`, { email: false }))
  await lireJson(await c.get(`${API}/ventes/factures/${f.id}/relance-apercu/`, T), 'aperçu (niveaux par défaut)')
  const url = (x) => `${API}/ventes/factures/${x.id}/relancer/`
  const reps = await Promise.all([1, 2].map(() => c.post(url(f), { ...T, data: { niveau: 1, note: 'appel' } })))
  expect(statuts(reps), `relancer niveau 1 ×2 : ${(await reps[1].text()).slice(0, 200)}`).toEqual([200, 200])
  expect((await c.post(url(f), { ...T, data: { niveau: 1, note: 'appel' } })).status(), '3e envoi : relance du jour rendue').toBe(200)
  expect((await relancesBd(f.id)).map((x) => x[0]), 'UNE relance niveau 1').toEqual([1])
  const reps2 = await Promise.all([1, 2].map(() => c.post(url(g), { ...T, data: {} })))
  expect(statuts(reps2), '{} ×2').toEqual([200, 200])
  expect((await relancesBd(g.id)).map((x) => x[0]), 'UNE relance niveau 1, aucun niveau 2').toEqual([1])
  // Un niveau différent reste consigné.
  expect((await c.post(url(f), { ...T, data: { niveau: 2, note: 'relance' } })).status()).toBe(200)
  expect((await relancesBd(f.id)).map((x) => x[0]), 'niveau 2 consigné à côté').toEqual([1, 2])
})

etape('PF9.11-ecran', ['ACNC11'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc11e', 'Commercial')
  const m = marque()
  const fa = await factureEmise(c, await venteAcceptee(r, c, `${m}a`, { email: false }))
  const fb = await factureEmise(c, await venteAcceptee(r, c, `${m}b`, { email: false }))
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const rx = /\/relancer\/$/
  const ouvrir = async (f) => {
    await p.goto('/ventes/relances')
    const ligne = p.getByRole('row').filter({ hasText: f.reference })
    await expect(ligne).toBeVisible({ timeout: 90_000 })
    await ligne.getByRole('button', { name: 'Relancer', exact: true }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Consigner une relance — ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.locator('#relance-note').fill('appel ACNC11')
    return dlg
  }
  const historique = async (f) => {
    await p.goto('/ventes/relances')
    const ligne = p.getByRole('row').filter({ hasText: f.reference })
    await expect(ligne).toBeVisible({ timeout: 90_000 })
    await ligne.getByRole('button', { name: `Plus d'actions — ${f.reference}` }).click()
    await p.getByRole('menuitem', { name: 'Historique' }).click()
    const h = p.getByRole('dialog').filter({ hasText: `Historique des relances — ${f.reference}` })
    await expect(h).toBeVisible({ timeout: 30_000 })
    return h.locator('li')
  }
  let dlg = await ouvrir(fa)
  let btn = dlg.getByRole('button', { name: 'Consigner' })
  const t = await tenir(p, rx)
  await btn.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btn, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  await expect(btn).toHaveAttribute('aria-busy', 'true')
  t.liberer()
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await t.fin()
  expect((await relancesBd(fa.id)).length, `double clic (${t.envois.length} envoi(s)) ⇒ UNE relance`).toBe(1)
  await expect(await historique(fa), 'historique : une ligne').toHaveCount(1, { timeout: 30_000 })
  dlg = await ouvrir(fb)
  btn = dlg.getByRole('button', { name: 'Consigner' })
  const envois = await couper(p, rx, suivi)
  await btn.click()
  await expect(dlg.getByRole('alert'), 'échec sans réponse affiché').toBeVisible({ timeout: 60_000 })
  const [rep] = await Promise.all([reponse(p, rx), btn.click()])
  expect(rep.status(), 'renvoi : relance du jour rendue').toBe(200)
  await expect(dlg).toBeHidden({ timeout: 60_000 })
  await p.unroute(rx)
  expect(envois.length).toBe(2)
  expect((await relancesBd(fb.id)).length, 'coupure + renvoi ⇒ UNE relance').toBe(1)
  await p.reload()
  await expect(await historique(fb), 'historique rechargé : une seule ligne').toHaveCount(1, { timeout: 30_000 })
}, { ecart: ECART_TOURNEE })

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC12 — avance, « générer la facture », proforma rejouables par clé (API seulement)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.12', ['ACNC12'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc12', 'Commercial')
  const m = marque()
  const v = await venteAcceptee(r, c, m)
  const avant = await bd(`sortie({'factures': [[f.pk, f.statut] for f in Facture.objects.filter(devis_id=${v.devisId}).order_by('pk')]})`)
  const parallele = async (chemin, opts) => {
    const reps = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/${chemin}`, { ...T, ...opts })))
    const x = await Promise.all(reps.map(async (y) => ({ s: y.status(), j: (y.headers()['content-type'] || '').includes('json') ? await y.json() : null })))
    note(testInfo, `course ${chemin}`, x.map((y) => y.s).join(' + '))
    return x
  }
  // generer-facture (en-tête Idempotency-Key)
  const hG = { headers: { 'Idempotency-Key': `acnc12g-${m}` }, data: {} }
  const g = await parallele(`devis/${v.devisId}/generer-facture/`, hG)
  for (const y of g) expect(y.s === 201 || enCours(y), `generer-facture : ${y.s} ${JSON.stringify(y.j).slice(0, 200)}`).toBe(true)
  const fac = g.find((y) => y.s === 201).j
  const g3 = await c.post(`${API}/ventes/devis/${v.devisId}/generer-facture/`, { ...T, ...hG })
  expect([g3.status(), (await g3.json()).id], '3e envoi : même facture').toEqual([201, fac.id])
  const apres = await bd(`sortie({'factures': [[f.pk, f.statut] for f in Facture.objects.filter(devis_id=${v.devisId}).order_by('pk')], 'emises': Facture.objects.filter(devis_id=${v.devisId}).exclude(statut__in=['brouillon', 'annulee']).count()})`)
  note(testInfo, 'factures de la vente', `avant ${JSON.stringify(avant.factures)} après ${JSON.stringify(apres.factures)}`)
  expect(apres.emises, 'UNE facture de tranche émise').toBe(1)
  expect(apres.factures.length, 'aucune facture de plus que la tranche').toBe(Math.max(avant.factures.length, 1))
  // proforma-pdf (en-tête Idempotency-Key) : un seul numéro PF-.
  const hP = { headers: { 'Idempotency-Key': `acnc12p-${m}` }, data: {} }
  const pf = await parallele(`devis/${v.devisId}/proforma-pdf/`, hP)
  for (const y of pf) expect(y.s === 200 || enCours(y), `proforma : ${y.s}`).toBe(true)
  expect((await c.post(`${API}/ventes/devis/${v.devisId}/proforma-pdf/`, { ...T, ...hP })).status()).toBe(200)
  expect(await bd(`sortie(ProformaDocument.objects.filter(devis_id=${v.devisId}).count())`), 'UN numéro PF-').toBe(1)
  // enregistrer-avance (clé du corps) : une seule avance de 2 000.
  const cle = `acnc12a-${m}`
  const av = await parallele('paiements/enregistrer-avance/', { data: { client: v.client, montant: '2000.00', mode: 'virement', idempotency_key: cle } })
  for (const y of av) expect(y.s === 201 || y.s === 409, `avance parallèle : ${y.s} ${JSON.stringify(y.j).slice(0, 300)}`).toBe(true)
  const avCrees = av.filter((y) => y.s === 201)
  expect(avCrees.length, 'au moins un 201').toBeGreaterThan(0)
  expect(new Set(avCrees.map((y) => y.j.id)).size, 'les 201 rendent la MÊME avance').toBe(1)
  for (const y of av.filter((z) => z.s === 409)) note(testInfo, 'avance : 409 du 2e envoi parallèle', JSON.stringify(y.j).slice(0, 300))
  const av3 = await c.post(`${API}/ventes/paiements/enregistrer-avance/`, { ...T, data: { client: v.client, montant: '2000.00', mode: 'virement', idempotency_key: cle } })
  expect([av3.status(), (await av3.json()).id], '3e envoi séquentiel : la même avance').toEqual([201, avCrees[0].j.id])
  expect(await bd(`sortie([str(p.montant) for p in Paiement.objects.filter(idempotency_key=${JSON.stringify(cle)})])`), 'UNE avance de 2 000').toEqual(['2000.00'])
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC13 — renouvellement sous verrou ; variantes rejouables par clé (Commercial)
// ════════════════════════════════════════════════════════════════════════════════════════════
const devisMax = () => bd(`sortie(Devis.objects.order_by('-pk').values_list('pk', flat=True).first() or 0)`)
const devisDepuis = (pk) => bd(`sortie([[d.pk, d.statut, d.version_parent_id, d.devis_origine_id] for d in Devis.objects.filter(pk__gt=${pk}).order_by('pk')])`)
async function devisBrouillon(r, c, m) {
  const l = await lireJson(await c.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACNC13 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique() } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Kit ACNC13 ${m}`, prix_vente: '5000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await c.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  return lireJson(await c.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
}

etape('PF9.13-reseau', ['ACNC13'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await acteur(testInfo, 'acnc13', 'Commercial')
  const m = marque()
  const src = await devisBrouillon(r, c, m)
  await lireJson(await c.post(`${API}/ventes/devis/${src.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await bd(`Devis.objects.filter(pk=${src.id}).update(statut='expire')
sortie(Devis.objects.get(pk=${src.id}).statut)`) // Given : devis envoyé EXPIRÉ (passage du job nocturne)
  const avant = await devisMax()
  const reps = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/devis/${src.id}/renouveler/`, { ...T, data: {} })))
  expect(statuts(reps), `renouveler ×2 : ${(await reps[0].text()).slice(0, 200)} | ${(await reps[1].text()).slice(0, 200)}`).toEqual([200, 201])
  const ids = await Promise.all(reps.map(async (y) => (await y.json()).id))
  expect(ids[0], 'le 2e rend le MÊME brouillon').toBe(ids[1])
  const neufs = await devisDepuis(avant)
  expect(neufs.length, 'UN renouvellement').toBe(1)
  expect(neufs[0][3], 'rattaché à sa source').toBe(src.id)
  // Variantes du brouillon renouvelé : deux envois parallèles même clé ⇒ un seul jeu.
  const B = ids[0]
  const avantV = await devisMax()
  const corps = { idempotency_key: `acnc13-${m}` } // taux société par défaut (le taux saisi est réservé au palier responsable)
  const vr = await Promise.all([1, 2].map(() => c.post(`${API}/ventes/devis/${B}/dupliquer-variante/`, { ...T, data: corps })))
  const x = await Promise.all(vr.map(async (y) => ({ s: y.status(), j: await y.json() })))
  for (const y of x) expect(y.s === 201 || enCours(y), `variantes : ${y.s} ${JSON.stringify(y.j).slice(0, 200)}`).toBe(true)
  note(testInfo, 'course variantes', x.map((y) => y.s).join(' + '))
  const jeu = x.find((y) => y.s === 201).j.map((d) => d.id).sort()
  const v3 = await c.post(`${API}/ventes/devis/${B}/dupliquer-variante/`, { ...T, data: corps })
  expect(v3.status()).toBe(201)
  expect((await v3.json()).map((d) => d.id).sort(), '3e envoi : le jeu rejoué').toEqual(jeu)
  const neufsV = await devisDepuis(avantV)
  expect(neufsV.map((d) => d[0]).sort(), 'UN seul jeu de variantes en base').toEqual(jeu)
})

etape('PF9.13-ecran', ['ACNC13'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom, ctx: c } = await acteur(testInfo, 'acnc13e', 'Commercial')
  const m = marque()
  const da = await devisBrouillon(r, c, `${m}a`)
  const db = await devisBrouillon(r, c, `${m}b`)
  const p = await onglet(page, suivi, await navigateur(page, testInfo, nom))
  const rx = /\/dupliquer-variante\/$/
  const ouvrir = async (d) => {
    await p.goto('/ventes/devis')
    await p.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
    const ligne = p.locator(`#devis-row-${d.id}`)
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByRole('button', { name: `Plus d'actions — ${d.reference}` }).click()
    await p.getByRole('menuitem', { name: 'Variante', exact: true }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Créer des variantes — ${d.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    const btn = dlg.getByRole('button', { name: 'Créer les variantes' })
    await expect(btn).toBeEnabled({ timeout: 30_000 })
    return { dlg, btn }
  }
  let avant = await devisMax()
  let { dlg, btn } = await ouvrir(da)
  const t = await tenir(p, rx)
  await btn.dblclick()
  await expect.poll(() => t.envois.length, { timeout: 30_000 }).toBeGreaterThan(0)
  await expect(btn, 'bouton désactivé pendant l\'envoi').toBeDisabled()
  await expect(btn).toHaveAttribute('aria-busy', 'true')
  t.liberer()
  await expect(p.getByText(`Variantes créées pour ${da.reference}.`).first(), 'succès affiché').toBeVisible({ timeout: 60_000 })
  await t.fin()
  expect(new Set(t.envois.map((x) => x.idempotency_key)).size, `${t.envois.length} envoi(s), une seule clé`).toBe(1)
  const jeu1 = await devisDepuis(avant)
  expect(jeu1.length, 'double clic ⇒ UN jeu de variantes').toBeGreaterThan(0)
  expect(new Set(jeu1.map((d) => d[2])).size, 'un seul groupe').toBe(1)
  avant = await devisMax()
  ;({ dlg, btn } = await ouvrir(db))
  const envois = await couper(p, rx, suivi)
  await btn.click()
  await expect.poll(async () => (await devisDepuis(avant)).length, { timeout: 60_000, message: 'le serveur a reçu le 1er envoi' }).toBe(jeu1.length)
  await expect(dlg, 'dialogue gardé après l\'échec sans réponse').toBeVisible()
  const [rep] = await Promise.all([reponse(p, rx), btn.click()])
  expect(rep.status(), 'renvoi : jeu rejoué').toBe(201)
  await expect(p.getByText(`Variantes créées pour ${db.reference}.`).first()).toBeVisible({ timeout: 60_000 })
  await p.unroute(rx)
  expect(envois[0].idempotency_key, 'clé gardée entre les deux clics').toBe(envois[1].idempotency_key)
  expect((await devisDepuis(avant)).length, 'coupure + renvoi ⇒ UN jeu').toBe(jeu1.length)
  await p.reload()
  await expect(p.getByRole('table', { name: `Comparaison des variantes de ${db.reference}` }), 'rechargé (?variantes=) : la comparaison des variantes est servie').toBeVisible({ timeout: 60_000 })
}, { ecart: ECART_TOURNEE })

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC15 — ligne de facture jamais re-postée après une réponse perdue ; onglet périmé ⇒ 409
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.15', ['ACNC15'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { nom } = await acteur(testInfo, 'acnc15', 'Directeur')
  const m = marque()
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00' })
  const f = await lireJson(await r.post(`${API}/ventes/factures/`, { ...T, data: { client: v.client, date_emission: AUJ() } }), 'brouillon')
  for (const des of ['Ligne A', 'Ligne B']) {
    await lireJson(await r.post(`${API}/ventes/factures-lignes/`, { ...T, data: { facture: f.id, produit: v.produitId, designation: des, quantite: '1', prix_unitaire: '1000.00', remise: '0', taux_tva: '20.00' } }), des)
  }
  const fr = await lireF(r, f.id)
  expect([fr.statut, fr.lignes.length], 'Given : brouillon à 2 lignes').toEqual(['brouillon', 2])
  const etat = () => bd(`f = Facture.objects.get(pk=${f.id})
sortie({'lignes': sorted(LigneFacture.objects.filter(facture=f).values_list('designation', flat=True)), 'note': f.note or '', 'version': f.lock_version})`)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const editer = async (p) => {
    const ligne = await ligneFacture(p, fr.reference, f.id)
    await ligne.getByRole('button', { name: 'Éditer' }).click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Éditer — ${fr.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    return dlg
  }
  const dlgB = await editer(pB) // onglet B ouvert AVANT la modification de l'onglet A
  const dlgA = await editer(pA)
  await dlgA.getByRole('button', { name: 'Ajouter une ligne' }).click()
  const neuve = dlgA.locator('tr[data-line-key]').last()
  await neuve.getByRole('button', { name: /Produit/ }).click()
  await pA.getByPlaceholder('Chercher un produit… (Entrée = premier résultat)').fill(v.produitNom)
  await expect(pA.getByRole('option').filter({ hasText: v.produitNom }).first()).toBeVisible({ timeout: 30_000 })
  await pA.getByPlaceholder('Chercher un produit… (Entrée = premier résultat)').press('Enter')
  await neuve.getByPlaceholder('Désignation').fill('Ligne C')
  await neuve.locator('[data-role="line-qty"]').fill('1')
  // La création de la 3e ligne atteint le serveur, sa réponse est perdue (délai dépassé simulé).
  const rxL = /\/factures-lignes\/$/
  const envois = await couper(pA, rxL, suivi)
  await dlgA.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgA, 'ligne perdue relue et rapprochée : enregistrement terminé').toBeHidden({ timeout: 60_000 })
  await pA.unroute(rxL)
  expect(envois.length, 'la ligne neuve n\'a été postée qu\'UNE fois').toBe(1)
  let e = await etat()
  expect(e.lignes, '3 lignes en base (pas 4)').toEqual(['Ligne A', 'Ligne B', 'Ligne C'])
  // « Enregistrer » de nouveau (formulaire rouvert) : toujours 3 lignes.
  await pA.reload()
  const dlgA2 = await editer(pA)
  await dlgA2.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgA2).toBeHidden({ timeout: 60_000 })
  e = await etat()
  expect(e.lignes, 'ré-enregistré : toujours 3 lignes').toEqual(['Ligne A', 'Ligne B', 'Ligne C'])
  // Onglet B (périmé) : il modifie la note et enregistre ⇒ bannière, puis forcé ⇒ 409 conflit_version, rien écrit.
  await dlgB.locator('#fc-note').fill(`écrasement onglet périmé ${m}`)
  await dlgB.getByRole('button', { name: 'Mettre à jour' }).click()
  await expect(dlgB.getByText(/pendant votre édition/), 'bannière d\'édition périmée').toBeVisible({ timeout: 30_000 })
  const rxF = new RegExp(`/ventes/factures/${f.id}/$`)
  suivi.attendre(rxF, 409)
  const [rep] = await Promise.all([pB.waitForResponse((x) => ['PUT', 'PATCH'].includes(x.request().method()) && rxF.test(new URL(x.url()).pathname), T),
    dlgB.getByRole('button', { name: 'Enregistrer quand même' }).click()])
  const corps = await rep.json()
  expect([rep.status(), corps.code], `onglet périmé : ${JSON.stringify(corps).slice(0, 200)}`).toEqual([409, 'conflit_version'])
  const apres = await etat()
  expect(apres, 'aucune écriture de l\'onglet périmé (lignes, note, version)').toEqual(e)
  await expect.poll(async () => (await dlgB.getByRole('alert').allInnerTexts()).join(' | '), { timeout: 30_000, message: 'message « modifié par quelqu\'un d\'autre… Rechargez-le » affiché' }).toMatch(/modifié par quelqu.un d.autre/)
})

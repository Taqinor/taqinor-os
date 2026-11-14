// Montage partagé des specs ACNC (acnc.spec.js, acnc2.spec.js) : comptes de rôles du registre, contextes API et
// navigateur, requêtes TENUES (double clic) ou COUPÉES après livraison (réponse perdue), ventes et factures d'essai.
import { test, expect, request as pwRequest } from '@playwright/test'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

export const API = '/api/django'
export const T = { timeout: 120_000 }
export const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
export const SOC = `U.objects.get(username='demo_admin').company_id`
export const AUJ = () => new Date().toISOString().slice(0, 10)
export const f2 = (v) => Number(v).toFixed(2)
export const cents = (v) => Math.round(Number(v) * 100)
export const plat = (s) => String(s).replace(/\s+/g, '').replace(/,(\d{2})(?!\d)/g, '.$1')
export const statuts = (reps) => reps.map((x) => x.status()).sort((a, b) => a - b)
export const ouverts = []
export const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[ACNC] ${type} : ${description}`)
}
// ÉCART ACCEPTÉ (écrans joués sous le rôle Commercial, avant midi) : défaut ANTÉRIEUR et hors des Files des tâches ACNC.
export const ECART_TOURNEE = {
  base: 'FAIL',
  raison: "GET installations/interventions/ma-tournee/ → 403 pour le rôle Commercial : le pré-chargement matinal de la tournée "
    + '(frontend/src/features/offlinesync/PrechargementTournee.jsx, NTMOB28 du 13/08/2026, monté par Layout sur TOUT écran '
    + "authentifié avant 12 h) interroge une route que le rôle Commercial ne lit pas — 403 + console.error à chaque écran ; présent "
    + "avant les commits ACNC (13/11/2026), hors de leurs Files (facturation / ventes) ; à ouvrir chez le propriétaire installations/offlinesync",
}
export const IMPORTS = `from apps.ventes.models import Facture, Paiement, Avoir, RelanceLog, Devis, BonCommande, LigneFacture
from apps.ventes.models_facturation import NoteDebit, FactureActivity, ProformaDocument, RemiseEncaissement
from apps.stock.models import MouvementStock, Produit
`
export const bd = (code) => py(`${IMPORTS}${code}`)

// ── comptes, contextes, écrans ───────────────────────────────────────────────────────────────

/** Compte d'essai du rôle SYSTÈME `nomRole` de la société démo ; {id, encaisser, admin, systeme}. */
export async function compteDuRole(nom, nomRole) {
  return py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nomRole)})
u = compte(${JSON.stringify(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'encaisser': 'encaisser' in (r.permissions or []), 'admin': 'roles_gerer' in (r.permissions or []), 'systeme': r.est_systeme})`)
}
/** Compte du rôle + contexte API connecté par la vraie route /token/. */
export async function acteur(testInfo, prefixe, nomRole) {
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
export async function navigateur(page, testInfo, nom) {
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
export async function onglet(page, suivi, ctx) {
  if (!page.isClosed()) await page.close()
  return suivi.surveiller(await ctx.newPage())
}

/** Tient les POST qui matchent `rx` jusqu'à `liberer()` (le bouton est affirmé désactivé entre-temps). */
export async function tenir(p, rx) {
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
export async function couper(p, rx, suivi) {
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
export const reponse = (p, rx, methode = 'POST') => p.waitForResponse((x) => x.request().method() === methode && rx.test(new URL(x.url()).pathname), T)

// ── données ──────────────────────────────────────────────────────────────────────────────────

/** Vente ACCEPTÉE : lead + devis portés par `cree`, produit + acceptation par demo_admin (`r`). */
export async function venteAcceptee(r, cree, m, { prixHt = '5000.00', qte = '1', stock = null, echeancier = null, email = true, client = null } = {}) {
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
export const lireF = async (ctx, id) => lireJson(await ctx.get(`${API}/ventes/factures/${id}/`, T), `facture ${id}`)
/** Facture COMPLÈTE émise du devis par `c` (créée par lui : portée du rôle). */
export async function factureEmise(c, v) {
  const rep = await lireJson(await c.post(`${API}/ventes/devis/${v.devisId}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facturer-complet')
  const f = await lireF(c, rep.facture_id)
  expect(f.statut, `facture ${f.reference} émise`).toBe('emise')
  return f
}
export const payer = async (c, id, montant, mode = 'virement') => lireJson(await c.post(`${API}/ventes/factures/${id}/enregistrer-paiement/`, {
  ...T, data: { montant: f2(montant), date_paiement: AUJ(), mode, reference: `PAY-${marque()}` },
}), 'paiement')
/** Le brouillon d'acompte provisoire posé à l'acceptation (VNT62). */
export async function brouillonAcompte(r, v) {
  const d = await lireJson(await r.get(`${API}/ventes/devis/${v.devisId}/`, T), 'devis relu')
  const b = (d.factures_liees || []).find((x) => x.statut === 'brouillon')
  expect(b, 'un brouillon d\'acompte posé à l\'acceptation').toBeTruthy()
  return lireF(r, b.id)
}
export const etatFacture = (id) => bd(`f = Facture.objects.filter(pk=${id}).first()
sortie(None if f is None else {'statut': f.statut, 'reference': f.reference, 'ttc': str(f.total_ttc), 'du': str(f.montant_du)})`)
export const LEGALE = /^FAC-/

/** Ligne de la facture dans /ventes/factures. */
export async function ligneFacture(p, ref, id) {
  await p.goto('/ventes/factures')
  await p.getByPlaceholder('Référence, client').fill(ref, { timeout: 60_000 })
  const ligne = p.locator(`#facture-row-${id}`).first()
  await expect(ligne, `ligne ${ref}`).toBeVisible({ timeout: 60_000 })
  return ligne
}

export const enCours = (x) => x.s === 409 && x.j.code === 'idempotency_en_cours'

/** Crochets communs d'un fichier de spec ACNC (shell Django fermé, session admin, contextes refermés). */
export function monter() {
  fermerDjangoApresTout()
  test.describe.configure({ timeout: 600_000 })
  test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
  test.afterEach(async () => { for (const c of ouverts.splice(0)) await (c.dispose ? c.dispose() : c.close()).catch(() => undefined) })
}

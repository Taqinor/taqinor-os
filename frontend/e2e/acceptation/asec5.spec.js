// Rejeu en direct d'ASEC96 (D-ASEC-VER6-1, constat C-ASEC-VER7-096 de la contre-visite ASEC du 11/11) :
// « Facturer la vente » avec `remplacer_brouillons` sur un brouillon à référence LÉGALE (acompte émis puis remis
// en brouillon : il garde son numéro FAC-…) émet un avoir de contre-passation, donc exige `encaisser`.
// Chaque étape joue l'ÉCRAN (liste des devis → « Facturer… » → dialogue « Facturer — <réf> » → onglet Totalité,
// « Émettre tout de suite » coupé → 409 `brouillons_a_remplacer` → « Remplacer les brouillons et facturer ») sous
// un vrai compte d'un rôle LIVRÉ du registre (`permissions_registre.py`, relu par son nom dans la société démo),
// relit la base (brouillon, factures, avoirs) puis recharge l'écran et rejoue le geste. Données propres : vente
// créée par l'API (lead, produit 5 000 HT, TVA 20 %, devis envoyé, accepté), acompte 1 200 TTC émis puis remis en
// brouillon par demo_admin (vraies routes `facturer/` et `remettre-brouillon/`) ; nettoyage best-effort.
// Montant : le Given de la tâche (vente 1 000 HT, acompte 1 200 TTC) n'est pas constructible par l'API réelle
// (un acompte doit rester < prix convenu, `_facturer_acompte`) : vente portée à 5 000 HT, acompte 1 200 TTC.
import { test, expect, request as pwRequest } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, connexionApi, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'

const etape = groupe('ASEC', ['ASEC96'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const SOC = `U.objects.get(username='demo_admin').company_id`
const REFUS = "droit d'encaissement"
const ouverts = []
test.afterEach(async () => { for (const c of ouverts.splice(0)) await c.close().catch(() => undefined) })
const note = (testInfo, type, description) => {
  testInfo.annotations.push({ type, description })
  console.log(`[ASEC96] ${type} : ${description}`)
}

/** Rejoue la sonde HÔTE du constat (`docs/audits/sondes/ASEC/<c>.py`, sans Django ni base) ; {ok, res|err}. */
function sondeHote(constat) {
  const chemin = join(RACINE, 'docs', 'audits', 'sondes', 'ASEC', `${constat}.py`)
  const code = 'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))'
  const r = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c', code, chemin], { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000 })
  const ligne = (r.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  if (!ligne) return { ok: false, err: `${(r.stderr || r.stdout || '').trim().split('\n').pop()}`.slice(0, 300) }
  return { ok: true, res: JSON.parse(ligne.slice(3)) }
}

/** Compte d'essai du rôle LIVRÉ `nomRole` de la société démo (vérifie s'il porte `encaisser`) ; {id, porte}. */
async function compteDuRole(nom, nomRole) {
  return py(`from apps.roles.models import Role
r = Role.objects.get(company_id=${SOC}, nom=${JSON.stringify(nomRole)})
u = compte(${JSON.stringify(nom)}, role=r.pk, societe=${SOC})
sortie({'id': u.id, 'porte': 'encaisser' in (r.permissions or []), 'systeme': r.est_systeme})`)
}

/** Contexte API connecté par la vraie route /token/. */
async function api(testInfo, nom) {
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return ctx
}

/** Écran sous le compte `nom` : contexte navigateur neuf (accueil vu, visites guidées vues, SW bloqué), observé.
 *  La page demo_admin de l'étape est refermée : la capture montre l'écran du rôle joué. */
async function ecran(page, suivi, testInfo, nom) {
  if (!page.isClosed()) await page.close()
  const ctx = await page.context().browser().newContext({
    baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
  })
  ouverts.push(ctx) // refermé après la capture de l'étape (afterEach)
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
  return suivi.surveiller(await ctx.newPage())
}

/** Vente acceptée : lead + devis créés par `cree` (porté par lui), produit et acceptation par demo_admin (`r`). */
async function venteAcceptee(r, cree, m) {
  const l = await lireJson(await cree.post(`${API}/crm/leads/`, { ...T, data: { nom: `ASEC96 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `asec96-${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation ASEC96 ${m}`, prix_vente: '5000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await cree.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: l.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await cree.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ASEC96' } }), 'accepter')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  return { devisId: d.id, reference: relu.reference, leadId: l.id, produitId: p.id }
}

/** Le Given : acompte 1 200 TTC ÉMIS (numéro légal) puis REMIS en brouillon (garde son numéro), sans paiement. */
async function brouillonRemis(r, v) {
  const rep = await lireJson(await r.post(`${API}/ventes/devis/${v.devisId}/facturer/`, { ...T, data: { nature: 'acompte', montant_ttc: '1200.00', emettre: true } }), 'acompte émis')
  const id = rep.facture.id
  await lireJson(await r.post(`${API}/ventes/factures/${id}/remettre-brouillon/`, { ...T, data: {} }), 'remis en brouillon')
  const f = await lireJson(await r.get(`${API}/ventes/factures/${id}/`, T), 'brouillon remis relu')
  expect([f.statut, f.reference.startsWith('BROUILLON-'), Number(f.total_ttc), Number(f.montant_paye)], 'Given : brouillon remis à référence légale, 1 200 TTC, sans paiement').toEqual(['brouillon', false, 1200, 0])
  return f
}

/** État en BASE de la vente : le brouillon, les factures de la vente, les avoirs (société et sur le brouillon). */
const etatBase = (v, brouillonId) => py(`from apps.facturation.models import Facture, Avoir
b = Facture.objects.get(pk=${brouillonId})
sortie({'brouillon': [b.statut, b.reference, str(b.total_ttc)],
        'factures': sorted(Facture.objects.filter(devis_id=${v.devisId}).values_list('pk', flat=True)),
        'avoirs_societe': Avoir.objects.filter(company_id=${SOC}).count(),
        'avoirs_brouillon': [[a.reference, a.type, a.statut, float(a.total_ttc)] for a in Avoir.objects.filter(facture_id=${brouillonId}).order_by('pk')]})`)

/** Liste des devis → ligne de la vente → « Facturer… » → dialogue « Facturer — <réf> » ouvert. */
async function ouvrirDialogue(p, v) {
  await p.goto('/ventes/devis')
  await p.getByPlaceholder('Rechercher (référence ou client)…').fill(v.reference, { timeout: 60_000 })
  const ligne = p.locator(`#devis-row-${v.devisId}`)
  await expect(ligne, 'ligne du devis dans la liste').toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: 'Facturer…' }).click()
  const dlg = p.getByRole('dialog').filter({ has: p.getByTestId('facturer-vente-form') })
  await expect(dlg, 'dialogue « Facturer la vente »').toBeVisible({ timeout: 60_000 })
  await expect(dlg).toContainText(`Facturer — ${v.reference}`)
  return dlg
}

/** Onglet Totalité, « Émettre tout de suite » coupé, « Créer la facture » → 409 `brouillons_a_remplacer` affiché ;
 *  renvoie le panneau « Remplacer les brouillons et facturer » qui liste le brouillon remis. */
async function jusquAuRemplacement(p, dlg, v, f) {
  await dlg.getByRole('tab', { name: 'Totalité' }).click()
  const emettre = dlg.getByRole('switch', { name: 'Émettre tout de suite' })
  await emettre.click()
  await expect(emettre, '« Émettre » coupé : le geste testé est le remplacement seul').toHaveAttribute('aria-checked', 'false')
  const cible = new RegExp(`/ventes/devis/${v.devisId}/facturer/$`)
  const [rep] = await Promise.all([
    p.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname), T),
    dlg.getByRole('button', { name: 'Créer la facture' }).click(),
  ])
  expect(rep.status(), `1er clic : ${(await rep.text()).slice(0, 300)}`).toBe(409)
  expect((await rep.json()).code).toBe('brouillons_a_remplacer')
  const panneau = dlg.getByTestId('facturer-remplacer')
  await expect(panneau, 'panneau de remplacement').toBeVisible()
  await expect(panneau, 'il nomme le brouillon remis (numéro légal)').toContainText(f.reference)
  return panneau
}

/** « Remplacer les brouillons et facturer » → réponse du POST (corps envoyé vérifié : remplacement, sans émettre). */
async function remplacer(p, panneau, v) {
  const cible = new RegExp(`/ventes/devis/${v.devisId}/facturer/$`)
  const [rep] = await Promise.all([
    p.waitForResponse((x) => x.request().method() === 'POST' && cible.test(new URL(x.url()).pathname), T),
    panneau.getByRole('button', { name: 'Remplacer les brouillons et facturer' }).click(),
  ])
  const corps = rep.request().postDataJSON()
  expect([corps.nature, corps.remplacer_brouillons, Boolean(corps.emettre), Boolean(corps.paiements)], 'corps envoyé : complete + remplacer, sans émettre ni paiement').toEqual(['complete', true, false, false])
  return rep
}

/** Étape de REFUS pour un rôle livré sans `encaisser` : écran, base, rechargement, écran rejoué, base relue. */
async function refusAuRole(page, suivi, testInfo, nomRole, prefixe) {
  const r = page.request
  const m = marque()
  const nom = `${prefixe}_${m}`
  const role = await compteDuRole(nom, nomRole)
  expect([role.systeme, role.porte], `${nomRole} : rôle système du registre, SANS encaisser`).toEqual([true, false])
  const v = await venteAcceptee(r, r, m)
  const f = await brouillonRemis(r, v)
  const avant = await etatBase(v, f.id)
  expect(avant.avoirs_brouillon, 'aucun avoir avant le geste').toEqual([])
  const cible = new RegExp(`/ventes/devis/${v.devisId}/facturer/$`)
  suivi.attendre(cible, 409) // 1er clic sans confirmation : `brouillons_a_remplacer` (parcours documenté du dialogue)
  suivi.attendre(cible, 403) // le refus PROUVÉ par l'étape (ASEC96)
  const p = await ecran(page, suivi, testInfo, nom)
  for (const passe of ['', 'après rechargement : ']) {
    if (passe) await p.reload()
    const dlg = await ouvrirDialogue(p, v)
    const panneau = await jusquAuRemplacement(p, dlg, v, f)
    const rep = await remplacer(p, panneau, v)
    expect(rep.status(), `${passe}${nomRole} : ${(await rep.text()).slice(0, 300)}`).toBe(403)
    expect(String((await rep.json()).detail), `${passe}${nomRole} : motif servi`).toContain(REFUS)
    await expect(dlg.getByTestId('facturer-bandeau'), `${passe}${nomRole} : refus au bandeau du dialogue`).toContainText(REFUS)
    await expect(dlg, `${passe}le dialogue reste ouvert`).toBeVisible()
    expect(await etatBase(v, f.id), `${passe}base relue : brouillon inchangé, aucune facture, aucun avoir`).toEqual(avant)
  }
  return { v, nom }
}

async function nettoyer(r, v) {
  if (!v) return
  await r.delete(`${API}/ventes/devis/${v.devisId}/`, T).catch(() => null)
  await r.delete(`${API}/crm/leads/${v.leadId}/`, T).catch(() => null)
}

etape('V7.96-AV', ['ASEC96'], async ({ page, suivi, testInfo }) => {
  // Sonde hôte du constat : rejouée ; si ses bouchons sont périmés par le correctif, elle est NOMMÉE, jamais comptée.
  const s = sondeHote('C-ASEC-VER7-096')
  if (s.ok) expect(s.res.repro, `sonde C-ASEC-VER7-096 : ${JSON.stringify(s.res.observe?.roles_sans_encaisser_qui_emettent_l_avoir)}`).toBe(false)
  else note(testInfo, 'sonde périmée (non comptée)', `C-ASEC-VER7-096 — ${s.err}`)
  const r = page.request
  const { v, nom } = await refusAuRole(page, suivi, testInfo, 'Admin Ventes', 'asec96av')
  await nettoyer(r, v)
  // Témoin : brouillon PROVISOIRE (`BROUILLON-<id>`) + Admin Ventes ⇒ 201 sans avoir (rien d'émis, pas d'encaisser exigé).
  const m = marque()
  const w = await venteAcceptee(r, r, `${m}w`)
  const b = (await lireJson(await r.post(`${API}/ventes/devis/${w.devisId}/facturer/`, { ...T, data: { nature: 'acompte', montant_ttc: '1200.00', emettre: false } }), 'brouillon provisoire')).facture
  expect(b.reference, 'brouillon provisoire').toMatch(/^BROUILLON-/)
  const av = await api(testInfo, nom)
  try {
    const avant = await etatBase(w, b.id)
    const x = await av.post(`${API}/ventes/devis/${w.devisId}/facturer/`, { ...T, data: { nature: 'complete', remplacer_brouillons: true } })
    expect(x.status(), `témoin BROUILLON- : ${(await x.text()).slice(0, 300)}`).toBe(201)
    const apres = await etatBase(w, b.id)
    expect([apres.avoirs_brouillon, apres.avoirs_societe, apres.brouillon[0]], 'témoin : aucun avoir, brouillon provisoire annulé').toEqual([[], avant.avoirs_societe, 'annulee'])
  } finally {
    await av.dispose()
    await nettoyer(r, w)
  }
})

etape('V7.96-RESP', ['ASEC96'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const { v } = await refusAuRole(page, suivi, testInfo, 'Responsable', 'asec96resp')
  await nettoyer(r, v)
})

etape('V7.96-COM', ['ASEC96'], async ({ page, suivi, testInfo }) => {
  // Rôle livré qui PORTE `encaisser` (Commercial) : le même geste passe, l'avoir de contre-passation est émis.
  const r = page.request
  const m = marque()
  const nom = `asec96com_${m}`
  const role = await compteDuRole(nom, 'Commercial')
  expect([role.systeme, role.porte], 'Commercial : rôle système du registre, AVEC encaisser').toEqual([true, true])
  const com = await api(testInfo, nom)
  const v = await venteAcceptee(r, com, m) // lead + devis portés par le Commercial (portée du rôle)
  await com.dispose()
  const f = await brouillonRemis(r, v)
  const avant = await etatBase(v, f.id)
  suivi.attendre(new RegExp(`/ventes/devis/${v.devisId}/facturer/$`), 409) // 1er clic sans confirmation (parcours documenté)
  const p = await ecran(page, suivi, testInfo, nom)
  const dlg = await ouvrirDialogue(p, v)
  const panneau = await jusquAuRemplacement(p, dlg, v, f)
  const rep = await remplacer(p, panneau, v)
  expect(rep.status(), `Commercial : ${(await rep.text()).slice(0, 300)}`).toBe(201)
  const nouvelle = (await rep.json()).facture
  await expect(dlg, 'dialogue refermé après succès').toBeHidden({ timeout: 30_000 })
  await expect(p.getByText(`Facture ${nouvelle.reference} créée en brouillon`), 'toast de succès').toBeVisible({ timeout: 30_000 })
  const apres = await etatBase(v, f.id)
  expect(apres.brouillon[0], 'brouillon remis annulé').toBe('annulee')
  expect(apres.avoirs_brouillon.length, 'UN avoir de contre-passation').toBe(1)
  expect(apres.avoirs_brouillon[0][3], 'avoir 1 200,00 TTC').toBe(1200)
  expect(apres.avoirs_brouillon[0][0].startsWith('BROUILLON-'), 'avoir numéroté').toBe(false)
  expect(apres.avoirs_societe, 'un seul avoir de plus dans la société').toBe(avant.avoirs_societe + 1)
  expect(apres.factures, 'la facture complète créée').toContain(nouvelle.id)
  expect(apres.factures.length, 'une seule facture de plus').toBe(avant.factures.length + 1)
  // Persistance : écran rechargé, la ligne du devis est là ; la base relue est identique.
  await p.reload()
  await p.getByPlaceholder('Rechercher (référence ou client)…').fill(v.reference, { timeout: 60_000 })
  await expect(p.locator(`#devis-row-${v.devisId}`), 'ligne du devis après rechargement').toBeVisible({ timeout: 60_000 })
  expect(await etatBase(v, f.id), 'base relue après rechargement').toEqual(apres)
  await nettoyer(r, v)
})

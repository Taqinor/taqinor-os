// Preuves en direct ACNC, lot 5 (audit PF9 « doubles clics, gestes rejoués, courses », dossier
// docs/audits/2026-11-11-parcours-PF9.md) : ACNC4, ACNC62, ACNC63 (PLAN_AUDIT_FACTURATION.md) et
// ACNC66, ACNC67, ACNC69 (PLAN_AUDIT_STOCK.md). Décision D-ACNC-1 (fondateur, 13/11) : paiement en double
// CONFIRMÉ, encaissement soldé refusé.
//
// Règle de preuve (METHODE §C.4 point 7) : chaque geste est joué par la vraie route — à l'écran sous le rôle
// du registre (compte d'essai connecté PAR L'ÉCRAN DE CONNEXION) ou par une session API du même rôle ; une
// course est une VRAIE course (le shell Django tient la ligne du BC, les deux requêtes sont vues bloquées
// ENSEMBLE dans `pg_stat_activity`, patron `course()` d'acnc2.spec.js) ; la base est relue par le shell.
// Données propres créées par l'API ou le shell, retirées en fin d'étape quand elles ne portent pas de
// numéro légal (base jetable du runner).
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI } from './_django.js'
import { lireJson, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'
import {
  monter, API, T, marque, SOC, AUJ, cents, statuts, note, bd, ouverts,
  venteAcceptee, lireF, factureEmise, payer, ligneFacture,
} from './_acnc.js'

const etape = groupe('ACNC', ['ACNC4', 'ACNC62', 'ACNC63', 'ACNC66', 'ACNC67', 'ACNC69'])
monter()
const J = JSON.stringify
const INIT = () => {
  try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
  try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
}
const apres = []
test.afterEach(async () => {
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})

/** Compte d'essai du rôle LIVRÉ `nomRole` (société démo, palier légacy dérivé du rôle) + session API. */
async function compte(testInfo, prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  const id = await py(`from apps.roles.models import Role
from authentication.role_tiers import tier_for_role_fields
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)})
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(u.id)`)
  const ctx = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  ouverts.push(ctx)
  await connexionApi(ctx, { username: nom, password: MDP_ESSAI })
  return { nom, id, ctx }
}
/** Navigateur À FROID du compte `nom` (connexion par l'écran), surveillé par les oracles ; la page demo_admin
 *  de l'étape est refermée (la capture montre l'écran du rôle joué). */
async function ecran(page, suivi, testInfo, nom, { fermer = true } = {}) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  if (fermer && !page.isClosed()) await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC4 — second paiement identique (même montant, même date) : 409 `paiement_similaire`, puis confirmé
// ════════════════════════════════════════════════════════════════════════════════════════════
const PHRASE = /Un\s+paiement\s+de\s+5\s?000\s+MAD\s+a\s+déjà\s+été\s+enregistré\s+(aujourd.hui|le\s+\d{2}\/\d{2}\/\d{4})\s+sur\s+cette\s+facture\s*:\s*confirmer\s*\?/
const etatPaiements = (id) => bd(`f = Facture.objects.get(pk=${id})
sortie({'paiements': [[str(p.montant), p.idempotency_key, str(p.date_paiement)] for p in Paiement.objects.filter(facture=f).order_by('pk')],
        'du': str(f.montant_du), 'ttc': str(f.total_ttc), 'statut': f.statut})`)

etape('PF9.1-ACNC4-api', ['ACNC4'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: c } = await compte(testInfo, 'acnc4c', 'Commercial')
  const { ctx: d } = await compte(testInfo, 'acnc4d', 'Directeur')
  const m = marque()
  const f = await factureEmise(c, await venteAcceptee(r, c, m, { prixHt: '10000.00' }))
  note(testInfo, 'Given', `facture ${f.reference} émise, TTC ${f.total_ttc}`)
  const url = `${API}/ventes/factures/${f.id}/enregistrer-paiement/`
  const base = { montant: '5000.00', mode: 'cheque', date_paiement: AUJ() }
  // 1er paiement de 5 000 daté du jour, par le Commercial.
  const p1 = await c.post(url, { ...T, data: { ...base, reference: `CHQ-1-${m}`, idempotency_key: `acnc4-1-${m}` } })
  expect(p1.status(), `1er paiement : ${(await p1.text()).slice(0, 200)}`).toBe(201)
  // 2e paiement IDENTIQUE par un AUTRE compte, AUTRE clé, sans confirmation ⇒ 409 typé, rien d'écrit.
  const corps2 = { ...base, reference: `CHQ-2-${m}`, idempotency_key: `acnc4-2-${m}` }
  const r2 = await d.post(url, { ...T, data: corps2 })
  const j2 = await r2.json()
  expect([r2.status(), j2.code], `2e envoi sans confirmation : ${J(j2)}`).toEqual([409, 'paiement_similaire'])
  expect(j2.detail, 'phrase serveur').toMatch(PHRASE)
  let e = await etatPaiements(f.id)
  expect(e.paiements.length, 'persistance après le 409 : UN paiement').toBe(1)
  expect(cents(e.du), 'reste dû = TTC − 5 000').toBe(cents(e.ttc) - 500000)
  const relue = await lireF(d, f.id)
  expect(relue.paiements.length, 'facture relue par l\'API : 1 paiement').toBe(1)
  // Même envoi (même clé) AVEC `confirmer_doublon` ⇒ 201, deux paiements.
  const r3 = await d.post(url, { ...T, data: { ...corps2, confirmer_doublon: true } })
  expect(r3.status(), `confirmé : ${(await r3.text()).slice(0, 200)}`).toBe(201)
  e = await etatPaiements(f.id)
  expect(e.paiements.map((x) => x[0]), 'DEUX paiements de 5 000').toEqual(['5000.00', '5000.00'])
  expect(cents(e.du), 'reste dû = TTC − 10 000').toBe(cents(e.ttc) - 1000000)
  // Ordre des refus (D-ACNC-1 : l'encaissement soldé reste refusé) : un 3e de 5 000 dépasse le reste ⇒ le refus
  // « dépasse » passe AVANT `paiement_similaire`, même confirmé.
  const r4 = await d.post(url, { ...T, data: { ...base, reference: `CHQ-3-${m}`, idempotency_key: `acnc4-3-${m}` } })
  const j4 = await r4.json()
  expect([r4.status(), j4.code ?? null], `3e envoi au-delà du reste : ${J(j4)}`).toEqual([409, null])
  expect(j4.detail).toMatch(/dépasse le reste à payer/)
  expect((await etatPaiements(f.id)).paiements.length, 'toujours deux paiements').toBe(2)
  await page.goto('/ventes/factures')
})

etape('PF9.1-ACNC4-ecran', ['ACNC4'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const com = await compte(testInfo, 'acnc4ec', 'Commercial')
  const dir = await compte(testInfo, 'acnc4ed', 'Directeur')
  const m = marque()
  const f = await factureEmise(com.ctx, await venteAcceptee(r, com.ctx, m, { prixHt: '10000.00' }))
  const rx = new RegExp(`/ventes/factures/${f.id}/enregistrer-paiement/$`)
  const ouvrir = async (p) => {
    const ligne = await ligneFacture(p, f.reference, f.id)
    await ligne.getByRole('button', { name: /Encaisser/ }).first().click()
    const dlg = p.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    await dlg.locator('#pay-montant').fill('5000.00')
    await dlg.locator('#pay-ref').fill(`CHQ-${marque()}`)
    return dlg
  }
  // Compte 1 (Directeur) : 5 000 saisis à l'écran.
  const pD = await ecran(page, suivi, testInfo, dir.nom)
  let dlg = await ouvrir(pD)
  const [rep1] = await Promise.all([pD.waitForResponse((x) => x.request().method() === 'POST' && rx.test(new URL(x.url()).pathname), T),
    dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click()])
  expect(rep1.status(), 'compte 1 : paiement enregistré').toBe(201)
  await expect(dlg, 'dialogue refermé').toBeHidden({ timeout: 60_000 })
  // Compte 2 (Commercial) : le MÊME paiement saisi de nouveau ⇒ la phrase serveur + « Confirmer ».
  const pC = await ecran(page, suivi, testInfo, com.nom, { fermer: false })
  const envois = []
  pC.on('request', (q) => { if (q.method() === 'POST' && rx.test(new URL(q.url()).pathname)) envois.push(q.postDataJSON()) })
  suivi.attendre(rx, 409)
  dlg = await ouvrir(pC)
  const [rep2] = await Promise.all([pC.waitForResponse((x) => x.request().method() === 'POST' && rx.test(new URL(x.url()).pathname), T),
    dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click()])
  expect(rep2.status(), 'compte 2 : 409 paiement_similaire').toBe(409)
  expect((await rep2.json()).code).toBe('paiement_similaire')
  const alerte = dlg.getByRole('alert').filter({ hasText: 'a déjà été enregistré' })
  await expect(alerte, 'la phrase serveur est affichée').toBeVisible({ timeout: 30_000 })
  await expect(alerte).toHaveText(PHRASE)
  const confirmer = alerte.getByRole('button', { name: 'Confirmer' })
  await expect(confirmer, 'bouton « Confirmer »').toBeVisible()
  // Persistance après le 409 : la facture relue porte UN paiement, reste dû TTC − 5 000.
  let e = await etatPaiements(f.id)
  expect(e.paiements.length, 'après le 409 : UN paiement en base').toBe(1)
  expect(cents(e.du)).toBe(cents(e.ttc) - 500000)
  // « Confirmer » ⇒ renvoi de la MÊME clé avec `confirmer_doublon` ⇒ 201, deux paiements.
  const [rep3] = await Promise.all([pC.waitForResponse((x) => x.request().method() === 'POST' && rx.test(new URL(x.url()).pathname), T), confirmer.click()])
  expect(rep3.status(), `confirmé : ${(await rep3.text()).slice(0, 200)}`).toBe(201)
  await expect(dlg, 'dialogue refermé au succès').toBeHidden({ timeout: 60_000 })
  expect(envois.length, 'deux envois du compte 2').toBe(2)
  expect(envois[1].idempotency_key, 'même clé renvoyée').toBe(envois[0].idempotency_key)
  expect([envois[0].confirmer_doublon ?? null, envois[1].confirmer_doublon], 'confirmer_doublon seulement au 2e envoi').toEqual([null, true])
  e = await etatPaiements(f.id)
  expect(e.paiements.map((x) => x[0]), 'DEUX paiements de 5 000').toEqual(['5000.00', '5000.00'])
  // Relu après rechargement : deux paiements listés.
  await pC.reload()
  const ligne = await ligneFacture(pC, f.reference, f.id)
  await ligne.getByRole('button', { name: /Encaisser/ }).first().click()
  const relu = pC.getByRole('dialog').filter({ hasText: `Enregistrer un paiement — ${f.reference}` })
  await expect(relu).toBeVisible({ timeout: 30_000 })
  await expect(relu.getByText('Paiements encaissés').locator('xpath=..').locator('li'), 'deux paiements listés').toHaveCount(2)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC62 — « Annuler » un BC relit le BC sous verrou : course RÉELLE avec « Créer la facture » / « Livrer partiellement »
// ════════════════════════════════════════════════════════════════════════════════════════════
const EN_ATTENTE = `from django.db import connection
with connection.cursor() as c:
    c.execute("select pg_stat_clear_snapshot()")
    c.execute("select left(query, 90) from pg_stat_activity where wait_event_type = 'Lock' and pid <> pg_backend_pid() and datname = current_database()")
    sortie([r[0] for r in c.fetchall()])`
/** Patron `course()` d'acnc2.spec.js : le shell tient `verrou` dans une transaction ouverte, les gestes partent,
 *  on attend `n` requêtes bloquées ENSEMBLE dans Postgres, puis le shell annule — les gestes reprennent. */
async function course({ verrou, gestes, n = 2, quoi }) {
  await py(`from django.db import transaction
transaction.set_autocommit(False)
${verrou}
sortie(True)`)
  let enVol = null
  let attentes = []
  try {
    enVol = Promise.all(gestes.map((g) => g()))
    enVol.catch(() => undefined)
    await expect.poll(async () => { attentes = await py(EN_ATTENTE); return attentes.length },
      { message: `${quoi} : ${n} requête(s) bloquée(s) ensemble dans Postgres`, timeout: 90_000 }).toBeGreaterThanOrEqual(n)
  } finally {
    await py(`from django.db import transaction
transaction.rollback()
transaction.set_autocommit(True)
sortie(True)`)
  }
  const reponses = await enVol
  console.log(`[${quoi}] requêtes bloquées ensemble : ${J(attentes)} → réponses ${J(reponses.map((x) => x.s))}`)
  return { reponses, attentes }
}
const lire = async (x) => ({ s: x.status(), b: await x.json().catch(() => null) })
const reglerSociete = (champ, valeur) => py(`import decimal
from authentication.models import Company
from apps.parametres.models import CompanyProfile
pr = CompanyProfile.get(company=Company.objects.get(pk=${SOC}))
avant = getattr(pr, ${J(champ)})
setattr(pr, ${J(champ)}, ${valeur})
pr.save()
sortie(str(avant))`)
/** BC en attente d'une vente (produit en stock 20, 5 unités) + chantier lié (patron acnc3.spec.js). */
async function bcEnAttente(r, m) {
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00', qte: '5', stock: 20 })
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${v.devisId}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
d = Devis.objects.get(pk=${v.devisId})
if not Installation.objects.filter(devis=d).exists():
    Installation.objects.create(company_id=d.company_id, reference='CHT-ACNC62-${m}', client_id=d.client_id, devis=d, statut=Installation.Statut.SIGNE)
sortie(1)`)
  return { v, bc }
}
const etatBc = (id) => bd(`from apps.ventes.models_facturation import LivraisonBC
b = BonCommande.objects.get(pk=${id})
sortie({'bc': b.statut, 'vivantes': Facture.objects.filter(bon_commande_id=b.pk).exclude(statut='annulee').count(),
        'livraisons': LivraisonBC.objects.filter(bon_commande_id=b.pk).count()})`)
const VERROU_BC = (id) => `from apps.ventes.models import BonCommande
BonCommande.objects.select_for_update().get(pk=${id})`
const LIBELLE = { en_attente: 'En attente', confirme: 'Confirmé', livre: 'Livré', annule: 'Annulé' }

etape('PF9.7-ACNC62-course', ['ACNC62'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const d1 = await compte(testInfo, 'acnc62a', 'Directeur')
  const d2 = await compte(testInfo, 'acnc62b', 'Directeur')
  const m = marque()
  // (1) BC confirmé : « Facture » (creer-facture) ∥ « Annuler », ligne du BC tenue par le shell.
  const { bc: bcF } = await bcEnAttente(r, `${m}f`)
  await lireJson(await d1.ctx.post(`${API}/ventes/bons-commande/${bcF.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  const c1 = await course({
    quoi: 'creer-facture ∥ annuler',
    verrou: VERROU_BC(bcF.id),
    gestes: [
      async () => lire(await d1.ctx.post(`${API}/ventes/bons-commande/${bcF.id}/creer-facture/`, { ...T, data: {} })),
      async () => lire(await d2.ctx.post(`${API}/ventes/bons-commande/${bcF.id}/annuler/`, { ...T, data: {} })),
    ],
  })
  expect(c1.attentes.length, 'les DEUX requêtes ont attendu le verrou du BC').toBeGreaterThanOrEqual(2)
  const [cf, an] = c1.reponses
  note(testInfo, 'course facture', `creer-facture ${cf.s} ${J(cf.b).slice(0, 160)} | annuler ${an.s} ${J(an.b).slice(0, 160)}`)
  expect([cf.s, an.s].filter((s) => s < 300).length, 'un seul des deux gestes aboutit (2xx)').toBe(1)
  expect([cf.s, an.s].filter((s) => s >= 300), 'le perdant répond 409').toEqual([409])
  const e1 = await etatBc(bcF.id)
  expect(e1.bc === 'annule' && e1.vivantes > 0, `jamais BC annulé portant une facture vivante (${J(e1)})`).toBe(false)
  expect(cf.s < 300 ? e1.vivantes : [e1.bc, e1.vivantes], 'état cohérent avec le gagnant').toEqual(cf.s < 300 ? 1 : ['annule', 0])
  // (2) BC confirmé : « Livrer partiellement » ∥ « Annuler ».
  const { v: vL, bc: bcL } = await bcEnAttente(r, `${m}l`)
  await lireJson(await d1.ctx.post(`${API}/ventes/bons-commande/${bcL.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  const ligneDevis = await bd(`sortie(Devis.objects.get(pk=${vL.devisId}).lignes.order_by('pk').first().pk)`)
  const c2 = await course({
    quoi: 'livrer-partiel ∥ annuler',
    verrou: VERROU_BC(bcL.id),
    gestes: [
      async () => lire(await d1.ctx.post(`${API}/ventes/bons-commande/${bcL.id}/livrer-partiel/`, { ...T, data: { lignes: [{ ligne_devis: ligneDevis, quantite: '2' }] } })),
      async () => lire(await d2.ctx.post(`${API}/ventes/bons-commande/${bcL.id}/annuler/`, { ...T, data: {} })),
    ],
  })
  expect(c2.attentes.length, 'les DEUX requêtes ont attendu le verrou du BC').toBeGreaterThanOrEqual(2)
  const [lv, an2] = c2.reponses
  note(testInfo, 'course livraison', `livrer-partiel ${lv.s} ${J(lv.b).slice(0, 160)} | annuler ${an2.s} ${J(an2.b).slice(0, 160)}`)
  expect([lv.s < 300, an2.s < 300].filter(Boolean).length, 'un seul des deux gestes aboutit').toBe(1)
  expect([lv.s, an2.s].filter((s) => s >= 300), 'le perdant répond 409').toEqual([409])
  const e2 = await etatBc(bcL.id)
  expect(e2.bc === 'annule' && e2.livraisons > 0, `jamais BC annulé portant une livraison (${J(e2)})`).toBe(false)
  // Persistance : relus une seconde fois, identiques.
  expect(await etatBc(bcF.id), 'BC facture relu : identique').toEqual(e1)
  expect(await etatBc(bcL.id), 'BC livraison relu : identique').toEqual(e2)
  // Écran : « Bons de commande » (Directeur), rechargé, montre le statut relu de chacun.
  const p = await ecran(page, suivi, testInfo, d1.nom)
  const verifierListe = async () => {
    for (const [bc, etat] of [[bcF, e1], [bcL, e2]]) {
      await p.goto('/ventes/bons-commande')
      await p.getByPlaceholder('Référence, client…').fill(bc.reference, { timeout: 60_000 })
      const ligne = p.getByRole('row').filter({ hasText: bc.reference })
      await expect(ligne, `${bc.reference} listé`).toBeVisible({ timeout: 60_000 })
      await expect(ligne, `${bc.reference} : statut relu « ${LIBELLE[etat.bc]} »`).toContainText(LIBELLE[etat.bc])
    }
  }
  await verifierListe()
  await p.reload()
  await verifierListe()
})

// Rejeu EN ENTIER de acnc3.spec.js › PF9.7-reseau (clause d'ACNC62) : même corps, mêmes affirmations.
const reservations = (v) => py(`from apps.installations.models import StockReservation
sortie([[x.quantite, x.active] for x in StockReservation.objects.filter(installation__devis_id=${v.devisId}, produit_id=${v.produitId})])`)
etape('PF9.7-reseau-rejeu', ['ACNC62'], async ({ page, testInfo }) => {
  const r = page.request
  const { ctx: d } = await compte(testInfo, 'acnc7', 'Directeur')
  const { ctx: d2 } = await compte(testInfo, 'acnc7b', 'Directeur')
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
  note(testInfo, 'course BC', `creer-facture ${cf.status()}, annuler ${an.status()}, base ${J(e2)}`)
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
  // (d) Deux « marquer payée » parallèles : 200 + 200, UNE ligne de journal.
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
  await page.goto('/ventes/bons-commande')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC63 — une facture ne se rattache plus à un BC annulé (sélecteur + 409)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.7-ACNC63-ecran', ['ACNC63'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc63', 'Directeur')
  const m = marque()
  const x = await bd(`from apps.crm.models import Client
cl = Client.objects.create(company_id=${SOC}, nom='Société Atlas ${m}', prenom='', type_client='entreprise', email='atlas-${m}@example.invalid')
a = BonCommande.objects.create(company_id=${SOC}, reference='BC-ACNC63-${m}-A', client=cl, statut='annule')
t = BonCommande.objects.create(company_id=${SOC}, reference='BC-ACNC63-${m}-T', client=cl, statut='en_attente')
sortie(dict(client=cl.pk, annule=a.pk, temoin=t.pk, ref_a=a.reference, ref_t=t.reference))`)
  apres.push(() => bd(`from apps.crm.models import Client
for fac in Facture.objects.filter(client_id=${x.client}):
    LigneFacture.objects.filter(facture=fac).delete(); fac.delete()
BonCommande.objects.filter(client_id=${x.client}).delete(); Client.objects.filter(pk=${x.client}).delete()
sortie(True)`))
  // Écran : « Nouvelle facture » — le BC annulé n'est pas proposé, le BC témoin (en attente, sans devis) l'est.
  const p = await ecran(page, suivi, testInfo, dir.nom)
  await p.goto('/ventes/factures')
  await p.getByRole('button', { name: 'Nouvelle facture' }).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Nouvelle facture' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#fc-bc').click()
  await expect(p.getByRole('option', { name: new RegExp(x.ref_t) }), 'BC témoin en attente proposé').toBeVisible({ timeout: 30_000 })
  await expect(p.getByRole('option', { name: new RegExp(x.ref_a) }), 'BC annulé NON proposé').toHaveCount(0)
  await p.keyboard.press('Escape')
  // API : le même corps qui choisit le BC annulé ⇒ 409 `bon_commande_annule`, aucune facture.
  const rep = await dir.ctx.post(`${API}/ventes/factures/`, { ...T, data: { client: x.client, bon_commande: x.annule, date_emission: AUJ() } })
  const corps = await rep.json()
  expect([rep.status(), corps.code], `POST BC annulé : ${J(corps)}`).toEqual([409, 'bon_commande_annule'])
  expect(String(corps.bon_commande), 'motif sous le champ BC').toMatch(/Ce bon de commande est annulé/)
  expect(await bd(`sortie(Facture.objects.filter(bon_commande_id=${x.annule}).count())`), 'persistance : aucune facture sur le BC annulé').toBe(0)
  // Témoin : BC sans devis en attente ⇒ accepté (201).
  const ok = await dir.ctx.post(`${API}/ventes/factures/`, { ...T, data: { client: x.client, bon_commande: x.temoin, date_emission: AUJ() } })
  expect(ok.status(), `POST BC en attente : ${(await ok.text()).slice(0, 200)}`).toBe(201)
  // Rechargé : le sélecteur ne propose toujours pas le BC annulé.
  await p.reload()
  await p.getByRole('button', { name: 'Nouvelle facture' }).first().click({ timeout: 60_000 })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#fc-bc').click()
  await expect(p.getByRole('option').first(), 'options chargées').toBeVisible({ timeout: 30_000 })
  await expect(p.getByRole('option', { name: new RegExp(x.ref_a) }), 'rechargé : BC annulé toujours absent').toHaveCount(0)
  await p.keyboard.press('Escape')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC66 — « Saisir un mouvement de stock » : réponse expirée ⇒ « l'action a peut-être abouti » sous le formulaire
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC66-ecran', ['ACNC66'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc66', 'Directeur')
  const m = marque()
  const x = await py(`from decimal import Decimal as D
from apps.stock.models import Produit
p = Produit.objects.create(company_id=${SOC}, nom='Câble 6 mm² ${m}', sku='ACNC66-${m}', prix_vente=D('10'), prix_achat=D('5'), quantite_stock=10)
sortie(dict(id=p.pk, nom=p.nom))`)
  apres.push(() => py(`from apps.stock.models import Produit, MouvementStock
MouvementStock.objects.filter(produit_id=${x.id}).delete(); Produit.objects.filter(pk=${x.id}).delete()
sortie(True)`))
  const MSG = "La réponse n'est pas arrivée : l'action a peut-être abouti. Vérifiez avant de recommencer."
  const p = await ecran(page, suivi, testInfo, dir.nom)
  suivi.attendre(/\/api\/django\/stock\/mouvements\/$/, 'reseau')
  await p.goto('/stock/mouvements')
  await p.getByRole('button', { name: 'Saisir mouvement' }).click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Saisir un mouvement de stock' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#mv-produit').click()
  await p.getByRole('option', { name: new RegExp(`Câble 6 mm² ${m}`) }).click()
  await dlg.locator('#mv-quantite').fill('3')
  await dlg.locator('#mv-reference').fill(`ACNC66-${m}`)
  // Le serveur APPLIQUE l'entrée, sa réponse est retenue au-delà du délai d'axios (20 s).
  let servi = null
  let liberer
  const porte = new Promise((res) => { liberer = res })
  await p.route((u) => u.pathname === `${API}/stock/mouvements/`, async (route) => {
    if (route.request().method() !== 'POST') { await route.fallback(); return }
    const rep = await route.fetch()
    servi = rep.status()
    await porte
    await route.abort('timedout').catch(() => undefined)
  })
  const debut = Date.now()
  await dlg.getByRole('button', { name: 'Enregistrer le mouvement' }).click()
  await expect.poll(() => servi, { message: 'le serveur a appliqué le mouvement', timeout: 60_000 }).toBe(201)
  await expect(dlg.getByText(MSG), 'sous le formulaire : « l\'action a peut-être abouti »').toBeVisible({ timeout: 45_000 })
  note(testInfo, 'délai', `message affiché ${Math.round((Date.now() - debut) / 1000)} s après le clic`)
  await expect(dlg, 'jamais « timeout of … exceeded »').not.toContainText('timeout of')
  liberer()
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  expect(await py(`from apps.stock.models import MouvementStock, Produit
sortie([MouvementStock.objects.filter(produit_id=${x.id}, reference='ACNC66-${m}').count(), float(Produit.objects.get(pk=${x.id}).quantite_stock)])`),
  'le mouvement a abouti UNE fois (10 + 3)').toEqual([1, 13])
  // Persistance : rechargé, le mouvement est listé une fois.
  await p.reload()
  await expect(p.locator('[aria-label="Mouvements de stock"]').getByRole('row').filter({ hasText: `ACNC66-${m}` }),
    'après rechargement : le mouvement, une ligne').toHaveCount(1, { timeout: 60_000 })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC67 — grand livre des paiements fournisseur : même Idempotency-Key entre deux clics, registre relu
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC67-ecran', ['ACNC67'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc67', 'Directeur')
  const m = marque()
  const x = await py(`import datetime
from decimal import Decimal
from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC67 ${m}', type='service')
ff = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC67-${m}', fournisseur=f,
    date_facture=datetime.date.today(), montant_ht=Decimal('8333.33'), montant_tva=Decimal('1666.67'), montant_ttc=Decimal('10000'))
sortie(dict(f=f.pk, ff=ff.pk, ref=ff.reference))`)
  apres.push(() => py(`from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur, PaiementFournisseur
PaiementFournisseur.objects.filter(facture_id=${x.ff}).delete(); FactureFournisseur.objects.filter(pk=${x.ff}).delete(); Fournisseur.objects.filter(pk=${x.f}).delete()
sortie(True)`))
  const etat = () => py(`from apps.achats.models import FactureFournisseur, PaiementFournisseur
ff = FactureFournisseur.objects.get(pk=${x.ff})
sortie({'reglements': [str(p.montant) for p in PaiementFournisseur.objects.filter(facture=ff).order_by('pk')], 'solde': str(ff.solde_du)})`)
  const rx = /\/api\/django\/stock\/paiements-fournisseur\/$/
  const cles = []
  const p = await ecran(page, suivi, testInfo, dir.nom)
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(q.url().split('?')[0])) cles.push(q.headers()['idempotency-key'] ?? null) })
  // La réponse du 1er POST est coupée APRÈS passage au serveur (`route.fetch()` puis `route.abort()`).
  suivi.attendre(rx, 'reseau')
  let coupe = true
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.continue()
  })
  await p.goto('/stock/paiements-fournisseur')
  const saisir = async (montant) => {
    await p.getByRole('combobox', { name: 'Facture fournisseur' }).click({ timeout: 60_000 })
    await p.getByRole('option', { name: new RegExp(x.ref) }).click()
    await p.getByLabel('Montant du règlement').fill(montant)
    await p.getByLabel('Date du règlement').fill(AUJ())
  }
  await saisir('3000')
  const bouton = p.getByRole('button', { name: 'Enregistrer le règlement' })
  const relu = p.waitForResponse((r) => r.request().method() === 'GET' && /\/stock\/paiements-fournisseur\//.test(r.url()), T)
  await bouton.click()
  await expect.poll(() => cles.length, { timeout: 30_000 }).toBe(1)
  await relu
  // Registre relu après l'échec : le règlement que le serveur a bien enregistré apparaît.
  const lignes = p.getByTestId('table-paiements').getByRole('row').filter({ hasText: x.ref })
  await expect(lignes, 'registre relu après la réponse perdue : le règlement de 3 000 est listé').toHaveCount(1, { timeout: 30_000 })
  expect(await etat(), 'le 1er POST est passé au serveur').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // Second clic, saisie gardée ⇒ MÊME clé ⇒ rejeu, toujours UN règlement.
  await expect(p.getByLabel('Montant du règlement'), 'saisie gardée').toHaveValue('3000')
  const [rep2] = await Promise.all([p.waitForResponse((r) => r.request().method() === 'POST' && rx.test(r.url().split('?')[0]), T), bouton.click()])
  expect(rep2.status(), `second clic : ${(await rep2.text()).slice(0, 200)}`).toBeLessThan(300)
  expect(cles.length).toBe(2)
  expect(cles[0], 'une clé est envoyée').toBeTruthy()
  expect(cles[1], 'les deux POST portent la MÊME Idempotency-Key').toBe(cles[0])
  expect(await etat(), 'UN règlement de 3 000, solde 7 000').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  await expect(lignes, 'toujours une ligne au registre').toHaveCount(1, { timeout: 30_000 })
  // Le règlement suivant part avec une clé NEUVE.
  await saisir('1000')
  const [rep3] = await Promise.all([p.waitForResponse((r) => r.request().method() === 'POST' && rx.test(r.url().split('?')[0]), T), bouton.click()])
  expect(rep3.status()).toBe(201)
  expect(cles[2], 'règlement suivant : clé neuve').not.toBe(cles[0])
  expect(await etat(), 'deux règlements, solde 6 000').toEqual({ reglements: ['3000.00', '1000.00'], solde: '6000.00' })
  // Persistance : rechargé, deux lignes au registre.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(p.getByTestId('table-paiements').getByRole('row').filter({ hasText: x.ref }), 'rechargé : deux règlements').toHaveCount(2, { timeout: 60_000 })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC69 — BCF : un second « Envoyer au fournisseur » après un envoi refusé repart avec la version servie
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC69-ecran', ['ACNC69'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc69', 'Directeur')
  const m = marque()
  const x = await py(`from decimal import Decimal
from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
from apps.installations.models import SeuilApprobationBCF
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC69 ${m}')
prods = [Produit.objects.create(company_id=${SOC}, nom='ACNC69 article %s ${m}' % n, prix_vente=100, prix_achat=60) for n in ('A', 'B')]
b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference='BCF-ACNC69-${m}', fournisseur=f, statut='brouillon', date_commande=timezone.localdate())
for pr in prods:
    LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=pr, quantite=10, prix_achat_unitaire=Decimal('60'))
s = SeuilApprobationBCF.objects.create(company_id=${SOC}, seuil_responsable=Decimal('100'), actif=True)
b.refresh_from_db()
sortie(dict(f=f.pk, prods=[p.pk for p in prods], bcf=b.pk, seuil=s.pk, version=b.lock_version))`)
  apres.push(() => py(`from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur
from apps.installations.models import SeuilApprobationBCF
for qs in (SeuilApprobationBCF.objects.filter(pk=${x.seuil}), BonCommandeFournisseur.objects.filter(pk=${x.bcf}),
           Produit.objects.filter(pk__in=${J(x.prods)}), Fournisseur.objects.filter(pk=${x.f})):
    try: qs.delete()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`))
  const rxP = new RegExp(`/api/django/stock/bons-commande-fournisseur/${x.bcf}/$`)
  const rxE = new RegExp(`/api/django/stock/bons-commande-fournisseur/${x.bcf}/envoyer/$`)
  const p = await ecran(page, suivi, testInfo, dir.nom)
  suivi.attendre(rxE, 409)
  const patchs = []
  p.on('request', (q) => { if (q.method() === 'PATCH' && rxP.test(q.url().split('?')[0])) patchs.push(q.postDataJSON()) })
  await p.goto('/stock/bons-commande-fournisseur')
  await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(`BCF-ACNC69-${m}`, { timeout: 60_000 })
  const ligne = p.getByRole('row').filter({ hasText: `BCF-ACNC69-${m}` })
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByText(`BCF-ACNC69-${m}`).click()
  const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-ref-fou') })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  const envoyer = async () => {
    const patch = p.waitForResponse((r) => r.request().method() === 'PATCH' && rxP.test(r.url().split('?')[0]), T)
    const envoi = p.waitForResponse((r) => r.request().method() === 'POST' && rxE.test(r.url().split('?')[0]), T)
    await dlg.getByRole('button', { name: 'Envoyer au fournisseur' }).click()
    const rp = await patch
    const re = await envoi
    return { patch: { s: rp.status(), b: await rp.json() }, envoi: { s: re.status(), b: await re.json() } }
  }
  const SEUIL = /dépasse le seuil d.approbation/
  const e1 = await envoyer()
  expect(e1.patch.s, `1er PATCH : ${J(e1.patch.b).slice(0, 200)}`).toBe(200)
  expect([e1.envoi.s, e1.envoi.b.detail], '1er envoi refusé : seuil d\'approbation').toEqual([409, expect.stringMatching(SEUIL)])
  await expect(dlg, 'message du seuil affiché').toContainText(SEUIL, { timeout: 30_000 })
  const servie = e1.patch.b.lock_version
  expect(servie, 'le PATCH a avancé la version').toBeGreaterThan(patchs[0].lock_version)
  // Nouvel essai : le 2e PATCH part avec la version SERVIE par le 1er, jamais « modifié entre-temps ».
  const e2 = await envoyer()
  expect(patchs.length).toBe(2)
  expect(patchs[1].lock_version, `2e PATCH : lock_version servie (${servie})`).toBe(servie)
  expect(e2.patch.s, `2e PATCH : ${J(e2.patch.b).slice(0, 200)}`).toBe(200)
  expect([e2.envoi.s, e2.envoi.b.detail], '2e envoi : de nouveau le seuil').toEqual([409, expect.stringMatching(SEUIL)])
  await expect(dlg, 'de nouveau le message du seuil').toContainText(SEUIL, { timeout: 30_000 })
  await expect(dlg, 'jamais « modifié entre-temps »').not.toContainText('modifié entre-temps')
  note(testInfo, 'versions', `BCF v${x.version} → PATCH 1 envoie ${patchs[0].lock_version}, servi ${servie} → PATCH 2 envoie ${patchs[1].lock_version}`)
  // Persistance : le BCF relu reste brouillon avec ses 2 lignes.
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.get(pk=${x.bcf})
sortie([b.statut, b.lignes.count()])`), 'BCF relu : brouillon, 2 lignes').toEqual(['brouillon', 2])
})

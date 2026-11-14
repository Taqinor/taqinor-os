// Preuves en direct ACNC, lot 6 (contre-visite du 14/11, 2e passe : C-ACNC-VER2-200, -201, -202) : ACNC70 et ACNC71
// (PLAN_AUDIT_FACTURATION.md), ACNC72 (PLAN_AUDIT_STOCK.md).
//
// Règle de preuve (METHODE §C.4 point 7) : chaque geste est joué par la vraie route — à l'écran sous le rôle LIVRÉ du
// registre (compte d'essai connecté PAR L'ÉCRAN DE CONNEXION) ou par une session API du même rôle ; une course est une
// VRAIE course (le shell Django tient une ligne, les requêtes sont vues bloquées dans `pg_stat_activity`, patron
// `course()` d'acnc2.spec.js / acnc5.spec.js) ; une réponse perdue est coupée APRÈS passage au serveur (`route.fetch()`
// puis `route.abort()`) ; la base est relue par le shell. Données propres créées par l'API ou le shell ; les factures à
// numéro légal restent dans la base jetable du runner.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI } from './_django.js'
import { lireJson, connexionApi, uiLoginJusquAuxApps } from '../helpers.js'
import {
  monter, API, T, marque, SOC, AUJ, note, bd, ouverts, couper, reponse,
  venteAcceptee, factureEmise, ligneFacture,
} from './_acnc.js'

const etape = groupe('ACNC', ['ACNC70', 'ACNC71', 'ACNC72'])
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
/** Navigateur À FROID du compte `nom` (connexion par l'écran), surveillé par les oracles ; la page demo_admin de
 *  l'étape est refermée (la capture montre l'écran du rôle joué). */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block',
    ...(u.locale ? { locale: u.locale } : {}), ...(u.timezoneId ? { timezoneId: u.timezoneId } : {}), viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  if (!page.isClosed()) await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC70 — « Facturer la vente » (complète) ∥ « Annuler » le BC : jamais un BC annulé portant une facture vivante
// ════════════════════════════════════════════════════════════════════════════════════════════
const EN_ATTENTE = `from django.db import connection
with connection.cursor() as c:
    c.execute("select pg_stat_clear_snapshot()")
    c.execute("select left(query, 90) from pg_stat_activity where wait_event_type = 'Lock' and pid <> pg_backend_pid() and datname = current_database()")
    sortie([r[0] for r in c.fetchall()])`
const lire = async (x) => ({ s: x.status(), b: await x.json().catch(() => null) })
/** BC CONFIRMÉ d'une vente acceptée, sans facture ni livraison (une ligne de 5 unités : le helper partagé `venteAcceptee`
 *  pose une ligne ; le nombre de lignes n'entre pas dans la course BC ∥ facture). */
async function bcConfirme(r, dir, m) {
  const v = await venteAcceptee(r, r, m, { prixHt: '1000.00', qte: '5' })
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${v.devisId}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await dir.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  return { v, bc }
}
const etatVente = (devisId, bcId) => bd(`from apps.ventes.models_facturation import LivraisonBC
b = BonCommande.objects.get(pk=${bcId})
fs = Facture.objects.filter(devis_id=${devisId}, type_facture='complete').exclude(statut='annulee').order_by('pk')
sortie({'bc': b.statut, 'vivantes_bc': Facture.objects.filter(bon_commande_id=b.pk).exclude(statut='annulee').count(),
        'completes': [[f.pk, f.bon_commande_id, f.statut] for f in fs]})`)
/** Le shell tient `verrou` ; « Facturer la vente » part et est vu EN ATTENTE ; puis « Annuler » part (il finit, ou
 *  attend à son tour) ; le shell relâche ; les deux répondent. */
async function course(verrou, facturer, annuler, quoi) {
  await py(`from django.db import transaction
transaction.set_autocommit(False)
from apps.ventes.models import Devis, BonCommande
${verrou}
sortie(True)`)
  let fa = null
  let an = null
  let anFini = false
  const vus = []
  try {
    fa = facturer()
    fa.catch(() => undefined)
    await expect.poll(async () => (await py(EN_ATTENTE)).length,
      { message: `${quoi} : « Facturer la vente » en attente du verrou`, timeout: 90_000 }).toBeGreaterThanOrEqual(1)
    vus.push(await py(EN_ATTENTE))
    an = annuler()
    an.then(() => { anFini = true }, () => { anFini = true })
    await expect.poll(async () => anFini || (await py(EN_ATTENTE)).length >= 2,
      { message: `${quoi} : « Annuler » a fini ou attend à son tour`, timeout: 90_000 }).toBe(true)
    vus.push(await py(EN_ATTENTE))
  } finally {
    await py(`from django.db import transaction
transaction.rollback()
transaction.set_autocommit(True)
sortie(True)`)
  }
  const [rf, ra] = await Promise.all([fa, an])
  console.log(`[${quoi}] en attente : ${J(vus)} → facturer ${rf.s}, annuler ${ra.s} ${J(ra.b).slice(0, 200)}`)
  return { rf, ra, vus, anFiniSousVerrou: vus[1].length < 2 }
}
const LIBELLE = { en_attente: 'En attente', confirme: 'Confirmé', livre: 'Livré', annule: 'Annulé' }

/** Invariant + issue cohérente avec le gagnant (Then de la clause). */
function juger(c, e, quoi) {
  expect(e.bc === 'annule' && e.vivantes_bc > 0, `${quoi} : jamais BC annulé portant une facture vivante (${J(e)})`).toBe(false)
  expect(c.rf.s, `${quoi} : « Facturer la vente » répond (${J(c.rf.b).slice(0, 200)})`).toBeLessThan(300)
  expect(e.completes.length, `${quoi} : une facture complète vivante`).toBe(1)
  if (c.ra.s === 409) {
    expect(c.ra.b?.detail, `${quoi} : 409 « La facture … est encore vivante sur ce bon de commande »`).toMatch(/est encore vivante sur ce bon de commande/)
    expect(e.bc, `${quoi} : BC non annulé`).not.toBe('annule')
    expect(e.completes[0][1], `${quoi} : facture complète rattachée au BC`).toBe(c.bcId)
  } else {
    expect(c.ra.s, `${quoi} : « Annuler » 2xx sinon 409`).toBeLessThan(300)
    expect([e.bc, e.completes[0][1]], `${quoi} : BC annulé, facture complète née SANS bon_commande`).toEqual(['annule', null])
  }
}

etape('PF9.7-ACNC70-course', ['ACNC70'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const d1 = await compte(testInfo, 'acnc70a', 'Directeur')
  const d2 = await compte(testInfo, 'acnc70b', 'Directeur')
  const m = marque()
  const facturer = (ctx, devisId) => async () => lire(await ctx.post(`${API}/ventes/devis/${devisId}/facturer/`, { ...T, data: { nature: 'complete', remplacer_brouillons: true } }))
  const annuler = (ctx, bcId) => async () => lire(await ctx.post(`${API}/ventes/bons-commande/${bcId}/annuler/`, { ...T, data: {} }))
  // (1) Clause : ligne du DEVIS tenue par le shell jusqu'à voir « Facturer » en attente, puis « Annuler ».
  const A = await bcConfirme(r, d1.ctx, `${m}a`)
  const cA = await course(`Devis.objects.select_for_update().get(pk=${A.v.devisId})`, facturer(d1.ctx, A.v.devisId), annuler(d2.ctx, A.bc.id), 'devis tenu')
  cA.bcId = A.bc.id
  const eA = await etatVente(A.v.devisId, A.bc.id)
  note(testInfo, 'course devis tenu', `facturer ${cA.rf.s} | annuler ${cA.ra.s} ${J(cA.ra.b).slice(0, 160)} | base ${J(eA)}`)
  juger(cA, eA, 'devis tenu')
  // (2) Ligne du BC tenue : « Facturer » (vente puis BC sous verrou) attend, « Annuler » attend derrière lui.
  const B = await bcConfirme(r, d1.ctx, `${m}b`)
  const cB = await course(`BonCommande.objects.select_for_update().get(pk=${B.bc.id})`, facturer(d1.ctx, B.v.devisId), annuler(d2.ctx, B.bc.id), 'BC tenu')
  cB.bcId = B.bc.id
  const eB = await etatVente(B.v.devisId, B.bc.id)
  note(testInfo, 'course BC tenu', `facturer ${cB.rf.s} | annuler ${cB.ra.s} ${J(cB.ra.b).slice(0, 160)} | base ${J(eB)}`)
  expect(cB.vus[1].length, 'BC tenu : les DEUX requêtes ont attendu ensemble').toBeGreaterThanOrEqual(2)
  juger(cB, eB, 'BC tenu')
  // Persistance : relus une seconde fois, identiques.
  expect(await etatVente(A.v.devisId, A.bc.id), 'vente A relue : identique').toEqual(eA)
  expect(await etatVente(B.v.devisId, B.bc.id), 'vente B relue : identique').toEqual(eB)
  // Écran : « Bons de commande » (Directeur), rechargé, montre le statut relu de chacun.
  const p = await ecran(page, suivi, testInfo, d1.nom)
  const verifierListe = async () => {
    for (const [bc, etat] of [[A.bc, eA], [B.bc, eB]]) {
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

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC71 — « Note de débit » : réponse perdue sur A, ouverture sur B ⇒ saisie vide, clé neuve, note sur B
// ════════════════════════════════════════════════════════════════════════════════════════════
const etatNotes = (id) => bd(`f = Facture.objects.get(pk=${id})
sortie({'notes': [[n.pk, n.reference] for n in NoteDebit.objects.filter(facture=f).order_by('pk')]})`)

etape('PF9.2-ACNC71-ecran', ['ACNC71'], async ({ page, suivi, testInfo }) => {
  const r = page.request
  const dir = await compte(testInfo, 'acnc71', 'Directeur')
  const m = marque()
  const fa = await factureEmise(r, await venteAcceptee(r, r, `${m}a`, { prixHt: '8333.33' }))
  const fb = await factureEmise(r, await venteAcceptee(r, r, `${m}b`, { prixHt: '8333.33' }))
  expect([Number(fa.taux_tva ?? 20), Number(fb.taux_tva ?? 20)], 'Given : deux factures émises à TVA 20 %').toEqual([20, 20])
  const p = await ecran(page, suivi, testInfo, dir.nom)
  const rx = /\/creer-note-debit\/$/
  const boite = (f) => p.getByRole('dialog').filter({ hasText: `Notes de débit — ${f.reference}` })
  const ouvrir = async (f) => {
    const ligne = await ligneFacture(p, f.reference, f.id)
    const bouton = ligne.getByRole('button', { name: /Actions/ })
    // Patron aerr6.spec.js (AERR133) : si la page reste inerte au pointeur après une boîte refermée (défaut antérieur
    // de FactureRow.jsx, hors des Files d'ACNC71), la ligne est ouverte au clavier.
    if (await p.evaluate(() => getComputedStyle(document.body).pointerEvents) === 'none') {
      testInfo.annotations.push({ type: 'défaut antérieur', description: 'page inerte au pointeur après la boîte de A' })
      await bouton.focus()
      await p.keyboard.press('Enter')
    } else {
      await bouton.click()
    }
    await p.getByRole('menuitem', { name: 'Note de débit' }).click()
    await expect(boite(f), `boîte ouverte sur ${f.reference}`).toBeVisible({ timeout: 30_000 })
    return boite(f)
  }
  const fermer = async (f) => {
    await boite(f).getByRole('button', { name: 'Fermer' }).click()
    await expect(boite(f), `boîte de ${f.reference} refermée`).toBeHidden({ timeout: 30_000 })
    if (await p.getByRole('menu').isVisible()) await p.keyboard.press('Escape')
    await expect(p.getByRole('menu'), 'menu de ligne refermé').toHaveCount(0)
  }
  // A : pénalité de 500 HT, la réponse du POST est coupée APRÈS passage au serveur.
  const envois = await couper(p, rx, suivi)
  let dlg = await ouvrir(fa)
  await dlg.locator('#nd-motif').fill('pénalité')
  await dlg.locator('#nd-montant').fill('500')
  await dlg.getByRole('button', { name: 'Créer la note de débit' }).click()
  await expect(dlg.getByRole('alert'), 'A : échec sans réponse affiché').toBeVisible({ timeout: 60_000 })
  await expect(dlg.locator('li').filter({ hasText: /ND-/ }), 'A : liste relue, la note créée paraît').toHaveCount(1, { timeout: 60_000 })
  expect((await etatNotes(fa.id)).notes.length, 'A : le POST est passé au serveur (une note)').toBe(1)
  // Fermer, ouvrir sur B : saisie VIDE.
  await fermer(fa)
  dlg = await ouvrir(fb)
  await expect(dlg.locator('#nd-motif'), 'B : motif vide à l\'ouverture').toHaveValue('')
  await expect(dlg.locator('#nd-montant'), 'B : montant vide à l\'ouverture').toHaveValue('')
  await expect(dlg.getByText('Aucune note de débit sur cette facture.'), 'B : aucune note').toBeVisible({ timeout: 30_000 })
  // Ressaisie identique, « Créer » ⇒ clé NEUVE, note créée sur B.
  await dlg.locator('#nd-motif').fill('pénalité')
  await dlg.locator('#nd-montant').fill('500')
  const [rep] = await Promise.all([reponse(p, rx), dlg.getByRole('button', { name: 'Créer la note de débit' }).click()])
  expect(rep.status(), `B : création ${(await rep.text()).slice(0, 200)}`).toBe(201)
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0].idempotency_key, 'A : une clé envoyée').toBeTruthy()
  expect(envois[1].idempotency_key, 'B : clé DIFFÉRENTE de celle de A').not.toBe(envois[0].idempotency_key)
  const nB = (await rep.json()).reference
  const eA = await etatNotes(fa.id)
  const eB = await etatNotes(fb.id)
  note(testInfo, 'notes', `A ${J(eA)} | B ${J(eB)} | réponse B ${nB}`)
  expect([eA.notes.length, eB.notes.length], 'base : une note sur A, une note sur B').toEqual([1, 1])
  expect(eB.notes[0][1], 'B : la note rendue est celle de B (pas un rejeu de A)').toBe(nB)
  expect(nB, 'B : référence distincte de la note de A').not.toBe(eA.notes[0][1])
  await expect(dlg.locator('li').filter({ hasText: nB }), 'B : sa note listée').toHaveCount(1, { timeout: 30_000 })
  // Persistance : rechargé, B porte UNE note, la sienne.
  await p.unroute(rx)
  await p.reload()
  dlg = await ouvrir(fb)
  await expect(dlg.locator('li').filter({ hasText: /ND-/ }), 'rechargé : B, une note').toHaveCount(1, { timeout: 60_000 })
  await expect(dlg.locator('li').filter({ hasText: nB }), 'rechargé : la note de B').toHaveCount(1)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC72 — règlement fournisseur : réponse coupée puis saisie changée ⇒ clé NEUVE (grand livre et fiche facture)
// ════════════════════════════════════════════════════════════════════════════════════════════
const facturesFournisseur = (m, montants) => py(`import datetime
from decimal import Decimal
from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC72 ${m}', type='service')
ffs = []
for i, ttc in enumerate(${J(montants)}):
    ttc = Decimal(ttc); ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
    ff = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC72-${m}-%d' % (i + 1), fournisseur=f,
        date_facture=datetime.date.today(), montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc)
    ffs.append([ff.pk, ff.reference])
sortie(dict(f=f.pk, ffs=ffs))`)
const retirerFf = (x) => py(`from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur, PaiementFournisseur
ids = ${J(x.ffs.map((y) => y[0]))}
PaiementFournisseur.objects.filter(facture_id__in=ids).delete(); FactureFournisseur.objects.filter(pk__in=ids).delete(); Fournisseur.objects.filter(pk=${x.f}).delete()
sortie(True)`)
const reglements = (x) => py(`from apps.achats.models import FactureFournisseur, PaiementFournisseur
out = []
for pk in ${J(x.ffs.map((y) => y[0]))}:
    ff = FactureFournisseur.objects.get(pk=pk)
    out.append({'reglements': [str(p.montant) for p in PaiementFournisseur.objects.filter(facture=ff).order_by('pk')], 'solde': str(ff.solde_du)})
sortie(out)`)

etape('PF9.4-ACNC72-grand-livre', ['ACNC72'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc72', 'Directeur')
  const m = marque()
  const x = await facturesFournisseur(m, ['10000', '4000'])
  apres.push(() => retirerFf(x))
  const [[, ref1], [, ref2]] = x.ffs
  const rx = /\/api\/django\/stock\/paiements-fournisseur\/$/
  const cles = []
  const p = await ecran(page, suivi, testInfo, dir.nom)
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(q.url().split('?')[0])) cles.push(q.headers()['idempotency-key'] ?? null) })
  suivi.attendre(rx, 'reseau')
  let coupe = true
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.continue()
  })
  await p.goto('/stock/paiements-fournisseur')
  const saisir = async (ref, montant) => {
    await p.getByRole('combobox', { name: 'Facture fournisseur' }).click({ timeout: 60_000 })
    await p.getByRole('option', { name: new RegExp(ref) }).click()
    await p.getByLabel('Montant du règlement').fill(montant)
    await p.getByLabel('Date du règlement').fill(AUJ())
  }
  const bouton = p.getByRole('button', { name: 'Enregistrer le règlement' })
  const registre = (ref) => p.getByTestId('table-paiements').getByRole('row').filter({ hasText: ref })
  // 3 000 sur la première facture : réponse coupée après passage au serveur ; le registre relu montre le règlement.
  await saisir(ref1, '3000')
  const relu = p.waitForResponse((q) => q.request().method() === 'GET' && /\/stock\/paiements-fournisseur\//.test(q.url()), T)
  await bouton.click()
  await expect.poll(() => cles.length, { timeout: 30_000 }).toBe(1)
  await relu
  await expect(registre(ref1), 'registre relu après la réponse perdue : le règlement de 3 000').toHaveCount(1, { timeout: 30_000 })
  expect((await reglements(x))[0], 'le 1er POST est passé au serveur').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // Saisie changée : la seconde facture, 1 000 ⇒ clé NEUVE, 201.
  await saisir(ref2, '1000')
  const [rep] = await Promise.all([p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(q.url().split('?')[0]), T), bouton.click()])
  expect(rep.status(), `règlement de la seconde facture : ${(await rep.text()).slice(0, 200)}`).toBe(201)
  expect(cles.length).toBe(2)
  expect(cles[0], 'une clé est envoyée').toBeTruthy()
  expect(cles[1], 'saisie changée : clé NEUVE (jamais le 409 « clé déjà utilisée »)').not.toBe(cles[0])
  expect(await reglements(x), 'base : 3 000 et 1 000').toEqual([{ reglements: ['3000.00'], solde: '7000.00' }, { reglements: ['1000.00'], solde: '3000.00' }])
  // Persistance : rechargé, les deux règlements au registre.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(registre(ref1), 'rechargé : 3 000 sur la première').toHaveCount(1, { timeout: 60_000 })
  await expect(registre(ref2), 'rechargé : 1 000 sur la seconde').toHaveCount(1, { timeout: 60_000 })
})

etape('PF9.4-ACNC72-fiche-facture', ['ACNC72'], async ({ page, suivi, testInfo }) => {
  const dir = await compte(testInfo, 'acnc72f', 'Directeur')
  const m = marque()
  const x = await facturesFournisseur(m, ['10000'])
  apres.push(() => retirerFf(x))
  const [[ffId, ref]] = x.ffs
  const rx = new RegExp(`/api/django/stock/factures-fournisseur/${ffId}/paiements/$`)
  const envois = []
  const p = await ecran(page, suivi, testInfo, dir.nom)
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(q.url().split('?')[0])) envois.push({ cle: q.headers()['idempotency-key'] ?? null, corps: q.postDataJSON() }) })
  suivi.attendre(rx, 'reseau')
  let coupe = true
  await p.route(rx, async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.continue()
  })
  const ouvrir = async () => {
    await p.goto('/stock/factures-fournisseur')
    await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(ref, { timeout: 60_000 })
    await p.getByRole('row').filter({ hasText: ref }).getByText(ref).first().click({ timeout: 60_000 })
    const dlg = p.getByRole('dialog').filter({ hasText: `Facture — ${ref}` })
    await expect(dlg, 'fiche de la facture ouverte').toBeVisible({ timeout: 30_000 })
    return dlg
  }
  let dlg = await ouvrir()
  // 3 000 : réponse coupée après passage au serveur.
  await dlg.locator('#pay-montant').fill('3000')
  await dlg.getByRole('button', { name: 'Ajouter le paiement' }).click()
  await expect.poll(() => envois.length, { timeout: 30_000 }).toBe(1)
  await expect(dlg.getByRole('alert').first(), 'échec sans réponse affiché').toBeVisible({ timeout: 60_000 })
  expect((await reglements(x))[0], 'le 1er POST est passé au serveur').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // Montant changé (1 000) ⇒ clé NEUVE, 201.
  await dlg.locator('#pay-montant').fill('1000')
  const [rep] = await Promise.all([p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(q.url().split('?')[0]), T),
    dlg.getByRole('button', { name: 'Ajouter le paiement' }).click()])
  expect(rep.status(), `paiement de 1 000 : ${(await rep.text()).slice(0, 200)}`).toBeLessThan(300)
  expect(envois.length).toBe(2)
  expect(envois[0].cle, 'une clé est envoyée').toBeTruthy()
  expect(envois[1].cle, 'montant changé : clé NEUVE').not.toBe(envois[0].cle)
  expect(await reglements(x), 'base : 3 000 et 1 000, solde 6 000').toEqual([{ reglements: ['3000.00', '1000.00'], solde: '6000.00' }])
  // Persistance : rechargée, la fiche montre le solde relu.
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  dlg = await ouvrir()
  await expect(dlg, 'rechargée : solde dû 6 000').toContainText(/6\s?000/)
})

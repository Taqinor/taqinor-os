// Preuves en direct ACNC, lot 9 (vague d'acceptation 6, runner GitHub, METHODE §C.4 point 7) : ACNC21, ACNC22, ACNC23,
// ACNC24, ACNC28, ACNC29 (PLAN_AUDIT_STOCK.md) — concurrence et rejeu du module Achats / Stock.
//   ACNC21 : BCF ouvert dans deux onglets (jeton de version) ; PATCH / DELETE croisés avec « Envoyer ».
//   ACNC22 : mouvement manuel et transfert rejouables sous la même Idempotency-Key ; l'écran garde la clé entre deux clics.
//   ACNC23 : réception, règlement et acompte rejoués sous la même clé ; plafond Σ acomptes ; « Facture déjà saisie ».
//   ACNC24 : variation de prix en masse rejouable sans cumul, tout-ou-rien, confirmée avant envoi.
//   ACNC28 : second retour fournisseur au-delà du reçu restant ⇒ 409.
//   ACNC29 : second « Envoyer » d'un BCF neuf réutilise le brouillon créé (moitié BCF ; la moitié « import OCR » exige
//            une clé fournisseur OCR, injouable sur le runner).
// Écartées de ce fichier : ACNC7 (acnc3.spec.js), ACNC42 et ACNC44 (déjà PASS dans acnc2.spec.js, enregistrement f4c345110).
//
// Règle de preuve : les gestes sont joués sous le rôle LIVRÉ « Directeur » (compte d'essai du registre) ; l'API est appelée
// sous ce rôle, les écrans par un navigateur à froid du même compte ; la base est relue par le shell Django.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { join } from 'node:path'
import { RACINE } from './_enregistrement.js'
import { groupe } from './_oracles.js'
import { py } from './_django.js'
import { lireJson } from '../helpers.js'
import { monter, API, T, marque, SOC, AUJ, note, acteur, navigateur, onglet } from './_acnc.js'

const etape = groupe('ACNC', ['ACNC21', 'ACNC22', 'ACNC23', 'ACNC24', 'ACNC28', 'ACNC29'])
monter()
const J = JSON.stringify
const apres = []
test.afterEach(async () => {
  for (const f of apres.splice(0)) await f().catch((e) => console.log(`[nettoyage] ${e.message}`))
})
const chemin = (u) => new URL(u).pathname
const STOCK = `${API}/stock`
const avecCle = (cle) => ({ 'Idempotency-Key': cle })

/** Fournisseur + produit + BCF (1 ligne) créés par le shell. */
const preparer = (m, { stock = 0, statut = 'envoye', qte = 10, pu = '1000', lignes2 = false } = {}) => py(`from decimal import Decimal as D
import datetime
from apps.stock.models import Fournisseur, Produit
from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC ${m}')
p = Produit.objects.create(company_id=${SOC}, nom='Panneau ACNC ${m}', sku='ACNC-${m}', prix_vente=D('2000'), prix_achat=D('${pu}'), quantite_stock=${stock})
b = BonCommandeFournisseur.objects.create(company_id=${SOC}, reference='BCF-ACNC-${m}', fournisseur=f, statut='${statut}', date_commande=datetime.date.today())
l = LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=p, quantite=${qte}, prix_achat_unitaire=D('${pu}'))
out = dict(f=f.pk, p=p.pk, b=b.pk, l=l.pk, ref=b.reference, nom=p.nom, fnom=f.nom, version=b.lock_version)
if ${lignes2 ? 'True' : 'False'}:
    p2 = Produit.objects.create(company_id=${SOC}, nom='Onduleur ACNC ${m}', sku='ACNC2-${m}', prix_vente=D('3000'), prix_achat=D('${pu}'), quantite_stock=0)
    l2 = LigneBonCommandeFournisseur.objects.create(bon_commande=b, produit=p2, quantite=3, prix_achat_unitaire=D('${pu}'))
    p3 = Produit.objects.create(company_id=${SOC}, nom='Batterie ACNC ${m}', sku='ACNC3-${m}', prix_vente=D('4000'), prix_achat=D('50'), quantite_stock=0)
    out.update(p2=p2.pk, l2=l2.pk, p3=p3.pk)
sortie(out)`)
/** Nettoyage tolérant : chaque suppression est essayée seule. */
const nettoyer = (m) => py(`from apps.stock.models import Fournisseur, Produit, MouvementStock, AcompteFournisseur
from apps.achats.models import (BonCommandeFournisseur, ReceptionFournisseur, FactureFournisseur, PaiementFournisseur, RetourFournisseur)
f = Fournisseur.objects.filter(nom__contains='ACNC ${m}')
qs = [PaiementFournisseur.objects.filter(facture__fournisseur__in=f), FactureFournisseur.objects.filter(fournisseur__in=f),
      AcompteFournisseur.objects.filter(bon_commande__fournisseur__in=f), RetourFournisseur.objects.filter(fournisseur__in=f),
      ReceptionFournisseur.objects.filter(bon_commande__fournisseur__in=f), BonCommandeFournisseur.objects.filter(fournisseur__in=f),
      MouvementStock.objects.filter(produit__nom__contains='ACNC ${m}'), Produit.objects.filter(nom__contains='ACNC ${m}'), f]
for q in qs:
    try: q.delete()
    except Exception as exc: print('nettoyage', exc)
sortie(True)`)
const stockDe = (id) => py(`from apps.stock.models import Produit
sortie(Produit.objects.get(pk=${id}).quantite_stock)`)
const lireBcf = async (ctx, id) => lireJson(await ctx.get(`${STOCK}/bons-commande-fournisseur/${id}/`, T), `BCF ${id}`)
const lignesPayload = (bcf) => bcf.lignes.map((l) => ({ id: l.id, produit: l.produit, quantite: l.quantite, prix_achat_unitaire: l.prix_achat_unitaire }))

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC21 — jeton de version du BCF : le second enregistrement est refusé et ne supprime pas la ligne du premier
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC21-api', ['ACNC21'], async ({ testInfo }) => {
  const { ctx } = await acteur(testInfo, 'acnc21a', 'Directeur')
  const m = marque()
  const x = await preparer(m, { statut: 'brouillon', qte: 5, lignes2: true })
  apres.push(() => nettoyer(m))
  // Given : brouillon P1 × 5, P2 × 3, lu par A et B à lock_version 0.
  const lu = await lireBcf(ctx, x.b)
  expect(lu.lock_version, 'Given : BCF lu à lock_version 0').toBe(0)
  expect(lu.lignes.length, 'Given : deux lignes (P1 × 5, P2 × 3)').toBe(2)
  const base = lignesPayload(lu)
  const url = `${STOCK}/bons-commande-fournisseur/${x.b}/`
  // A ajoute P3 × 7.
  const ra = await ctx.patch(url, { ...T, data: { lock_version: 0, lignes: [...base, { produit: x.p3, quantite: 7, prix_achat_unitaire: '50' }] } })
  expect(ra.status(), `A enregistre P3 × 7 : ${(await ra.text()).slice(0, 300)}`).toBe(200)
  // B (lu à 0) enregistre P2 à 4 : 409 `conflit_version` avec `actuel`, la ligne de A reste.
  const modifiee = base.map((l) => (l.id === x.l2 ? { ...l, quantite: 4 } : l))
  const rb = await ctx.patch(url, { ...T, data: { lock_version: 0, lignes: modifiee } })
  const jb = await rb.json().catch(() => ({}))
  expect([rb.status(), jb.code], `B périmé : ${J(jb).slice(0, 300)}`).toEqual([409, 'conflit_version'])
  expect(jb.actuel, 'le 409 porte `actuel` (la version à jour)').toBeTruthy()
  const apresB = await lireBcf(ctx, x.b)
  expect(apresB.lignes.length, 'persistance : trois lignes').toBe(3)
  expect(apresB.lignes.find((l) => l.produit === x.p3)?.quantite, 'P3 × 7 toujours en base').toBe(7)
  expect(apresB.lignes.find((l) => l.id === x.l2)?.quantite, 'P2 inchangée (3), pas 4').toBe(3)
  expect(apresB.statut, 'statut inchangé').toBe('brouillon')
  // BCF ENVOYÉ : un PATCH puis un DELETE tardifs rendent 409, BCF présent et ENVOYÉ.
  const y = await preparer(`${m}b`, { statut: 'brouillon', qte: 5 })
  apres.push(() => nettoyer(`${m}b`))
  await lireJson(await ctx.post(`${STOCK}/bons-commande-fournisseur/${y.b}/envoyer/`, T), 'envoyer')
  const p409 = await ctx.patch(`${STOCK}/bons-commande-fournisseur/${y.b}/`, { ...T, data: { note: 'X' } })
  expect(p409.status(), `PATCH d'un BCF envoyé : ${(await p409.text()).slice(0, 200)}`).toBe(409)
  const d409 = await ctx.delete(`${STOCK}/bons-commande-fournisseur/${y.b}/`, T)
  expect(d409.status(), `DELETE d'un BCF envoyé : ${(await d409.text()).slice(0, 200)}`).toBe(409)
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.filter(pk=${y.b}).first()
sortie(None if b is None else b.statut)`), 'BCF présent et ENVOYÉ').toBe('envoye')
  // Courses réelles « Envoyer » ∥ PATCH et « Envoyer » ∥ DELETE (3 passes) : jamais un BCF remis en brouillon ni supprimé envoyé.
  const observes = []
  for (let i = 0; i < 3; i += 1) {
    const z = await preparer(`${m}c${i}`, { statut: 'brouillon', qte: 5 })
    apres.push(() => nettoyer(`${m}c${i}`))
    const v = (await lireBcf(ctx, z.b)).lock_version
    const [env, pat] = await Promise.all([
      ctx.post(`${STOCK}/bons-commande-fournisseur/${z.b}/envoyer/`, T),
      ctx.patch(`${STOCK}/bons-commande-fournisseur/${z.b}/`, { ...T, data: { lock_version: v, note: `course ${i}` } }),
    ])
    const etat = await py(`from apps.achats.models import BonCommandeFournisseur
sortie(BonCommandeFournisseur.objects.get(pk=${z.b}).statut)`)
    observes.push(`envoyer ${env.status()} / patch ${pat.status()} => ${etat}`)
    expect([200, 409], `envoyer ∥ patch #${i}`).toContain(env.status())
    expect([200, 409], `patch ∥ envoyer #${i} : jamais un 5xx`).toContain(pat.status())
    if (env.status() === 200) expect(etat, `après envoyer ∥ patch #${i} : le BCF reste envoyé (jamais remis en brouillon)`).toBe('envoye')
    const w = await preparer(`${m}d${i}`, { statut: 'brouillon', qte: 5 })
    apres.push(() => nettoyer(`${m}d${i}`))
    const [env2, sup] = await Promise.all([
      ctx.post(`${STOCK}/bons-commande-fournisseur/${w.b}/envoyer/`, T),
      ctx.delete(`${STOCK}/bons-commande-fournisseur/${w.b}/`, T),
    ])
    const reste = await py(`from apps.achats.models import BonCommandeFournisseur
b = BonCommandeFournisseur.objects.filter(pk=${w.b}).first()
sortie(None if b is None else b.statut)`)
    observes.push(`envoyer ${env2.status()} / delete ${sup.status()} => ${reste}`)
    // Invariant : jamais « envoyé ET supprimé », jamais un envoyé effacé par le DELETE.
    expect(env2.status() === 200 && sup.status() < 300, `envoyer ∥ delete #${i} : jamais les deux`).toBe(false)
    if (env2.status() === 200) expect(reste, 'envoyé puis DELETE refusé : BCF présent et envoyé').toBe('envoye')
  }
  note(testInfo, 'courses observées', observes.join(' | '))
})

etape('PF9.4-ACNC21-ecran', ['ACNC21'], async ({ page, suivi, testInfo }) => {
  const { nom, ctx: api } = await acteur(testInfo, 'acnc21e', 'Directeur')
  const m = marque()
  const x = await preparer(m, { statut: 'brouillon', qte: 5, lignes2: true })
  apres.push(() => nettoyer(m))
  const rx = new RegExp(`/api/django/stock/bons-commande-fournisseur/${x.b}/$`)
  suivi.attendre(rx, 409) // le refus PROUVÉ par l'étape (onglet B périmé)
  const ctx = await navigateur(page, testInfo, nom)
  const pA = await onglet(page, suivi, ctx)
  const pB = suivi.surveiller(await ctx.newPage())
  const ouvrir = async (p) => {
    await p.goto('/stock/bons-commande-fournisseur')
    await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(x.ref, { timeout: 60_000 })
    await p.getByRole('row').filter({ hasText: x.ref }).getByText(x.ref).first().click({ timeout: 60_000 })
    const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-ref-fou') })
    await expect(dlg, 'fiche du BCF ouverte').toBeVisible({ timeout: 30_000 })
    await expect(dlg.getByRole('spinbutton').first(), 'lignes chargées').toBeVisible({ timeout: 30_000 })
    return dlg
  }
  const dB = await ouvrir(pB)
  const dA = await ouvrir(pA)
  // A : P1 × 5 devient × 6, « Enregistrer ».
  await dA.getByRole('spinbutton').nth(0).fill('6')
  const [ra] = await Promise.all([
    pA.waitForResponse((r) => r.request().method() === 'PATCH' && rx.test(chemin(r.url())), T),
    dA.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(ra.status(), `onglet A : ${(await ra.text()).slice(0, 200)}`).toBe(200)
  // B (ouvert avant A) : P2 × 3 devient × 4, « Enregistrer » ⇒ 409 + message à l'écran.
  await dB.getByRole('spinbutton').nth(2).fill('4')
  const [rb] = await Promise.all([
    pB.waitForResponse((r) => r.request().method() === 'PATCH' && rx.test(chemin(r.url())), T),
    dB.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  const jb = await rb.json().catch(() => ({}))
  expect([rb.status(), jb.code], `onglet B périmé : ${J(jb).slice(0, 200)}`).toEqual([409, 'conflit_version'])
  await expect(dB, 'l\'écran dit « modifié entre-temps »').toContainText('modifié entre-temps', { timeout: 30_000 })
  note(testInfo, 'message affiché', await dB.getByText(/modifié entre-temps/).first().innerText())
  // La version à jour (celle de A) remplace la saisie de B : P1 × 6 affiché, P2 × 3.
  await expect(dB.getByRole('spinbutton').nth(0), 'B recharge la version à jour (P1 × 6)').toHaveValue('6', { timeout: 30_000 })
  await expect(dB.getByRole('spinbutton').nth(2), 'B recharge la version à jour (P2 × 3)').toHaveValue('3')
  // Persistance : la base garde le travail de A, pas celui de B.
  const bcf = await lireBcf(api, x.b)
  expect(bcf.lignes.find((l) => l.id === x.l)?.quantite, 'base : P1 × 6 (A)').toBe(6)
  expect(bcf.lignes.find((l) => l.id === x.l2)?.quantite, 'base : P2 × 3 (la saisie de B n\'a pas écrasé)').toBe(3)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC22 — mouvement manuel et transfert : même clé ⇒ un seul objet
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC22-api', ['ACNC22'], async ({ page, testInfo }) => {
  const { ctx } = await acteur(testInfo, 'acnc22a', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 10, statut: 'brouillon' })
  apres.push(() => nettoyer(m))
  const corps = { produit: x.p, type_mouvement: 'entree', quantite: 5 }
  const r1 = await ctx.post(`${STOCK}/mouvements/`, { ...T, data: corps, headers: avecCle(`k1-${m}`) })
  const r2 = await ctx.post(`${STOCK}/mouvements/`, { ...T, data: corps, headers: avecCle(`k1-${m}`) })
  expect([r1.status(), r2.status()], `deux envois sous k1 : ${(await r2.text()).slice(0, 200)}`).toEqual([201, 201])
  const j1 = await r1.json()
  const j2 = await r2.json()
  expect(j2.id, 'le second envoi rend la réponse mémorisée (même id)').toBe(j1.id)
  expect(await py(`from apps.stock.models import MouvementStock
sortie(MouvementStock.objects.filter(produit_id=${x.p}).count())`), 'UN mouvement en base').toBe(1)
  expect(await stockDe(x.p), 'stock 10 + 5 = 15 (pas 20)').toBe(15)
  const r3 = await ctx.post(`${STOCK}/mouvements/`, { ...T, data: { ...corps, quantite: 6 }, headers: avecCle(`k1-${m}`) })
  const j3 = await r3.json().catch(() => ({}))
  expect(r3.status(), `corps différent sous la même clé : ${J(j3)}`).toBe(409)
  expect(J(j3), 'code d\'idempotence').toMatch(/idempotency/i)
  expect(await stockDe(x.p), 'après le 409 : toujours 15').toBe(15)
  // Transfert : deux fois sous `k2` ⇒ un transfert, 2 en camionnette.
  const emp = await py(`from apps.stock.models import EmplacementStock
from apps.stock.services import ensure_emplacements
from authentication.models import Company
co = Company.objects.get(pk=${SOC})
ensure_emplacements(co)
sortie(dict(principal=EmplacementStock.objects.get(company=co, is_principal=True).pk, camionnette=EmplacementStock.objects.get(company=co, nom='Camionnette').pk))`)
  const ct = { produit: x.p, source: emp.principal, destination: emp.camionnette, quantite: 2 }
  const t1 = await ctx.post(`${STOCK}/transferts/`, { ...T, data: ct, headers: avecCle(`k2-${m}`) })
  const t2 = await ctx.post(`${STOCK}/transferts/`, { ...T, data: ct, headers: avecCle(`k2-${m}`) })
  expect([t1.status(), t2.status()], `deux transferts sous k2 : ${(await t2.text()).slice(0, 200)}`).toEqual([201, 201])
  expect((await t2.json()).id, 'transfert : même id rejoué').toBe((await t1.json()).id)
  expect(await py(`from apps.stock.models import TransfertStock, StockEmplacement
sortie([TransfertStock.objects.filter(produit_id=${x.p}).count(), StockEmplacement.objects.get(produit_id=${x.p}, emplacement_id=${emp.camionnette}).quantite])`),
  'UN transfert, 2 en camionnette').toEqual([1, 2])
  await page.goto('/stock/mouvements')
  await expect(page.locator('body')).toBeVisible()
})

etape('PF9.4-ACNC22-ecran-mouvement', ['ACNC22'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc22e', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 10, statut: 'brouillon' })
  apres.push(() => nettoyer(m))
  const rx = /\/api\/django\/stock\/mouvements\/$/
  suivi.attendre(rx, 'reseau')
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null }) })
  await p.goto('/stock/mouvements')
  await p.getByRole('button', { name: 'Saisir mouvement' }).click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Saisir un mouvement de stock' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#mv-produit').click()
  await p.getByRole('option', { name: new RegExp(x.nom) }).click()
  await dlg.locator('#mv-quantite').fill('5')
  await dlg.locator('#mv-reference').fill(`ACNC22-${m}`)
  // Réponse du 1er POST perdue APRÈS passage au serveur ; le second passe.
  let coupe = true
  await p.route((u) => rx.test(u.pathname), async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.fallback()
  })
  const relue = p.waitForResponse((r) => r.request().method() === 'GET' && /\/api\/django\/stock\/produits\//.test(chemin(r.url())), T)
  await dlg.getByRole('button', { name: 'Enregistrer le mouvement' }).click()
  await relue // après l'échec sans réponse, l'écran RELIT le stock
  await expect(dlg, 'le dialogue reste ouvert après l\'échec').toBeVisible()
  expect(await stockDe(x.p), 'le serveur a appliqué le 1er envoi (10 + 5)').toBe(15)
  expect(await dlg.locator('#mv-quantite').inputValue(), 'la saisie est gardée (5)').toBe('5')
  // Second clic : MÊME clé ⇒ réponse rejouée, aucun second mouvement.
  const [r2] = await Promise.all([
    p.waitForResponse((r) => r.request().method() === 'POST' && rx.test(chemin(r.url())), T),
    dlg.getByRole('button', { name: 'Enregistrer le mouvement' }).click(),
  ])
  expect(r2.status(), `second clic : ${(await r2.text()).slice(0, 200)}`).toBe(201)
  await expect(dlg, 'dialogue refermé au succès').toBeHidden({ timeout: 30_000 })
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0].cle, 'une clé d\'idempotence envoyée').toBeTruthy()
  expect(envois[1].cle, 'MÊME clé au second clic').toBe(envois[0].cle)
  expect(await py(`from apps.stock.models import MouvementStock
sortie(MouvementStock.objects.filter(produit_id=${x.p}, reference='ACNC22-${m}').count())`), 'UN mouvement en base').toBe(1)
  expect(await stockDe(x.p), 'stock 15 (jamais 20)').toBe(15)
  await p.unrouteAll({ behavior: 'ignoreErrors' })
  await p.reload()
  await expect(p.locator('[aria-label="Mouvements de stock"]').getByRole('row').filter({ hasText: `ACNC22-${m}` }),
    'rechargé : le mouvement, une ligne').toHaveCount(1, { timeout: 60_000 })
})

etape('PF9.4-ACNC22-ecran-transfert', ['ACNC22'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc22t', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 10, statut: 'brouillon' })
  apres.push(() => nettoyer(m))
  const emp = await py(`from apps.stock.models import EmplacementStock
from apps.stock.services import ensure_emplacements
from authentication.models import Company
co = Company.objects.get(pk=${SOC})
ensure_emplacements(co)
sortie(dict(principal=EmplacementStock.objects.get(company=co, is_principal=True).pk, camionnette=EmplacementStock.objects.get(company=co, nom='Camionnette').pk,
  nprincipal=EmplacementStock.objects.get(company=co, is_principal=True).nom))`)
  const rx = /\/api\/django\/stock\/transferts\/$/
  suivi.attendre(rx, 'reseau')
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null }) })
  await p.goto('/stock')
  await p.getByRole('button', { name: /Transférer/ }).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Transférer du stock entre emplacements' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#tr-produit').click()
  await p.getByRole('option', { name: new RegExp(x.nom) }).click()
  await dlg.locator('#tr-src').click()
  await p.getByRole('option', { name: new RegExp(emp.nprincipal) }).first().click()
  await dlg.locator('#tr-dst').click()
  await p.getByRole('option', { name: /Camionnette/ }).first().click()
  await dlg.locator('#tr-qte').fill('2')
  let coupe = true
  await p.route((u) => rx.test(u.pathname), async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.fallback()
  })
  const relue = p.waitForResponse((r) => r.request().method() === 'GET' && /\/stock\/produits\/\d+\/emplacements\//.test(chemin(r.url())), T)
  await dlg.getByRole('button', { name: /^Transférer$/ }).click()
  await relue // l'écran relit la ventilation après l'échec sans réponse
  expect(await py(`from apps.stock.models import TransfertStock
sortie(TransfertStock.objects.filter(produit_id=${x.p}).count())`), 'le serveur a appliqué le 1er envoi').toBe(1)
  const [r2] = await Promise.all([
    p.waitForResponse((r) => r.request().method() === 'POST' && rx.test(chemin(r.url())), T),
    dlg.getByRole('button', { name: /^Transférer$/ }).click(),
  ])
  expect(r2.status(), `second clic : ${(await r2.text()).slice(0, 200)}`).toBe(201)
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0].cle, 'une clé envoyée').toBeTruthy()
  expect(envois[1].cle, 'MÊME clé au second clic').toBe(envois[0].cle)
  expect(await py(`from apps.stock.models import TransfertStock, StockEmplacement
sortie([TransfertStock.objects.filter(produit_id=${x.p}).count(), StockEmplacement.objects.get(produit_id=${x.p}, emplacement_id=${emp.camionnette}).quantite])`),
  'UN transfert, 2 en camionnette (jamais 4)').toEqual([1, 2])
  await p.unrouteAll({ behavior: 'ignoreErrors' })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC23 — réception, règlement et acompte rejoués sous la même clé ; plafond Σ acomptes ; « Facture déjà saisie »
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC23-api', ['ACNC23'], async ({ page, testInfo }) => {
  const { ctx } = await acteur(testInfo, 'acnc23a', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 0, qte: 10, pu: '1000' })
  apres.push(() => nettoyer(m))
  const ff = await py(`import datetime
from decimal import Decimal as D
from apps.achats.models import FactureFournisseur
f = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC23-${m}', fournisseur_id=${x.f}, date_facture=datetime.date.today(),
    montant_ht=D('8333.33'), montant_tva=D('1666.67'), montant_ttc=D('10000'))
sortie(dict(id=f.pk, solde=str(f.solde_du)))`)
  expect(Number(ff.solde), 'Given : facture de 10 000 à payer').toBe(10000)
  // Réception partielle (5 sur 10) POSTée deux fois sous la même clé.
  const rec = { receptions: [{ ligne: x.l, quantite: 5 }] }
  const a1 = await ctx.post(`${STOCK}/bons-commande-fournisseur/${x.b}/recevoir/`, { ...T, data: rec, headers: avecCle(`rec-${m}`) })
  const a2 = await ctx.post(`${STOCK}/bons-commande-fournisseur/${x.b}/recevoir/`, { ...T, data: rec, headers: avecCle(`rec-${m}`) })
  expect([a1.status(), a2.status()], `recevoir ×2 : ${(await a2.text()).slice(0, 200)}`).toEqual([200, 200])
  const e1 = await py(`from apps.achats.models import ReceptionFournisseur, LigneBonCommandeFournisseur, BonCommandeFournisseur
l = LigneBonCommandeFournisseur.objects.get(pk=${x.l})
sortie(dict(receptions=ReceptionFournisseur.objects.filter(bon_commande_id=${x.b}).count(), recue=l.quantite_recue, statut=BonCommandeFournisseur.objects.get(pk=${x.b}).statut))`)
  expect(e1, 'UNE réception, 5 reçus, BCF encore envoyé').toEqual({ receptions: 1, recue: 5, statut: 'envoye' })
  expect(await stockDe(x.p), 'stock + 5 (pas + 10) ; reste dû 5').toBe(5)
  // Règlement de 3 000 POSTé deux fois sous la même clé.
  const pay = { montant: '3000', date_paiement: AUJ() }
  const p1 = await ctx.post(`${STOCK}/factures-fournisseur/${ff.id}/paiements/`, { ...T, data: pay, headers: avecCle(`pay-${m}`) })
  const p2 = await ctx.post(`${STOCK}/factures-fournisseur/${ff.id}/paiements/`, { ...T, data: pay, headers: avecCle(`pay-${m}`) })
  expect([p1.status(), p2.status()], `paiements ×2 : ${(await p1.text()).slice(0, 200)} | ${(await p2.text()).slice(0, 200)}`).toEqual([201, 201])
  expect(await py(`from apps.achats.models import FactureFournisseur, PaiementFournisseur
f = FactureFournisseur.objects.get(pk=${ff.id})
sortie({'reglements': [str(p.montant) for p in PaiementFournisseur.objects.filter(facture=f)], 'solde': str(f.solde_du)})`),
  'UN règlement de 3 000, solde 7 000').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // Acompte de 2 000 POSTé deux fois sous la même clé ; puis 11 000 (Σ > total TTC du BCF) ⇒ 409.
  const ac = { bon_commande: x.b, montant: '2000', date_versement: AUJ() }
  const c1 = await ctx.post(`${STOCK}/acomptes-fournisseur/`, { ...T, data: ac, headers: avecCle(`ac-${m}`) })
  const c2 = await ctx.post(`${STOCK}/acomptes-fournisseur/`, { ...T, data: ac, headers: avecCle(`ac-${m}`) })
  expect([c1.status(), c2.status()], `acomptes ×2 : ${(await c2.text()).slice(0, 200)}`).toEqual([201, 201])
  const c3 = await ctx.post(`${STOCK}/acomptes-fournisseur/`, { ...T, data: { ...ac, montant: '11000' } })
  const j3 = await c3.json().catch(() => ({}))
  expect(c3.status(), `acompte au-delà du total : ${J(j3)}`).toBe(409)
  expect(J(j3), 'message du plafond').toContain('total TTC du BCF')
  expect(await py(`from apps.stock.models import AcompteFournisseur
sortie(AcompteFournisseur.objects.filter(bon_commande_id=${x.b}).count())`), 'UN acompte, rien de créé par le 409').toBe(1)
  // Facture au même ref_fournisseur : le serveur rend `doublon_warning` (affiché à l'écran par le pas suivant).
  const fa = { fournisseur: x.f, ref_fournisseur: `RF-${m}`, date_facture: AUJ(), montant_ht: 1000, montant_tva: 200, montant_ttc: 1200 }
  const f1 = await ctx.post(`${STOCK}/factures-fournisseur/`, { ...T, data: fa, headers: avecCle(`fa1-${m}`) })
  expect(f1.status(), `1re facture : ${(await f1.text()).slice(0, 200)}`).toBe(201)
  const premiere = await f1.json()
  const f2 = await ctx.post(`${STOCK}/factures-fournisseur/`, { ...T, data: fa, headers: avecCle(`fa2-${m}`) })
  expect(f2.status(), `2e facture même ref : ${(await f2.text()).slice(0, 200)}`).toBe(201)
  const j2 = await f2.json()
  expect((j2.doublon_warning || []).map((d) => d.reference), 'doublon_warning cite la 1re facture').toContain(premiere.reference)
  await page.goto('/stock/factures-fournisseur')
})

etape('PF9.4-ACNC23-ecran-doublon', ['ACNC23'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc23e', 'Directeur')
  const m = marque()
  const x = await preparer(m, { statut: 'brouillon' })
  apres.push(() => nettoyer(m))
  const ff = await py(`import datetime
from decimal import Decimal as D
from apps.achats.models import FactureFournisseur
f = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC23E-${m}', ref_fournisseur='RFE-${m}', fournisseur_id=${x.f},
    date_facture=datetime.date.today(), montant_ht=D('1000'), montant_tva=D('200'), montant_ttc=D('1200'))
sortie(dict(id=f.pk, ref=f.reference))`)
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  await p.goto('/stock/factures-fournisseur')
  await p.getByRole('button', { name: /Nouvelle facture/ }).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Nouvelle facture fournisseur' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#ff-fou').click()
  await p.getByRole('option', { name: x.fnom }).click()
  await dlg.locator('#ff-ref').fill(`RFE-${m}`)
  await dlg.locator('#ff-datef').fill(AUJ())
  await dlg.locator('#ff-ht').fill('1000')
  await dlg.locator('#ff-tva').fill('200')
  await expect(dlg.locator('#ff-ttc'), 'TTC calculé').toHaveValue('1200')
  const [r] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && /\/api\/django\/stock\/factures-fournisseur\/$/.test(chemin(q.url())), T),
    dlg.getByRole('button', { name: 'Enregistrer', exact: true }).click(),
  ])
  expect(r.status(), `création : ${(await r.text()).slice(0, 200)}`).toBe(201)
  await expect(dlg, 'dialogue refermé').toBeHidden({ timeout: 30_000 })
  const msg = p.getByText(new RegExp(`Facture déjà saisie : ${ff.ref}`))
  await expect(msg, '« Facture déjà saisie : <référence> » affiché').toBeVisible({ timeout: 30_000 })
  note(testInfo, 'message affiché', await msg.first().innerText())
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC24 — variation de prix en masse : rejouable sans cumul, tout-ou-rien, confirmée avant envoi
// ════════════════════════════════════════════════════════════════════════════════════════════
const deuxProduits = (m, a = '1000', b = '2000') => py(`from decimal import Decimal as D
from apps.stock.models import Produit
p1 = Produit.objects.create(company_id=${SOC}, nom='ACNC24 Alpha ${m}', sku='ACNC24A-${m}', prix_vente=D('${a}'), prix_achat=D('500'), quantite_stock=1)
p2 = Produit.objects.create(company_id=${SOC}, nom='ACNC24 Beta ${m}', sku='ACNC24B-${m}', prix_vente=D('${b}'), prix_achat=D('800'), quantite_stock=1)
sortie(dict(p1=p1.pk, p2=p2.pk, n1=p1.nom, n2=p2.nom))`)
const prixDe = (x) => py(`from apps.stock.models import Produit
sortie([str(Produit.objects.get(pk=${x.p1}).prix_vente), str(Produit.objects.get(pk=${x.p2}).prix_vente)])`)
const nettoyerProduits = (m) => py(`from apps.stock.models import Produit
try: Produit.objects.filter(nom__contains='ACNC24 ').filter(nom__endswith='${m}').delete()
except Exception as exc: print('nettoyage', exc)
sortie(True)`)

etape('PF9.4-ACNC24-api', ['ACNC24'], async ({ testInfo }) => {
  const { ctx } = await acteur(testInfo, 'acnc24a', 'Directeur')
  const m = marque()
  const x = await deuxProduits(m)
  apres.push(async () => {
    await py(`from django.db import connection
from apps.stock.models import Produit
with connection.cursor() as c: c.execute('ALTER TABLE %s DROP CONSTRAINT IF EXISTS acnc24_${m}' % Produit._meta.db_table)
sortie(True)`)
    await nettoyerProduits(m)
  })
  const bulk = (cle, valeur = '10') => ctx.post(`${STOCK}/produits/bulk/`, {
    ...T, data: { action: 'set_price', ids: [x.p1, x.p2], mode: 'percent', valeur }, headers: avecCle(cle),
  })
  const r1 = await bulk(`b1-${m}`)
  const j1 = await r1.json().catch(() => ({}))
  expect([r1.status(), j1.updated], `1er envoi : ${J(j1)}`).toEqual([200, 2])
  expect(await prixDe(x), 'après le 1er envoi : 1 100 et 2 200').toEqual(['1100.00', '2200.00'])
  const r2 = await bulk(`b1-${m}`)
  expect(r2.status(), `2e envoi sous la même clé : ${(await r2.text()).slice(0, 200)}`).toBe(200)
  expect(await prixDe(x), 'après le rejeu : TOUJOURS 1 100 et 2 200 (aucun cumul à 1 210)').toEqual(['1100.00', '2200.00'])
  // Troisième envoi (AUTRE clé) dont la sauvegarde du 2e produit échoue : aucun prix ne change.
  // Même requête que `apply_product_bulk` (select_for_update, filtre société + ids) : l'ordre de traitement réel du service.
  const ordre = await py(`from django.db import transaction
from apps.stock.models import Produit
with transaction.atomic():
    ids = [p.pk for p in Produit.objects.select_for_update().filter(company_id=${SOC}, id__in=[${x.p1}, ${x.p2}])]
sortie(ids)`)
  const dernier = ordre[ordre.length - 1]
  // Échec injecté : le DERNIER produit de la boucle refuse tout changement de prix (contrainte CHECK posée puis retirée).
  await py(`from django.db import connection
from apps.stock.models import Produit
cur = Produit.objects.get(pk=${dernier}).prix_vente
with connection.cursor() as c:
    c.execute('ALTER TABLE %s ADD CONSTRAINT acnc24_${m} CHECK (id <> ${dernier} OR prix_vente <= %s)' % (Produit._meta.db_table, cur))
sortie(True)`)
  const r3 = await bulk(`b3-${m}`)
  expect(r3.status(), `3e envoi (échec injecté sur le produit ${dernier}) : ${(await r3.text()).slice(0, 120)}`).toBeGreaterThanOrEqual(500)
  expect(await prixDe(x), 'après la panne à mi-boucle : AUCUN prix changé (1 100 et 2 200)').toEqual(['1100.00', '2200.00'])
  await py(`from django.db import connection
from apps.stock.models import Produit
with connection.cursor() as c: c.execute('ALTER TABLE %s DROP CONSTRAINT IF EXISTS acnc24_${m}' % Produit._meta.db_table)
sortie(True)`)
  const r4 = await bulk(`b4-${m}`)
  expect(r4.status(), 'après réparation, un envoi neuf s\'applique').toBe(200)
  expect(await prixDe(x), 'envoi neuf : 1 210 et 2 420').toEqual(['1210.00', '2420.00'])
  // Sonde C-ACNC-006 REJOUÉE (hôte) : elle n'extrait que `apply_product_bulk` avec un ORM factice ; le `transaction.atomic`
  // est posé dans la VUE (unique appelant) : son verdict est donc nommé, jamais compté comme preuve.
  const sonde = spawnSync(process.env.E2E_PYTHON || 'python', ['-I', '-c',
    'import runpy, sys, json; ns = runpy.run_path(sys.argv[1]); print("@@S" + json.dumps(ns["sonde"](), default=str))',
    join(RACINE, 'docs', 'audits', 'sondes', 'ACNC', 'C-ACNC-006.py')],
  { cwd: RACINE, encoding: 'utf8', maxBuffer: 20_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  const ligne = (sonde.stdout || '').split('\n').find((l) => l.startsWith('@@S'))
  const verdictSonde = ligne ? J(JSON.parse(ligne.slice(3))).slice(0, 500) : `sonde illisible : ${(sonde.stderr || '').slice(-300)}`
  console.log(`[ACNC24] sonde C-ACNC-006 rejouée : ${verdictSonde}`)
  note(testInfo, 'sonde C-ACNC-006 rejouée', verdictSonde)
}, {
  ecart: {
    base: 'FAIL',
    raison: 'sonde insensible : atomic posé dans la vue, unique appelant ; tout-ou-rien prouvé par la panne déterministe sur la vraie route '
      + '(C-ACNC-006 rejouée : repro:true car elle extrait `apply_product_bulk` avec un ORM factice, sans la vue qui porte `transaction.atomic`)',
  },
})

etape('PF9.4-ACNC24-ecran', ['ACNC24'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc24e', 'Directeur')
  const m = marque()
  const x = await deuxProduits(m)
  apres.push(() => nettoyerProduits(m))
  const rx = /\/api\/django\/stock\/produits\/bulk\/$/
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null, corps: q.postDataJSON() }) })
  await p.goto('/stock')
  await p.locator('input[type="search"]').first().fill(m, { timeout: 60_000 })
  await p.getByRole('checkbox', { name: `Sélectionner ${x.n1}`, exact: true }).click({ timeout: 60_000 })
  await p.getByRole('checkbox', { name: `Sélectionner ${x.n2}`, exact: true }).click()
  const barre = p.getByRole('region', { name: 'Actions produits en masse' })
  await expect(barre, 'barre d\'actions en masse').toBeVisible({ timeout: 30_000 })
  await barre.getByText('Prix', { exact: true }).first().click()
  await barre.getByPlaceholder('ex. 10 ou -5').fill('10')
  await barre.getByRole('button', { name: 'Appliquer', exact: true }).click()
  // « Appliquer » ouvre une confirmation : nombre de produits + exemple avant → après ; RIEN n'est encore envoyé.
  const alerte = barre.getByRole('alert')
  await expect(alerte, 'confirmation affichée').toBeVisible({ timeout: 15_000 })
  const espace = '[\\s\\u202f\\u00a0]?'
  await expect(alerte).toHaveText(new RegExp(`^2 produits — ex\\. (1${espace}000,00 → 1${espace}100,00|2${espace}000,00 → 2${espace}200,00)`))
  note(testInfo, 'confirmation affichée', await alerte.innerText())
  expect(envois.length, 'avant « Confirmer » : aucun envoi').toBe(0)
  expect(await prixDe(x), 'avant « Confirmer » : prix inchangés').toEqual(['1000.00', '2000.00'])
  const [r] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(chemin(q.url())), T),
    alerte.getByRole('button', { name: 'Confirmer' }).click(),
  ])
  expect(r.status(), `confirmé : ${(await r.text()).slice(0, 200)}`).toBe(200)
  expect(envois.length, 'UN envoi').toBe(1)
  expect(envois[0].cle, 'clé d\'idempotence envoyée').toBeTruthy()
  expect(await prixDe(x), 'après « Confirmer » : 1 100 et 2 200').toEqual(['1100.00', '2200.00'])
  // La valeur est vidée au succès : rouvrir « Prix » montre un champ vide.
  await barre.getByText('Prix', { exact: true }).first().click()
  await expect(barre.getByPlaceholder('ex. 10 ou -5'), 'valeur vidée au succès').toHaveValue('')
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC28 — second retour fournisseur au-delà du reçu restant ⇒ 409, rien ne sort
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC28-api', ['ACNC28'], async ({ page, testInfo }) => {
  const { ctx } = await acteur(testInfo, 'acnc28', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 0, qte: 10, pu: '100' })
  apres.push(() => nettoyer(m))
  // Given : BCF de 10, 5 reçus (stock 5), premier retour de 5 validé (reçu 0, stock 0).
  const rec = await ctx.post(`${STOCK}/bons-commande-fournisseur/${x.b}/recevoir/`, { ...T, data: { receptions: [{ ligne: x.l, quantite: 5 }] }, headers: avecCle(`rec28-${m}`) })
  expect(rec.status(), `réception de 5 : ${(await rec.text()).slice(0, 200)}`).toBe(200)
  expect(await stockDe(x.p), 'Given : stock 5').toBe(5)
  const retour = async () => lireJson(await ctx.post(`${STOCK}/retours-fournisseur/`, {
    ...T, data: { fournisseur: x.f, bon_commande: x.b, motif: 'ACNC28', lignes: [{ produit: x.p, quantite: 5, motif: 'Défectueux' }] },
  }), 'retour')
  const r1 = await retour()
  const v1 = await ctx.post(`${STOCK}/retours-fournisseur/${r1.id}/valider/`, T)
  expect(v1.status(), `1er retour validé : ${(await v1.text()).slice(0, 200)}`).toBe(200)
  expect(await py(`from apps.achats.models import LigneBonCommandeFournisseur
from apps.stock.models import Produit
sortie([LigneBonCommandeFournisseur.objects.get(pk=${x.l}).quantite_recue, Produit.objects.get(pk=${x.p}).quantite_stock])`),
  'Given : reçu ramené à 0, stock 0').toEqual([0, 0])
  // When : un second retour de 5 est créé puis validé.
  const r2 = await retour()
  const v2 = await ctx.post(`${STOCK}/retours-fournisseur/${r2.id}/valider/`, T)
  const j2 = await v2.json().catch(() => ({}))
  expect(v2.status(), `2e validation : ${J(j2)}`).toBe(409)
  expect(J(j2), 'message nommé').toMatch(/quantité reçue restante \(0\)/i)
  const etat = await py(`from apps.stock.models import Produit, MouvementStock
from apps.achats.models import RetourFournisseur
sortie(dict(stock=Produit.objects.get(pk=${x.p}).quantite_stock, sorties=MouvementStock.objects.filter(produit_id=${x.p}, type_mouvement='sortie').count(),
  statut=RetourFournisseur.objects.get(pk=${r2.id}).statut))`)
  expect(etat, 'persistance : stock 0, UNE seule sortie (le 1er retour), 2nd retour brouillon').toEqual({ stock: 0, sorties: 1, statut: 'brouillon' })
  await page.goto('/stock/retours-fournisseur')
  await expect(page.locator('body')).toBeVisible()
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC29 — « Envoyer » d'un BCF neuf : le second clic réutilise le brouillon créé (moitié BCF ; l'import OCR est injouable)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC29-ecran-bcf', ['ACNC29'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc29', 'Directeur')
  const m = marque()
  const x = await py(`from decimal import Decimal as D
from apps.stock.models import Fournisseur, Produit
from apps.installations.models import SeuilApprobationBCF
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC ${m}')
p = Produit.objects.create(company_id=${SOC}, nom='Panneau ACNC ${m}', sku='ACNC29-${m}', prix_vente=D('2000'), prix_achat=D('60'), quantite_stock=0)
s = SeuilApprobationBCF.objects.create(company_id=${SOC}, seuil_responsable=D('100'), actif=True)
sortie(dict(f=f.pk, p=p.pk, s=s.pk, fnom=f.nom, nom=p.nom))`)
  apres.push(async () => {
    await py(`from apps.installations.models import SeuilApprobationBCF
SeuilApprobationBCF.objects.filter(pk=${x.s}).delete()
sortie(True)`)
    await nettoyer(m)
  })
  const base = /\/api\/django\/stock\/bons-commande-fournisseur\/$/
  const sur = /\/api\/django\/stock\/bons-commande-fournisseur\/(\d+)\/$/
  const envoyer = /\/api\/django\/stock\/bons-commande-fournisseur\/(\d+)\/envoyer\/$/
  suivi.attendre(envoyer, 409) // refus DÉTERMINISTE du seuil d'approbation
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const appels = []
  p.on('request', (q) => {
    const c = chemin(q.url())
    if (q.method() === 'POST' && base.test(c)) appels.push({ t: 'create' })
    else if (q.method() === 'PATCH' && sur.test(c)) appels.push({ t: 'update', id: Number(c.match(sur)[1]) })
    else if (q.method() === 'POST' && envoyer.test(c)) appels.push({ t: 'envoyer', id: Number(c.match(envoyer)[1]) })
  })
  await p.goto('/stock/bons-commande-fournisseur')
  await p.getByRole('button', { name: /Nouveau bon de commande/ }).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: 'Nouveau bon de commande fournisseur' })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.locator('#bcf-fou').click()
  await p.getByRole('option', { name: x.fnom }).click()
  if (await dlg.getByRole('button', { name: '— Produit —' }).count() === 0) await dlg.getByRole('button', { name: /Ajouter une ligne/ }).click()
  await dlg.getByRole('button', { name: '— Produit —' }).first().click()
  await p.getByPlaceholder(/Chercher un produit à commander/).fill(x.nom)
  await p.getByRole('option', { name: new RegExp(x.nom) }).first().click()
  await dlg.getByRole('spinbutton').nth(0).fill('10')
  await dlg.getByRole('spinbutton').nth(1).fill('60')
  const tenter = async () => {
    const [re] = await Promise.all([
      p.waitForResponse((q) => q.request().method() === 'POST' && envoyer.test(chemin(q.url())), T),
      dlg.getByRole('button', { name: 'Envoyer au fournisseur' }).click(),
    ])
    return { s: re.status(), b: await re.json().catch(() => ({})) }
  }
  const SEUIL = /dépasse le seuil d.approbation/
  const e1 = await tenter()
  expect([e1.s, e1.b.detail], '1er « Envoyer » : refus du seuil d\'approbation').toEqual([409, expect.stringMatching(SEUIL)])
  await expect(dlg, 'message du seuil affiché').toContainText(SEUIL, { timeout: 30_000 })
  const e2 = await tenter()
  expect([e2.s, e2.b.detail], '2e « Envoyer » : de nouveau le seuil (409 déterministe)').toEqual([409, expect.stringMatching(SEUIL)])
  note(testInfo, 'appels', J(appels))
  // UN SEUL create ; le second clic appelle update PUIS envoyer sur le MÊME id.
  expect(appels.filter((a) => a.t === 'create').length, 'UN seul create (jamais un second brouillon)').toBe(1)
  const envois = appels.filter((a) => a.t === 'envoyer')
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[1].id, '2e envoi sur le MÊME id').toBe(envois[0].id)
  const maj = appels.filter((a) => a.t === 'update')
  expect(maj.length, 'le 2e clic met à jour le brouillon existant').toBeGreaterThanOrEqual(1)
  expect(new Set(maj.map((a) => a.id)), 'la mise à jour vise ce même brouillon').toEqual(new Set([envois[0].id]))
  expect(await py(`from apps.achats.models import BonCommandeFournisseur
sortie([[b.statut, b.lignes.count()] for b in BonCommandeFournisseur.objects.filter(lignes__produit_id=${x.p}).distinct()])`),
  'persistance : UN seul BCF, brouillon, 1 ligne').toEqual([['brouillon', 1]])
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// Round 2 — preuves À L'ÉCRAN avec réponse COUPÉE après passage au serveur (ACNC23, ACNC24, ACNC28)
// ════════════════════════════════════════════════════════════════════════════════════════════
const ouvrirBcf = async (p, ref) => {
  await p.goto('/stock/bons-commande-fournisseur')
  await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(ref, { timeout: 60_000 })
  await p.getByRole('row').filter({ hasText: ref }).getByText(ref).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ has: p.locator('#bcf-ref-fou') })
  await expect(dlg, 'fiche du BCF ouverte').toBeVisible({ timeout: 30_000 })
  return dlg
}
/** Coupe la réponse du 1er POST qui matche `rx` APRÈS passage au serveur ; les suivants passent. */
const coupePremier = async (p, rx) => {
  let coupe = true
  await p.route((u) => rx.test(u.pathname), async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.fallback()
  })
}

etape('PF9.4-ACNC23-ecran-reception', ['ACNC23'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc23r', 'Directeur')
  const m = marque()
  const x = await preparer(m, { stock: 0, qte: 10, pu: '1000' })
  apres.push(() => nettoyer(m))
  const rx = new RegExp(`/api/django/stock/bons-commande-fournisseur/${x.b}/recevoir/$`)
  suivi.attendre(rx, 'reseau')
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null }) })
  const dlg = await ouvrirBcf(p, x.ref)
  const saisie = dlg.locator('input[placeholder^="/"]').first()
  await expect(saisie, 'champ « À recevoir »').toBeVisible({ timeout: 30_000 })
  await saisie.fill('5')
  await coupePremier(p, rx)
  await dlg.getByRole('button', { name: 'Recevoir les quantités' }).click()
  await expect.poll(() => envois.length, { message: 'premier envoi parti', timeout: 30_000 }).toBe(1)
  await expect.poll(() => py(`from apps.achats.models import ReceptionFournisseur
sortie(ReceptionFournisseur.objects.filter(bon_commande_id=${x.b}).count())`), { message: 'le serveur a appliqué la réception', timeout: 30_000 }).toBe(1)
  await expect(dlg, 'le dialogue reste ouvert avec l\'échec dit').toContainText(/réception a échoué|réponse|abouti/i, { timeout: 30_000 })
  await expect(saisie, 'la saisie est gardée (5)').toHaveValue('5')
  const [r2] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(chemin(q.url())), T),
    dlg.getByRole('button', { name: 'Recevoir les quantités' }).click(),
  ])
  expect(r2.status(), `second clic : ${(await r2.text()).slice(0, 200)}`).toBe(200)
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0].cle, 'une clé envoyée').toBeTruthy()
  expect(envois[1].cle, 'MÊME clé au second clic').toBe(envois[0].cle)
  const e = await py(`from apps.achats.models import ReceptionFournisseur, LigneBonCommandeFournisseur
from apps.stock.models import Produit
sortie(dict(rec=ReceptionFournisseur.objects.filter(bon_commande_id=${x.b}).count(), recue=LigneBonCommandeFournisseur.objects.get(pk=${x.l}).quantite_recue, stock=Produit.objects.get(pk=${x.p}).quantite_stock))`)
  expect(e, 'UNE réception (REC), 5 reçus, stock 5 (jamais 10)').toEqual({ rec: 1, recue: 5, stock: 5 })
  await p.unrouteAll({ behavior: 'ignoreErrors' })
})

etape('PF9.4-ACNC24-ecran-coupure', ['ACNC24'], async ({ page, suivi, testInfo }) => {
  const { nom } = await acteur(testInfo, 'acnc24c', 'Directeur')
  const m = marque()
  const x = await deuxProduits(m)
  apres.push(() => nettoyerProduits(m))
  const rx = /\/api\/django\/stock\/produits\/bulk\/$/
  suivi.attendre(rx, 'reseau')
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null }) })
  await p.goto('/stock')
  await p.locator('input[type="search"]').first().fill(m, { timeout: 60_000 })
  await p.getByRole('checkbox', { name: `Sélectionner ${x.n1}`, exact: true }).click({ timeout: 60_000 })
  await p.getByRole('checkbox', { name: `Sélectionner ${x.n2}`, exact: true }).click()
  const barre = p.getByRole('region', { name: 'Actions produits en masse' })
  await expect(barre).toBeVisible({ timeout: 30_000 })
  await barre.getByText('Prix', { exact: true }).first().click()
  await barre.getByPlaceholder('ex. 10 ou -5').fill('10')
  await barre.getByRole('button', { name: 'Appliquer', exact: true }).click()
  await coupePremier(p, rx)
  const relue = p.waitForResponse((q) => q.request().method() === 'GET' && /\/api\/django\/stock\/produits\/(\?|$)/.test(q.url().replace(/^https?:\/\/[^/]+/, '')), T)
  await barre.getByRole('alert').getByRole('button', { name: 'Confirmer' }).click()
  await expect.poll(() => envois.length, { message: 'premier envoi parti', timeout: 30_000 }).toBe(1)
  await relue // la liste est relue après l'échec sans réponse
  expect(await prixDe(x), 'le serveur a appliqué le 1er envoi : 1 100 et 2 200').toEqual(['1100.00', '2200.00'])
  // « Prix + 10 % » rouvert : la valeur est GARDÉE (l'échec ne l'a pas vidée) ; nouvel essai, même clé.
  await barre.getByText('Prix', { exact: true }).first().click()
  await expect(barre.getByPlaceholder('ex. 10 ou -5'), 'valeur gardée après l\'échec').toHaveValue('10')
  await barre.getByRole('button', { name: 'Appliquer', exact: true }).click()
  const [r2] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(chemin(q.url())), T),
    barre.getByRole('alert').getByRole('button', { name: 'Confirmer' }).click(),
  ])
  expect(r2.status(), `nouvel essai : ${(await r2.text()).slice(0, 200)}`).toBe(200)
  expect(envois.length, 'deux envois').toBe(2)
  expect(envois[0].cle, 'une clé').toBeTruthy()
  expect(envois[1].cle, 'MÊME clé au nouvel essai').toBe(envois[0].cle)
  expect(await prixDe(x), 'UN SEUL +10 % : 1 100 et 2 200 (jamais 1 210 et 2 420)').toEqual(['1100.00', '2200.00'])
  await p.unrouteAll({ behavior: 'ignoreErrors' })
})

etape('PF9.4-ACNC28-ecran', ['ACNC28'], async ({ page, suivi, testInfo }) => {
  const { nom, ctx: api } = await acteur(testInfo, 'acnc28e', 'Directeur')
  const m = marque()
  const a = await preparer(`${m}a`, { stock: 0, qte: 10, pu: '100' })
  const b = await preparer(`${m}b`, { stock: 0, qte: 10, pu: '100' })
  apres.push(() => nettoyer(`${m}a`))
  apres.push(() => nettoyer(`${m}b`))
  for (const [i, x] of [[0, a], [1, b]]) {
    const rec = await api.post(`${STOCK}/bons-commande-fournisseur/${x.b}/recevoir/`, { ...T, data: { receptions: [{ ligne: x.l, quantite: 5 }] }, headers: avecCle(`r28e-${m}-${i}`) })
    expect(rec.status(), `Given : 5 reçus (${i})`).toBe(200)
  }
  const ctx = await navigateur(page, testInfo, nom)
  const p = await onglet(page, suivi, ctx)
  const relecture = (x) => p.waitForResponse((q) => q.request().method() === 'GET' && new RegExp(`/api/django/stock/bons-commande-fournisseur/${x.b}/$`).test(chemin(q.url())), T)
  const ouvrirRetour = async (x) => {
    const dlg = await ouvrirBcf(p, x.ref)
    await dlg.getByRole('button', { name: /Retour fournisseur/ }).click()
    const rdlg = p.getByRole('dialog').filter({ hasText: 'Retour fournisseur —' })
    await expect(rdlg, 'fenêtre de retour').toBeVisible({ timeout: 30_000 })
    return rdlg
  }
  const cellRecu = (rdlg, x) => rdlg.getByRole('row').filter({ hasText: x.nom }).getByRole('cell').nth(1)
  // Phase 1 — réponse de la validation COUPÉE : la fenêtre relit le BCF et rebase ses plafonds ; aucun second retour ne part.
  const rxValider = /\/api\/django\/stock\/retours-fournisseur\/\d+\/valider\/$/
  const rxCreer = /\/api\/django\/stock\/retours-fournisseur\/$/
  suivi.attendre(rxValider, 'reseau')
  suivi.attendre(rxValider, 409)
  const creations = []
  p.on('request', (q) => { if (q.method() === 'POST' && rxCreer.test(chemin(q.url()))) creations.push(1) })
  let rd = await ouvrirRetour(a)
  await expect(cellRecu(rd, a), 'Reçu : 5').toHaveText('5')
  await rd.getByRole('spinbutton').first().fill('5')
  await rd.getByPlaceholder('ex. cassé à la livraison').fill('Défectueux')
  await coupePremier(p, rxValider)
  const relu = relecture(a)
  await rd.getByRole('button', { name: 'Valider le retour' }).click()
  await relu // le BCF est relu après l'échec
  expect(await py(`from apps.stock.models import Produit
sortie(Produit.objects.get(pk=${a.p}).quantite_stock)`), 'le serveur a validé le retour (stock 5 → 0)').toBe(0)
  await expect(cellRecu(rd, a), 'plafond rebasé : Reçu relu = 0').toHaveText('0', { timeout: 30_000 })
  await rd.getByRole('spinbutton').first().fill('5')
  await expect(rd.getByText(/Max 0/), 'saisie de 5 : « Max 0 »').toBeVisible()
  await rd.getByRole('button', { name: 'Valider le retour' }).click()
  await expect(rd, 'rien à retourner : refus à l\'écran').toContainText('Saisissez au moins une quantité à retourner', { timeout: 15_000 })
  expect(creations.length, 'aucun second retour créé').toBe(1)
  // Phase 2 — fenêtre périmée : un collègue retourne les 5 pendant que la fenêtre est ouverte ⇒ 409 à la validation.
  rd = await ouvrirRetour(b)
  await expect(cellRecu(rd, b), 'Reçu : 5').toHaveText('5')
  await rd.getByRole('spinbutton').first().fill('5')
  await rd.getByPlaceholder('ex. cassé à la livraison').fill('Défectueux')
  const r1 = await lireJson(await api.post(`${STOCK}/retours-fournisseur/`, { ...T, data: { fournisseur: b.f, bon_commande: b.b, lignes: [{ produit: b.p, quantite: 5, motif: 'Collègue' }] } }), 'retour du collègue')
  const v1 = await api.post(`${STOCK}/retours-fournisseur/${r1.id}/valider/`, T)
  expect(v1.status(), 'le collègue valide son retour').toBe(200)
  const relu2 = relecture(b)
  const [rv] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rxValider.test(chemin(q.url())), T),
    rd.getByRole('button', { name: 'Valider le retour' }).click(),
  ])
  expect(rv.status(), `validation périmée : ${(await rv.text()).slice(0, 200)}`).toBe(409)
  await expect(rd, 'message du 409 affiché').toContainText(/quantité reçue restante/i, { timeout: 30_000 })
  await relu2 // la fenêtre relit le BCF après l'échec
  await expect(cellRecu(rd, b), 'Reçu relu = 0').toHaveText('0', { timeout: 30_000 })
  const e = await py(`from apps.stock.models import Produit, MouvementStock
sortie(dict(stock=Produit.objects.get(pk=${b.p}).quantite_stock, sorties=MouvementStock.objects.filter(produit_id=${b.p}, type_mouvement='sortie').count()))`)
  expect(e, 'stock 0, UNE seule sortie (le retour du collègue)').toEqual({ stock: 0, sorties: 1 })
  await p.unrouteAll({ behavior: 'ignoreErrors' })
})

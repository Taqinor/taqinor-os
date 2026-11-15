// Preuves en direct ACNC, lot 8 (contre-visite du 15/11, C-ACNC-VER4-400 et -401) : ACNC74 et ACNC75
// (PLAN_AUDIT_STOCK.md) — règlements fournisseur.
//   ACNC74 : un second règlement identique (même facture, même montant, même jour) sous une autre clé rend 409
//            `paiement_similaire` sans rien écrire ; « Confirmer » renvoie `confirmer_doublon` sous la MÊME clé ⇒ 201 ;
//            depuis la fiche facture ET depuis le registre (Achats › Paiements fournisseur).
//   ACNC75 : après une réponse perdue sur « Ajouter le paiement », le bouton reste occupé jusqu'au retour de la
//            relecture de la fiche, puis « Paiement de 3 000 MAD enregistré (réponse perdue, fiche relue). » remplace
//            le bandeau d'échec.
//
// Règle de preuve (METHODE §C.4 point 7) : chaque geste est joué À L'ÉCRAN sous le rôle LIVRÉ « Directeur » du registre
// (compte d'essai connecté PAR L'ÉCRAN DE CONNEXION) ; la réponse du POST est coupée APRÈS passage au serveur
// (`route.fetch()` puis `route.abort()`, patron d'acnc7.spec.js) ; la relecture est TENUE par une route jusqu'à ce que
// l'état occupé du bouton soit affirmé ; la base est relue par le shell Django. Factures de 10 000 TTC créées par le
// shell, retirées à la fin.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI } from './_django.js'
import { uiLoginJusquAuxApps } from '../helpers.js'
import { monter, T, marque, SOC, note, ouverts } from './_acnc.js'

const etape = groupe('ACNC', ['ACNC74', 'ACNC75'])
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

/** Compte d'essai du rôle LIVRÉ `nomRole` (rôle système de la société démo, palier dérivé du rôle). */
async function compte(prefixe, nomRole) {
  const nom = `${prefixe}_${marque()}`
  await py(`from apps.roles.models import Role
from authentication.role_tiers import tier_for_role_fields
r = Role.objects.get(company_id=${SOC}, nom=${J(nomRole)}, est_systeme=True)
u = compte(${J(nom)}, role=r.pk, societe=${SOC})
u.role_legacy = tier_for_role_fields(r.nom, r.est_systeme, r.permissions); u.save(update_fields=['role_legacy'])
sortie(u.id)`)
  return nom
}
/** Navigateur À FROID du compte `nom` (connexion par l'écran), surveillé par les oracles. */
async function ecran(page, suivi, testInfo, nom) {
  const u = testInfo.project.use
  const ctx = await page.context().browser().newContext({
    baseURL: u.baseURL, storageState: { cookies: [], origins: [] }, serviceWorkers: 'block', viewport: { width: 1600, height: 1000 },
  })
  ouverts.push(ctx)
  if (!page.isClosed()) await page.close()
  const p = suivi.surveiller(await ctx.newPage())
  await p.addInitScript(INIT)
  await uiLoginJusquAuxApps(p, { username: nom, password: MDP_ESSAI })
  return p
}

const factureFournisseur = (m) => py(`import datetime
from decimal import Decimal
from django.utils import timezone
from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur
f = Fournisseur.objects.create(company_id=${SOC}, nom='Fournisseur ACNC74 ${m}', type='service')
ttc = Decimal('10000'); ht = (ttc / Decimal('1.2')).quantize(Decimal('0.01'))
ff = FactureFournisseur.objects.create(company_id=${SOC}, reference='FF-ACNC74-${m}', fournisseur=f,
    date_facture=datetime.date.today(), montant_ht=ht, montant_tva=ttc - ht, montant_ttc=ttc)
sortie(dict(f=f.pk, ff=ff.pk, ref=ff.reference, solde=str(ff.solde_du), jour=str(timezone.localdate())))`)
const retirer = (x) => py(`from apps.stock.models import Fournisseur
from apps.achats.models import FactureFournisseur, PaiementFournisseur
PaiementFournisseur.objects.filter(facture_id=${x.ff}).delete(); FactureFournisseur.objects.filter(pk=${x.ff}).delete(); Fournisseur.objects.filter(pk=${x.f}).delete()
sortie(True)`)
const base = (x) => py(`from apps.achats.models import FactureFournisseur, PaiementFournisseur
ff = FactureFournisseur.objects.get(pk=${x.ff})
sortie({'reglements': [str(p.montant) for p in PaiementFournisseur.objects.filter(facture=ff).order_by('pk')], 'solde': str(ff.solde_du)})`)

// Phrase du 409 `paiement_similaire` (montant formaté par core.formats_fr : espace fine / insécable).
const PHRASE = /^Un règlement de 3\s?000\s?MAD a déjà été enregistré aujourd'hui sur cette facture\s?:\s?confirmer\s?\?/
const INFO = /Paiement de 3\s?000\s?MAD enregistré \(réponse perdue, fiche relue\)\./
const ECHEC = "L'enregistrement du paiement a échoué."
const rxFiche = (x) => new RegExp(`/api/django/stock/factures-fournisseur/${x.ff}/paiements/$`)
const rxRegistre = /\/api\/django\/stock\/paiements-fournisseur\/$/
const chemin = (u) => new URL(u).pathname

/** Fiche de la facture ouverte depuis Achats › Factures fournisseur. */
async function ouvrirFiche(p, x) {
  await p.goto('/stock/factures-fournisseur')
  await p.getByPlaceholder('Rechercher (référence, fournisseur)…').fill(x.ref, { timeout: 60_000 })
  await p.getByRole('row').filter({ hasText: x.ref }).getByText(x.ref).first().click({ timeout: 60_000 })
  const dlg = p.getByRole('dialog').filter({ hasText: `Facture — ${x.ref}` })
  await expect(dlg, 'fiche de la facture ouverte').toBeVisible({ timeout: 30_000 })
  return dlg
}
const soldeDu = (dlg) => dlg.getByText('Solde dû', { exact: true }).locator('..')
const lignesPaiement = (dlg) => dlg.getByRole('row').filter({ hasText: /3\s?000/ })
/** Clic sur « Ajouter le paiement » et la réponse de son POST. */
const ajouter = (p, dlg, x) => Promise.all([
  p.waitForResponse((q) => q.request().method() === 'POST' && rxFiche(x).test(chemin(q.url())), T),
  dlg.getByRole('button', { name: 'Ajouter le paiement' }).click(),
]).then(([r]) => r)

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC74 — porte 1 : la fiche facture (3 000 puis 3 000 du jour ⇒ 409, « Confirmer » ⇒ deux règlements)
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC74-fiche-facture', ['ACNC74'], async ({ page, suivi, testInfo }) => {
  const nom = await compte('acnc74f', 'Directeur')
  const x = await factureFournisseur(marque())
  apres.push(() => retirer(x))
  expect(Number(x.solde), 'Given : facture fournisseur de 10 000 TTC à payer').toBe(10000)
  const rx = rxFiche(x)
  const envois = []
  const p = await ecran(page, suivi, testInfo, nom)
  p.on('request', (q) => { if (q.method() === 'POST' && rx.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null, corps: q.postDataJSON() }) })
  suivi.attendre(rx, 409) // le refus PROUVÉ par l'étape
  let dlg = await ouvrirFiche(p, x)
  await expect(dlg.getByText('Aucun paiement.'), 'Given : aucun paiement').toBeVisible()

  // 3 000 du jour : enregistré.
  await dlg.locator('#pay-montant').fill('3000')
  const r1 = await ajouter(p, dlg, x)
  expect(r1.status(), `1er règlement : ${(await r1.text()).slice(0, 200)}`).toBe(201)
  await expect(lignesPaiement(dlg), 'un règlement de 3 000 affiché').toHaveCount(1, { timeout: 30_000 })
  expect(await base(x), 'Given : 3 000 du jour déjà réglés').toEqual({ reglements: ['3000.00'], solde: '7000.00' })

  // Second 3 000 du jour (autre clé) ⇒ 409 `paiement_similaire`, phrase + « Confirmer », RIEN d'écrit.
  await dlg.locator('#pay-montant').fill('3000')
  const r2 = await ajouter(p, dlg, x)
  const j2 = await r2.json().catch(() => ({}))
  expect([r2.status(), j2.code], `2e envoi sans confirmation : ${J(j2)}`).toEqual([409, 'paiement_similaire'])
  const alerte = dlg.getByRole('alert').filter({ hasText: 'a déjà été enregistré' })
  await expect(alerte, 'la phrase serveur est affichée').toBeVisible({ timeout: 30_000 })
  await expect(alerte).toHaveText(PHRASE)
  note(testInfo, 'phrase affichée (fiche)', await alerte.innerText())
  const confirmer = alerte.getByRole('button', { name: 'Confirmer' })
  await expect(confirmer, 'bouton « Confirmer »').toBeVisible()
  expect(await base(x), 'après le 409 : UN règlement en base, solde 7 000').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  await expect(lignesPaiement(dlg), 'après le 409 : toujours un règlement affiché').toHaveCount(1)

  // « Confirmer » ⇒ MÊME clé + `confirmer_doublon` ⇒ 201, deux règlements.
  const [r3] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'POST' && rx.test(chemin(q.url())), T), confirmer.click(),
  ])
  expect(r3.status(), `confirmé : ${(await r3.text()).slice(0, 200)}`).toBe(201)
  expect(envois.length, 'trois envois').toBe(3)
  expect(envois[1].cle, '2e envoi : autre clé que le 1er règlement').not.toBe(envois[0].cle)
  expect(envois[2].cle, '« Confirmer » : MÊME clé que le 409').toBe(envois[1].cle)
  expect(envois.map((e) => e.corps.confirmer_doublon ?? null), 'confirmer_doublon seulement au renvoi').toEqual([null, null, true])
  expect(await base(x), 'après « Confirmer » : DEUX règlements de 3 000, solde 4 000')
    .toEqual({ reglements: ['3000.00', '3000.00'], solde: '4000.00' })
  await expect(lignesPaiement(dlg), 'deux règlements affichés').toHaveCount(2, { timeout: 30_000 })
  await expect(soldeDu(dlg), 'solde dû 4 000').toContainText(/4\s?000/)
  await expect(alerte, 'phrase retirée après confirmation').toHaveCount(0)

  // Persistance : rechargé, la fiche relue porte les deux règlements.
  await p.reload()
  dlg = await ouvrirFiche(p, x)
  await expect(lignesPaiement(dlg), 'rechargée : deux règlements de 3 000').toHaveCount(2, { timeout: 30_000 })
  await expect(soldeDu(dlg), 'rechargée : solde 4 000').toContainText(/4\s?000/)
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC74 — porte 2 : 3 000 par la fiche, puis 3 000 par Achats › Paiements fournisseur ⇒ 409, « Confirmer » ⇒ deux
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC74-grand-livre', ['ACNC74'], async ({ page, suivi, testInfo }) => {
  const nom = await compte('acnc74g', 'Directeur')
  const x = await factureFournisseur(marque())
  apres.push(() => retirer(x))
  expect(Number(x.solde), 'Given : facture fournisseur de 10 000 TTC à payer').toBe(10000)
  const p = await ecran(page, suivi, testInfo, nom)
  // 3 000 du jour par la fiche.
  const dlg = await ouvrirFiche(p, x)
  await dlg.locator('#pay-montant').fill('3000')
  const r1 = await ajouter(p, dlg, x)
  expect(r1.status(), `règlement par la fiche : ${(await r1.text()).slice(0, 200)}`).toBe(201)
  expect(await base(x), 'Given : 3 000 du jour déjà réglés (fiche)').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  await dlg.getByRole('button', { name: 'Fermer' }).first().click()
  await expect(dlg, 'fiche refermée').toBeHidden({ timeout: 30_000 })

  // Puis par le registre : même facture, 3 000, même jour.
  const envois = []
  p.on('request', (q) => { if (q.method() === 'POST' && rxRegistre.test(chemin(q.url()))) envois.push({ cle: q.headers()['idempotency-key'] ?? null, corps: q.postDataJSON() }) })
  suivi.attendre(rxRegistre, 409) // le refus PROUVÉ par l'étape
  await p.goto('/stock/paiements-fournisseur')
  await p.getByRole('combobox', { name: 'Facture fournisseur' }).click({ timeout: 60_000 })
  await p.getByRole('option', { name: new RegExp(x.ref) }).click()
  await p.getByLabel('Montant du règlement').fill('3000')
  await p.getByLabel('Date du règlement').fill(x.jour)
  const bouton = p.getByRole('button', { name: 'Enregistrer le règlement' })
  const registre = () => p.getByTestId('table-paiements').getByRole('row').filter({ hasText: x.ref })
  const reponse = () => p.waitForResponse((q) => q.request().method() === 'POST' && rxRegistre.test(chemin(q.url())), T)
  const [r2] = await Promise.all([reponse(), bouton.click()])
  const j2 = await r2.json().catch(() => ({}))
  expect([r2.status(), j2.code], `registre, sans confirmation : ${J(j2)}`).toEqual([409, 'paiement_similaire'])
  const alerte = p.getByRole('alert').filter({ hasText: 'a déjà été enregistré' })
  await expect(alerte, 'la phrase serveur est affichée au registre').toBeVisible({ timeout: 30_000 })
  await expect(alerte).toHaveText(PHRASE)
  note(testInfo, 'phrase affichée (registre)', await alerte.innerText())
  const confirmer = alerte.getByRole('button', { name: 'Confirmer' })
  await expect(confirmer, 'bouton « Confirmer »').toBeVisible()
  expect(await base(x), 'après le 409 : UN règlement en base').toEqual({ reglements: ['3000.00'], solde: '7000.00' })

  // « Confirmer » ⇒ MÊME clé + `confirmer_doublon` ⇒ 201, deux règlements.
  const [r3] = await Promise.all([reponse(), confirmer.click()])
  expect(r3.status(), `registre, confirmé : ${(await r3.text()).slice(0, 200)}`).toBe(201)
  expect(envois.length, 'deux envois au registre').toBe(2)
  expect(envois[0].cle, 'une clé envoyée').toBeTruthy()
  expect(envois[1].cle, '« Confirmer » : MÊME clé que le 409').toBe(envois[0].cle)
  expect(envois.map((e) => e.corps.confirmer_doublon ?? null), 'confirmer_doublon seulement au renvoi').toEqual([null, true])
  expect(await base(x), 'après « Confirmer » : DEUX règlements de 3 000, solde 4 000')
    .toEqual({ reglements: ['3000.00', '3000.00'], solde: '4000.00' })
  await expect(registre(), 'registre : deux règlements de la facture').toHaveCount(2, { timeout: 60_000 })

  // Persistance : rechargé, le registre relu porte les deux règlements.
  await p.reload()
  await expect(registre(), 'rechargé : deux règlements au registre').toHaveCount(2, { timeout: 60_000 })
})

// ════════════════════════════════════════════════════════════════════════════════════════════
// ACNC75 — réponse perdue : bouton occupé jusqu'à la relecture, puis le règlement relu est dit enregistré
// ════════════════════════════════════════════════════════════════════════════════════════════
etape('PF9.4-ACNC75-fiche-facture', ['ACNC75'], async ({ page, suivi, testInfo }) => {
  const nom = await compte('acnc75', 'Directeur')
  const x = await factureFournisseur(marque())
  apres.push(() => retirer(x))
  expect(Number(x.solde), 'Given : facture fournisseur de 10 000 TTC à payer').toBe(10000)
  const rx = rxFiche(x)
  const relecture = new RegExp(`/api/django/stock/factures-fournisseur/${x.ff}/$`)
  const p = await ecran(page, suivi, testInfo, nom)
  suivi.attendre(rx, 'reseau')
  const dlg = await ouvrirFiche(p, x)
  await expect(dlg.getByText('Aucun paiement.'), 'Given : aucun paiement').toBeVisible()
  await expect(soldeDu(dlg), 'Given : solde dû 10 000').toContainText(/10\s?000/)

  // Réponse du POST coupée APRÈS passage au serveur ; la relecture (GET de la facture) est TENUE.
  let coupe = true
  await p.route((u) => rx.test(u.pathname), async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    if (coupe) { coupe = false; await route.fetch(); return route.abort('failed') }
    return route.continue()
  })
  let liberer
  const tenue = new Promise((r) => { liberer = r })
  let relectureVue
  const vue = new Promise((r) => { relectureVue = r })
  await p.route((u) => relecture.test(u.pathname), async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    relectureVue()
    await tenue
    return route.continue()
  })
  await dlg.locator('#pay-montant').fill('3000')
  await dlg.getByRole('button', { name: 'Ajouter le paiement' }).click()
  await vue
  expect(await base(x), 'shell : le POST coupé est passé au serveur (un règlement de 3 000)').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  // Relecture en vol : le bouton reste occupé (« … », aria-busy, désactivé).
  const occupe = dlg.locator('button[aria-busy="true"]').filter({ hasText: '…' })
  await expect(occupe, 'relecture en vol : bouton occupé « … »').toHaveCount(1)
  await expect(occupe, 'relecture en vol : bouton désactivé').toBeDisabled()
  await expect(dlg.getByRole('button', { name: 'Ajouter le paiement' }), 'relecture en vol : « Ajouter le paiement » pas encore rendu').toHaveCount(0)
  await p.waitForTimeout(1500)
  await expect(occupe, 'toujours occupé tant que la relecture est tenue').toHaveCount(1)
  // La relecture revient.
  const [relue] = await Promise.all([
    p.waitForResponse((q) => q.request().method() === 'GET' && relecture.test(chemin(q.url())), T),
    Promise.resolve().then(() => liberer()),
  ])
  expect(relue.status(), 'relecture de la fiche').toBe(200)
  await expect(dlg.getByRole('button', { name: 'Ajouter le paiement' }), 'après la relecture : bouton rendu').toBeEnabled({ timeout: 30_000 })
  await expect(dlg.getByText(INFO), 'message « Paiement de 3 000 MAD enregistré (réponse perdue, fiche relue). »').toBeVisible({ timeout: 30_000 })
  await expect(dlg.getByText(ECHEC), 'plus de « L\'enregistrement du paiement a échoué. »').toHaveCount(0)
  await expect(dlg.getByText(/a échoué/), 'aucun « a échoué » à l\'écran').toHaveCount(0)
  await expect(lignesPaiement(dlg), 'règlement de 3 000 affiché, sans rechargement').toHaveCount(1, { timeout: 30_000 })
  await expect(dlg.getByText('Aucun paiement.'), 'plus « Aucun paiement »').toHaveCount(0)
  await expect(soldeDu(dlg), 'solde dû relu 7 000').toContainText(/7\s?000/)
  await expect(dlg.locator('#pay-montant'), 'montant gardé (un reclic rejouerait la même clé)').toHaveValue('3000')
  note(testInfo, 'message affiché', await dlg.getByText(INFO).innerText())
  expect(await base(x), 'shell : toujours UN règlement de 3 000').toEqual({ reglements: ['3000.00'], solde: '7000.00' })
  await p.unrouteAll({ behavior: 'ignoreErrors' })
})

// Rejeux en direct ACNC7 et ACNC15 (groupe ACNC, parcours PF9) restés ROUGES au rejeu runner du 14/11/2026 — défauts
// produits dans les Files des tâches, gardés tels quels pour le rejeu qui suivra la correction (même montage que
// acnc.spec.js, `_acnc.js`) :
// - ACNC7 (run 43541934037) : « Créer la facture » et « Annuler » croisés sur un BC confirmé ⇒ 201 ET 200 — BC annulé
//   portant une facture vivante (`BonCommandeViewSet.annuler` lit l'état sans verrou) ;
// - ACNC15 (run 43540956204) : l'onglet périmé reçoit bien 409 `conflit_version` sans écriture, mais l'écran affiche
//   « code : conflit_version » au lieu de la phrase serveur (FactureForm.jsx).
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py } from './_django.js'
import { lireJson } from '../helpers.js'
import {
  monter,
  API,
  T,
  marque,
  SOC,
  AUJ,
  statuts,
  note,
  bd,
  acteur,
  navigateur,
  onglet,
  couper,
  reponse,
  venteAcceptee,
  lireF,
  factureEmise,
  payer,
  ligneFacture,
} from './_acnc.js'

const etape = groupe('ACNC', ['ACNC7', 'ACNC15'])
monter()
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

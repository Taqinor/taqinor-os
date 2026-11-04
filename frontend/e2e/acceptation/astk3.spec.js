// Acceptation en direct — groupe ASTK, troisième lot (preuves dues ASTK258, ASTK259, ASTK262, ASTK263) : « une vente =
// une sortie » quand l'acompte a déjà sorti le matériel. Données posées au shell Django dans la société de demo_admin
// (jamais `company_id` codé en dur) : panneau à stock connu, lead « Signé », devis accepté de 10, chantier (réservation
// 10). Gestes par les VRAIES routes (generer-facture/emettre, valider-consommation, recevoir, annuler, PATCH du lead) ;
// l'annulation de facture est jouée sur l'écran Factures. La clé d'étape du lead vient de STAGES.py (lue au shell).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ASTK', ['ASTK258', 'ASTK259', 'ASTK262', 'ASTK263'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const T = { timeout: 120_000 }
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

/** Vente de 10 panneaux acceptée + chantier (réservation 10), stock `stock`. */
async function vente(stock) {
  const m = marque()
  return py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.installations.services import create_installation_from_devis
p = Produit.objects.create(company=co, nom='Panneau ACC-ASTK ${m}', sku='ACC-ASTK-${m}', prix_vente=D('100'), prix_achat=D('60'), quantite_stock=${stock}, tva=D('20.00'))
cl = Client.objects.create(company=co, nom='ACC ASTK', prenom='${m}', email='acc-astk-${m.toLowerCase()}@example.invalid')
kw = dict(company=co, nom='ACC ASTK', prenom='${m}', stage=stages.SIGNED, type_installation='residentiel')
if any(f.name == 'client' for f in Lead._meta.fields): kw['client'] = cl
lead = Lead.objects.create(**kw)
d = Devis.objects.create(company=co, reference='DEV-ACC-ASTK-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=D('20'), mode_installation='residentiel')
LigneDevis.objects.create(devis=d, produit=p, designation='Panneau ACC-ASTK ${m}', quantite=D('10'), prix_unitaire=D('100'), taux_tva=D('20.00'))
inst, _ = create_installation_from_devis(d, a, co)
sortie(dict(m='${m}', produit=p.id, lead=lead.id, devis=d.id, ref=d.reference, chantier=inst.id, chantier_ref=inst.reference, quote_sent=stages.QUOTE_SENT))`)
}

/** Σ SORTIE, Σ ENTRÉE, stock, réservations, mouvements du panneau. */
const bilan = (x) => py(`from django.db.models import Sum
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_entree, mouvement_type_sortie
from apps.installations.models import StockReservation
p = Produit.objects.get(pk=${x.produit})
s = lambda t: float(MouvementStock.objects.filter(produit=p, type_mouvement=t).aggregate(t=Sum('quantite'))['t'] or 0)
sortie(dict(sorties=s(mouvement_type_sortie()), entrees=s(mouvement_type_entree()), stock=float(p.quantite_stock),
  resas=[[float(r.quantite), r.consomme] for r in StockReservation.objects.filter(installation_id=${x.chantier}, produit=p)],
  mvts=[[t, r, float(q)] for t, r, q in MouvementStock.objects.filter(produit=p).order_by('id').values_list('type_mouvement', 'reference', 'quantite')]))`)

/** Acompte par les routes de l'écran (generer-facture, puis emettre si brouillon) ; rend la facture. */
async function acompte(r, x) {
  const g = await r.post(`${API}/ventes/devis/${x.devis}/generer-facture/`, { ...T, data: {} })
  expect(g.status(), await g.text()).toBeLessThan(400)
  const f = await py(`from apps.ventes.models import Facture
f = Facture.objects.filter(devis_id=${x.devis}).exclude(statut='annulee').order_by('-id').first()
sortie(dict(id=f.id, reference=f.reference, statut=f.statut))`)
  if (f.statut === 'brouillon') await lireJson(await r.post(`${API}/ventes/factures/${f.id}/emettre/`, { ...T, data: {} }), 'émettre')
  return f
}

/** F11 : intervention du chantier, consommation de la nomenclature (quantité `qte` justifiée si ≠ prévu), validée par la route. */
async function f11(r, x, qte = null) {
  const itv = await py(`from decimal import Decimal as D
from apps.installations import field_capture
from apps.installations.models import Intervention, Installation
inst = Installation.objects.get(pk=${x.chantier})
itv = Intervention.objects.create(company=inst.company, installation=inst)
cons = field_capture.ensure_consommation(itv)
${qte === null ? '' : `cons.lignes.filter(produit_id=${x.produit}).update(quantite_utilisee=D('${qte}'), justification='acceptation ASTK')`}
sortie(dict(id=itv.id, lignes=[[l.produit_id, float(l.quantite_utilisee or 0)] for l in cons.lignes.all()]))`)
  const rep = await r.post(`${API}/installations/interventions/${itv.id}/valider-consommation/`, { ...T, data: {} })
  expect(rep.status(), `valider-consommation (${await rep.text()})`).toBe(200)
  return itv
}

const installer = (x) => py(`a = U.objects.get(username='demo_admin')
from apps.installations.models import Installation
from apps.installations.services import changer_statut_chantier
inst = Installation.objects.get(pk=${x.chantier})
changer_statut_chantier(inst, Installation.Statut.INSTALLE, a, verifier_gates=False)
sortie(1)`)

const archiver = (x) => py(`from apps.stock.models import Produit
Produit.objects.filter(pk=${x.produit}).update(**({'is_active': False} if any(f.name == 'is_active' for f in Produit._meta.fields) else {}))
sortie(1)`).catch(() => null)

// ── ASTK262 + ASTK263 : acompte émis puis « Annuler » sur l'écran Factures ⇒ ENTRÉE 10 sous la référence du devis,
//    stock 20, réservation rouverte ; puis le lead sort de « Signé » (accepté, chantier annulé, stock 20). ─────────
etape('P.annulation_acompte_ecran', ['ASTK262', 'ASTK263'], async ({ page, suivi }) => {
  const r = page.request
  const x = await vente(20)
  try {
    const f = await acompte(r, x)
    const b1 = await bilan(x)
    expect([b1.sorties, b1.stock], `acompte émis : SORTIE 10, stock 10 (${JSON.stringify(b1)})`).toEqual([10, 10])
    expect(b1.resas, 'réservation soldée par la vente').toEqual([[0, true]])
    await page.goto('/ventes/factures')
    await page.getByPlaceholder('Référence, client').fill(f.reference)
    const ligne = page.locator(`#facture-row-${f.id}`).first()
    await expect(ligne).toBeVisible({ timeout: 60_000 })
    await ligne.getByTitle("Plus d'actions").click()
    await page.getByTestId('annuler-facture').click()
    const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture ${f.reference}` })
    await expect(dlg).toBeVisible({ timeout: 30_000 })
    const [rep] = await Promise.all([
      page.waitForResponse((q) => q.request().method() === 'POST' && new RegExp(`/ventes/factures/${f.id}/annuler/$`).test(new URL(q.url()).pathname), { timeout: 120_000 }),
      dlg.getByRole('button', { name: 'Annuler la facture' }).click(),
    ])
    expect(rep.status(), await rep.text()).toBe(200)
    const b2 = await bilan(x)
    expect(b2.stock, `annulation : stock 20 (${JSON.stringify(b2)})`).toBe(20)
    expect(b2.mvts.filter(([t, ref]) => t === 'entree' && ref === x.ref).map((m) => m[2]), 'UNE ENTRÉE 10 sous devis.reference').toEqual([10])
    expect(b2.resas, 'ASTK263 : réservation rouverte (10, non consommée)').toEqual([[10, false]])
    // Ré-annuler ⇒ refus, aucune seconde ENTRÉE.
    suivi.attendre(new RegExp(`/ventes/factures/${f.id}/annuler/`), 400)
    suivi.attendre(new RegExp(`/ventes/factures/${f.id}/annuler/`), 409)
    const re = await r.post(`${API}/ventes/factures/${f.id}/annuler/`, { ...T, data: {} })
    expect(re.status(), `ré-annulation refusée (${re.status()})`).toBeGreaterThanOrEqual(400)
    expect((await bilan(x)).entrees).toBe(10)
    // ASTK263 (a) : le lead sort de « Signé » (dés-acceptation) ⇒ 200, chantier annulé, stock 20.
    const patch = await r.patch(`${API}/crm/leads/${x.lead}/`, { ...T, data: { stage: x.quote_sent, confirme_recul: true } })
    expect(patch.status(), `lead sorti de « Signé » (${await patch.text()})`).toBe(200)
    const etat = await py(`from apps.installations.models import Installation
from apps.ventes.models import Devis
i = Installation.objects.get(pk=${x.chantier}); d = Devis.objects.get(pk=${x.devis})
sortie(dict(annule=i.annule, devis=d.statut))`)
    expect(etat, 'chantier annulé, devis repassé envoyé').toEqual({ annule: true, devis: 'envoye' })
    expect((await bilan(x)).stock).toBe(20)
    // Persistance : rechargement de l'écran + relecture ⇒ facture « Annulée », mêmes mouvements.
    const avantRelecture = await bilan(x)
    await page.reload({ waitUntil: 'domcontentloaded' })
    const relu = await lireJson(await r.get(`${API}/ventes/factures/${f.id}/`, T), 'facture relue')
    expect(relu.statut).toBe('annulee')
    expect((await bilan(x)).mvts).toEqual(avantRelecture.mvts)
  } finally {
    await archiver(x)
  }
})

// ── ASTK263 (b) + ASTK262 (b) : annulée puis NOUVELLE facture émise ⇒ réservation soldée de nouveau, « Installé » ne
//    sort rien de plus (Σ SORTIE 20 = 10 + 10, Σ ENTRÉE 10, stock 10). ─────────────────────────────────────────────
etape('P.refacture_puis_installe', ['ASTK262', 'ASTK263'], async ({ page }) => {
  const r = page.request
  const x = await vente(20)
  try {
    const f = await acompte(r, x)
    await lireJson(await r.post(`${API}/ventes/factures/${f.id}/annuler/`, { ...T, data: {} }), 'annuler')
    expect((await bilan(x)).stock).toBe(20)
    await acompte(r, x)
    const b = await bilan(x)
    expect([b.stock, b.resas], `nouvelle facture : stock 10, réservation soldée (${JSON.stringify(b)})`).toEqual([10, [[0, true]]])
    await installer(x)
    const fin = await bilan(x)
    expect([fin.sorties, fin.entrees, fin.stock], `« Installé » : aucune sortie de plus (${JSON.stringify(fin)})`).toEqual([20, 10, 10])
    await page.goto(`/chantiers?id=${x.chantier}`)
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await archiver(x)
  }
})

// ── ASTK258 : acompte émis puis F11 10 (route de l'écran d'intervention) ⇒ aucune seconde sortie (Σ 10, stock 20) ;
//    revalider ⇒ refusé (409), « Installé » ⇒ rien de plus. ────────────────────────────────────────────────────────
etape('P.acompte_puis_f11', ['ASTK258'], async ({ page, suivi }) => {
  const r = page.request
  const x = await vente(30)
  try {
    await acompte(r, x)
    expect((await bilan(x)).stock).toBe(20)
    const itv = await f11(r, x)
    const b = await bilan(x)
    expect([b.sorties, b.stock], `F11 10 après acompte : Σ SORTIE 10, stock 20 (${JSON.stringify(b)})`).toEqual([10, 20])
    suivi.attendre(new RegExp(`/interventions/${itv.id}/valider-consommation/`), 409)
    const re = await r.post(`${API}/installations/interventions/${itv.id}/valider-consommation/`, { ...T, data: {} })
    expect(re.status(), 'revalider ⇒ 409 (déjà validée)').toBe(409)
    await installer(x)
    const fin = await bilan(x)
    expect([fin.sorties, fin.stock], `« Installé » : rien de plus (${JSON.stringify(fin)})`).toEqual([10, 20])
    // Persistance : relecture ⇒ identique ; l'écran des mouvements de stock se rouvre.
    expect((await bilan(x)).mvts).toEqual(fin.mvts)
    await page.goto('/stock/mouvements')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await archiver(x)
  }
})

// ── ASTK259 : acompte émis, BCF livré en direct au chantier de 15 puis F11 15 ⇒ ENTRÉE 15, SORTIE 5 sous la
//    référence du chantier, stock 30 = 30 + 15 − 15. ──────────────────────────────────────────────────────────────
etape('P.acompte_bcf_direct_f11', ['ASTK259'], async ({ page }) => {
  const r = page.request
  const x = await vente(30)
  try {
    await acompte(r, x)
    const bc = await py(`from decimal import Decimal as D
from apps.installations.models import Installation
from apps.stock.models import BonCommandeFournisseur, Fournisseur
inst = Installation.objects.get(pk=${x.chantier}); co = inst.company
fo = Fournisseur.objects.create(company=co, nom='Fournisseur ACC-ASTK ${x.m}')
bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-ACC-ASTK-${x.m}', fournisseur=fo, chantier_livraison=inst, statut=BonCommandeFournisseur.Statut.ENVOYE)
li = bc.lignes.create(produit_id=${x.produit}, quantite=15, prix_achat_unitaire=D('60'))
sortie(dict(id=bc.id, ligne=li.id))`)
    const rec = await r.post(`${API}/stock/bons-commande-fournisseur/${bc.id}/recevoir/`, { ...T, data: { receptions: [{ ligne: bc.ligne, quantite: 15 }] } })
    expect(rec.status(), await rec.text()).toBe(200)
    const b = await bilan(x)
    expect([b.entrees, b.sorties, b.stock], `BCF direct 15 après acompte : ENTRÉE 15, Σ SORTIE 15 (10 + 5), stock 30 (${JSON.stringify(b)})`).toEqual([15, 15, 30])
    expect(b.mvts.filter(([t, ref]) => t === 'sortie' && ref === x.chantier_ref).map((m) => m[2]), 'SORTIE 5 sous la référence du chantier').toEqual([5])
    await f11(r, x, 15)
    const fin = await bilan(x)
    expect([fin.sorties, fin.stock], `F11 15 : rien de plus, stock 30 (${JSON.stringify(fin)})`).toEqual([15, 30])
    // Persistance : relecture ⇒ identique ; l'écran du BCF se rouvre.
    expect((await bilan(x)).mvts).toEqual(fin.mvts)
    await page.goto('/stock/mouvements')
    await expect(page.locator('body')).toBeVisible()
  } finally {
    await archiver(x)
  }
})

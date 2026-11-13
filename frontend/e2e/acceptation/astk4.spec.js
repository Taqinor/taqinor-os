// Acceptation en direct — groupe ASTK, quatrième lot (run 99392c vague 10) : preuve due d'ASTK264 — « acompte,
// révision acceptée, pose » ⇒ stock 20 : la sortie déjà faite sous la référence de la V1 (facture d'acompte émise)
// compte pour sa révision V2 acceptée ; la pose F11 de 10 sur le chantier ne sort rien de plus.
// Même montage que astk3.spec.js (panneau à stock connu, lead « Signé », devis accepté de 10, chantier) ; gestes par les
// VRAIES routes : generer-facture/emettre (acompte), reviser, share-link (envoi) + accepter (V2), valider-consommation.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ASTK', ['ASTK264'])
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
const J = JSON.stringify
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

/** Vente de 10 panneaux acceptée + chantier (réservation 10), stock `stock` (patron astk3.spec.js). */
async function vente(stock) {
  const m = marque()
  return py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.installations.services import create_installation_from_devis
p = Produit.objects.create(company=co, nom='Panneau ACC-ASTK264 ${m}', sku='ACC-ASTK264-${m}', prix_vente=D('100'), prix_achat=D('60'), quantite_stock=${stock}, tva=D('20.00'))
cl = Client.objects.create(company=co, nom='ACC ASTK264', prenom='${m}', email='acc-astk264-${m.toLowerCase()}@example.invalid')
kw = dict(company=co, nom='ACC ASTK264', prenom='${m}', stage=stages.SIGNED, type_installation='residentiel')
if any(f.name == 'client' for f in Lead._meta.fields): kw['client'] = cl
lead = Lead.objects.create(**kw)
d = Devis.objects.create(company=co, reference='DEV-ACC-ASTK264-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=D('20'), mode_installation='residentiel')
LigneDevis.objects.create(devis=d, produit=p, designation='Panneau ACC-ASTK264 ${m}', quantite=D('10'), prix_unitaire=D('100'), taux_tva=D('20.00'))
inst, _ = create_installation_from_devis(d, a, co)
sortie(dict(m='${m}', produit=p.id, lead=lead.id, devis=d.id, ref=d.reference, chantier=inst.id, chantier_ref=inst.reference))`)
}

/** Σ SORTIE, Σ ENTRÉE, stock, mouvements du panneau. */
const bilan = (x) => py(`from django.db.models import Sum
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_entree, mouvement_type_sortie
p = Produit.objects.get(pk=${x.produit})
s = lambda t: float(MouvementStock.objects.filter(produit=p, type_mouvement=t).aggregate(t=Sum('quantite'))['t'] or 0)
sortie(dict(sorties=s(mouvement_type_sortie()), entrees=s(mouvement_type_entree()), stock=float(p.quantite_stock),
  mvts=[[t, r, float(q)] for t, r, q in MouvementStock.objects.filter(produit=p).order_by('id').values_list('type_mouvement', 'reference', 'quantite')]))`)

/** Acompte par les routes de l'écran (generer-facture, puis emettre si brouillon). */
async function acompte(r, x) {
  const g = await r.post(`${API}/ventes/devis/${x.devis}/generer-facture/`, { ...T, data: {} })
  expect(g.status(), await g.text()).toBeLessThan(400)
  const f = await py(`from apps.ventes.models import Facture
f = Facture.objects.filter(devis_id=${x.devis}).exclude(statut='annulee').order_by('-id').first()
sortie(dict(id=f.id, reference=f.reference, statut=f.statut))`)
  if (f.statut === 'brouillon') await lireJson(await r.post(`${API}/ventes/factures/${f.id}/emettre/`, { ...T, data: {} }), 'émettre')
  return f
}

const sortiesDeLaVente = (devisId) => py(`from apps.ventes.selectors_sorties_vente import sorties_de_la_vente
co = U.objects.get(username='demo_admin').company
sortie({str(k): float(v) for k, v in sorties_de_la_vente(${devisId}, co).items()})`)

etape('P.acompte_revision_acceptee_pose', ['ASTK264'], async ({ page }) => {
  const r = page.request
  const x = await vente(30)
  // (1) Acompte émis sur la V1 : SORTIE 10 sous V1.reference, stock 20.
  await acompte(r, x)
  const b1 = await bilan(x)
  expect([b1.sorties, b1.stock], `acompte émis : SORTIE 10, stock 20 (${J(b1)})`).toEqual([10, 20])
  // (2) Révision de la V1 acceptée (route « Réviser ») ⇒ V2 brouillon, envoyée puis acceptée par les routes.
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${x.devis}/reviser/`, { ...T, data: {} }), 'réviser V1')
  expect(v2.reference, 'V2 : nouvelle référence').not.toBe(x.ref)
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V2')
  const acc = await r.post(`${API}/ventes/devis/${v2.id}/accepter/`, { ...T, data: { nom: 'Client ACC ASTK264' } })
  expect(acc.status(), `acceptation de la V2 (${(await acc.text()).slice(0, 300)})`).toBeLessThan(300)
  const etatV2 = await py(`from apps.ventes.models import Devis
from apps.installations.models import Installation
v2 = Devis.objects.get(pk=${v2.id})
inst = Installation.objects.filter(devis_id=v2.pk).order_by('id').first() or Installation.objects.get(pk=${x.chantier})
sortie(dict(statut=v2.statut, chantier=inst.id, chantier_devis=inst.devis_id))`)
  expect(etatV2.statut, 'V2 acceptée').toBe('accepte')
  // (a) La V2 compte la sortie faite sous la référence de la V1.
  expect(await sortiesDeLaVente(v2.id), 'sorties_de_la_vente(V2) = {panneau: 10}').toEqual({ [String(x.produit)]: 10 })
  const b2 = await bilan(x)
  expect([b2.sorties, b2.stock], `révision acceptée : aucune sortie de plus (${J(b2)})`).toEqual([10, 20])
  // (b) Pose : F11 de 10 sur le chantier de la vente, validée par la route ⇒ aucune SORTIE de plus, stock 20.
  const itv = await py(`from decimal import Decimal as D
from apps.installations import field_capture
from apps.installations.models import Intervention, Installation
inst = Installation.objects.get(pk=${etatV2.chantier})
itv = Intervention.objects.create(company=inst.company, installation=inst)
cons = field_capture.ensure_consommation(itv)
lignes = [[l.produit_id, float(l.quantite_utilisee or 0)] for l in cons.lignes.all()]
if not cons.lignes.filter(produit_id=${x.produit}).exists():
    from apps.installations.models import ConsommationLigne
    ConsommationLigne.objects.create(company=inst.company, consommation=cons, produit_id=${x.produit}, designation='Panneau', quantite_utilisee=D('10'), justification='pose ACC ASTK264', hors_nomenclature=True)
else:
    cons.lignes.filter(produit_id=${x.produit}).update(quantite_utilisee=D('10'), justification='pose ACC ASTK264')
sortie(dict(id=itv.id, lignes_amorcees=lignes))`)
  const rep = await r.post(`${API}/installations/interventions/${itv.id}/valider-consommation/`, { ...T, data: {} })
  expect(rep.status(), `valider-consommation (${(await rep.text()).slice(0, 300)})`).toBe(200)
  const b3 = await bilan(x)
  expect([b3.sorties, b3.stock], `pose de 10 après acompte + révision : Σ SORTIE 10, stock 20 (${J(b3)})`).toEqual([10, 20])
  // Persistance : relecture ⇒ mêmes mouvements ; revalider ⇒ 409 et 0 sortie.
  const re = await r.post(`${API}/installations/interventions/${itv.id}/valider-consommation/`, { ...T, data: {} })
  expect(re.status(), 'revalider ⇒ 409 (déjà validée)').toBe(409)
  expect((await bilan(x)).mvts, 'mouvements inchangés à la relecture').toEqual(b3.mvts)
  const produit = await lireJson(await r.get(`${API}/stock/produits/${x.produit}/`, T), 'produit relu')
  expect(Number(produit.quantite_stock), 'fiche produit : stock 20').toBe(20)
  // Écran : mouvements de stock du panneau (recherche par référence de chantier/vente) — la liste se rouvre.
  await page.goto('/stock/mouvements')
  await expect(page.locator('body')).toBeVisible()
})

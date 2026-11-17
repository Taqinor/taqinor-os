// Acceptation en direct — groupe ASTK, cinquième lot (vague d'acceptation 8 sur runner GitHub, METHODE §C.4 point 7) :
// preuve due d'ASTK250 (D-ASTK-VER-1 = a) — une sortie de stock qui puise dans la QUARANTAINE (rappel, réception non conforme)
// n'est JAMAIS refusée et pose UNE note au devis qui nomme la référence et le nombre d'unités en quarantaine sorties.
// Montage (patron astk4.spec.js) : produit à stock connu, blocage de qualité posé par le service de stock, devis ACCEPTÉ de 12
// lignes-unités ; gestes par les VRAIES routes : `facturer-complet` (facture directe) et `convertir-bc` + `confirmer` +
// `marquer-livre` (« Livrer »). La note est relue par l'API du chatter ET à l'écran (liste des devis → « Historique des
// modifications »). Aucune écriture hors société de démo ; jamais la prod.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage, lireJson, listeDe, API_DJANGO as API } from '../helpers.js'

const etape = groupe('ASTK', ['ASTK250'])
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
const MOTIF = /unité\(s\) en quarantaine sorties \(rappel ou réception non conforme\)/

/** Produit à `stock` unités dont `quarantaine` bloquées, devis ACCEPTÉ de `quantite` (patron astk4.spec.js). */
async function vente({ stock, quarantaine, quantite }) {
  const m = marque()
  return py(`a = U.objects.get(username='demo_admin'); co = a.company
from decimal import Decimal as D
from apps.crm import stages
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.stock.services_wms import mettre_en_quarantaine
from apps.ventes.models import Devis, LigneDevis
p = Produit.objects.create(company=co, nom='Panneau ACC-ASTK250 ${m}', sku='ACC-ASTK250-${m}', prix_vente=D('100'), prix_achat=D('60'), quantite_stock=${stock}, tva=D('20.00'))
if ${quarantaine}:
    mettre_en_quarantaine(company=co, produit=p, quantite=${quarantaine}, user=a, motif='rappel ACC-ASTK250')
cl = Client.objects.create(company=co, nom='ACC ASTK250', prenom='${m}', email='acc-astk250-${m.toLowerCase()}@example.invalid')
kw = dict(company=co, nom='ACC ASTK250', prenom='${m}', stage=stages.SIGNED, type_installation='residentiel')
if any(f.name == 'client' for f in Lead._meta.fields): kw['client'] = cl
lead = Lead.objects.create(**kw)
d = Devis.objects.create(company=co, reference='DEV-ACC-ASTK250-${m}', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=D('20'), mode_installation='residentiel')
LigneDevis.objects.create(devis=d, produit=p, designation='Panneau ACC-ASTK250 ${m}', quantite=D('${quantite}'), prix_unitaire=D('100'), taux_tva=D('20.00'))
sortie(dict(m='${m}', produit=p.id, sku=p.sku, devis=d.id, ref=d.reference, lead=lead.id, client=cl.id))`)
}

/** Stock du produit, mouvements SORTIE, factures du devis, notes « quarantaine » du devis (relus en base). */
const etat = (x) => py(`from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_sortie
from apps.ventes.models import DevisActivity, Facture
p = Produit.objects.get(pk=${x.produit})
sortie(dict(stock=float(p.quantite_stock),
  sorties=float(sum(q for q in MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).values_list('quantite', flat=True))),
  factures=[[f.reference, f.statut] for f in Facture.objects.filter(devis_id=${x.devis}).order_by('id')],
  notes=[a.body for a in DevisActivity.objects.filter(devis_id=${x.devis}, body__contains='quarantaine')]))`)

/** Écran : liste des devis → « Plus d'actions » → « Historique des modifications » ; rend le panneau ouvert. */
async function ouvrirHistorique(page, ref) {
  await page.goto(`/ventes/devis?q=${encodeURIComponent(ref)}`)
  const bouton = page.getByRole('button', { name: `Plus d'actions — ${ref}` })
  await expect(bouton, 'liste des devis : action du devis').toBeVisible({ timeout: 60_000 })
  await bouton.click()
  await page.getByRole('menuitem', { name: 'Historique des modifications' }).click()
  const panneau = page.getByText(`Historique des modifications — ${ref}`)
  await expect(panneau, "panneau « Historique des modifications » du devis").toBeVisible({ timeout: 60_000 })
  return page.locator('tr').filter({ has: panneau })
}

etape('P5.1-ASTK250-facture-directe', ['ASTK250'], async ({ page }) => {
  const r = page.request
  // Given : produit de 15 en stock dont 10 en quarantaine, devis accepté de 12.
  const x = await vente({ stock: 15, quarantaine: 10, quantite: 12 })
  // When : la facture directe est émise (« Facturer » en un geste).
  const rep = await r.post(`${API}/ventes/devis/${x.devis}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } })
  const corpsFacture = await rep.text()
  expect(rep.status(), `facturer-complet (${corpsFacture.slice(0, 300)})`).toBeLessThan(300)
  const facture = JSON.parse(corpsFacture)
  expect(facture.statut, 'réponse de la route : facture émise').toBe('emise')
  // Then : facture ÉMISE (jamais bloquée), 12 unités sorties (stock 3), UNE note qui nomme la référence et 7 unités.
  const e = await etat(x)
  expect(e.factures.map((f) => f[1]), `facture émise (${J(e.factures)})`).toEqual(['emise'])
  expect([e.sorties, e.stock], `12 unités sorties, stock 3 (${J(e)})`).toEqual([12, 3])
  expect(e.notes, `UNE seule note de quarantaine (${J(e.notes)})`).toHaveLength(1)
  expect(e.notes[0], 'la note nomme la référence et les 7 unités en quarantaine sorties')
    .toBe(`${x.sku} : 7 unité(s) en quarantaine sorties (rappel ou réception non conforme).`)
  // Persistance : le chatter du devis relu par l'API ; la facture relue par l'API.
  const histo = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${x.devis}/historique/`, T), 'historique du devis'))
  const notes = histo.filter((a) => MOTIF.test(a.body || ''))
  expect(notes.map((a) => a.body), 'historique (API) : UNE note nommant la référence et 7').toEqual([e.notes[0]])
  const relue = await lireJson(await r.get(`${API}/ventes/factures/${facture.facture_id}/`, T), 'facture relue')
  expect(relue.statut, 'facture relue par l\'API : émise').toBe('emise')
  // Écran : la note est VISIBLE, une seule fois, dans l'historique du devis.
  const ligne = await ouvrirHistorique(page, x.ref)
  await expect(ligne.getByText(e.notes[0]), "historique à l'écran : la note de quarantaine (une seule)").toHaveCount(1, { timeout: 60_000 })
  await expect(ligne, 'la note nomme la référence').toContainText(x.sku)
  await expect(ligne, 'la note nomme les 7 unités').toContainText('7 unité(s) en quarantaine sorties')

  // Contrôle : une sortie COUVERTE par le disponible hors quarantaine ⇒ aucune note (stock 15, quarantaine 3, devis de 12 : 12 dispo).
  const y = await vente({ stock: 15, quarantaine: 3, quantite: 12 })
  const rep2 = await r.post(`${API}/ventes/devis/${y.devis}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } })
  expect(rep2.status(), `facturer-complet couverte (${(await rep2.text()).slice(0, 300)})`).toBeLessThan(300)
  const ey = await etat(y)
  expect([ey.factures.map((f) => f[1]), ey.stock, ey.notes], `sortie couverte : facture émise, stock 3, aucune note (${J(ey)})`).toEqual([['emise'], 3, []])
})

etape('P5.2-ASTK250-livrer-bc', ['ASTK250'], async ({ page }) => {
  const r = page.request
  // Même règle pour « Livrer » d'un bon de commande : stock 15 dont 10 en quarantaine, devis accepté de 12.
  const x = await vente({ stock: 15, quarantaine: 10, quantite: 12 })
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${x.devis}/convertir-bc/`, { ...T, data: {} }), 'convertir-bc')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer le BC')
  const livre = await r.post(`${API}/ventes/bons-commande/${bc.id}/marquer-livre/`, { ...T, data: {} })
  expect(livre.status(), `« Livrer » jamais refusé (${(await livre.text()).slice(0, 300)})`).toBe(200)
  expect((await livre.json()).statut, 'BC livré').toBe('livre')
  const e = await etat(x)
  expect([e.sorties, e.stock], `12 unités sorties, stock 3 (${J(e)})`).toEqual([12, 3])
  expect(e.notes, `UNE seule note de quarantaine (${J(e.notes)})`).toEqual([`${x.sku} : 7 unité(s) en quarantaine sorties (rappel ou réception non conforme).`])
  const ligne = await ouvrirHistorique(page, x.ref)
  await expect(ligne.getByText(e.notes[0]), "historique à l'écran : la note de quarantaine (une seule)").toHaveCount(1, { timeout: 60_000 })
})

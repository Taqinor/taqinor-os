// AARG (3e spec) — preuves en direct : retour d'un chantier à « Installé », écran factures sans paiement carte, relevés
// (J+7, réimport partiel), reliquat après révision, escompte en avoir. Gestes par l'API et l'écran réels ; le shell Django
// ne pose que ce qu'aucun geste ne pose (date de signature au domicile, escompte de la facture, BC rattaché à la V2).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage, uniq } from '../helpers.js'

const etape = groupe('AARG', ['AARG6', 'AARG10', 'AARG29', 'AARG33', 'AARG46', 'AARG57'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const email = () => `${uniq('aarg3').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid`
const jourIso = (decalage = 0) => new Date(Date.now() + decalage * 86_400_000).toISOString().slice(0, 10)

async function vente(request, lignes = [['Onduleur AARG', '1', '10000.00', '20.00']]) {
  const lead = await lireJson(await request.post(`${API}/crm/leads/`, { ...T, data: { nom: uniq('AARG3 Client'), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: email() } }), 'lead')
  const lignesDevis = []
  for (const [i, [d, q, pu, tva]] of lignes.entries()) {
    const p = await lireJson(await request.post(`${API}/stock/produits/`, { ...T, data: { nom: `${d} ${Date.now()}-${i}`, prix_vente: pu, prix_achat: '100.00' } }), `produit ${d}`)
    lignesDevis.push({ produit: p.id, designation: d, quantite: q, prix_unitaire: pu, remise: '0.00', taux_tva: tva, type_ligne: 'produit', ordre: i })
  }
  const devis = await lireJson(await request.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lignes: lignesDevis, lead: lead.id } }), 'devis')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await request.post(`${API}/ventes/devis/${devis.id}/accepter/`, { ...T, data: { nom: 'Client AARG' } }), 'acceptation')
  return lireJson(await request.get(`${API}/ventes/devis/${devis.id}/`, T), 'devis relu')
}
const factureComplete = async (request, d) => {
  const r = await lireJson(await request.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture complète')
  await request.post(`${API}/ventes/factures/${r.facture_id}/emettre/`, { ...T, data: {} })
  return lireJson(await request.get(`${API}/ventes/factures/${r.facture_id}/`, T), 'facture')
}
const csv = (lignes) => Buffer.from(`date;reference;montant;mode\n${lignes.join('\n')}\n`, 'utf-8')
const dryRun = async (r, buffer) => lireJson(await r.post(`${API}/ventes/paiements/import-releve/dry-run/`, { ...T, multipart: { file: { name: 'releve.csv', mimeType: 'text/csv', buffer } } }), 'dry-run')
const commit = async (r, corps) => lireJson(await r.post(`${API}/ventes/paiements/import-releve/commit/`, { ...T, data: corps }), 'commit')
const nbPaiements = (fid) => py(`from apps.ventes.models import Paiement
sortie(Paiement.objects.filter(facture_id=${fid}).count())`)

etape('PA5.retour_installe', ['AARG46'], async ({ page }) => {
  const r = page.request
  const d = await vente(r)
  const inst = await py(`from apps.installations.models import Installation
sortie(Installation.objects.get(devis_id=${d.id}).id)`)
  const etat = () => py(`from apps.installations.models import Installation
from apps.installations.services import chantiers_a_facturer
from apps.gestion_projet.models import JalonProjet
from apps.portail.models import JalonChantierPortail
from authentication.models import Company
co = Company.objects.get(pk=1)
j = JalonProjet.objects.filter(installation_id=${inst}, phase=JalonProjet.Phase.RECEPTION)
p = JalonChantierPortail.objects.filter(company=co, chantier_id=${inst}, cle_phase=JalonProjet.Phase.RECEPTION).first()
sortie(dict(n=j.count(), atteint=j.first().atteint if j.exists() else None, portail=p.atteint if p else None, a_facturer=any(c['installation_id']==${inst} for c in chantiers_a_facturer(co)), statut=Installation.objects.get(pk=${inst}).statut))`)
  const passer = (statut) => py(`from apps.installations.models import Installation
from apps.installations.services import changer_statut_chantier
changer_statut_chantier(Installation.objects.get(pk=${inst}), ${JSON.stringify(statut)}, U.objects.get(username='demo_admin'), verifier_gates=False)
sortie(1)`)
  await passer('installe')
  await passer('receptionne')
  expect(await etat(), 'réceptionné').toEqual({ n: 1, atteint: true, portail: true, a_facturer: true, statut: 'receptionne' })
  // Le geste rejoué : la route de la fiche chantier.
  const retour = await r.patch(`${API}/installations/chantiers/${inst}/`, { ...T, data: { statut: 'installe' } })
  expect(retour.status(), `retour à Installé : ${(await retour.text()).slice(0, 200)}`).toBe(200)
  expect(await etat(), 'jalon, portail et à-facturer défaits').toEqual({ n: 1, atteint: false, portail: false, a_facturer: false, statut: 'installe' })
  await passer('receptionne')
  expect(await etat(), 'nouvelle réception : un seul jalon').toEqual({ n: 1, atteint: true, portail: true, a_facturer: true, statut: 'receptionne' })
})

etape('P.factures_sans_carte', ['AARG10'], async ({ page }) => {
  const r = page.request
  const d = await vente(r, [['Prestation AARG10', '1', '1000.00', '20.00']])
  const f = await factureComplete(r, d)
  expect(f.statut, 'facture émise').toBe('emise')
  const appels = []
  page.on('request', (q) => { if (q.url().includes('/core/paiements-en-ligne')) appels.push(q.url()) })
  await page.goto('/ventes/factures')
  await page.getByPlaceholder(/Rechercher/).first().fill(f.reference, { timeout: 60_000 })
  const ligne = page.locator('tr', { hasText: f.reference }).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByRole('button', { name: /actions|plus|menu|⋯|…/i }).first().click()
  await expect(page.getByRole('menuitem', { name: /Payer en ligne/ }).or(page.getByRole('button', { name: /Payer en ligne/ })).first(), '« Payer en ligne » reste').toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Demander un paiement carte'), 'entrée retirée').toHaveCount(0)
  expect(appels, 'aucun appel paiements-en-ligne').toEqual([])
})

etape('PA4.08.reimport_partiel', ['AARG33'], async ({ page }) => {
  const r = page.request
  const A = await factureComplete(r, await vente(r, [['Prestation AARG33 A', '1', '1000.00', '20.00']]))
  const B = await factureComplete(r, await vente(r, [['Prestation AARG33 B', '1', '2000.00', '20.00']]))
  const jour = jourIso()
  const fichier = csv([`${jour};${A.reference};1200.00;virement`, `${jour};${B.reference};2400.00;virement`])
  const d1 = await dryRun(r, fichier)
  const ligneA = d1.preview.find((l) => l.reference === A.reference)
  const c1 = await commit(r, { token: d1.token, lignes: [ligneA.ligne] })
  expect(c1.created, 'premier commit limité à A').toBe(1)
  expect(await nbPaiements(A.id), 'A payée').toBe(1)
  const d2 = await dryRun(r, fichier)
  const statutA = d2.preview.find((l) => JSON.stringify(l).includes(A.reference)).statut
  expect(statutA, 'ligne A : déjà importée').toMatch(/deja_importe|doublon_import/)
  const c2 = await commit(r, { token: d2.token })
  expect(c2.created, 'réimport : B seule').toBe(1)
  const c3 = await commit(r, { token: (await dryRun(r, fichier)).token }).catch((e) => ({ erreur: String(e) }))
  expect(c3.created ?? 0, `3e import : rien (${JSON.stringify(c3).slice(0, 200)})`).toBe(0)
  expect([await nbPaiements(A.id), await nbPaiements(B.id)], 'un paiement par ligne').toEqual([1, 1])
})

etape('PA4.08.j7_domicile', ['AARG6'], async ({ page }) => {
  const r = page.request
  const acompteDomicile = async (jours) => {
    const d = await vente(r, [['Prestation AARG6', '1', '2500.00', '20.00']])
    const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC')
    await py(`from apps.ventes.models import BonCommande
BonCommande.objects.filter(pk=${bc.id}).update(signe_au_domicile=True, date_signature_domicile=timezone.localdate() - datetime.timedelta(days=${jours}))
sortie(1)`)
    const ac = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer/`, { ...T, data: { nature: 'acompte', emettre: true } }), 'acompte')
    return lireJson(await r.get(`${API}/ventes/factures/${ac.facture.id}/`, T), 'acompte relu')
  }
  const f = await acompteDomicile(3)
  const fichier = (ref, m) => csv([`${jourIso()};${ref};${m};virement`])
  const ap = await dryRun(r, fichier(f.reference, f.total_ttc))
  expect(ap.preview[0].statut, 'aperçu').toBe('non_encaissable')
  expect(ap.preview[0].motif, 'motif nommé').toContain('Acompte non encaissable avant le')
  const c = await commit(r, { token: ap.token }).catch((e) => ({ erreur: String(e) }))
  expect(c.created ?? 0, 'commit : 0 créé').toBe(0)
  expect(await nbPaiements(f.id), '0 Paiement').toBe(0)
  expect((await lireJson(await r.get(`${API}/ventes/factures/${f.id}/`, T), 'relue')).statut, 'facture toujours émise').toBe('emise')
  const g = await acompteDomicile(8)
  const ap2 = await dryRun(r, fichier(g.reference, g.total_ttc))
  expect((await commit(r, { token: ap2.token })).created, 'J+8 : créé').toBe(1)
  expect(await nbPaiements(g.id)).toBe(1)
})

etape('PA4.03.reliquat_revision', ['AARG29'], async ({ page }) => {
  const r = page.request
  const d = await vente(r, [['Panneau AARG29', '10', '900.00', '20.00'], ['Onduleur AARG29', '1', '7000.00', '20.00']])
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  const pan = d.lignes.find((l) => l.designation === 'Panneau AARG29')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/livrer-partiel/`, { ...T, data: { lignes: [{ ligne_devis: pan.id, quantite: '6' }] } }), 'livraison partielle')
  // V2 réelle (route de révision), 12 panneaux, puis le BC rattaché à la révision comme à sa conversion.
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/reviser/`, { ...T, data: {} }), 'révision V2')
  await py(`from apps.ventes.models import Devis, LigneDevis, BonCommande
v2 = Devis.objects.get(pk=${v2.id})
LigneDevis.objects.filter(devis=v2, designation='Panneau AARG29').update(quantite=12)
Devis.objects.filter(pk=v2.pk).update(statut='accepte')
BonCommande.objects.filter(pk=${bc.id}).update(devis=v2)
sortie(1)`)
  const relu = await lireJson(await r.get(`${API}/ventes/bons-commande/${bc.id}/`, T), 'BC relu')
  const reste = Object.fromEntries(relu.reliquat_par_ligne.map((x) => [x.designation, [Number(x.quantite_commandee), Number(x.quantite_livree), Number(x.reliquat)]]))
  expect(reste['Panneau AARG29'], 'panneaux 12 / 6 / 6').toEqual([12, 6, 6])
  expect(reste['Onduleur AARG29'], 'onduleur 1 / 0 / 1').toEqual([1, 0, 1])
  expect(relu.est_partiellement_livre, 'partiellement livré').toBe(true)
})

etape('PA4.11.escompte_avoir', ['AARG57'], async ({ page }) => {
  const r = page.request
  const f = await factureComplete(r, await vente(r, [['Prestation AARG57', '1', '1000.00', '20.00']]))
  await py(`from apps.ventes.models import Facture
Facture.objects.filter(pk=${f.id}).update(escompte_pct=2, escompte_jours=10)
sortie(1)`)
  const p = await lireJson(await r.post(`${API}/ventes/factures/${f.id}/enregistrer-paiement/`, {
    ...T, data: { montant: '1176.00', mode: 'virement', date_paiement: jourIso() },
  }), 'paiement net')
  expect(Number(p.montant ?? p.paiement?.montant), 'paiement 1 176').toBe(1176)
  const e = await py(`from apps.ventes.models import Facture, Paiement
f = Facture.objects.get(pk=${f.id})
pa = Paiement.objects.filter(facture=f).order_by('-pk').first()
av = list(Facture.objects.filter(company_id=1, devis_id=f.devis_id, type_facture='avoir').values('total_ht', 'total_tva', 'total_ttc'))
sortie(dict(statut=f.statut, escompte=str(pa.escompte_montant or 0), avoirs=av))`)
  expect(Number(e.escompte), 'paiement sans escompte_montant').toBe(0)
  expect(e.statut, 'facture payée').toBe('payee')
  expect(e.avoirs.length, 'un avoir').toBe(1)
  expect(e.avoirs.map((a) => [Math.abs(Number(a.total_ht)), Math.abs(Number(a.total_tva)), Math.abs(Number(a.total_ttc))])[0], 'avoir 20 HT, 4 TVA, 24 TTC').toEqual([20, 4, 24])
  const rel = listeDe(await lireJson(await r.get(`${API}/ventes/factures/${f.id}/paiements/`, T), 'paiements'))
  expect(rel.length, 'relecture : un paiement').toBe(1)
})

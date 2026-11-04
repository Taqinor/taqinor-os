// ADVS (3e spec) — preuves en direct : arrondi à la centaine, PDF de partage signable, TVA société à la composition, total
// « Les deux » du générateur, garde de dés-acceptation sur un BCF envoyé.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, textePdf } from '../helpers.js'

const etape = groupe('ADVS', ['ADVS3', 'ADVS14', 'ADVS40'])
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
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const emailEssai = () => `advs3${marque()}@example.invalid`
const nouveauLead = async (r, nom, extra = {}) => lireJson(await r.post(`${API}/crm/leads/`, {
  ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: emailEssai(), ...extra },
}), 'lead')
const produit = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
const ligne = (p, q, pu, ordre = 0) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: pu, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
async function devisStandard(r, tag) {
  const m = marque()
  const lead = await nouveauLead(r, `ADVS ${tag} ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produit(r, `Panneau mono 550W ${m}`, '1000.00')
  const ond = await produit(r, `Onduleur réseau 10kW ${m}`, '10000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, 12, '1000.00'), ligne(ond, 1, '10000.00', 1)] } }), 'devis')
  return { lead, d, m }
}

etape('PA3-01.arrondi_centaine', ['ADVS3'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await nouveauLead(r, `ADVS3 ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const pan = await produit(r, `Panneau mono 550W ${m}`, '833.33')
  const creer = (q, pu) => lireJson(r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes: [ligne(pan, q, pu)] } }), 'devis')
  const d = await creer(3, '833.33')
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'relu')
  expect(Number(relu.total_ttc), '3 × 1 000 TTC → 3 000, jamais 2 900').toBe(3000)
  const ht = Number(relu.total_ht_net ?? relu.total_ht)
  const tva = Number(relu.total_tva ?? relu.tva)
  expect(Math.round((ht + tva) * 100), 'ht_net + tva == ttc au centime').toBe(300000)
  const lignes = relu.lignes
  expect(Number(lignes[0].prix_unitaire), 'aucune ligne repricée').toBeCloseTo(833.33, 2)
  // Témoin : un total franchement sous la centaine reste ramené à la centaine inférieure.
  const d2 = await creer(1, '2464.17')
  expect(Number((await lireJson(await r.get(`${API}/ventes/devis/${d2.id}/`, T), 'relu 2')).total_ttc), '2 957 → 2 900 inchangé').toBe(2900)
})

etape('PA3-02.pdf_partage_signable', ['ADVS14'], async ({ page }) => {
  const r = page.request
  const { d } = await devisStandard(r, 'ADVS14')
  const rendu = await r.get(`${API}/ventes/devis/${d.id}/pdf-partage/`, T)
  expect(rendu.status(), `pdf-partage : ${rendu.status()}`).toBe(200)
  expect(rendu.headers()['content-type'], 'un PDF').toContain('pdf')
  const pdf = await rendu.body()
  const txt = await textePdf(pdf)
  expect(txt, 'prix d\'achat jamais imprimé').not.toContain('111,11')
  expect(txt, 'libellé de signature au PDF').toMatch(/signer/i)
  // Le rendu partagé reçoit le jeton de `ShareLink.for_devis` (même espion que le plan : ce qu'on passe au moteur).
  const vu = await py(`from unittest import mock
from rest_framework.test import APIClient
from apps.ventes.models import ShareLink, Devis
import apps.ventes.quote_engine as q
orig = q.generate_premium_devis_pdf
capt = {}
def espion(devis_id, opts=None, **k):
    capt['token'] = (opts or {}).get('share_token'); capt['persist'] = k.get('persist'); return orig(devis_id, opts, **k)
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
with mock.patch.object(q, 'generate_premium_devis_pdf', espion):
    rep = c.get('/api/django/ventes/devis/${d.id}/pdf-partage/', HTTP_HOST='localhost')
sortie(dict(code=rep.status_code, token=capt.get('token'), persist=capt.get('persist'), lien=ShareLink.for_devis(Devis.objects.get(pk=${d.id})).token))`)
  expect(vu.code).toBe(200)
  expect(vu.token, 'rendu avec le jeton du lien de partage').toBe(vu.lien)
  expect(vu.persist, 'persist=False').toBe(false)
  // GET n'a rien marqué envoyé.
  expect((await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'relu')).statut, 'rendu sans effet').toBe('brouillon')
})

etape('PA3-13.bcf_envoye_bloque', ['ADVS40'], async ({ page }) => {
  const r = page.request
  const { d, lead } = await devisStandard(r, 'ADVS40')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADVS40' } }), 'acceptation')
  const bcf = await py(`from apps.installations.models import Installation
from apps.achats.models import BonCommandeFournisseur as B
from apps.stock.models import Fournisseur
i = Installation.objects.get(devis_id=${d.id})
fr = Fournisseur.objects.filter(company_id=1).first()
b = B.objects.create(company_id=1, fournisseur=fr, reference='BCF-ADVS40-${d.id}', statut='envoye', chantier_origine=i)
sortie(dict(id=b.id, ref=b.reference))`)
  const sortir = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'CONTACTED' } })
  expect(sortir.status(), `sortie de Signé : ${(await sortir.text()).slice(0, 300)}`).toBe(409)
  expect(await sortir.text(), 'nomme le BCF').toContain(bcf.ref)
  expect((await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'relu')).statut, 'devis inchangé').toBe('accepte')
  expect((await lireJson(await r.get(`${API}/crm/leads/${lead.id}/`, T), 'lead')).stage, 'lead toujours Signé').toBe('SIGNED')
  // Témoin : BCF annulé, plus de blocage.
  await py(`from apps.achats.models import BonCommandeFournisseur as B
B.objects.filter(pk=${bcf.id}).update(statut='annule')
sortie(1)`)
  const ok = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'CONTACTED' } })
  expect(ok.status(), `BCF annulé : ${(await ok.text()).slice(0, 200)}`).toBe(200)
})

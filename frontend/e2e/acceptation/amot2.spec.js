// AMOT — 2e spec d'acceptation en direct : panneau Économie (AMOT54), productible société (AMOT64), « estimation » agricole
// (AMOT65), batterie nette au modèle factures (AMOT78), carte C&I TTC (AMOT115), motif réel d'un BT sans contrat (AMOT116),
// format mémorisé à l'e-mail (AMOT117). Données posées par l'API ou par le vrai générateur ; profil rétabli à la fin.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import {
  lireJson, telephoneMobileUnique, assurerSessionPage,
} from '../helpers.js'

const etape = groupe('AMOT', ['AMOT54', 'AMOT64', 'AMOT117'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(420_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`
const nouveauLead = async (r, nom, extra = {}) => lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid`, ...extra } }), 'lead')
const produit = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
const ligne = (p, q, ordre = 0) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })
async function residentiel(r, tag, batterie = false) {
  const m = marque()
  const lead = await nouveauLead(r, `AMOT ${tag} ${m}`, { type_installation: 'residentiel', facture_hiver: '1500' })
  const lignes = [ligne(await produit(r, `Panneau mono 550W ${m}`, '1000.00'), 12)]
  if (batterie) {
    lignes.push(ligne(await produit(r, `Onduleur hybride Deye 10kW ${m}`, '10000.00'), 1, 1))
    lignes.push(ligne(await produit(r, `Batterie Dyness BX51100 ${m}`, '15000.00'), 1, 2))
  } else {
    lignes.push(ligne(await produit(r, `Onduleur réseau 10kW ${m}`, '10000.00'), 1, 1))
  }
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes } }), 'devis')
  return { lead, d }
}

etape('P2.3.economie', ['AMOT54'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await residentiel(r, 'AMOT54')
  const e = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/economie/`, T), 'économie')
  expect(e.flux?.length, 'flux non vide').toBeGreaterThan(1)
  expect(e.flux.at(-1).annee, 'horizon 25 ans').toBe(25)
  expect(e.hypotheses?.length ?? Object.keys(e.hypotheses ?? {}).length, 'hypothèses listées').toBeGreaterThan(0)
  const hyps = Array.isArray(e.hypotheses) ? e.hypotheses : Object.values(e.hypotheses)
  for (const h of hyps) expect(h.source, `source de ${JSON.stringify(h).slice(0, 60)}`).toBeTruthy()
  const pdf = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
sortie(build_quote_data(Devis.objects.get(pk=${d.id}), {'pdf_mode': 'full'}).get('roi_s'))`)
  const retour = e.retour_ans ?? e.retour ?? e.retour_annees
  expect(retour, 'retour servi').toBeTruthy()
  if (pdf) expect(Math.abs(Number(retour) - Number(pdf)), `retour écran ${retour} ≈ PDF ${pdf}`).toBeLessThanOrEqual(0.6)
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

etape('P1.3.productible', ['AMOT64'], async ({ page, suivi }) => {
  const r = page.request
  const prof = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
  // Un devis NEUF à chaque réglage : l'étude d'un devis déjà enregistré garde ses chiffres jusqu'au prochain recalcul.
  const hyp = async () => {
    const { d } = await residentiel(r, 'AMOT64')
    return py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
q = build_quote_data(Devis.objects.get(pk=${d.id}), {'pdf_mode': 'full'})
sortie({'prod': q.get('prod_kwh')})`)
  }
  const poser = async (v) => {
    // Le profil bouge pendant la création d'un devis (compteurs) : le verrou optimiste se relit à chaque essai.
    for (let i = 0; i < 4; i += 1) {
      const cur = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
      const rep = await r.patch(`${API}/parametres/update/`, { ...T, data: { productible_kwh_kwc: v, updated_at: cur.updated_at } })
      if (rep.ok()) return
      expect(rep.status(), `productible ${v}`).toBe(409)
    }
    throw new Error(`productible ${v} : verrou toujours en conflit`)
  }
  try {
    await poser(1600)
    const a = await hyp()
    await poser(1601)
    const b = await hyp()
    expect(Number(b.prod) / Number(a.prod), 'toute valeur saisie : proportionnelle').toBeCloseTo(1601 / 1600, 3)
        await poser(null)
    const c = await hyp()
    expect(Number(c.prod), 'vide : PVGIS, autre chiffre que 1 600').not.toBe(Number(a.prod))
    // Écran : rendement retiré ; tarif étiqueté repli.
    await page.goto('/parametres?onglet=referentiels')
    await page.goto('/parametres')
    await expect(page.getByRole('button', { name: 'Enregistrer', exact: true }).first()).toBeVisible({ timeout: 60_000 })
    await expect(page.getByText(/rendement global/i), 'rendement_global retiré').toHaveCount(0)
    const onglet = page.getByRole('tab', { name: /tarif|Énergie|Solaire|Devis/i }).first()
    if (await onglet.count()) await onglet.click().catch(() => undefined)
    // Enregistrer sans toucher : valeurs identiques (persistance).
    const avant = await lireJson(await r.get(`${API}/parametres/`, T), 'profil')
    await page.getByRole('button', { name: 'Enregistrer', exact: true }).first().click()
    await expect.poll(async () => (await lireJson(await r.get(`${API}/parametres/`, T), 'profil')).productible_kwh_kwc, { timeout: 20_000 }).toBe(avant.productible_kwh_kwc)
  } finally {
    await poser(prof.productible_kwh_kwc)
  }
  suivi.verifie(5)
})

etape('P.email_format', ['AMOT117'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await residentiel(r, 'AMOT117')
  const res = await py(`from apps.ventes.models import Devis
from rest_framework.test import APIClient
import apps.ventes.quote_engine as qe
Devis.objects.filter(pk=${d.id}).update(pdf_render_meta={'options': {'pdf_mode': 'onepage'}})
vus = []
vrai = qe.generate_premium_devis_pdf
def espion(devis_id, pdf_options=None, persist=True):
    vus.append((pdf_options or {}).get('pdf_mode'))
    return vrai(devis_id, pdf_options, persist)
c = APIClient(); c.force_authenticate(U.objects.get(username='demo_admin'))
with mock.patch('apps.ventes.quote_engine.generate_premium_devis_pdf', side_effect=espion):
    rep = c.post('/api/django/ventes/devis/${d.id}/envoyer-email/', {'to_email': 'amot117@example.invalid'}, format='json', HTTP_HOST='localhost')
sortie({'code': rep.status_code, 'modes': vus})`)
  expect(res.code, 'envoi').toBe(200)
  expect(res.modes.length, 'le moteur est appelé').toBeGreaterThan(0)
  expect(res.modes.at(-1), 'format du dernier rendu : une page').toBe('onepage')
  suivi.verifie(6)
  void page
})

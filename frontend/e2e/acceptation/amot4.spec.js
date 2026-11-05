// Rejeu en direct d'AMOT125 (lot 7) : le payback horaire « avec batterie » du générateur suit le niveau de règles du
// devis — un devis d'origine (`regles_calcul = 1`) affiche le payback que son PDF `/proposal` imprime. Devis posé par
// la vraie route ; niveau d'origine posé en base (c'est le Given : un devis ancien), PDF lu par la vraie route.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'
import { pdfTexte } from './_ci.js'

const etape = groupe('AMOT', ['AMOT125'])
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
const produit = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom, prix_vente: pv, prix_achat: '111.11' } }), 'produit')
const ligne = (p, q, ordre = 0) => ({ produit: p.id, designation: p.nom, quantite: String(q), prix_unitaire: p.prix_vente, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre })

etape('V4.125', ['AMOT125'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AMOT125 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `amot125_${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '1500' } }), 'lead')
  const lignes = [
    ligne(await produit(r, `Panneau mono 550W ${m}`, '1000.00'), 12),
    ligne(await produit(r, `Onduleur hybride Deye 10kW ${m}`, '10000.00'), 1, 1),
    ligne(await produit(r, `Batterie Dyness BX51100 5.12kWh ${m}`, '15000.00'), 1, 2),
  ]
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', lignes } }), 'devis')
  // L'étude horaire du devis est posée par le générateur lui-même (« Enregistrer les modifications »), comme pour
  // tout devis réel : le PDF chiffre alors la même étude que l'écran.
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  await expect.poll(async () => {
    const v = await page.locator('[data-figure="payback_ans"][data-figure-option="avec"]').first().getAttribute('data-figure-value').catch(() => null)
    return v && /\d/.test(v) ? v : null
  }, { timeout: 180_000, message: 'étude chiffrée à l\'écran' }).not.toBeNull()
  const figures = (pg) => pg.locator('[data-figure]').evaluateAll((xs) => xs.map((x) => [x.dataset.figure, x.dataset.figureOption, x.dataset.figureValue]))
  console.log('[V4.125] figures devis neuf (règles courantes)', JSON.stringify(await figures(page)))
  const etude = page.waitForResponse((x) => x.request().method() === 'PATCH' && new RegExp(`/ventes/devis/${d.id}/etude-params/?$`).test(new URL(x.url()).pathname), { timeout: 120_000 })
  await page.getByRole('button', { name: /Enregistrer les modifications/ }).click()
  expect((await etude).status(), 'étude enregistrée').toBeLessThan(300)
  // Le Given : un devis d'ORIGINE (niveau 1). Chiffres du PDF à ce niveau, et aux règles courantes pour témoin.
  const chiffres = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
Devis.objects.filter(pk=${d.id}).update(regles_calcul=1)
d = Devis.objects.get(pk=${d.id})
q1 = build_quote_data(d, {'pdf_mode': 'full'})
courant = Devis._meta.get_field('regles_calcul').default
d.regles_calcul = courant() if callable(courant) else courant
qc = build_quote_data(d, {'pdf_mode': 'full'})
cles = ('roi_a', 'roi_s', 'eco_a_ann', 'eco_s_ann', 'prod_kwh', 'autoconso_avec', 'autoconso_sans', 'total_avec')
sortie({'pdf_niveau1': {k: q1.get(k) for k in cles}, 'pdf_courant': {k: qc.get(k) for k in cles},'roi_a': q1.get('roi_a'), 'net_gain_avec': q1.get('net_gain_avec'), 'roi_a_courant': qc.get('roi_a'), 'niveau_courant': d.regles_calcul, 'niveau': Devis.objects.get(pk=${d.id}).regles_calcul})`)
  console.log(`[V4.125] ${JSON.stringify(chiffres)}`)
  expect(chiffres.niveau, 'devis au niveau 1').toBe(1)
  expect(Number(chiffres.roi_a), 'payback « avec » du PDF chiffré').toBeGreaterThan(0)
  // Générateur : la carte ROI « Avec batterie » (ancre `payback_ans` / `avec`) = le payback du PDF.
  const p2 = suivi.surveiller(await page.context().newPage())
  await p2.goto(`/ventes/devis/nouveau?edit=${d.id}`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  const ancre = p2.locator('[data-figure="payback_ans"][data-figure-option="avec"]')
  await expect.poll(async () => {
    const v = await ancre.first().getAttribute('data-figure-value').catch(() => null)
    return v && /\d/.test(v) ? v : null
  }, { timeout: 180_000, message: 'payback « avec » affiché' }).not.toBeNull()
  // AMOT127 — l'écran converge (miroir local `computeROI` → étude horaire serveur, convention de
  // figures-parite.spec.js) : comparer au PDF seulement une fois les cartes servies par le moteur horaire.
  await expect(p2.getByTestId('bandeau-modele-cartes'), 'cartes chiffrées par le moteur horaire serveur').toBeVisible({ timeout: 180_000 })
  const nombre = async (sel) => Number(String(await p2.locator(sel).first().getAttribute('data-figure-value')).replace(/\s/g, '').replace(',', '.').match(/[\d.]+/)?.[0])
  await expect.poll(() => nombre('[data-figure="production_annuelle_kwh"]'), { timeout: 30_000, message: `production écran = PDF ${chiffres.pdf_niveau1?.prod_kwh}` }).toBe(Number(chiffres.pdf_niveau1?.prod_kwh))
  console.log('[V4.125] figures devis niveau 1', JSON.stringify(await figures(p2)))
  await expect.poll(async () => Math.abs(await nombre('[data-figure="payback_ans"][data-figure-option="avec"]') - Number(chiffres.roi_a)), { timeout: 30_000, message: `écran = PDF niveau 1 ${chiffres.roi_a} (règles courantes : ${chiffres.roi_a_courant})` }).toBeLessThanOrEqual(0.05)
  // Le PDF `/proposal` imprime ce même payback.
  const texte = await pdfTexte(r, d.id)
  const affiche = String(chiffres.roi_a)
  expect(texte.includes(affiche) || texte.includes(affiche.replace('.', ',')), `PDF /proposal imprime ${affiche}`).toBe(true)
})

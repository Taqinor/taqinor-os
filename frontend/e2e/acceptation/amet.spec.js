// AMET — spec d'acceptation en direct : brouillon d'acompte automatique à l'acceptation, défait par la dés-acceptation (AMET4).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AMET', ['AMET4'])
const API = '/api/django'
const T = { timeout: 120_000 }
test.beforeEach(async ({ page }, testInfo) => {
  testInfo.setTimeout(300_000)
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

etape('PA4.1', ['AMET4'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AMET4 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur AMET4 ${m}`, prix_vente: '10000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id,
      echeancier: [{ libelle: 'Acompte', type: 'acompte', unite: 'pct', pct_or_montant: 30 }, { libelle: 'Livraison', type: 'materiel', unite: 'pct', pct_or_montant: 60 }, { libelle: 'Solde', type: 'solde', unite: 'pct', pct_or_montant: 10 }],
      lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }],
    },
  }), 'devis 12 000 TTC, 30/60/10')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AMET4' } }), 'accepter')
  const acomptes = async () => listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${d.id}&page_size=50`, T), 'factures')).filter((f) => f.devis === d.id && f.type_facture === 'acompte' && f.statut !== 'annulee')
  await expect.poll(async () => (await acomptes()).length, { timeout: 60_000, intervals: [1_000, 2_000] }).toBe(1)
  const [f] = await acomptes()
  expect(f.statut, 'brouillon').toBe('brouillon')
  expect(Number(f.total_ttc), '30 % de 12 000').toBeCloseTo(3600, 2)
  // Écran Factures : présent ; modifiable (PATCH brouillon comme tout brouillon).
  await page.goto(`/ventes/factures?q=${encodeURIComponent(f.reference)}`)
  await expect(page.getByText(f.reference).first(), 'présent dans Factures').toBeVisible({ timeout: 60_000 })
  await page.reload()
  await expect(page.getByText(f.reference).first()).toBeVisible({ timeout: 60_000 })
  // Dés-accepter le lead : le brouillon disparaît des pièces vivantes (annulé, sa référence reste tracée — AARG26).
  const des = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'QUOTE_SENT', confirme_recul: true } })
  expect(des.status(), `dés-accepter (${(await des.text()).slice(0, 160)})`).toBe(200)
  await expect.poll(async () => (await acomptes()).length, { timeout: 60_000, intervals: [1_000, 2_000] }).toBe(0)
  // Second signal : pas de double à la ré-acceptation.
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AMET4' } }), 'ré-accepter')
  await expect.poll(async () => (await acomptes()).length, { timeout: 60_000 }).toBe(1)
  // Émise, elle bloque la dés-acceptation en 409.
  const [f2] = await acomptes()
  const modif = await r.patch(`${API}/ventes/factures/${f2.id}/`, { ...T, data: { notes: `AMET4 ${m}` } })
  expect(modif.status(), `brouillon modifiable comme tout brouillon (${(await modif.text()).slice(0, 120)})`).toBe(200)
  await lireJson(await r.post(`${API}/ventes/factures/${f2.id}/emettre/`, { ...T, data: {} }), 'émettre')
  const bloque = await r.patch(`${API}/crm/leads/${lead.id}/`, { ...T, data: { stage: 'QUOTE_SENT', confirme_recul: true } })
  expect(bloque.status(), 'facture émise : 409').toBe(409)
  suivi.verifie(5)
})

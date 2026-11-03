// AFAC — 2e spec d'acceptation en direct : total TTC servi après « Créer la facture » depuis un BC (AFAC105). AFAC106 exige un `seed_demo` neuf : non jouable sur une pile partagée.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { lireJson, listeDe, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('AFAC', ['AFAC105'])
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

etape('AFAC67', ['AFAC105'], async ({ page, suivi }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AFAC105 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur AFAC105 ${m}`, prix_vente: '5000.00', prix_achat: '111.11', quantite_stock: 10 } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '2', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AFAC105' } }), 'accepter')
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  // Écran : nouvelle facture → ce BC → « Créer la facture depuis ce BC ».
  const relu = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  await page.goto('/ventes/factures')
  await page.getByRole('button', { name: /Nouvelle facture/ }).first().click({ timeout: 90_000 })
  const client = page.locator('#fc-client')
  await expect(client).toBeVisible({ timeout: 60_000 })
  await client.click()
  await page.keyboard.type(String(relu.client_nom ?? `AFAC105 ${m}`).slice(0, 18))
  await page.getByRole('option').filter({ hasText: m }).first().click({ timeout: 60_000 })
  await page.locator('#fc-bc').click()
  await page.getByRole('option').filter({ hasText: bc.reference }).first().click({ timeout: 60_000 })
  await page.getByRole('button', { name: 'Créer la facture depuis ce BC' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'identique au devis signé' }).first(), 'le TTC servi').toContainText(/Total TTC\s*12\s?000,00/, { timeout: 90_000 })
  const factures = listeDe(await lireJson(await r.get(`${API}/ventes/factures/?devis=${d.id}&page_size=50`, T), 'factures')).filter((f) => f.devis === d.id && f.bon_commande === bc.id)
  expect(factures.length, 'facture créée').toBeGreaterThan(0)
  expect(Number(factures.at(-1).total_ttc), 'rouverte : 12 000 TTC').toBeCloseTo(12000, 2)
  suivi.verifie(5)
})

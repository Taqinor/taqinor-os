// ATOT53 — rejeu des écarts de la contre-visite du 01/11/2026 : les six sondes commitées (`C-ATOT-VER-002` à `-007`,
// transaction annulée) et l'écran de la liste des BC (étape 2). La bande `/proposition` (Astro, hors pile docker) se lit par la
// sonde de son contrat ; l'admin Django (étape 7) a sa preuve du 01/11 (`ATOT/2026-11-01-15ebadca5`, P7) : non rejouée ici.
import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { groupe } from './_oracles.js'
import { RACINE } from './_enregistrement.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ATOT', ['ATOT53'])
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

for (const n of ['002', '003', '004', '006', '007']) {
  etape(`S-${n}`, ['ATOT53'], async () => {
    const s = spawnSync('python', ['scripts/sonde.py', `ATOT/C-ATOT-VER-${n}`], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
    expect(s.stdout, s.stderr?.slice(-300)).toContain('"repro": false')
  })
}

// (5) — révision à taux opposés : le « repro » de la sonde date d'avant D-ATOT-VER-2 (« TVA ≠ 3 000 ») ; la décision veut DEUX
// documents : complément 24 000 TTC à 20 % (TVA 4 000), puis avoir 11 000 confirmé. On lit donc les chiffres, pas le verdict.
etape('S-005', ['ATOT53'], async () => {
  const s = spawnSync('python', ['scripts/sonde.py', 'ATOT/C-ATOT-VER-005'], { cwd: RACINE, encoding: 'utf8', maxBuffer: 50_000_000, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } })
  expect(s.stdout, 'complément 24 000 TTC').toMatch(/complement_ttc\W+24000\.00/)
  expect(s.stdout, 'à 20 %, TVA 4 000').toMatch(/complement_tva\W+4000\.00/)
})

// ── (2) — BC d'un devis déjà facturé : plus de bouton « Facture » qui répondrait 409 ─────────────────
etape('E2.bc_facture', ['ATOT53'], async ({ page, suivi }) => {
  const r = page.request
  const m = `${Date.now().toString(36)}`
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ATOT53 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ATOT53 ${m}`, prix_vente: '5000.00', prix_achat: '111.11', quantite_stock: 10 } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '2', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ATOT53' } }), 'accepter')
  const bc = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/convertir-bc/`, { ...T, data: {} }), 'BC')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/confirmer/`, { ...T, data: {} }), 'confirmer')
  await lireJson(await r.post(`${API}/ventes/bons-commande/${bc.id}/creer-facture/`, { ...T, data: {} }), 'facture du BC')
  await page.goto(`/ventes/bons-commande?q=${encodeURIComponent(bc.reference)}`)
  const rangee = page.getByRole('row').filter({ hasText: bc.reference }).first()
  await expect(rangee).toBeVisible({ timeout: 60_000 })
  await expect(rangee.getByRole('button', { name: /^Facture$/ }), 'aucun bouton qui répond 409').toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('row').filter({ hasText: bc.reference }).first().getByRole('button', { name: /^Facture$/ })).toHaveCount(0, { timeout: 60_000 })
  suivi.verifie(5)
})

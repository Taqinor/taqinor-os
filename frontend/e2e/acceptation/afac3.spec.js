// AFAC103 — le dialogue d'annulation ne propose comme cibles du transfert d'acompte que les factures que le serveur accepte.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage, uniq } from '../helpers.js'

const etape = groupe('AFAC', ['AFAC103'])
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
const jour = () => new Date().toISOString().slice(0, 10)

async function devisAccepte(r, cible, ttcHt) {
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Prestation AFAC103 ${Date.now()}`, prix_vente: ttcHt, prix_achat: '100.00' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', ...cible, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: ttcHt, remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client AFAC103' } }), 'acceptation')
  return lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
}
// Factures de même devis posées par le shell (une vente réelle n'en laisse qu'une ouverte à la fois : c'est le Given du plan).
const facture = (devisId, reference, ttc) => py(`from apps.ventes.models import Devis, Facture
from decimal import Decimal as D
d = Devis.objects.get(pk=${devisId})
ttc = D('${ttc}'); ht = (ttc / D('1.2')).quantize(D('0.01'))
f = Facture.objects.create(company_id=1, devis=d, client=d.client, reference=${JSON.stringify(reference)}, statut='emise', type_facture='acompte', total_ht=ht, total_tva=ttc-ht, total_ttc=ttc, date_emission=timezone.localdate())
sortie(f.id)`)

etape('P103.1', ['AFAC103'], async ({ page }) => {
  const r = page.request
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: uniq('AFAC103'), ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${uniq('afac').toLowerCase().replace(/[^a-z0-9]/g, '')}@example.invalid` } }), 'lead')
  const d1 = await devisAccepte(r, { lead: lead.id }, '10000.00')
  const d2 = await devisAccepte(r, { client: d1.client }, '16666.67')
  const m = uniq('A103').replace(/[^A-Za-z0-9]/g, '').slice(-8)
  const F = await facture(d1.id, `FAC-F-${m}`, '12000.00')
  const G = await facture(d1.id, `FAC-G-${m}`, '8000.00')
  const H = await facture(d2.id, `FAC-H-${m}`, '20000.00')
  await facture(d1.id, `FAC-K-${m}`, '3000.00')
  await lireJson(await r.post(`${API}/ventes/factures/${F}/enregistrer-paiement/`, { ...T, data: { montant: '5000.00', date_paiement: jour(), mode: 'virement', reference: `VIR-${m}` } }), 'paiement F')
  await page.goto('/ventes/factures')
  await page.getByPlaceholder('Référence, client').fill(m)
  const ligne = page.locator(`#facture-row-${F}`).first()
  await expect(ligne).toBeVisible({ timeout: 60_000 })
  await ligne.getByTitle("Plus d'actions").click()
  await page.getByTestId('annuler-facture').click()
  const dlg = page.getByRole('dialog').filter({ hasText: `Annuler la facture FAC-F-${m}` })
  await expect(dlg).toBeVisible({ timeout: 30_000 })
  await dlg.getByRole('radio', { name: /Transférer/ }).check()
  const select = dlg.getByLabel('Facture cible')
  await expect(select).toBeVisible()
  const options = await select.locator('option').evaluateAll((o) => o.map((x) => ({ v: x.value, t: x.textContent })).filter((x) => x.v))
  expect(options.map((o) => Number(o.v)), `seule G : ni H (autre devis), ni K (doit moins que l'acompte) (${JSON.stringify(options)})`).toEqual([G])
  // Le serveur reste seul juge : G accepté, H refusé.
  const refus = await r.post(`${API}/ventes/factures/${F}/annuler/`, { ...T, data: { acompte: { action: 'transferer', facture_cible: H } } })
  expect(refus.status(), 'H refusée par le serveur').toBeGreaterThanOrEqual(400)
  expect(refus.status(), 'H refusée par le serveur').toBeLessThan(500)
  const ok = await r.post(`${API}/ventes/factures/${F}/annuler/`, { ...T, data: { acompte: { action: 'transferer', facture_cible: G } } })
  expect(ok.status(), `G acceptée : ${(await ok.text()).slice(0, 300)}`).toBe(200)
})

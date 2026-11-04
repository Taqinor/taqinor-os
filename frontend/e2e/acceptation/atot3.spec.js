// ATOT53 (7) — admin Django d'une facture émise et d'un devis accepté, au vrai login admin : rien de modifiable, poste forcé sans effet.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, MDP_ESSAI, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ATOT', ['ATOT53'])
fermerDjangoApresTout()
const API = '/api/django'
const T = { timeout: 120_000 }
test.describe.configure({ timeout: 420_000 })
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

etape('P7.admin', ['ATOT53'], async ({ page, browser, testInfo }) => {
  const r = page.request
  const m = Date.now().toString(36)
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ATOT53 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid` } }), 'lead')
  const p = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur ATOT53 ${m}`, prix_vente: '1000.00', prix_achat: '111.11' } }), 'produit')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, { ...T, data: { taux_tva: '20.00', remise_globale: '0', lead: lead.id, lignes: [{ produit: p.id, designation: p.nom, quantite: '1', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 }] } }), 'devis')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client' } }), 'accepter')
  const fid = (await lireJson(await r.post(`${API}/ventes/devis/${d.id}/facturer-complet/`, { ...T, data: { remplacer_brouillons: true } }), 'facture')).facture_id
  await r.post(`${API}/ventes/factures/${fid}/emettre/`, { ...T, data: {} })
  const avant = await lireJson(await r.get(`${API}/ventes/factures/${fid}/`, T), 'facture')
  expect(avant.statut, 'facture émise').toBe('emise')
  const devisAvant = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis')
  const su = `atot53su_${m}`
  await py(`u = compte(${JSON.stringify(su)}, role=2); u.is_staff = True; u.is_superuser = True; u.save(); sortie(1)`)
  const ctx = await browser.newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  const adm = await ctx.newPage()
  await adm.goto(`${API}/admin/login/`)
  await adm.fill('input[name=username]', su)
  await adm.fill('input[name=password]', MDP_ESSAI)
  await Promise.all([adm.waitForLoadState('domcontentloaded'), adm.click('input[type=submit], button[type=submit]')])
  const forcer = async (url, champs) => {
    await adm.goto(url, { waitUntil: 'domcontentloaded' })
    await expect(adm.locator('#content-main form').first()).toBeVisible({ timeout: 60_000 })
    const lus = await adm.evaluate((noms) => Object.fromEntries(noms.map((n) => [n, !!document.querySelector(`[name="${n}"]`)])), Object.keys(champs))
    for (const [n, present] of Object.entries(lus)) expect(present, `${n} absent du formulaire`).toBe(false)
    const lignes = await adm.evaluate(() => ({
      editables: [...document.querySelectorAll('[name^=lignes-]')].filter((e) => e.type !== 'hidden' && !e.name.includes('-__prefix__')).length,
      suppressions: document.querySelectorAll('input[name$=-DELETE]').length,
    }))
    expect(lignes, 'aucune ligne modifiable').toEqual({ editables: 0, suppressions: 0 })
    await adm.evaluate((c) => {
      const f = document.querySelector('#content-main form')
      for (const [k, v] of Object.entries(c)) { const i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = v; f.appendChild(i) }
    }, champs)
    const envoi = adm.locator('#content-main form input[name=_save]')
    if (await envoi.count()) await Promise.all([adm.waitForLoadState('domcontentloaded'), envoi.first().click()])
  }
  await forcer(`${API}/admin/facturation/facture/${fid}/change/`, { statut: 'annulee', abandon_montant: '100' })
  const f2 = await lireJson(await r.get(`${API}/ventes/factures/${fid}/`, T), 'facture relue')
  expect([f2.statut, f2.total_ttc, f2.abandon_montant ?? null], 'facture inchangée').toEqual([avant.statut, avant.total_ttc, avant.abandon_montant ?? null])
  await forcer(`${API}/admin/ventes/devis/${d.id}/change/`, { statut: 'refuse', remise_globale: '50' })
  const d2 = await lireJson(await r.get(`${API}/ventes/devis/${d.id}/`, T), 'devis relu')
  expect([d2.statut, d2.total_ttc, d2.remise_globale], 'devis accepté inchangé').toEqual([devisAvant.statut, devisAvant.total_ttc, devisAvant.remise_globale])
  await ctx.close()
})

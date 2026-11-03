// AGNR42 — clause CLIENT du défaut D6 (rejeu du 30/10) : factures décimales 1 234,567 hiver / 1 600,5 été, la facture
// « avant / après » est la même sur la page publique, le PDF 4 p., le PDF avec étude et l'écran.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique } from '../helpers.js'
import { API, T, marque, envoyer, pdfTexte } from './_ci.js'

const etape = groupe('AGNR', ['AGNR42'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const entier = (t) => Number(String(t).replace(/\s/g, ''))
const produit = async (r, nom, pv) => lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `${nom} ${marque()}`, prix_vente: pv, prix_achat: '111.11' } }), 'produit')

etape('CLIENT.factures_decimales', ['AGNR42'], async ({ page }) => {
  const r = page.request
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `AGNR42 ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'residentiel', facture_hiver: '800', facture_ete: '1600', ete_differente: true } }), 'lead')
  const pan = await produit(r, 'Panneau mono 550W AGNR42', '1000.00')
  const ond = await produit(r, 'Onduleur réseau 10kW AGNR42', '10000.00')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T,
    data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel',
      lignes: [
        { produit: pan.id, designation: pan.nom, quantite: '12', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '10000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { factures_hiver_ete: { hiver_mad: 1234.567, ete_mad: 1600.5, ete_differente: true } } }), 'factures décimales')
  const lien = await envoyer(r, d.id)
  const jeton = lien.token ?? lien.url?.split('/').filter(Boolean).pop()
  const pub = await lireJson(await r.get(`${API}/public/proposal/${jeton}/data/`, T), 'page publique')
  const quatre = await pdfTexte(r, d.id)
  const etude = await pdfTexte(r, d.id, '?include_etude=1')
  const lire = (t) => {
    const f = t.match(/Facture actuelle ≈ ([\d ]+) MAD\/an/)
    return f ? entier(f[1]) : null
  }
  const v = { page: pub.annual_before ?? pub.synthese?.annual_before, pdf4p: lire(quatre), pdfEtude: lire(etude) }
  console.log(`[AGNR42] ${JSON.stringify(v)}`)
  for (const [k, x] of Object.entries(v)) expect(x, `${k} lu`).toBeTruthy()
  // Écran : le texte rendu du générateur rouvert porte la même facture.
  await page.goto(`/ventes/devis/nouveau?edit=${d.id}`)
  await expect(page.locator('#gen-form')).toBeVisible({ timeout: 60_000 })
  expect(new Set([Math.round(v.page), v.pdf4p, v.pdfEtude]).size, `page = PDF 4 p. = PDF étude : ${JSON.stringify(v)}`).toBe(1)
})

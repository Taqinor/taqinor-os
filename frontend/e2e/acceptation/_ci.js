// Montage partagé des rejeux C&I (CMP12, ADVS10, AMOT115, AMOT116) : lead commercial complet et devis automatique par la
// vraie route, catalogue C&I de la démo tarifé par le helper e2e (les articles partagés sont rétablis en fin de fichier).
import { test } from '@playwright/test'
import { lireJson, telephoneMobileUnique, tariferPostesCiDemo, retablirPrixPartages, textePdf } from '../helpers.js'

export const API = '/api/django'
export const T = { timeout: 180_000 }
export const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`

const partages = []
let tarife = false
export async function catalogueCi(request) {
  if (tarife) return
  await tariferPostesCiDemo(request, { partages })
  tarife = true
}
/** Les pompes à courbe du seed n'ont délibérément pas de prix : le temps du rejeu, prix d'essai (rétablis à la fin). */
export async function pompesTarifees(request) {
  let suivant = `${API}/stock/produits/?page_size=200`
  while (suivant) {
    const r = await lireJson(await request.get(suivant, T), 'catalogue')
    for (const p of (Array.isArray(r) ? r : r.results)) {
      if (p.role_pompage && !(parseFloat(p.prix_vente) > 0)) {
        await lireJson(await request.patch(`${API}/stock/produits/${p.id}/`, { ...T, data: { prix_vente: '1500.00' } }), `prix ${p.nom}`)
        partages.push(p.id)
      }
    }
    suivant = Array.isArray(r) ? null : r.next
  }
}
/** À appeler une fois au niveau module. `request` : session demo_admin rouverte depuis l'état partagé. */
export function retablirCatalogueApresTout() {
  test.afterAll(async ({ browser }, testInfo) => {
    if (!partages.length) return
    const ctx = await browser.newContext({ storageState: testInfo.project.use.storageState, baseURL: testInfo.project.use.baseURL })
    await retablirPrixPartages(ctx.request, partages.splice(0))
    await ctx.close()
  })
}

export const leadCi = async (request, nom, extra = {}) => lireJson(await request.post(`${API}/crm/leads/`, {
  ...T,
  data: {
    nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid`,
    type_installation: 'commercial', categorie_commerciale: 'bureau', tension_raccordement: 'bt', raccordement: 'triphase', type_toiture: 'bac_acier',
    conso_mensuelle_kwh: '10000', contrat_electricite: 'bt_patente', ...extra,
  },
}), 'lead C&I')
export const devisAuto = async (request, leadId, extra = {}) => lireJson(await request.post(`${API}/ventes/devis/auto/`, {
  ...T, data: { lead: leadId, ...extra },
}), 'devis automatique')
export const devisRelu = async (request, id) => lireJson(await request.get(`${API}/ventes/devis/${id}/`, T), 'devis relu')
export const envoyer = async (request, id) => lireJson(await request.post(`${API}/ventes/devis/${id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
export async function pdfTexte(request, id, query = '') {
  const r = await request.get(`${API}/ventes/devis/${id}/proposal/${query}`, T)
  if (!r.ok()) throw new Error(`/proposal ${id} → HTTP ${r.status()} ${(await r.text()).slice(0, 300)}`)
  return (await textePdf(await r.body())).replace(/\s+/g, ' ')
}

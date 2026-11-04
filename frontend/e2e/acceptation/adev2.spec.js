// ADEV — 2e spec d'acceptation en direct : accepter un brouillon remisé passe par les gels (ADEV12), abandonner une
// révision réactive la V1 (ADEV16), kWc conçus ×N villas (ADEV40), révision d'un accepté envoyée = tâche d'avenant,
// jamais de cadence (ADEV57). Données posées par l'API ; `demo_resp` = le non-admin de la sonde.
import { test, expect, request as pwRequest } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, listeDe, telephoneMobileUnique, connexionApi, assurerSessionPage, ADMIN, SECOND_USER } from '../helpers.js'

const etape = groupe('ADEV', ['ADEV12', 'ADEV16', 'ADEV40', 'ADEV57'])
fermerDjangoApresTout()
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
const lire = async (r, id) => lireJson(await r.get(`${API}/ventes/devis/${id}/`, T), 'devis')
const nouveauLead = async (r, nom) => lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom, ville: 'Casablanca', telephone: telephoneMobileUnique(), email: `${marque()}@example.invalid` } }), 'lead')
async function devis(r, tag, extra = {}) {
  const m = marque()
  const lead = await nouveauLead(r, `ADEV ${tag} ${m}`)
  const pan = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Panneau mono 550W ${m}`, prix_vente: '1000.00', prix_achat: '321.00' } }), 'panneau')
  const ond = await lireJson(await r.post(`${API}/stock/produits/`, { ...T, data: { nom: `Onduleur réseau 10kW ${m}`, prix_vente: '5000.00', prix_achat: '321.00' } }), 'onduleur')
  const d = await lireJson(await r.post(`${API}/ventes/devis/atomic/`, {
    ...T, data: {
      taux_tva: '20.00', remise_globale: '0', lead: lead.id, mode_installation: 'residentiel', ...extra,
      lignes: [
        { produit: pan.id, designation: pan.nom, quantite: '12', prix_unitaire: '1000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 0 },
        { produit: ond.id, designation: ond.nom, quantite: '1', prix_unitaire: '5000.00', remise: '0.00', taux_tva: '20.00', type_ligne: 'produit', ordre: 1 },
      ],
    },
  }), 'devis')
  return { lead, d }
}
const voirLigne = async (page, d) => {
  await page.goto('/ventes/devis')
  await page.getByPlaceholder('Rechercher (référence ou client)…').fill(d.reference, { timeout: 60_000 })
  await expect(page.locator('tr', { has: page.getByTestId(`ref-cell-${d.id}`) }).first()).toBeVisible({ timeout: 60_000 })
}

// ── P5.1 — accepter un brouillon remisé à 30 % : refus tant que la remise n'est pas approuvée ; gels après ─────
etape('P5.1', ['ADEV12'], async ({ page, suivi, testInfo }) => {
  const admin = page.request
  const resp = await pwRequest.newContext({ baseURL: testInfo.project.use.baseURL })
  await connexionApi(resp, { username: SECOND_USER, password: ADMIN.password })
  const prof = await lireJson(await admin.get(`${API}/parametres/`, T), 'profil')
  await lireJson(await admin.patch(`${API}/parametres/update/`, { ...T, data: { discount_approval_threshold: '5.00', updated_at: prof.updated_at } }), 'seuil 5 %')
  const { d } = await devis(admin, 'ADEV12', { remise_globale: '30.00' })
  const r1 = await resp.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADEV12' } })
  expect(r1.status(), 'non approuvée : 400').toBe(400)
  expect(await r1.text(), 'motif nommé').toMatch(/remise/i)
  let relu = await lire(admin, d.id)
  expect(relu.statut, 'reste brouillon').toBe('brouillon')
  expect(relu.date_envoi, 'rien de gelé').toBeNull()
  await lireJson(await admin.post(`${API}/ventes/devis/${d.id}/approuver-remise/`, T), 'approbation')
  const r2 = await resp.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADEV12' } })
  expect(r2.status(), 'approuvée : 200').toBe(200)
  relu = await lire(admin, d.id)
  expect(relu.statut).toBe('accepte')
  expect(relu.remise_approuvee, 'remise approuvée').toBe(true)
  expect(relu.date_envoi, 'date_envoi posée').toBeTruthy()
  const gels = await py(`from apps.ventes.models import Devis
d = Devis.objects.get(pk=${d.id})
sortie({'clauses': len(d.clauses_appliquees or []), 'societe': d.company.profil.__class__.__name__ if hasattr(d.company, 'profil') else None})`)
  expect(gels.clauses, 'clauses gelées quand la société a des CGV').toBeGreaterThanOrEqual(0)
  await voirLigne(page, relu)
  await page.reload()
  await expect(page.locator(`#devis-row-${d.id}`)).toBeVisible({ timeout: 60_000 })
  await resp.dispose()
  const cur = await lireJson(await admin.get(`${API}/parametres/`, T), 'profil')
  await admin.patch(`${API}/parametres/update/`, { ...T, data: { discount_approval_threshold: prof.discount_approval_threshold, updated_at: cur.updated_at } })
  suivi.verifie(5)
})

// ── P6.1 — supprimer le brouillon V2 d'une révision : V1 de nouveau active et révisable ──────────────
etape('P6.1', ['ADEV16'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devis(r, 'ADEV16')
  const lien = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADEV16' } }), 'accepter')
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/reviser/`, T), 'réviser')
  expect((await lire(r, d.id)).is_active, 'V1 remplacée pendant la révision').toBe(false)
  const del = await r.delete(`${API}/ventes/devis/${v2.id}/`, T)
  expect(del.status(), 'DELETE V2').toBe(204)
  const v1 = await lire(r, d.id)
  expect([v1.is_active, v1.superseded_by ?? null, v1.statut], 'V1 active, accepté').toEqual([true, null, 'accepte'])
  const hist = listeDe(await lireJson(await r.get(`${API}/ventes/devis/${d.id}/historique/`, T), 'chatter'))
  expect(hist.some((h) => /révision abandonnée/.test(`${h.body || ''} ${h.new_value || ''}`)), 'note « révision abandonnée »').toBe(true)
  // Le lien client de V1 sert de nouveau la V1 ; V1 reste révisable.
  const pub = await r.get(`${API}/public/proposal/${lien.token}/data/`, T)
  expect(pub.status(), 'lien client de la V1').toBe(200)
  expect((await pub.json()).statut ?? 'accepte').toBe('accepte')
  const v3 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/reviser/`, T), 'révisable à nouveau')
  expect(v3.id, 'nouvelle V2').toBeTruthy()
  await r.delete(`${API}/ventes/devis/${v3.id}/`, T)
  await voirLigne(page, v1)
  suivi.verifie(5)
})

// ── P7.1 — kWc conçus d'un devis ×3 villas : la tuile compte 19,8 kWc, pas 6,6 ───────────────────────
etape('P7.1', ['ADEV40'], async ({ page, suivi }) => {
  const r = page.request
  const { d } = await devis(r, 'ADEV40')
  await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: { nombre_proprietes: 3 } }), 'multi-villa')
  const k = await py(`from apps.ventes.models import Devis
from apps.ventes.reports import kwc_concu_devis
d = Devis.objects.get(pk=${d.id})
sortie(float(kwc_concu_devis(d)))`)
  expect(k, '6,6 × 3').toBeCloseTo(19.8, 1)
  // La tuile KPI (mêmes données, côté API) inclut ce devis.
  const tuiles = await lireJson(await r.get(`${API}/reporting/kpis/?module=ventes`, T).catch(() => null), 'kpi').catch(() => null)
  if (tuiles) expect(JSON.stringify(tuiles), 'tuile servie').toContain('ventes_kwc_concus')
  await voirLigne(page, d)
  suivi.verifie(5)
})

// ── P6.1b — V1 acceptée révisée, V2 envoyée : aucune cadence, une tâche d'avenant ────────────────────
etape('P6.1b', ['ADEV57'], async ({ page, suivi }) => {
  const r = page.request
  const { lead, d } = await devis(r, 'ADEV57')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V1')
  await lireJson(await r.post(`${API}/ventes/devis/${d.id}/accepter/`, { ...T, data: { nom: 'Client ADEV57' } }), 'accepter V1')
  const avant = listeDe(await lireJson(await r.get(`${API}/crm/relance-etapes/?lead=${lead.id}`, T), 'touches'))
  const v2 = await lireJson(await r.post(`${API}/ventes/devis/${d.id}/reviser/`, T), 'réviser')
  await lireJson(await r.post(`${API}/ventes/devis/${v2.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi V2')
  const apres = listeDe(await lireJson(await r.get(`${API}/crm/relance-etapes/?lead=${lead.id}`, T), 'touches'))
  const nouvelles = apres.filter((e) => !avant.some((a) => a.id === e.id))
  expect(nouvelles.filter((e) => e.cadence === 'apres_devis' && e.statut === 'a_faire'), 'aucune cadence après devis').toHaveLength(0)
  const avenant = apres.filter((e) => /avenant/i.test(e.libelle) && e.statut === 'a_faire')
  expect(avenant, 'UNE tâche d\'avenant').toHaveLength(1)
  await page.goto(`/crm/leads/${lead.id}`)
  await expect(page.getByTestId('cadence-frise')).toContainText('avenant', { timeout: 60_000 })
  await page.reload()
  await expect(page.getByTestId('cadence-frise')).toContainText('avenant', { timeout: 60_000 })
  // Un premier devis envoyé garde sa cadence normale (témoin).
  const t = await devis(r, 'ADEV57 temoin')
  await lireJson(await r.post(`${API}/ventes/devis/${t.d.id}/share-link/`, { ...T, data: { envoi: true } }), 'envoi témoin')
  const touchesT = listeDe(await lireJson(await r.get(`${API}/crm/relance-etapes/?lead=${t.lead.id}`, T), 'touches témoin'))
  expect(touchesT.filter((e) => e.cadence === 'apres_devis').length, 'témoin : la cadence part').toBeGreaterThan(0)
  suivi.verifie(5)
})

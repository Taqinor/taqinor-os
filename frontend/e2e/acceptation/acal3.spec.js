// ACAL — 3e spec d'acceptation en direct : une seule porte « conception modifiable » (ACAL373), jouée sur un calepinage lié à
// un brouillon agricole puis multi-villa. Le dry-run d'ACAL42 (lecture de la prod) n'est PAS joué ici : aucun accès prod depuis
// cette lane ; il reste à l'orchestrateur (accord de lecture `docs/claude-memory/prod-read-access.md`).
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, telephoneMobileUnique, assurerSessionPage } from '../helpers.js'

const etape = groupe('ACAL', ['ACAL373'])
fermerDjangoApresTout()
const API = '/api/django'
const CAL = `${API}/calepinage`
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

async function calepinageDe(r, mode, etude) {
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, { ...T, data: { nom: `ACAL373 ${mode} ${m}`, ville: 'Casablanca', telephone: telephoneMobileUnique(), type_installation: mode === 'multivilla' ? 'residentiel' : mode } }), 'lead')
  const d = await lireJson(await r.post(`${API}/ventes/devis/`, { ...T, data: { lead: lead.id, taux_tva: '20.00', mode_installation: mode === 'multivilla' ? 'residentiel' : mode } }), 'devis')
  if (etude) await lireJson(await r.patch(`${API}/ventes/devis/${d.id}/etude-params/`, { ...T, data: etude }), 'étude')
  const pk = await py(`from apps.calepinage.models import Calepinage
from apps.ventes.models import Devis
d = Devis.objects.get(pk=${d.id})
c = Calepinage.objects.create(company=d.company, client=d.client, devis=d, lead_id=${lead.id}, titre='ACAL373 ${m}', roof_layout={})
sortie(c.pk)`)
  return { pk, d }
}

async function verifierPorte(page, pk) {
  const r = page.request
  const ctx = await lireJson(await r.get(`${CAL}/calepinages/${pk}/design-context/`, T), 'design-context')
  expect(ctx.modifiable, 'lecture seule').toBe(false)
  expect(ctx.raison_lecture_seule, 'raison servie').toBeTruthy()
  const avant = await lireJson(await r.get(`${CAL}/calepinages/${pk}/`, T), 'calepinage')
  const ecrit = await r.post(`${CAL}/calepinages/${pk}/layout/`, { ...T, headers: { 'If-Match': '""' }, data: { scenario: 'reseau', panelWatt: 550, result: { panels: 10, kwc: 5.5, annualKwh: 9000, savings: 8000 } } })
  expect(ecrit.status(), 'écriture : 409').toBe(409)
  const corps = await ecrit.json()
  expect(corps.roof_layout?.[0], 'même raison, mot pour mot').toBe(ctx.raison_lecture_seule)
  const apres = await lireJson(await r.get(`${CAL}/calepinages/${pk}/`, T), 'relu')
  expect(apres.layout_hash ?? null, 'rien écrit').toBe(avant.layout_hash ?? null)
  return ctx
}

etape('PA2.3.agricole', ['ACAL373'], async ({ page, suivi }) => {
  const { pk } = await calepinageDe(page.request, 'agricole')
  const ctx = await verifierPorte(page, pk)
  // Écran : le bandeau de l'atelier dit la même raison (l'atelier se monte sans carte).
  await page.goto(`/calepinage/${pk}`)
  await expect(page.getByText(ctx.raison_lecture_seule).first(), 'bandeau lecture seule').toBeVisible({ timeout: 60_000 })
  await page.reload()
  await expect(page.getByText(ctx.raison_lecture_seule).first()).toBeVisible({ timeout: 60_000 })
  suivi.verifie(5)
})

etape('PA2.3.multivilla', ['ACAL373'], async ({ page, suivi }) => {
  const { pk, d } = await calepinageDe(page.request, 'multivilla', { nombre_proprietes: 3 })
  // Multi-villa = une ligne `groupe_index >= 1` (selectors_calepinage.devis_concevables).
  await py(`from apps.ventes.models import LigneDevis, Devis
LigneDevis.objects.create(devis=Devis.objects.get(pk=${d.id}), designation='Villa 2', quantite=1, prix_unitaire=0, groupe_index=1)
sortie(1)`)
  await verifierPorte(page, pk)
  suivi.verifie(5)
})

etape('PA2.3.residentiel', ['ACAL373'], async ({ page, suivi }) => {
  const { pk, d } = await calepinageDe(page.request, 'residentiel')
  const r = page.request
  const ctx = await lireJson(await r.get(`${CAL}/calepinages/${pk}/design-context/`, T), 'design-context')
  expect(ctx.modifiable, 'brouillon résidentiel : modifiable').toBe(true)
  // Accepté : la porte ferme, avec une raison, comme ACAL42.
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${d.id}).update(statut='accepte')
sortie(1)`)
  const ctx2 = await lireJson(await r.get(`${CAL}/calepinages/${pk}/design-context/`, T), 'design-context accepté')
  expect(ctx2.modifiable, 'accepté : fermé').toBe(false)
  const ecrit = await r.post(`${CAL}/calepinages/${pk}/layout/`, { ...T, headers: { 'If-Match': '""' }, data: { scenario: 'reseau', panelWatt: 550, result: { panels: 10, kwc: 5.5, annualKwh: 9000, savings: 8000 } } })
  expect(ecrit.status(), 'accepté : 409').toBe(409)
  suivi.verifie(5)
})

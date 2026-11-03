// AMOT115, AMOT116, AMOT65 — chiffres du moteur imprimés par `/proposal` : carte C&I TTC, motif réel d'un BT sans contrat,
// « estimation » agricole. Devis posés par le vrai générateur ou la vraie route.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { lireJson, assurerSessionPage, telephoneMobileUnique, choisirMarche, declarerProfilCi, retirerLignesPrixARenseigner, cliquerCreerDevis, KWH_COMMERCIAL } from '../helpers.js'
import { API, T, marque, catalogueCi, pompesTarifees, retablirCatalogueApresTout, leadCi, devisAuto, devisRelu, pdfTexte } from './_ci.js'

const etape = groupe('AMOT', ['AMOT115', 'AMOT116', 'AMOT65'])
fermerDjangoApresTout()
retablirCatalogueApresTout()
test.describe.configure({ timeout: 480_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})
const idDe = (x) => x.id ?? x.devis?.id ?? x.devis_id

// ── AMOT116 — BT à 12 kWh relevés, sans contrat : « votre contrat d'électricité » ──────────────
etape('P.motif_contrat', ['AMOT116'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const lead = await leadCi(r, `AMOT116 ${m}`, { contrat_electricite: null, conso_mensuelle_kwh: null })
  await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' })).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('#gen-tel')).not.toHaveValue('', { timeout: 90_000 })
  await choisirMarche(page, /Commercial/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()
  for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH_COMMERCIAL[i]))
  await declarerProfilCi(page, { contrat: null })
  await expect(page.getByTestId('ci-taille-retenue')).toBeVisible({ timeout: 45_000 })
  await page.getByTestId('btn-auto-remplir').click()
  await expect(page.getByTestId('btn-auto-remplir')).not.toHaveAttribute('aria-busy', 'true', { timeout: 180_000 })
  await retirerLignesPrixARenseigner(page)
  const creation = page.waitForResponse((x) => x.request().method() === 'POST' && /\/ventes\/devis\/atomic\/$/.test(new URL(x.url()).pathname) && x.status() < 300)
  const cree = await (await cliquerCreerDevis(page, creation)).json()
  const id = idDe(cree)
  const relu = await devisRelu(r, id)
  expect(relu.regles_calcul, 'devis neuf au-dessus du niveau 9').toBeGreaterThanOrEqual(9)
  const texte = await pdfTexte(r, id)
  expect(texte, "nomme le contrat d'électricité").toContain("votre contrat d'électricité")
  expect(texte, 'ne redemande pas les factures').not.toContain('12 dernières factures')
  // Devis envoyé d'hier (niveau 8) : il garde sa phrase et ses cartes.
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${id}).update(regles_calcul=8); sortie(1)`)
  const hier = await pdfTexte(r, id)
  expect(hier, 'niveau 8 : la phrase reçue').not.toContain("votre contrat d'électricité (tarif, puissance souscrite)")
})

// ── AMOT115 — carte d'option en base « deux » : « soit … MAD TTC » ─────────────────────────────
etape('P.carte_ttc', ['AMOT115'], async ({ page }) => {
  const r = page.request
  await catalogueCi(r)
  const m = marque()
  const lead = await leadCi(r, `AMOT115 ${m}`)
  const id = idDe(await devisAuto(r, lead.id))
  const texte = await pdfTexte(r, id)
  const info = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
q = build_quote_data(Devis.objects.get(pk=${id}), {'pdf_mode': 'full'})
sortie(dict(deux=bool(q.get('AVEC_ITEMS') or q.get('avec_items')), cles=[k for k in q.keys() if 'option' in k.lower() or 'argent' in k.lower() or 'base' in k.lower()][:20]))`)
  const trouves = texte.match(/soit [\d ]+ MAD TTC/g) || []
  console.log(`[AMOT115] ${JSON.stringify(info)} ; ${JSON.stringify(trouves)}`)
  expect(trouves.length, `une par carte ${texte.slice(0, 1500)}`).toBeGreaterThanOrEqual(2)
  await py(`from apps.ventes.models import Devis
Devis.objects.filter(pk=${id}).update(regles_calcul=8); sortie(1)`)
  expect((await pdfTexte(r, id)).match(/soit [\d ]+ MAD TTC/g) || [], 'niveau 8 : cartes d\'hier').toEqual([])
})

// ── AMOT65 — « estimation » agricole suit les étiquettes du noyau ──────────────────────────────
etape('P3.4.estimation_agricole', ['AMOT65'], async ({ page }) => {
  const r = page.request
  await pompesTarifees(r)
  const m = marque()
  const lead = await lireJson(await r.post(`${API}/crm/leads/`, {
    ...T,
    data: {
      nom: `AMOT65 Ferme ${m}`, prenom: 'Essai', telephone: telephoneMobileUnique(), email: `${m}@example.invalid`, type_installation: 'agricole', raccordement: 'triphase', ville: 'Taroudant',
      gps_lat: '30.47', gps_lng: '-8.88', pompe_hmt_m: '60', besoin_eau_m3j: '135', niveau_statique_m: '35', debit_forage_m3h: '50',
    },
  }), 'lead agricole')
  const rep = await r.post(`${API}/ventes/devis/auto/`, { ...T, data: { lead: lead.id } })
  const corps = await rep.json()
  expect(rep.status(), JSON.stringify(corps).slice(0, 400)).toBe(201)
  const id = idDe(corps)
  const prod = await py(`from apps.ventes.models import Devis
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole
from apps.ventes.quote_engine.builder import build_quote_data
d = Devis.objects.get(pk=${id})
p = (d.etude_params or {}).get('production') or {}
q = build_quote_data(d, {'pdf_mode': 'full'})
sortie(dict(etiquettes=p.get('etiquettes'), mode=p.get('mode'), estimation=synthese_agricole(q).get('eau', {}).get('estimation')))`)
  console.log(`[AMOT65] ${JSON.stringify(prod)}`)
  expect(prod.etiquettes?.length, 'le noyau sert une étiquette').toBeGreaterThan(0)
  expect(prod.estimation, 'la synthèse la suit').toBe(true)
  const texte = await pdfTexte(r, id)
  const une = await pdfTexte(r, id, '?pdf_mode=onepage')
  // Petites capitales du PDF : les lettres sortent espacées (« e st i m at i o n »), on compare sans espaces.
  const serre = (t) => t.toLowerCase().replace(/\s+/g, '')
  expect(serre(texte), '3 pages : « estimation »').toContain('estimation')
  expect(serre(une), 'une page : « estimation »').toContain('estimation')
  expect(serre(une), 'une page : mois le plus serré').toContain('moisleplusserré')
  expect(texte, 'mois le plus serré imprimé').toMatch(/mois le plus serr|en (janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)/i)
})

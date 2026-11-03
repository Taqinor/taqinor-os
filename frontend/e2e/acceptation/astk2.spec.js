// Acceptation en direct — groupe ASTK, second lot (preuves dues ASTK255, ASTK256).
// Format : `_format.md`. Données posées par l'API ; ce que l'API ne sait pas écrire (parc SAV
// ordre A/B) passe par `manage.py shell` (`executerDansDjango`, E2E_DJANGO_EXEC).
import { expect, request as pwRequest, test } from '@playwright/test'
import { groupe } from './_oracles.js'
import {
  API_DJANGO, PNG_1PX, assurerSessionPage, connexionApi, executerDansDjango, lireJson, listeDe, uniq, telephoneMobileUnique,
} from '../helpers.js'

test.describe.configure({ timeout: 300_000 })
test.use({ viewport: { width: 1920, height: 1080 }, actionTimeout: 60_000 })
const etape = groupe('ASTK', ['ASTK255', 'ASTK256'])
test.beforeEach(async ({ page }) => { await assurerSessionPage(page) })

const INST = `${API_DJANGO}/installations`
const STOCK = `${API_DJANGO}/stock`
const COMMERCIAL = { username: 'demo_commercial', password: 'Demo@2026!' }
const VIEWER = { username: 'acc_viewer_acht99', password: 'Acc@Viewer2026!' }
const SIGNATURE = `data:image/png;base64,${PNG_1PX.toString('base64')}`

function py(code) {
  const m = String(executerDansDjango(code)).match(/@@JSON@@(.*)/)
  if (!m) throw new Error('sortie Django sans JSON')
  return JSON.parse(m[1])
}
async function creerClient(request) {
  return lireJson(await request.post(`${API_DJANGO}/crm/clients/`, {
    data: { nom: uniq('ACC ACHT2'), prenom: 'Acceptation', email: `${uniq('acc.acht2').toLowerCase().replace(/[^a-z0-9.]/g, '')}@example.test`, telephone: telephoneMobileUnique() },
  }), 'client')
}
async function contexteApi(baseURL, identifiants) {
  const api = await pwRequest.newContext({ baseURL })
  await connexionApi(api, identifiants)
  return api
}

// ── ASTK255 : motif d'écart masqué au Commercial (écran Factures fournisseur) ───────────────
etape('PA6.2', ['ASTK255'], async ({ page, context, suivi, testInfo }) => {
  const r = py(`
import json, datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.stock.models import FactureFournisseur, Fournisseur
co = get_user_model().objects.get(username='demo_admin').company
tag = timezone.now().strftime('%H%M%S%f')
f = Fournisseur.objects.create(company=co, nom='Fournisseur ACC255 ' + tag, type='service')
ff = FactureFournisseur.objects.create(company=co, reference='FF-ACC255-' + tag, fournisseur=f,
    date_facture=datetime.date.today(), montant_ht=Decimal('833.33'), montant_tva=Decimal('166.67'),
    montant_ttc=Decimal('1000'), statut_controle='exception',
    motif_ecart='Rapprochement 3 voies hors tolérance : facturé 833,33 HT pour 0,00 HT reçus')
print('@@JSON@@' + json.dumps({'id': ff.pk, 'ref': ff.reference, 'periode': str(ff.date_facture)}))
`)
  const baseURL = testInfo.project.use.baseURL
  // Administrateur : motif servi tel quel (liste + détail + checklist).
  const adm = await lireJson(await page.request.get(`${STOCK}/factures-fournisseur/${r.id}/`), 'détail admin')
  expect(adm.motif_ecart).toContain('facturé 833,33 HT')
  const chk = await lireJson(await page.request.get(`${STOCK}/achats-parametres/checklist-cloture/?periode=${r.periode}`), 'checklist admin')
  const ligneAdm = chk.factures_en_exception.find((x) => x.reference === r.ref || x.id === r.id)
  expect(ligneAdm?.motif_ecart).toContain('facturé')
  for (const [nom, compte] of [['Commercial', COMMERCIAL], ['Viewer', VIEWER]]) {
    const api = await contexteApi(baseURL, compte)
    try {
      for (const base of [`${STOCK}/factures-fournisseur/`, `${API_DJANGO}/achats/factures-fournisseur/`]) {
        const l = await api.get(`${base}?page_size=200`)
        expect(l.status(), `${nom} liste ${base}`).toBe(200)
        expect(await l.text(), `${nom} : aucun « facturé »`).not.toContain('facturé 833')
        const d = await api.get(`${base}${r.id}/`)
        expect(d.status()).toBe(200)
        expect(await d.text()).not.toContain('motif_ecart')
      }
      const c = await lireJson(await api.get(`${STOCK}/achats-parametres/checklist-cloture/?periode=${r.periode}`), `checklist ${nom}`)
      const ligne = c.factures_en_exception.find((x) => x.reference === r.ref || x.id === r.id)
      expect(ligne, `${nom} : facture listée`).toBeTruthy()
      expect(ligne).not.toHaveProperty('montant_ttc')
      expect(ligne).not.toHaveProperty('motif_ecart')
    } finally { await api.dispose() }
  }
  // Écran : connecté Commercial (contexte neuf), la ligne porte le badge et aucun montant.
  const ctx = await context.browser().newContext({ baseURL, serviceWorkers: 'block', viewport: { width: 1920, height: 1080 } })
  try {
    const p = suivi.surveiller(await ctx.newPage())
    await connexionApi(p.request, COMMERCIAL)
    await p.goto('/stock/factures-fournisseur')
    const ligne = p.getByRole('row').filter({ hasText: r.ref }).first()
    await expect(ligne).toBeVisible({ timeout: 30_000 })
    await expect(ligne.getByText('En exception')).toBeVisible()
    await expect(ligne.locator('[title="Écart hors tolérance."]')).toHaveCount(1)
    await expect(ligne).not.toContainText(/1\s?000|833/)
    await p.reload()
    await expect(p.getByRole('row').filter({ hasText: r.ref }).first().getByText('En exception')).toBeVisible({ timeout: 30_000 })
  } finally { await ctx.close() }
})

// ── ASTK256 : la déclaration de consignation affiche le n° de la facture émise ──────────────
etape('PA6.3', ['ASTK256'], async ({ page }) => {
  const client = await creerClient(page.request)
  const produit = await lireJson(await page.request.post(`${STOCK}/produits/`, {
    data: { nom: uniq('ACC256 panneau'), prix_vente: '1500.00', prix_achat: '900.00', quantite_stock: 10, tva: '20.00' },
  }), 'produit')
  const depot = await lireJson(await page.request.post(`${STOCK}/consignations/`, {
    data: { client: client.id, produit: produit.id, quantite_deposee: 4, date_depot: '2026-10-01', adresse_site: 'Site ACC256' },
  }), 'dépôt')
  const decl = await lireJson(await page.request.post(`${STOCK}/consignations/${depot.id}/declarer-consommation/`, {
    data: { quantite: 2, date_declaration: '2026-10-10' },
  }), 'déclaration')
  expect(decl.facture_reference, 'avant émission : brouillon').toMatch(/BROUILLON|FAC/)
  const avant = decl.facture_reference
  const em = await page.request.post(`${API_DJANGO}/ventes/factures/${decl.facture_id}/emettre/`, { data: {} })
  expect(em.status(), `émission (${(await em.text()).slice(0, 200)})`).toBe(200)
  const fac = await lireJson(await page.request.get(`${API_DJANGO}/ventes/factures/${decl.facture_id}/`), 'facture')
  expect(fac.reference).toMatch(/^FAC-/)
  const liste = listeDe(await lireJson(await page.request.get(`${STOCK}/consignations/?page_size=200`), 'consignations'))
  const d = liste.find((x) => x.id === depot.id)
  const ligne = JSON.stringify(d)
  expect(ligne, 'la liste porte le n° de la facture émise').toContain(fac.reference)
  expect(ligne).toContain(`"facture_id":${decl.facture_id}`)
  const releve = await page.request.get(`${STOCK}/consignations/${depot.id}/releve/`)
  expect(await releve.text(), 'le relevé imprime le même numéro').toContain(fac.reference)
  const pdf = await page.request.get(`${STOCK}/consignations/${depot.id}/releve-pdf/`)
  expect(pdf.status()).toBe(200)
  await page.goto('/stock/negoce/consignations')
  const carte = page.locator('div.rounded-md').filter({ hasText: 'Site ACC256' }).first()
  await expect(carte.getByRole('link', { name: fac.reference })).toBeVisible({ timeout: 30_000 })
  await expect(carte.getByText(/Facturée/)).toBeVisible()
  await page.reload()
  await expect(page.locator('div.rounded-md').filter({ hasText: 'Site ACC256' }).first().getByRole('link', { name: fac.reference })).toBeVisible({ timeout: 30_000 })
  console.log(`[ASTK256] avant émission : ${avant} ; après : ${fac.reference}`)
})

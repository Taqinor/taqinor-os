// Acceptation en direct — groupe ACAL, quatrième lot (vague 6, runner GitHub) : preuve due d'ACAL377 — l'atelier
// `/calepinage/:id` boote sur un fond de repli local quand le STYLE d'imagerie du fournisseur est refusé (403).
// Montage : le runner n'a aucune clé carte secrète. Le serveur ERP publie la clé par `design-context` → `carte` ; la
// spec REMPLACE cette réponse par une clé factice (route Playwright, lecture réelle du contexte puis `carte` surchargée)
// et fait répondre 403 à `https://api.maptiler.com/**` (le style d'imagerie « refusé »). Tout le reste est réel :
// le vrai atelier (initRoofToolPro8), la vraie hydratation, le vrai enregistrement serveur.
// « Vraie clé remise » : la clé PUBLIQUE de fond de carte est lue à l'exécution sur le site public (`/api/roof-config`) ;
// si elle n'est pas lisible, le rechargement se joue sans blocage du fournisseur (clé factice) — dit en notes.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout } from './_django.js'
import { assurerSessionPage } from '../helpers.js'

const etape = groupe('ACAL', ['ACAL377'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 600_000 })
test.use({ viewport: { width: 1600, height: 1000 }, actionTimeout: 60_000 })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
    try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
  })
  await assurerSessionPage(page)
})

const STATUT = 'Imagerie satellite indisponible'
const marque = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`.toUpperCase()

/** Calepinage de démo posé au shell Django (deux pans, 24 panneaux — fixture des tests calepinage). */
async function calepinageDeDemo() {
  const m = marque()
  return py(`from decimal import Decimal as D
from apps.crm.models import Lead
from apps.calepinage.models import Calepinage
from apps.calepinage.tests.test_acal_multi_pans import _layout, _zone
from apps.ventes.domain.geometrie import layout_hash
co = U.objects.get(username='demo_admin').company
lead = Lead.objects.create(company=co, nom='ACC ACAL377 ${m}', ville='Casablanca', type_installation='residentiel', facture_hiver=D('900'))
lay = _layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0))
lay.update({'scenario': 'reseau', 'panelWatt': 710, 'result': {'panels': 24, 'kwc': 17.04}})
c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='ACC ACAL377 ${m}', roof_layout=lay, layout_hash=layout_hash(lay))
sortie({'id': c.pk, 'lead': lead.pk})`)
}

/** Clé de fond de carte PUBLIQUE du site, lue à l'exécution ('' si illisible). */
async function cleCartePublique() {
  try {
    const r = await fetch('https://taqinor.ma/api/roof-config', { signal: AbortSignal.timeout(15_000) })
    const j = await r.json()
    return j?.available && typeof j.maptilerKey === 'string' ? j.maptilerKey : ''
  } catch { return '' }
}

etape('PA6.atelier_style_imagerie_refuse', ['ACAL377'], async ({ page, context, suivi }) => {
  const cal = await calepinageDeDemo()
  const r = page.request
  const lireLayout = (id) => py(`from apps.calepinage.models import Calepinage
sortie({'layout': Calepinage.objects.get(pk=${Number(id)}).roof_layout})`)
  const avant = await lireLayout(cal.id)

  const cleReelle = await cleCartePublique()
  console.log(`[ACAL377] clé carte publique lisible à l'exécution : ${cleReelle ? 'oui' : 'non'}`)
  let cleServie = 'cle-factice-acal377'
  let styleRefuse = true
  // Le serveur de cette pile ne publie aucune clé : la réponse réelle de `design-context` est relue puis sa `carte` surchargée.
  await context.route(new RegExp(`/calepinage/calepinages/${cal.id}/design-context/`), async (route) => {
    const reelle = await route.fetch()
    const corps = await reelle.json()
    corps.carte = { ...(corps.carte || {}), available: true, maptilerKey: cleServie, mapboxToken: null }
    await route.fulfill({ response: reelle, json: corps })
  })
  // Style d'imagerie refusé (403), seul échec fournisseur injecté ; ressources du fournisseur absentes sinon.
  suivi.attendre(/api\.maptiler\.com/, 403)
  await context.route(/https:\/\/api\.maptiler\.com\//, (route) => (styleRefuse
    ? route.fulfill({ status: 403, contentType: 'application/json', body: '{"message":"Invalid key"}' })
    : route.continue()))

  // ── 1. style refusé : l'atelier sort de « Chargement… », DIT l'imagerie indisponible, « Enregistrer » s'active ──
  await page.goto(`/calepinage/${cal.id}`)
  await expect(page.getByText(STATUT).first(), 'le statut nomme l’imagerie indisponible').toBeVisible({ timeout: 120_000 })
  const statut = page.locator('#rp9-status')
  await expect(statut, '`#rp9-status` n’est plus « Chargement… »').not.toHaveText(/^Chargement/, { timeout: 120_000 })
  const enregistrer = page.getByRole('button', { name: 'Enregistrer le calepinage' })
  await expect(enregistrer, '« Enregistrer le calepinage » visible').toBeVisible({ timeout: 120_000 })
  await expect(enregistrer, '« Enregistrer le calepinage » ACTIF (scène hydratée)').toBeEnabled({ timeout: 120_000 })
  // Pas de blocage « Carte indisponible » côté ERP : la clé publiée existe, c'est le STYLE qui est refusé.
  await expect(page.getByRole('alert').filter({ hasText: 'clé MapTiler' })).toHaveCount(0)

  // ── 2. enregistrement : 200 ──
  const reponse = page.waitForResponse((x) => x.request().method() !== 'GET'
    && new RegExp(`/calepinage/calepinages/${cal.id}/layout/(?:$|\\?)`).test(x.url()), { timeout: 60_000 })
  await enregistrer.click()
  const rep = await reponse
  expect(rep.status(), `enregistrement du calepinage : 200 (${rep.request().method()} ${rep.url()})`).toBe(200)
  await expect(page.getByTestId('cal-erreur-enregistrement')).toHaveCount(0, { timeout: 15_000 })

  // ── 3. persistance : le fond de repli n'est JAMAIS écrit dans le document ; rouvrir ⇒ conception identique ──
  const enregistre = await lireLayout(cal.id)
  expect(enregistre.layout, 'le document enregistré existe').toBeTruthy()
  const layoutEnregistre = JSON.stringify(enregistre.layout)
  expect(layoutEnregistre, 'aucune trace du fond de repli dans le document').not.toContain('fond-sans-imagerie')
  expect(layoutEnregistre, 'aucune trace de l’URL du fournisseur dans le document').not.toContain('api.maptiler.com')
  expect((enregistre.layout?.zones || []).length, 'les deux pans de la conception sont toujours là').toBe((avant.layout?.zones || []).length)
  expect((avant.layout?.zones || []).length, 'la conception de départ a bien deux pans').toBe(2)

  // ── 4. imagerie « remise » : la clé publique lue à l'exécution (sinon rechargement sans blocage) ; document identique ──
  if (cleReelle) cleServie = cleReelle
  styleRefuse = false
  await page.reload()
  const enregistrer2 = page.getByRole('button', { name: 'Enregistrer le calepinage' })
  await expect(enregistrer2, 'rouvert : l’atelier boote et « Enregistrer » est actif').toBeEnabled({ timeout: 120_000 })
  const relu = await lireLayout(cal.id)
  expect(JSON.stringify(relu.layout), 'rechargement avec imagerie : conception identique au document enregistré').toBe(layoutEnregistre)
  console.log(`[ACAL377] rechargement avec ${cleReelle ? 'la clé publique lue à l’exécution' : 'clé factice non bloquée'} ; statut : ${(await page.locator('#rp9-status').innerText()).slice(0, 160)}`)

  // Nettoyage.
  await py(`from apps.calepinage.models import Calepinage
Calepinage.objects.filter(pk=${Number(cal.id)}).delete()
sortie(1)`)
})

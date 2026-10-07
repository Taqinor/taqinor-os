// AGR318 — CLÔTURE DE LA VAGUE AGR : aller-retour EN DIRECT d'un devis agricole,
// de la création à l'écran jusqu'au lien public (leçon QJR5 du 02/10 :
// « déployable ≠ vert », la preuve se fait en direct, pile locale `seed_demo`).
//
//   1. création depuis `/ventes/devis/nouveau` (marché Agricole, pompe chiffrée
//      sans courbe), enregistrement, réouverture, ré-enregistrement sans rien
//      toucher → `etude_params` IDENTIQUE ;
//   2. `/proposal` au format complet → PDF de 3 pages ; une page → 1 page
//      (même moteur que `generer-pdf`, règle #4) ;
//   3. lien de partage → `GET /public/proposal/<token>/data/` : `synthese_agricole`
//      présent, `quote.eco_s_ann` et `quote.roi_s` NULS (aucun chiffre
//      résidentiel), `mode_kpis` sans `bassin_m3` ni `fda_eligible`, aucun
//      « 30 % » isolé ;
//   4. (optionnel, `WEB_URL` = apps/web en dev) page /proposition capturée en
//      FR puis en AR, jointe au rapport.
// Aucun mock réseau. Base partagée, workers: 1 : nettoyage best-effort.
import { test, expect } from '@playwright/test'
import { choisirMarche } from './helpers'

const API = '/api/django'
const devisIds = []

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

/** Nombre de pages d'un PDF, lu sur ses objets /Type /Page (pas /Pages). */
function nombrePages(octets) {
  const texte = Buffer.from(octets).toString('latin1')
  return (texte.match(/\/Type\s*\/Page(?![s\w])/g) || []).length
}

async function premierClient(request) {
  const corps = await json(await request.get(`${API}/crm/clients/`), 'clients')
  const liste = Array.isArray(corps) ? corps : (corps.results || [])
  expect(liste.length, 'seed_demo doit fournir au moins un client').toBeGreaterThan(0)
  return liste[0]
}

test.describe.configure({ mode: 'serial' })

let devisId = null
let etudeAvant = null

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('AGR318 — créer, rouvrir, ré-enregistrer : etude_params identique', async ({ page, request }) => {
  test.setTimeout(240_000)
  const client = await premierClient(request)
  await page.goto('/ventes/devis/nouveau')
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await expect(page.locator('table.lines-table tbody tr').first())
    .toBeVisible({ timeout: 45_000 })
  await page.locator('#gen-client').click()
  await page.locator('[role="searchbox"]').last().fill(client.nom || client.name || '')
  await page.locator('[role="option"]').first().click()
  await choisirMarche(page, /Agricole/)
  await page.getByRole('radio', { name: 'Pompe neuve' }).click()
  await page.getByRole('radio', { name: 'Volume déclaré' }).click()
  await page.locator('#gen-besoin-volume').fill('40')
  await page.locator('#gen-hmt').fill('60')
  await page.getByRole('radio', { name: /Tri 380V/ }).click()
  await expect(page.getByTestId('resultat-pompage')).toBeVisible({ timeout: 45_000 })
  await page.getByTestId('btn-auto-remplir').click()
  await expect(page.getByTestId('pompage-auto-rempli')).toBeVisible({ timeout: 30_000 })

  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const corps = await (await creation).json()
  await expect(page.getByText('Devis enregistré')).toBeVisible({ timeout: 45_000 })
  devisId = corps.id ?? corps.devis?.id
  expect(devisId, 'identifiant du devis créé').toBeTruthy()
  devisIds.push(devisId)

  etudeAvant = (await json(await request.get(`${API}/ventes/devis/${devisId}/`), 'devis')).etude_params
  expect(etudeAvant.mode_pompe).toBe('neuve')

  // Rouvrir, ré-enregistrer sans rien toucher.
  await page.goto(`/ventes/devis/nouveau?edit=${devisId}`)
  await expect(page.getByTestId('bloc-cas-pompe')).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('#gen-besoin-volume')).toHaveValue('40')
  const sauvegarde = page.waitForResponse((r) => r.request().method() !== 'GET'
    && new RegExp(`/ventes/devis/${devisId}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Enregistrer/ }).first().click()
  await sauvegarde
  await expect.poll(async () => {
    const relu = await json(await request.get(`${API}/ventes/devis/${devisId}/`), 'devis relu')
    return relu.etude_params
  }, { timeout: 30_000, message: 'etude_params identique après réouverture' }).toEqual(etudeAvant)
})

test('AGR318 — /proposal : 3 pages au format complet, 1 page en une-page', async ({ request }) => {
  test.setTimeout(180_000)
  expect(devisId, 'le test de création doit précéder').toBeTruthy()
  const complet = await request.get(`${API}/ventes/devis/${devisId}/proposal/?pdf_mode=full`)
  expect(complet.status(), '/proposal full').toBe(200)
  expect(nombrePages(await complet.body()), 'pages du format complet').toBe(3)
  const unePage = await request.get(`${API}/ventes/devis/${devisId}/proposal/?pdf_mode=onepage`)
  expect(unePage.status(), '/proposal onepage').toBe(200)
  expect(nombrePages(await unePage.body()), 'pages de la une-page').toBe(1)
})

test('AGR318 — lien public : synthèse agricole, aucun chiffre résidentiel', async ({ request }) => {
  expect(devisId, 'le test de création doit précéder').toBeTruthy()
  const lien = await json(await request.post(`${API}/ventes/devis/${devisId}/share-link/`,
    { data: {} }), 'lien de partage')
  const jeton = lien.token_interne
  expect(jeton, 'jeton interne de la proposition').toBeTruthy()
  const data = await json(await request.get(`${API}/public/proposal/${jeton}/data/`),
    'données publiques')
  expect(data.synthese_agricole, 'synthese_agricole').toBeTruthy()
  expect(data.quote?.eco_s_ann ?? null, 'quote.eco_s_ann').toBeNull()
  expect(data.quote?.roi_s ?? null, 'quote.roi_s').toBeNull()
  const kpis = data.mode_kpis || {}
  expect('bassin_m3' in kpis, 'mode_kpis.bassin_m3').toBeFalsy()
  expect('fda_eligible' in kpis, 'mode_kpis.fda_eligible').toBeFalsy()
  // Aucun « 30 % » isolé (le taux de subvention n'est jamais promis seul).
  expect(JSON.stringify(data)).not.toMatch(/(^|[^\d.,])30\s?%/)

  test.info().annotations.push({ type: 'jeton', description: jeton })
})

test('AGR318 — page /proposition en FR et en AR (apps/web en dev, WEB_URL requis)', async ({ page, request }) => {
  test.skip(!process.env.WEB_URL, 'WEB_URL (apps/web en dev) non fourni : captures non prises')
  expect(devisId, 'le test de création doit précéder').toBeTruthy()
  const lien = await json(await request.post(`${API}/ventes/devis/${devisId}/share-link/`,
    { data: {} }), 'lien de partage')
  for (const langue of ['fr', 'ar']) {
    await page.goto(`${process.env.WEB_URL}/proposition/${lien.token_interne}`)
    await page.locator(`#prop-lang-${langue}`).click()
    await expect(page.locator('body')).toContainText(/\S/, { timeout: 30_000 })
    await test.info().attach(`proposition-${langue}`, {
      body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
    })
  }
})

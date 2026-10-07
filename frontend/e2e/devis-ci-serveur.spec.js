// CIQ126 — ALLER-RETOUR EN DIRECT du générateur commercial : Auto-remplir,
// enregistrer et rouvrir passent par le SERVEUR (aperçu `etude-ci/preview`,
// CIQ118/CIQ124), le navigateur n'envoie que les ENTRÉES C&I v2 (contrat
// `etude_ci_preview.json`, `cles_etude_params_ci_v2.entrees`).
//
// Pile locale `seed_demo`, aucun mock réseau. Lead commercial (le premier de la
// démo, passé en marché Commercial à l'écran) → Édition complète → profil
// déclaré (12 mois) → Auto-remplir (lignes de la composition serveur) →
// enregistrer → rouvrir (`?edit=`) ⇒ mêmes lignes et même taille que l'aperçu,
// aucune clé v1 (taux_autoconso, payback, part_diurne_pct…) écrite.
// Nettoyage best-effort en afterAll (base partagée, workers: 1).
import { test, expect } from '@playwright/test'
import { choisirMarche, declarerProfilCi } from './helpers'

const API = '/api/django'
const KWH = [9800, 9200, 10100, 10800, 12500, 14800, 17200, 17600, 14900, 12100, 10200, 9900]
const CLES_V1 = ['taux_autoconso', 'taux_couverture', 'payback', 'part_diurne_pct',
  'etude_kwc_base', 'injection_kwh_an', 'injection_dh_an']
const devisIds = []

async function json(res, quoi) {
  expect(res.ok(), `${quoi} → HTTP ${res.status()} ${await res.text()}`).toBeTruthy()
  return res.json()
}

async function premierLead(request) {
  const corps = await json(await request.get(`${API}/crm/leads/`), 'leads')
  const liste = Array.isArray(corps) ? corps : (corps.results || [])
  expect(liste.length, 'seed_demo doit fournir au moins un lead').toBeGreaterThan(0)
  return liste.find((l) => l.type_installation === 'commercial') || liste[0]
}

const lignesComparables = (devis) => (devis.lignes || []).map((l) => ({
  produit: l.produit, designation: l.designation, quantite: Number(l.quantite),
}))

test.describe.configure({ mode: 'serial' })

test.afterAll(async ({ request }) => {
  await Promise.all(devisIds.map((id) =>
    request.delete(`${API}/ventes/devis/${id}/`).catch(() => null)))
})

test('CIQ126 — commercial : Auto-remplir (moteur serveur), enregistrer, rouvrir = mêmes lignes et même taille', async ({ page, request }) => {
  test.setTimeout(240_000)
  const lead = await premierLead(request)
  await page.goto(`/ventes/devis/nouveau?lead=${lead.id}`)
  await expect(page.getByRole('heading', { name: 'Générateur de Devis Solaire' }))
    .toBeVisible({ timeout: 30_000 })
  await choisirMarche(page, /Commercial/)
  await expect(page.getByTestId('ci-profil')).toBeVisible()
  for (let i = 0; i < 12; i += 1) await page.locator(`#gen-ci-kwh-${i}`).fill(String(KWH[i]))
  // Calendrier + contrat : le moteur C&I n'en suppose aucun (voir le helper).
  await declarerProfilCi(page)

  // L'aperçu serveur répond (aucun calcul local) : la taille retenue s'affiche.
  const tailleApercu = page.getByTestId('ci-taille-retenue')
  await expect(tailleApercu).toBeVisible({ timeout: 45_000 })
  const texteTaille = await tailleApercu.textContent()

  const auto = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/etude-ci\/preview\/$/.test(new URL(r.url()).pathname))
  await page.getByTestId('btn-auto-remplir').click()
  const apercu = await (await auto).json()

  const creation = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/atomic\/$/.test(new URL(r.url()).pathname) && r.status() < 300)
  // Les entrées C&I v2 partent APRÈS la création, par la fusion
  // `PATCH …/etude-params/` (QJR62, DevisGenerator) : relire le devis avant
  // cette réponse lisait un etude_params sans `mode` (nocturne 37585800165).
  const etudeEcrite = page.waitForResponse((r) => r.request().method() === 'PATCH'
    && /\/ventes\/devis\/\d+\/etude-params\/$/.test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: /Créer le devis/ }).click()
  const cree = await (await creation).json()
  await etudeEcrite
  const id = cree.id ?? cree.devis?.id
  expect(id, 'identifiant du devis créé').toBeTruthy()
  devisIds.push(id)

  const avant = await json(await request.get(`${API}/ventes/devis/${id}/`), 'devis')
  const etude = avant.etude_params || {}
  expect(etude.mode).toBe('commercial')
  expect(etude.consommation?.kwh_mensuels).toEqual(KWH)
  for (const k of CLES_V1) expect(etude, `clé v1 ${k} jamais écrite`).not.toHaveProperty(k)
  // Les lignes enregistrées sont celles de la composition serveur (prix connus).
  const designationsMoteur = (apercu.composition?.lignes || [])
    .filter((l) => l.prix_connu).map((l) => l.designation)
  for (const d of designationsMoteur) {
    expect(lignesComparables(avant).some((l) => l.designation === d), d).toBeTruthy()
  }

  // Rouvrir puis ré-enregistrer sans toucher : même objet serveur, même taille.
  await page.goto(`/ventes/devis/nouveau?edit=${id}`)
  await expect(page.locator('#gen-ci-kwh-0')).toHaveValue(String(KWH[0]), { timeout: 45_000 })
  await expect(page.getByTestId('ci-taille-retenue')).toHaveText(texteTaille, { timeout: 45_000 })
  const sauvegarde = page.waitForResponse((r) => ['PUT', 'POST', 'PATCH'].includes(r.request().method())
    && new RegExp(`/ventes/devis/${id}/replace-lines/`).test(new URL(r.url()).pathname)
    && r.status() < 300, { timeout: 60_000 })
  await page.locator('#gen-form').getByRole('button', { name: 'Enregistrer les modifications' }).click()
  await sauvegarde
  const apres = await json(await request.get(`${API}/ventes/devis/${id}/`), 'devis rouvert')
  expect(lignesComparables(apres)).toEqual(lignesComparables(avant))
  for (const cle of ['mode', 'consommation', 'rythme', 'toit', 'tension', 'taille_explicite_kwc']) {
    expect(apres.etude_params[cle], `etude_params.${cle} identique`).toEqual(etude[cle])
  }
})

// CIQ127 — bouton « Devis automatique » de la fiche d'un lead commercial :
// UN appel `POST /ventes/devis/auto/` (autoQuote.js), le serveur crée le
// brouillon avec les lignes de SON moteur C&I, aucune clé v1 écrite.
test('CIQ127 — devis automatique commercial depuis la fiche lead : brouillon aux lignes du moteur', async ({ page, request }) => {
  test.setTimeout(180_000)
  const lead = await premierLead(request)
  // Une taille explicite sur le lead garantit une composition chiffrable.
  await json(await request.patch(`${API}/crm/leads/${lead.id}/`, {
    data: { type_installation: 'commercial', taille_souhaitee_kwc: '20' },
  }), 'lead commercial')
  await page.goto(`/crm/leads/${lead.id}`)
  const appel = page.waitForResponse((r) => r.request().method() === 'POST'
    && /\/ventes\/devis\/auto\/$/.test(new URL(r.url()).pathname), { timeout: 60_000 })
  await page.getByRole('button', { name: /Devis automatique/ }).first().click()
  const reponse = await appel
  expect(reponse.status(), await reponse.text()).toBeLessThan(300)
  const cree = await reponse.json()
  devisIds.push(cree.id)
  const devis = await json(await request.get(`${API}/ventes/devis/${cree.id}/`), 'devis auto')
  expect(devis.statut).toBe('brouillon')
  expect((devis.lignes || []).length).toBeGreaterThan(0)
  for (const k of CLES_V1) expect(devis.etude_params || {}, `clé v1 ${k}`).not.toHaveProperty(k)
})

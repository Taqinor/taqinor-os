// Acceptation en direct — revue du module chantiers (groupe ACHT), parcours
// fondateur de bout en bout : admin prépare le matériel et les interventions,
// le technicien exécute sa journée (prépa, trajet, photos, séries, signature,
// retour dépôt), l'admin relit le résultat. Format : `_format.md`.
//
// Données : celles de `seed_demo` (chantier du devis DEV-DEMO-0003, technicien
// demo_tech, intervention « Pose » du jour). Étapes jouées dans l'ordre (le
// parcours est une histoire : S4 exécute ce que S1-S3 ont préparé), mais
// chacune relit l'état serveur et s'arrête par un échec EXPLICITE si sa donnée
// manque.
//
// « Non couvert » : une étape dont la donnée n'est pas semée (ex. aucun manque
// à commander) lève `nonCouvert(...)`. L'étape est alors enregistrée FAIL avec
// la raison « non couvert : … » en notes — elle ne couvre RIEN (jamais un PASS
// creux). Les libellés des écrans encore en construction sont ceux du brief.
import { expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { connexionApi, lireJson, listeDe } from '../helpers.js'

const etape = groupe('ACHT', ['ACHT-CHANTIER-PARCOURS'])
const API = '/api/django/installations'
const TECH = { username: 'demo_tech', password: 'Demo@2026!' }
const REF_DEVIS = 'DEV-DEMO-0003'

// Un pixel JPEG valide (1×1, blanc).
const JPEG_1X1 = Buffer.from(
  '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////'
  + 'wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=',
  'base64')
const photo = (nom) => ({ name: nom, mimeType: 'image/jpeg', buffer: JPEG_1X1 })

const nonCouvert = (raison) => { throw new Error(`non couvert : ${raison}`) }

// Chantier du devis accepté de démonstration.
async function chantierDemo(request) {
  const corps = await lireJson(await request.get(`${API}/chantiers/?page_size=200`), 'chantiers')
  const c = listeDe(corps).find((x) => JSON.stringify(x).includes(REF_DEVIS))
  if (!c) nonCouvert(`chantier de ${REF_DEVIS} introuvable (seed_demo à relancer)`)
  return c
}

// Intervention « Pose » du chantier démo, assignée à demo_tech.
async function poseDemo(request, chantierId) {
  const corps = await lireJson(
    await request.get(`${API}/interventions/?installation=${chantierId}&page_size=100`), 'interventions')
  const iv = listeDe(corps).find((x) => x.type_intervention === 'pose')
  if (!iv) nonCouvert('intervention Pose du chantier démo absente (seed_demo)')
  return iv
}

async function ouvrirChantier(page, id, onglet) {
  await page.goto(`/chantiers?id=${id}`)
  await expect(page.getByRole('dialog')).toBeVisible()
  if (onglet) await page.getByRole('tab', { name: onglet }).click()
}

// Contexte NEUF connecté en technicien (le projet s'exécute en demo_admin).
async function pageTechnicien(browser, suivi, baseURL) {
  const ctx = await browser.newContext({ baseURL, serviceWorkers: 'block' })
  const p = suivi.surveiller(await ctx.newPage())
  await connexionApi(p.request, TECH)
  await p.context().addInitScript(() => {
    try { localStorage.setItem('taqinor.onboardingTerrain.anonyme', '1') } catch { /* indisponible */ }
  })
  return { p, ctx }
}

etape('S1', ['ACHT-CHANTIER-PARCOURS'], async ({ page }) => {
  // Approvisionnement visible SANS clic « Calculer », chantier « Prêt à poser ».
  const c = await chantierDemo(page.request)
  await ouvrirChantier(page, c.id, /Matériel/)
  await expect(page.getByRole('button', { name: /^Calculer$/ })).toHaveCount(0)
  await expect(page.getByRole('table').first()).toBeVisible()
  await expect(page.getByText(/Prêt à poser/).first()).toBeVisible()
  await page.reload() // persistance : rechargé, l'état est relu du serveur
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('tab', { name: /Matériel/ }).click()
  await expect(page.getByRole('table').first()).toBeVisible()
})

etape('S2', ['ACHT-CHANTIER-PARCOURS'], async ({ page }) => {
  // « Commander les manques » crée le(s) BCF et le chantier passe « Matériel commandé ».
  const c = await chantierDemo(page.request)
  await ouvrirChantier(page, c.id, /Matériel/)
  const bouton = page.getByRole('button', { name: 'Commander les manques' })
  if (!(await bouton.isVisible().catch(() => false)) || await bouton.isDisabled()) {
    nonCouvert('aucun manque à commander dans les données semées (stock démo suffisant)')
  }
  await bouton.click()
  await expect(page.getByText(/Matériel commandé/).first()).toBeVisible()
  await page.reload()
  await expect(page.getByText(/Matériel commandé/).first()).toBeVisible()
  const relu = await lireJson(await page.request.get(`${API}/chantiers/${c.id}/`), 'chantier relu')
  expect(relu.statut).toBe('materiel_commande')
})

etape('S3', ['ACHT-CHANTIER-PARCOURS'], async ({ page }) => {
  // Onglet Interventions : l'intervention Pose existe ; « Créer les interventions standard » est idempotent.
  const c = await chantierDemo(page.request)
  await ouvrirChantier(page, c.id, /Interventions/)
  const creer = page.getByRole('button', { name: 'Créer les interventions standard' })
  if (await creer.isVisible().catch(() => false)) await creer.click()
  await expect(page.getByText(/Pose/).first()).toBeVisible()
  const iv = await poseDemo(page.request, c.id)
  expect(iv.technicien, 'Pose assignée à demo_tech').toBeTruthy()
  await page.reload() // persistance
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('tab', { name: /Interventions/ }).click()
  await expect(page.getByText(/Pose/).first()).toBeVisible()
})

etape('S4', ['ACHT-CHANTIER-PARCOURS'], async ({ page, suivi, testInfo, context }) => {
  // demo_tech : « Ma journée » montre la Pose ; Prépa « Tout est chargé », Trajet « Départ dépôt » puis « Check-in ».
  const c = await chantierDemo(page.request)
  const iv = await poseDemo(page.request, c.id)
  const { p, ctx } = await pageTechnicien(context.browser(), suivi, testInfo.project.use.baseURL)
  try {
    await p.goto('/ma-journee')
    await expect(p.getByText(/Pose/).first()).toBeVisible()
    await p.getByText(/Pose/).first().click()
    await expect(p.getByRole('dialog')).toBeVisible()
    await p.getByRole('tab', { name: /Prépa/ }).click()
    await p.getByRole('button', { name: /Tout est chargé/ }).click()
    await p.getByRole('tab', { name: /Trajet/ }).click()
    await p.getByRole('button', { name: /Départ dépôt/ }).click()
    await p.getByRole('button', { name: /Check-in/ }).click()
    await expect.poll(async () => (await lireJson(
      await p.request.get(`${API}/interventions/${iv.id}/`), 'intervention')).statut,
    { timeout: 20_000 }).toBe('sur_site')
  } finally { await ctx.close() }
})

etape('S5', ['ACHT-CHANTIER-PARCOURS'], async ({ page, suivi, testInfo, context }) => {
  // Photos : une image dans chaque emplacement obligatoire.
  const c = await chantierDemo(page.request)
  const iv = await poseDemo(page.request, c.id)
  const { p, ctx } = await pageTechnicien(context.browser(), suivi, testInfo.project.use.baseURL)
  try {
    await p.goto('/ma-journee')
    await p.getByText(/Pose/).first().click()
    await p.getByRole('tab', { name: 'Photos' }).click()
    const champs = p.locator('input[type="file"]')
    const n = await champs.count()
    if (n === 0) nonCouvert('aucun emplacement photo obligatoire affiché')
    for (let i = 0; i < n; i += 1) await champs.nth(i).setInputFiles(photo(`acceptation-${i}.jpg`))
    await expect.poll(async () => listeDe(await lireJson(
      await p.request.get(`${API}/interventions/${iv.id}/photos/`), 'photos')).length,
    { timeout: 30_000 }).toBeGreaterThanOrEqual(n)
  } finally { await ctx.close() }
})

etape('S6', ['ACHT-CHANTIER-PARCOURS'], async ({ page, suivi, testInfo, context }) => {
  // N° série : progression « x/N », ajout d'une série pour le panneau depuis le select.
  const c = await chantierDemo(page.request)
  const iv = await poseDemo(page.request, c.id)
  const { p, ctx } = await pageTechnicien(context.browser(), suivi, testInfo.project.use.baseURL)
  try {
    await p.goto('/ma-journee')
    await p.getByText(/Pose/).first().click()
    await p.getByRole('tab', { name: /N° série|Séries/ }).click()
    await expect(p.getByText(/\d+\s*\/\s*\d+/).first()).toBeVisible()
    await expect(p.getByRole('button', { name: /Scanner/ })).toBeVisible()
    const select = p.getByRole('combobox').first()
    await select.selectOption({ index: 1 })
    const sn = `ACC-SN-${Date.now().toString(36)}`
    await p.getByPlaceholder(/N° de série/).fill(sn)
    await p.getByRole('button', { name: /Ajouter/ }).click()
    await expect(p.getByText(sn)).toBeVisible()
    await p.reload() // persistance
    await p.getByText(/Pose/).first().click()
    await p.getByRole('tab', { name: /N° série|Séries/ }).click()
    await expect(p.getByText(sn)).toBeVisible()
    const series = listeDe(await lireJson(await p.request.get(`${API}/interventions/${iv.id}/serials/`), 'séries'))
    expect(series.some((s) => s.numero_serie === sn)).toBeTruthy()
  } finally { await ctx.close() }
})

etape('S7', ['ACHT-CHANTIER-PARCOURS'], async ({ page, suivi, testInfo, context }) => {
  // Signature client puis « Retour dépôt » : l'intervention passe « Terminée ».
  const c = await chantierDemo(page.request)
  const iv = await poseDemo(page.request, c.id)
  const { p, ctx } = await pageTechnicien(context.browser(), suivi, testInfo.project.use.baseURL)
  try {
    await p.goto('/ma-journee')
    await p.getByText(/Pose/).first().click()
    await p.getByRole('tab', { name: /Signature/ }).click()
    const zone = p.locator('canvas').first()
    await expect(zone).toBeVisible()
    const box = await zone.boundingBox()
    await p.mouse.move(box.x + 20, box.y + 20)
    await p.mouse.down()
    await p.mouse.move(box.x + box.width - 20, box.y + box.height - 20, { steps: 8 })
    await p.mouse.up()
    const accord = p.getByLabel(/J'ai lu et j'accepte/)
    if (await accord.count()) await accord.check()
    await p.getByRole('button', { name: /Enregistrer la signature|Valider/ }).first().click()
    await p.getByRole('tab', { name: /Trajet/ }).click()
    await p.getByRole('button', { name: /Retour dépôt/ }).click()
    await expect.poll(async () => (await lireJson(
      await p.request.get(`${API}/interventions/${iv.id}/`), 'intervention')).statut,
    { timeout: 20_000 }).toBe('terminee')
  } finally { await ctx.close() }
})

etape('S8', ['ACHT-CHANTIER-PARCOURS'], async ({ page }) => {
  // Retour admin : photos Avant/Après, séries comptées, Suivi GPS avec la liste des consentements.
  const c = await chantierDemo(page.request)
  await ouvrirChantier(page, c.id, 'Photos')
  await expect(page.getByText(/Avant/).first()).toBeVisible()
  await expect(page.getByText(/Après/).first()).toBeVisible()
  await page.getByRole('tab', { name: /Matériel/ }).click()
  await expect(page.getByText(/série/i).first()).toBeVisible()
  await page.goto('/planification/suivi-gps')
  await expect(page.getByText(/Position partagée/).first()).toBeVisible()
  await page.reload() // persistance
  await expect(page.getByText(/Position partagée/).first()).toBeVisible()
})

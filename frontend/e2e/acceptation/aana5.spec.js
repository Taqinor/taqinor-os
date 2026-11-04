// ERR-ACC-ACCUEIL-403-LECTEUR — preuve en direct sur la pile locale : l'accueil du rôle Lecteur (Viewer) ne monte
// plus `MesEquipesCard` (GET /crm/equipes/statistiques/) ni `ImpactPastille` (GET /monitoring/configs/co2-fleet/) :
// aucune de ces deux requêtes, aucun toast d'erreur global. Compte d'essai du rôle « Viewer » de la société de
// demo_admin (jamais `company_id` codé en dur), désactivé en fin d'étape. Contre-épreuve : demo_admin (direction)
// lit toujours les deux cartes.
import { test, expect } from '@playwright/test'
import { groupe } from './_oracles.js'
import { py, fermerDjangoApresTout, MDP_ESSAI } from './_django.js'
import { assurerSessionPage, uiLoginJusquAuxApps } from '../helpers.js'

const etape = groupe('AANA', ['ERR-ACC-ACCUEIL-403-LECTEUR'])
fermerDjangoApresTout()
test.describe.configure({ timeout: 300_000 })
const INTERDITES = [/\/monitoring\/configs\/co2-fleet\/?/, /\/crm\/equipes\/statistiques\/?/]
// Écart accepté (base FAIL : la même étape échouait déjà avant la correction, avec en plus les deux lectures visées) :
// deux AUTRES cartes de l'accueil répondent encore 403 au Lecteur — hors ERR-ACC-ACCUEIL-403-LECTEUR.
const ECART = { base: 'FAIL', raison: "deux autres lectures de l'accueil restent refusées au Lecteur, hors de cette correction : GET /reporting/dashboard/ → 403 (carte CA « Accès réservé : chiffre d'affaires visible par la direction. », comportement voulu d'AANA60) et GET /core/fiabilite/reglages/ → 403 + console.error (SlaBadgeCard, NTOBS21 : sans toast depuis 36c72d4809 mais l'appel part encore) ; les deux lectures visées (co2-fleet, equipes/statistiques) ne partent plus et aucun toast d'erreur" }
const TOAST = '[data-sonner-toast][data-type="error"], [role="status"] .toast-error, .Toastify__toast--error'

etape('P.lecteur_accueil_sans_403', ['ERR-ACC-ACCUEIL-403-LECTEUR'], async ({ page: pageAdmin, suivi, testInfo }) => {
  await py(`a = U.objects.get(username='demo_admin')
from apps.roles.models import Role
r = Role.objects.get(company_id=a.company_id, nom='Viewer')
c = compte('erracc_lecteur', role=r.pk, societe=a.company_id)
sortie(dict(id=c.id))`)
  const ctx = await pageAdmin.context().browser().newContext({ baseURL: testInfo.project.use.baseURL, storageState: { cookies: [], origins: [] } })
  try {
    const page = suivi.surveiller(await ctx.newPage())
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor-pwa-install-dismissed', '1') } catch { /* mode privé */ }
      try { localStorage.setItem('taqinor:welcome:seen:v1', '1') } catch { /* mode privé */ }
    })
    const vues = []
    page.on('request', (q) => { if (INTERDITES.some((re) => re.test(q.url()))) vues.push(q.url()) })
    await uiLoginJusquAuxApps(page, { username: 'erracc_lecteur', password: MDP_ESSAI })
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    await page.waitForTimeout(3_000)
    expect(vues, `accueil Lecteur : aucune lecture interdite (${vues.join(', ')})`).toEqual([])
    await expect(page.locator(TOAST), 'aucun toast d\'erreur global').toHaveCount(0)
    // Persistance : rechargement ⇒ toujours aucune des deux lectures.
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForLoadState('networkidle', { timeout: 60_000 }).catch(() => undefined)
    await page.waitForTimeout(3_000)
    expect(vues, 'après rechargement').toEqual([])
    await expect(page.locator(TOAST)).toHaveCount(0)
    // L'accueil est bien rendu (carte CA du Lecteur, AANA60) — la capture de l'étape est cette page (contexte laissé ouvert).
    await expect(page.getByText("Accès réservé : chiffre d'affaires visible par la direction.")).toBeVisible({ timeout: 60_000 })
    await pageAdmin.close() // la capture de l'étape prend la première page ouverte : celle du Lecteur
  } finally {
    await py(`U.objects.filter(username='erracc_lecteur').update(is_active=False)
sortie(1)`).catch(() => null)
  }
}, { ecart: ECART })

etape('P.direction_garde_les_cartes', ['ERR-ACC-ACCUEIL-403-LECTEUR'], async ({ page }) => {
  await assurerSessionPage(page)
  const equipes = page.waitForResponse((x) => /\/crm\/equipes\/statistiques\/?/.test(x.url()), { timeout: 60_000 })
  const co2 = page.waitForResponse((x) => /\/monitoring\/configs\/co2-fleet\/?/.test(x.url()), { timeout: 60_000 })
  await page.goto('/dashboard')
  expect((await equipes).status(), 'direction : statistiques d\'équipes lues').toBe(200)
  expect((await co2).status(), 'direction : pastille d\'impact lue').toBe(200)
})

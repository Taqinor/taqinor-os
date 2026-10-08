// NTDMO37 — parcours complet « premier login sur société démo fraîche ».
// Distinct de `taqinor-demo` (la société partagée par les 34 autres specs,
// `est_demo=False` — voir helpers.js/ADMIN) : ce spec cible `taqinor-demo-full`
// (`est_demo=True`, admin `demo_admin_full`), seedée en fixture par
// `manage.py seed_demo_company` (.github/workflows/release-verify.yml, ajoutée
// pour ce spec ; `Faker`, dev-only, y est installé ponctuellement pour cette
// étape, jamais ajouté à requirements.txt). Comme `leads.spec.js`,
// ce spec vit en e2e COMPLET (release-verify), pas dans le palier smoke
// par-merge de ci.yml (qui ne seed pas `taqinor-demo-full`). Runs COLD (pas
// le storageState partagé) : c'est tout l'intérêt du scénario « premier
// login ».
import { test, expect } from '@playwright/test'
import { uiLogin, fermerMomentAccueil } from './helpers'

test.use({ storageState: { cookies: [], origins: [] } })

// Identifiants FIXES documentés dans
// `authentication/management/commands/seed_demo_company.py` (slug par défaut
// `taqinor-demo-full`) — jamais un secret, jeu de démo jetable.
const DEMO_FULL_ADMIN = { username: 'demo_admin_full', password: 'DemoFull@2026!' }

// CAD177 — UNE seule connexion UI à froid pour les quatre constats. Quatre
// connexions en ~15 s (une par test) + celles des specs voisines dépassaient
// le throttle « login » 5/min/IP (règle produit, jamais assouplie) : POST
// /token/ 429 « Requête ralentie », (2) restait sur /login (nocturne
// 37792898726). La connexion est le vrai « premier login » ; chaque test
// repart ensuite d'un contexte NEUF (localStorage vide → moment d'accueil à
// froid) muni des seuls cookies de session. Un 429 résiduel (specs voisines
// dans la même minute) est ATTENDU puis rejoué — une condition observée,
// comme `connexionApi`, jamais une pause aveugle.
let cookiesSession = null

test.beforeAll(async ({ browser }) => {
  test.setTimeout(120_000)
  const baseURL = test.info().project.use.baseURL
  const ctx = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } })
  try {
    const page = await ctx.newPage()
    await expect(async () => {
      await uiLogin(page, DEMO_FULL_ADMIN)
      await expect(page).toHaveURL(/\/apps/, { timeout: 10_000 })
    }).toPass({ intervals: [5_000, 10_000, 15_000], timeout: 90_000 })
    cookiesSession = (await ctx.storageState()).cookies
  } finally {
    await ctx.close()
  }
})

test.describe('NTDMO37 — premier login sur société démo fraîche', () => {
  test.beforeEach(async ({ page }) => {
    expect(cookiesSession, 'connexion à froid de demo_admin_full').toBeTruthy()
    await page.context().addCookies(cookiesSession)
    await page.goto('/apps')
    await expect(page).toHaveURL(/\/apps/, { timeout: 30_000 })
    // CAD177 — premier login À FROID : le moment d'accueil VX156 (c2e0fa64)
    // s'ouvre et interceptait le clic de (4) sur « Démo & Onboarding »
    // (run 36990128960). C'est le comportement voulu d'un premier login : on
    // le constate, puis on le ferme comme l'utilisateur.
    await fermerMomentAccueil(page)
  })

  test('(1) le widget « Premiers pas » affiche une progression non-nulle', async ({ page }) => {
    await page.goto('/dashboard')
    // Le widget se masque de lui-même à 100 % (NTDMO13) — sur une société
    // fraîche, aucun item de la checklist n'est encore fait : il doit rester
    // visible avec un catalogue non-vide (« Premiers pas — 0/N », N > 0).
    const heading = page.getByRole('heading', { name: /^Premiers pas — \d+\/\d+$/ })
    await expect(heading).toBeVisible({ timeout: 20_000 })
    const texte = await heading.textContent()
    const total = Number(texte.match(/\/(\d+)/)?.[1] ?? 0)
    expect(total).toBeGreaterThan(0)
  })

  test('(2) au moins une visite guidée (<ProductTour>) se déclenche sur /dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    // Le tour « dashboard » (NTDMO14) est la cible de cette route ; sa 1re
    // étape n'a pas de sélecteur (voile centré) — voir ProductTour.jsx.
    const tour = page.getByRole('dialog', { name: /^Visite guidée/ })
    await expect(tour).toBeVisible({ timeout: 20_000 })
  })

  test("(3) la bannière mode présentation n'apparaît PAS par défaut", async ({ page }) => {
    await page.goto('/dashboard')
    // `mode_presentation_actif` reste False à la création (NTDMO10/27), même
    // si `est_demo=True` — le bandeau ne s'affiche que si activé explicitement.
    await expect(page.getByTestId('presentation-mode-banner')).toHaveCount(0)
  })

  test('(4) le bouton « Réinitialiser les données de démonstration » est visible dans Paramètres', async ({ page }) => {
    await page.goto('/parametres')
    await page.getByRole('button', { name: 'Démo & Onboarding' }).click()
    await expect(page.getByTestId('demo-reset-card')).toBeVisible({ timeout: 20_000 })
    await expect(page.getByRole('button', {
      name: 'Réinitialiser les données de démonstration',
    })).toBeVisible()
  })
})

import { test, expect } from '@playwright/test'

// ── Régression VISUELLE (@visual) ───────────────────────────────────────────
// Ces captures tournent UNIQUEMENT dans release-verify.yml (manuel + nightly),
// jamais dans le smoke e2e par-merge (ci.yml). Au tout premier run il n'existe
// pas de baseline : `--update-snapshots` les génère, et le workflow les uploade
// en artefact `visual-baselines`. Le fondateur relit ces images puis les commit
// sous e2e/**-snapshots/ — la comparaison pixel devient alors un vrai garde-fou.
//
// Le projet `chromium` est pré-authentifié (storageState) et dépend de `setup`,
// donc ces tests s'exécutent connectés sur la base démo déterministe (seed_demo).

// Tolérance commune : la base démo est déterministe mais l'anti-aliasing varie.
const SHOT = { fullPage: true, animations: 'disabled', maxDiffPixelRatio: 0.02 }

test('dashboard — capture de référence', { tag: '@visual' }, async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Tableau de bord' })).toBeVisible()
  await expect(page).toHaveScreenshot('dashboard.png', SHOT)
})

// ── VX70 — Extension étroite : 5 écrans clés supplémentaires, CLAIR + SOMBRE ──
// On garde le tag @visual (tier release-verify, jamais le smoke par-merge) et la
// même tolérance. Le thème sombre est forcé au boot via localStorage
// (taqinor-theme=dark, appliqué par le ThemeProvider au montage). Contenus
// dynamiques masqués au besoin, animations coupées. PAS de couverture
// exhaustive — uniquement les surfaces à plus fort blast-radius.

// Chaque cas : un chemin, un « prêt » (heading/élément à attendre), et un nom.
const SCREENS = [
  {
    name: 'devis-list',
    path: '/ventes/devis',
    ready: (page) => expect(page.getByRole('heading', { name: 'Devis' })).toBeVisible(),
  },
  {
    name: 'leads-kanban',
    path: '/crm/leads',
    ready: async (page) => {
      await expect(page.locator('.header-title')).toBeVisible()
      await page.waitForLoadState('networkidle').catch(() => {})
    },
  },
  {
    name: 'devis-generator',
    path: '/ventes/devis/nouveau',
    ready: (page) => expect(
      page.getByRole('heading', { name: 'Générateur de Devis Solaire' }),
    ).toBeVisible(),
  },
  {
    name: 'facture-list',
    path: '/ventes/factures',
    ready: async (page) => {
      await expect(page.locator('.header-title')).toBeVisible()
      await page.waitForLoadState('networkidle').catch(() => {})
    },
  },
]

for (const { name, path, ready } of SCREENS) {
  test(`${name} — capture clair`, { tag: '@visual' }, async ({ page }) => {
    await page.goto(path)
    await ready(page)
    await expect(page).toHaveScreenshot(`${name}-light.png`, SHOT)
  })

  test(`${name} — capture sombre`, { tag: '@visual' }, async ({ page }) => {
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* mode privé */ }
    })
    await page.goto(path)
    await ready(page)
    await expect(page).toHaveScreenshot(`${name}-dark.png`, SHOT)
  })
}

// Login : écran public, capturé cold (sans état d'authentification), clair + sombre.
test.describe('login — capture (clair + sombre)', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('login — capture clair', { tag: '@visual' }, async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByPlaceholder('Entrez votre identifiant')).toBeVisible()
    await expect(page).toHaveScreenshot('login-light.png', SHOT)
  })

  test('login — capture sombre', { tag: '@visual' }, async ({ page }) => {
    await page.addInitScript(() => {
      try { localStorage.setItem('taqinor-theme', 'dark') } catch { /* mode privé */ }
    })
    await page.goto('/login')
    await expect(page.getByPlaceholder('Entrez votre identifiant')).toBeVisible()
    await expect(page).toHaveScreenshot('login-dark.png', SHOT)
  })
})

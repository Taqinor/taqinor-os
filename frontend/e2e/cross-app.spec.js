// ODY7 — E2E : suivre un lien croisé bascule la coquille sur l'app CIBLE.
//
// Le pendant vitest (`src/lib/apps/crossAppNavigate.test.jsx`) couvre les 6
// parcours croisés recensés par l'audit ; ce spec le prouve sur l'app RÉELLE
// bâtie, où la coquille est reconstruite par le vrai routeur.
//
// Les assertions portent sur `aside.sidebar[data-app]` plutôt que sur le nom
// affiché : l'attribut existe quelle que soit la largeur ou l'état replié de la
// sidebar, donc le spec ne dépend d'aucune décision de mise en page.
import { test, expect } from '@playwright/test'

// { chemin, clé d'app attendue, préfixe d'une AUTRE app qui ne doit jamais
//   apparaître dans la nav de celle-ci }
const STOPS = [
  { path: '/crm/leads', app: 'crm', foreign: '/ventes' },
  { path: '/ventes/devis', app: 'ventes', foreign: '/crm' },
  { path: '/chantiers', app: 'installations', foreign: '/ventes' },
  { path: '/sav', app: 'sav', foreign: '/crm' },
  { path: '/stock', app: 'stock', foreign: '/sav' },
]

test('ODY7: chaque bascule inter-apps reconstruit la coquille sur l’app cible', async ({ page }) => {
  for (const stop of STOPS) {
    await page.goto(stop.path)
    // La coquille authentifiée est bien rendue (ancre e2e historique).
    await expect(page.locator('.header-title')).toBeVisible()
    // 1. l'identité de la coquille EST celle de l'app de la route…
    await expect(page.locator('aside.sidebar')).toHaveAttribute('data-app', stop.app)
    // 2. …et la nav ne contient AUCUNE destination d'une autre app.
    await expect(
      page.locator(`aside.sidebar .sidebar-nav a[href^="${stop.foreign}"]`),
      `fuite d'une autre app dans la nav de ${stop.app}`,
    ).toHaveCount(0)
    // 3. la sortie canonique vers le Menu d'accueil est toujours offerte.
    await expect(page.getByRole('link', { name: 'Toutes les apps' })).toHaveCount(1)
  }
})

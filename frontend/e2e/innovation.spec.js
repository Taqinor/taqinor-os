// NTIDE59/60/61 — module Innovation (boîte à idées interne) : proposer une
// idée, voter, et le cycle examiner→retenir (admin). Un seul fichier — même
// esprit que activities.spec.js/doublons.spec.js : plusieurs scénarios liés
// au même module, DB seedée partagée (E2E_BASE_URL, seed_demo), donc chaque
// idée créée porte un titre `uniq()` pour ne jamais collisionner entre runs.
import { test, expect } from '@playwright/test'
import { uniq } from './helpers'

// ── NTIDE59 — proposer une idée ──────────────────────────────────────────────
test('NTIDE59: propose une idée, redirige vers le détail, apparaît dans « Mes idées »', async ({ page }) => {
  const titre = uniq('Idée E2E')

  await page.goto('/innovation/proposer')
  await expect(page.getByRole('heading', { name: 'Proposer une idée' })).toBeVisible()

  await page.getByLabel('Titre').fill(titre)
  await page.getByLabel('Description').fill('Décrite par le test E2E NTIDE59.')
  await page.getByRole('button', { name: "Proposer l'idée" }).click()

  // Redirection vers le détail (NTIDE8/NTIDE5) — le titre y est le heading.
  await expect(page).toHaveURL(/\/innovation\/idees\/\d+$/)
  await expect(page.getByRole('heading', { name: titre })).toBeVisible()

  // Apparaît dans « Mes idées » (NTIDE15, filtre owner = utilisateur connecté).
  // DataTable rend TOUJOURS desktop (table) + mobile (cartes) dans le DOM,
  // basculés par CSS uniquement (data-dt-table/data-dt-cards) — scoper à la
  // table desktop pour éviter un double-match strict-mode.
  await page.goto('/innovation/mes-idees')
  await expect(page.getByRole('heading', { name: 'Mes idées' })).toBeVisible()
  await expect(page.locator('[data-dt-table]').getByText(titre)).toBeVisible()
})

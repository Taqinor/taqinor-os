import { test, expect } from '@playwright/test'

// SCAFFOLD — parcours e2e « réel utilisateur » pour le module SAV.
// À remplir : `bash scripts/e2e-local.sh` puis
// `npx playwright codegen http://localhost:4173/sav` (cf. docs/TESTING.md).
// `test.fixme` = NON exécuté tant que non implémenté (TODO visible, ne casse pas
// la suite). À l'implémentation : enlever `.fixme`, test AUTONOME, noms uniques
// via `uniq()`.
test.fixme('E-SAV: ouvrir un ticket → assigner un technicien → clôturer', async ({ page }) => {
  await page.goto('/sav')
  await expect(page.getByRole('heading', { name: /sav|ticket|maintenance/i })).toBeVisible()
  // TODO (codegen) :
  //  1. créer un ticket (sur un équipement seedé si présent),
  //  2. assigner un technicien (ex. demo_resp),
  //  3. clôturer le ticket, puis ASSERTER le statut visible (clôturé/fermé).
})

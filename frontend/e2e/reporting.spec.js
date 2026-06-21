import { test, expect } from '@playwright/test'

// SCAFFOLD — parcours e2e « réel utilisateur » pour le module REPORTING.
// À remplir : `bash scripts/e2e-local.sh` puis
// `npx playwright codegen http://localhost:4173/reporting` (cf. docs/TESTING.md).
// `test.fixme` = NON exécuté tant que non implémenté (TODO visible, ne casse pas
// la suite). À l'implémentation : enlever `.fixme`. Lecture seule → bon candidat
// pour le smoke par-merge une fois autonome.
test.fixme('E-REPORTING: ouvrir un tableau de bord → filtrer → exporter', async ({ page }) => {
  await page.goto('/reporting')
  await expect(page.getByRole('heading', { name: /rapport|reporting|tableau de bord/i })).toBeVisible()
  // TODO (codegen) :
  //  1. ouvrir un dashboard / rapport (ventes, stock, service…),
  //  2. appliquer un filtre ou une plage de dates,
  //  3. déclencher un export (XLSX/PDF) et ASSERTER le téléchargement
  //     (page.waitForEvent('download')) ou le rendu mis à jour.
})

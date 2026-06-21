import { test, expect } from '@playwright/test'

// SCAFFOLD — parcours e2e « réel utilisateur » pour le module INSTALLATIONS.
// À remplir : `bash scripts/e2e-local.sh` puis
// `npx playwright codegen http://localhost:4173/installations` (cf. docs/TESTING.md).
// `test.fixme` = NON exécuté tant que non implémenté (TODO visible, ne casse pas
// la suite). Au moment d'implémenter : enlever `.fixme`, garder le test AUTONOME
// (un devis accepté est un PRÉ-REQUIS — le créer dans le test, pas dépendre d'un
// autre spec, cf. la leçon leads.spec).
test.fixme('E-INSTALL: créer un chantier depuis un devis accepté → ajouter une intervention', async ({ page }) => {
  await page.goto('/installations')
  await expect(page.getByRole('heading', { name: /chantier|installation/i })).toBeVisible()
  // TODO (codegen) :
  //  1. partir d'un devis ACCEPTÉ (le rendre accepté dans le test), créer le
  //     chantier (creer-depuis-devis),
  //  2. ouvrir le chantier, ajouter une intervention / cocher un item de
  //     checklist,
  //  3. ASSERTER l'état visible (intervention listée, item coché).
})

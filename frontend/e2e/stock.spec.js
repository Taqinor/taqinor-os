import { test, expect } from '@playwright/test'

// SCAFFOLD — parcours e2e « réel utilisateur » pour le module STOCK.
// À remplir par enregistrement : `bash scripts/e2e-local.sh` puis
// `npx playwright codegen http://localhost:4173/stock` (cf. docs/TESTING.md).
// `test.fixme` = NON exécuté tant que non implémenté → visible comme TODO dans le
// rapport sans casser la matrice e2e complète. Quand c'est prêt : enlever
// `.fixme`, et nommer tout enregistrement créé avec `uniq()` (base mutable
// partagée, suite série). Garder le test AUTONOME pour pouvoir le promouvoir en
// smoke par-merge.
test.fixme('E-STOCK: réception de stock → la quantité du produit augmente', async ({ page }) => {
  await page.goto('/stock')
  await expect(page.getByRole('heading', { name: /stock/i })).toBeVisible()
  // TODO (codegen) : ouvrir « Réception » (ou bon de commande fournisseur),
  // choisir un produit seedé (seed_catalogue), saisir une quantité unique,
  // enregistrer, puis ASSERTER l'effet visible (la quantité/mouvement reflète
  // la réception).
})

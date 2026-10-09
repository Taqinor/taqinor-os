import { expect, test } from '@playwright/test';

/**
 * YBW66 — l'appel d'une page produit pré-sélectionne le sujet du formulaire
 * (`?produit=`), seulement avec une valeur du contrat ; une valeur inconnue
 * laisse le choix vide.
 */
test('?produit=solarbow pré-sélectionne SolarBow ; une valeur inconnue ne sélectionne rien', async ({ page }) => {
  await page.goto('/rendez-vous/?produit=solarbow');
  await expect(page.locator('select[name="produit"]')).toHaveValue('solarbow');
  await page.goto('/rendez-vous/?produit=inconnu');
  await expect(page.locator('select[name="produit"]')).toHaveValue('');
});

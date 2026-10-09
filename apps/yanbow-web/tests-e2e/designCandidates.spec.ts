import { expect, test } from '@playwright/test';
import { CANDIDATS, cheminCandidat, FICHES } from '../src/styles/candidates/candidats';
import { ciblesTropPetites, debordement, LARGEURS, violationsAxe } from './gardes';

/**
 * YBW42 — les candidats du tour design dans CHAQUE schéma qu'ils rendent.
 * Le schéma clair est déjà couvert par overflow/axe/crawl (toutes les pages
 * construites) ; ici : le schéma SOMBRE de A et B (débordement aux 4 largeurs,
 * axe-core, cibles tactiles), et C qui reste CLAIR même quand le système est
 * sombre.
 */

for (const id of CANDIDATS.filter((c) => FICHES[c].schemas.includes('sombre'))) {
  for (const locale of ['fr', 'en'] as const) {
    const url = cheminCandidat(id, locale);
    test.describe(`${url} (sombre)`, () => {
      test.use({ colorScheme: 'dark' });

      for (const largeur of LARGEURS) {
        test(`@ ${largeur}px : aucun débordement`, async ({ page }) => {
          await page.setViewportSize({ width: largeur, height: 900 });
          await page.goto(url);
          expect(await debordement(page)).toEqual([]);
        });
      }

      test('0 violation axe sérieuse/critique, cibles ≥ 44 px', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 900 });
        await page.goto(url);
        expect(await violationsAxe(page)).toEqual([]);
        expect(await ciblesTropPetites(page)).toEqual([]);
      });

      test('le fond suit bien le schéma sombre', async ({ page }) => {
        await page.goto(url);
        const fond = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        const [r, g, b] = (fond.match(/\d+/g) ?? []).map(Number);
        expect(r + g + b).toBeLessThan(120);
      });
    });
  }
}

test.describe('C reste clair quand le système est sombre', () => {
  test.use({ colorScheme: 'dark' });
  for (const locale of ['fr', 'en'] as const) {
    test(cheminCandidat('c', locale), async ({ page }) => {
      await page.goto(cheminCandidat('c', locale));
      const fond = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
      expect(fond).toBe('rgb(255, 255, 255)');
      expect(await violationsAxe(page)).toEqual([]);
    });
  }
});

test.describe('menu mobile (sans script) : ouvert, il reste dans la page', () => {
  for (const id of CANDIDATS) {
    test(`${cheminCandidat(id, 'fr')} @ 320px`, async ({ page }) => {
      await page.setViewportSize({ width: 320, height: 800 });
      await page.goto(cheminCandidat(id, 'fr'));
      await page.locator('.nav-mobile summary').click();
      await expect(page.locator('.nav-mobile nav')).toBeVisible();
      expect(await debordement(page)).toEqual([]);
      expect(await ciblesTropPetites(page)).toEqual([]);
      expect(await violationsAxe(page)).toEqual([]);
    });
  }
});

import { expect, test } from '@playwright/test';
import { ciblesTropPetites, debordement, LARGEURS, pagesDuBuild } from './gardes';

/** YBW15 — aucun débordement horizontal à 320/375/768/1440 px ; cibles tactiles ≥ 44 px. */

const PIEGE_LARGE = '<!doctype html><html lang="fr"><head><title>p</title></head><body><div style="width:2000px">x</div></body></html>';
const PIEGE_PETIT =
  '<!doctype html><html lang="fr"><head><title>p</title></head><body><main><button style="width:20px;height:20px;padding:0">x</button></main></body></html>';

test.describe('preuve : les détecteurs rougissent sur une page piège', () => {
  test('débordement détecté', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.route('**/__piege/large/', (r) => r.fulfill({ contentType: 'text/html', body: PIEGE_LARGE }));
    await page.goto('/__piege/large/');
    expect(await debordement(page)).toHaveLength(1);
  });

  test('cible tactile trop petite détectée', async ({ page }) => {
    await page.route('**/__piege/petit/', (r) => r.fulfill({ contentType: 'text/html', body: PIEGE_PETIT }));
    await page.goto('/__piege/petit/');
    expect((await ciblesTropPetites(page)).join('\n')).toContain('button');
  });
});

for (const url of pagesDuBuild()) {
  for (const largeur of LARGEURS) {
    test(`${url} @ ${largeur}px : aucun débordement`, async ({ page }) => {
      await page.setViewportSize({ width: largeur, height: 900 });
      await page.goto(url);
      expect(await debordement(page)).toEqual([]);
    });
  }

  test(`${url} @ 375px : cibles tactiles ≥ 44 px`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url);
    expect(await ciblesTropPetites(page)).toEqual([]);
  });
}

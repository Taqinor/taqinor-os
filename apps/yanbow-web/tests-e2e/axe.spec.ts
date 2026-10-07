import { expect, test } from '@playwright/test';
import { pagesDuBuild, violationsAxe } from './gardes';

/** YBW15 — axe-core : 0 violation sérieuse ou critique sur chaque page FR et EN. */

// Image sans alternative + texte gris clair sur blanc : violations sérieuses connues.
const PIEGE =
  '<!doctype html><html lang="fr"><head><title>p</title></head><body><main><h1>t</h1>' +
  '<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" width="10" height="10">' +
  '<p style="color:#ddd;background:#fff">texte illisible</p></main></body></html>';

test('preuve : axe rougit sur une page piège', async ({ page }) => {
  await page.route('**/__piege/axe/', (r) => r.fulfill({ contentType: 'text/html', body: PIEGE }));
  await page.goto('/__piege/axe/');
  const v = await violationsAxe(page);
  expect(v.join('\n')).toMatch(/image-alt|color-contrast/);
});

for (const url of pagesDuBuild()) {
  test(`${url} : 0 violation axe sérieuse/critique`, async ({ page }) => {
    await page.goto(url);
    expect(await violationsAxe(page)).toEqual([]);
  });
}

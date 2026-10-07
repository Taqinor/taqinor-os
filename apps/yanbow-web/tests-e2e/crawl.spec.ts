import { expect, test } from '@playwright/test';
import { buildCsp } from '../worker/headers.mjs';
import { sourcesCsp } from '../src/lib/subprocessors';
import { crawler, installerSondes, pagesDuBuild } from './gardes';

/**
 * YBW15 — crawl : 0 erreur CSP / console / pageerror / requête échouée ;
 * 0 Set-Cookie, document.cookie vide, 0 écriture local/sessionStorage,
 * 0 service worker, 0 requête vers un hôte absent du registre (YBW26).
 * (YBW56 rejoue `crawler` après un envoi de rendez-vous vers le faux ERP.)
 */

const CSP = buildCsp(sourcesCsp());

// Piège 1 : la VRAIE CSP du site + un script en ligne → violation CSP.
const PIEGE_CSP = '<!doctype html><html lang="fr"><head><title>p</title><script>window.x=1</script></head><body></body></html>';

// Piège 2 : sans CSP, tout ce qu'un traceur ferait.
const PIEGE_TRACEUR = `<!doctype html><html lang="fr"><head><title>p</title></head><body>
<img src="https://traceur.exemple.test/pixel.gif" alt="">
<script>
  document.cookie = 'suivi=1; path=/';
  localStorage.setItem('suivi', '1');
  sessionStorage.setItem('suivi', '1');
  navigator.serviceWorker && navigator.serviceWorker.register('/sw-piege.js').catch(function () {});
  console.error('erreur plantée');
  setTimeout(function () { throw new Error('exception plantée'); }, 0);
  fetch('/__piege/absent');
</script></body></html>`;

test.describe('preuve : le crawl rougit sur des pages pièges', () => {
  test('violation CSP détectée', async ({ page }) => {
    await installerSondes(page);
    await page.route('**/__piege/csp/', (r) =>
      r.fulfill({ contentType: 'text/html; charset=utf-8', headers: { 'content-security-policy': CSP }, body: PIEGE_CSP }),
    );
    const p = (await crawler(page, '/__piege/csp/')).join('\n');
    expect(p).toMatch(/violation CSP|Content Security Policy/);
  });

  test('cookie, stockage, service worker, hôte tiers, console, exception, 404 détectés', async ({ page }) => {
    await installerSondes(page);
    await page.route('**/__piege/traceur/', (r) =>
      r.fulfill({ contentType: 'text/html; charset=utf-8', headers: { 'set-cookie': 'id=1; Path=/' }, body: PIEGE_TRACEUR }),
    );
    await page.route('https://traceur.exemple.test/**', (r) => r.fulfill({ contentType: 'image/gif', body: '' }));
    await page.route('**/__piege/absent', (r) => r.fulfill({ status: 404, body: '' }));
    await page.route('**/sw-piege.js', (r) => r.fulfill({ contentType: 'text/javascript', body: '' }));
    const p = (await crawler(page, '/__piege/traceur/')).join('\n');
    for (const attendu of [
      'cookie posé : ',
      'document.cookie non vide',
      'localStorage.suivi',
      'sessionStorage.suivi',
      'service worker',
      'hôte hors registre : traceur.exemple.test',
      'console.error : erreur plantée',
      'pageerror : exception plantée',
      'HTTP 404',
    ]) {
      expect(p, attendu).toContain(attendu);
    }
  });
});

for (const url of pagesDuBuild()) {
  test(`${url} : crawl propre`, async ({ page }) => {
    await installerSondes(page);
    expect(await crawler(page, url)).toEqual([]);
  });
}

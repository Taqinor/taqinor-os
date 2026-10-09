import { expect, test, type Page } from '@playwright/test';
import { ciblesTropPetites, debordement, pagesDuBuild, violationsAxe } from './gardes';

/**
 * YBW60 — l'en-tête ne passe JAMAIS à la ligne, de 320 à 1440 px : chaque
 * élément visible de la barre (logo, navigation, actions, menu mobile) tient
 * sur une seule ligne et chaque entrée de navigation aussi. Menu mobile ouvert
 * (sans script) : dans la page, accessible.
 */
const LARGEURS_ENTETE = [320, 375, 768, 1024, 1280, 1440] as const;

/** Problèmes de mise en ligne de l'en-tête (vide = une seule ligne). */
async function entetePasseALaLigne(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const out: string[] = [];
    const barre = document.querySelector<HTMLElement>('.entete-int');
    if (!barre) return ['en-tête absent'];
    const visibles = [...barre.children].filter((e) => getComputedStyle(e).display !== 'none' && (e as HTMLElement).offsetWidth > 0) as HTMLElement[];
    const milieux = visibles.map((e) => {
      const r = e.getBoundingClientRect();
      return r.top + r.height / 2;
    });
    if (Math.max(...milieux) - Math.min(...milieux) > 4) out.push(`éléments de l'en-tête sur plusieurs lignes (${milieux.map(Math.round).join(', ')})`);
    for (const el of barre.querySelectorAll<HTMLElement>('.nav-bureau a, .entete-actions a, .nav-mobile summary')) {
      if (getComputedStyle(el).display === 'none' || el.offsetWidth === 0) continue;
      const hauteurLigne = parseFloat(getComputedStyle(el).lineHeight) || 24;
      if (el.getClientRects().length > 1 || el.scrollHeight > Math.max(el.clientHeight, hauteurLigne * 1.6)) out.push(`« ${el.textContent?.trim()} » passe à la ligne`);
    }
    const r = barre.getBoundingClientRect();
    if (barre.scrollWidth > barre.clientWidth + 1) out.push(`en-tête plus large que sa barre (${barre.scrollWidth} > ${barre.clientWidth}, ${Math.round(r.width)})`);
    return out;
  });
}

test('preuve : la garde rougit sur un en-tête qui passe à la ligne', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.route('**/__piege/entete/', (r) =>
    r.fulfill({
      contentType: 'text/html',
      body: '<!doctype html><html lang="fr"><body><header><div class="entete-int" style="display:flex;flex-wrap:wrap;width:300px"><a style="display:block;width:250px">Logo</a><a style="display:block;width:250px">Nav</a></div></header></body></html>',
    }),
  );
  await page.goto('/__piege/entete/');
  expect((await entetePasseALaLigne(page)).length).toBeGreaterThan(0);
});

const AVEC_ENTETE = pagesDuBuild().filter((u) => !['/bonjour/', '/en/bonjour/'].includes(u));

for (const url of AVEC_ENTETE) {
  test(`${url} : en-tête sur une seule ligne de 320 à 1440 px`, async ({ page }) => {
    for (const largeur of LARGEURS_ENTETE) {
      await page.setViewportSize({ width: largeur, height: 900 });
      await page.goto(url);
      expect(await entetePasseALaLigne(page), `${largeur} px`).toEqual([]);
    }
  });

  test(`${url} @ 320px : menu mobile ouvert dans la page, accessible`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(url);
    await page.locator('.nav-mobile summary').click();
    await expect(page.locator('.nav-mobile nav')).toBeVisible();
    expect(await debordement(page)).toEqual([]);
    expect(await ciblesTropPetites(page)).toEqual([]);
    expect(await violationsAxe(page)).toEqual([]);
  });

  test(`${url} (sombre) : aucun débordement, 0 violation axe, fond sombre`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.setViewportSize({ width: 375, height: 900 });
    await page.goto(url);
    expect(await debordement(page)).toEqual([]);
    expect(await violationsAxe(page)).toEqual([]);
    const fond = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const [r, g, b] = (fond.match(/\d+/g) ?? []).map(Number);
    expect(r + g + b).toBeLessThan(120);
  });
}

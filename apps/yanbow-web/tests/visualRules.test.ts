/**
 * YBW44 — gardes visuelles sur le HTML RENDU (direction figée « A maison +
 * bandes produit B », STYLE.md) :
 *  - seules les images de `src/brand` (logo, SVG en ligne) et de
 *    `src/assets/product` (captures, servies hachées sous /_astro/) ;
 *  - chaque capture porte sa légende « Données fictives » dans la langue de la page ;
 *  - le slogan jamais dans l'en-tête, jamais sous 420 px ;
 *  - aucune animation sur l'élément LCP (le h1, la capture prioritaire) ;
 *  - les routes du tour design `/_design/*` ont disparu du build.
 * Chaque garde rougit sur une fixture qui la viole.
 */
import { existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { LEGENDE } from '../src/data/productScreens';
import { DIST_CLIENT, pagesRendues } from './builtHtml';

const PRODUIT = fileURLToPath(new URL('../src/assets/product/', import.meta.url));
/** Noms de base (sans extension) des fichiers image du kit de captures. */
const BASES_PRODUIT = existsSync(PRODUIT)
  ? readdirSync(PRODUIT)
      .filter((n) => /\.(avif|webp|png|jpe?g)$/.test(n))
      .map((n) => n.replace(/\.[^.]+$/, ''))
  : [];

/** Images hors kit : toute `<img>`/`<source>` hors `figure[data-capture]` ou d'une autre origine que les captures. */
export function imagesHorsKit(doc: Document, bases: readonly string[] = BASES_PRODUIT): string[] {
  const out: string[] = [];
  for (const el of doc.querySelectorAll('img, picture source, image, input[type="image"]')) {
    const urls = [el.getAttribute('src'), el.getAttribute('href'), ...(el.getAttribute('srcset') ?? '').split(',').map((s) => s.trim().split(/\s+/)[0])]
      .filter((u): u is string => !!u);
    if (!el.closest('figure[data-capture]')) out.push(`image hors capture produit : ${el.outerHTML.slice(0, 80)}`);
    for (const u of urls) {
      const nom = u.split('/').pop() ?? '';
      if (!u.startsWith('/_astro/') || !bases.some((b) => nom.startsWith(`${b}.`))) out.push(`image hors src/assets/product : ${u}`);
    }
  }
  for (const el of doc.querySelectorAll('[style]')) {
    if (/url\(/.test(el.getAttribute('style') ?? '')) out.push(`image de fond en ligne : ${el.outerHTML.slice(0, 80)}`);
  }
  return out;
}

/** Captures sans la légende de la langue de la page. */
export function legendesManquantes(doc: Document, langue: 'fr' | 'en'): string[] {
  return [...doc.querySelectorAll('figure[data-capture]')]
    .filter((f) => f.querySelector('figcaption')?.textContent?.trim() !== LEGENDE[langue])
    .map((f) => `capture « ${f.getAttribute('data-capture')} » sans légende « ${LEGENDE[langue]} »`);
}

/** Slogan dans l'en-tête ou rendu sous 420 px. */
export function sloganMalPlace(doc: Document): string[] {
  const out: string[] = [];
  for (const l of doc.querySelectorAll('[data-logo="slogan"]')) {
    if (l.closest('header')) out.push('slogan dans l’en-tête');
    const largeur = Number(l.querySelector('svg')?.getAttribute('width'));
    if (!(largeur >= 420)) out.push(`slogan à ${largeur} px (< 420)`);
  }
  return out;
}

/** Éléments animés qui sont, contiennent ou sont contenus dans l'élément LCP (h1, capture prioritaire). */
export function animationSurLcp(doc: Document): string[] {
  const lcp = [...doc.querySelectorAll('h1, img[loading="eager"], img[fetchpriority="high"]')];
  const out: string[] = [];
  for (const a of doc.querySelectorAll('.motif-anime, [data-anime]')) {
    for (const l of lcp) {
      if (a === l || a.contains(l) || l.contains(a)) out.push(`animation sur l’élément LCP <${l.tagName.toLowerCase()}>`);
    }
  }
  for (const l of lcp) {
    if (/animation/.test(l.getAttribute('style') ?? '')) out.push(`animation en ligne sur <${l.tagName.toLowerCase()}>`);
  }
  return out;
}

const doc = (html: string) => new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window.document;

describe('YBW44 — chaque garde rougit sur une fixture', () => {
  it('image d’illustration hors kit', () => {
    expect(imagesHorsKit(doc('<main><img src="/photos/equipe.jpg" alt=""></main>'), ['crm-pipeline-1440'])).toHaveLength(2);
    expect(imagesHorsKit(doc('<figure data-capture="x"><img src="/_astro/autre.abc.webp" alt=""></figure>'), ['crm-pipeline-1440'])).toHaveLength(1);
    expect(imagesHorsKit(doc('<div style="background-image:url(/x.jpg)"></div>'))).toHaveLength(1);
    expect(
      imagesHorsKit(doc('<figure data-capture="x"><picture><source srcset="/_astro/crm-pipeline-1440.abc.avif"><img src="/_astro/crm-pipeline-1440.def.webp" alt=""></picture></figure>'), [
        'crm-pipeline-1440',
      ]),
    ).toEqual([]);
  });

  it('capture sans légende, ou légende dans l’autre langue', () => {
    expect(legendesManquantes(doc('<figure data-capture="x"><div></div></figure>'), 'fr')).toHaveLength(1);
    expect(legendesManquantes(doc(`<figure data-capture="x"><figcaption>${LEGENDE.en}</figcaption></figure>`), 'fr')).toHaveLength(1);
    expect(legendesManquantes(doc(`<figure data-capture="x"><figcaption>${LEGENDE.fr}</figcaption></figure>`), 'fr')).toEqual([]);
  });

  it('slogan dans l’en-tête ou sous 420 px', () => {
    expect(sloganMalPlace(doc('<header><span data-logo="slogan"><svg width="420"></svg></span></header>'))).toEqual(['slogan dans l’en-tête']);
    expect(sloganMalPlace(doc('<footer><span data-logo="slogan"><svg width="300"></svg></span></footer>'))).toHaveLength(1);
    expect(sloganMalPlace(doc('<footer><span data-logo="slogan"><svg width="420"></svg></span></footer>'))).toEqual([]);
  });

  it('animation posée sur le h1 ou la capture prioritaire', () => {
    expect(animationSurLcp(doc('<h1><svg class="motif-anime"></svg>Titre</h1>'))).toHaveLength(1);
    expect(animationSurLcp(doc('<div class="motif-anime"><img loading="eager" src="x"></div>'))).toHaveLength(1);
    expect(animationSurLcp(doc('<h1 style="animation: x 1s">T</h1>'))).toHaveLength(1);
    expect(animationSurLcp(doc('<h1>T</h1><div><svg class="motif-anime"></svg></div>'))).toEqual([]);
  });
});

describe('YBW44 — site construit', () => {
  it('les routes privées du tour design ont disparu du build', () => {
    expect(existsSync(DIST_CLIENT + '_design')).toBe(false);
    for (const p of pagesRendues()) expect(p.html, p.url).not.toContain('/_design');
  });

  for (const p of pagesRendues()) {
    describe(p.url, () => {
      it('images : logo en ligne et captures du kit seulement', () => expect(imagesHorsKit(p.document)).toEqual([]));
      it('chaque capture porte sa légende dans la langue de la page', () => expect(legendesManquantes(p.document, p.langueUrl)).toEqual([]));
      it('slogan jamais dans l’en-tête ni sous 420 px', () => expect(sloganMalPlace(p.document)).toEqual([]));
      it('aucune animation sur l’élément LCP', () => expect(animationSurLcp(p.document)).toEqual([]));
    });
  }
});

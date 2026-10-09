/**
 * YBW39 — polices OFL auto-hébergées + garde de typographie française.
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { cssPolices, FAMILLES, fichierLicence, fichierPolice } from '../scripts/build-fonts.mjs';
import { metriques } from '../scripts/font-metrics.mjs';
import { ecartsTypoFr, INTERDITS, NBSP, POLICES_PRECHARGEES, typoFr } from '../src/lib/typo';
import { DIST_CLIENT, pagesRendues } from './builtHtml';

const POLICES = fileURLToPath(new URL('../public/fonts/', import.meta.url));
const CSS = readFileSync(fileURLToPath(new URL('../src/styles/fonts.css', import.meta.url)), 'utf-8');
const CDN = /fonts\.googleapis|fonts\.gstatic|fontsource|use\.typekit|fonts\.bunny|cdn\.jsdelivr|unpkg\.com/i;

/** Texte public d'une page : texte visible + title/alt/aria-label/content des méta. */
function textePublic(doc: Document): string {
  const clone = doc.documentElement.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('script, style').forEach((n) => n.remove());
  const attributs = [...doc.querySelectorAll('[title], [alt], [aria-label], meta[content]')].flatMap((e) =>
    ['title', 'alt', 'aria-label', 'content'].map((a) => e.getAttribute(a) ?? ''),
  );
  return [clone.textContent ?? '', ...attributs].join('\n');
}

describe('YBW39 — familles OFL auto-hébergées', () => {
  for (const f of FAMILLES) {
    it(`${f.nom} : woff2 latin variable + texte OFL livrés`, () => {
      const police = readFileSync(POLICES + fichierPolice(f.id));
      expect(police.toString('ascii', 0, 4)).toBe('wOF2');
      expect(readFileSync(POLICES + fichierLicence(f.id), 'utf-8')).toMatch(/SIL OPEN FONT LICENSE Version 1\.1/);
      // La police couvre l'échantillon latin (lecture des tables : cmap + hmtx).
      expect(metriques(police).avanceMoyenne).toBeGreaterThan(0);
    });
  }

  it('YBW44 : seules les familles retenues (Outfit + Instrument Sans) sont livrées', () => {
    expect(FAMILLES.map((f) => f.nom)).toEqual(['Outfit', 'Instrument Sans']);
    expect(CSS).not.toMatch(/Urbanist|Geist|Fraunces|Jakarta/);
  });

  it('aucun fichier de police sans licence à côté', () => {
    const woff2 = readdirSync(POLICES).filter((n) => n.endsWith('.woff2'));
    expect(woff2.sort()).toEqual(FAMILLES.map((f) => fichierPolice(f.id)).sort());
  });

  it('fonts.css = sortie du générateur (métriques recalculées depuis les polices)', () => {
    expect(CSS).toBe(cssPolices());
  });

  it('fonts.css : sources locales seulement, swap, unicode-range, repli métrique par famille', () => {
    const urls = [...CSS.matchAll(/url\(([^)]+)\)/g)].map((m) => m[1].replace(/['"]/g, ''));
    expect(urls.length).toBe(FAMILLES.length);
    expect(urls.every((u) => u.startsWith('/fonts/'))).toBe(true);
    expect(CSS).not.toMatch(CDN);
    expect(CSS.match(/font-display: swap/g)).toHaveLength(FAMILLES.length);
    expect(CSS.match(/unicode-range:/g)).toHaveLength(FAMILLES.length);
    for (const f of FAMILLES) expect(CSS).toMatch(new RegExp(`font-family: '${f.nom} repli';[^}]*size-adjust: [\\d.]+%;[^}]*ascent-override`));
  });

  it('2 fichiers critiques préchargés, existants', () => {
    expect(POLICES_PRECHARGEES).toHaveLength(2);
    for (const p of POLICES_PRECHARGEES) expect(existsSync(POLICES + p.replace('/fonts/', ''))).toBe(true);
  });
});

describe('YBW39 — HTML et CSS RENDUS', () => {
  it('CSS construit : aucune police chargée depuis un CDN', () => {
    const dossier = DIST_CLIENT + '_astro/';
    const feuilles = existsSync(dossier) ? readdirSync(dossier).filter((n) => n.endsWith('.css')) : [];
    expect(feuilles.length).toBeGreaterThan(0);
    for (const f of feuilles) expect(readFileSync(dossier + f, 'utf-8')).not.toMatch(CDN);
  });

  for (const p of pagesRendues()) {
    it(`${p.url} : préchargement des 2 polices critiques, aucun CDN`, () => {
      const pre = [...p.document.querySelectorAll('link[rel="preload"][as="font"]')];
      expect(pre.map((l) => l.getAttribute('href'))).toEqual([...POLICES_PRECHARGEES]);
      for (const l of pre) {
        expect(l.getAttribute('type')).toBe('font/woff2');
        expect(l.hasAttribute('crossorigin')).toBe(true);
      }
      expect(p.html).not.toMatch(CDN);
    });

    it(`${p.url} : jamais U+202F, U+2009 ni U+2192`, () => {
      for (const c of Object.keys(INTERDITS)) expect(p.html.includes(c), INTERDITS[c]).toBe(false);
    });

    if (p.langueUrl === 'fr') {
      it(`${p.url} : typographie française (U+00A0 avant ; : ? ! et dans « »)`, () => {
        expect(ecartsTypoFr(textePublic(p.document))).toEqual([]);
      });
    }
  }
});

describe('YBW39 — typoFr / ecartsTypoFr', () => {
  it('insère U+00A0 avant ; : ? ! et dans les guillemets', () => {
    expect(typoFr('Pourquoi ? Voici : un « test » !')).toBe(`Pourquoi${NBSP}? Voici${NBSP}: un «${NBSP}test${NBSP}»${NBSP}!`);
    expect(typoFr('Quoi?!')).toBe(`Quoi${NBSP}?!`);
    expect(typoFr('10:30 et https://exemple.test')).toBe('10:30 et https://exemple.test');
    expect(typoFr('fine !')).toBe(`fine${NBSP}!`);
  });

  it('cas négatifs : chaque écart planté est détecté', () => {
    expect(ecartsTypoFr('Bonjour !')).toHaveLength(1);
    expect(ecartsTypoFr('Bonjour!')).toHaveLength(1);
    expect(ecartsTypoFr('« test »').length).toBe(2);
    expect(ecartsTypoFr('a ;')).toContain(INTERDITS[' ']);
    expect(ecartsTypoFr('Suite →')).toContain(INTERDITS['→']);
    expect(ecartsTypoFr(typoFr('Pourquoi ? Voici : un « test » !'))).toEqual([]);
  });
});

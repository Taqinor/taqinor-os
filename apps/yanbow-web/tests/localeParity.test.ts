/**
 * YBW70 + YBW71 — parité des langues et détection de fuite du français, sur le
 * HTML RENDU (`dist/client/`, après `npm run build`).
 *
 *  - mêmes nombres de h1/h2/h3/sections/affirmations par page FR et EN ;
 *  - aucun mot français fréquent, aucune lettre accentuée française, aucun
 *    « undefined » ni emplacement `{nom}` non remplacé dans une page EN ;
 *  - paires hreflang complètes et réciproques ;
 *  - le sélecteur de langue mène à la page équivalente.
 *
 * Preuve que le test mord : `comparerParite` / `fuitesFrancais` sont éprouvées
 * sur une page EN tronquée / contaminée exprès (fixtures JSDOM ci-dessous).
 */
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { PAGES, type PageId } from '../src/i18n/pages';
import { LOCALES_ACTIVES } from '../src/i18n/config';
import { pagesRendues, type PageRendue } from './builtHtml';

/** Mots français fréquents interdits dans une page EN (aucun n'est un mot anglais courant). */
export const MOTS_FRANCAIS = [
  'le', 'la', 'les', 'des', 'du', 'de', 'une', 'un', 'et', 'ou', 'dans', 'sur', 'avec', 'vous', 'votre', 'vos',
  'nos', 'notre', 'est', 'sont', 'qui', 'que', 'cette', 'aux', 'mais', 'pas', 'nous', 'pour', 'prendre', 'rendez-vous',
] as const;
// « pour » : verbe anglais possible, mais jamais présent dans notre texte EN (garde volontairement stricte).

const ACCENTS_FR = /[àâäçéèêëîïôöùûüÿœæ]/i;
const MARQUEURS_CASSES = /\bundefined\b|\bnull\b|\bNaN\b|\[object |\{(?:n|nom|partie|numero|forme)\}/;

/** Texte VISIBLE d'une page : sans script/style/svg, sans les éléments balisés `lang="fr"` (nom de langue du sélecteur). */
export function texteVisible(doc: Document): string {
  const copie = new JSDOM(doc.documentElement.outerHTML).window.document;
  copie.querySelectorAll('script,style,svg,noscript,[lang="fr"]').forEach((e) => e.remove());
  const meta = ['meta[name="description"]', 'meta[property="og:title"]', 'meta[property="og:description"]', 'meta[name="twitter:title"]']
    .map((s) => copie.querySelector(s)?.getAttribute('content') ?? '')
    .join(' ');
  return `${copie.title} ${meta} ${copie.body.textContent ?? ''}`.replace(/\s+/g, ' ');
}

export function fuitesFrancais(doc: Document): string[] {
  const texte = texteVisible(doc);
  const mots = texte.toLowerCase().match(/[a-zàâäçéèêëîïôöùûüÿœæ'’-]+/g) ?? [];
  const trouves = new Set<string>();
  for (const m of mots) if ((MOTS_FRANCAIS as readonly string[]).includes(m)) trouves.add(m);
  const accents = texte.match(ACCENTS_FR);
  if (accents) trouves.add(`lettre accentuée « ${accents[0]} »`);
  const casse = doc.documentElement.outerHTML.replace(/<script[\s\S]*?<\/script>/g, '').match(MARQUEURS_CASSES);
  if (casse) trouves.add(`marqueur cassé « ${casse[0]} »`);
  return [...trouves];
}

const MESURES = {
  h1: 'h1',
  h2: 'main h2',
  h3: 'main h3',
  sections: 'main section',
  affirmations: '[data-affirmation]',
} as const;

export function compter(doc: Document): Record<keyof typeof MESURES, number> {
  return Object.fromEntries(Object.entries(MESURES).map(([k, s]) => [k, doc.querySelectorAll(s).length])) as Record<
    keyof typeof MESURES,
    number
  >;
}

/** Écarts de structure entre la page FR et la page EN ; liste vide si elles ont la même ossature. */
export function comparerParite(fr: Document, en: Document): string[] {
  const a = compter(fr);
  const b = compter(en);
  return (Object.keys(MESURES) as (keyof typeof MESURES)[])
    .filter((k) => a[k] !== b[k])
    .map((k) => `${k} : FR ${a[k]} ≠ EN ${b[k]}`);
}

const hreflangs = (doc: Document) =>
  [...doc.querySelectorAll('link[rel="alternate"][hreflang]')].map((l) => `${l.getAttribute('hreflang')}=${l.getAttribute('href')}`);

// ── Fixtures : preuve que les gardes mordent ────────────────────────────────
const page = (corps: string, lang = 'en') =>
  new JSDOM(`<html lang="${lang}"><head><title>T</title></head><body><main><h1>A</h1>${corps}</main></body></html>`).window.document;
const CORPS = '<section><h2>B</h2><p data-affirmation="X">x</p></section><section><h2>C</h2><h3>D</h3></section>';

describe('YBW71 — les gardes mordent (fixtures)', () => {
  it('même ossature → aucun écart', () => {
    expect(comparerParite(page(CORPS, 'fr'), page(CORPS))).toEqual([]);
  });
  it('page EN tronquée exprès → écart signalé', () => {
    const tronquee = page('<section><h2>B</h2><p data-affirmation="X">x</p></section>');
    const ecarts = comparerParite(page(CORPS, 'fr'), tronquee);
    expect(ecarts.length).toBeGreaterThan(0);
    expect(ecarts.join(' ')).toMatch(/h2|h3|sections/);
  });
  it('français, accent ou « undefined » dans une page EN → fuite signalée', () => {
    expect(fuitesFrancais(page('<p>Prendre rendez-vous avec nous</p>')).length).toBeGreaterThan(0);
    expect(fuitesFrancais(page('<p>Société</p>')).length).toBeGreaterThan(0);
    expect(fuitesFrancais(page('<p>Book undefined</p>')).length).toBeGreaterThan(0);
    expect(fuitesFrancais(page('<p>Book {nom}</p>')).length).toBeGreaterThan(0);
  });
  it('anglais propre → aucune fuite ; le nom de langue « Français » du sélecteur est toléré', () => {
    expect(fuitesFrancais(page('<p>Book a meeting</p><a lang="fr" href="/">Français</a>'))).toEqual([]);
  });
});

// ── Pages réellement construites ────────────────────────────────────────────
const rendues = pagesRendues();
const parUrl = new Map<string, PageRendue>(rendues.map((p) => [p.url, p]));
const ids = Object.keys(PAGES) as PageId[];

describe('YBW71 — l’anglais est actif', () => {
  it('LOCALES_ACTIVES contient fr et en', () => {
    expect([...LOCALES_ACTIVES]).toEqual(['fr', 'en']);
  });
  it('chaque page du registre est construite dans les DEUX langues, ou dans aucune (pages juridiques fermées)', () => {
    for (const id of ids) {
      const fr = parUrl.has(PAGES[id].fr);
      const en = parUrl.has(PAGES[id].en);
      expect(fr, `${id} : FR ${PAGES[id].fr}`).toBe(en);
    }
    expect(ids.filter((id) => parUrl.has(PAGES[id].en)).length).toBeGreaterThanOrEqual(6);
  });
});

for (const id of ids) {
  const fr = parUrl.get(PAGES[id].fr);
  const en = parUrl.get(PAGES[id].en);
  if (!fr || !en) continue;

  describe(`YBW71 — ${id} (${PAGES[id].fr} ↔ ${PAGES[id].en})`, () => {
    it('même ossature (h1/h2/h3/sections/affirmations) en FR et en EN', () => {
      expect(comparerParite(fr.document, en.document)).toEqual([]);
    });

    it('<html lang> correct', () => {
      expect(fr.document.documentElement.lang).toBe('fr');
      expect(en.document.documentElement.lang).toBe('en');
    });

    it('aucun mot français ni « undefined » dans la page EN (YBW70)', () => {
      expect(fuitesFrancais(en.document)).toEqual([]);
    });

    it('paires hreflang complètes (fr, en, x-default) et identiques sur les deux pages', () => {
      const attendu = [`fr=${PAGES[id].fr}`, `en=${PAGES[id].en}`, `x-default=${PAGES[id].fr}`];
      expect(hreflangs(fr.document)).toEqual(attendu);
      expect(hreflangs(en.document)).toEqual(attendu);
    });

    it('le sélecteur de langue mène à la page équivalente', () => {
      const versEn = [...fr.document.querySelectorAll('.lien-langue, [hreflang="en"][lang="en"]')].map((a) => a.getAttribute('href'));
      const versFr = [...en.document.querySelectorAll('.lien-langue, [hreflang="fr"][lang="fr"]')].map((a) => a.getAttribute('href'));
      expect(versEn.length).toBeGreaterThan(0);
      expect(versFr.length).toBeGreaterThan(0);
      for (const h of versEn) expect(h).toBe(PAGES[id].en);
      for (const h of versFr) expect(h).toBe(PAGES[id].fr);
    });
  });
}

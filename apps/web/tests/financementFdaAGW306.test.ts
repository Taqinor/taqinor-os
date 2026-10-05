// AGW306 (D-AGR-6) — pages Financement (FR/EN/AR) : la carte FDA est la RÈGLE
// complète et sourcée de l'aide, avec les mêmes mots que le repli daté du devis
// agricole (quote_engine/agricole/mentions.py, AGR306). Jamais « jusqu'à 30 % »,
// « ≈ 30 % », « pouvant atteindre » ni « Cumulable » (le cumul n'est pas confirmé
// par la DPA). Garde sur le HTML CONSTRUIT (astro build) des 3 pages.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { builtPage, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string]> = [
  ['FR', '/financement'],
  ['EN', '/en/financement'],
  ['AR', '/ar/financement'],
];

const INTERDITS: Record<string, RegExp[]> = {
  FR: [/≈\s?30/, /jusqu['’]à 30/i, /pouvant atteindre/i, /cumulable/i],
  EN: [/≈\s?30/, /up to 30/i, /can reach/i, /cumulative with/i, /cumulable/i],
  AR: [/≈/, /حتى\s?30/, /قابلة للتراكم/, /يصل إلى/],
};

const mentions = readFileSync(
  fileURLToPath(new URL('../../../backend/django_core/apps/ventes/quote_engine/agricole/mentions.py', import.meta.url)),
  'utf-8',
);
const repli = (cle: string): number => {
  const m = mentions.match(new RegExp(`"${cle}":\\s*(\\d+)`));
  if (!m) throw new Error(`REPLI_FDA.${cle} introuvable dans mentions.py`);
  return Number(m[1]);
};

describe('AGW306 — carte FDA : la règle, pas une promesse', () => {
  for (const [lang, route] of PAGES) {
    const txt = visibleText(builtPage(route));

    it(`${lang} — aucune formulation « ≈ 30 % » / « jusqu'à 30 % » / « Cumulable »`, () => {
      for (const re of INTERDITS[lang]) expect(txt).not.toMatch(re);
    });

    it(`${lang} — cite « Guide FDA 2024 », sa date de lecture et l'accord AVANT travaux`, () => {
      expect(txt).toContain('Guide FDA 2024');
      expect(txt).toMatch(lang === 'FR' ? /relevé le 2 octobre 2026/ : lang === 'EN' ? /read on 2 October 2026/ : /2 أكتوبر 2026/);
      expect(txt).toMatch(lang === 'FR' ? /avant travaux/i : lang === 'EN' ? /before the works/i : /قبل الأشغال/);
    });

    it(`${lang} — conditions, versement après réalisation, un projet par exploitation, DPA/ORMVA non garantie`, () => {
      if (lang !== 'AR') {
        expect(txt).toMatch(/DPA/);
        expect(txt).toMatch(/ORMVA/);
      }
      if (lang === 'FR') {
        expect(txt).toContain('pompe au butane');
        expect(txt).toContain('irrigation localisée');
        expect(txt).toContain('compteur d’eau');
        expect(txt).toContain('versée après réalisation');
        expect(txt).toContain('un seul projet par exploitation');
        expect(txt).toContain('non garantie');
        expect(txt).toContain('n’est pas organisme subventionneur');
      } else if (lang === 'EN') {
        expect(txt).toContain('butane pump');
        expect(txt).toContain('localised irrigation');
        expect(txt).toContain('paid after completion');
        expect(txt).toContain('one project per farm');
        expect(txt).toContain('not guaranteed');
        expect(txt).toContain('is not a subsidising body');
      } else {
        expect(txt).toContain('مضخة تعمل بالبوطان');
        expect(txt).toContain('بعد الإنجاز');
        expect(txt).toContain('مشروع واحد لكل استغلالية');
        expect(txt).toContain('غير مضمون');
        expect(txt).toContain('المديرية الإقليمية للفلاحة');
      }
    });

    it(`${lang} — les plafonds sont ceux du repli daté du devis (mentions.py), sans montant client`, () => {
      const norm = txt.replace(/ | /g, ' ');
      const fr = (n: number) => n.toLocaleString('fr-FR').replace(/ | /g, ' ');
      const en = (n: number) => n.toLocaleString('en-US');
      const projet = repli('plafond_mad_par_projet');
      expect(norm).toContain(lang === 'EN' ? en(projet) : fr(projet));
      expect(norm).toContain(String(repli('taux_pct')));
      const ha = repli('plafond_mad_par_ha');
      expect(norm).toContain(lang === 'EN' ? en(ha) : fr(ha));
    });

    it(`${lang} — la carte Saquii reste inchangée`, () => {
      expect(txt).toContain('Saquii');
    });
  }
});

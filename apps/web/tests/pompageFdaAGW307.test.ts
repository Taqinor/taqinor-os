// AGW307 (D-AGR-6) — pages Pompage solaire (FR/EN/AR) : la carte « Piste de financement — à
// vérifier » (WG11) publie la RÈGLE sourcée de l'aide FDA, sans montant, avec les mêmes mots
// que le devis agricole (quote_engine/agricole/mentions.py) et que la page Financement
// (AGW306). Le paragraphe Saquii reste inchangé (non vérifié). Garde sur le HTML CONSTRUIT.
import { describe, expect, it } from 'vitest';
import { builtPage, mainOf, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string]> = [
  ['FR', '/pompage-solaire'],
  ['EN', '/en/pompage-solaire'],
  ['AR', '/ar/pompage-solaire'],
];

/** La carte « aide de l'État » : de `data-fda-regle` à `data-saquii` (incluse). */
function carte(html: string): string {
  const main = mainOf(html);
  const a = main.indexOf('data-fda-regle');
  const b = main.indexOf('data-saquii');
  expect(a, 'data-fda-regle').toBeGreaterThan(-1);
  expect(b, 'data-saquii').toBeGreaterThan(a);
  const fin = main.indexOf('</p>', b);
  return visibleText(main.slice(a, fin));
}

describe('AGW307 — la carte FDA de /pompage-solaire = la règle, pas une promesse', () => {
  for (const [lang, route] of PAGES) {
    const html = builtPage(route);
    const txt = carte(html);
    const page = visibleText(mainOf(html));

    it(`${lang} — la règle (conditions, plafonds, accord avant travaux, versement après réalisation) et sa source sont présentes`, () => {
      if (lang === 'FR') {
        for (const m of ['pompe au butane', 'irrigation localisée', 'compteur d’eau', '3 000 DH par hectare', '3 000 DH par kWc', '30 000 DH par projet',
          'avant travaux', 'versée après réalisation', 'un seul projet par exploitation', 'DPA/ORMVA', 'non garantie',
          'Guide FDA 2024, p. 20-23']) expect(txt, m).toContain(m);
      } else if (lang === 'EN') {
        for (const m of ['butane pump', 'localised irrigation', 'water meter', '3,000 MAD per hectare', '3,000 MAD per kWp', '30,000 MAD per project',
          'before the works', 'paid after completion', 'one project per farm', 'DPA/ORMVA', 'not guaranteed',
          'Guide FDA 2024, pp. 20-23']) expect(txt, m).toContain(m);
      } else {
        for (const m of ['مضخة تعمل بالبوطان', 'الري الموضعي', 'عداد الماء', 'قبل الأشغال', 'بعد الإنجاز', 'مشروع واحد لكل استغلالية',
          'غير مضمون', 'Guide FDA 2024']) expect(txt, m).toContain(m);
      }
    });

    it(`${lang} — aucun « jusqu'à », « pouvant atteindre » ni « ≈ 30 % » dans la carte, ni « jusqu'à 30 » sur la page`, () => {
      expect(txt).not.toMatch(/jusqu['’]à|pouvant atteindre|up to|can reach|حتى|يصل إلى|≈/i);
      expect(page).not.toMatch(/jusqu['’]à 30|up to 30|حتى\s?30|≈\s?30\s?%/i);
    });

    it(`${lang} — la date de lecture est donnée (2 octobre 2026)`, () => {
      expect(txt).toMatch(lang === 'FR' ? /relevé le 2 octobre 2026/ : lang === 'EN' ? /read on 2 October 2026/ : /2 أكتوبر 2026/);
    });

    it(`${lang} — le paragraphe Saquii reste présent et ne publie ni pourcentage ni montant`, () => {
      const main = mainOf(html);
      const a = main.indexOf('data-saquii');
      const saquii = visibleText(main.slice(a, main.indexOf('</p>', a)));
      expect(saquii).toContain('Saquii');
      expect(saquii).not.toMatch(/\d/);
    });

    it(`${lang} — jamais d'éligibilité promise : décision de l'administration, non garantie`, () => {
      expect(page).toMatch(lang === 'FR' ? /ne garantit aucune éligibilité/ : lang === 'EN' ? /guarantees no eligibility/ : /لا تضمن/);
    });
  }
});

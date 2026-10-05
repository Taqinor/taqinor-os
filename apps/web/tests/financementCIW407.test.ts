// CIW407 — pages Financement (FR/EN/AR) : l'entrée « Entreprises » et la section
// « leviers fiscaux » (W336) ne publient plus l'exonération à l'import (art.
// 123-22°), un amortissement non sourcé (« 5 % par an »), la note « skim
// juridique » ni un crédit-bail nommé (Maghrebail « Energy Lease » avec
// « subvention d'investissement intégrée ») — jusqu'aux avis ÉCRITS du fiscaliste
// et de l'expert-comptable (tâches manuelles), comme CIW402 pour /professionnel.
// « La plupart de nos clients règlent… » ne s'appuie sur rien : retiré.
// Garde sur le HTML CONSTRUIT (astro build) des 3 pages.
import { describe, expect, it } from 'vitest';
import { builtPage, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string]> = [
  ['FR', '/financement'],
  ['EN', '/en/financement'],
  ['AR', '/ar/financement'],
];

const INTERDITS = [
  '123-22', '5 % par an', '5 % a year', 'skim', 'Maghrebail', 'Energy Lease',
  "subvention d'investissement", 'subvention d’investissement',
  'la plupart de nos clients', 'La plupart de nos clients', 'Most of our clients',
  'investment subsidy', 'معظم زبنائنا', 'إعانة استثمار',
];

describe('CIW407 — Financement : ni exonération à l’import, ni amortissement non sourcé, ni crédit-bail nommé', () => {
  for (const [lang, route] of PAGES) {
    const txt = visibleText(builtPage(route));

    it(`${lang} — aucune des formulations retirées`, () => {
      for (const bad of INTERDITS) expect(txt, bad).not.toContain(bad);
      expect(txt).not.toMatch(/5\s?%\s?(par an|a year|في السنة)/);
    });

    it(`${lang} — l'entrée Entreprises dit l'offre ÉCRITE d'un prêteur, jointe au devis, sans banque ni taux`, () => {
      expect(txt).toContain(
        lang === 'FR'
          ? 'Offre de financement'
          : lang === 'EN'
            ? 'Financing offer'
            : 'عرض التمويل',
      );
      expect(txt).toMatch(
        lang === 'FR'
          ? /offre écrite d’un prêteur, jointe à votre devis/
          : lang === 'EN'
            ? /lender’s written offer, attached to your quote/
            : /العرض الكتابي لمُقرض، مرفق بعرض الثمن/,
      );
    });

    it(`${lang} — pas de « subvention » (ni « subsidy ») proposée à une entreprise (Q22)`, () => {
      // La seule mention de subvention doit rester dans le segment Agricole (FDA) et
      // l'avertissement résidentiel ; l'entrée Entreprises n'en porte aucune.
      const apresEntreprises = txt.slice(
        Math.max(
          txt.indexOf(lang === 'FR' ? 'Entreprises' : lang === 'EN' ? 'Businesses' : 'المقاولات'),
          0,
        ),
      );
      const bloc = apresEntreprises.slice(0, 400);
      expect(bloc).not.toMatch(/subvention|subsid|إعان/i);
    });
  }
});

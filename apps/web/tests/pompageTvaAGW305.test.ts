// AGW305 — l'exonération de TVA ne « couvre » plus « la pompe comme les panneaux »
// et n'est plus « vérifiée » avant l'avis du fiscaliste (FR/EN/AR). Garde de
// contenu sur le HTML CONSTRUIT (astro build) des 3 langues.
import { describe, expect, it } from 'vitest';
import { builtPage, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string]> = [
  ['FR', '/pompage-solaire'],
  ['EN', '/en/pompage-solaire'],
  ['AR', '/ar/pompage-solaire'],
];

const INTERDITS = [
  'la pompe comme les panneaux',
  'Avantage fiscal vérifié',
  'the pump as much as the panels',
  'Verified tax advantage',
  'المضخّة كما الألواح',
  'امتياز ضريبي مؤكَّد',
];

describe('AGW305 — exonération TVA pompage : périmètre exact', () => {
  for (const [lang, route] of PAGES) {
    it(`${lang} — aucune promesse d'exonération étendue aux panneaux, rien de « vérifié »`, () => {
      const txt = visibleText(builtPage(route));
      for (const bad of INTERDITS) expect(txt).not.toContain(bad);
    });
  }

  it('la phrase de périmètre (art. 91 du CGI + devis ligne par ligne) est servie dans les 3 langues', () => {
    expect(visibleText(builtPage('/pompage-solaire'))).toContain(
      'La vente de pompes à eau solaires à usage agricole est exonérée de TVA (art. 91 du CGI)',
    );
    expect(visibleText(builtPage('/en/pompage-solaire'))).toContain(
      'The sale of solar water pumps for agricultural use is VAT-exempt (art. 91 of the CGI)',
    );
    expect(visibleText(builtPage('/ar/pompage-solaire'))).toContain('المادة 91');
  });
});

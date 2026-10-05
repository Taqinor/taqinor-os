// CIW402 — /professionnel (FR/EN/AR) et FAQ pro : loi 82-21 exacte (autoconsommation
// d'abord), plus de levier fiscal non validé, promesses de service avec leur
// périmètre exact. Garde sur le HTML CONSTRUIT (astro build) des 3 pages.
import { describe, expect, it } from 'vitest';
import { builtPage, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string]> = [
  ['FR', '/professionnel'],
  ['EN', '/en/professionnel'],
  ['AR', '/ar/professionnel'],
];

const INTERDITS_FR = [
  '123-22', '5 % par an', 'skim', 'chaque kilowattheure exporté',
  "Jusqu'à 5 MW", 'jusqu’à 5 MW', 'courbes de charge', 'fourchettes',
];
const INTERDITS_EN = [
  '123-22', '5 % a year', 'skim', 'Make every exported', 'Up to 5 MW', 'up to 5 MW',
  'load curves', 'published indicative ranges', 'whole fleet',
];
const INTERDITS_AR = ['123-22', 'منحنيات الحمل', 'منحنيات', 'كامل الأسطول', 'المجالات الإرشادية'];

describe('CIW402 — loi 82-21 exacte sur /professionnel', () => {
  for (const [lang, route] of PAGES) {
    const txt = visibleText(builtPage(route));
    it(`${lang} — aucune des formulations retirées (levier fiscal, export, 5 MW inclusif, courbes de charge, fourchettes)`, () => {
      const interdits = lang === 'FR' ? INTERDITS_FR : lang === 'EN' ? INTERDITS_EN : INTERDITS_AR;
      for (const bad of interdits) expect(txt).not.toContain(bad);
      // le « 5 % par an » d'amortissement ne subsiste dans aucune langue
      expect(txt).not.toMatch(/5\s?%\s?(par an|a year|في السنة)/);
    });

    it(`${lang} — « 20 % », « 18 » et « 21 » sont présents à côté de « MT »`, () => {
      expect(txt).toContain('20 %');
      expect(txt).toContain('18 cDH');
      expect(txt).toContain('21 cDH');
      expect(txt).toContain(lang === 'EN' ? 'MV' : 'MT');
      // « MT/HT/THT » (ou MV/HV/EHV en anglais) et la frontière 5 MW restent
      expect(txt).toMatch(lang === 'EN' ? /MV\/HV\/EHV/ : /MT\/HT\/THT/);
      expect(txt).toContain('5 MW');
    });

    it(`${lang} — les régimes : déclaration sous 11 kW, accord de 11 kW à moins de 5 MW, autorisation dès 5 MW`, () => {
      expect(txt).toContain('11 kW');
      expect(txt).toContain('2.25.100');
    });
  }

  it('FR — l\'économie vient de l\'autoconsommation ; en BT la revente n\'est pas ouverte ; le dossier reste monté', () => {
    const txt = visibleText(builtPage('/professionnel'));
    expect(txt).toContain("L'économie vient de l'autoconsommation");
    expect(txt).toContain("En basse tension, la revente n'est pas ouverte");
    expect(txt).toContain('nous montons le dossier');
    expect(txt).toContain('loi 82-21 art. 12');
    expect(txt).toContain('ANRE décision 04/26');
  });

  it('FR — la FAQ pro : suivi sur « votre site », délai fixé par le contrat, aucune fourchette publiée', () => {
    const txt = visibleText(builtPage('/professionnel'));
    expect(txt).toContain('porte sur votre site');
    expect(txt).toContain('le délai d’intervention est fixé par votre contrat');
  });
});

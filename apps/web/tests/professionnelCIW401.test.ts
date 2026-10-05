// CIW401 — /professionnel (FR/EN/AR) : plus de « preuve » villa (page ET aperçu du
// menu), plus de « remboursé en 3 à 5 ans », plus de tableau de prix, plus de
// crédit-bail ni d'estimateur résidentiel publié. Garde sur le HTML CONSTRUIT
// (astro build ; en CI le build précède vitest).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { builtPage, mainOf, visibleText } from './builtHtmlHelper';

const PAGES: Array<[string, string, string]> = [
  ['FR', '/professionnel', '../src/pages/professionnel.astro'],
  ['EN', '/en/professionnel', '../src/pages/en/professionnel.astro'],
  ['AR', '/ar/professionnel', '../src/pages/ar/professionnel.astro'],
];

const INTERDITS = [
  'Preuve', 'Proof:', 'Exemple réel', 'Real example', 'مثال حقيقي',
  '17,04', '3,72 kWc',
  '3 à 5 ans', '3 to 5 years', '3-to-5', '3–5', '3 إلى 5',
  'MAD/kWc',
  'crédit-bail',
];

describe('CIW401 — page /professionnel : aucune preuve villa, aucun chiffre non sourcé', () => {
  for (const [lang, route] of PAGES) {
    const main = mainOf(builtPage(route));
    const txt = visibleText(main);

    it(`${lang} — aucune des chaînes interdites dans <main>`, () => {
      for (const bad of INTERDITS) expect(txt).not.toContain(bad);
      expect(txt.toLowerCase()).not.toContain('leasing');
    });

    it(`${lang} — aucun estimateur résidentiel (InstantEstimator) ni tableau des tranches`, () => {
      expect(main).not.toContain('data-instant-estimator');
      expect(txt).not.toMatch(/kWc\s*·\s*\d/); // plus de ligne « N kWc · retour » de tranche
    });

    it(`${lang} — les deux entrées vers le tunnel ?mode=industriel et ?mode=commercial sont présentes`, () => {
      const html = builtPage(route);
      const base = lang === 'FR' ? '/devis/mon-toit' : `/${lang.toLowerCase()}/devis/mon-toit`;
      expect(html).toContain(`href="${base}?mode=industriel"`);
      expect(html).toContain(`href="${base}?mode=commercial"`);
    });
  }

  it('FR — les deux entrées portent leur libellé sans chiffre', () => {
    const txt = visibleText(mainOf(builtPage('/professionnel')));
    expect(txt).toContain('Usine, atelier, entrepôt');
    expect(txt).toContain('Hôtel, commerce, clinique, école');
    expect(txt).toContain('Achat comptant ou offre de financement écrite');
  });

  it('aucune page du segment pro n\'importe billEstimate/billRange/InstantEstimator/realisations', () => {
    for (const [, , rel] of PAGES) {
      const src = readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
      const imports = src.split(/\r?\n/).filter((l) => /^\s*import\b/.test(l)).join('\n');
      expect(imports).not.toMatch(/billEstimate|billRange|InstantEstimator|realisations/);
    }
  });

  it('aucun aperçu de menu pour /professionnel tant qu\'aucune réalisation de segment « professionnel » n\'existe', () => {
    const realisations = readFileSync(fileURLToPath(new URL('../src/lib/realisations.ts', import.meta.url)), 'utf-8');
    expect(realisations).not.toMatch(/segment:\s*'professionnel'/);
    for (const route of ['/', '/professionnel', '/en', '/ar/professionnel', '/pompage-solaire']) {
      const html = builtPage(route);
      expect(html).not.toMatch(/<[^>]*data-preview-card="\/professionnel"/);
    }
    // l'aperçu résidentiel reste
    expect(builtPage('/')).toMatch(/<[^>]*data-preview-card="\/résidentiel"/);
  });

  it('Header.astro : plus d\'entrée \'/professionnel\' dans solutionPreview', () => {
    const header = readFileSync(fileURLToPath(new URL('../src/components/Header.astro', import.meta.url)), 'utf-8');
    const bloc = header.slice(header.indexOf('const solutionPreview'), header.indexOf('const previewStr'));
    expect(bloc).not.toContain("'/professionnel'");
    expect(bloc).toContain("'/résidentiel'");
  });
});

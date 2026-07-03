// Garde-fous de l'élévation « élégance retenue » promue en production
// (2026-06-13) : les pages publiques principales montent le moteur de
// mouvement, restent indexables, et la couche photo (Ken Burns + montée
// d'échelle) reste gated mouvement/JS. Les routes de prévisualisation /v2 et
// /v3 ont été supprimées.
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const pagesDir = fileURLToPath(new URL('../src/pages', import.meta.url));
const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Les pages élevées (les 2 pages légales restent volontairement sobres).
// Inclut le lot SEO public (W2–W8) : pages ville, FAQ, garanties, pourquoi,
// MRE — toutes indexées et montant le moteur d'élévation.
const ELEVATED = [
  'index',
  'contact',
  'loi-82-21',
  'professionnel',
  'regularization-article-33',
  'résidentiel',
  'équipement',
  'faq',
  'garanties',
  'pourquoi-taqinor',
  'marocains-du-monde',
  'à-propos',
  'installation-solaire-[city]',
  // Lot IA/contenu (W23–W30) : pages de solutions + hub + financement.
  'pompage-solaire',
  'batteries-stockage',
  'maintenance-monitoring',
  'financement',
  'nos-solutions',
];

describe('élévation — pages publiques', () => {
  for (const p of ELEVATED) {
    it(`/${p} monte le moteur d'élévation et reste indexable`, () => {
      const src = read(`../src/pages/${p}.astro`);
      expect(src, `${p}: V2Enhance`).toContain('V2Enhance');
      expect(src, `${p}: wrapper .v2`).toContain('class="v2"');
      // Page publique : surtout PAS de noindex (régression d'indexation).
      expect(src, `${p}: pas de noindex`).not.toContain('noindex');
    });
  }
});

describe('élévation — mouvement photo global et sûr', () => {
  it('V2Enhance importe la couche photo (active sur toute page élevée)', () => {
    const enhance = read('../src/components/V2Enhance.astro');
    expect(enhance).toContain('v3-photo-motion.css');
  });

  it('la couche photo ne bouge que sous JS ET hors prefers-reduced-motion', () => {
    const css = read('../src/styles/v3-photo-motion.css');
    expect(css).toContain('prefers-reduced-motion: no-preference');
    expect(css).toContain('.v2-js .v2-hero-media'); // Ken Burns
    expect(css).toContain('.v2-js .v2-rise > picture'); // montée d'échelle
    // transform/opacity uniquement → zéro CLS (aucune propriété de reflow).
    expect(css).not.toMatch(/\b(top|left|width|height|margin)\s*:/);
  });
});

describe('prévisualisations supprimées', () => {
  it('les dossiers /v2 et /v3 n\'existent plus', () => {
    expect(existsSync(`${pagesDir}/v2`)).toBe(false);
    expect(existsSync(`${pagesDir}/v3`)).toBe(false);
    const slugs = readdirSync(pagesDir).filter((f) => f.endsWith('.astro'));
    // 9 d'origine (7 élevées + 2 légales) + 5 du lot SEO public top-level
    // (installation-solaire-[city], faq, garanties, pourquoi-taqinor,
    // marocains-du-monde) + 1 (à-propos, W13) + 5 du lot IA/contenu W23–W30
    // (pompage-solaire, batteries-stockage, maintenance-monitoring, financement,
    // nos-solutions) + 1 (recharge-voiture-electrique-solaire, pilier EV W120)
    // + 1 (impact-taqinor, page transparence W279)
    // + 4 du lot drain 2026-07-03 (production-mesuree W354, ensoleillement-maroc W355,
    //   prix-panneaux-solaires-maroc W293, parrainage W338)
    // + 2 (methodologie-estimation W359, liens W350).
    // Les études de cas, guides et articles de blog vivent en sous-dossier
    // (realisations/, guides/, blog/) et ne comptent pas ici.
    expect(slugs.length).toBe(28);
  });

  it('le filtre sitemap ne référence plus /v2 ni /v3', () => {
    const config = read('../astro.config.mjs');
    const filterLine = config.split('\n').find((l) => l.includes('filter:')) ?? '';
    expect(filterLine).not.toContain('v2');
    expect(filterLine).not.toContain('v3');
  });
});

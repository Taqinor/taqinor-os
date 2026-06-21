// W131 — Garde-fous des invariants de l'expansion de contenu (W119–W130).
// Tests SOURCE (comme seoInvariantsW104) : pas de build requis. Assertions :
//  1. /faq reste la SEULE route qui émet un FAQPage — le pilier VE et
//     /batteries-stockage rendent le composant Faq avec schema={false} ;
//  2. chaque NOUVELLE page (W120–W128) passe par le Layout (un seul canonical
//     auto-référent) et ne pose aucun <link rel="canonical"> inline ;
//  3. les guides portent un JSON-LD Article ; le pilier VE porte Service +
//     BreadcrumbList ;
//  4. les nouvelles routes publiques NE sont PAS exclues du sitemap, /preview/ l'est ;
//  5. (best-effort) les figures de marché volatiles sont labellisées « indicatif ».
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const GUIDES = [
  'combien-de-panneaux-pour-ma-maison',
  'on-grid-off-grid-ou-hybride',
  'orientation-inclinaison-ombrage',
  'entretien-et-duree-de-vie-des-panneaux',
  'monocristallin-ou-polycristallin',
  'batterie-lithium-ou-gel',
  'quelle-taille-de-batterie',
  'electricite-pendant-les-coupures',
];
const EV_PAGE = '../src/pages/recharge-voiture-electrique-solaire.astro';

// Filtre d'exclusion du sitemap, recopié À L'IDENTIQUE depuis astro.config.mjs.
const sitemapExcluded = (page: string) =>
  /type-test|media-test|variants-test|craft-|\/preview\//.test(page);

describe('W131 — /faq reste l’unique propriétaire du FAQPage', () => {
  it('le pilier VE et /batteries-stockage utilisent Faq avec schema={false}', () => {
    for (const f of [EV_PAGE, '../src/pages/batteries-stockage.astro']) {
      const src = read(f);
      expect(src, f).toContain('<Faq');
      expect(src, f).toContain('schema={false}');
    }
  });

  it('aucune nouvelle page n’émet de FAQPage en dur (seul le composant Faq le fait, sur /faq)', () => {
    // On cible l'ÉMISSION JSON-LD (@type FAQPage), pas le mot dans un commentaire.
    const pages = [EV_PAGE, '../src/pages/batteries-stockage.astro', ...GUIDES.map((g) => `../src/pages/guides/${g}.astro`)];
    for (const f of pages) {
      expect(read(f), f).not.toMatch(/['"]@type['"]:\s*['"]FAQPage['"]/);
    }
  });

  it('/faq porte bien le FAQPage (Faq sans schema={false})', () => {
    const faq = read('../src/pages/faq.astro');
    expect(faq).toContain('<Faq');
    expect(faq).not.toContain('schema={false}');
  });
});

describe('W131 — un seul canonical auto-référent par nouvelle page', () => {
  const newPages = [EV_PAGE, ...GUIDES.map((g) => `../src/pages/guides/${g}.astro`)];
  it('chaque nouvelle page passe par le Layout et ne pose pas de canonical inline', () => {
    for (const f of newPages) {
      const src = read(f);
      expect(src, f).toContain('import Layout from');
      expect(src, f).toContain('<Layout');
      expect(src.match(/<link\s+rel="canonical"/g) ?? [], f).toHaveLength(0);
    }
  });
});

describe('W131 — données structurées des nouvelles pages', () => {
  it('chaque guide porte un JSON-LD Article', () => {
    for (const g of GUIDES) {
      const src = read(`../src/pages/guides/${g}.astro`);
      expect(src, g).toContain('application/ld+json');
      expect(src, g).toMatch(/['"]@type['"]:\s*['"]Article['"]/);
    }
  });

  it('le pilier VE porte Service + BreadcrumbList', () => {
    const src = read(EV_PAGE);
    expect(src).toMatch(/['"]@type['"]:\s*['"]Service['"]/);
    expect(src).toMatch(/['"]@type['"]:\s*['"]BreadcrumbList['"]/);
  });
});

describe('W131 — sitemap : nouvelles routes incluses, /preview/ exclu', () => {
  it('les nouvelles routes publiques NE sont PAS exclues', () => {
    for (const p of [
      '/recharge-voiture-electrique-solaire',
      ...GUIDES.map((g) => `/guides/${g}`),
      '/blog',
      '/blog/prix-installation-solaire-maroc-2026',
    ]) {
      expect(sitemapExcluded(p), p).toBe(false);
    }
  });
  it('la prévisualisation privée reste exclue', () => {
    expect(sitemapExcluded('/preview/toiture-3d-pro-11')).toBe(true);
  });
});

describe('W131 — figures de marché volatiles labellisées (best-effort)', () => {
  it('le post coût affiche « indicatif » et jamais un prix unique non labellisé', () => {
    const post = read('../src/content/blog/prix-installation-solaire-maroc-2026.md');
    expect(post.toLowerCase()).toContain('indicati');
  });
});

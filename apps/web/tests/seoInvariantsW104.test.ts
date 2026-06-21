// W104 — Garde-fous des invariants de l'audit SEO (W98–W104).
// Fichier de tests NOUVEAU : ne remplace pas tests/seo-pages.test.ts.
// Asserte trois invariants permanents :
//  1. la dernière route de prévisualisation privée (/preview/toiture-3d-pro-11)
//     est EXCLUE par le filtre du sitemap (jamais indexée, jamais dans le plan
//     du site) — on rejoue la regex de astro.config.mjs ;
//  2. l'accueil porte le JSON-LD LocalBusiness (émis centralement par le Layout,
//     dont l'accueil hérite) ;
//  3. chaque route publique porte exactement UN canonical auto-référent (le
//     Layout émet un seul <link rel="canonical"> et les pages publiques passent
//     par le Layout).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Le filtre d'exclusion du sitemap, recopié À L'IDENTIQUE depuis
// apps/web/astro.config.mjs (intégration @astrojs/sitemap, option `filter`).
// `page` est exclue du sitemap quand cette fonction renvoie `true`.
const sitemapExcluded = (page: string) =>
  /type-test|media-test|variants-test|craft-|\/preview\//.test(page);

describe('W104 — exclusion sitemap des prévisualisations privées', () => {
  it('la dernière prévisualisation privée /preview/toiture-3d-pro-11 est exclue du sitemap', () => {
    expect(sitemapExcluded('/preview/toiture-3d-pro-11')).toBe(true);
  });

  it('toute la zone /preview/ (et les variantes toiture-3d-pro-*) reste exclue', () => {
    for (const p of [
      '/preview/toiture-3d-pro-11',
      '/preview/toiture-3d-pro',
      '/preview/diagnostic',
      '/preview/toiture-3d',
    ]) {
      expect(sitemapExcluded(p), p).toBe(true);
    }
  });

  it('les routes publiques ne sont PAS exclues du sitemap', () => {
    for (const p of ['/', '/faq', '/pompage-solaire', '/nos-solutions', '/installation-solaire-casablanca']) {
      expect(sitemapExcluded(p), p).toBe(false);
    }
  });

  it('le filtre rejoué correspond au littéral présent dans astro.config.mjs', () => {
    const cfg = read('../astro.config.mjs');
    // La même regex (mêmes alternatives, dont \/preview\/) doit vivre dans la config.
    expect(cfg).toContain('type-test|media-test|variants-test|craft-|\\/preview\\/');
  });
});

describe('W104 — LocalBusiness JSON-LD sur l’accueil', () => {
  it('le Layout émet un JSON-LD de type LocalBusiness', () => {
    const layout = read('../src/layouts/Layout.astro');
    expect(layout).toContain("'@type': 'LocalBusiness'");
    expect(layout).toContain('application/ld+json');
  });

  it('l’accueil rend via le Layout partagé → il hérite du LocalBusiness', () => {
    const idx = read('../src/pages/index.astro');
    expect(idx).toContain("import Layout from '../layouts/Layout.astro'");
    expect(idx).toContain('<Layout');
  });
});

describe('W104 — un seul canonical auto-référent par route publique', () => {
  it('le Layout contient exactement UN <link rel="canonical">', () => {
    const layout = read('../src/layouts/Layout.astro');
    const matches = layout.match(/<link\s+rel="canonical"/g) ?? [];
    expect(matches).toHaveLength(1);
  });

  it('le canonical du Layout est auto-référent (URL de la page courante)', () => {
    const layout = read('../src/layouts/Layout.astro');
    // canonical = new URL(Astro.url.pathname, Astro.site) → href de la page elle-même.
    expect(layout).toContain('const canonical = new URL(Astro.url.pathname, Astro.site)');
    expect(layout).toContain('<link rel="canonical" href={canonical.href} />');
  });

  it('les pages publiques passent par le Layout (donc un seul canonical chacune)', () => {
    const publicPages = [
      '../src/pages/index.astro',
      '../src/pages/faq.astro',
      '../src/pages/pompage-solaire.astro',
      '../src/pages/batteries-stockage.astro',
      '../src/pages/maintenance-monitoring.astro',
      '../src/pages/nos-solutions.astro',
      '../src/pages/financement.astro',
      '../src/pages/garanties.astro',
      '../src/pages/realisations/index.astro',
      '../src/pages/installation-solaire-[city].astro',
    ];
    for (const f of publicPages) {
      const src = read(f);
      expect(src, f).toContain("import Layout from");
      expect(src, f).toContain('<Layout');
      // Aucune page publique n'émet son propre <link rel="canonical"> inline :
      // le canonical unique vient du Layout, jamais dupliqué dans la page.
      expect(src.match(/<link\s+rel="canonical"/g) ?? [], f).toHaveLength(0);
    }
  });
});

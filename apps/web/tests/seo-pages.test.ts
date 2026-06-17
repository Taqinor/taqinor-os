// Garde-fous du lot SEO public (W2–W10) : pages ville, études de cas, FAQ,
// guides, Pourquoi, MRE, garanties, maillage interne, format téléphone.
// Vérifie l'indexabilité, l'inclusion sitemap, les données structurées et
// l'intégrité des faits (aucun chiffre inventé).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { REALISATIONS, CITIES, realisationByRef } from '../src/lib/realisations';
import { NAP } from '../src/lib/nap';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// Le filtre d'exclusion sitemap (copié depuis astro.config.mjs).
const sitemapExcluded = (page: string) =>
  /type-test|media-test|variants-test|craft-|\/preview\//.test(page);

describe('réalisations — intégrité des faits', () => {
  it('5 installations réelles, total 43,48 kWc (= chiffre de l’accueil)', () => {
    expect(REALISATIONS).toHaveLength(5);
    const total = REALISATIONS.reduce((s, r) => s + r.kwcNum, 0);
    expect(Number(total.toFixed(2))).toBe(43.48);
  });

  it('slugs uniques', () => {
    const slugs = REALISATIONS.map((r) => r.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it('Nouaceur (réf. NC-10/25) n’a PAS de production inventée', () => {
    const nc = realisationByRef('NC-10/25');
    expect(nc).toBeTruthy();
    expect(nc!.production).toBeNull();
    expect(nc!.productionNum).toBeNull();
  });

  it('réf. 134 : onduleur/batterie non publiés → null (jamais inventés)', () => {
    const r134 = realisationByRef('134');
    expect(r134!.onduleur).toBeNull();
    expect(r134!.batterie).toBeNull();
  });

  it('les productions publiées correspondent au site', () => {
    expect(realisationByRef('468')!.production).toBe('21 406 kWh/an');
    expect(realisationByRef('400')!.production).toBe('14 271 kWh/an');
    expect(realisationByRef('236')!.production).toBe('7 135 kWh/an');
  });
});

describe('villes — alignées sur la zone de service NAP', () => {
  it('les 5 villes = NAP.serviceArea (hors « Maroc »)', () => {
    const cityNames = CITIES.map((c) => c.name);
    const napCities = NAP.serviceArea.filter((s) => s !== 'Maroc');
    expect(cityNames).toEqual(napCities);
  });

  it('seule Casablanca revendique un chantier local (le reste reste honnête)', () => {
    const local = CITIES.filter((c) => c.hasLocalInstall).map((c) => c.name);
    expect(local).toEqual(['Casablanca']);
    for (const c of CITIES.filter((c) => !c.hasLocalInstall)) {
      expect(c.featuredRefs).toHaveLength(0);
    }
  });

  it('l’ensoleillement est indicatif (préfixe « ≈ »), jamais une mesure', () => {
    for (const c of CITIES) expect(c.sunshineHours.startsWith('≈')).toBe(true);
  });
});

describe('pages publiques SEO — indexées et dans le sitemap', () => {
  const publicRoutes = [
    '/installation-solaire-casablanca',
    '/installation-solaire-agadir',
    '/realisations',
    '/realisations/el-jadida-17-kwc',
    '/faq',
    '/guides',
    '/guides/loi-82-21-expliquee',
    '/pourquoi-taqinor',
    '/marocains-du-monde',
    '/garanties',
    '/à-propos',
  ];
  for (const r of publicRoutes) {
    it(`${r} n’est pas exclue du sitemap`, () => {
      expect(sitemapExcluded(r)).toBe(false);
    });
  }

  const files = [
    '../src/pages/installation-solaire-[city].astro',
    '../src/pages/realisations/[slug].astro',
    '../src/pages/realisations/index.astro',
    '../src/pages/faq.astro',
    '../src/pages/guides/index.astro',
    '../src/pages/guides/loi-82-21-expliquee.astro',
    '../src/pages/guides/faut-il-des-batteries.astro',
    '../src/pages/guides/onduleur-hybride-ou-reseau.astro',
    '../src/pages/pourquoi-taqinor.astro',
    '../src/pages/marocains-du-monde.astro',
    '../src/pages/garanties.astro',
    '../src/pages/à-propos.astro',
  ];
  for (const f of files) {
    it(`${f} est publique (pas de noindex) et monte l’élévation`, () => {
      const src = read(f);
      expect(src).not.toContain('noindex');
      expect(src).toContain('V2Enhance');
      expect(src).toContain('class="v2"');
    });
  }
});

describe('données structurées', () => {
  it('le composant Breadcrumb émet un BreadcrumbList', () => {
    const src = read('../src/components/Breadcrumb.astro');
    expect(src).toContain("'@type': 'BreadcrumbList'");
  });

  it('l’étude de cas émet un Article JSON-LD', () => {
    const src = read('../src/pages/realisations/[slug].astro');
    expect(src).toContain("'@type': 'Article'");
    expect(src).toContain('application/ld+json');
  });

  it('la page ville émet un Service avec areaServed (City)', () => {
    const src = read('../src/pages/installation-solaire-[city].astro');
    expect(src).toContain("'@type': 'Service'");
    expect(src).toContain('areaServed');
  });

  it('les 3 guides émettent chacun un Article', () => {
    for (const g of ['loi-82-21-expliquee', 'faut-il-des-batteries', 'onduleur-hybride-ou-reseau']) {
      expect(read(`../src/pages/guides/${g}.astro`)).toContain("'@type': 'Article'");
    }
  });

  it('la page /faq émet UN FAQPage (via le composant Faq), sans doublon', () => {
    const src = read('../src/pages/faq.astro');
    expect(src).toContain('<Faq');
    // Le FAQPage JSON-LD vit dans le composant Faq, jamais inline ici → pas de
    // double bloc FAQPage sur la page (on cible le marqueur JSON-LD, pas le
    // mot « FAQPage » qui apparaît dans le commentaire d'en-tête).
    expect(src).not.toContain("'@type': 'FAQPage'");
    // Et le composant Faq, lui, émet bien le FAQPage.
    expect(read('../src/components/Faq.astro')).toContain("'@type': 'FAQPage'");
  });
});

describe('maillage & téléphone (W9 / W10)', () => {
  it('le pied de page lie les nouvelles pages et les villes', () => {
    const f = read('../src/components/Footer.astro');
    for (const href of ['/realisations', '/guides', '/faq', '/garanties', '/pourquoi-taqinor', '/marocains-du-monde', '/à-propos']) {
      expect(f, href).toContain(`href="${href}"`);
    }
    expect(f).toContain('installation-solaire-');
  });

  it('la nav d’en-tête contient Guides, FAQ et À propos', () => {
    const h = read('../src/components/Header.astro');
    expect(h).toContain("/guides");
    expect(h).toContain("/faq");
    expect(h).toContain("/à-propos");
  });

  it('téléphone affiché reformaté (W10) ; cible tel: et JSON-LD inchangées', () => {
    expect(NAP.phoneDisplayIntl).toBe('+212 6 61 85 04 10');
    expect(NAP.phone).toBe('+212661850410'); // E.164 inchangé (tel:, JSON-LD)
    const h = read('../src/components/Header.astro');
    const f = read('../src/components/Footer.astro');
    expect(h).toContain('NAP.phoneDisplayIntl');
    expect(f).toContain('NAP.phoneDisplayIntl');
    // Les liens tel: pointent toujours vers le E.164 NAP
    expect(h).toContain('tel:${NAP.phone}');
    expect(f).toContain('tel:${NAP.phone}');
  });

  it('breadcrumbs ajoutés aux pages profondes existantes', () => {
    for (const p of ['équipement', 'loi-82-21', 'professionnel', 'résidentiel', 'regularization-article-33']) {
      expect(read(`../src/pages/${p}.astro`), p).toContain('Breadcrumb');
    }
  });
});

describe('teaser garanties (W16)', () => {
  const teaser = read('../src/components/GarantiesTeaser.astro');
  // Corps rendu uniquement (hors commentaire de tête entre les barrières ---),
  // pour que les gardes « rien d'inventé » ne matchent pas la docstring.
  const body = teaser.split('---').slice(2).join('---');

  it('reprend les chiffres déjà publiés sur /garanties et y renvoie', () => {
    for (const fig of ['12 ans', '25 ans', '10 ans', '20 ans', '2 ans']) {
      expect(teaser, fig).toContain(fig);
    }
    expect(teaser).toContain('84,8');
    expect(body).toContain('Deye Cloud');
    expect(body).toContain('href="/garanties"');
  });

  it('n’invente aucun SLA ni politique de sous-performance (corps rendu)', () => {
    // Aucun délai de réponse / SLA inventé ne doit apparaître dans le rendu.
    expect(body).not.toMatch(/\bSLA\b/i);
    expect(body).not.toMatch(/sous\s*-?\s*performance/i);
    expect(body).not.toMatch(/délai de réponse|sous \d+ ?h|24 ?h|48 ?h|7 ?j/i);
  });

  it('est présent sur l’accueil, le résidentiel et le professionnel', () => {
    for (const p of ['index', 'résidentiel', 'professionnel']) {
      expect(read(`../src/pages/${p}.astro`), p).toContain('GarantiesTeaser');
    }
  });
});

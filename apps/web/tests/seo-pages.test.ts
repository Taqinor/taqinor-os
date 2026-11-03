// Garde-fous du lot SEO public (W2–W10) : pages ville, études de cas, FAQ,
// guides, Pourquoi, MRE, garanties, maillage interne, format téléphone.
// Vérifie l'indexabilité, l'inclusion sitemap, les données structurées et
// l'intégrité des faits (aucun chiffre inventé).
import { cityContentBySlug } from '../src/lib/cityContent';
import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { lireAstroAvecBlocs } from './astroBlocsHelper';
import { builtPage, mainOf, visibleText } from './builtHtmlHelper';
// @ts-expect-error — module JS pur sans déclaration de types
import { dateArticle, datesDuDepot, lastmodPour } from '../scripts/sitemap-dates.mjs';
import { REALISATIONS, CITIES, realisationByRef } from '../src/lib/realisations';
import { NAP } from '../src/lib/nap';

const readSrc = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
// ENF19 — le corps des pages ville et études de cas (V2Enhance, class="v2", JSON-LD Service) vit dans
// components/{CityPageBody,RealisationSlugBody,V2Page}.astro + lib/cityPageData.ts : ces pages se lisent avec eux.
const read = (rel: string) =>
  rel.includes('installation-solaire-[city]')
    ? [rel, '../src/components/CityPageBody.astro', '../src/components/V2Page.astro', '../src/lib/cityPageData.ts'].map(readSrc).join('\n')
    : rel.includes('realisations/[slug]')
      ? [rel, '../src/components/RealisationSlugBody.astro', '../src/components/V2Page.astro'].map(readSrc).join('\n')
      : lireAstroAvecBlocs(fileURLToPath(new URL(rel, import.meta.url)));

// Le filtre d'exclusion sitemap (copié depuis astro.config.mjs).
const sitemapExcluded = (page: string) =>
  /type-test|media-test|variants-test|craft-|\/preview\//.test(page);

describe('réalisations — intégrité des faits', () => {
  it('6 installations réelles (2026-09 : + Bouskoura 11,44 kWc), total 54,92 kWc', () => {
    // (2026-09) Bouskoura ajoutée — chantier réel, 11,44 kWc (faits fondateur 08/09/2026) :
    // `kwcNum` optionnel, exclu de la somme (`?? 0`) plutôt qu'un NaN — les 5
    // totaux ORIGINAUX restent bit à bit intacts.
    expect(REALISATIONS).toHaveLength(6);
    const total = REALISATIONS.reduce((s, r) => s + (r.kwcNum ?? 0), 0);
    expect(Number(total.toFixed(2))).toBe(54.92);
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

  it('aucune production annuelle inventée : null pour toutes les installations (WB1)', () => {
    for (const ref of ['468', '400', '236']) {
      const r = realisationByRef(ref);
      expect(r, ref).toBeTruthy();
      expect(r!.production, ref).toBeNull();
      expect(r!.productionNum, ref).toBeNull();
    }
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
    // Lot IA/contenu W23–W30.
    '/pompage-solaire',
    '/batteries-stockage',
    '/maintenance-monitoring',
    '/financement',
    '/nos-solutions',
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
    // Lot IA/contenu W23–W30.
    '../src/pages/pompage-solaire.astro',
    '../src/pages/batteries-stockage.astro',
    '../src/pages/maintenance-monitoring.astro',
    '../src/pages/financement.astro',
    '../src/pages/nos-solutions.astro',
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
    // /faq utilise le composant SANS désactiver le schéma → il porte le FAQPage.
    expect(src).not.toContain('schema={false}');
    // Et le composant Faq, lui, émet bien le FAQPage.
    expect(read('../src/components/Faq.astro')).toContain("'@type': 'FAQPage'");
  });

  it('hygiène FAQPage : l’accueil ne duplique PAS le FAQPage de /faq (W19)', () => {
    const faqCmp = read('../src/components/Faq.astro');
    // Le composant ne rend le JSON-LD que si `schema` est vrai (gardé).
    expect(faqCmp).toMatch(/\{schema && <script type="application\/ld\+json"/);
    // L'accueil réutilise l'accordéon mais coupe le schéma → un seul FAQPage
    // (sur /faq) pour ces questions qui se recoupent.
    const idx = read('../src/pages/index.astro');
    expect(idx).toMatch(/<Faq items=\{faq\} schema=\{false\}/);
    // L'accueil n'émet aucun FAQPage inline non plus.
    expect(idx).not.toContain("'@type': 'FAQPage'");
  });
});

describe('maillage & téléphone (W9 / W10)', () => {
  it('le pied de page lie les nouvelles pages et les villes', () => {
    const f = read('../src/components/Footer.astro');
    // Forme-agnostique : les liens du pied vivent dans des tableaux rendus en
    // boucle (href: '/x'), pas forcément en attribut littéral href="/x".
    for (const href of ['/realisations', '/guides', '/faq', '/garanties', '/pourquoi-taqinor', '/marocains-du-monde', '/à-propos']) {
      expect(f, href).toContain(href);
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

  it('l’accueil lie la galerie vers /realisations et chaque étude de cas (W18, post-W54)', () => {
    const idx = read('../src/pages/index.astro');
    // Lien vers le hub /realisations depuis la galerie. W54 a retiré le bloc
    // « Fiches chantier » en double : la galerie photo porte désormais seule la
    // preuve (et ses données), d'où un seul lien hub au lieu de deux.
    expect((idx.match(/href="\/realisations\/"/g) ?? []).length).toBeGreaterThanOrEqual(1);
    // Chaque carte de la galerie lie son étude de cas (template `/realisations/${g.slug}`).
    expect(idx).toContain('/realisations/${g.slug}');
    // Chaque étude de cas réelle (5 installs) reste référencée par slug sur l’accueil.
    for (const r of REALISATIONS) {
      expect(idx, r.slug).toContain(`slug: '${r.slug}'`);
    }
  });

  it('l’accueil partage le même header/footer que le reste du site (W17)', () => {
    // L'accueil passe par le Layout partagé, qui rend <Header/> + <Footer/> :
    // même nav (Guides, FAQ, À propos), même téléphone formaté, même footer.
    const idx = read('../src/pages/index.astro');
    expect(idx).toContain("import Layout from '../layouts/Layout.astro'");
    expect(idx).toContain('<Layout');
    const layout = read('../src/layouts/Layout.astro');
    expect(layout).toContain('<Header />');
    expect(layout).toContain('<Footer />');
  });
});

describe('teaser garanties (W16)', () => {
  const teaser = read('../src/components/GarantiesTeaser.astro');
  // Corps rendu uniquement (hors commentaire de tête entre les barrières ---),
  // pour que les gardes « rien d'inventé » ne matchent pas la docstring.
  const body = teaser.split('---').slice(2).join('---');

  it('reprend les chiffres déjà publiés sur /garanties et y renvoie', () => {
    for (const fig of ['12 ans', '30 ans', '20 ans', '2 ans']) {
      expect(teaser, fig).toContain(fig);
    }
    // 5 / 10 / 7 ans : dérivés de lib/warranty.ts (Deye, Huawei, batterie Dyness).
    for (const c of ['DEYE_INVERTER_WARRANTY_YEARS', 'HUAWEI_INVERTER_WARRANTY_YEARS', 'BATTERY_WARRANTY_YEARS']) {
      expect(teaser, c).toContain(c);
    }
    expect(teaser).toContain('87,4');
    expect(teaser).toMatch(/temps réel|real-time|الوقت الحقيقي/);
    // W67 : le lien est désormais localisé via localizeNavHref('/garanties', locale)
    // (FR inchangé : localizeNavHref('/garanties','fr') === '/garanties'). On vérifie
    // donc la cible /garanties plutôt que le littéral href="/garanties".
    expect(body).toContain('/garanties');
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

describe('WAUD4 — pages à chemin accentué : hreflang, sélecteur, contexte WhatsApp', () => {
  const CHEMINS = ['résidentiel', 'équipement', 'à-propos'];
  for (const [prefixe, attendu] of [['', 'fr'], ['/en', 'en'], ['/ar', 'ar']] as const) {
    for (const c of CHEMINS) {
      it(`${prefixe}/${c}`, () => {
        const html = builtPage(`${prefixe}/${c}`);
        for (const l of ['fr', 'en', 'ar', 'x-default']) {
          expect(html).toMatch(new RegExp(`<link rel="alternate" hreflang="${l}"`));
        }
        expect(html.includes(`lang="${attendu}"`)).toBe(true);
      });
    }
  }

  it('le lien WhatsApp de /résidentiel/ nomme la page', () => {
    const liens = [...builtPage('/résidentiel').matchAll(/https:\/\/wa\.me\/[^"]+/g)].map((m) => decodeURIComponent(m[0]));
    expect(liens.some((l) => l.includes('page Résidentiel'))).toBe(true);
  });
});

describe('WAUD25 — 404 de la marque', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/pages/404.astro', import.meta.url)), 'utf-8');
  it('trilingue, statut 404, au moins 3 sorties', () => {
    expect(page).toContain('Astro.response.status = 404');
    expect(page).toContain('prerender = false');
    for (const l of ['fr:', 'en:', 'ar:']) expect(page).toContain(l);
    expect(page.match(/data-sortie-404/g)!.length).toBeGreaterThanOrEqual(3);
    expect(page).toContain('quoteJourneyHref(locale)');
    expect(page).toContain('whatsappLink(');
  });
  it('favicon.ico servi', () => {
    const ico = readFileSync(fileURLToPath(new URL('../public/favicon.ico', import.meta.url)));
    expect([...ico.subarray(0, 4)]).toEqual([0, 0, 1, 0]);
  });
});

describe('WAUD58 — pages utilitaires hors index', () => {
  const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../${p}`, import.meta.url)), 'utf-8');
  it('/status, /liens noindex ; /confiance noindex quand le flux est vide, repli vers /garanties', () => {
    expect(lire('src/pages/status/index.astro')).toMatch(/title="Statut du service \| Taqinor"\s+noindex/);
    expect(lire('src/pages/liens.astro')).toMatch(/noindex/);
    const confiance = lire('src/pages/confiance.astro');
    expect(confiance).toContain('noindex={groupes.length === 0}');
    expect(confiance).toContain('/garanties/');
    expect(confiance).not.toContain('momentanément indisponibles');
  });
  it('noindex ne coupe pas la mesure : /liens, /status et /confiance gardent pixel et tag', () => {
    const layout = lire('src/layouts/Layout.astro');
    expect(layout).toMatch(/mesure = !noindex/);
    expect(layout).toContain('{mesure && <MetaPixel />}');
    expect(layout).toContain('{mesure && <GoogleTag />}');
    for (const page of ['src/pages/liens.astro', 'src/pages/status/index.astro', 'src/pages/confiance.astro']) {
      expect(lire(page)).toMatch(/^\s+mesure\r?$/m);
    }
    // Pages privées : noindex sans `mesure`, donc jamais de pixel.
    for (const page of ['src/pages/equipe.astro', 'src/pages/suivi/[token].astro']) {
      expect(lire(page)).not.toMatch(/^\s+mesure\r?$/m);
    }
  });
  it('/liens a un H1 et sort du sitemap', () => {
    expect(lire('src/pages/liens.astro')).toContain('<h1');
    expect(lire('astro.config.mjs')).toContain('\\/liens\\/?$');
  });
});

describe('WAUD85 — lastmod : vraies dates seulement', () => {
  it('guides, articles et relevé sont datés ; une page sans date réelle ne l’est jamais', () => {
    const table = datesDuDepot();
    expect(lastmodPour(table, 'https://taqinor.ma/guides/loi-82-21-expliquee/')).toBe('2026-10-05');
    expect(lastmodPour(table, 'https://taqinor.ma/en/guides/loi-82-21-expliquee/')).toBe('2026-10-05');
    expect(lastmodPour(table, 'https://taqinor.ma/blog/prix-installation-solaire-maroc-2026/')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(lastmodPour(table, 'https://taqinor.ma/production-mesuree/')).toBe('2026-07-05');
    for (const u of ['https://taqinor.ma/', 'https://taqinor.ma/contact/', 'https://taqinor.ma/faq/', 'https://taqinor.ma/installation-solaire-casablanca/']) {
      expect(lastmodPour(table, u)).toBeUndefined();
    }
  });
  it('un brouillon n’a pas de date ; updatedDate l’emporte', () => {
    expect(dateArticle('---\ndraft: true\npubDate: 2026-01-01\n---\n')).toBeNull();
    expect(dateArticle('---\npubDate: 2026-01-01\nupdatedDate: 2026-02-02\n---\n')).toBe('2026-02-02');
  });
  it('astro.config.mjs ne lit plus git', () => {
    expect(readFileSync(fileURLToPath(new URL('../astro.config.mjs', import.meta.url)), 'utf-8')).not.toContain('git log');
  });
});

describe('WAUD37 — aucune référence de tâche interne dans le texte public', () => {
  it('scan de <main> sur tout le build', () => {
    const racine = `${process.cwd()}/dist/client`;
    const fautes: string[] = [];
    for (const f of readdirSync(racine, { recursive: true }) as string[]) {
      if (!String(f).endsWith('index.html')) continue;
      const texte = visibleText(mainOf(readFileSync(`${racine}/${f}`, 'utf-8')).replace(/<!--[\s\S]*?-->/g, ' '));
      for (const m of texte.matchAll(/\b(W|WJ|WA|WB|WC|CIW|AGW|RWEB|QJW)\d+\b/g)) fautes.push(`${f}: ${m[0]}`);
    }
    expect(fautes).toEqual([]);
  });
});

describe('WAUD45 — couverture, heures de soleil et « 300 jours » retirés', () => {
  const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../src/${p}`, import.meta.url)), 'utf-8');
  const PAGES = ['index', 'financement', 'résidentiel', 'nos-solutions', 'faq'].flatMap((p) => [`${p}`, `en/${p}`, `ar/${p}`]);
  it.each(PAGES)('%s : ni 50-100 %%, ni 300 jours', (p) => {
    const s = lire(`pages/${p}.astro`).replace(/\/\*[\s\S]*?\*\//g, '');
    expect(s).not.toMatch(/50\s*(–|-|à|to|إلى)\s*100\s*%/);
    expect(s).not.toMatch(/300 (jours|days|يوم)/);
  });
  it('héros ville : rendement PVGIS de la ville, source nommée, plus d’heures', () => {
    const body = lire('components/CityPageBody.astro');
    expect(body).toContain('specificYield(');
    expect(body).not.toContain('c.sunshineHours}');
    expect(body).not.toContain('50–100 %');
    for (const p of ['', 'en/', 'ar/']) {
      const s = lire(`pages/${p}installation-solaire-[city].astro`);
      expect(s).toMatch(/hoursUnit: 'kWh\/kWc\//);
      expect(s).toContain('PVGIS');
    }
  });
  it('prose ville rendue sans heures chiffrées (roiNuance hors rendu)', () => {
    for (const slug of ['casablanca', 'rabat', 'marrakech', 'tanger', 'agadir']) {
      for (const loc of ['fr', 'en', 'ar'] as const) {
        const cc = cityContentBySlug(slug, loc);
        const rendu = JSON.stringify({ ...cc, roiNuance: '' });
        expect(rendu, `${slug} ${loc}`).not.toMatch(/≈\s?\d[\s,]?\d{3}/);
      }
    }
  });
});

describe('WAUD27 — titres ville et meta de Rabat', () => {
  it('FR « panneaux solaires », AR « الألواح الشمسية », Rabat sans chantier local', () => {
    for (const slug of ['casablanca', 'rabat', 'marrakech', 'tanger', 'agadir']) {
      expect(cityContentBySlug(slug, 'fr').title).toMatch(/^Installation de panneaux solaires à /);
      expect(cityContentBySlug(slug, 'ar').title).toContain('الألواح الشمسية');
    }
    expect(cityContentBySlug('rabat', 'fr').description).not.toContain('dans la région');
    expect(cityContentBySlug('rabat', 'en').description).not.toContain('in the region');
    expect(cityContentBySlug('rabat', 'ar').description).not.toMatch(/في الجهة|بالجهة|في المنطقة/);
  });
  it('titres arabes : prix, accueil, guide onduleur', () => {
    const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../src/pages/ar/${p}.astro`, import.meta.url)), 'utf-8');
    expect(lire('prix-panneaux-solaires-maroc')).toMatch(/title="[^"]*ثمن/);
    expect(lire('index')).toMatch(/title="[^"]*الألواح الشمسية/);
    expect(lire('guides/onduleur-hybride-ou-reseau')).toMatch(/title="[^"]*إنفرتر/);
  });
});

describe('WAUD71 WAUD51 — JSON-LD', () => {
  const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../src/${p}`, import.meta.url)), 'utf-8');
  it('WAUD71 : Product sans Offer sans prix, description depuis fiches.ts', () => {
    const s = lire('pages/produits/[slug].astro');
    expect(s).not.toMatch(/offers: \{/);
    expect(s).not.toContain('InStock');
    expect(s).toContain('description: fiche.resume');
  });
  it('WAUD51 : entité complète sur 3 pages, référence @id ailleurs, Person sur /à-propos seulement', () => {
    const l = lire('layouts/Layout.astro');
    expect(l).toContain("'@id': ENTITE_ID");
    expect(l).toContain('legalName: LEGAL_IDENTITY.raisonSociale');
    expect(l).toContain('contactPoint:');
    expect(l).toContain("availableLanguage: ['fr', 'ar', 'en']");
    expect(l).toMatch(/entiteComplete \? jsonLd : \{/);
    expect(lire('pages/à-propos.astro')).toContain("'@type': 'Person'");
    for (const p of ['pages/index.astro', 'pages/en/index.astro', 'pages/ar/index.astro']) expect(lire(p)).not.toContain("'@type': 'Person'");
  });
});

describe('WAUD53 — « 10 questions » : titre et liens', () => {
  const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../${p}`, import.meta.url)), 'utf-8');
  it('titre « choisir un installateur », liens depuis menu, pied de page, 3 pages et llms.txt', () => {
    expect(lire('src/pages/ressources/10-questions-avant-de-signer.astro')).toContain('title="Choisir un installateur de panneaux solaires au Maroc : 10 questions avant de signer');
    expect(lire('src/pages/ar/ressources/10-questions-avant-de-signer.astro')).toMatch(/title="[^"]*الألواح الشمسية[^"]*10 أسئلة/);
    for (const f of ['src/components/Header.astro', 'src/components/Footer.astro', 'src/pages/résidentiel.astro', 'src/pages/faq.astro', 'src/pages/garanties.astro', 'public/llms.txt']) {
      expect(lire(f), f).toContain('/ressources/10-questions-avant-de-signer');
    }
  });
});

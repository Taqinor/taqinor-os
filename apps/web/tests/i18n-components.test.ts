// W67 — Garde-fou i18n des 6 composants à chiffres (GarantiesTeaser, BrandStrip,
// FounderPortrait, VideoChantier, WhatsAppMock, Testimonials).
//
// Ces composants sont devenus « locale-aware » via un objet STR inline (fr/en/ar)
// + getLocaleFromPath + localizeNavHref. Ce test LIT la source (aucun rendu) et
// vérifie :
//   1. les trois branches fr/en/ar existent ;
//   2. les chaînes FR sont présentes MOT POUR MOT (rendu FR inchangé) ;
//   3. une traduction EN et une traduction AR distinctives existent ;
//   4. les CHIFFRES sont identiques dans toutes les langues (jamais traduits) ;
//   5. le deeplink WhatsApp pré-rempli part dans la langue de la page (WAUD10, D-WAUD-3=a).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { FICHES } from '../src/lib/fiches';
import { CATEGORIES_FICHE, EN_TETES_FICHE } from '../src/lib/fichesLocale';
import { localesForPath } from '../src/i18n/pages';
import { builtPage } from './builtHtmlHelper';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const garanties = read('../src/components/GarantiesTeaser.astro');
const brandStrip = read('../src/components/BrandStrip.astro');
const founder = read('../src/components/FounderPortrait.astro');
const video = read('../src/components/VideoChantier.astro');
const whatsapp = read('../src/components/WhatsAppMock.astro');
const testimonials = read('../src/components/Testimonials.astro');

const ALL: Array<[string, string]> = [
  ['GarantiesTeaser', garanties],
  ['BrandStrip', brandStrip],
  ['FounderPortrait', founder],
  ['VideoChantier', video],
  ['WhatsAppMock', whatsapp],
  ['Testimonials', testimonials],
];

describe('W67 — les 6 composants à chiffres ont 3 branches de locale', () => {
  it.each(ALL)('%s expose getLocaleFromPath + un objet STR fr/en/ar', (_name, src) => {
    // ENF19 : la locale se déduit du chemin, directement ou via lib/contexteLocale (qui appelle getLocaleFromPath).
    expect(src).toMatch(/getLocaleFromPath|contexteLocale\(Astro\.url\.pathname\)/);
    // L'objet de traduction typé Record<Locale, …> avec les trois branches.
    expect(src).toMatch(/Record<\s*Locale/);
    expect(src).toMatch(/\bfr:\s*\{/);
    expect(src).toMatch(/\ben:\s*\{/);
    expect(src).toMatch(/\bar:\s*\{/);
    expect(src).toContain("import type { Locale } from '../i18n/config'");
  });
});

describe('GarantiesTeaser — FR verbatim, EN/AR présents, chiffres invariants', () => {
  it('reprend les libellés FR mot pour mot', () => {
    expect(garanties).toContain('Garanties écrites');
    expect(garanties).toContain('De 2 à 30 ans, noir sur blanc');
    expect(garanties).toContain('Voir toutes nos garanties →');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(garanties).toContain('Written warranties');
    expect(garanties).toContain('See all our warranties →');
    expect(garanties).toContain('ضمانات مكتوبة');
  });
  it('les VALEURS chiffrées sont identiques dans toutes les locales — seuls le mot d’unité et le séparateur décimal localisent (W302)', () => {
    // years est désormais locale-keyé (YEARS_BY_LOCALE) : mêmes nombres, unité localisée.
    for (const fig of ['12 ans', '30 ans', '20 ans', '2 ans']) {       // FR
      expect(garanties, fig).toContain(fig);
    }
    for (const fig of ['12 years', '30 years', '20 years', '2 years']) { // EN
      expect(garanties, fig).toContain(fig);
    }
    // Performance : « 87,4 % » en FR (virgule) ; « 87.4 % » en EN/AR (point —
    // convention déjà en place sur garanties/financement/faq/équipement). La
    // VALEUR (87,4) est identique partout ; seul le séparateur décimal localise.
    // (WA11 2026-07-04 : barème datasheet réel N-type TOPCon, 30 ans / ≥ 87,4 %.)
    expect(garanties).toContain('Performance ≥ 87,4 %');
    expect(garanties).toContain('87.4 %');
    // Les chiffres ne sont JAMAIS « traduits » en chiffres arabo-indiens.
    expect(garanties).not.toMatch(/[٠-٩۰-۹]/);
    // WC10 (2026-07-05) : le suivi n'est plus nommé par la marque de l'app —
    // on vérifie la présence du concept générique « temps réel » (toutes locales).
    expect(garanties).toMatch(/temps réel|real-time|الوقت الحقيقي/);
    // Lien interne localisé (via le helper L = localizeNavHref(href, locale)).
    expect(garanties).toContain('localizeNavHref');
    expect(garanties).toContain("L('/garanties')");
  });
});

describe('BrandStrip — FR verbatim, EN/AR présents, marques invariantes', () => {
  it('reprend le titre et le CTA FR mot pour mot', () => {
    expect(brandStrip).toContain("heading: 'Marques tier-1'"); // WAUD49
    expect(brandStrip).toContain('Voir notre équipement →');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(brandStrip).toContain("heading: 'Tier-1 brands'"); // WAUD49
    expect(brandStrip).toContain('See our equipment →');
    expect(brandStrip).toContain('علامات الفئة الأولى');
  });
  it('localise le lien /équipement et ne touche pas les noms de marque (lib/brands)', () => {
    expect(brandStrip).toContain('localizeNavHref');
    expect(brandStrip).toContain("L('/équipement')");
    // Les noms de marque restent fournis par lib/brands (jamais en dur ni traduits).
    expect(brandStrip).toContain("import { BRANDS } from '../lib/brands'");
  });
});

describe('FounderPortrait — FR verbatim, EN/AR présents, faits/chiffre invariants', () => {
  it('reprend la prose FR mot pour mot', () => {
    expect(founder).toContain('Le fondateur');
    expect(founder).toContain('Un docteur-ingénieur valide chaque étude, à la main');
    expect(founder).toContain('Chaque étude validée par le fondateur');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(founder).toContain('A doctor-engineer validates every study, by hand');
    expect(founder).toContain('The founder and his method →');
    expect(founder).toContain('مهندس دكتور يراجع كل دراسة');
  });
  it('garde les faits/chiffres identiques : Reda Kasri, 10+ ans, liste de marques', () => {
    expect(founder).toContain('Reda Kasri');
    expect(founder).toContain('10+ ans'); // figure identique fr/en/ar (pas « 10+ years »)
    expect(founder).not.toContain('10+ years');
    expect(founder).toContain('Huawei, Ericsson et STMicroelectronics');
    // Déclaration FOUNDER_PHOTO bien typée (null = repli texte, ou portrait réel)
    // + branche conditionnelle conservée + lien localisé.
    expect(founder).toMatch(/const FOUNDER_PHOTO\s*:\s*string \| null\s*=\s*(?:null|'[^']+')\s*;/);
    expect(founder).toContain('FOUNDER_PHOTO ?');
    expect(founder).toContain('localizeNavHref');
    expect(founder).toContain("L('/à-propos')");
  });
});

describe('VideoChantier — FR verbatim, EN/AR présents, lieux/chemins invariants', () => {
  it('reprend la prose FR mot pour mot', () => {
    expect(video).toContain('30 secondes de chantier — installations réelles');
    expect(video).toContain('Regardez l\'équipe au travail');
    expect(video).toContain('Lire la vidéo de chantier');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(video).toContain('Watch the team at work');
    expect(video).toContain('Play the on-site video');
    expect(video).toContain('شاهد الفريق أثناء العمل');
  });
  it('garde les lieux et les chemins vidéo identiques dans toutes les locales', () => {
    // Noms de lieux jamais traduits.
    expect(video).toContain('El Jadida');
    expect(video).toContain('Nouaceur');
    // Chemins /videos/... intacts. W346 — la façade clic-pour-lire est
    // désormais LiteVideo (poster passé SANS extension, .avif/.webp dérivés
    // à l'intérieur du composant) ; le chemin racine et le mp4 restent
    // identiques dans toutes les locales.
    expect(video).toContain('poster="/videos/chantier-poster"');
    expect(video).toContain('/videos/chantier-a.mp4');
  });
});

describe('WhatsAppMock — FR verbatim, EN/AR présents, deeplink dans la langue de la page', () => {
  it('reprend les bulles et libellés FR mot pour mot', () => {
    expect(whatsapp).toContain('répond sur WhatsApp sous 1 h, 7j/7');
    expect(whatsapp).toContain('WhatsApp direct');
    expect(whatsapp).toContain('📷 Photo de la toiture');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(whatsapp).toContain('replies on WhatsApp within 1 h, 7 days a week');
    expect(whatsapp).toContain('📷 Photo of the roof');
    expect(whatsapp).toContain('يردّ عبر واتساب خلال ساعة، 7 أيام على 7');
  });
  it('garde les chiffres + lieux identiques et le deeplink WhatsApp localisé (WAUD10)', () => {
    // Chiffres et lieu identiques dans toutes les langues (présents au moins en FR).
    expect(whatsapp).toContain('1 800 MAD');
    // WAUD19 — aucune puissance chiffrée ni « anonymisé » : c'est un exemple.
    expect(whatsapp).not.toMatch(/kWc'|\d kWc/);
    expect(whatsapp).not.toContain('anonymis');
    expect(whatsapp).toContain('Casablanca');
    // WAUD10 — le message pré-rempli suit la locale ; FR identique à l'octet.
    expect(whatsapp).toContain("fr: 'Bonjour, je viens de faire le diagnostic sur taqinor.ma.'");
    expect(whatsapp).toContain("en: 'Hello, I have just done the diagnosis on taqinor.ma.'");
    expect(whatsapp).toContain('whatsappLink(WHATSAPP_LEADS, WA_TEXTE[locale])');
  });
});

describe('Testimonials — FR verbatim, EN/AR présents, garde « rien d’inventé »', () => {
  it('reprend l’eyebrow et le titre FR mot pour mot', () => {
    expect(testimonials).toContain('Avis clients');
    expect(testimonials).toContain('Ils nous ont fait confiance');
    expect(testimonials).toContain('avis Google');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(testimonials).toContain('Client reviews');
    expect(testimonials).toContain('They trusted us');
    expect(testimonials).toContain('آراء العملاء');
  });
  it('conserve la garde de données réelles (aucun markup sans données)', () => {
    expect(testimonials).toContain('hasTestimonials()');
    expect(testimonials).toContain('hasRating()');
  });
});

describe('WAUD24 — liens ville du pied de page localisés', () => {
  it('href via L(), libellé par locale, villes en arabe', () => {
    const src = readFileSync(fileURLToPath(new URL('../src/components/Footer.astro', import.meta.url)), 'utf-8');
    expect(src).toContain('href={L(`/installation-solaire-${c.slug}`)}');
    expect(src).toContain("villeLocale(c.slug, locale)");
    expect(src).toContain('in ${villeLocale(c.slug, locale)}');
  });
  it('villeLocale : arabe sur /ar, nom latin sinon', async () => {
    const { villeLocale } = await import('../src/lib/realisations');
    expect(villeLocale('casablanca', 'ar')).toBe('الدار البيضاء');
    expect(villeLocale('tanger', 'en')).toBe('Tangier');
    expect(villeLocale('rabat', 'fr')).toBe('Rabat');
  });
});

describe('WAUD87 — assurance habitation sur /garanties EN et AR', () => {
  it.each(['en/garanties', 'ar/garanties'])('%s', (p) => {
    const src = readFileSync(fileURLToPath(new URL(`../src/pages/${p}.astro`, import.meta.url)), 'utf-8');
    expect(src).toContain('items={insuranceFaq}');
    expect(src).toContain('schema={false}');
  });
  it('pages ville et tunnel AR : liens vers la page de LEUR locale quand elle existe (loi 82-21, méthodologie, réalisations)', () => {
    const lire = (p: string) => readFileSync(fileURLToPath(new URL(`../src/${p}`, import.meta.url)), 'utf-8');
    const city = lire('lib/cityContent.ts');
    expect(city).toContain(`en: '<a href="/en/loi-82-21/"`);
    expect(city).toContain(`ar: '<a href="/ar/loi-82-21/"`);
    const arTunnel = lire('pages/ar/devis/mon-toit.astro');
    expect(arTunnel).not.toMatch(/href="\/(methodologie-estimation|realisations)\/"/);
  });

  it('fiches /produits : chaque fiche et chaque catégorie a son en-tête EN et AR (nom + résumé)', () => {
    expect(FICHES.length).toBe(16);
    for (const f of FICHES) {
      for (const loc of ['en', 'ar'] as const) {
        const t = EN_TETES_FICHE[f.slug]?.[loc];
        expect(t?.nom, `${f.slug} ${loc}`).toBeTruthy();
        expect(t?.resume, `${f.slug} ${loc}`).toBeTruthy();
        expect(t?.resume).not.toBe(f.resume);
        expect(CATEGORIES_FICHE[f.categorie][loc], f.categorie).toBeTruthy();
      }
    }
    expect(localesForPath('/produits')).toEqual(['fr', 'en', 'ar']);
    expect(localesForPath('/produits/cablage')).toEqual(['fr', 'en', 'ar']);
  });

  it.each(['en', 'ar'])('fiches /%s/produits construites : en-tête localisé + repli FR explicite', (loc) => {
    expect(builtPage(`/${loc}/produits`)).toContain(`href="/${loc}/produits/cablage/"`);
    for (const f of FICHES) {
      const html = builtPage(`/${loc}/produits/${f.slug}`);
      expect(html).toContain(EN_TETES_FICHE[f.slug][loc as 'en' | 'ar'].nom.replace(/&/g, '&amp;'));
      expect(html).toMatch(new RegExp(`<a href="/produits/${f.slug}/" hreflang="fr"`));
    }
  });
});

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
//   5. le deeplink WhatsApp pré-rempli reste EN FRANÇAIS.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

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
    expect(src).toContain('getLocaleFromPath');
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
    expect(garanties).toContain('De 2 à 25 ans, noir sur blanc');
    expect(garanties).toContain('Voir toutes nos garanties →');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(garanties).toContain('Written warranties');
    expect(garanties).toContain('See all our warranties →');
    expect(garanties).toContain('ضمانات مكتوبة');
  });
  it('les VALEURS chiffrées sont identiques dans toutes les locales — seuls le mot d’unité et le séparateur décimal localisent (W302)', () => {
    // years est désormais locale-keyé (YEARS_BY_LOCALE) : mêmes nombres, unité localisée.
    for (const fig of ['12 ans', '25 ans', '10 ans', '20 ans', '2 ans']) {       // FR
      expect(garanties, fig).toContain(fig);
    }
    for (const fig of ['12 years', '25 years', '10 years', '20 years', '2 years']) { // EN
      expect(garanties, fig).toContain(fig);
    }
    // Performance : « 84,8 % » en FR (virgule) ; « 84.8 % » en EN/AR (point —
    // convention déjà en place sur garanties/financement/faq/équipement). La
    // VALEUR (84,8) est identique partout ; seul le séparateur décimal localise.
    expect(garanties).toContain('Performance ≥ 84,8 %');
    expect(garanties).toContain('84.8 %');
    // Les chiffres ne sont JAMAIS « traduits » en chiffres arabo-indiens.
    expect(garanties).not.toMatch(/[٠-٩۰-۹]/);
    // Le nom de marque reste identique et présent dans le corps rendu.
    expect(garanties).toContain('Deye Cloud');
    // Lien interne localisé (via le helper L = localizeNavHref(href, locale)).
    expect(garanties).toContain('localizeNavHref');
    expect(garanties).toContain("L('/garanties')");
  });
});

describe('BrandStrip — FR verbatim, EN/AR présents, marques invariantes', () => {
  it('reprend le titre et le CTA FR mot pour mot', () => {
    expect(brandStrip).toContain('Marques tier-1 · distributeurs officiels au Maroc');
    expect(brandStrip).toContain('Voir notre équipement →');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(brandStrip).toContain('Tier-1 brands · official distributors in Morocco');
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

describe('WhatsAppMock — FR verbatim, EN/AR présents, deeplink FR figé', () => {
  it('reprend les bulles et libellés FR mot pour mot', () => {
    expect(whatsapp).toContain('répond généralement en quelques minutes');
    expect(whatsapp).toContain('WhatsApp direct');
    expect(whatsapp).toContain('📷 Photo de la toiture');
  });
  it('contient des traductions EN et AR distinctives', () => {
    expect(whatsapp).toContain('usually replies within a few minutes');
    expect(whatsapp).toContain('📷 Photo of the roof');
    expect(whatsapp).toContain('يردّ عادةً خلال بضع دقائق');
  });
  it('garde les chiffres + lieux identiques et le deeplink WhatsApp EN FRANÇAIS', () => {
    // Chiffres et lieu identiques dans toutes les langues (présents au moins en FR).
    expect(whatsapp).toContain('1 800 MAD');
    expect(whatsapp).toContain('5 à 9 kWc');
    expect(whatsapp).toContain('Casablanca');
    // Le message pré-rempli du lien reste en français (atteint l'équipe FR).
    expect(whatsapp).toContain(
      "whatsappLink(WHATSAPP_LEADS, 'Bonjour, je viens de faire le diagnostic sur taqinor.ma.')",
    );
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

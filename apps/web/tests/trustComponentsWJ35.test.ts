// WJ35 — Preuve sociale premium + grade v3 sur les deux pages du parcours.
//
// Lecture SOURCE en texte, sans build (même convention que quoteCtaWJ36.test.ts
// / sticky-cta-w59.test.ts) : ces composants font du rendu conditionnel Astro
// (fetch réseau / DOM) qu'on ne peut pas monter facilement sous vitest — on
// prouve donc les invariants d'INTÉGRITÉ (jamais de chiffre/avis fabriqué) et
// de câblage (les deux pages du parcours importent bien les composants) au
// niveau du code source, et on couvre la logique pure (InstallCounter) via
// realisations.ts directement.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { REALISATIONS } from '../src/lib/realisations';
import { TESTIMONIALS, GOOGLE_RATING, hasTestimonials, hasRating } from '../src/lib/testimonials';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const STAR_RATING = read('../src/components/StarRating.astro');
const TESTIMONIAL_CAROUSEL = read('../src/components/TestimonialCarousel.astro');
const INSTALL_COUNTER = read('../src/components/InstallCounter.astro');
const CERT_LOGO_ROW = read('../src/components/CertLogoRow.astro');
const MON_TOIT = read('../src/pages/devis/mon-toit.astro');
const PROPOSITION = read('../src/pages/proposition/[token].astro');

describe('WJ35 — StarRating : jamais de note/avis fabriqués', () => {
  it('ne rend une note QUE si GOOGLE_RATING est réel (hasRating())', () => {
    expect(STAR_RATING).toContain('hasRating()');
    expect(STAR_RATING).toContain('pending real content from Reda');
  });
  it("aujourd'hui GOOGLE_RATING est null → le composant montre le scaffold, jamais une note inventée", () => {
    expect(hasRating()).toBe(false);
    expect(GOOGLE_RATING).toBeNull();
  });
});

describe('WJ35 — TestimonialCarousel : mêmes garde-fous d\'intégrité que <Testimonials/>', () => {
  it('ne rend rien tant que TESTIMONIALS est vide (source unique de vérité)', () => {
    expect(TESTIMONIAL_CAROUSEL).toContain('hasTestimonials()');
    expect(hasTestimonials()).toBe(false);
    expect(TESTIMONIALS).toHaveLength(0);
  });
  it('accessible : région aria-live, navigation étiquetée', () => {
    expect(TESTIMONIAL_CAROUSEL).toContain('aria-live="polite"');
    expect(TESTIMONIAL_CAROUSEL).toContain('aria-label="Avis précédent"');
    expect(TESTIMONIAL_CAROUSEL).toContain('aria-label="Avis suivant"');
  });
});

describe('WJ35 — InstallCounter : chiffres dérivés de realisations.ts, jamais codés en dur', () => {
  it("n'importe que realisations.ts comme source (aucune valeur numérique inventée dans le composant)", () => {
    expect(INSTALL_COUNTER).toContain("from '../lib/realisations'");
    // WC5/WC6 (2026-07-05) : le composant n'affiche plus la CAPACITÉ installée
    // (« 43,48 kWc », retirée du site) mais la PRODUCTION mesurée de la flotte.
    expect(INSTALL_COUNTER).toContain('MEASURED_FLEET_LIFETIME_MWH');
    expect(INSTALL_COUNTER).not.toContain('kWc installés');
  });
  it('affiche la production mesurée de la flotte (MWh), pas la capacité', () => {
    expect(INSTALL_COUNTER).toContain('MEASURED_FLEET_LIFETIME_MWH');
    expect(INSTALL_COUNTER).toContain('MWh produits et mesurés');
    expect(INSTALL_COUNTER).not.toContain('kwcNum');
  });
  it('reduced-motion : le count-up est gated, la valeur finale est toujours révélée', () => {
    expect(INSTALL_COUNTER).toContain('prefers-reduced-motion');
    expect(INSTALL_COUNTER).toContain('shouldDigitRoll');
    expect(INSTALL_COUNTER).toContain('reserveWidth');
  });
});

describe('WJ35 — CertLogoRow : faits vérifiables uniquement, aucun logo fabriqué', () => {
  it('documente pourquoi aucune image de logo (licence) et flague le remplacement futur', () => {
    expect(CERT_LOGO_ROW).toContain('pending real content from Reda');
    expect(CERT_LOGO_ROW).toContain('IEC 61215');
    expect(CERT_LOGO_ROW).toContain('Loi 82-21');
  });
});

describe('WJ35 — câblage : les deux pages du parcours montent les composants premium', () => {
  it('mon-toit.astro importe StarRating / CertLogoRow / InstallCounter / ZelligeSignature', () => {
    expect(MON_TOIT).toContain("import StarRating from '../../components/StarRating.astro'");
    expect(MON_TOIT).toContain("import CertLogoRow from '../../components/CertLogoRow.astro'");
    expect(MON_TOIT).toContain("import InstallCounter from '../../components/InstallCounter.astro'");
    expect(MON_TOIT).toContain("import ZelligeSignature from '../../components/ZelligeSignature.astro'");
    expect(MON_TOIT).toContain('<InstallCounter');
    expect(MON_TOIT).toContain('<StarRating');
    expect(MON_TOIT).toContain('<CertLogoRow');
    expect(MON_TOIT).toContain('<ZelligeSignature');
  });

  it('[token].astro importe StarRating / TestimonialCarousel / InstallCounter / CertLogoRow', () => {
    expect(PROPOSITION).toContain("import StarRating from '../../components/StarRating.astro'");
    expect(PROPOSITION).toContain("import TestimonialCarousel from '../../components/TestimonialCarousel.astro'");
    expect(PROPOSITION).toContain("import InstallCounter from '../../components/InstallCounter.astro'");
    expect(PROPOSITION).toContain("import CertLogoRow from '../../components/CertLogoRow.astro'");
    expect(PROPOSITION).toContain('<InstallCounter');
    expect(PROPOSITION).toContain('<StarRating');
    expect(PROPOSITION).toContain('<TestimonialCarousel');
    expect(PROPOSITION).toContain('<CertLogoRow');
  });

  it('[token].astro applique le grade v3 UNIQUEMENT à une photo non-LCP (jamais au héros eager)', () => {
    // Le héros (loading="eager", ligne ~244) ne doit JAMAIS porter v3-grade —
    // seule la photo secondaire du bloc 3D (loading="lazy") le porte.
    const heroImgBlock = PROPOSITION.slice(PROPOSITION.indexOf('loading="eager"') - 400, PROPOSITION.indexOf('loading="eager"') + 50);
    expect(heroImgBlock).not.toContain('v3-grade');
    const lazyImgBlock = PROPOSITION.slice(PROPOSITION.indexOf('loading="lazy"') - 400, PROPOSITION.indexOf('loading="lazy"') + 50);
    expect(lazyImgBlock).toContain('v3-grade');
  });

  it('[token].astro importe v3-photo-motion.css (ne monte pas <V2Enhance/> qui l’importerait sinon)', () => {
    expect(PROPOSITION).toContain("import '../../styles/v3-photo-motion.css'");
  });
});

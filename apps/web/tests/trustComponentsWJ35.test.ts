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
const PROPOSITION = read('../src/pages/proposition/[...token].astro');

describe('WJ35/WN6 — StarRating : jamais de note/avis fabriqués, jamais un scaffold "bientôt"', () => {
  it('ne rend une note QUE si GOOGLE_RATING est réel (hasRating())', () => {
    expect(STAR_RATING).toContain('hasRating()');
  });
  // WN6 — « Avis clients — bientôt disponibles » retiré (checked-facts-only :
  // pas de note → on OMET le composant entièrement, jamais un "coming soon").
  it('WN6 — plus de scaffold "bientôt disponibles" : le composant ne rend RIEN sans note réelle', () => {
    expect(STAR_RATING).not.toContain('bientôt disponibles');
    expect(STAR_RATING).not.toContain('pending real content from Reda');
  });
  it("aujourd'hui GOOGLE_RATING est null → le composant ne rend rien, jamais une note inventée", () => {
    expect(hasRating()).toBe(false);
    expect(GOOGLE_RATING).toBeNull();
  });
  // WJ99 — proposal page must not silently fall back to French under EN/AR.
  it('WJ99 — le libellé "avis Google" porte une variante anglaise (data-en)', () => {
    expect(STAR_RATING).toContain('data-en="Google reviews"');
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

  // (fondateur 2026-08-17) les DURÉES du bandeau viennent de la source unique
  // des garanties : plus aucun « 30 ans » / « 10 ans » codé en dur ici.
  it('tire ses durées de lib/warranty.ts (aucun chiffre de garantie en dur)', () => {
    expect(CERT_LOGO_ROW).toContain("from '../lib/warranty'");
    expect(CERT_LOGO_ROW).toContain('PANEL_PERFORMANCE_WARRANTY_YEARS');
    expect(CERT_LOGO_ROW).toContain('INVERTER_WARRANTY_YEARS');
    expect(CERT_LOGO_ROW).not.toContain("label: '30 ans'");
    expect(CERT_LOGO_ROW).not.toContain("label: '10 ans'");
  });

  // Règle fondateur : un badge n'existe que s'il est cliquable vers une page
  // réelle et bien remplie. Le composant sait rendre un badge en LIEN quand la
  // page hôte lui en donne la cible ; sans `hrefs`, rendu historique inchangé.
  it('rend un badge en lien quand la page hôte fournit sa cible', () => {
    expect(CERT_LOGO_ROW).toContain('hrefs?: Partial<Record<CertKey, string>>');
    expect(CERT_LOGO_ROW).toContain('cert-row__item--link');
    expect(CERT_LOGO_ROW).toContain('href={hrefs[c.key]}');
  });

  it('[token].astro ne rend QUE des badges cliquables (garanties, fiche panneau, loi 82-21)', () => {
    expect(PROPOSITION).toContain('<CertLogoRow keys={certKeys} hrefs={certHrefs} />');
    expect(PROPOSITION).toContain("panneaux: '/garanties'");
    expect(PROPOSITION).toContain("onduleur: '/garanties'");
    expect(PROPOSITION).toContain('iec: `/produits/${panelFicheSlug}`');
    // Le badge IEC n'existe que si le panneau devisé a une fiche appariée.
    expect(PROPOSITION).toContain("ficheBySlug(slug)?.categorie === 'Panneaux photovoltaïques'");
    // La loi 82-21 a sa page dédiée trilingue (+ guide) : badge cliquable.
    expect(PROPOSITION).toContain("loi8221: '/loi-82-21'");
  });
  // WJ99 — le libellé de détail porte désormais une variante anglaise, et
  // l'aria-label racine (statique auparavant) porte les 3 traductions en
  // data-attrs pour que la page hôte (proposition/[token].astro) le retraduise.
  it('WJ99 — detail data-i18n porte data-en, aria-label racine porte les 3 data-aria-label-*', () => {
    expect(CERT_LOGO_ROW).toContain('detailEn:');
    expect(CERT_LOGO_ROW).toMatch(/data-en=\{c\.detailEn\}/);
    expect(CERT_LOGO_ROW).toContain('data-aria-label-fr="Certifications et garanties"');
    expect(CERT_LOGO_ROW).toContain('data-aria-label-en="Certifications and warranties"');
    expect(CERT_LOGO_ROW).toContain('data-aria-label-ar="الشهادات والضمانات"');
  });
});

describe('WJ99 — proposition/[token].astro : aria-label retranslated on language switch', () => {
  it('the signature canvas aria-label carries all 3 languages, not a static FR string', () => {
    expect(PROPOSITION).toContain('data-aria-label-fr="Zone de signature manuscrite');
    expect(PROPOSITION).toContain('data-aria-label-en="Handwritten signature area');
    expect(PROPOSITION).toContain('data-aria-label-ar="منطقة التوقيع اليدوي');
  });

  it('applyLang() retranslates [data-aria-label-fr] elements on every language switch', () => {
    expect(PROPOSITION).toContain("querySelectorAll<HTMLElement>('[data-aria-label-fr]')");
    expect(PROPOSITION).toContain('el.dataset.ariaLabelAr');
    expect(PROPOSITION).toContain('el.dataset.ariaLabelEn');
    expect(PROPOSITION).toContain('el.dataset.ariaLabelFr');
  });
});

describe('WJ101 — keyboard-accessible signature step on proposition/[token].astro', () => {
  it('the signature canvas is keyboard-focusable (tabindex) with a visible focus style', () => {
    expect(PROPOSITION).toMatch(/id="sign-pad"\s*\n\s*tabindex="0"/);
    expect(PROPOSITION).toContain('.sign-pad:focus-visible');
  });

  it('an explicit "skip signature" affordance exists, in FR/EN/AR, and moves focus to the name field', () => {
    expect(PROPOSITION).toContain('id="sign-pad-skip"');
    expect(PROPOSITION).toContain('data-fr="Signature non nécessaire — passer au nom"');
    expect(PROPOSITION).toContain('data-en="Signature not needed — skip to name"');
    expect(PROPOSITION).toContain('data-ar="لا حاجة للتوقيع — الانتقال إلى الاسم"');
    expect(PROPOSITION).toMatch(/getElementById\('sign-pad-skip'\)\?\.addEventListener\('click', \(\) => \{\s*\n\s*\(document\.getElementById\('sign-nom'\)/);
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

  // (fondateur 2026-08-17) la proposition ne monte PLUS <StarRating/> : sans
  // note Google réelle le composant ne rendait rien, et la décision du jour
  // bannit tout avis/étoile de ce document commercial. Les trois autres
  // composants restent câblés à l'identique.
  it('[token].astro importe TestimonialCarousel / InstallCounter / CertLogoRow, PAS StarRating', () => {
    expect(PROPOSITION).toContain("import TestimonialCarousel from '../../components/TestimonialCarousel.astro'");
    expect(PROPOSITION).toContain("import InstallCounter from '../../components/InstallCounter.astro'");
    expect(PROPOSITION).toContain("import CertLogoRow from '../../components/CertLogoRow.astro'");
    expect(PROPOSITION).toContain('<InstallCounter');
    expect(PROPOSITION).toContain('<TestimonialCarousel');
    expect(PROPOSITION).toContain('<CertLogoRow');
    expect(PROPOSITION).not.toContain("import StarRating from '../../components/StarRating.astro'");
    expect(PROPOSITION).not.toContain('<StarRating />');
  });

  it('[token].astro applique le grade v3 UNIQUEMENT à une photo non-LCP (jamais au héros eager)', () => {
    // Le héros (loading="eager", ligne ~244) ne doit JAMAIS porter v3-grade —
    // seule la photo secondaire du bloc 3D (loading="lazy", dans #roof3d) le
    // porte. WJ114 a ajouté une AUTRE image lazy plus haut dans le document
    // (photo du vendeur, hors bloc 3D, sans grade v3) : on scope donc la
    // recherche à PARTIR du bloc #roof3d pour cibler la bonne image, plutôt
    // que la première occurrence globale de loading="lazy".
    const heroImgBlock = PROPOSITION.slice(PROPOSITION.indexOf('loading="eager"') - 400, PROPOSITION.indexOf('loading="eager"') + 50);
    expect(heroImgBlock).not.toContain('v3-grade');
    const roof3dSection = PROPOSITION.slice(PROPOSITION.indexOf('id="roof3d"'));
    const lazyImgBlock = roof3dSection.slice(roof3dSection.indexOf('loading="lazy"') - 400, roof3dSection.indexOf('loading="lazy"') + 50);
    expect(lazyImgBlock).toContain('v3-grade');
  });

  it('[token].astro importe v3-photo-motion.css (ne monte pas <V2Enhance/> qui l’importerait sinon)', () => {
    expect(PROPOSITION).toContain("import '../../styles/v3-photo-motion.css'");
  });
});

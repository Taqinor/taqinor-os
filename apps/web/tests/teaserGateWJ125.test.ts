// WJ125 — RÈGLE FONDATEUR anti-concurrent : le document d'estimation chiffré ne
// se rend PLUS pendant la saisie publique. À l'étape 3, une CARTE TEASER
// verrouillée (aperçu flouté SANS le moindre chiffre) mène au formulaire ; le
// document complet + « Imprimer » vivent uniquement sur /proposition/<token>.
//
// Ces tests sont des lectures SOURCE en texte (même convention que
// perceivedPerfWJ34 / quoteCtaWJ36 : ces micro-interactions DOM ne se montent
// pas facilement sous vitest). Ils prouvent trois invariants de sûreté :
//   (1) le rendu chiffré public est SUPPRIMÉ — le document est `hidden` et les
//       chemins « succès » s'arrêtent AVANT d'écrire un chiffre, la carte teaser
//       ne contient AUCUN chiffre dimensionnant (le flou seul ne suffit pas : un
//       concurrent lit le DOM, donc les zones gatées ne portent aucune valeur) ;
//   (2) le CALCUL reste — estimateShown + labels sont toujours construits et
//       joints au lead (le commercial voit tout) ;
//   (3) la carte teaser + la promesse « étude complète et personnalisée »
//       existent sur les 3 locales, et « Imprimer » a disparu du parcours public.
//
// Le CALCUL/l'API (captureWJ, wj111AgricoleEstimate, la partie unitaire de
// wj112RefineEstimate) restent verts SANS changement — seul le RENDU public est
// gaté ici.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const PAGES = {
  FR: read('../src/pages/devis/mon-toit.astro'),
  EN: read('../src/pages/en/devis/mon-toit.astro'),
  AR: read('../src/pages/ar/devis/mon-toit.astro'),
} as const;

// Motifs de FUITE de chiffre dimensionnant (unité-porteurs). On ne teste PAS les
// chiffres nus (l'icône cadenas SVG a des coordonnées) mais les VALEURS avec unité.
const FIGURE_LEAK = /\bkWc\b|\bkWh\b|\bMAD\b|\bDH\b|dirham|m³|%|panneaux|panels|\/\s*mois|\/\s*month|\/\s*an\b|\/\s*yr\b|\/\s*سنة/i;

// Les ids des zones CHIFFRÉES qui ne doivent JAMAIS vivre dans la carte teaser.
const FIGURE_IDS = [
  'mt-est-kwc', 'mt-est-prod', 'mt-est-savings', 'mt-est-payback',
  'mt-pro-kwc', 'mt-pro-prod', 'mt-pro-eco', 'mt-pro-retour',
  'mt-agri-pompe', 'mt-agri-champ', 'mt-agri-eau', 'mt-agri-fuel',
  'mt-cost-of-waiting-value', 'mt-nearest-install-text', 'mt-doc-chart',
];

/** Extrait le bloc markup de la carte teaser : de `id="mt-teaser"` jusqu'au
 *  document chiffré qui la suit (`id="mt-doc"`). */
function teaserBlock(src: string): string {
  const start = src.indexOf('id="mt-teaser"');
  const end = src.indexOf('id="mt-doc"', start);
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe.each(Object.entries(PAGES))('WJ125 — %s mon-toit.astro : rendu public gaté', (_label, src) => {
  it('le garde-fou de gating est ARMÉ (le rendu chiffré public est coupé)', () => {
    expect(src).toContain('const PUBLIC_ESTIMATE_GATED: boolean = true;');
    // Le document chiffré est `hidden` en permanence dans le parcours public.
    expect(src).toContain('<div id="mt-doc" class="mt-doc mt-4" hidden>');
    // Le teaser est révélé AVANT toute branche de calcul (une seule porte).
    expect(src).toContain('if (PUBLIC_ESTIMATE_GATED) showEstimateTeaser(mode);');
  });

  it('showEstimateTeaser masque #mt-doc + les zones fuiantes hors-#mt-doc et révèle le teaser', () => {
    const start = src.indexOf('function showEstimateTeaser(');
    expect(start).toBeGreaterThan(-1);
    const fn = src.slice(start, start + 900);
    expect(fn).toContain("$('mt-doc')");
    expect(fn).toContain("$('mt-nearest-install')");
    expect(fn).toContain("$('mt-cost-of-waiting')");
    expect(fn).toContain("$('mt-print-estimate')");
    expect(fn).toContain("$('mt-teaser')");
    // révèle le teaser, masque le reste.
    expect(fn).toContain('teaser.hidden = false');
  });

  it('les 3 chemins « succès » (résidentiel/pro/agricole) s\'arrêtent AVANT d\'écrire un chiffre', () => {
    // Exactement une porte-teaser sans accolade (le top-gate) + 3 retours gatés.
    const gatedReturns = (src.match(/if \(PUBLIC_ESTIMATE_GATED\) \{/g) ?? []).length;
    expect(gatedReturns).toBe(3);
    // Chaque retour gaté annonce un message SANS chiffre (GATED_ANNOUNCE), jamais
    // l'ancienne annonce « Votre estimation : X kWc … ».
    const gatedAnnounce = (src.match(/announceEstimate\(GATED_ANNOUNCE\)/g) ?? []).length;
    expect(gatedAnnounce).toBe(3);
  });

  it('la carte teaser ne contient AUCUN chiffre dimensionnant (le flou seul ne gate pas)', () => {
    const block = teaserBlock(src);
    expect(block).not.toMatch(FIGURE_LEAK);
    for (const id of FIGURE_IDS) {
      expect(block).not.toContain(id);
    }
    // aperçu purement décoratif (barres grises), jamais peuplé par le calcul.
    expect(block).toContain('mt-teaser-preview');
    expect(block).toContain('mt-teaser-bar');
    // une accroche grossière + la promesse honnête.
    expect(block).toContain('id="mt-teaser-hook-roof"');
    expect(block).toContain('id="mt-teaser-hook-pump"');
  });

  it('le CALCUL reste : estimateShown + labels sont toujours construits et joints au lead', () => {
    // estimateShown est reconstruit dans les 3 moteurs (résidentiel objet + pro/agri `s`).
    expect(src).toContain('estimateShown = {');
    expect((src.match(/estimateShown = s;/g) ?? []).length).toBeGreaterThanOrEqual(2);
    // …et parvient au webhook CRM inchangé (contrat capture-lead).
    expect(src).toContain('estimateShown: estimateShown ?? undefined,');
    expect(src).toContain('kwcLabel: lastKwcLabel || undefined,');
    expect(src).toContain('savingsLabel: lastSavingsLabel || undefined,');
  });

  it('« Imprimer / Enregistrer en PDF » a disparu du parcours public (bouton + ligne d\'immédiateté)', () => {
    // Plus de BOUTON d'impression dans le markup (les handlers JS restent des no-op via ?. ).
    expect(src).not.toContain('<button type="button" id="mt-print-estimate"');
    // Plus de promesse « estimation immédiate » (il n'y a plus de chiffre à l'écran).
    expect(src).not.toContain('Estimation immédiate — pas une simple demande de rappel');
    expect(src).not.toContain('Instant estimate — not just a callback request');
  });
});

describe('WJ125 — la promesse « étude complète et personnalisée » est présente sur chaque locale', () => {
  it('FR', () => {
    const block = teaserBlock(PAGES.FR);
    expect(block).toContain('Recevez votre étude complète et personnalisée');
    expect(block).toContain('Votre toit peut couvrir une bonne part de votre facture.');
  });
  it('EN', () => {
    const block = teaserBlock(PAGES.EN);
    expect(block).toContain('Get your complete, personalised study');
    expect(block).toContain('Your roof could cover a good part of your bill.');
  });
  it('AR', () => {
    const block = teaserBlock(PAGES.AR);
    // AR : dual-node data-fr (défaut SSR) + data-ar (appliqué par applyLang('ar')).
    expect(block).toContain('استلموا دراستكم الكاملة والمخصّصة');
    expect(block).toContain('سطحكم يمكن أن يغطّي جزءاً كبيراً من فاتورتكم.');
  });
});

describe('WJ125 — le message aria-live gaté ne divulgue aucun chiffre (parité voyant/lecteur d\'écran)', () => {
  it.each(Object.entries(PAGES))('%s : GATED_ANNOUNCE est figure-free', (_label, src) => {
    const m = /const GATED_ANNOUNCE = '([^']*)';/.exec(src);
    expect(m).not.toBeNull();
    if (!m) return;
    expect(m[1]).not.toMatch(FIGURE_LEAK);
  });
});

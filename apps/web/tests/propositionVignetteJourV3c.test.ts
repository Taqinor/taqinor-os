// PREVIEW-V3C (16/09/2026) — LA VIGNETTE DE « VOS ÉCONOMIES » EST LA JOURNÉE.
//
// Ordre fondateur (Reda, 16/09) : « quand j'ai dit qu'on devrait ajouter la
// production vs la consommation, je parlais du chiffre JOURNALIER, pas de
// l'annuel. » La carte portait les 12 barres MENSUELLES ; elle porte désormais
// la MÊME courbe journalière que la vue « Sur une journée » du chapitre
// Production, rendue en compact par la MÊME fonction pure.
//
// Deux gardes, et la seconde est la plus importante :
//  1. le mode compact est purement ADDITIF — sans le 6ᵉ paramètre, le SVG est
//     identique OCTET POUR OCTET à celui d'hier (aucune régression possible sur
//     le grand dessin, qui est le plus persuasif de la page) ;
//  2. la vignette n'a PAS de repère d'axe, donc elle ne peut pas écrire
//     « profil — année type » : la page ne la rend QUE sur une échelle réelle.
//     Sans ça, une cloche normalisée nue passerait pour une mesure — c'est
//     exactement la règle « zéro chiffre inventé » appliquée à un dessin.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { renderYearCurve, DEFAULT_CURVE_BOX } from '../src/lib/proposalCurve';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');

const COMPACT_BOX = { width: 320, height: 128, padLeft: 6, padRight: 6, padTop: 6, padBottom: 18 };
const COMPACT_OPTS = { annotate: false, sun: false };

/** Forme PVGIS servie (24 parts, somme 1) — la même discipline que le backend. */
const FORME = Array.from({ length: 24 }, (_, h) => (h >= 6 && h <= 19 ? Math.sin(((h - 6) / 14) * Math.PI) : 0));
const SOMME = FORME.reduce((a, b) => a + b, 0);
const SERVED = {
  production: { forme: FORME.map((v) => v / SOMME), kwhJour: 28.4, picKw: 4.2 },
  consumptionKwhJour: 19.6,
  season: 'ete' as const,
};

describe('PREVIEW-V3C — le mode compact est ADDITIF (défaut byte-identique)', () => {
  it('sans le 6ᵉ paramètre, le SVG est identique à un appel avec {}', () => {
    const sansParam = renderYearCurve(5200, DEFAULT_CURVE_BOX, 'fr', {}, null);
    const avecVide = renderYearCurve(5200, DEFAULT_CURVE_BOX, 'fr', {}, null, {});
    expect(avecVide.svg).toBe(sansParam.svg);
    expect(avecVide).toEqual(sansParam);
  });

  it('idem sur le chemin SERVI (forme PVGIS + conso réelle), dans les trois langues', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const sansParam = renderYearCurve(5200, DEFAULT_CURVE_BOX, lang, { mode: 'residentiel' }, SERVED);
      const avecVide = renderYearCurve(5200, DEFAULT_CURVE_BOX, lang, { mode: 'residentiel' }, SERVED, {});
      expect(avecVide.svg, lang).toBe(sansParam.svg);
    }
  });

  it('les drapeaux de vérité (échelle réelle, forme servie, conso réelle) ne bougent pas en compact', () => {
    const plein = renderYearCurve(5200, COMPACT_BOX, 'fr', { mode: 'residentiel' }, SERVED);
    const compact = renderYearCurve(5200, COMPACT_BOX, 'fr', { mode: 'residentiel' }, SERVED, COMPACT_OPTS);
    expect(compact.hasRealScale).toBe(plein.hasRealScale);
    expect(compact.hasServedShape).toBe(plein.hasServedShape);
    expect(compact.hasRealConsScale).toBe(plein.hasRealConsScale);
  });
});

describe('PREVIEW-V3C — ce que la vignette dessine, et ce qu’elle ne dessine pas', () => {
  const compact = renderYearCurve(5200, COMPACT_BOX, 'fr', { mode: 'residentiel' }, SERVED, COMPACT_OPTS);

  it('garde les DEUX courbes — production pleine, consommation pointillée', () => {
    expect(compact.svg).toContain('class="curve-solar-line"');
    expect(compact.svg).toContain('class="curve-cons-line"');
    expect(compact.svg).toContain('stroke-dasharray="4 3"');
  });

  it('retire le repère d’axe (qui est aussi la source du tap-to-reveal) et le soleil', () => {
    expect(compact.svg).not.toContain('data-curve-scale');
    expect(compact.svg).not.toContain('curve-sun');
    // Le repère est la SEULE chose qui écrit des chiffres dans le SVG : sans
    // lui, la vignette ne porte aucun nombre.
    expect(compact.svg).not.toContain('kWh');
    expect(compact.svg).not.toContain('kW<');
  });

  it('garde les trois repères horaires, dans la langue demandée', () => {
    expect(compact.svg).toContain('lever');
    expect(compact.svg).toContain('midi');
    expect(compact.svg).toContain('coucher');
    const ar = renderYearCurve(5200, COMPACT_BOX, 'ar', { mode: 'residentiel' }, SERVED, COMPACT_OPTS);
    expect(ar.svg).toContain('الشروق');
    expect(ar.svg).toContain('الغروب');
  });

  it('tient dans la hauteur demandée (viewBox 320×128, ~130 px)', () => {
    expect(compact.svg).toContain('viewBox="0 0 320 128"');
  });

  it('le grand dessin, lui, garde son repère et son soleil', () => {
    const plein = renderYearCurve(5200, DEFAULT_CURVE_BOX, 'fr', { mode: 'residentiel' }, SERVED);
    expect(plein.svg).toContain('data-curve-scale');
    expect(plein.svg).toContain('curve-sun');
  });
});

describe('PREVIEW-V3C — la page pose la vignette, et seulement quand c’est vrai', () => {
  it('la carte « Vos économies » rend la courbe JOURNALIÈRE, plus les barres mensuelles', () => {
    expect(PROPOSITION).toContain('showCurveVignette');
    expect(PROPOSITION).toContain('curveCompactByLang');
    expect(PROPOSITION).toContain('COMPACT_CURVE_OPTS');
    // La vignette mensuelle de v3 n'existe plus.
    expect(PROPOSITION).not.toContain('chartCompactFr');
    expect(PROPOSITION).not.toContain('COMPACT_CHART_BOX');
  });

  it('le gate exige une ÉCHELLE RÉELLE — jamais une courbe illustrative nue', () => {
    const ligne = PROPOSITION.split('\n').find((l) => l.startsWith('const showCurveVignette')) ?? '';
    expect(ligne).toContain('hasRealScale');
    expect(ligne).toContain('svg.length > 0');
  });

  it('le graphe MENSUEL complet reste dans le repli (rien n’a été supprimé)', () => {
    expect(PROPOSITION).toContain('data-prod-layer="monthly"');
    expect(PROPOSITION).toContain('chartSvgFr');
    expect(PROPOSITION).toContain('renderProposalChart(data?.monthly_production');
  });

  it('les deux pastilles portent leurs trois langues', () => {
    expect(PROPOSITION).toContain('data-fr="Production solaire" data-en="Solar production" data-ar="الإنتاج الشمسي"');
    expect(PROPOSITION).toContain('data-fr="Votre consommation" data-en="Your consumption" data-ar="استهلاككم"');
  });

  it('la vignette a sa propre classe : ni animation de tracé, ni tap-to-reveal', () => {
    expect(PROPOSITION).toContain('class="curve-vignette"');
    expect(PROPOSITION).toContain('.curve-vignette {');
    // Le câblage tap-to-reveal ne vise que .chart-svg / .daily-curve-wrap.
    expect(PROPOSITION).toContain("('.chart-svg, .daily-curve-wrap')");
  });
});

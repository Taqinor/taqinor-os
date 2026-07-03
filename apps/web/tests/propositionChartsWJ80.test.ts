// WJ80 — Charts que parlent la langue de la page ET du téléphone.
// Prouve : (a) les étiquettes de mois/heures suivent `lang` (FR/EN/AR), jamais
// un repli français figé sous EN/AR ; (b) une annotation pic/annuel visible
// existe dans le SVG (pas seulement dans le texte alentour) ; (c) chaque barre/
// repère porte des data-* tap-to-reveal (le survol `<title>` est invisible au
// tactile) ; (d) le comportement PAR DÉFAUT (sans `lang`) reste FR, rétro-
// compatible avec l'appel historique.
import { describe, expect, it } from 'vitest';
import {
  renderProposalChart,
  monthLabelsFor,
  MONTH_LABELS_FR,
  MONTH_LABELS_EN,
  MONTH_LABELS_AR,
} from '../src/lib/proposalChart';
import { renderYearCurve } from '../src/lib/proposalCurve';

const PROD = [800, 900, 1100, 1300, 1500, 1600, 1700, 1650, 1400, 1100, 850, 750];
const CONS = [1200, 1100, 1000, 900, 850, 1300, 1600, 1550, 1000, 950, 1050, 1250];

describe('WJ80 — renderProposalChart : langue + annotation + tap-to-reveal', () => {
  it('monthLabelsFor bascule FR/EN/AR (12 valeurs chacune)', () => {
    expect(monthLabelsFor('fr')).toEqual(MONTH_LABELS_FR);
    expect(monthLabelsFor('en')).toEqual(MONTH_LABELS_EN);
    expect(monthLabelsFor('ar')).toEqual(MONTH_LABELS_AR);
    expect(MONTH_LABELS_EN).toHaveLength(12);
    expect(MONTH_LABELS_AR).toHaveLength(12);
  });

  it('sans `lang` (repli par défaut) → FR, rétro-compatible', () => {
    const svg = renderProposalChart(PROD, CONS);
    for (const lbl of MONTH_LABELS_FR) expect(svg).toContain(`>${lbl}<`);
  });

  it('lang=en → étiquettes de mois anglaises, jamais de français figé', () => {
    const svg = renderProposalChart(PROD, CONS, undefined, 'en');
    for (const lbl of MONTH_LABELS_EN) expect(svg).toContain(`>${lbl}<`);
    for (const lbl of MONTH_LABELS_FR) expect(svg).not.toContain(`>${lbl}<`);
  });

  it('lang=ar → étiquettes de mois arabes', () => {
    const svg = renderProposalChart(PROD, CONS, undefined, 'ar');
    for (const lbl of MONTH_LABELS_AR) expect(svg).toContain(`>${lbl}<`);
  });

  it('porte une annotation VISIBLE de pic mensuel + total annuel (calculée depuis les valeurs backend)', () => {
    const svg = renderProposalChart(PROD, CONS);
    const peak = Math.max(...PROD);
    const total = PROD.reduce((a, b) => a + b, 0);
    expect(svg).toContain(`pic ≈`);
    expect(svg).toMatch(new RegExp(peak.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')));
    expect(svg).toMatch(new RegExp(total.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')));
  });

  it('chaque barre porte des data-* tap-to-reveal (mois + valeur déjà formatés)', () => {
    const svg = renderProposalChart(PROD, CONS);
    expect(svg).toContain('data-chart-bar');
    expect(svg).toContain('data-month="janv."');
    expect(svg).toContain('data-value="800 kWh"');
    expect(svg).toContain('role="button"');
    expect(svg).toContain('tabindex="0"');
  });

  it('polices relevées pour la lisibilité mobile (>= 9, plus les anciennes 7)', () => {
    const svg = renderProposalChart(PROD, CONS);
    expect(svg).not.toContain('font-size="7"');
  });
});

describe('WJ80 — renderYearCurve : langue + tap-to-reveal du repère pic/moyenne', () => {
  it('sans `lang` (repli par défaut) → FR, rétro-compatible', () => {
    const out = renderYearCurve(10000);
    expect(out.svg).toContain('lever');
    expect(out.svg).toContain('midi');
    expect(out.svg).toContain('coucher');
  });

  it('lang=en → étiquettes horaires anglaises', () => {
    const out = renderYearCurve(10000, undefined, 'en');
    expect(out.svg).toContain('sunrise');
    expect(out.svg).toContain('noon');
    expect(out.svg).toContain('sunset');
    expect(out.svg).not.toContain('>lever<');
  });

  it('lang=ar → étiquettes horaires arabes + repli « année type » traduit', () => {
    const out = renderYearCurve(10000, undefined, 'ar');
    expect(out.svg).toContain('الشروق');
    expect(out.svg).toContain('الظهر');
    expect(out.svg).toContain('الغروب');

    const fallback = renderYearCurve(null, undefined, 'ar');
    expect(fallback.svg).toContain('نمط — سنة نموذجية');
  });

  it('repère pic/moyenne porte des data-* tap-to-reveal quand échelle réelle', () => {
    const out = renderYearCurve(10000);
    expect(out.svg).toContain('data-curve-scale');
    expect(out.svg).toContain('data-peak=');
    expect(out.svg).toContain('data-avg=');
    expect(out.svg).toContain('role="button"');
  });

  it('mode « année type » (sans production) — aucune valeur kWh fabriquée, dans les trois langues', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const out = renderYearCurve(null, undefined, lang);
      expect(out.svg).not.toMatch(/\d[\d ,.]*kWh/);
    }
  });
});

// Tests PURS de la logique de la fenêtre « Production estimée » (W50). Aucun DOM, aucun
// réseau : on vérifie la sélection de série par scope, le cyclage mois/jour, le rescale
// linéaire par nombre de panneaux, le plafonnement honnête des économies, et la géométrie
// SVG (barres + courbe horaire).
import { describe, expect, it } from 'vitest';
import {
  yearSeries,
  monthSeries,
  daySeries,
  cycleMonth,
  cycleDay,
  daysInMonth,
  rescaleByPanels,
  rescaleDateByPanels,
  annualSavings,
  monthlySavings,
  dailySavings,
  barGeometry,
  dayCurvePath,
  dayAreaPath,
  fmtKwh,
  fmtKwc,
  fmtSavings,
  sourceLabel,
  isEstimate,
  DEFAULT_GRAPH_BOX,
  MONTH_NAMES_FR,
  MONTH_LABELS_FR,
} from '../src/lib/productionWindow';
import {
  DAYS_IN_MONTH,
  PANEL_KWC,
  scaleByKwc,
  type PerKwcProduction,
  type ScaledProduction,
  type SpecificDateProfile,
} from '../src/lib/productionEngine';

// — Fixtures déterministes (production PAR 1 kWc, ancrée comme le ferait le moteur) ——

function bell24(peak = 0.6): number[] {
  // Cloche solaire simple (06–18 h), pic à midi.
  const out = new Array<number>(24).fill(0);
  for (let h = 6; h <= 18; h++) {
    const x = (h - 12) / 4;
    out[h] = peak * Math.exp(-0.5 * x * x);
  }
  return out;
}

function makePerKwc(annual = 1600): PerKwcProduction {
  // 12 mensuels qui somment à `annual`, jours types en cloche recalés sur E_m.
  const weights = [0.72, 0.8, 0.95, 1.05, 1.15, 1.2, 1.22, 1.18, 1.05, 0.92, 0.78, 0.68];
  const wTot = weights.reduce((a, b) => a + b, 0);
  const monthlyKwh = weights.map((w) => (annual * w) / wTot);
  const sum = monthlyKwh.reduce((a, b) => a + b, 0);
  const corr = annual / sum;
  const monthly = monthlyKwh.map((v) => v * corr);
  const shape = bell24();
  const shapeSum = shape.reduce((a, b) => a + b, 0);
  const typicalDayByMonth: number[][] = [];
  const dailyKwhByMonth: number[] = [];
  for (let m = 0; m < 12; m++) {
    const targetDaily = monthly[m] / DAYS_IN_MONTH[m];
    const k = shapeSum > 0 ? targetDaily / shapeSum : 0;
    const prof = shape.map((v) => v * k);
    typicalDayByMonth.push(prof);
    dailyKwhByMonth.push(prof.reduce((a, b) => a + b, 0));
  }
  return { source: 'pvgis', annualKwh: annual, monthlyKwh: monthly, typicalDayByMonth, dailyKwhByMonth };
}

function scaledOf(annual = 1600, panels = 12): ScaledProduction {
  return scaleByKwc(makePerKwc(annual), panels * PANEL_KWC);
}

describe('cyclage mois', () => {
  it('avance et recule avec wrap circulaire 0↔11', () => {
    expect(cycleMonth(0, 1)).toBe(1);
    expect(cycleMonth(11, 1)).toBe(0); // déc → janv
    expect(cycleMonth(0, -1)).toBe(11); // janv → déc
    expect(cycleMonth(5, -1)).toBe(4);
  });

  it('le cyclage parcourt TOUS les 12 mois et revient au départ', () => {
    let m = 0;
    const seen = new Set<number>();
    for (let i = 0; i < 12; i++) {
      seen.add(m);
      m = cycleMonth(m, 1);
    }
    expect(seen.size).toBe(12); // les 12 mois ont été visités
    expect(m).toBe(0); // retour à janvier après 12 pas
  });
});

describe('cyclage jour (dans le mois)', () => {
  it('reste dans le mois et wrappe au dernier/premier jour', () => {
    // février = 28 jours
    expect(cycleDay(1, 1, -1)).toBe(28); // 1 fév recule → 28 fév
    expect(cycleDay(1, 28, 1)).toBe(1); // 28 fév avance → 1 fév
    expect(cycleDay(0, 15, 1)).toBe(16); // janvier
  });
  it('daysInMonth renvoie le bon nombre par mois', () => {
    expect(daysInMonth(0)).toBe(31); // janvier
    expect(daysInMonth(1)).toBe(28); // février
    expect(daysInMonth(3)).toBe(30); // avril
  });
});

describe('scope → bonne série', () => {
  it('Année = 12 barres mensuelles + total annuel = annualKwh', () => {
    const prod = scaledOf(1600, 12);
    const { bars, totalKwh } = yearSeries(prod);
    expect(bars).toHaveLength(12);
    expect(bars[0].label).toBe(MONTH_LABELS_FR[0]);
    expect(totalKwh).toBeCloseTo(prod.annualKwh, 3);
    // la somme des barres ≈ le total annuel (cohérence moteur)
    const sumBars = bars.reduce((a, b) => a + b.kwh, 0);
    expect(sumBars).toBeCloseTo(prod.annualKwh, 0);
  });

  it('Mois = ~jours-du-mois barres journalières + total mensuel', () => {
    const prod = scaledOf(1600, 12);
    for (const m of [0, 1, 3]) {
      const { bars, totalKwh } = monthSeries(prod, m);
      expect(bars).toHaveLength(DAYS_IN_MONTH[m]); // janv 31, fév 28, avr 30
      expect(totalKwh).toBeCloseTo(prod.monthlyKwh[m], 3);
      // total journalier moyen × jours = total mensuel
      expect(bars[0].kwh * DAYS_IN_MONTH[m]).toBeCloseTo(prod.monthlyKwh[m], 0);
    }
  });

  it('Jour = 24 points horaires ; par défaut le JOUR TYPE du mois', () => {
    const prod = scaledOf(1600, 12);
    const { points, totalKwh, isTypical } = daySeries(prod, 5, null);
    expect(points).toHaveLength(24);
    expect(isTypical).toBe(true);
    // total journalier = somme des puissances horaires = total journalier du mois
    expect(totalKwh).toBeCloseTo(prod.dailyKwhByMonth[5], 3);
    // nuit = 0
    expect(points[0].kw).toBe(0);
    expect(points[23].kw).toBe(0);
  });

  it('Jour : une DATE précise fournie SURCHARGE le jour type', () => {
    const prod = scaledOf(1600, 12);
    const specific: SpecificDateProfile = {
      month: 6,
      day: 15,
      hourlyKw: bell24(2.5), // profil clairement différent du jour type
      dailyKwh: bell24(2.5).reduce((a, b) => a + b, 0),
      yearsAveraged: 5,
    };
    const typical = daySeries(prod, 5, null);
    const picked = daySeries(prod, 5, specific);
    expect(picked.isTypical).toBe(false);
    expect(picked.totalKwh).toBeCloseTo(specific.dailyKwh, 3);
    expect(picked.totalKwh).not.toBeCloseTo(typical.totalKwh, 1); // vraiment différent
  });
});

describe('rescale linéaire par nombre de panneaux (sans appel serveur)', () => {
  it('doubler les panneaux double TOUTES les figures (annuel, mensuel, journalier)', () => {
    const perKwc = makePerKwc(1600);
    const a = rescaleByPanels(perKwc, 10, PANEL_KWC);
    const b = rescaleByPanels(perKwc, 20, PANEL_KWC);
    expect(b.annualKwh).toBeCloseTo(a.annualKwh * 2, 6);
    for (let m = 0; m < 12; m++) {
      expect(b.monthlyKwh[m]).toBeCloseTo(a.monthlyKwh[m] * 2, 6);
      expect(b.dailyKwhByMonth[m]).toBeCloseTo(a.dailyKwhByMonth[m] * 2, 6);
    }
    // le jour type aussi (puissance horaire) double
    expect(b.typicalDayByMonth[5][12]).toBeCloseTo(a.typicalDayByMonth[5][12] * 2, 6);
  });

  it('rescale d\'une date précise est linéaire', () => {
    const date: SpecificDateProfile = {
      month: 3,
      day: 1,
      hourlyKw: bell24(1),
      dailyKwh: bell24(1).reduce((a, b) => a + b, 0),
      yearsAveraged: 5,
    };
    const a = rescaleDateByPanels(date, 10, PANEL_KWC);
    const b = rescaleDateByPanels(date, 30, PANEL_KWC);
    expect(b.dailyKwh).toBeCloseTo(a.dailyKwh * 3, 6);
    expect(b.hourlyKw[12]).toBeCloseTo(a.hourlyKw[12] * 3, 6);
  });

  it('0 panneau → tout à zéro (pas de NaN)', () => {
    const out = rescaleByPanels(makePerKwc(1600), 0, PANEL_KWC);
    expect(out.annualKwh).toBe(0);
    expect(out.monthlyKwh.every((v) => v === 0)).toBe(true);
  });
});

describe('économies plafonnées (jamais production × tarif non plafonné)', () => {
  it('annuel : l\'économie ne dépasse JAMAIS la facture évitable', () => {
    const target = 14000; // conso annuelle
    const s = annualSavings(20000, target); // surproduction massive
    const sMatched = annualSavings(target, target);
    // surproduire au-delà de la conso n'augmente pas l'économie (plafond autoconso)
    expect(s.high).toBeLessThanOrEqual(sMatched.high + 1e-6);
    expect(s.high).toBeGreaterThan(0);
    expect(s.low).toBeLessThanOrEqual(s.high);
  });

  it('mensuel et journalier sont des fractions cohérentes de l\'annuel', () => {
    const target = 14000;
    const yr = annualSavings(12000, target);
    const mo = monthlySavings(1000, target); // 1000 kWh/mois ≈ 12000/an
    const day = dailySavings(12000 / 365, target);
    // l'économie mensuelle ≈ annuelle/12 (même conso ramenée), jamais au-dessus
    expect(mo.high).toBeLessThanOrEqual(yr.high / 12 + 1e-6);
    expect(day.high).toBeGreaterThanOrEqual(0);
    expect(mo.high).toBeGreaterThan(0);
  });

  it('production nulle → économie nulle', () => {
    expect(annualSavings(0, 14000)).toEqual({ low: 0, high: 0 });
    expect(monthlySavings(0, 14000)).toEqual({ low: 0, high: 0 });
  });
});

describe('géométrie SVG (déterministe)', () => {
  it('barGeometry : 12 barres réparties, la plus haute occupe la hauteur utile', () => {
    const bars = MONTH_LABELS_FR.map((label, i) => ({ label, kwh: 100 + i * 10 }));
    const rects = barGeometry(bars, DEFAULT_GRAPH_BOX, 0.2);
    expect(rects).toHaveLength(12);
    const plotH = DEFAULT_GRAPH_BOX.height - DEFAULT_GRAPH_BOX.padTop - DEFAULT_GRAPH_BOX.padBottom;
    // la dernière barre (max) atteint la hauteur de tracé
    expect(rects[11].height).toBeCloseTo(plotH, 5);
    // toutes restent dans la zone
    for (const r of rects) {
      expect(r.x).toBeGreaterThanOrEqual(DEFAULT_GRAPH_BOX.padLeft - 1e-6);
      expect(r.height).toBeGreaterThanOrEqual(0);
    }
  });

  it('barGeometry : toutes valeurs nulles → barres de hauteur 0 (pas de NaN)', () => {
    const rects = barGeometry([{ label: 'a', kwh: 0 }, { label: 'b', kwh: 0 }]);
    expect(rects.every((r) => r.height === 0 && Number.isFinite(r.x))).toBe(true);
  });

  it('dayCurvePath : 24 points → chemin M…L… non vide ; ≠24 → vide', () => {
    const pts = bell24(0.6).map((kw, h) => ({ hour: h, kw }));
    const d = dayCurvePath(pts, DEFAULT_GRAPH_BOX);
    expect(d.startsWith('M')).toBe(true);
    expect((d.match(/L/g) || []).length).toBe(23); // 24 points → 1 M + 23 L
    expect(dayCurvePath(pts.slice(0, 10))).toBe(''); // mauvaise longueur → vide
  });

  it('dayAreaPath ferme le chemin (Z)', () => {
    const pts = bell24(0.6).map((kw, h) => ({ hour: h, kw }));
    const area = dayAreaPath(pts, DEFAULT_GRAPH_BOX);
    expect(area.endsWith('Z')).toBe(true);
  });
});

describe('formatage FR + étiquettes de source', () => {
  it('fmtKwh : espace fine en séparateur, unité après, « ~ » optionnel', () => {
    expect(fmtKwh(12480)).toMatch(/kWh$/);
    expect(fmtKwh(12480)).toMatch(/12.480/); // séparateur de milliers (espace insécable)
    expect(fmtKwh(12480, true).startsWith('~')).toBe(true);
    expect(fmtKwh(-5)).toBe('0 kWh');
  });
  it('fmtKwc : 1 décimale + unité', () => {
    expect(fmtKwc(8.64)).toMatch(/kWc$/);
    expect(fmtKwc(8.64)).toMatch(/8,6/);
  });
  it('fmtSavings : fourchette MAD', () => {
    expect(fmtSavings(9200, 11800)).toMatch(/9.200 – 11.800 MAD/);
  });
  it('sourceLabel + isEstimate distinguent PVGIS du repli', () => {
    expect(sourceLabel('pvgis')).toMatch(/PVGIS/);
    expect(sourceLabel('estimate')).toMatch(/estimé/i);
    expect(isEstimate('estimate')).toBe(true);
    expect(isEstimate('pvgis')).toBe(false);
  });
  it('MONTH_NAMES_FR a 12 mois longs', () => {
    expect(MONTH_NAMES_FR).toHaveLength(12);
    expect(MONTH_NAMES_FR[2]).toBe('mars');
  });
});

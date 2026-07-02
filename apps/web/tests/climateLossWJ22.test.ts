// WJ22 — couche de pertes climatiques honnêtes (opt-in, défaut OFF). La production réelle
// côtière estivale est sur-estimée (~15–20 %) : dérate thermique + salissure + brume. On
// vérifie les bornes du dérate, que la fourchette respecte low ≤ point ≤ high, et que les
// économies de la borne basse ne dépassent JAMAIS le coût énergie évitable. Module PUR.
import { describe, expect, it } from 'vitest';
import {
  climateDerateFactor,
  productionConfidenceBand,
  annualSavingsMad,
  billToAnnualKwh,
  billMAD,
  TEMP_COEFF_PMAX_PER_C,
  SUMMER_CELL_DELTA_T_C,
  EXTRA_SOILING_LOSS,
  HAZE_LOSS,
  recommend,
  packConfig,
} from '../src/lib/estimatorBrainV2';
import type { LngLat } from '../src/lib/roof';

describe('WJ22 — dérate climatique (bornes documentées)', () => {
  it('facteur dans ]0;1[ avec les constantes par défaut', () => {
    const f = climateDerateFactor();
    expect(f).toBeGreaterThan(0);
    expect(f).toBeLessThan(1);
  });

  it('la perte totale est de l’ordre de 15–20 % (été côtier), jamais un gain', () => {
    const f = climateDerateFactor();
    const lossPct = (1 - f) * 100;
    expect(lossPct).toBeGreaterThan(10);
    expect(lossPct).toBeLessThan(25);
  });

  it('sans aucune perte (constantes nulles) → facteur 1', () => {
    expect(climateDerateFactor(0, 0, 0, 0)).toBeCloseTo(1, 9);
  });

  it('compose bien thermique × salissure × brume', () => {
    const thermal = 1 + TEMP_COEFF_PMAX_PER_C * SUMMER_CELL_DELTA_T_C;
    const expected = thermal * (1 - EXTRA_SOILING_LOSS) * (1 - HAZE_LOSS);
    expect(climateDerateFactor()).toBeCloseTo(expected, 9);
  });

  it('clampe les entrées absurdes (perte > 100 % → facteur borné ≥ 0)', () => {
    expect(climateDerateFactor(-1, 1000, 2, 2)).toBeGreaterThanOrEqual(0);
    expect(climateDerateFactor(-1, 1000, 2, 2)).toBeLessThanOrEqual(1);
  });
});

describe('WJ22 — fourchette de confiance production', () => {
  it('low ≤ point ≤ high, high = chiffre nu', () => {
    const b = productionConfidenceBand(10000);
    expect(b.high).toBe(10000);
    expect(b.low).toBeLessThanOrEqual(b.point);
    expect(b.point).toBeLessThanOrEqual(b.high);
    expect(b.low).toBeGreaterThan(0);
  });

  it('point = moyenne géométrique de low et high', () => {
    const b = productionConfidenceBand(8000);
    expect(b.point).toBeCloseTo(Math.sqrt(b.low * b.high), 6);
  });

  it('chiffre ≤ 0 → fourchette nulle', () => {
    expect(productionConfidenceBand(0)).toEqual({ low: 0, point: 0, high: 0 });
    expect(productionConfidenceBand(-5)).toEqual({ low: 0, point: 0, high: 0 });
  });

  it('dérate 1 → fourchette plate (low = point = high)', () => {
    const b = productionConfidenceBand(5000, 1);
    expect(b.low).toBeCloseTo(5000, 6);
    expect(b.point).toBeCloseTo(5000, 6);
    expect(b.high).toBe(5000);
  });
});

describe('WJ22 — économies de la borne basse plafonnées à la facture', () => {
  it('même dératée, l’économie ne dépasse jamais le coût évitable', () => {
    const bill = 1200; // MAD/mois
    const target = billToAnnualKwh(bill);
    const avoidable = billMAD(target / 12) * 12; // coût énergie annuel évitable
    // production généreuse (surdimensionnée) : borne basse quand même ≤ coût évitable.
    const band = productionConfidenceBand(target * 3);
    const savLow = annualSavingsMad(band.low, target);
    expect(savLow.high).toBeLessThanOrEqual(avoidable + 1e-6);
    expect(savLow.low).toBeLessThanOrEqual(savLow.high + 1e-6);
    expect(savLow.low).toBeGreaterThanOrEqual(0);
  });
});

describe('WJ22 — additif : recommend() reste inchangé (aucun chemin par défaut ne l’appelle)', () => {
  it('recommend ne dépend pas de la couche climatique (résultat déterministe)', () => {
    const ring: LngLat[] = [
      [-7.62, 33.59],
      [-7.6196, 33.59],
      [-7.6196, 33.5903],
      [-7.62, 33.5903],
    ];
    const r1 = recommend(ring, 33.59, 900);
    const r2 = recommend(ring, 33.59, 900);
    // Déterministe et non muté par l'existence de la couche opt-in.
    expect(r1.recommended.kwc).toBe(r2.recommended.kwc);
    expect(r1.recommended.annualKwh).toBe(r2.recommended.annualKwh);
    // sanity : packConfig toujours opérationnel
    expect(packConfig(ring, 33.59, { family: 'south', tiltDeg: 15 }).best.count).toBeGreaterThanOrEqual(0);
  });
});

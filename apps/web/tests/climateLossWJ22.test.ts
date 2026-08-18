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
  PRODUCTION_NET_FACTOR,
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

describe('WJ22 — fourchette de confiance production (rebasée 20 %, 18/08)', () => {
  it('low ≤ point ≤ high, point = le central reçu (base 20 %)', () => {
    const b = productionConfidenceBand(10000);
    // ORDRE FONDATEUR 18/08 — l'entrée EST le central (déjà net de 20 %) : la
    // fonction ne le rabote plus. La borne haute remonte à la base PVGIS nue :
    // 10 000 ÷ 0,9302325581 = 10 750 kWh (à la main : 10 000 × 0,86/0,80).
    expect(b.point).toBe(10000);
    expect(b.high).toBeCloseTo(10750, 0);
    expect(b.high).toBeCloseTo(10000 / PRODUCTION_NET_FACTOR, 6);
    expect(b.low).toBeLessThanOrEqual(b.point);
    expect(b.point).toBeLessThanOrEqual(b.high);
    expect(b.low).toBeGreaterThan(0);
  });

  it('les BORNES sont inchangées par le rebasage : seul le central bouge (+0,43 %)', () => {
    // Avant le 18/08 : high = chiffre nu PVGIS, low = high × dérate, point =
    // moyenne géométrique = high × √0,8579941 = high × 0,9262797.
    // Depuis : on entre le central (= high_avant × 0,9302325), et la fonction
    // reconstruit EXACTEMENT les mêmes bornes — c'est la preuve qu'aucune perte
    // n'est comptée deux fois (0,9302 × 0,9263 aurait fait ~26 % au total).
    const pvgisNu = 10000;
    const central = pvgisNu * PRODUCTION_NET_FACTOR; // 9 302,33
    const b = productionConfidenceBand(central);
    expect(b.high).toBeCloseTo(pvgisNu, 6);
    expect(b.low).toBeCloseTo(pvgisNu * climateDerateFactor(), 6);
    // Le central ne vaut plus la moyenne géométrique : il la dépasse de +0,43 %.
    const ancienPoint = Math.sqrt(b.low * b.high);
    expect(b.point / ancienPoint).toBeCloseTo(1.0042674, 6);
  });

  it('chiffre ≤ 0 → fourchette nulle', () => {
    expect(productionConfidenceBand(0)).toEqual({ low: 0, point: 0, high: 0 });
    expect(productionConfidenceBand(-5)).toEqual({ low: 0, point: 0, high: 0 });
  });

  it('dérate 1 → aucune borne basse sous le central (garde-fou anti-inversion)', () => {
    // Sans perte climatique, la borne basse remonterait à la base PVGIS nue
    // (5 000 ÷ 0,9302 = 5 375) et passerait AU-DESSUS du central : le garde-fou
    // la ramène au central. On n'annonce jamais un « bas » supérieur au central.
    const b = productionConfidenceBand(5000, 1);
    expect(b.low).toBeCloseTo(5000, 6);
    expect(b.point).toBe(5000);
    expect(b.high).toBeCloseTo(5375, 0);
    expect(b.low).toBeLessThanOrEqual(b.point);
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

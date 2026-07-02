// WJ24 — modèle de batterie LFP approfondi (DoD + rendement aller-retour + dégradation +
// tailles réelles + cashflow 25 ans, coût indicatif « à confirmer »). Module PUR : bornes
// physiques (utile ≤ nominal, dégradation décroissante), choix de pack, cashflow monotone.
import { describe, expect, it } from 'vitest';
import {
  LFP_DOD,
  LFP_ROUND_TRIP_EFFICIENCY,
  LFP_ANNUAL_CAPACITY_FADE,
  LFP_PACK_SIZES_KWH,
  chooseLfpPackKwh,
  batteryUsableKwh,
  batteryCashflow,
} from '../src/lib/estimatorBrainV2';

describe('WJ24 — bornes du modèle batterie', () => {
  it('énergie utile ≤ nominal (DoD + rendement < 1)', () => {
    const nominal = 10;
    const usable = batteryUsableKwh(nominal, 1);
    expect(usable).toBeLessThan(nominal);
    expect(usable).toBeCloseTo(nominal * LFP_DOD * LFP_ROUND_TRIP_EFFICIENCY, 6);
  });

  it('dégradation : l’utile décroît strictement d’année en année', () => {
    const y1 = batteryUsableKwh(10, 1);
    const y10 = batteryUsableKwh(10, 10);
    const y25 = batteryUsableKwh(10, 25);
    expect(y10).toBeLessThan(y1);
    expect(y25).toBeLessThan(y10);
    // fade annuel appliqué : y10 = y1 × (1−fade)^9
    expect(y10).toBeCloseTo(y1 * Math.pow(1 - LFP_ANNUAL_CAPACITY_FADE, 9), 6);
  });

  it('nominal ≤ 0 → utile 0', () => {
    expect(batteryUsableKwh(0)).toBe(0);
    expect(batteryUsableKwh(-5)).toBe(0);
  });
});

describe('WJ24 — choix de pack (tailles réelles LFP)', () => {
  it('choisit la plus petite taille ≥ besoin (remonté au nominal via DoD)', () => {
    // besoin utile 8 kWh → nominal ≈ 8/0,9 = 8,9 → pack 10 kWh.
    expect(chooseLfpPackKwh(8)).toBe(10);
    // besoin utile 4 kWh → nominal ≈ 4,4 → pack 5 kWh.
    expect(chooseLfpPackKwh(4)).toBe(5);
  });

  it('besoin au-delà du catalogue → la plus grande taille', () => {
    expect(chooseLfpPackKwh(100)).toBe(LFP_PACK_SIZES_KWH[LFP_PACK_SIZES_KWH.length - 1]);
  });

  it('besoin ≤ 0 → pas de batterie (0)', () => {
    expect(chooseLfpPackKwh(0)).toBe(0);
    expect(chooseLfpPackKwh(-3)).toBe(0);
  });
});

describe('WJ24 — cashflow 25 ans (coût indicatif « à confirmer »)', () => {
  it('produit un horizon complet, coût initial négatif en année 1', () => {
    const cf = batteryCashflow(10, 1.5);
    expect(cf.years.length).toBe(25);
    expect(cf.indicativeCostMad).toBeGreaterThan(0);
    // le cumul démarre sous zéro (on a payé le pack).
    expect(cf.years[0].cumulativeNetMad).toBeLessThan(cf.years[24].cumulativeNetMad);
  });

  it('cumul net monotone croissant (économies positives chaque année)', () => {
    const cf = batteryCashflow(10, 1.5);
    for (let i = 1; i < cf.years.length; i++) {
      expect(cf.years[i].cumulativeNetMad).toBeGreaterThanOrEqual(cf.years[i - 1].cumulativeNetMad);
    }
  });

  it('économies annuelles décroissent (dégradation du pack)', () => {
    const cf = batteryCashflow(10, 1.5);
    expect(cf.years[9].savingsMad).toBeLessThan(cf.years[0].savingsMad);
  });

  it('tarif marginal 0 → aucune économie, jamais amorti', () => {
    const cf = batteryCashflow(10, 0);
    expect(cf.years.every((y) => y.savingsMad === 0)).toBe(true);
    expect(cf.paybackYear).toBeNull();
  });

  it('nominal 0 → coût 0, utile 0', () => {
    const cf = batteryCashflow(0, 1.5);
    expect(cf.indicativeCostMad).toBe(0);
    expect(cf.years.every((y) => y.usableKwh === 0)).toBe(true);
  });
});

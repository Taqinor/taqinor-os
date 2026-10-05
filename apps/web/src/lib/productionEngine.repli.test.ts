// ACAL271 — le repli de production (atelier + /api/roof-estimate) vaut le
// productible du devis : UNE constante (productionEngine.ts), roof.ts la réexporte.
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PRODUCTIBLE_DEVIS,
  FALLBACK_SPECIFIC_YIELD_KWH_PER_KWC,
  FALLBACK_SPECIFIC_YIELD_PVGIS14,
  fallbackPerKwc,
} from './productionEngine';
import { PRODUCTION_NET_FACTOR } from './systemLoss';
import { fallbackAnnualKwh, KWH_PER_KWC_YEAR, KWH_PER_KWC_YEAR_PVGIS14 } from './roof';

describe('repli = productible du devis et roof.ts identique', () => {
  it('productionEngine : 1651 x PRODUCTION_NET_FACTOR (miroir de productible.py:38)', () => {
    expect(DEFAULT_PRODUCTIBLE_DEVIS).toBe(1651);
    expect(FALLBACK_SPECIFIC_YIELD_PVGIS14).toBe(1651);
    expect(FALLBACK_SPECIFIC_YIELD_KWH_PER_KWC).toBeCloseTo(1651 * PRODUCTION_NET_FACTOR, 9);
  });

  it('roof.ts réexporte la même constante (plus de 1600 propre)', () => {
    expect(KWH_PER_KWC_YEAR_PVGIS14).toBe(FALLBACK_SPECIFIC_YIELD_PVGIS14);
    expect(KWH_PER_KWC_YEAR).toBe(FALLBACK_SPECIFIC_YIELD_KWH_PER_KWC);
  });

  it('10 kWc : ~15 357 kWh (plus 14 884) côté site public ET atelier', () => {
    const site = fallbackAnnualKwh(10);
    expect(Math.round(site)).toBe(Math.round(10 * 1651 * PRODUCTION_NET_FACTOR));
    expect(site).toBeGreaterThan(15300);
    expect(site).toBeLessThan(15400);
    const atelier = fallbackPerKwc();
    expect(atelier.annualKwh * 10).toBeCloseTo(site, 3);
  });
});

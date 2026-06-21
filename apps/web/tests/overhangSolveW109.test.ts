// W109 — le débord panneaux (overhangM) traverse le SOLVE (V7 toit plat + V8 toit en
// pente) jusqu'au pavage. On ancre : overhangM=0 → résultat IDENTIQUE octet pour octet
// (rétro-compatible) ; un overhang > 0 ne fait QUE croître la CAPACITÉ géométrique
// (fitCount ≥ sans overhang) ; le PLAFOND besoin (facture) n'est jamais dépassé
// (placedCount ≤ effectiveNeed) ; les économies restent plafonnées (savingsHigh fini,
// monotone avec la conso). Modules PURS, sans DOM, sans réseau.
import { describe, expect, it } from 'vitest';
import { solveLive } from '../src/lib/estimatorBrainV7';
import { solveLivePitched } from '../src/lib/estimatorBrainV8';
import { annualSavingsMad, billToAnnualKwh, tariffForCity } from '../src/lib/estimatorBrainV2';
import { fineGridMatrixV6 } from '../src/lib/estimatorBrainV6';
import { type LngLat } from '../src/lib/roof';

const LAT = 33.59;

function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

describe('W109 — overhang dans le SOLVE TOIT PLAT (V7)', () => {
  const ring = squareRing(16);
  const obstructions: LngLat[][] = [];
  // Facture ÉLEVÉE → besoin grand → fitCount n'est pas plafonné par le besoin (on observe
  // bien la capacité géométrique croître avec l'overhang).
  const BILL_HIGH = 99999;

  it('overhangM=0 est byte-identique au défaut (rétro-compatible)', () => {
    const base = solveLive(ring, LAT, BILL_HIGH, obstructions, {});
    const zero = solveLive(ring, LAT, BILL_HIGH, obstructions, {}, { overhangM: 0 });
    expect(zero.winner.fitCount).toBe(base.winner.fitCount);
    expect(zero.winner.placedCount).toBe(base.winner.placedCount);
    expect(zero.winner.kwc).toBeCloseTo(base.winner.kwc, 9);
    expect(zero.winner.annualKwh).toBeCloseTo(base.winner.annualKwh, 6);
  });

  it('un overhang > 0 FAIT croître la capacité géométrique (plus de panneaux aux rives)', () => {
    const base = solveLive(ring, LAT, BILL_HIGH, obstructions, {}, { overhangM: 0 });
    const over = solveLive(ring, LAT, BILL_HIGH, obstructions, {}, { overhangM: 1.2 });
    // Sur ce toit, le débord loge STRICTEMENT plus de panneaux (capacité, pas le besoin).
    expect(over.winner.fitCount).toBeGreaterThan(base.winner.fitCount);
  });

  it('le plafond BESOIN (facture) n’est jamais dépassé, overhang ou pas', () => {
    const BILL = 1500; // besoin modeste : posé plafonné au besoin
    const need = solveLive(ring, LAT, BILL, obstructions, {}, { overhangM: 0 }).effectiveNeed;
    const over = solveLive(ring, LAT, BILL, obstructions, {}, { overhangM: 2 });
    expect(over.winner.placedCount).toBeLessThanOrEqual(over.effectiveNeed);
    expect(over.effectiveNeed).toBe(need); // l'overhang NE change PAS le cap besoin
  });

  it('les économies restent plafonnées à la facture (savingsHigh fini, ≤ coût évitable)', () => {
    const BILL = 1500;
    const tariff = tariffForCity(undefined);
    const target = billToAnnualKwh(BILL, tariff);
    const over = solveLive(ring, LAT, BILL, obstructions, {}, { overhangM: 2 });
    expect(Number.isFinite(over.winner.savingsHigh)).toBe(true);
    expect(over.winner.savingsHigh).toBeGreaterThanOrEqual(0);
    // PLAFOND HONNÊTE : l'économie est bornée par le coût annuel ÉVITABLE = ce qu'on
    // économiserait en auto-consommant TOUTE la conso (production ≥ conso). overhang ou
    // pas, l'économie affichée ne peut PAS dépasser ce plafond bill-capé.
    const ceiling = annualSavingsMad(target * 10, target, tariff).high; // production >> conso
    expect(over.winner.savingsHigh).toBeLessThanOrEqual(ceiling + 1e-6);
  });
});

describe('W109 — overhang dans le SOLVE TOIT EN PENTE (V8)', () => {
  const ring = squareRing(14);
  const obstructions: LngLat[][] = [];
  const PITCH = 22;
  const FACING = 180; // plein sud
  const BILL_HIGH = 99999;

  it('overhangM=0 est byte-identique au défaut (rétro-compatible)', () => {
    const base = solveLivePitched(ring, LAT, BILL_HIGH, PITCH, FACING, obstructions, {});
    const zero = solveLivePitched(ring, LAT, BILL_HIGH, PITCH, FACING, obstructions, {}, { overhangM: 0 });
    expect(zero.winner.fitCount).toBe(base.winner.fitCount);
    expect(zero.winner.placedCount).toBe(base.winner.placedCount);
    expect(zero.winner.kwc).toBeCloseTo(base.winner.kwc, 9);
  });

  it('un overhang > 0 FAIT croître la capacité géométrique (plus de panneaux aux rives)', () => {
    const base = solveLivePitched(ring, LAT, BILL_HIGH, PITCH, FACING, obstructions, {}, { overhangM: 0 });
    const over = solveLivePitched(ring, LAT, BILL_HIGH, PITCH, FACING, obstructions, {}, { overhangM: 1.2 });
    expect(over.winner.fitCount).toBeGreaterThan(base.winner.fitCount);
  });

  it('le plafond BESOIN n’est pas dépassé et n’est pas modifié par l’overhang', () => {
    const BILL = 1500;
    const need = solveLivePitched(ring, LAT, BILL, PITCH, FACING, obstructions, {}, { overhangM: 0 }).effectiveNeed;
    const over = solveLivePitched(ring, LAT, BILL, PITCH, FACING, obstructions, {}, { overhangM: 2 });
    expect(over.winner.placedCount).toBeLessThanOrEqual(over.effectiveNeed);
    expect(over.effectiveNeed).toBe(need);
  });
});

describe('W109 — overhang dans la MATRICE V6 (toit plat)', () => {
  const ring = squareRing(16);
  it('overhangM=0 → mêmes comptages que le défaut ; overhang > 0 → capacité ≥', () => {
    const base = fineGridMatrixV6(ring, LAT, 99999, []);
    const zero = fineGridMatrixV6(ring, LAT, 99999, [], { overhangM: 0 });
    const over = fineGridMatrixV6(ring, LAT, 99999, [], { overhangM: 1.2 });
    expect(zero.winner.fitCount).toBe(base.winner.fitCount);
    expect(over.winner.fitCount).toBeGreaterThan(base.winner.fitCount);
  });
});

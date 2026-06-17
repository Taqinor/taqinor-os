// Cerveau V8 — src/lib/estimatorBrainV8.ts (preview privé pro-11). L'OPTIMISEUR
// CONTRAINT VIVANT pour TOIT EN PENTE / TUILES : jumeau de V7 (toit plat) avec deux
// différences physiques — PAS d'axe inclinaison (tilt = pente) et orientation fixée à
// « aligné toit » (azimut = face ; plein sud / Est-Ouest impossibles). Axes libres :
// pose (portrait/paysage), marge (garder/pleine rive), cible besoin. Ces tests ancrent :
// l'absence d'axe tilt/orientation, le verrou tenu pendant que le reste se re-résout,
// les verrous cumulatifs + Réinitialiser, le recommandé-par-axe = optimum de l'axe
// libéré, production = posé × kWc × rendement PVGIS (pose 'building') avec posé =
// min(besoin, ce qui tient) et le plafond jamais dépassé, le repli gracieux, et la pose
// affleurante coplanaire INCHANGÉE.
import { describe, expect, it } from 'vitest';
import {
  betterPitched,
  solveLivePitched,
  type PitchedLiveEval,
  type PitchedYieldFn,
} from '../src/lib/estimatorBrainV8';
import { packFlushPlane, flushPlaneYield } from '../src/lib/estimatorBrainV3';
import { pointInPolygon, type LngLat } from '../src/lib/roof';

const LAT = 33.59;
const BILL = 1500;
const PITCH = 30;
const FACING = 180; // sud

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

describe('V8 — comparateur déterministe', () => {
  it('betterPitched : plus d\'énergie posée, puis moins de matériel, marge gardée, portrait', () => {
    const base = {
      layout: 'portrait', margin: 'keep', fitCount: 10, placedCount: 10, kwc: 7.2,
      annualKwh: 11000, pctOfTarget: 100, savingsLow: 1, savingsHigh: 2, perPanelYield: 1528,
      yieldSource: 'pvgis', pack: {} as never, grid: {} as never, layoutLabel: 'portrait',
      marginLabel: 'marge gardée', label: 'x',
    } as unknown as PitchedLiveEval;
    expect(betterPitched({ ...base, annualKwh: 11500 }, base)).toBe(true);
    expect(betterPitched({ ...base, placedCount: 8 }, base)).toBe(true); // énergie égale → moins de panneaux
  });
});

describe('V8 — PAS d\'axe inclinaison, orientation fixée à « aligné toit »', () => {
  it('le résultat impose tilt = pente et azimut = face (jamais optimisés)', () => {
    const res = solveLivePitched(squareRing(16), LAT, BILL, PITCH, FACING, [], {});
    expect(res.pitchDeg).toBe(PITCH);
    expect(res.facingAzimuthDeg).toBe(FACING);
    // les seules valeurs d'axe possibles sont pose × marge (≤ 4 lignes)
    expect(res.rows.length).toBeLessThanOrEqual(4);
    for (const r of res.rows) {
      expect(['portrait', 'landscape']).toContain(r.layout);
      expect(['keep', 'remove']).toContain(r.margin);
    }
  });
});

describe('V8 — un verrou est TENU pendant que le reste se re-résout', () => {
  const ring = squareRing(16);

  it('verrouiller la pose la tient ; la marge reste optimale sous contrainte', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'landscape' });
    expect(res.winner.layout).toBe('landscape');
    for (const margin of ['keep', 'remove'] as const) {
      const probe = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'landscape', margin }).winner;
      expect(probe.annualKwh).toBeLessThanOrEqual(res.winner.annualKwh + 1e-6);
    }
  });

  it('verrouiller la marge la tient', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { margin: 'remove' });
    expect(res.winner.margin).toBe('remove');
  });
});

describe('V8 — verrous cumulatifs + Réinitialiser', () => {
  const ring = squareRing(16);

  it('deux verrous tiennent les deux ; globalWinner = optimum tous-axes-libres', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'landscape', margin: 'remove' });
    expect(res.winner.layout).toBe('landscape');
    expect(res.winner.margin).toBe('remove');
    const reset = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], {});
    expect(res.globalWinner.label).toBe(reset.winner.label);
    expect(res.globalWinner.annualKwh).toBeCloseTo(reset.winner.annualKwh, 6);
  });
});

describe('V8 — « Recommandé » par axe = optimum de l\'axe libéré (autre verrou tenu)', () => {
  const ring = squareRing(16);

  it('verrou pose sous-optimale → la marge recommandée tient compte de la pose verrouillée', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'landscape' });
    const freedMargin = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'landscape' });
    expect(res.recommended.margin).toBe(freedMargin.winner.margin);
  });

  it('le besoin recommandé est la cible dérivée de la facture, verrou besoin respecté', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { need: 4 });
    expect(res.recommended.need).toBe(res.neededPanels);
    expect(res.effectiveNeed).toBe(4);
  });
});

describe('V8 — production PVGIS (pose building), plafond besoin, repli gracieux', () => {
  const ring = squareRing(16);

  it('production = posé × kWc × rendement ; le yieldFn (building) est la source de vérité', () => {
    const seen: { pitch: number; facing: number }[] = [];
    const fn: PitchedYieldFn = (pitch, facing) => {
      seen.push({ pitch, facing });
      return 1500;
    };
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'portrait', margin: 'keep' }, { yieldFn: fn });
    const w = res.winner;
    expect(w.yieldSource).toBe('pvgis');
    expect(seen.some((s) => s.pitch === PITCH && s.facing === FACING)).toBe(true);
    expect(w.annualKwh).toBeCloseTo(w.kwc * 1500, 6);
  });

  it('posé = min(besoin, ce qui tient) — plafond jamais dépassé', () => {
    const big = solveLivePitched(squareRing(28), LAT, BILL, PITCH, FACING, [], {});
    expect(big.winner.placedCount).toBeLessThanOrEqual(big.effectiveNeed);
    expect(big.winner.placedCount).toBeLessThanOrEqual(big.winner.fitCount);
    const small = solveLivePitched(squareRing(7), LAT, 3000, PITCH, FACING, [], {});
    expect(small.winner.placedCount).toBe(small.winner.fitCount);
    expect(small.roofLimited).toBe(true);
  });

  it('repli gracieux : yieldFn=null → table flush committée, source « estimate »', () => {
    const withNull = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], {}, { yieldFn: () => null });
    const tableOnly = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], {});
    expect(withNull.winner.yieldSource).toBe('estimate');
    expect(Math.round(withNull.winner.annualKwh)).toBe(Math.round(tableOnly.winner.annualKwh));
    // la table flush = specificYield(lat, pente, offSouth(face)) via flushPlaneYield
    const expectedYield = flushPlaneYield(LAT, PITCH, FACING);
    expect(tableOnly.winner.perPanelYield).toBeCloseTo(expectedYield, 6);
  });

  it('pan orienté NORD → aucun panneau posé (honnêteté), signalé northFacing', () => {
    const res = solveLivePitched(ring, LAT, BILL, PITCH, 0 /* nord */, [], {});
    expect(res.northFacing).toBe(true);
    expect(res.winner.placedCount).toBe(0);
    expect(res.winner.annualKwh).toBe(0);
  });
});

describe('V8 — la pose AFFLEURANTE coplanaire est INCHANGÉE (géométrie V3 préservée)', () => {
  it('le pavage reste celui de packFlushPlane (chaque panneau dans le polygone tracé)', () => {
    const ring = squareRing(16);
    const res = solveLivePitched(ring, LAT, BILL, PITCH, FACING, [], { layout: 'portrait', margin: 'remove' });
    const w = res.winner;
    // le pack du gagnant EST un packFlushPlane à la même pente/face/marge
    expect(w.pack.pitchDeg).toBe(PITCH);
    expect(w.pack.facingAzimuthDeg).toBe(FACING);
    const ref = packFlushPlane({ ring, pitchDeg: PITCH, facingAzimuthDeg: FACING }, { setbackM: 0 });
    expect(w.grid.count).toBe(ref.portrait.count);
    // chaque centre de panneau reste DANS le polygone tracé (pavage flush V3 inchangé)
    for (const p of w.grid.panels) {
      expect(pointInPolygon([p.cx, p.cy], w.pack.ringENU)).toBe(true);
    }
  });
});

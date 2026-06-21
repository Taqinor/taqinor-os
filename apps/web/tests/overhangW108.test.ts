/**
 * W108 — débord autorisé des panneaux au-delà de la rive (rails sur le toit, le
 * panneau déborde). Garde-fous PURS sur les deux calepineurs :
 *  - toit plat  : `packConfig` / `packCells` (estimatorBrainV2.ts)
 *  - toit pente : `packFlushPlane` / `packFlushCells` (estimatorBrainV3.ts)
 *
 * On prouve : (1) overhangM=0 = BYTE-IDENTIQUE à aujourd'hui (compte, kWc,
 * empreinte, usableAreaM2, et le tableau de panneaux au pixel près) ; (2) un
 * débord>0 ne fait QUE croître le compte, de façon monotone et BORNÉE par la
 * place géométrique réellement gagnée ; (3) la borne d'honnêteté
 * « Σ empreintes ≤ utile » tient toujours (utile élargie de l'anneau de débord).
 */
import { describe, expect, it } from 'vitest';
import { packConfig, type ConfigFamily } from '../src/lib/estimatorBrainV2';
import { packFlushPlane } from '../src/lib/estimatorBrainV3';
import { geodesicPerimeterM, type LngLat } from '../src/lib/roof';

const LAT = 33.57; // Casablanca
const LNG0 = -7.6;
const M_PER_DEG_LAT = 111_320;
const M_PER_DEG_LNG = M_PER_DEG_LAT * Math.cos(LAT * (Math.PI / 180));

/** Rectangle wM (E-O) × hM (N-S) centré sur (LNG0, LAT), anneau lng/lat fermé. */
function rect(wM: number, hM: number): LngLat[] {
  const dlng = wM / 2 / M_PER_DEG_LNG;
  const dlat = hM / 2 / M_PER_DEG_LAT;
  return [
    [LNG0 - dlng, LAT - dlat],
    [LNG0 + dlng, LAT - dlat],
    [LNG0 + dlng, LAT + dlat],
    [LNG0 - dlng, LAT + dlat],
  ];
}

const FOOTPRINT_EPS = 0.5; // m² — tolérance flottante sur la borne d'honnêteté

describe('W108 — toit PLAT (packConfig)', () => {
  const ring = rect(20, 16);
  const families: ConfigFamily[] = ['south', 'eastwest'];

  it('overhangM=0 est byte-identique à l’option absente (compte, kWc, empreinte, utile, panneaux)', () => {
    for (const family of families) {
      for (const tiltDeg of [10, 15, 20]) {
        const base = packConfig(ring, LAT, { family, tiltDeg });
        const zero = packConfig(ring, LAT, { family, tiltDeg, overhangM: 0 });
        expect(zero.usableAreaM2).toBe(base.usableAreaM2);
        expect(zero.best.count).toBe(base.best.count);
        expect(zero.best.kwc).toBe(base.best.kwc);
        expect(zero.best.footprintPerPanelM2).toBe(base.best.footprintPerPanelM2);
        expect(zero.portrait.panels).toEqual(base.portrait.panels);
        expect(zero.landscape.panels).toEqual(base.landscape.panels);
      }
    }
  });

  it('un débord>0 ne fait QUE croître le compte, de façon monotone', () => {
    for (const family of families) {
      const c0 = packConfig(ring, LAT, { family, tiltDeg: 15, overhangM: 0 }).best.count;
      const c2 = packConfig(ring, LAT, { family, tiltDeg: 15, overhangM: 0.2 }).best.count;
      const c5 = packConfig(ring, LAT, { family, tiltDeg: 15, overhangM: 0.5 }).best.count;
      expect(c2).toBeGreaterThanOrEqual(c0);
      expect(c5).toBeGreaterThanOrEqual(c2);
    }
  });

  it('la borne « Σ empreintes ≤ utile » tient pour tout débord (0 → grand)', () => {
    for (const family of families) {
      for (const overhangM of [0, 0.2, 0.5, 1, 3]) {
        const pack = packConfig(ring, LAT, { family, tiltDeg: 15, overhangM });
        const sumFootprint = pack.best.count * pack.best.footprintPerPanelM2;
        expect(sumFootprint).toBeLessThanOrEqual(pack.usableAreaM2 + FOOTPRINT_EPS);
      }
    }
  });

  it('usableAreaM2 s’élargit exactement de l’anneau de Minkowski (périmètre·r + π·r²)', () => {
    const base = packConfig(ring, LAT, { family: 'south', tiltDeg: 15, overhangM: 0 });
    const oh = 0.4;
    const grown = packConfig(ring, LAT, { family: 'south', tiltDeg: 15, overhangM: oh });
    const expectedRing = geodesicPerimeterM(ring) * oh + Math.PI * oh * oh;
    expect(grown.usableAreaM2 - base.usableAreaM2).toBeCloseTo(expectedRing, 2);
  });

  it('un débord énorme reste BORNÉ par la géométrie (jamais une capacité inventée)', () => {
    const pack = packConfig(ring, LAT, { family: 'south', tiltDeg: 15, overhangM: 5 });
    expect(Number.isFinite(pack.best.count)).toBe(true);
    const sumFootprint = pack.best.count * pack.best.footprintPerPanelM2;
    expect(sumFootprint).toBeLessThanOrEqual(pack.usableAreaM2 + FOOTPRINT_EPS);
  });
});

describe('W108 — toit EN PENTE (packFlushPlane)', () => {
  const ring = rect(18, 14);
  const plane = { ring, pitchDeg: 22, facingAzimuthDeg: 180 }; // plein sud → pas « nord »

  it('overhangM=0 est byte-identique à l’option absente', () => {
    const base = packFlushPlane(plane, {});
    const zero = packFlushPlane(plane, { overhangM: 0 });
    expect(zero.northFacing).toBe(false);
    expect(zero.usableAreaM2).toBe(base.usableAreaM2);
    expect(zero.best.count).toBe(base.best.count);
    expect(zero.best.kwc).toBe(base.best.kwc);
    expect(zero.best.footprintPerPanelM2).toBe(base.best.footprintPerPanelM2);
    expect(zero.portrait.panels).toEqual(base.portrait.panels);
    expect(zero.landscape.panels).toEqual(base.landscape.panels);
  });

  it('un débord>0 croît de façon monotone et reste sous la borne d’honnêteté', () => {
    const c0 = packFlushPlane(plane, { overhangM: 0 }).best.count;
    const c3 = packFlushPlane(plane, { overhangM: 0.3 }).best.count;
    const c6 = packFlushPlane(plane, { overhangM: 0.6 }).best.count;
    expect(c3).toBeGreaterThanOrEqual(c0);
    expect(c6).toBeGreaterThanOrEqual(c3);
    for (const overhangM of [0, 0.3, 0.6, 2]) {
      const pack = packFlushPlane(plane, { overhangM });
      const sumFootprint = pack.best.count * pack.best.footprintPerPanelM2;
      expect(sumFootprint).toBeLessThanOrEqual(pack.usableAreaM2 + FOOTPRINT_EPS);
    }
  });
});

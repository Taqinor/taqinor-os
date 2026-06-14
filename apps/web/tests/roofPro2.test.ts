// Calepinage HAUTE FIDÉLITÉ (vrais panneaux 720 W + espacement par géométrie
// solaire) — src/lib/roofPro2.ts. On vérifie : vrai panneau (kWc = n × 0,72),
// azimut réel, espacement inter-rangées dérivé de la latitude (plus la latitude
// est haute, plus les rangées sont écartées), panneaux dans le tracé, pose
// affleurante plus dense que la pose inclinée espacée.
import { describe, expect, it } from 'vitest';
import {
  layoutProRows2,
  orientationToAzimuthDeg,
  designSunElevationDeg,
  PANEL2_WATT,
} from '../src/lib/roofPro2';
import { pointInPolygon, geodesicAreaM2, type LngLat } from '../src/lib/roof';

function squareRing(side: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

describe('orientationToAzimuthDeg — azimut réel', () => {
  it('mappe les orientations FR vers l’azimut (Sud = 180°)', () => {
    expect(orientationToAzimuthDeg('sud')).toBe(180);
    expect(orientationToAzimuthDeg('est')).toBe(90);
    expect(orientationToAzimuthDeg('ouest')).toBe(270);
    expect(orientationToAzimuthDeg('nord')).toBe(0);
    expect(orientationToAzimuthDeg('sud-est')).toBe(135);
    expect(orientationToAzimuthDeg('inconnu')).toBe(180); // défaut plein sud
  });
});

describe('designSunElevationDeg — élévation de design (solstice)', () => {
  it('≈ 33° à Casablanca (lat 33,5°)', () => {
    expect(designSunElevationDeg(33.5)).toBeCloseTo(33.06, 1);
  });
  it('plus la latitude est haute, plus l’élévation de design est basse', () => {
    expect(designSunElevationDeg(45)).toBeLessThan(designSunElevationDeg(20));
  });
});

describe('layoutProRows2 — vrais panneaux 720 W, espacés par le soleil', () => {
  it('pose des panneaux et calcule kWc = nombre × 0,72', () => {
    const ring = squareRing(28);
    const layout = layoutProRows2(ring, 'sud', 33.5);
    expect(layout.count).toBeGreaterThan(10);
    expect(layout.kwc).toBeCloseTo((layout.count * PANEL2_WATT) / 1000, 6);
    expect(layout.azimuthDeg).toBe(180);
    expect(layout.areaM2).toBeCloseTo(geodesicAreaM2(ring), 6);
    expect(layout.dims.alongRow).toBeCloseTo(2.384, 3);
    expect(layout.dims.slope).toBeCloseTo(1.303, 3);
  });

  it('le pas de rangée croît avec la latitude (ombres plus longues → moins de rangées)', () => {
    const ring = squareRing(28);
    const low = layoutProRows2(ring, 'sud', 20);
    const high = layoutProRows2(ring, 'sud', 50);
    expect(high.rowPitchM).toBeGreaterThan(low.rowPitchM);
    expect(high.count).toBeLessThanOrEqual(low.count);
  });

  it('tous les panneaux sont à l’intérieur du tracé', () => {
    const ring = squareRing(28);
    const layout = layoutProRows2(ring, 'sud', 33.5);
    for (const p of layout.panels) {
      expect(pointInPolygon([p.cx, p.cy], layout.ringENU)).toBe(true);
    }
  });

  it('le pas inclut bien l’ombre solaire (pas > simple empreinte)', () => {
    const ring = squareRing(28);
    const layout = layoutProRows2(ring, 'sud', 33.5);
    expect(layout.rowPitchM).toBeGreaterThan(layout.dims.depthFootprint);
  });

  it('pose affleurante (toit en pente) plus dense que l’inclinée espacée', () => {
    const ring = squareRing(28);
    const tilted = layoutProRows2(ring, 'sud', 33.5);
    const flush = layoutProRows2(ring, 'sud', 33.5, { tiltDeg: 18, flush: true });
    expect(flush.rowPitchM).toBeLessThan(tilted.rowPitchM);
    expect(flush.count).toBeGreaterThanOrEqual(tilted.count);
  });

  it('un tracé trop petit ou invalide → zéro panneau', () => {
    expect(layoutProRows2(squareRing(2), 'sud', 33.5).count).toBe(0);
    expect(layoutProRows2([[0, 0], [1, 1]] as LngLat[], 'sud', 33.5).count).toBe(0);
  });
});

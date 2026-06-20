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
  sunDirection,
  WINTER_SOLSTICE_DAY,
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

describe('sunDirection — VRAIE position solaire (W87)', () => {
  it('midi du solstice d’hiver → soleil plein SUD (azimut ≈ 180°)', () => {
    const s = sunDirection(33.5, WINTER_SOLSTICE_DAY, 12);
    expect(s.azimuthDeg).toBeCloseTo(180, 0);
  });

  it('au midi du solstice d’hiver, l’élévation rejoint l’élévation de DESIGN (anti-ombrage)', () => {
    // C'est le pire cas qui pilote l'espacement des rangées : à cet angle, le soleil de la
    // scène et le soleil de design coïncident → les rangées espacées se dégagent.
    const s = sunDirection(33.5, WINTER_SOLSTICE_DAY, 12);
    expect(s.elevationDeg).toBeCloseTo(designSunElevationDeg(33.5), 1);
  });

  it('le matin le soleil est à l’EST (azimut < 180°), l’après-midi à l’OUEST (> 180°)', () => {
    const morning = sunDirection(33.5, WINTER_SOLSTICE_DAY, 9);
    const afternoon = sunDirection(33.5, WINTER_SOLSTICE_DAY, 15);
    expect(morning.azimuthDeg).toBeLessThan(180);
    expect(afternoon.azimuthDeg).toBeGreaterThan(180);
    // symétrie autour du midi solaire
    expect(morning.elevationDeg).toBeCloseTo(afternoon.elevationDeg, 3);
  });

  it('le soleil est plus HAUT à midi en été qu’en hiver', () => {
    const summer = sunDirection(33.5, 172, 12); // ~21 juin
    const winter = sunDirection(33.5, WINTER_SOLSTICE_DAY, 12);
    expect(summer.elevationDeg).toBeGreaterThan(winter.elevationDeg);
  });

  it('le soleil est sous l’horizon (élévation < 0) en pleine nuit', () => {
    const night = sunDirection(33.5, WINTER_SOLSTICE_DAY, 0);
    expect(night.elevationDeg).toBeLessThan(0);
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

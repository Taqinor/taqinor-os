// WJ21 — carte d'accès solaire (heatmap d'irradiance) : accès solaire relatif d'un point
// = part RÉELLE de l'irradiation annuelle reçue (obstructions retirées du soleil direct,
// diffus conservé), pondérée par les vrais profils PVGIS. Astronomie pure, aucune API,
// aucun chiffre inventé — même modèle que le dérate de production, évalué par point. Les
// couleurs de la heatmap sont mappées à ces vraies valeurs (pas des teintes arbitraires).
import { describe, expect, it } from 'vitest';
import {
  pointSolarAccess,
  cellsSolarAccess,
  solarAccessColorRGB,
  DIFFUSE_FRACTION_WHEN_SHADED,
  type ShadeObstructionENU,
} from '../src/lib/shadingEngine';
import { fallbackPerKwc } from '../src/lib/productionEngine';

const CASA_LAT = 33.57;
const prod = fallbackPerKwc();

describe('WJ21 — accès solaire par point (astronomie pure, pondérée PVGIS)', () => {
  it('aucune obstruction → accès plein (1) partout', () => {
    expect(pointSolarAccess(CASA_LAT, [], prod, 0, 0)).toBe(1);
    expect(pointSolarAccess(CASA_LAT, [], prod, 5, -3)).toBe(1);
  });

  it('une obstruction haute juste au sud abaisse l’accès sous 1 mais jamais sous le diffus', () => {
    // Mur haut de 10 m à 2 m au sud du point (côté équateur = plein sur la course solaire).
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -2, effHeightM: 10, halfWidthM: 4 }];
    const a = pointSolarAccess(CASA_LAT, obs, prod, 0, 0);
    expect(a).toBeGreaterThan(0);
    expect(a).toBeLessThan(1); // vraiment ombré
    // borne physique : on ne perd jamais le diffus → accès ≥ fraction diffuse.
    expect(a).toBeGreaterThanOrEqual(DIFFUSE_FRACTION_WHEN_SHADED - 1e-9);
  });

  it('un point plus éloigné de l’obstruction reçoit plus de soleil (monotonie physique)', () => {
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -2, effHeightM: 10, halfWidthM: 4 }];
    const near = pointSolarAccess(CASA_LAT, obs, prod, 0, 0); // pied du mur
    const far = pointSolarAccess(CASA_LAT, obs, prod, 0, 20); // loin au nord du mur
    expect(far).toBeGreaterThanOrEqual(near);
  });

  it('production nulle → accès 1 (aucun dérate inventé)', () => {
    const zeroProd = { ...prod, monthlyKwh: new Array(12).fill(0), annualKwh: 0 };
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -2, effHeightM: 10, halfWidthM: 4 }];
    expect(pointSolarAccess(CASA_LAT, obs, zeroProd, 0, 0)).toBe(1);
  });

  it('cellsSolarAccess : un tableau aligné, valeurs dans [diffus;1]', () => {
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -2, effHeightM: 8, halfWidthM: 3 }];
    const pts = [
      { x: 0, y: 0 },
      { x: 0, y: 10 },
      { x: 30, y: 30 },
    ];
    const acc = cellsSolarAccess(CASA_LAT, obs, prod, pts);
    expect(acc.length).toBe(3);
    for (const a of acc) {
      expect(a).toBeGreaterThanOrEqual(DIFFUSE_FRACTION_WHEN_SHADED - 1e-9);
      expect(a).toBeLessThanOrEqual(1 + 1e-9);
    }
  });
});

describe('WJ21 — couleur mappée à la vraie valeur d’accès', () => {
  it('accès plein (1) → vert franc ; nul (0) → rouge franc', () => {
    const full = solarAccessColorRGB(1);
    expect(full.g).toBeCloseTo(1, 6);
    expect(full.r).toBeCloseTo(0, 6);
    const none = solarAccessColorRGB(0);
    expect(none.r).toBeCloseTo(1, 6);
    expect(none.g).toBeCloseTo(0, 6);
  });

  it('milieu (0,5) → ambre (rouge + vert)', () => {
    const mid = solarAccessColorRGB(0.5);
    expect(mid.r).toBeCloseTo(1, 6);
    expect(mid.g).toBeCloseTo(1, 6);
    expect(mid.b).toBe(0);
  });

  it('mapping monotone : plus d’accès → plus de vert, moins de rouge', () => {
    const lo = solarAccessColorRGB(0.3);
    const hi = solarAccessColorRGB(0.8);
    expect(hi.g).toBeGreaterThan(lo.g);
    expect(hi.r).toBeLessThan(lo.r);
  });

  it('borne les entrées hors [0;1]', () => {
    expect(solarAccessColorRGB(2).g).toBeCloseTo(1, 6);
    expect(solarAccessColorRGB(-1).r).toBeCloseTo(1, 6);
    expect(solarAccessColorRGB(NaN).g).toBeCloseTo(1, 6); // NaN → traité comme plein (1)
  });
});

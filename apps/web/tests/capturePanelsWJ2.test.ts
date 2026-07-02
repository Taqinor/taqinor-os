// WJ2 — « Voir les panneaux sur votre toit » à la capture (mon-toit.astro).
// Logique PURE : construire un RoofLayout illustratif à un seul pan depuis un
// contour tracé par le visiteur (captureBoot.ts onCaptureChange, [lat,lng])
// + le kWc de l'estimation instantanée WJ1. Aucun DOM, aucun Three.js — cette
// fonction est ensuite passée telle quelle à buildViewerModel (WJ25) + le
// viewer en lecture seule (WJ27), donc réutilise 100 % du rendu existant.
import { describe, expect, it } from 'vitest';
import { capturePreviewLayout, buildViewerModel, CAPTURE_PANEL_WATT } from '../src/lib/proposition';

// Petit carré ~10 m × 10 m autour de Casablanca (lat, lng — format onCaptureChange).
const LAT0 = 33.5;
const LNG0 = -7.6;
const DEG2M = 111_320;
const COS = Math.cos((LAT0 * Math.PI) / 180);
/** Sommet [lat,lng] à (x,y) mètres du centre — même convention que le contour capturé. */
function ll(xM: number, yM: number): [number, number] {
  return [LAT0 + yM / DEG2M, LNG0 + xM / (DEG2M * COS)];
}
const SQUARE_OUTLINE: Array<[number, number]> = [ll(-5, -5), ll(5, -5), ll(5, 5), ll(-5, 5)];

describe('WJ2 — capturePreviewLayout : construction du RoofLayout illustratif', () => {
  it('renvoie null sans contour (moins de 3 sommets)', () => {
    expect(capturePreviewLayout([], 5)).toBeNull();
    expect(capturePreviewLayout([ll(0, 0), ll(1, 1)], 5)).toBeNull();
  });

  it('renvoie null sans kWc (estimation indisponible)', () => {
    expect(capturePreviewLayout(SQUARE_OUTLINE, null)).toBeNull();
    expect(capturePreviewLayout(SQUARE_OUTLINE, 0)).toBeNull();
    expect(capturePreviewLayout(SQUARE_OUTLINE, -3)).toBeNull();
    expect(capturePreviewLayout(SQUARE_OUTLINE, NaN)).toBeNull();
  });

  it('construit un layout à un seul pan plat, plein sud illustratif', () => {
    const layout = capturePreviewLayout(SQUARE_OUTLINE, 5);
    expect(layout).not.toBeNull();
    expect(layout!.zones).toHaveLength(1);
    const z = layout!.zones[0];
    expect(z.roofType).toBe('flat');
    expect(z.pitchDeg).toBe(0);
    expect(z.facingAzimuthDeg).toBeGreaterThan(90);
    expect(z.facingAzimuthDeg).toBeLessThan(270); // orienté sud, pas nord
    expect(z.obstacles).toHaveLength(0);
  });

  it('convertit [lat,lng] (contour capturé) en [lng,lat] (RoofLayoutZone attendu)', () => {
    const layout = capturePreviewLayout(SQUARE_OUTLINE, 5)!;
    const v = layout.zones[0].vertices;
    // Le premier sommet capturé est ll(-5,-5) = [lat, lng] ; le layout doit le
    // stocker en [lng, lat] (même invariant que parseRoofLayout / le backend).
    expect(v[0][0]).toBeCloseTo(SQUARE_OUTLINE[0][1], 6); // lng
    expect(v[0][1]).toBeCloseTo(SQUARE_OUTLINE[0][0], 6); // lat
  });

  it('le nombre de panneaux dérive du MÊME calcul Wc que le reste du site (jamais inventé)', () => {
    const kwc = 5;
    const layout = capturePreviewLayout(SQUARE_OUTLINE, kwc)!;
    const expected = Math.max(1, Math.ceil((kwc * 1000) / CAPTURE_PANEL_WATT));
    expect(layout.zones[0].neededPanels).toBe(expected);
  });

  it('un kWc plus grand demande plus de panneaux (monotone)', () => {
    const small = capturePreviewLayout(SQUARE_OUTLINE, 3)!;
    const big = capturePreviewLayout(SQUARE_OUTLINE, 9)!;
    expect(big.zones[0].neededPanels).toBeGreaterThan(small.zones[0].neededPanels);
  });

  it('ignore les points malformés dans le contour sans jeter', () => {
    const dirty: Array<[number, number]> = [
      ...SQUARE_OUTLINE,
      [NaN, 1] as [number, number],
      [1, Infinity] as [number, number],
    ];
    const layout = capturePreviewLayout(dirty, 4);
    expect(layout).not.toBeNull();
    expect(layout!.zones[0].vertices).toHaveLength(SQUARE_OUTLINE.length);
  });

  it('reste consommable tel quel par buildViewerModel (WJ25) — même pipeline que la proposition', () => {
    const layout = capturePreviewLayout(SQUARE_OUTLINE, 5);
    const model = buildViewerModel(layout);
    expect(model).not.toBeNull();
    expect(model!.zones).toHaveLength(1);
    expect(model!.totalPanels).toBeGreaterThan(0);
    expect(model!.radiusM).toBeGreaterThan(0);
  });
});

// L-MAP (fondateur 26/08/2026 : « i want it visible on the map in the 3D
// layouter ») — `referenceContourRing` (roofPro11/prefill.ts) est la fonction
// PURE que `roof-tool-pro11.ts` appelle pour transformer le contour ORIGINAL
// du client (`opts.referenceContour`, `[lat, lng] × n`) en anneau `[lng, lat]`
// prêt pour la source GeoJSON du calque de référence géo-référencé. MÊME
// validation que `hydrateFromLead` (≥ 3 sommets finis) — jamais redéfinie.
import { describe, expect, it } from 'vitest';
import { referenceContourRing } from '../src/scripts/roofPro11/prefill';

// Carré ≈ 20 m à Casablanca, MÊME contour que TraceToitClient/traceToit.test.mjs
// côté ERP (frontend/src/features/crm/workspace/traceToit.test.mjs) — la fixture
// partagée par les deux couches (fiche lead + calque du calepinage).
const CONTOUR: Array<[number, number]> = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
];

describe('referenceContourRing', () => {
  it('convertit [lat, lng] × n en [lng, lat] × n, MÊME convention que hydrateFromLead', () => {
    const ring = referenceContourRing(CONTOUR);
    expect(ring).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);
  });

  it('null sans contour exploitable — jamais un anneau dégénéré', () => {
    expect(referenceContourRing(null)).toBeNull();
    expect(referenceContourRing(undefined)).toBeNull();
    expect(referenceContourRing([])).toBeNull();
    expect(referenceContourRing([[33.589, -7.603], [33.589, -7.602784]])).toBeNull();
  });

  it('écarte les points non finis, refuse si moins de 3 restent valides', () => {
    const avecUnPointInvalide: Array<[number, number]> = [
      [33.589, -7.603],
      [Number.NaN, -7.602784],
      [33.58918, -7.602784],
      [33.58918, -7.603],
    ];
    const ring = referenceContourRing(avecUnPointInvalide);
    expect(ring).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);
  });
});

// CAL56 — préréts de forme de toiture (2/4 pans, appentis, plat) : géométrie PURE qui
// GÉNÈRE les pans depuis un contour fermé + une pente saisie, au lieu du choix binaire
// plat/pente par zone. Testé hors DOM/Three (pure geometry in, geometry out).
import { describe, expect, it } from 'vitest';
import { generateRoofShapePans, type RoofShapePan } from './scene3d';
import { buildAreasFromShape } from './zones';
import { geodesicAreaM2, type LngLat } from '../../lib/roof';

/** Contour RECTANGULAIRE (même convention que ctx.vertices : anneau ouvert, sans point de
 *  fermeture dupliqué), côtés widthM (E-O) × depthM (N-S), centré sur (lng0, lat0). */
function rectRing(widthM: number, depthM: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = depthM / 2 / 111320;
  const dLng = widthM / 2 / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng, lat0 - dLat],
    [lng0 + dLng, lat0 - dLat],
    [lng0 + dLng, lat0 + dLat],
    [lng0 - dLng, lat0 + dLat],
  ];
}

const sumAreaM2 = (pans: RoofShapePan[]): number => pans.reduce((s, p) => s + geodesicAreaM2(p.vertices), 0);

describe('CAL56 — generateRoofShapePans', () => {
  it('contour < 3 sommets → aucun pan', () => {
    expect(generateRoofShapePans([[0, 0], [1, 1]], 'hip')).toEqual([]);
  });

  it('plat : un seul pan = le contour entier', () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'flat');
    expect(pans).toHaveLength(1);
    expect(pans[0].vertices).toEqual(ring);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 3);
  });

  it('appentis : un seul pan, azimut = perpendiculaire au grand côté', () => {
    const ring = rectRing(10, 6); // grand côté E-O → face nord/sud
    const pans = generateRoofShapePans(ring, 'shed');
    expect(pans).toHaveLength(1);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 3);
    // La face est perpendiculaire au grand côté (E-O) → un azimut proche de 0°/180° (± petit écart).
    const az = pans[0].facingAzimuthDeg;
    const nearNorthOrSouth = Math.min(Math.abs(az - 0), Math.abs(az - 180), Math.abs(az - 360));
    expect(nearNorthOrSouth).toBeLessThan(5);
  });

  it('4 pans (croupe) : la somme des surfaces égale EXACTEMENT la surface au sol projetée', () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    expect(pans).toHaveLength(4); // un pan par arête du contour à 4 sommets
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
    // Chaque pan est un triangle cohérent (3 sommets).
    for (const p of pans) expect(p.vertices).toHaveLength(3);
  });

  it('2 pans (gable) : deux pans qui se font face, faîtière centrale — aire conservée', () => {
    const ring = rectRing(10, 6);
    const pans = generateRoofShapePans(ring, 'gable');
    expect(pans).toHaveLength(2);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
    // Les deux pans se font face (azimuts opposés à ~180° l'un de l'autre).
    const diff = Math.abs(pans[0].facingAzimuthDeg - pans[1].facingAzimuthDeg);
    const opposed = Math.min(diff, 360 - diff);
    expect(opposed).toBeGreaterThan(170);
  });

  it('un contour carré redécoupé en 4 pans reste cohérent (surfaces positives, aucun pan dégénéré)', () => {
    const ring = rectRing(6, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    for (const p of pans) expect(geodesicAreaM2(p.vertices)).toBeGreaterThan(0);
    expect(sumAreaM2(pans)).toBeCloseTo(geodesicAreaM2(ring), 2);
  });
});

describe('CAL56 — buildAreasFromShape (zones.ts)', () => {
  it("traduit chaque pan en AreaRecord — 'flat' → roofType plat, sinon pente saisie inchangée", () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'hip');
    let n = 0;
    const areas = buildAreasFromShape(pans, 'hip', 30, () => `a${n++}`);
    expect(areas).toHaveLength(4);
    expect(new Set(areas.map((a) => a.id)).size).toBe(4); // ids distincts
    for (const a of areas) {
      expect(a.roofType).toBe('pitched');
      expect(a.pitchDeg).toBe(30); // jamais réinventée — celle saisie par l'utilisateur
      expect(a.result).toBeNull();
      expect(a.neededAuto).toBe(true);
    }
  });

  it("préré 'flat' → roofType flat pour chaque pan (ici un seul)", () => {
    const ring = rectRing(8, 6);
    const pans = generateRoofShapePans(ring, 'flat');
    const areas = buildAreasFromShape(pans, 'flat', 0, () => 'z0');
    expect(areas).toHaveLength(1);
    expect(areas[0].roofType).toBe('flat');
  });
});

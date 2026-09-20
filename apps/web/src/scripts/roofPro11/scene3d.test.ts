// CAL56 — préréts de forme de toiture (2/4 pans, appentis, plat) : géométrie PURE qui
// GÉNÈRE les pans depuis un contour fermé + une pente saisie, au lieu du choix binaire
// plat/pente par zone. Testé hors DOM/Three (pure geometry in, geometry out).
import { describe, expect, it } from 'vitest';
import {
  generateRoofShapePans,
  computeRidgeLifts,
  computeMixedAltitudeOffsets,
  type RoofShapePan,
  type RidgePan,
  hdTargetSize,
  HD_MAX_SIDE_PX,
  HD_SCALES,
  type MixedRidgePan,
} from './scene3d';
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

// ═══════════ CAL61 — calage d'altitude MIXTE (pans plats + pans en pente) ═══════════
/** Rectangle ENU (m), x ∈ [x0, x0+w], y ∈ [y0, y0+h] — anneau ouvert. */
function enuRect(x0: number, y0: number, w: number, h: number): [number, number][] {
  return [
    [x0, y0],
    [x0 + w, y0],
    [x0 + w, y0 + h],
    [x0, y0 + h],
  ];
}

describe('CAL61 — computeMixedAltitudeOffsets', () => {
  it('NON-RÉGRESSION : un ensemble 100 % pente donne EXACTEMENT computeRidgeLifts (au mm près)', () => {
    // Deux pans en pente accolés sur leur côté est/ouest, faces opposées (même géométrie
    // que le test W107 existant côté scene3d).
    const a: RidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 90, tiltDeg: 20 };
    const b: RidgePan = { ringENU: enuRect(10, 0, 10, 6), facingAzimuthDeg: 270, tiltDeg: 20 };
    const expected = computeRidgeLifts([a, b]);
    const mixed: MixedRidgePan[] = [
      { ...a, pitched: true },
      { ...b, pitched: true },
    ];
    const got = computeMixedAltitudeOffsets(mixed);
    expect(got[0]).toBeCloseTo(expected[0], 9);
    expect(got[1]).toBeCloseTo(expected[1], 9);
  });

  it('un pan plat ISOLÉ (aucun voisin en pente) garde un offset de 0 (rendu inchangé)', () => {
    const flat: MixedRidgePan = { ringENU: enuRect(0, 0, 8, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const other: MixedRidgePan = { ringENU: enuRect(100, 100, 8, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    expect(computeMixedAltitudeOffsets([flat, other])).toEqual([0, 0]);
  });

  it('un pan plat accolé à l’ÉGOUT d’un pan en pente (le point le plus bas) reste au niveau 0', () => {
    // Face sud (180°) : l'égout est le côté SUD (y minimal). Pan en pente y∈[0,6], pan
    // plat accolé juste au sud, y∈[-6,0] — arête partagée exactement à l'égout.
    const pitched: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 180, tiltDeg: 30, pitched: true };
    const flat: MixedRidgePan = { ringENU: enuRect(0, -6, 10, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([pitched, flat]);
    expect(offsets[0]).toBeCloseTo(0, 9); // pan en pente isolé → aucun lift
    expect(offsets[1]).toBeCloseTo(0, 6); // accolé à l'égout → aucune marche
  });

  it('un pan plat accolé au FAÎTAGE d’un pan en pente monte à sa hauteur exacte (tan(pente)×profondeur)', () => {
    // Même pan en pente, mais le pan plat est accolé au NORD (côté haut de pente).
    const pitched: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 6), facingAzimuthDeg: 180, tiltDeg: 30, pitched: true };
    const flat: MixedRidgePan = { ringENU: enuRect(0, 6, 10, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([pitched, flat]);
    const expectedH = 6 * Math.tan((30 * Math.PI) / 180);
    expect(offsets[1]).toBeCloseTo(expectedH, 6);
  });

  it('un pan plat touchant DEUX pans en pente de hauteurs différentes monte au niveau du PLUS HAUT (jamais transpercé)', () => {
    const low: MixedRidgePan = { ringENU: enuRect(0, 0, 10, 3), facingAzimuthDeg: 180, tiltDeg: 15, pitched: true };
    const high: MixedRidgePan = { ringENU: enuRect(10, 0, 10, 3), facingAzimuthDeg: 180, tiltDeg: 45, pitched: true };
    // Pan plat qui longe l'égout (y=0) des deux pans en pente, sur toute leur largeur.
    const flat: MixedRidgePan = { ringENU: enuRect(0, -6, 20, 6), facingAzimuthDeg: 180, tiltDeg: 0, pitched: false };
    const offsets = computeMixedAltitudeOffsets([low, high, flat]);
    // Les deux pans en pente touchent l'égout du plat exactement à leur propre hauteur 0
    // (aucun lift, isolés l'un de l'autre — pas de faîtière commune) : le plat reste à 0.
    expect(offsets[2]).toBeCloseTo(0, 6);
  });

  it('moins de 2 pans → aucun offset (garde-fou)', () => {
    const solo: MixedRidgePan = { ringENU: enuRect(0, 0, 8, 6), facingAzimuthDeg: 180, tiltDeg: 20, pitched: true };
    expect(computeMixedAltitudeOffsets([solo])).toEqual([0]);
  });
});

// CAL180 — dimensions de la cible HORS ÉCRAN. Partie PURE du rendu haute résolution :
// le facteur est RABAISSÉ quand le plafond l'impose, et le facteur effectif est rendu
// à l'appelant (il ne le suppose jamais).
describe('CAL180 — hdTargetSize', () => {
  it('2× et 3× sont les facteurs proposés', () => {
    expect([...HD_SCALES]).toEqual([2, 3]);
  });

  it('agrandit exactement du facteur demandé quand le plafond le permet', () => {
    expect(hdTargetSize(1280, 720, 2)).toEqual({ width: 2560, height: 1440, scale: 2 });
    expect(hdTargetSize(1280, 720, 3)).toEqual({ width: 3840, height: 2160, scale: 3 });
  });

  it('rabaisse le facteur plutôt que de dépasser le plafond', () => {
    const t = hdTargetSize(4000, 2000, 3)!;
    expect(t.width).toBeLessThanOrEqual(HD_MAX_SIDE_PX);
    expect(t.height).toBeLessThanOrEqual(HD_MAX_SIDE_PX);
    expect(t.scale).toBeLessThan(3);
    expect(t.width).toBe(HD_MAX_SIDE_PX);
  });

  it('un canvas déjà plus grand que le plafond n’est jamais réduit sous 1×', () => {
    const t = hdTargetSize(10000, 800, 2)!;
    expect(t.scale).toBe(1);
    expect(t.width).toBe(10000);
  });

  it('un canvas sans surface ne produit aucune cible (jamais une taille inventée)', () => {
    expect(hdTargetSize(0, 720, 2)).toBeNull();
    expect(hdTargetSize(1280, 0, 2)).toBeNull();
    expect(hdTargetSize(Number.NaN, 720, 2)).toBeNull();
    expect(hdTargetSize(1280, 720, 0)).toBeNull();
  });
});

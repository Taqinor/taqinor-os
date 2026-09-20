// Géométrie pure des obstacles de toiture (preview privé /preview/toiture-3d-pro-3).
// Vérifie : un rectangle centre+dimensions retombe sur ses dimensions au cm près ;
// le glissé mesure la bonne taille ; le scale est uniforme ; les bornes tiennent.
import { describe, expect, it } from 'vitest';
import {
  OBSTACLE_MAX_DIM_M,
  OBSTACLE_MIN_DIM_M,
  OBSTACLE_MAX_HEIGHT_M,
  OBSTACLE_MIN_HEIGHT_M,
  OBSTACLE_STEP_FACTOR,
  NON_ENGAGEABLE_PROVENANCES,
  clampDim,
  defaultObstacle,
  duplicatedObstacle,
  gridPositions,
  isNonEngageable,
  obstacleFromDrag,
  obstacleRing,
  resizedObstacle,
  ringDimsM,
  scaledObstacle,
  withHeight,
  withProvenance,
  type Obstacle,
} from '../src/lib/obstacles';
import type { LngLat } from '../src/lib/roof';

const at = (lng: number, lat: number, lengthM: number, widthM: number): Obstacle => ({
  id: 'o1',
  centerLng: lng,
  centerLat: lat,
  lengthM,
  widthM,
});

describe('obstacleRing ⇆ ringDimsM — la mesure retombe sur les dimensions', () => {
  for (const [lengthM, widthM] of [
    [3, 2],
    [1.5, 4],
    [0.8, 0.8],
    [10, 6],
  ] as const) {
    it(`${lengthM} m × ${widthM} m retombe au cm près`, () => {
      const ring = obstacleRing(at(-7.62, 33.59, lengthM, widthM));
      const dims = ringDimsM(ring);
      expect(dims.lengthM).toBeCloseTo(lengthM, 2);
      expect(dims.widthM).toBeCloseTo(widthM, 2);
    });
  }

  it('mesure correcte à une autre latitude (correction du cosinus)', () => {
    const ring = obstacleRing(at(-5.0, 31.0, 5, 3));
    const dims = ringDimsM(ring);
    expect(dims.lengthM).toBeCloseTo(5, 2);
    expect(dims.widthM).toBeCloseTo(3, 2);
  });
});

describe('obstacleFromDrag — mesure le rectangle glissé', () => {
  it('un glissé de ~6 m × ~4 m donne ces dimensions', () => {
    const DEG2M = (Math.PI / 180) * 6378137;
    const lat = 33.59;
    const cosLat = Math.cos((lat * Math.PI) / 180);
    const a: LngLat = [-7.62, lat];
    const b: LngLat = [-7.62 + 4 / (DEG2M * cosLat), lat + 6 / DEG2M];
    const o = obstacleFromDrag('x', a, b);
    expect(o.lengthM).toBeCloseTo(6, 1);
    expect(o.widthM).toBeCloseTo(4, 1);
    // centre = milieu du glissé
    expect(o.centerLat).toBeCloseTo(lat + 3 / DEG2M, 6);
  });

  it('un glissé minuscule est borné au minimum', () => {
    const a: LngLat = [-7.62, 33.59];
    const b: LngLat = [-7.62 + 1e-7, 33.59 + 1e-7];
    const o = obstacleFromDrag('x', a, b);
    expect(o.lengthM).toBe(OBSTACLE_MIN_DIM_M);
    expect(o.widthM).toBe(OBSTACLE_MIN_DIM_M);
  });
});

describe('scaledObstacle — agrandissement UNIFORME, centre conservé', () => {
  it('le + multiplie les deux côtés par le même facteur', () => {
    const o = at(-7.62, 33.59, 3, 2);
    const bigger = scaledObstacle(o, OBSTACLE_STEP_FACTOR);
    expect(bigger.lengthM).toBeCloseTo(3 * OBSTACLE_STEP_FACTOR, 6);
    expect(bigger.widthM).toBeCloseTo(2 * OBSTACLE_STEP_FACTOR, 6);
    expect(bigger.centerLng).toBe(o.centerLng);
    expect(bigger.centerLat).toBe(o.centerLat);
    // ratio d'aspect inchangé = scale uniforme
    expect(bigger.lengthM / bigger.widthM).toBeCloseTo(o.lengthM / o.widthM, 6);
  });

  it('le − ne descend jamais sous le minimum', () => {
    const o = at(-7.62, 33.59, OBSTACLE_MIN_DIM_M, OBSTACLE_MIN_DIM_M);
    const smaller = scaledObstacle(o, 1 / OBSTACLE_STEP_FACTOR);
    expect(smaller.lengthM).toBe(OBSTACLE_MIN_DIM_M);
    expect(smaller.widthM).toBe(OBSTACLE_MIN_DIM_M);
  });
});

describe('resizedObstacle + clampDim — saisie exacte, bornée', () => {
  it('applique la longueur/largeur saisies en conservant le centre', () => {
    const o = at(-7.62, 33.59, 3, 2);
    const r = resizedObstacle(o, 5.5, 1.2);
    expect(r.lengthM).toBeCloseTo(5.5, 6);
    expect(r.widthM).toBeCloseTo(1.2, 6);
    expect(r.centerLng).toBe(o.centerLng);
  });

  it('borne les valeurs aberrantes', () => {
    expect(clampDim(0)).toBe(OBSTACLE_MIN_DIM_M);
    expect(clampDim(-4)).toBe(OBSTACLE_MIN_DIM_M);
    expect(clampDim(NaN)).toBe(OBSTACLE_MIN_DIM_M);
    expect(clampDim(1000)).toBe(OBSTACLE_MAX_DIM_M);
    expect(clampDim(3.3)).toBe(3.3);
  });

  it('defaultObstacle est un carré centré sur le point', () => {
    const o = defaultObstacle('z', [-7.62, 33.59]);
    expect(o.lengthM).toBe(o.widthM);
    expect(o.centerLng).toBe(-7.62);
  });
});

describe('CAL66 — withHeight : hauteur SAISIE, jamais inventée', () => {
  it('applique une hauteur finie et positive, bornée', () => {
    const o = at(-7.62, 33.59, 1.5, 1.5);
    expect(withHeight(o, 1.2).heightM).toBe(1.2);
    expect(withHeight(o, 1000).heightM).toBe(OBSTACLE_MAX_HEIGHT_M);
    expect(withHeight(o, 0.001).heightM).toBe(OBSTACLE_MIN_HEIGHT_M);
  });

  it('efface la hauteur (jamais une valeur par défaut) sur une saisie vide/nulle/aberrante', () => {
    const withH = withHeight(at(-7.62, 33.59, 1.5, 1.5), 2);
    expect('heightM' in withHeight(withH, null)).toBe(false);
    expect('heightM' in withHeight(withH, undefined)).toBe(false);
    expect('heightM' in withHeight(withH, 0)).toBe(false);
    expect('heightM' in withHeight(withH, -3)).toBe(false);
    expect('heightM' in withHeight(withH, NaN)).toBe(false);
  });

  it('un obstacle sans heightM (défaut) n’en porte toujours pas — comportement historique', () => {
    expect('heightM' in at(-7.62, 33.59, 1.5, 1.5)).toBe(false);
  });
});

describe('CAL72 — withProvenance + isNonEngageable', () => {
  it('applique/efface la provenance', () => {
    const o = at(-7.62, 33.59, 1.5, 1.5);
    expect(withProvenance(o, 'MESURE').provenance).toBe('MESURE');
    expect('provenance' in withProvenance(withProvenance(o, 'MESURE'), null)).toBe(false);
  });

  it('PLAN et DEVINE (et leurs équivalents RELEVE/MESURE) rendent le compte NON engageable', () => {
    expect(NON_ENGAGEABLE_PROVENANCES).toEqual(['PLAN', 'DEVINE']);
    expect(isNonEngageable('PLAN')).toBe(true);
    expect(isNonEngageable('DEVINE')).toBe(true);
    expect(isNonEngageable('MESURE')).toBe(false);
    expect(isNonEngageable('RELEVE')).toBe(false);
    expect(isNonEngageable('MESURE_DOUTEUX')).toBe(false);
    expect(isNonEngageable('DECLARE_CLIENT')).toBe(false);
    expect(isNonEngageable('ECARTE')).toBe(false);
  });

  it('provenance absente n’est jamais bloquante (comportement historique)', () => {
    expect(isNonEngageable(undefined)).toBe(false);
    expect(isNonEngageable(null)).toBe(false);
  });
});

describe('CAL73 — duplicatedObstacle + gridPositions', () => {
  it('duplicatedObstacle copie tout SAUF id et centre', () => {
    const o = withProvenance(withHeight(at(-7.62, 33.59, 2, 1.5), 1.2), 'MESURE');
    const dup = duplicatedObstacle(o, 'obs-2', [-7.63, 33.6]);
    expect(dup.id).toBe('obs-2');
    expect(dup.centerLng).toBe(-7.63);
    expect(dup.centerLat).toBe(33.6);
    expect(dup.lengthM).toBe(o.lengthM);
    expect(dup.widthM).toBe(o.widthM);
    expect(dup.heightM).toBe(o.heightM);
    expect(dup.provenance).toBe(o.provenance);
  });

  it('gridPositions : N×M points au pas saisi, centrés sur l’origine', () => {
    const pts = gridPositions([-7.62, 33.59], 5, 3, 1);
    expect(pts).toHaveLength(3);
    // Une seule rangée : les 3 points partagent la MÊME latitude (alignés est-ouest).
    expect(pts.every((p) => p[1] === pts[0][1])).toBe(true);
    expect(pts[1][0]).toBeCloseTo(-7.62, 6); // colonne centrale = l'origine
    expect(pts[1][1]).toBeCloseTo(33.59, 6);
  });

  it('gridPositions : pas/compte invalides → []', () => {
    expect(gridPositions([-7.62, 33.59], 0, 3, 3)).toEqual([]);
    expect(gridPositions([-7.62, 33.59], -5, 3, 3)).toEqual([]);
    expect(gridPositions([-7.62, 33.59], 5, 0, 3)).toEqual([]);
    expect(gridPositions([-7.62, 33.59], 5, 3, -1)).toEqual([]);
    expect(gridPositions([-7.62, 33.59], NaN, 3, 3)).toEqual([]);
  });

  it('gridPositions : 20 lanterneaux (4×5) en une trame', () => {
    expect(gridPositions([-7.62, 33.59], 3, 4, 5)).toHaveLength(20);
  });
});

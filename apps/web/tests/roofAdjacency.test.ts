// Adjacence des pans de toiture + inférence d'azimut (lib PURE) —
// src/lib/roofAdjacency.ts. On vérifie : un PIGNON (deux rectangles partageant
// une faîtière) → façades OPPOSÉES (~180° d'écart), chacune normale à l'arête
// partagée, connected:true ; une MONO-PENTE / continuation → MÊME façade que le
// voisin, connected:true ; deux zones DISJOINTES → connected:false, repli sud
// (180°), sharedEdge:null ; azimuts dans [0,360), confiance dans [0,1].
import { describe, expect, it } from 'vitest';
import {
  inferZoneFacing,
  inferZoneFacingAmong,
  findSharedEdge,
  normalizeAzimuthDeg,
  FALLBACK_FACING_DEG,
  type LngLat,
} from '../src/lib/roofAdjacency';

// — Helpers de fixtures : un plan local en mètres autour de Casablanca —
const LAT0 = 33.5;
const LNG0 = -7.6;
const M_PER_DEG_LAT = 111320;
const M_PER_DEG_LNG = 111320 * Math.cos((LAT0 * Math.PI) / 180);

/** Construit une coordonnée [lng, lat] depuis un offset métrique (est, nord). */
function at(eastM: number, northM: number): LngLat {
  return [LNG0 + eastM / M_PER_DEG_LNG, LAT0 + northM / M_PER_DEG_LAT];
}

/**
 * Rectangle aligné est-ouest / nord-sud : coins (x0..x1, y0..y1) en mètres,
 * anneau anti-horaire. x = est, y = nord.
 */
function rect(x0: number, x1: number, y0: number, y1: number): LngLat[] {
  return [at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1)];
}

/** Écart angulaire minimal (degrés) entre deux azimuts, dans [0, 180]. */
function azDiff(a: number, b: number): number {
  let d = Math.abs(a - b) % 360;
  if (d > 180) d = 360 - d;
  return d;
}

describe('normalizeAzimuthDeg', () => {
  it('ramène tout azimut dans [0, 360)', () => {
    expect(normalizeAzimuthDeg(0)).toBe(0);
    expect(normalizeAzimuthDeg(360)).toBe(0);
    expect(normalizeAzimuthDeg(450)).toBe(90);
    expect(normalizeAzimuthDeg(-90)).toBe(270);
    expect(normalizeAzimuthDeg(-1)).toBeCloseTo(359, 6);
    expect(normalizeAzimuthDeg(540)).toBe(180);
  });
  it('replie une valeur non finie sur le repli sud', () => {
    expect(normalizeAzimuthDeg(Number.NaN)).toBe(FALLBACK_FACING_DEG);
  });
});

describe('inferZoneFacing — PIGNON (gable)', () => {
  // Faîtière commune = arête est-ouest à y = 0 (longueur 20 m).
  // Pan SUD : y de -10 à 0  → centroïde au sud → regarde le SUD (~180°).
  // Pan NORD : y de 0 à 10  → centroïde au nord → regarde le NORD (~0°).
  // Pignon : le pan voisin DESCEND À L'OPPOSÉ de l'arête partagée (l'arête est
  // sa faîtière), donc neighbourFacing pointe loin de l'arête.
  const southPan = rect(-10, 10, -10, 0);
  const northPan = rect(-10, 10, 0, 10);

  it('détecte la connexion et l’arête partagée (longueur ≈ 20 m)', () => {
    // Voisin = pan nord, qui regarde le nord (0°) → loin de l'arête → pignon.
    const r = inferZoneFacing(southPan, northPan, 0);
    expect(r.connected).toBe(true);
    expect(r.kind).toBe('gable');
    expect(r.sharedEdge).not.toBeNull();
    expect(r.sharedEdge!.lengthM).toBeCloseTo(20, 0);
  });

  it('le pan sud regarde le sud (~180°), le pan nord regarde le nord (~0°)', () => {
    const south = inferZoneFacing(southPan, northPan, 0); // voisin nord regarde 0°
    const north = inferZoneFacing(northPan, southPan, 180); // voisin sud regarde 180°
    expect(azDiff(south.facingAzimuthDeg, 180)).toBeLessThan(5);
    expect(azDiff(north.facingAzimuthDeg, 0)).toBeLessThan(5);
  });

  it('les deux pans ont des façades OPPOSÉES (~180° d’écart)', () => {
    const south = inferZoneFacing(southPan, northPan, 0);
    const north = inferZoneFacing(northPan, southPan, 180);
    expect(azDiff(south.facingAzimuthDeg, north.facingAzimuthDeg)).toBeGreaterThan(170);
  });

  it('infère un pignon SANS façade voisine connue, par la pure géométrie', () => {
    // Sans neighbourFacing, le critère géométrique (centroïdes de part et
    // d'autre) suffit pour un pignon classique : pans opposés et normaux à l'arête.
    const south = inferZoneFacing(southPan, northPan);
    const north = inferZoneFacing(northPan, southPan);
    expect(south.kind).toBe('gable');
    expect(north.kind).toBe('gable');
    expect(azDiff(south.facingAzimuthDeg, 180)).toBeLessThan(5);
    expect(azDiff(north.facingAzimuthDeg, 0)).toBeLessThan(5);
    expect(azDiff(south.facingAzimuthDeg, north.facingAzimuthDeg)).toBeGreaterThan(170);
  });

  it('la façade est normale à l’arête partagée (faîtière est-ouest → façade nord/sud)', () => {
    const south = inferZoneFacing(southPan, northPan, 0);
    // Arête est-ouest (cap 90°/270°) ⇒ normale = nord/sud (0°/180°).
    const a = south.facingAzimuthDeg % 180; // 0 ou ~180 → 0
    expect(Math.min(a, 180 - a)).toBeLessThan(5);
  });

  it('un pignon orienté est-ouest (faîtière nord-sud) → façades est/ouest opposées', () => {
    // Faîtière nord-sud à x = 0. Pan ouest regarde l'ouest (~270°), pan est l'est (~90°).
    const westPan = rect(-10, 0, -10, 10);
    const eastPan = rect(0, 10, -10, 10);
    const west = inferZoneFacing(westPan, eastPan, 90); // voisin est regarde l'est → pignon
    const east = inferZoneFacing(eastPan, westPan, 270); // voisin ouest regarde l'ouest → pignon
    expect(west.connected).toBe(true);
    expect(east.connected).toBe(true);
    expect(azDiff(west.facingAzimuthDeg, 270)).toBeLessThan(5);
    expect(azDiff(east.facingAzimuthDeg, 90)).toBeLessThan(5);
    expect(azDiff(west.facingAzimuthDeg, east.facingAzimuthDeg)).toBeGreaterThan(170);
  });

  it('confiance dans [0,1] et élevée pour un pignon net', () => {
    const r = inferZoneFacing(southPan, northPan, 0);
    expect(r.confidence).toBeGreaterThanOrEqual(0);
    expect(r.confidence).toBeLessThanOrEqual(1);
    expect(r.confidence).toBeGreaterThan(0.5);
  });
});

describe('inferZoneFacing — MONO-PENTE (continuation)', () => {
  // Continuation : le voisin DESCEND VERS l'arête partagée (sa pente traverse
  // l'arête vers le nouveau pan), donc le nouveau pan PROLONGE la même pente et
  // COPIE la façade du voisin.
  // Voisin au NORD (y 0→10), nouveau pan au SUD (y -10→0), arête partagée y=0.
  // Le voisin regarde le SUD (180°) → sa pente traverse l'arête vers le nouveau
  // pan → mono-pente, le nouveau pan regarde aussi le sud.
  const neighbourNorth = rect(-10, 10, 0, 10); // voisin au nord
  const newSouth = rect(-10, 10, -10, 0); // nouveau pan au sud, partage y=0

  it('copie EXACTEMENT la façade du voisin quand il descend vers l’arête', () => {
    const neighbourFacing = 180; // voisin descend plein sud, vers l'arête → continuation
    const r = inferZoneFacing(newSouth, neighbourNorth, neighbourFacing);
    expect(r.connected).toBe(true);
    expect(r.kind).toBe('mono-pente');
    expect(azDiff(r.facingAzimuthDeg, neighbourFacing)).toBeLessThan(1);
    expect(r.facingAzimuthDeg).toBe(180);
  });

  it('copie une façade voisine non cardinale (ex. 200°) à l’identique', () => {
    const neighbourFacing = 200; // sud-sud-ouest, traverse encore l'arête → continuation
    const r = inferZoneFacing(newSouth, neighbourNorth, neighbourFacing);
    expect(r.connected).toBe(true);
    expect(r.kind).toBe('mono-pente');
    expect(r.facingAzimuthDeg).toBe(200);
  });

  it('même géométrie mais voisin qui descend À L’OPPOSÉ de l’arête → PIGNON', () => {
    // Voisin nord qui regarde le NORD (0°) : sa faîtière EST l'arête partagée →
    // pignon, le nouveau pan sud regarde le sud (opposé).
    const r = inferZoneFacing(newSouth, neighbourNorth, 0);
    expect(r.kind).toBe('gable');
    expect(azDiff(r.facingAzimuthDeg, 180)).toBeLessThan(5);
  });

  it('continuation sans façade voisine connue → fallback géométrique cohérent', () => {
    const r = inferZoneFacing(newSouth, neighbourNorth);
    expect(r.connected).toBe(true);
    expect(r.facingAzimuthDeg).toBeGreaterThanOrEqual(0);
    expect(r.facingAzimuthDeg).toBeLessThan(360);
  });
});

describe('inferZoneFacing — DISJOINT (aucune adjacence)', () => {
  const a = rect(-10, 10, -10, 10);
  // Très loin : ~1 km à l'est.
  const b = rect(990, 1010, -10, 10);

  it('renvoie connected:false, fallback 180°, sharedEdge:null, kind:none', () => {
    const r = inferZoneFacing(a, b);
    expect(r.connected).toBe(false);
    expect(r.facingAzimuthDeg).toBe(180);
    expect(r.sharedEdge).toBeNull();
    expect(r.kind).toBe('none');
    expect(r.confidence).toBe(0);
  });

  it('findSharedEdge renvoie null pour deux zones éloignées', () => {
    expect(findSharedEdge(a, b)).toBeNull();
  });

  it('deux zones qui ne se touchent qu’en un coin → pas connecté (recouvrement insuffisant)', () => {
    const c1 = rect(-10, 0, -10, 0);
    const c2 = rect(0, 10, 0, 10); // touche c1 uniquement au point (0,0)
    const r = inferZoneFacing(c1, c2);
    expect(r.connected).toBe(false);
  });
});

describe('inferZoneFacing — robustesse / contrats', () => {
  it('un anneau dégénéré (< 3 sommets) → fallback non connecté', () => {
    const ok = rect(-10, 10, -10, 0);
    const bad = [
      [LNG0, LAT0],
      [LNG0 + 0.001, LAT0],
    ] as LngLat[];
    const r = inferZoneFacing(bad, ok);
    expect(r.connected).toBe(false);
    expect(r.facingAzimuthDeg).toBe(FALLBACK_FACING_DEG);
  });

  it('azimut toujours dans [0, 360) et confiance toujours dans [0, 1]', () => {
    const cases: Array<[LngLat[], LngLat[]]> = [
      [rect(-10, 10, -10, 0), rect(-10, 10, 0, 10)],
      [rect(-10, 0, -10, 10), rect(0, 10, -10, 10)],
      [rect(-10, 10, 10, 20), rect(-10, 10, 0, 10)],
      [rect(-10, 10, -10, 10), rect(990, 1010, -10, 10)],
    ];
    for (const [z, n] of cases) {
      const r = inferZoneFacing(z, n);
      expect(r.facingAzimuthDeg).toBeGreaterThanOrEqual(0);
      expect(r.facingAzimuthDeg).toBeLessThan(360);
      expect(r.confidence).toBeGreaterThanOrEqual(0);
      expect(r.confidence).toBeLessThanOrEqual(1);
    }
  });

  it('tolère un petit écart entre les arêtes (tracé satellite imprécis)', () => {
    // Pan nord décollé de 0,8 m vers le nord (gap < maxGap 1,5 m). Pignon par
    // pure géométrie (centroïdes de part et d'autre).
    const south = rect(-10, 10, -10, 0);
    const north = rect(-10, 10, 0.8, 10);
    const r = inferZoneFacing(south, north);
    expect(r.connected).toBe(true);
    expect(r.kind).toBe('gable');
    expect(azDiff(r.facingAzimuthDeg, 180)).toBeLessThan(8);
  });
});

describe('inferZoneFacingAmong — plusieurs voisins', () => {
  it('choisit le voisin avec la plus longue arête partagée et l’inclut', () => {
    const zone = rect(-10, 10, -10, 0); // pan sud, faîtière est-ouest à y=0
    const bigNeighbour = rect(-10, 10, 0, 10); // partage 20 m
    const tinyNeighbour = rect(10, 12, -10, 0); // partage seulement 2 m à l'est
    const farNeighbour = rect(990, 1010, -10, 10); // disjoint
    const r = inferZoneFacingAmong(
      zone,
      [tinyNeighbour, bigNeighbour, farNeighbour],
      [undefined, undefined, undefined],
    );
    expect(r.connected).toBe(true);
    expect(r.sharedEdge!.lengthM).toBeCloseTo(20, 0);
    expect(azDiff(r.facingAzimuthDeg, 180)).toBeLessThan(5);
  });

  it('aucun voisin adjacent → fallback non connecté', () => {
    const zone = rect(-10, 10, -10, 0);
    const far1 = rect(990, 1010, -10, 10);
    const far2 = rect(-2010, -1990, -10, 10);
    const r = inferZoneFacingAmong(zone, [far1, far2]);
    expect(r.connected).toBe(false);
    expect(r.facingAzimuthDeg).toBe(FALLBACK_FACING_DEG);
    expect(r.sharedEdge).toBeNull();
  });
});

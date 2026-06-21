// W106 — auto-orientation de la FACE d'un pan EN PENTE adjacent, via la lib PURE
// roofAdjacency (W105) telle que roof-tool-pro11.ts l'appelle à la fermeture d'une zone
// (inferZoneFacingAmong(newRing, existingRings, existingFacings)). On vérifie le CONTRAT
// que le câblage consomme : PIGNON → faces opposées (~180° d'écart) ; MONO-PENTE /
// continuation → même face que le voisin ; DISJOINT → non connecté, repli sud (180°),
// donc le câblage NE change rien (l'utilisateur garde 180/son choix). Lib pure, sans DOM.
import { describe, expect, it } from 'vitest';
import {
  inferZoneFacingAmong,
  FALLBACK_FACING_DEG,
  type LngLat,
} from '../src/lib/roofAdjacency';

const LAT0 = 33.5;
const LNG0 = -7.6;
const M_PER_DEG_LAT = 111320;
const M_PER_DEG_LNG = 111320 * Math.cos((LAT0 * Math.PI) / 180);

function at(eastM: number, northM: number): LngLat {
  return [LNG0 + eastM / M_PER_DEG_LNG, LAT0 + northM / M_PER_DEG_LAT];
}
/** Rectangle est-ouest / nord-sud, anneau anti-horaire (x = est, y = nord). */
function rect(x0: number, x1: number, y0: number, y1: number): LngLat[] {
  return [at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1)];
}
function azDiff(a: number, b: number): number {
  let d = Math.abs(a - b) % 360;
  if (d > 180) d = 360 - d;
  return d;
}

/** Réplique EXACTE de l'appel de câblage de roof-tool-pro11.ts autoInferFacing() : un
 *  voisin n'apporte sa face connue que s'il est lui-même en pente, et on retient le
 *  meilleur résultat connecté avec une confiance raisonnable (seuil 0,2). */
function wireFacing(
  newRing: LngLat[],
  others: { vertices: LngLat[]; roofType: 'flat' | 'pitched'; facingAzimuthDeg: number }[],
): number {
  const neighbours = others.filter((a) => a.vertices.length >= 3).map((a) => a.vertices);
  const neighbourFacings = others
    .filter((a) => a.vertices.length >= 3)
    .map((a) => (a.roofType === 'pitched' ? a.facingAzimuthDeg : undefined));
  const res = inferZoneFacingAmong(newRing, neighbours, neighbourFacings);
  if (!res.connected || res.confidence < 0.2) return FALLBACK_FACING_DEG; // → 180, choix utilisateur
  return res.facingAzimuthDeg;
}

describe('W106 — câblage auto-orientation : PIGNON → faces opposées', () => {
  // Faîtière commune = arête est-ouest à y = 0. Pan NORD existe déjà, regarde le NORD (0°).
  // Le NOUVEAU pan sud (y -10..0) doit s'auto-orienter À L'OPPOSÉ → ~sud (180°).
  const northPan = rect(-10, 10, 0, 10);
  const southPanNew = rect(-10, 10, -10, 0);

  it('le nouveau pan sud, adjacent au pan nord (face 0°), s’auto-oriente ~sud (180°)', () => {
    const facing = wireFacing(southPanNew, [
      { vertices: northPan, roofType: 'pitched', facingAzimuthDeg: 0 },
    ]);
    expect(azDiff(facing, 180)).toBeLessThan(5);
    // Inférence ACTIVE (connectée) : la lib renvoie connected=true, pas le repli.
    const direct = inferZoneFacingAmong(southPanNew, [northPan], [0]);
    expect(direct.connected).toBe(true);
    expect(direct.kind).toBe('gable');
  });

  it('deux pans connectés ont des faces opposées (~180° d’écart)', () => {
    const southFacing = wireFacing(southPanNew, [{ vertices: northPan, roofType: 'pitched', facingAzimuthDeg: 0 }]);
    const northFacing = wireFacing(northPan, [{ vertices: southPanNew, roofType: 'pitched', facingAzimuthDeg: 180 }]);
    expect(azDiff(southFacing, northFacing)).toBeGreaterThan(170);
  });
});

describe('W106 — câblage auto-orientation : MONO-PENTE → même face que le voisin', () => {
  // Continuation collinéaire : le voisin descend EN TRAVERSANT l'arête partagée vers le
  // nouveau pan (face qui pointe vers lui) → le nouveau pan COPIE la face du voisin.
  // Voisin OUEST (x -10..0) regarde l'EST (90°, vers l'arête x=0) ; nouveau pan EST
  // (x 0..10) → continuation → copie ~90°.
  const westNeighbour = rect(-10, 0, -10, 10);
  const eastNew = rect(0, 10, -10, 10);

  it('le nouveau pan copie ~la face est (90°) du voisin en continuation', () => {
    const facing = wireFacing(eastNew, [
      { vertices: westNeighbour, roofType: 'pitched', facingAzimuthDeg: 90 },
    ]);
    expect(azDiff(facing, 90)).toBeLessThan(20);
  });
});

describe('W106 — câblage auto-orientation : DISJOINT → repli sud (180°), aucun override', () => {
  const panA = rect(-10, 10, -10, 0);
  // Pan B nettement séparé (gap > maxGap 1,5 m) → aucune arête partagée.
  const panBFar = rect(-10, 10, 30, 40);

  it('deux zones disjointes → repli sud 180° (le câblage ne change rien)', () => {
    const facing = wireFacing(panBFar, [{ vertices: panA, roofType: 'pitched', facingAzimuthDeg: 180 }]);
    expect(facing).toBe(FALLBACK_FACING_DEG);
    expect(facing).toBe(180);
  });

  it('aucune autre zone → repli sud 180°', () => {
    const facing = wireFacing(panA, []);
    expect(facing).toBe(180);
  });
});

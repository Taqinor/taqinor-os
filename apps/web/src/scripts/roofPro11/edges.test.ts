// CAL57 — déduction PURE du type d'arête par segment de contour.
import { describe, expect, it } from 'vitest';
import { deduceEdgeTypes, EDGE_COLOR_BY_TYPE, type EdgeDeductionZone } from './edges';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LAT0 = 33.59;

/** Rectangle EW×NS (m) centré sur (LNG0,LAT0), en lng/lat. */
function rect(lng0: number, lat0: number, wEW: number, hNS: number) {
  const cosLat = Math.cos(lat0 * DEG2RAD);
  const dLng = wEW / 2 / (DEG2M * cosLat);
  const dLat = hNS / 2 / DEG2M;
  return [
    [lng0 - dLng, lat0 - dLat],
    [lng0 + dLng, lat0 - dLat],
    [lng0 + dLng, lat0 + dLat],
    [lng0 - dLng, lat0 + dLat],
  ] as [number, number][];
}

describe('CAL57 — deduceEdgeTypes', () => {
  it('toit PLAT : chaque segment est une rive (aucune supposition de pente)', () => {
    const zone: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'flat', facingAzimuthDeg: 180 };
    const edges = deduceEdgeTypes(zone, []);
    expect(edges).toHaveLength(4);
    expect(edges.every((e) => e.type === 'rive')).toBe(true);
    expect(edges.map((e) => e.index)).toEqual([0, 1, 2, 3]);
  });

  it('contour < 3 sommets → []', () => {
    expect(deduceEdgeTypes({ vertices: [[0, 0], [0, 1]], roofType: 'pitched', facingAzimuthDeg: 180 }, [])).toEqual([]);
  });

  it('pan en pente ISOLÉ : l’arête la plus en aval de la pente est l’égout, le reste inconnu', () => {
    // Face plein sud (180°) : le segment le plus au SUD est le plus en aval → égout.
    const zone: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 180 };
    const edges = deduceEdgeTypes(zone, []);
    const egout = edges.find((e) => e.type === 'egout');
    expect(egout).toBeTruthy();
    // Segment 0 = (dLng-,dLat-)→(dLng+,dLat-) : c'est le côté SUD (latitude minimale).
    expect(egout!.index).toBe(0);
    expect(edges.filter((e) => e.type === 'inconnue')).toHaveLength(3);
    expect(edges.some((e) => e.type === 'faitage')).toBe(false);
  });

  it('deux pans en pente ADJACENTS (arête commune) : le segment partagé est une faîtière', () => {
    // Deux rectangles 10×6 côte à côte, accolés sur leur côté EST/OUEST.
    const a: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 90 };
    const dLng = 10 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
    const b: EdgeDeductionZone = { vertices: rect(-7.6 + dLng, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 270 };
    const edgesA = deduceEdgeTypes(a, [b]);
    expect(edgesA.some((e) => e.type === 'faitage')).toBe(true);
    const edgesB = deduceEdgeTypes(b, [a]);
    expect(edgesB.some((e) => e.type === 'faitage')).toBe(true);
  });

  it('un pan plat voisin ne crée jamais de faîtière (seuls deux pans EN PENTE se rejoignent)', () => {
    const a: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 90 };
    const dLng = 10 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
    const flatNeighbor: EdgeDeductionZone = { vertices: rect(-7.6 + dLng, LAT0, 10, 6), roofType: 'flat', facingAzimuthDeg: 270 };
    const edges = deduceEdgeTypes(a, [flatNeighbor]);
    expect(edges.some((e) => e.type === 'faitage')).toBe(false);
  });

  it('déduction déterministe : même entrée → même sortie (stable pour un round-trip)', () => {
    const zone: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 200 };
    expect(deduceEdgeTypes(zone, [])).toEqual(deduceEdgeTypes(zone, []));
  });

  it('EDGE_COLOR_BY_TYPE couvre les six types (rendu 3D)', () => {
    for (const t of ['faitage', 'noue', 'arretier', 'egout', 'rive', 'inconnue'] as const) {
      expect(typeof EDGE_COLOR_BY_TYPE[t]).toBe('number');
    }
  });
});

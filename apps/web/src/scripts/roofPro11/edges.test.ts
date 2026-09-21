// CAL57 — déduction PURE du type d'arête par segment de contour.
// CALX93 — noue / arêtier déduits des pentes et azimuts SAISIS, sinon « inconnue ».
import { describe, expect, it } from 'vitest';
import { deduceEdgeDetails, deduceEdgeTypes, EDGE_COLOR_BY_TYPE, type EdgeDeductionZone } from './edges';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LAT0 = 33.59;
const LNG0 = -7.6;

/** Contour donné en MÈTRES autour de (LNG0, LAT0) — x vers l'est, y vers le nord. */
function polyM(pts: [number, number][]): [number, number][] {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  return pts.map(([x, y]) => [LNG0 + x / (DEG2M * cosLat), LAT0 + y / DEG2M] as [number, number]);
}

/** Demi-croupe SUD d'un carré 10×10 centré sur l'origine : sommet au centre, égout au
 *  sud, et la diagonale centre→coin SE partagée avec le pan EST. */
const TRIANGLE_SUD: [number, number][] = [
  [0, 0],
  [-5, -5],
  [5, -5],
];
/** Demi-croupe EST du même carré : partage la diagonale centre→coin SE. */
const TRIANGLE_EST: [number, number][] = [
  [0, 0],
  [5, -5],
  [5, 5],
];
/** Rang du segment partagé (la diagonale) dans chaque triangle. */
const DIAGONALE_SUD = 2;
const DIAGONALE_EST = 0;

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

describe('CALX93 — noue et arêtier déduits des pans voisins', () => {
  /** Les deux demi-croupes, avec les fruits et pentes SAISIS passés en argument. */
  function croupes(azSud: number, azEst: number, pitchSud?: number, pitchEst?: number) {
    const sud: EdgeDeductionZone = {
      vertices: polyM(TRIANGLE_SUD),
      roofType: 'pitched',
      facingAzimuthDeg: azSud,
      ...(pitchSud === undefined ? {} : { pitchDeg: pitchSud }),
    };
    const est: EdgeDeductionZone = {
      vertices: polyM(TRIANGLE_EST),
      roofType: 'pitched',
      facingAzimuthDeg: azEst,
      ...(pitchEst === undefined ? {} : { pitchDeg: pitchEst }),
    };
    return { sud, est };
  }

  it('config 1 — FAÎTAGE : arête de niveau, fruits opposés (déduction inchangée)', () => {
    // Deux rectangles accolés sur un côté N-S : l'arête est de niveau pour les deux pans.
    const a: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 90, pitchDeg: 25 };
    const dLng = 10 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
    const b: EdgeDeductionZone = { vertices: rect(-7.6 + dLng, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 270, pitchDeg: 25 };
    const details = deduceEdgeDetails(a, [b]);
    const partagee = details.filter((e) => e.type === 'faitage');
    expect(partagee).toHaveLength(1);
    expect(partagee[0].raison).toContain('niveau');
    expect(details.some((e) => e.type === 'noue' || e.type === 'arretier')).toBe(false);
  });

  it('config 2 — NOUE : arête montante vers laquelle les deux pans descendent', () => {
    // Fruits vers le nord et vers l'ouest : les deux versants se déversent dans la diagonale.
    const { sud, est } = croupes(0, 270, 30, 30);
    expect(deduceEdgeDetails(sud, [est])[DIAGONALE_SUD].type).toBe('noue');
    expect(deduceEdgeDetails(est, [sud])[DIAGONALE_EST].type).toBe('noue');
  });

  it('config 3 — ARÊTIER : arête montante dont les deux pans s’écartent', () => {
    // Fruits vers le sud et vers l'est : l'eau s'éloigne de la diagonale des deux côtés.
    const { sud, est } = croupes(180, 90, 30, 30);
    const detailSud = deduceEdgeDetails(sud, [est])[DIAGONALE_SUD];
    expect(detailSud.type).toBe('arretier');
    expect(detailSud.raison).toContain('saillant');
    expect(deduceEdgeDetails(est, [sud])[DIAGONALE_EST].type).toBe('arretier');
  });

  it('config 4 — INDÉCIDABLE : un pan descend vers l’arête, l’autre s’en écarte', () => {
    const { sud, est } = croupes(180, 270, 30, 30);
    const detail = deduceEdgeDetails(sud, [est])[DIAGONALE_SUD];
    expect(detail.type).toBe('inconnue');
    expect(detail.raison).toContain('ni noue ni arêtier');
  });

  it('pan sans pitchDeg SAISI : l’arête reste « inconnue » et dit ce qui manque', () => {
    const { sud, est } = croupes(180, 90, undefined, 30);
    const depuisSud = deduceEdgeDetails(sud, [est])[DIAGONALE_SUD];
    expect(depuisSud.type).toBe('inconnue');
    expect(depuisSud.raison).toContain('pente non saisie sur ce pan');
    // Vu depuis le pan EST, c'est le VOISIN dont la pente manque — le motif le nomme.
    const depuisEst = deduceEdgeDetails(est, [sud])[DIAGONALE_EST];
    expect(depuisEst.type).toBe('inconnue');
    expect(depuisEst.raison).toContain('pan voisin');
  });

  it('pente SAISIE à 0° : aucune arête ne monte, rien n’est tranché', () => {
    const { sud, est } = croupes(180, 90, 0, 30);
    const detail = deduceEdgeDetails(sud, [est])[DIAGONALE_SUD];
    expect(detail.type).toBe('inconnue');
    expect(detail.raison).toContain('pente saisie nulle');
  });

  it('arête de niveau mais fruits PARALLÈLES : ni faîtage ni noue (inconnue)', () => {
    const a: EdgeDeductionZone = { vertices: rect(-7.6, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 90, pitchDeg: 25 };
    const dLng = 10 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
    const b: EdgeDeductionZone = { vertices: rect(-7.6 + dLng, LAT0, 10, 6), roofType: 'pitched', facingAzimuthDeg: 90, pitchDeg: 25 };
    const details = deduceEdgeDetails(a, [b]);
    expect(details.some((e) => e.type === 'faitage')).toBe(false);
    const partagee = details.find((e) => e.raison.includes('fruits non opposés'));
    expect(partagee?.type).toBe('inconnue');
  });

  it('chaque arête porte un motif non vide, et le document sérialisé n’en porte AUCUN', () => {
    const { sud, est } = croupes(180, 90, 30, 30);
    const details = deduceEdgeDetails(sud, [est]);
    expect(details).toHaveLength(3);
    expect(details.every((e) => e.raison.trim().length > 0)).toBe(true);
    const serialise = deduceEdgeTypes(sud, [est]);
    expect(serialise).toEqual(details.map((e) => ({ index: e.index, type: e.type })));
    expect(serialise.every((e) => !('raison' in e))).toBe(true);
  });

  it('les autres segments des croupes gardent l’égout déduit de la pente', () => {
    const { sud, est } = croupes(180, 90, 30, 30);
    const details = deduceEdgeDetails(sud, [est]);
    // Segment 1 = (-5,-5) → (5,-5) : le bas de pente du pan SUD.
    expect(details[1].type).toBe('egout');
    expect(details[0].type).toBe('inconnue');
  });
});

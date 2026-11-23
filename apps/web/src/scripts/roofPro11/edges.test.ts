// CAL57 — déduction PURE du type d'arête par segment de contour.
// CALX93 — noue / arêtier déduits des pentes et azimuts SAISIS, sinon « inconnue ».
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { deduceEdgeDetails, deduceEdgeTypes, EDGE_COLOR_BY_TYPE, EDGE_TYPES, reinitialiserDepuisTraceClient, type EdgeDeductionZone } from './edges';
import { lireTableRetraits, poserRetraitsSociete } from './retraitsSociete'; // ACAL562
import { fusionnerAretesSaisies } from './edges';
import { TRIANGLE_SUD, TRIANGLE_EST, DIAGONALE_SUD, ctxDeBase, panDeTest } from './harnaisAtelier';
import { poserRetraitsPuisRecalculer } from './fermetureDuPan'; // demande croisée ACAL562
import { type Ctx } from './context';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LAT0 = 33.59;
const LNG0 = -7.6;

/** Contour donné en MÈTRES autour de (LNG0, LAT0) — x vers l'est, y vers le nord. */
function polyM(pts: [number, number][]): [number, number][] {
  const cosLat = Math.cos(LAT0 * DEG2RAD);
  return pts.map(([x, y]) => [LNG0 + x / (DEG2M * cosLat), LAT0 + y / DEG2M] as [number, number]);
}

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

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL78 — « Recommencer depuis le tracé client » efface les arêtes corrigées à la main
// et le rattachement au bâtiment devenu faux.
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL78 — reinitialiserDepuisTraceClient', () => {
  const ancien: [number, number][] = [[-7.6, 33.5], [-7.5998, 33.5], [-7.5998, 33.5002], [-7.6, 33.5002]];
  const trace: [number, number][] = [[-7.61, 33.51], [-7.6098, 33.51], [-7.6098, 33.5102], [-7.61, 33.5102]];

  it('reinitialiserDepuisTraceClient efface les arêtes manuelles', () => {
    const pan = {
      id: 'area-1', vertices: ancien, obstacles: [{ id: 'obs-1' }], buildingId: 'bat-1',
      edges: [{ index: 1, type: 'faitage' as const, manuel: true as const, retraitM: 0.8 }],
    };
    const neuf = reinitialiserDepuisTraceClient(pan, trace, [pan]);
    expect(neuf.edges).toBeUndefined();
    expect(neuf.vertices).toEqual(trace);
    expect(neuf.obstacles).toEqual([]);
    // Pan seul de son bâtiment : le bâtiment, c'est lui — le rattachement reste vrai.
    expect(neuf.buildingId).toBe('bat-1');
    // Pur : l'ancien pan n'a pas bougé.
    expect(pan.edges).toHaveLength(1);
  });

  it('le rattachement au bâtiment est retiré quand le tracé sort de l’emprise des autres pans du bâtiment', () => {
    const pan = { id: 'area-1', vertices: ancien, buildingId: 'bat-1' };
    const frere = { id: 'area-2', vertices: ancien.map(([x, y]) => [x + 0.0001, y] as [number, number]), buildingId: 'bat-1' };
    expect(reinitialiserDepuisTraceClient(pan, trace, [pan, frere]).buildingId).toBeUndefined();
    // Un tracé qui reste dans l'emprise du bâtiment garde son rattachement.
    expect(reinitialiserDepuisTraceClient(pan, ancien, [pan, frere]).buildingId).toBe('bat-1');
  });
});

describe('ACAL561 — TYPES_ARETE du serveur = EDGE_TYPES sans « inconnue »', () => {
  it('les deux listes portent les mêmes types, dans le même ordre', () => {
    const py = readFileSync(
      fileURLToPath(new URL('../../../../../backend/django_core/apps/calepinage/services/degagements.py', import.meta.url)),
      'utf8',
    );
    const ligne = /^TYPES_ARETE = \(([^)]*)\)/m.exec(py);
    expect(ligne, 'TYPES_ARETE absent de degagements.py').not.toBeNull();
    const serveur = [...(ligne as RegExpExecArray)[1].matchAll(/'([a-z_]+)'/g)].map((m) => m[1]);
    expect(serveur).toEqual(EDGE_TYPES.filter((t) => t !== 'inconnue'));
  });
});

describe('ACAL562 — retraits de la société posés sur les arêtes typées', () => {
  const table = lireTableRetraits({
    retraits_par_arete: [
      { type: 'egout', retrait_m: 0.4, source: 'notice X' },
      { type: 'rive', retrait_m: 0.3, source: 'notice X' },
      { type: 'faitage', retrait_m: 0.2, source: 'notice X' },
    ],
  });
  const quatre = [
    { index: 0, type: 'egout' as const },
    { index: 1, type: 'rive' as const },
    { index: 2, type: 'faitage' as const },
    { index: 3, type: 'rive' as const },
  ];

  it('pan à 4 arêtes (2 rives, 1 faîtage, 1 égout) ⇒ 3 retraits distincts lus au réglage, marqués société', () => {
    const { edges, inconnues } = poserRetraitsSociete(undefined, quatre, table);
    expect(edges!.map((e) => e.retraitM)).toEqual([0.4, 0.3, 0.2, 0.3]);
    expect(new Set(edges!.map((e) => e.retraitM)).size).toBe(3);
    expect(edges!.every((e) => e.retraitOrigine === 'societe')).toBe(true);
    expect(inconnues).toBe(0);
  });

  it('une arête au retrait saisi reste intacte ; une arête inconnue n’en reçoit aucun et est comptée', () => {
    const saisie = [{ index: 0, type: 'egout' as const, retraitM: 0.9 }];
    const deduites = [...quatre.slice(0, 3), { index: 3, type: 'inconnue' as const }];
    const { edges, inconnues } = poserRetraitsSociete(saisie, deduites, table);
    expect(edges![0]).toEqual({ index: 0, type: 'egout', retraitM: 0.9 });
    expect(edges!.find((e) => e.index === 3)).toBeUndefined();
    expect(inconnues).toBe(1);
  });

  it('sans table : aucun changement ; `fusionnerAretesSaisies` reporte retraitOrigine', () => {
    expect(poserRetraitsSociete(undefined, quatre, {}).edges).toBeUndefined();
    const { edges } = poserRetraitsSociete(undefined, quatre, table);
    const fusion = fusionnerAretesSaisies(edges, quatre);
    expect(fusion![0]).toMatchObject({ retraitM: 0.4, retraitOrigine: 'societe' });
  });

  // Demande croisée — le premier pavage d'un pan neuf voit déjà les retraits de la société.
  it('à la fin du tracé, les retraits sont posés AVANT le premier recalc (jamais juste après)', () => {
    const pan = panDeTest('area-1', { vertices: polyM([[0, 0], [10, 0], [10, 6], [0, 6]]), roofType: 'flat' });
    const ctx = {
      ...ctxDeBase([pan]),
      activeArea: () => pan,
      opts: { reglagesAtelier: { degagements: { retraits_par_arete: [{ type: 'egout', retrait_m: 0.4 }, { type: 'rive', retrait_m: 0.3 }, { type: 'faitage', retrait_m: 0.2 }] } } },
    } as unknown as Ctx;
    let aretesVues: unknown;
    poserRetraitsPuisRecalculer(ctx, () => { aretesVues = pan.edges?.map((e) => e.retraitOrigine); });
    expect(aretesVues).toBeDefined();
    expect((aretesVues as string[]).length).toBeGreaterThan(0);
    expect(aretesVues).toContain('societe');
  });
});

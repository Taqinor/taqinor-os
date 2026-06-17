// Cerveau V6 de l'estimateur — src/lib/estimatorBrainV6.ts (preview privé pro-9).
// V6 COMPOSE sur V2/V4/V5 sans les modifier. Ces tests ANCRENT les deux corrections
// sur de la géométrie / des invariants vérifiables (le build ne voit pas la carte) :
//
//  FIX 1 — TOIT EN PENTE = VRAI PLAN INCLINÉ, panneaux AFFLEURANTS (coplanaires) :
//    - la normale du toit n'est PAS verticale dès que pitch > 0 (et vaut bien la
//      normale (pente, face)) ;
//    - chaque panneau est COPLANAIRE (même normale que le toit) ;
//    - chaque panneau est à un MÊME petit décalage constant au-dessus du plan
//      (pas de hauteurs variables = pas de châssis) ;
//    - les panneaux haut-de-pente sont PHYSIQUEMENT plus hauts (vrai plan incliné) ;
//    - le helper du rendu (`flushPanelCenterAt`) coïncide avec la pose testée.
//
//  FIX 2 — L'OPTIMISEUR BALAIE *ET RENVOIE* LA MATRICE COMPLÈTE (toit plat) :
//    - grille d'inclinaison 0→35° par pas de 5° + optimum ; azimut sud ±45° par pas
//      de 15° RÉELLEMENT balayé + Est-Ouest ; bien plus que 6 lignes ;
//    - le RECOMMANDÉ est le VRAI maximum sur tout le balayage (PVGIS = source de
//      vérité, repli « estimé »), plafonné au besoin ;
//    - tri/regroupement du tableau exploitables sur téléphone.
import { describe, expect, it } from 'vitest';
import {
  COPLANAR_TOL,
  PITCHED_FLUSH_STANDOFF_M,
  acrossUnit,
  dot3,
  eaveUpSlopeCoord,
  facingUnit,
  fineGridMatrixV6,
  flushPanelCenterAt,
  flushPanelPose,
  matrixGroupKey,
  matrixTiltGrid,
  pitchedDeckZ,
  pvgisMatrixCandidatePairs,
  roofPlaneNormal,
  signedDistanceToPlane,
  sortMatrix,
  southSpanAzimuths,
  upSlopeUnit,
  type YieldFn,
} from '../src/lib/estimatorBrainV6';
import { optimalSouthTiltDeg } from '../src/lib/estimatorBrainV2';
import type { LngLat } from '../src/lib/roof';

const LAT = 33.59;

function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

// ════════════════════════════════════════════════════════════════════════════════
// FIX 1 — géométrie du plan incliné (toit en pente, pose affleurante)
// ════════════════════════════════════════════════════════════════════════════════
describe('V6 FIX 1 — la normale du toit n\'est PAS verticale en pente', () => {
  it('toit plat (pitch 0) → normale = vecteur vertical (0,0,1)', () => {
    const n = roofPlaneNormal(0, 180);
    expect(n.x).toBeCloseTo(0, 9);
    expect(n.y).toBeCloseTo(0, 9);
    expect(n.z).toBeCloseTo(1, 9);
  });

  it('pitch > 0 → normale inclinée (composante horizontale = sin θ), JAMAIS verticale', () => {
    for (const pitch of [10, 22, 30, 45]) {
      const n = roofPlaneNormal(pitch, 180);
      const horiz = Math.hypot(n.x, n.y);
      expect(horiz).toBeCloseTo(Math.sin((pitch * Math.PI) / 180), 9);
      expect(horiz).toBeGreaterThan(0.01); // pas le vecteur vertical
      expect(n.z).toBeCloseTo(Math.cos((pitch * Math.PI) / 180), 9);
      // unitaire
      expect(Math.hypot(n.x, n.y, n.z)).toBeCloseTo(1, 9);
    }
  });

  it('la normale penche VERS la face (sud → −Y ; est → +X)', () => {
    const south = roofPlaneNormal(30, 180); // face sud → -Y (Nord = +Y)
    expect(south.y).toBeLessThan(0);
    expect(Math.abs(south.x)).toBeLessThan(1e-9);
    const east = roofPlaneNormal(30, 90); // face est → +X
    expect(east.x).toBeGreaterThan(0);
    expect(Math.abs(east.y)).toBeLessThan(1e-9);
  });

  it('base ENU cohérente : face, amont opposé, travers perpendiculaire', () => {
    const f = facingUnit(180); // sud
    const us = upSlopeUnit(180);
    const ac = acrossUnit(180);
    expect(us.x).toBeCloseTo(-f.x, 9);
    expect(us.y).toBeCloseTo(-f.y, 9);
    expect(us.x * ac.x + us.y * ac.y).toBeCloseTo(0, 9); // perpendiculaires
  });
});

describe('V6 FIX 1 — panneaux COPLANAIRES, décalage constant, plan incliné réel', () => {
  const pitch = 30;
  const facing = 180; // sud
  const baseZ = 6;
  const n = roofPlaneNormal(pitch, facing);

  // Un échantillon de panneaux à différents (amont, travers) sur le plan.
  const offsets = [
    [0, 0],
    [2, 1],
    [5, -3],
    [9, 4],
    [12, -6],
  ];
  const poses = offsets.map(([up, across]) => flushPanelPose(up, across, baseZ, pitch, facing));

  it('chaque panneau a EXACTEMENT la normale du toit (coplanaire)', () => {
    for (const p of poses) {
      expect(dot3(p.normal, n)).toBeCloseTo(1, 9); // même direction
      expect(Math.abs(1 - dot3(p.normal, n))).toBeLessThan(COPLANAR_TOL);
    }
  });

  it('chaque panneau est au MÊME décalage constant (standoff) au-dessus du plan', () => {
    for (const p of poses) {
      const d = signedDistanceToPlane(p.center, baseZ, pitch, facing);
      expect(d).toBeCloseTo(PITCHED_FLUSH_STANDOFF_M, 9);
    }
    // distances toutes identiques → pas de hauteurs variables (= pas de châssis)
    const dists = poses.map((p) => signedDistanceToPlane(p.center, baseZ, pitch, facing));
    const spread = Math.max(...dists) - Math.min(...dists);
    expect(spread).toBeLessThan(1e-9);
  });

  it('les panneaux haut-de-pente sont PHYSIQUEMENT plus hauts (vrai plan incliné)', () => {
    const low = flushPanelPose(0, 0, baseZ, pitch, facing).center.z;
    const mid = flushPanelPose(5, 0, baseZ, pitch, facing).center.z;
    const high = flushPanelPose(10, 0, baseZ, pitch, facing).center.z;
    expect(mid).toBeGreaterThan(low);
    expect(high).toBeGreaterThan(mid);
    // un toit PLAT mettrait tout à la même hauteur — ici l'écart suit tan(pente)
    expect(high - low).toBeCloseTo(10 * Math.tan((pitch * Math.PI) / 180), 6);
  });

  it('toit plat (pitch 0) → tous les centres à la même hauteur (pas d\'inclinaison)', () => {
    const a = flushPanelPose(0, 0, baseZ, 0, facing).center.z;
    const b = flushPanelPose(10, 0, baseZ, 0, facing).center.z;
    expect(a).toBeCloseTo(b, 9);
  });
});

describe('V6 FIX 1 — surface de toit inclinée + helper de rendu cohérent', () => {
  const pitch = 22;
  const facing = 200; // toit tourné
  const baseZ = 6;
  const ring = squareRing(14);

  it('pitchedDeckZ : l\'égout reste à baseZ, le faîte monte', () => {
    // contour ENU approximatif (mètres) autour de l'origine : on prend un carré.
    const enu: [number, number][] = [
      [-7, -7],
      [7, -7],
      [7, 7],
      [-7, 7],
    ];
    const eave = eaveUpSlopeCoord(enu, facing);
    const zs = enu.map(([x, y]) => pitchedDeckZ(x, y, eave, baseZ, pitch, facing));
    expect(Math.min(...zs)).toBeCloseTo(baseZ, 6); // l'égout est à baseZ
    expect(Math.max(...zs)).toBeGreaterThan(baseZ + 0.5); // le faîte est plus haut
  });

  it('flushPanelCenterAt (rendu) pose le panneau sur le plan à standoff constant', () => {
    const enu: [number, number][] = [
      [-7, -7],
      [7, -7],
      [7, 7],
      [-7, 7],
    ];
    const eave = eaveUpSlopeCoord(enu, facing);
    for (const [cx, cy] of [
      [-3, 2],
      [0, 0],
      [4, -5],
      [6, 6],
    ]) {
      const center = flushPanelCenterAt(cx, cy, eave, baseZ, pitch, facing);
      // posé à standoff au-dessus du plan passant par l'égout
      const planeZ = pitchedDeckZ(cx, cy, eave, baseZ, pitch, facing);
      const planePoint = { x: cx, y: cy, z: planeZ };
      const d = signedDistanceToPlane(
        { x: center.x, y: center.y, z: center.z },
        baseZ,
        pitch,
        facing,
      );
      const dPlane = signedDistanceToPlane(planePoint, baseZ, pitch, facing);
      expect(d - dPlane).toBeCloseTo(PITCHED_FLUSH_STANDOFF_M, 6);
    }
    void ring;
  });
});

// ════════════════════════════════════════════════════════════════════════════════
// FIX 2 — la matrice complète balayée ET renvoyée pour affichage
// ════════════════════════════════════════════════════════════════════════════════
describe('V6 FIX 2 — grille d\'inclinaison & balayage d\'azimut', () => {
  it('grille d\'inclinaison : 0→35° par pas de 5° + l\'optimum, bornée [0,35]', () => {
    const grid = matrixTiltGrid(LAT);
    expect(grid[0]).toBe(0);
    expect(grid[grid.length - 1]).toBeLessThanOrEqual(35);
    for (const t of [0, 5, 10, 15, 20, 25, 30, 35]) expect(grid).toContain(t);
    expect(grid).toContain(optimalSouthTiltDeg(LAT));
    expect([...grid].sort((a, b) => a - b)).toEqual(grid);
  });

  it('balayage d\'azimut = sud ±45° par pas de 15° (135..225, inclut plein sud)', () => {
    const span = southSpanAzimuths();
    expect(span).toEqual([135, 150, 165, 180, 195, 210, 225]);
    expect(span).toContain(180);
  });

  it('couples PVGIS candidats : aspects du span sud présents, plus nombreux sur toit tourné', () => {
    const flat = pvgisMatrixCandidatePairs(LAT, 180);
    const aspects = flat.map((p) => p.aspect);
    for (const a of [-45, 0, 45]) expect(aspects).toContain(a); // span sud réellement interrogé
    const turned = pvgisMatrixCandidatePairs(LAT, 235);
    expect(turned.length).toBeGreaterThan(flat.length); // l'axe aligné ajoute des aspects
  });
});

describe('V6 FIX 2 — fineGridMatrixV6 renvoie la MATRICE complète', () => {
  const ring = squareRing(20);
  const bill = 1500;

  it('renvoie BIEN plus de 6 lignes et couvre tout le span d\'azimut (pas 6 presets)', () => {
    const res = fineGridMatrixV6(ring, LAT, bill, []);
    expect(res.rows.length).toBe(res.evaluated);
    expect(res.rows.length).toBeGreaterThan(50); // pas ~6
    // le span sud est RÉELLEMENT évalué : des aspects négatifs ET positifs présents.
    const aspects = res.rows.filter((r) => r.family === 'south').map((r) => Math.round(r.aspect));
    expect(aspects.some((a) => a <= -30)).toBe(true); // sud-est
    expect(aspects.some((a) => a >= 30)).toBe(true); // sud-ouest
    expect(aspects.some((a) => a === 0)).toBe(true); // plein sud
    // le mode Est-Ouest dos à dos est présent
    expect(res.rows.some((r) => r.family === 'eastwest')).toBe(true);
    // portrait ET paysage présents
    expect(res.rows.some((r) => r.orientation === 'portrait')).toBe(true);
    expect(res.rows.some((r) => r.orientation === 'landscape')).toBe(true);
  });

  it('le gagnant fait partie de la matrice et est le VRAI maximum (comparateur)', () => {
    const res = fineGridMatrixV6(ring, LAT, bill, []);
    expect(res.rows).toContainEqual(res.winner);
    // aucune ligne n'est strictement meilleure que le gagnant.
    for (const r of res.rows) {
      expect(r.annualKwh).toBeLessThanOrEqual(res.winner.annualKwh + 1e-6);
    }
    expect(res.optimumRow.label).toContain('Optimum calculé');
    expect(res.optimumRow.reason.length).toBeGreaterThan(10);
  });

  it('PVGIS = source de vérité : un pic injecté DÉPLACE le gagnant (tilt ET azimut)', () => {
    // Pic injecté à 10° et aspect −30 (sud-est) : le gagnant doit s\'y caler — pas un
    // preset plein-sud à l\'inclinaison de table. Prouve que le SPAN d\'azimut compte.
    const peakTilt = 10;
    const peakAspect = -30;
    const yieldFn: YieldFn = (tilt, aspect) =>
      Math.max(150, 1700 - Math.abs(tilt - peakTilt) * 14 - Math.abs(aspect - peakAspect) * 10);
    const res = fineGridMatrixV6(ring, LAT, bill, [], { yieldFn });
    expect(res.yieldSource).toBe('pvgis');
    expect(res.winner.tiltDeg).toBe(peakTilt);
    expect(res.winner.family).toBe('south');
    expect(Math.round(res.winner.aspect)).toBe(peakAspect); // azimut sud-est gagne
  });

  it('repli gracieux : yieldFn=null → table committée, source « estimate »', () => {
    const nullFn: YieldFn = () => null;
    const withNull = fineGridMatrixV6(ring, LAT, bill, [], { yieldFn: nullFn });
    const tableOnly = fineGridMatrixV6(ring, LAT, bill, []);
    expect(withNull.yieldSource).toBe('estimate');
    expect(Math.round(withNull.winner.annualKwh)).toBe(Math.round(tableOnly.winner.annualKwh));
  });

  it('respecte le plafond « besoin » : posé ≤ besoin partout', () => {
    const res = fineGridMatrixV6(ring, LAT, bill, []);
    expect(res.winner.placedCount).toBeLessThanOrEqual(res.neededPanels);
    for (const r of res.rows) expect(r.placedCount).toBeLessThanOrEqual(res.neededPanels);
  });
});

describe('V6 FIX 2 — tri & regroupement du tableau (lisible sur téléphone)', () => {
  const ring = squareRing(20);

  it('sortMatrix(kWh/an, desc) place le max en tête et reste stable', () => {
    const res = fineGridMatrixV6(ring, LAT, 1500, []);
    const sorted = sortMatrix(res.rows, 'annualKwh', 'desc');
    expect(sorted[0].annualKwh).toBeCloseTo(res.winner.annualKwh, 6);
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i - 1].annualKwh).toBeGreaterThanOrEqual(sorted[i].annualKwh - 1e-6);
    }
  });

  it('sortMatrix gère panneaux et % du besoin (asc/desc)', () => {
    const res = fineGridMatrixV6(ring, LAT, 1500, []);
    const byPanels = sortMatrix(res.rows, 'placedCount', 'asc');
    expect(byPanels[0].placedCount).toBeLessThanOrEqual(byPanels[byPanels.length - 1].placedCount);
    const byPct = sortMatrix(res.rows, 'pctOfTarget', 'desc');
    expect(byPct[0].pctOfTarget).toBeGreaterThanOrEqual(byPct[byPct.length - 1].pctOfTarget);
  });

  it('matrixGroupKey regroupe par orientation/pose (clés limitées, lisibles)', () => {
    const res = fineGridMatrixV6(ring, LAT, 1500, []);
    const groups = new Set(res.rows.map(matrixGroupKey));
    expect(groups.size).toBeGreaterThan(1);
    expect(groups.size).toBeLessThan(res.rows.length); // vrai regroupement, pas 1:1
    expect([...groups].some((g) => g.includes('portrait'))).toBe(true);
    expect([...groups].some((g) => g.includes('paysage'))).toBe(true);
  });
});

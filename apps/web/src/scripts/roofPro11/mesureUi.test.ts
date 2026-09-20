// CAL102 — outil de mesure (distance/surface/angle), persistable comme annotation du
// calepinage. Géométrie PURE testée hors DOM ; la couche UI (createMesureUi) est testée via
// un `ctx` minimal (mêmes conventions que les autres tests roofPro11 — ctx partiel typé `as
// Ctx`, seuls les champs lus sont fournis).
import { describe, expect, it } from 'vitest';
import {
  segmentDistanceM,
  cumulativeDistanceM,
  polygonAreaM2,
  vertexAngleDeg,
  measureValue,
  isMeasureValid,
  formatMeasure,
  createMesureUi,
} from './mesureUi';
import { geodesicAreaM2, geodesicPerimeterM, type LngLat } from '../../lib/roof';
import { type Ctx } from './context';

/** Contour RECTANGULAIRE (même convention que le tracé du toit), côtés widthM × depthM. */
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

describe('CAL102 — segmentDistanceM / cumulativeDistanceM', () => {
  it('une mesure posée sur un côté du bâtiment donne la MÊME longueur que le tracé du toit, à 1 % près', () => {
    const ring = rectRing(12, 8);
    // Le côté sud du rectangle = ring[0] → ring[1] (12 m).
    const measured = segmentDistanceM(ring[0], ring[1]);
    expect(Math.abs(measured - 12) / 12).toBeLessThan(0.01);
    // Vérifié aussi contre le périmètre de l'ATELIER lui-même (geodesicPerimeterM),
    // jamais une formule dupliquée qui pourrait diverger en silence.
    const perim = geodesicPerimeterM(ring);
    const cumul = cumulativeDistanceM(ring.concat([ring[0]])); // même contour, en polyligne fermée
    expect(cumul).toBeCloseTo(perim, 6);
  });

  it('distance cumulée sur PLUSIEURS points = somme des segments, pas la distance à vol d’oiseau', () => {
    const ring = rectRing(12, 8);
    const twoSides = cumulativeDistanceM([ring[0], ring[1], ring[2]]); // sud puis est
    expect(twoSides).toBeCloseTo(segmentDistanceM(ring[0], ring[1]) + segmentDistanceM(ring[1], ring[2]), 6);
    expect(twoSides).toBeGreaterThan(segmentDistanceM(ring[0], ring[2])); // jamais la diagonale
  });

  it('moins de 2 points → 0 (rien à mesurer)', () => {
    expect(cumulativeDistanceM([])).toBe(0);
    expect(cumulativeDistanceM([[-7.6, 33.5]])).toBe(0);
  });
});

describe('CAL102 — polygonAreaM2', () => {
  it('réutilise EXACTEMENT geodesicAreaM2 — aucune formule dupliquée', () => {
    const ring = rectRing(10, 6);
    expect(polygonAreaM2(ring)).toBe(geodesicAreaM2(ring));
  });

  it('une mesure de surface posée sur le contour du toit donne la surface au sol projetée', () => {
    const ring = rectRing(12, 8);
    expect(polygonAreaM2(ring)).toBeCloseTo(96, -1); // 12×8=96 m², tolérance projection locale
  });
});

describe('CAL102 — vertexAngleDeg', () => {
  it('un angle droit (coin de rectangle) mesure ~90°', () => {
    const ring = rectRing(10, 6);
    // ring[0]→ring[1]→ring[2] : le coin au sommet 1 est un angle droit du rectangle.
    const angle = vertexAngleDeg([ring[0], ring[1], ring[2]]);
    expect(angle).toBeCloseTo(90, 0);
  });

  it('trois points alignés → 180°', () => {
    const ring = rectRing(10, 6);
    const mid: LngLat = [(ring[0][0] + ring[1][0]) / 2, (ring[0][1] + ring[1][1]) / 2];
    const angle = vertexAngleDeg([ring[0], mid, ring[1]]);
    expect(angle).toBeCloseTo(180, 0);
  });

  it('pas exactement 3 points → 0 (jamais un angle inventé)', () => {
    expect(vertexAngleDeg([[0, 0], [1, 1]])).toBe(0);
  });
});

describe('CAL102 — measureValue / isMeasureValid / formatMeasure', () => {
  it('measureValue route vers la bonne géométrie selon le genre', () => {
    const ring = rectRing(10, 6);
    expect(measureValue({ kind: 'distance', points: [ring[0], ring[1]] })).toBeCloseTo(segmentDistanceM(ring[0], ring[1]), 6);
    expect(measureValue({ kind: 'area', points: ring })).toBe(geodesicAreaM2(ring));
    expect(measureValue({ kind: 'angle', points: [ring[0], ring[1], ring[2]] })).toBeCloseTo(90, 0);
  });

  it('isMeasureValid refuse une mesure sous le minimum de points de son genre', () => {
    expect(isMeasureValid({ kind: 'distance', points: [[0, 0]] })).toBe(false);
    expect(isMeasureValid({ kind: 'distance', points: [[0, 0], [1, 1]] })).toBe(true);
    expect(isMeasureValid({ kind: 'area', points: [[0, 0], [1, 1]] })).toBe(false);
    expect(isMeasureValid({ kind: 'area', points: [[0, 0], [1, 1], [1, 0]] })).toBe(true);
    expect(isMeasureValid({ kind: 'angle', points: [[0, 0], [1, 1], [1, 0], [0, 1]] })).toBe(false);
  });

  it('formatMeasure affiche l’unité correcte par genre (m / m² / °)', () => {
    expect(formatMeasure({ kind: 'distance', points: [[0, 0], [0, 0.0001]] })).toMatch(/ m$/);
    expect(formatMeasure({ kind: 'area', points: [[0, 0], [0, 0.0001], [0.0001, 0.0001]] })).toMatch(/m²$/);
    expect(formatMeasure({ kind: 'angle', points: [[0, 0], [0, 0.0001], [0.0001, 0]] })).toMatch(/°$/);
  });
});

describe('CAL102 — createMesureUi (persistance)', () => {
  function minimalCtx(): Ctx {
    return {} as Ctx; // ctx.measurements est ABSENT au départ — jamais lu en aveugle
  }

  it('add() refuse une mesure géométriquement invalide (rien n’est posé)', () => {
    const ctx = minimalCtx();
    const ui = createMesureUi(ctx);
    const result = ui.add('area', [[0, 0], [1, 1]]); // 2 points, il en faut ≥ 3 pour une surface
    expect(result).toBeNull();
    expect(ui.list()).toHaveLength(0);
  });

  it('add() pose la mesure et list() la retrouve — id, genre et points intacts', () => {
    const ctx = minimalCtx();
    const ui = createMesureUi(ctx);
    const m = ui.add('distance', [[-7.6, 33.5], [-7.601, 33.5]], 'côté sud');
    expect(m).not.toBeNull();
    const found = ui.list();
    expect(found).toHaveLength(1);
    expect(found[0].label).toBe('côté sud');
    expect(found[0].points).toEqual([[-7.6, 33.5], [-7.601, 33.5]]);
  });

  it('les mesures se RECHARGENT avec le calepinage : ctx.measurements est la forme persistée', () => {
    const ctx = minimalCtx();
    const ui = createMesureUi(ctx);
    ui.add('distance', [[0, 0], [0, 1]]);
    // Un rechargement typique = un nouveau ctx hydraté avec le measurements sauvegardé.
    const reloaded: Ctx = { measurements: ctx.measurements } as Ctx;
    const ui2 = createMesureUi(reloaded);
    expect(ui2.list()).toHaveLength(1);
  });

  it('remove() retire une mesure par id ; clear() les retire toutes', () => {
    const ctx = minimalCtx();
    const ui = createMesureUi(ctx);
    const a = ui.add('distance', [[0, 0], [0, 1]])!;
    ui.add('distance', [[0, 0], [1, 0]]);
    expect(ui.remove(a.id)).toBe(true);
    expect(ui.list()).toHaveLength(1);
    ui.clear();
    expect(ui.list()).toHaveLength(0);
  });

  it('list() renvoie des COPIES : muter le retour ne touche pas le stockage vivant', () => {
    const ctx = minimalCtx();
    const ui = createMesureUi(ctx);
    ui.add('distance', [[0, 0], [0, 1]]);
    const found = ui.list();
    found[0].points.push([9, 9]);
    expect(ui.list()[0].points).toHaveLength(2);
  });
});

describe('CAL102 — session interactive (begin/addPoint/undoPoint/finish/cancel)', () => {
  function minimalCtx(): Ctx {
    return {} as Ctx;
  }

  it('hors session : isActive() faux, activeKind() null, addPoint()/undoPoint() sont des no-op', () => {
    const ui = createMesureUi(minimalCtx());
    expect(ui.isActive()).toBe(false);
    expect(ui.activeKind()).toBeNull();
    ui.addPoint([0, 0]); // ne doit rien lever ni rien poser
    ui.undoPoint();
    expect(ui.sessionPoints()).toEqual([]);
    expect(ui.list()).toHaveLength(0);
  });

  it('begin() ouvre une session, addPoint() l’alimente, sessionPoints() la reflète', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('distance');
    expect(ui.isActive()).toBe(true);
    expect(ui.activeKind()).toBe('distance');
    ui.addPoint([-7.6, 33.5]);
    ui.addPoint([-7.601, 33.5]);
    expect(ui.sessionPoints()).toEqual([[-7.6, 33.5], [-7.601, 33.5]]);
    expect(ui.list()).toHaveLength(0); // pas encore posée
  });

  it('finish() pose la mesure et referme la session quand elle est géométriquement valide', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('distance');
    ui.addPoint([0, 0]);
    ui.addPoint([0, 1]);
    const m = ui.finish('côté test');
    expect(m).not.toBeNull();
    expect(ui.list()).toHaveLength(1);
    expect(ui.isActive()).toBe(false); // session refermée
    expect(ui.sessionPoints()).toEqual([]);
  });

  it('finish() sur une session encore invalide GARDE la session ouverte (renvoie null, pose rien)', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('area'); // il faut ≥ 3 points
    ui.addPoint([0, 0]);
    ui.addPoint([0, 1]);
    const m = ui.finish();
    expect(m).toBeNull();
    expect(ui.isActive()).toBe(true); // toujours ouverte : l'utilisateur peut compléter
    expect(ui.sessionPoints()).toHaveLength(2);
    expect(ui.list()).toHaveLength(0);
  });

  it('un genre « angle » se plafonne à 3 points : un 4ᵉ point est ignoré', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('angle');
    ui.addPoint([0, 0]);
    ui.addPoint([1, 1]);
    ui.addPoint([1, 0]);
    ui.addPoint([9, 9]); // ignoré : déjà 3 points pour un angle
    expect(ui.sessionPoints()).toHaveLength(3);
  });

  it('undoPoint() retire le dernier point posé', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('distance');
    ui.addPoint([0, 0]);
    ui.addPoint([0, 1]);
    ui.undoPoint();
    expect(ui.sessionPoints()).toEqual([[0, 0]]);
  });

  it('begin() pendant une session en cours ABANDONNE la précédente sans rien poser (parité changement d’outil)', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('distance');
    ui.addPoint([0, 0]);
    ui.addPoint([0, 1]);
    ui.begin('area'); // change de genre avant de finir la distance
    expect(ui.activeKind()).toBe('area');
    expect(ui.sessionPoints()).toEqual([]);
    expect(ui.list()).toHaveLength(0);
  });

  it('cancel() abandonne la session en cours sans rien poser', () => {
    const ui = createMesureUi(minimalCtx());
    ui.begin('distance');
    ui.addPoint([0, 0]);
    ui.addPoint([0, 1]);
    ui.cancel();
    expect(ui.isActive()).toBe(false);
    expect(ui.sessionPoints()).toEqual([]);
    expect(ui.list()).toHaveLength(0);
  });
});

// CAL80/CAL81 — rotation LIBRE d'un panneau (ou d'une sélection) + aimantation/alignement en
// placement libre. Géométrie PURE (lib/freeLayout), testée hors DOM — même esprit que
// freePlacementPV30.test.ts : toit carré 20 m de côté, azimut 180° (u = est-ouest, s = nord-sud).
import { describe, expect, it } from 'vitest';
import {
  geomAxes,
  freeStateFrom,
  panelCornersUV,
  polyOverlap,
  polySeparation,
  checkPanelRotation,
  rotateFreePanels,
  snapCandidateForPanel,
  alignPanels,
  distributePanels,
  type FreeGeom,
  type FreeLayoutState,
} from '../src/lib/freeLayout';

const SQUARE: [number, number][] = [
  [-10, -10],
  [10, -10],
  [10, 10],
  [-10, 10],
];

function geom(over: Partial<FreeGeom> = {}): FreeGeom {
  const { u, s } = geomAxes(180);
  return { u, s, widthM: 2, depthM: 1, ringENU: SQUARE, obstacles: [], ...over };
}
const NO_MARGIN = { setbackM: 0, gapM: 0 };
const withPanels = (...p: { cx: number; cy: number; angleDeg?: number }[]): FreeLayoutState => freeStateFrom(p);

describe('CAL80 — panelCornersUV', () => {
  it('angle 0 → un rectangle axé de dimensions widthM × depthM centré en (cu, cv)', () => {
    const g = geom();
    const corners = panelCornersUV(g, 5, 3, 0);
    expect(corners).toHaveLength(4);
    const us = corners.map((c) => c[0]);
    const vs = corners.map((c) => c[1]);
    expect(Math.min(...us)).toBeCloseTo(5 - 1, 9); // widthM/2 = 1
    expect(Math.max(...us)).toBeCloseTo(5 + 1, 9);
    expect(Math.min(...vs)).toBeCloseTo(3 - 0.5, 9); // depthM/2 = 0.5
    expect(Math.max(...vs)).toBeCloseTo(3 + 0.5, 9);
  });

  it('rotation à 90° échange largeur et profondeur (aux arrondis près)', () => {
    const g = geom();
    const corners = panelCornersUV(g, 0, 0, 90);
    const us = corners.map((c) => c[0]);
    const vs = corners.map((c) => c[1]);
    expect(Math.max(...us) - Math.min(...us)).toBeCloseTo(g.depthM, 9);
    expect(Math.max(...vs) - Math.min(...vs)).toBeCloseTo(g.widthM, 9);
  });
});

describe('CAL80 — polyOverlap / polySeparation (SAT)', () => {
  it('deux panneaux AXÉS (angle 0) loin l’un de l’autre : aucun recouvrement, séparation mesurée', () => {
    const g = geom();
    const a = panelCornersUV(g, 0, 0, 0);
    const b = panelCornersUV(g, 5, 0, 0);
    expect(polyOverlap(a, b)).toBe(false);
    expect(polySeparation(a, b)).toBeCloseTo(5 - 1 - 1, 6); // 5 − widthM/2 − widthM/2
  });

  it('deux panneaux qui se touchent PILE (bord à bord) ne se recouvrent pas', () => {
    const g = geom();
    const a = panelCornersUV(g, 0, 0, 0);
    const b = panelCornersUV(g, 2, 0, 0); // widthM=2 → bord à bord exact
    expect(polyOverlap(a, b)).toBe(false);
    expect(polySeparation(a, b)).toBeCloseTo(0, 6);
  });

  it('deux panneaux qui se chevauchent réellement → recouvrement détecté', () => {
    const g = geom();
    const a = panelCornersUV(g, 0, 0, 0);
    const b = panelCornersUV(g, 0.5, 0, 0);
    expect(polyOverlap(a, b)).toBe(true);
  });

  it('une rotation qui rapproche deux coins peut créer un recouvrement qu’un test axé raterait', () => {
    const g = geom();
    const a = panelCornersUV(g, 0, 0, 45);
    const b = panelCornersUV(g, 1.3, 1.3, 45); // proche en diagonale, aligné par la même rotation
    expect(polyOverlap(a, b)).toBe(true);
  });
});

describe('CAL80 — checkPanelRotation / rotateFreePanels', () => {
  it('rotation SANS conflit (panneau seul, loin du bord) → acceptée, angle persisté', () => {
    const g = geom();
    const state = withPanels({ cx: 0, cy: 0 });
    const res = rotateFreePanels(state, g, [0], 30, NO_MARGIN);
    expect(res.ok).toBe(true);
    expect(state.panels[0].angleDeg).toBe(30);
  });

  it('rotation qui ferait chevaucher un AUTRE panneau → refusée, RIEN n’a bougé', () => {
    const g = geom();
    // Deux panneaux bord à bord (axés) : les tourner ferait chevaucher leurs coins.
    const state = withPanels({ cx: 0, cy: 0 }, { cx: 2, cy: 0 });
    const before = JSON.stringify(state);
    const res = rotateFreePanels(state, g, [0], 45, NO_MARGIN);
    expect(res.ok).toBe(false);
    expect(res.blocked?.violations).toContain('overlap');
    expect(JSON.stringify(state)).toBe(before); // tout ou rien
  });

  it('rotation qui sortirait du contour (panneau collé au bord) → refusée', () => {
    const g = geom();
    const state = withPanels({ cx: 9.4, cy: 0 }); // à 0,6 m du bord est (largeur 2 → dépasse en tournant)
    const res = rotateFreePanels(state, g, [0], 45, NO_MARGIN);
    expect(res.ok).toBe(false);
    expect(res.blocked?.violations).toContain('outline');
  });

  it('une contrainte RELÂCHABLE (retrait/écart) seule ne bloque PAS la rotation — seul un chevauchement RÉEL refuse', () => {
    const g = geom();
    const state = withPanels({ cx: 0, cy: 0 });
    const strictMargins = { setbackM: 5, gapM: 5 }; // retrait bien plus grand que la place dispo
    const res = rotateFreePanels(state, g, [0], 30, strictMargins);
    expect(res.ok).toBe(true); // pas de chevauchement réel → acceptée malgré la marge
  });

  it('rotation d’un GROUPE : chaque membre tourne autour de son PROPRE centre, tout ou rien', () => {
    const g = geom();
    const state = withPanels({ cx: -3, cy: 0 }, { cx: 3, cy: 0 });
    const res = rotateFreePanels(state, g, [0, 1], 20, NO_MARGIN);
    expect(res.ok).toBe(true);
    expect(state.panels[0].angleDeg).toBe(20);
    expect(state.panels[1].angleDeg).toBe(20);
  });
});

describe('CAL81 — aimantation (arêtes de toit / faîtage / autres panneaux)', () => {
  it('un panneau glissé près du bord du toit s’aimante dessus (dans le seuil)', () => {
    const g = geom();
    const state = withPanels({ cx: 0, cy: 0 });
    // Bord est du toit à u=10 ; on vise un centre à u=8.85 (à 15 cm du contact bord-à-bord u=9).
    const snapped = snapCandidateForPanel(state, g, 0, 8.85, 0, 0.2);
    expect(snapped.cu).toBeCloseTo(9, 6); // collé au bord (demi-largeur 1 → bord du panneau à 10)
  });

  it('hors du seuil d’aimantation, la position demandée n’est PAS modifiée', () => {
    const g = geom();
    const state = withPanels({ cx: 0, cy: 0 });
    const snapped = snapCandidateForPanel(state, g, 0, 5, 0, 0.2);
    expect(snapped.cu).toBeCloseTo(5, 6);
    expect(snapped.snapped).toBe(false);
  });

  it('un panneau glissé près d’un AUTRE panneau s’aimante à son bord', () => {
    const g = geom();
    const state = withPanels({ cx: 0, cy: 0 }, { cx: 5, cy: 0 });
    // Le panneau 1 (déplacé) visé à cu=1.9, à 0,1 m de la cible bord-à-bord (u=2).
    const snapped = snapCandidateForPanel(state, g, 1, 1.9, 0, 0.2);
    expect(snapped.cu).toBeCloseTo(2, 6); // bord à bord : 1 (bord de 0) + widthM/2 (1) = 2
  });
});

describe('CAL81 — aligner / distribuer une sélection', () => {
  it('« aligner » cale tous les membres sur la coordonnée v du PREMIER (une rangée droite)', () => {
    const g = geom();
    const state = withPanels({ cx: -6, cy: 0.3 }, { cx: 0, cy: -0.4 }, { cx: 6, cy: 0.1 });
    const res = alignPanels(state, g, [0, 1, 2], 'row', NO_MARGIN);
    expect(res.ok).toBe(true);
    const vs = state.panels.map((p) => p.cy);
    expect(vs[0]).toBeCloseTo(vs[1], 6);
    expect(vs[1]).toBeCloseTo(vs[2], 6);
  });

  it('« distribuer » répartit à écart ÉGAL entre les deux extrêmes, sans chevauchement', () => {
    const g = geom();
    const state = withPanels({ cx: -6, cy: 0 }, { cx: -1, cy: 0 }, { cx: 6, cy: 0 });
    const res = distributePanels(state, g, [0, 1, 2], NO_MARGIN);
    expect(res.ok).toBe(true);
    const us = state.panels.map((p) => p.cx).sort((a, b) => a - b);
    expect(us[0]).toBeCloseTo(-6, 6); // les deux extrêmes ne bougent pas
    expect(us[2]).toBeCloseTo(6, 6);
    expect(us[1] - us[0]).toBeCloseTo(us[2] - us[1], 6); // écart égal
  });
});

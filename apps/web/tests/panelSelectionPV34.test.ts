// PV34 — SÉLECTION FACILE + DÉPLACEMENT DE GROUPE (ordre du fondateur, 25/08 :
// « i cannot select a group of pannels or a raw … the selection should be made easy
// and also once we select the pannels it should be easier and more natural to drag
// them »).
//
// Ce fichier verrouille la GÉOMÉTRIE PURE des nouveaux gestes — la seule part testable
// hors navigateur :
//   1. le cadre attrape les panneaux TRAVERSÉS (et plus seulement ceux dont le centre
//      tombe dedans) : c'est ce qui rendait « encadrer une rangée » impossible ;
//   2. l'accumulation de la sélection (clic nu / ajout au cadre / Ctrl+clic) ;
//   3. la rangée en un geste, sur un toit dont les rangées NE SONT PAS alignées au nord ;
//   4. la zone de calepinage qui arbitre « cadre de sélection » vs « déplacement de carte » ;
//   5. `planGroupMove` : l'aperçu vivant calcule EXACTEMENT ce que `moveGroup` committera,
//      sans jamais muter l'état.
//
// Le geste lui-même (pointeur sur la carte, cadre peint en surcouche DOM, re-rendu 3D à
// chaque image) demande une vraie carte MapLibre + WebGL : il relève de l'e2e.
import { describe, expect, it } from 'vitest';
import { geomAxes } from '../src/lib/freeLayout';
import {
  applySelectionGesture,
  centerInRect,
  normalizeSelectRect,
  panelCrossesRect,
  panelsCrossingRect,
  pointInLayoutArea,
  rowMembersOf,
  type PanelFootprint,
} from '../src/lib/panelSelection';
import { createLayoutState, moveGroup, planGroupMove } from '../src/lib/layoutVariability';

// Panneau 2 m (axe u) × 1 m d'empreinte au sol (axe s), azimut 180° → u ≈ est, s ≈ sud.
function footprint(azimuthDeg = 180, widthM = 2, depthM = 1): PanelFootprint {
  const { u, s } = geomAxes(azimuthDeg);
  return { u, s, widthM, depthM };
}

// Une rangée de 4 panneaux alignés est-ouest, centres espacés de 2 m, à y = 0.
const ROW = [
  { cx: 0, cy: 0 },
  { cx: 2, cy: 0 },
  { cx: 4, cy: 0 },
  { cx: 6, cy: 0 },
];

describe('PV34 — le cadre attrape ce qu’il TRAVERSE', () => {
  it('un cadre qui effleure la rangée SANS avaler aucun centre la prend quand même', () => {
    // Bande fine posée au-dessus de la ligne des centres : elle mord les panneaux
    // (demi-profondeur 0,5 m) sans contenir un seul centre. C'est LE geste qui ne
    // sélectionnait rien avant PV34.
    const rect = normalizeSelectRect(-1, 0.2, 7, 0.4);
    expect(ROW.filter((p) => centerInRect(p, rect))).toHaveLength(0);
    expect(panelsCrossingRect(ROW, rect, footprint())).toEqual([0, 1, 2, 3]);
  });

  it('un cadre franchement à côté n’attrape rien', () => {
    const rect = normalizeSelectRect(-1, 3, 7, 4); // 2,5 m au-dessus du bord des panneaux
    expect(panelsCrossingRect(ROW, rect, footprint())).toEqual([]);
  });

  it('un cadre partiel ne prend que les panneaux qu’il touche', () => {
    // De x = -1 à x = 2,5 : touche les panneaux 0 et 1 (bords ±1 m autour du centre),
    // et effleure le 2 (bord gauche à x = 3) ? non : 2,5 < 3 → pas de contact.
    const rect = normalizeSelectRect(-1, -0.4, 2.5, 0.4);
    expect(panelsCrossingRect(ROW, rect, footprint())).toEqual([0, 1]);
  });

  it('le sens du geste n’a aucune importance (coins normalisés)', () => {
    const a = normalizeSelectRect(-1, 0.2, 7, 0.4);
    const b = normalizeSelectRect(7, 0.4, -1, 0.2);
    expect(panelsCrossingRect(ROW, b, footprint())).toEqual(panelsCrossingRect(ROW, a, footprint()));
  });

  it('un simple CONTACT au bord compte comme une traversée (jamais raté d’un centimètre)', () => {
    // Bord droit du panneau 0 exactement à x = 1 ; le cadre démarre à x = 1.
    const rect = normalizeSelectRect(1, -0.4, 1.5, 0.4);
    expect(panelCrossesRect(ROW[0], rect, footprint())).toBe(true);
  });

  it('sans empreinte exploitable, on retombe EXACTEMENT sur le critère historique « centre dedans »', () => {
    const rect = normalizeSelectRect(-1, 0.2, 7, 0.4);
    expect(panelsCrossingRect(ROW, rect, null)).toEqual([]);
    const large = normalizeSelectRect(-1, -1, 3, 1);
    expect(panelsCrossingRect(ROW, large, null)).toEqual([0, 1]);
    // Empreinte dégénérée (plan sans dimensions) → même repli, jamais un plantage.
    expect(panelsCrossingRect(ROW, rect, { ...footprint(), widthM: 0 })).toEqual([]);
  });

  it('un toit en biais : le cadre suit l’emprise ORIENTÉE du panneau, pas une boîte nord-sud', () => {
    const fp = footprint(135); // rangées à 45°
    const p = { cx: 0, cy: 0 };
    // Cadre minuscule décalé le long de l'axe LONG du panneau (u) : traversé.
    const alongU = normalizeSelectRect(0.55, 0.55, 0.65, 0.65);
    // Même distance mais le long de l'axe COURT (s) : hors du panneau.
    const alongS = normalizeSelectRect(0.55, -0.65, 0.65, -0.55);
    expect(panelCrossesRect(p, alongU, fp)).toBe(true);
    expect(panelCrossesRect(p, alongS, fp)).toBe(false);
  });
});

describe('PV34 — accumulation de la sélection', () => {
  it('clic nu = remplace ; cadre + modificateur = ajoute ; Ctrl+clic = bascule', () => {
    expect(applySelectionGesture([1, 2], [5], 'replace')).toEqual([5]);
    expect(applySelectionGesture([1, 2], [5, 6], 'add')).toEqual([1, 2, 5, 6]);
    expect(applySelectionGesture([1, 2, 5], [5], 'toggle')).toEqual([1, 2]);
    expect(applySelectionGesture([1, 2], [5], 'toggle')).toEqual([1, 2, 5]);
  });

  it('le résultat est toujours dédoublonné et trié (l’ordre des gestes ne fuit pas)', () => {
    expect(applySelectionGesture([], [3, 1, 3, 2], 'replace')).toEqual([1, 2, 3]);
    expect(applySelectionGesture([9], [2, 2], 'add')).toEqual([2, 9]);
  });

  it('ajouter un lot déjà présent ne retire rien (« add » n’est pas « toggle »)', () => {
    expect(applySelectionGesture([1, 2], [1, 2], 'add')).toEqual([1, 2]);
  });
});

describe('PV34 — la rangée en un geste', () => {
  const GRID = [
    { cx: 0, cy: 0 },
    { cx: 2, cy: 0 },
    { cx: 4, cy: 0 },
    { cx: 0, cy: 1.5 },
    { cx: 2, cy: 1.5 },
  ];

  it('prend toute la rangée du panneau visé, et elle seule', () => {
    expect(rowMembersOf(GRID, 1, footprint())).toEqual([0, 1, 2]);
    expect(rowMembersOf(GRID, 4, footprint())).toEqual([3, 4]);
  });

  it('un index hors liste ne renvoie rien (jamais une sélection fantôme)', () => {
    expect(rowMembersOf(GRID, 99, footprint())).toEqual([]);
    expect(rowMembersOf(GRID, -1, footprint())).toEqual([]);
  });

  it('sur un toit en biais, la rangée suit l’axe d’EMPILEMENT du pavage', () => {
    const fp = footprint(135); // s = [sin135, cos135] ≈ [0.707, -0.707]
    // Deux panneaux alignés le long de u (donc MÊME rangée) et un décalé selon s.
    const biais = [
      { cx: 0, cy: 0 },
      { cx: -2 * Math.SQRT1_2, cy: -2 * Math.SQRT1_2 }, // + 2 m le long de u
      { cx: 1.5 * Math.SQRT1_2, cy: -1.5 * Math.SQRT1_2 }, // + 1,5 m le long de s
    ];
    expect(rowMembersOf(biais, 0, fp)).toEqual([0, 1]);
    // Le critère naïf « même cy » se tromperait ici : les trois ont des cy différents.
    expect(new Set(biais.map((p) => p.cy)).size).toBe(3);
  });
});

describe('PV34 — zone de calepinage (cadre de sélection vs déplacement de carte)', () => {
  it('un point sur la zone des panneaux y est, un point loin n’y est pas', () => {
    expect(pointInLayoutArea(ROW, 3, 0, 1)).toBe(true);
    expect(pointInLayoutArea(ROW, 50, 50, 1)).toBe(false);
  });

  it('la marge élargit la zone d’exactement ce qu’on lui donne', () => {
    expect(pointInLayoutArea(ROW, -0.5, 0, 0)).toBe(false);
    expect(pointInLayoutArea(ROW, -0.5, 0, 1)).toBe(true);
  });

  it('aucun panneau posé → aucune zone : la carte garde tous ses gestes', () => {
    expect(pointInLayoutArea([], 0, 0, 5)).toBe(false);
  });
});

describe('PV34 — planGroupMove : l’aperçu calcule ce que le commit fera, sans muter', () => {
  // Lattice 3×2 : pas 2 m en x, 1,5 m en y. Les 3 premières cellules occupées.
  const CELLS = [
    { cx: 0, cy: 0 },
    { cx: 2, cy: 0 },
    { cx: 4, cy: 0 },
    { cx: 0, cy: 1.5 },
    { cx: 2, cy: 1.5 },
    { cx: 4, cy: 1.5 },
  ];

  it('le plan ne touche PAS à l’occupation ; le commit donne les mêmes cibles', () => {
    const state = createLayoutState(CELLS, 3);
    const before = [...state.occupied].sort((a, b) => a - b);
    const plan = planGroupMove(state, [0, 1, 2], 0, 1.5, { maxSnapM: 1 });
    expect(plan.ok).toBe(true);
    expect(plan.targets).toEqual([3, 4, 5]);
    expect(plan.members).toEqual([0, 1, 2]);
    expect([...state.occupied].sort((a, b) => a - b)).toEqual(before); // rien n'a bougé
    const res = moveGroup(state, [0, 1, 2], 0, 1.5, { maxSnapM: 1 });
    expect(res.ok).toBe(true);
    expect(res.targets).toEqual(plan.targets);
    expect([...state.occupied].sort((a, b) => a - b)).toEqual([3, 4, 5]);
  });

  it('un refus est un refus des DEUX côtés, et n’altère rien', () => {
    const state = createLayoutState(CELLS, 3);
    const plan = planGroupMove(state, [0, 1, 2], 100, 0, { maxSnapM: 1 });
    expect(plan.ok).toBe(false);
    expect(plan.targets).toEqual([]);
    expect(plan.members).toEqual([]);
    expect([...state.occupied].sort((a, b) => a - b)).toEqual([0, 1, 2]);
    expect(moveGroup(state, [0, 1, 2], 100, 0, { maxSnapM: 1 }).ok).toBe(false);
    expect([...state.occupied].sort((a, b) => a - b)).toEqual([0, 1, 2]);
  });

  it('un membre non posé refuse tout le lot (non-régression du tout-ou-rien)', () => {
    const state = createLayoutState(CELLS, 3);
    const plan = planGroupMove(state, [0, 5], 0, 1.5, { maxSnapM: 1 });
    expect(plan.ok).toBe(false);
    expect(plan.reason).toBe('not-occupied');
  });

  it('appeler le plan deux fois de suite donne le même résultat (aucun effet de bord)', () => {
    const state = createLayoutState(CELLS, 3);
    const a = planGroupMove(state, [0, 1, 2], 0, 1.5, { maxSnapM: 1 });
    const b = planGroupMove(state, [0, 1, 2], 0, 1.5, { maxSnapM: 1 });
    expect(b.targets).toEqual(a.targets);
  });
});

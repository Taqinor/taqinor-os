// Tests PURS de la VARIABILITÉ de disposition (W69, « Personnaliser la disposition ») de
// l'estimateur pro-11. Aucun DOM, aucune 3D : on vérifie que la lattice = les cellules
// DÉJÀ validées par le pavage (valides par construction), que le SNAP n'atterrit que sur
// une cellule VIDE valide, que les cibles invalides (hors lattice, occupées) sont rejetées,
// que add/remove changent le comptage en respectant le plafond, que la réinit restaure
// l'optimum, et que l'invariant (footprint/besoin) tient — le rendement par panneau ne
// dépendant PAS de la position (recompute par comptage côté appelant).
import { describe, expect, it } from 'vitest';
import {
  buildLattice,
  createLayoutState,
  occupiedCount,
  occupiedIndices,
  emptyIndices,
  isLatticeCell,
  isValidEmptyTarget,
  nearestCell,
  nearestEmptyCell,
  movePanelToPoint,
  movePanelToCell,
  addPanel,
  addFirstEmpty,
  removePanel,
  removeLast,
  resetToOptimal,
  layoutIsValid,
  type PackedLike,
} from '../src/lib/layoutVariability';
import { packConfig } from '../src/lib/estimatorBrainV2';
import type { LngLat } from '../src/lib/roof';

// Une grille 4×3 de cellules régulières (1 m de pas) pour les tests déterministes.
function gridCells(cols: number, rows: number): PackedLike[] {
  const out: PackedLike[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) out.push({ cx: c, cy: r });
  return out;
}

describe('W69 — lattice = cellules valides par construction (issues du pavage)', () => {
  it('un vrai pavage estimatorBrainV2 fournit la lattice (toutes cellules valides)', () => {
    // toit 12 m × 10 m → plusieurs panneaux ; chaque PackedPanel est dans le polygone,
    // dans le retrait, hors obstacle (garanti par packCells).
    const ring: LngLat[] = [
      [-7.6, 33.5],
      [-7.6 + 12 / 92000, 33.5],
      [-7.6 + 12 / 92000, 33.5 + 10 / 111000],
      [-7.6, 33.5 + 10 / 111000],
    ];
    const pack = packConfig(ring, 33.5, { family: 'south', tiltDeg: 15 });
    const lattice = buildLattice(pack.best.panels);
    expect(lattice.length).toBe(pack.best.panels.length);
    expect(lattice.length).toBeGreaterThan(0);
    // les index sont stables 0..n-1
    lattice.forEach((c, i) => expect(c.index).toBe(i));
  });
});

describe('W69 — état initial : les N premières cellules occupées (disposition optimale)', () => {
  const cells = gridCells(4, 3); // 12 cellules
  it('createLayoutState occupe exactement initialCount cellules', () => {
    const s = createLayoutState(cells, 7);
    expect(occupiedCount(s)).toBe(7);
    expect(occupiedIndices(s)).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(emptyIndices(s)).toEqual([7, 8, 9, 10, 11]);
  });
  it('initialCount borné à [0, length]', () => {
    expect(occupiedCount(createLayoutState(cells, 99))).toBe(12);
    expect(occupiedCount(createLayoutState(cells, -3))).toBe(0);
  });
});

describe('W69 — SNAP : un déplacement n’atterrit que sur une cellule VIDE valide', () => {
  const cells = gridCells(4, 3);

  it('nearestEmptyCell trouve la cellule vide la plus proche d’un point', () => {
    const s = createLayoutState(cells, 6); // 0..5 occupées, 6..11 vides
    // point proche de la cellule 6 (cx=2, cy=1)
    expect(nearestEmptyCell(s, 2.1, 1.0)).toBe(6);
    // point hors toit (loin) → quand même snap à la cellule vide la plus proche
    expect(nearestEmptyCell(s, 99, 99)).toBe(11); // coin le plus proche du point lointain
  });

  it('movePanelToPoint snappe vers une cellule vide ; jamais hors lattice', () => {
    const s = createLayoutState(cells, 6);
    const before = occupiedCount(s);
    const res = movePanelToPoint(s, 0, 3.0, 2.0); // déplace le panneau 0 vers le coin (3,2)=cellule 11
    expect(res.ok).toBe(true);
    expect(isValidEmptyTarget(createLayoutState(cells, 0), res.toIndex)).toBe(true); // c’est une cellule réelle
    expect(s.occupied.has(res.toIndex)).toBe(true);
    expect(s.occupied.has(0)).toBe(false); // l’ancienne cellule est libérée
    expect(occupiedCount(s)).toBe(before); // le comptage ne change pas (déplacement)
    expect(layoutIsValid(s)).toBe(true);
  });

  it('toit PLEIN : un déplacement ne peut aller nulle part → snap-back (rien ne bouge)', () => {
    const s = createLayoutState(cells, 12); // toutes occupées
    const res = movePanelToPoint(s, 0, 3.0, 2.0);
    expect(res.ok).toBe(false);
    expect(res.toIndex).toBe(0); // remis sur place
    expect(s.occupied.has(0)).toBe(true);
    expect(occupiedCount(s)).toBe(12);
  });
});

describe('W69 — cibles invalides rejetées (hors polygone/lattice, occupées)', () => {
  const cells = gridCells(4, 3);

  it('movePanelToCell rejette une cible HORS lattice', () => {
    const s = createLayoutState(cells, 6);
    expect(movePanelToCell(s, 0, 999).ok).toBe(false); // index inexistant
    expect(movePanelToCell(s, 0, -1).ok).toBe(false);
    expect(s.occupied.has(0)).toBe(true); // inchangé
  });

  it('movePanelToCell rejette une cible OCCUPÉE', () => {
    const s = createLayoutState(cells, 6); // 0..5 occupées
    expect(movePanelToCell(s, 0, 3).ok).toBe(false); // 3 est occupée
    expect(occupiedCount(s)).toBe(6);
  });

  it('movePanelToCell accepte une cible VIDE valide', () => {
    const s = createLayoutState(cells, 6);
    const res = movePanelToCell(s, 0, 8); // 8 est vide
    expect(res.ok).toBe(true);
    expect(s.occupied.has(8)).toBe(true);
    expect(s.occupied.has(0)).toBe(false);
  });

  it('isValidEmptyTarget : seul un index existant ET vide passe', () => {
    const s = createLayoutState(cells, 6);
    expect(isValidEmptyTarget(s, 7)).toBe(true);
    expect(isValidEmptyTarget(s, 2)).toBe(false); // occupée
    expect(isValidEmptyTarget(s, 50)).toBe(false); // hors lattice
    expect(isLatticeCell(s, 11)).toBe(true);
    expect(isLatticeCell(s, 12)).toBe(false);
  });
});

describe('W69 — AJOUT / SUPPRESSION change le comptage (recompute par comptage côté appelant)', () => {
  const cells = gridCells(4, 3);

  it('addPanel occupe une cellule vide, monte le comptage', () => {
    const s = createLayoutState(cells, 6);
    const res = addPanel(s, 7);
    expect(res.ok).toBe(true);
    expect(res.count).toBe(7);
    expect(s.occupied.has(7)).toBe(true);
  });

  it('addPanel rejette une cellule occupée ou hors lattice', () => {
    const s = createLayoutState(cells, 6);
    expect(addPanel(s, 2).ok).toBe(false); // occupée
    expect(addPanel(s, 99).ok).toBe(false); // hors lattice
    expect(occupiedCount(s)).toBe(6);
  });

  it('addPanel respecte le plafond (besoin/footprint)', () => {
    const s = createLayoutState(cells, 6);
    expect(addPanel(s, 7, 6).ok).toBe(false); // cap atteint → refus
    expect(addPanel(s, 7, 8).ok).toBe(true); // sous le cap → ok
    expect(occupiedCount(s)).toBe(7);
  });

  it('addFirstEmpty occupe la première cellule vide', () => {
    const s = createLayoutState(cells, 6);
    expect(addFirstEmpty(s).count).toBe(7);
    expect(s.occupied.has(6)).toBe(true);
  });

  it('removePanel / removeLast baissent le comptage (jusqu’à 0 honnêtement)', () => {
    const s = createLayoutState(cells, 3);
    expect(removePanel(s, 1).count).toBe(2);
    expect(s.occupied.has(1)).toBe(false);
    expect(removeLast(s).ok).toBe(true); // enlève la plus haute occupée (2)
    expect(removeLast(s).ok).toBe(true); // enlève 0
    expect(occupiedCount(s)).toBe(0);
    expect(removeLast(s).ok).toBe(false); // plus rien à enlever
  });
});

describe('W69 — RÉINITIALISER restaure la disposition optimale', () => {
  const cells = gridCells(4, 3);
  it('resetToOptimal remet les N premières cellules occupées', () => {
    const s = createLayoutState(cells, 6);
    // bouge et ajoute du désordre
    movePanelToCell(s, 0, 9);
    addPanel(s, 7);
    resetToOptimal(s, 6);
    expect(occupiedIndices(s)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(layoutIsValid(s)).toBe(true);
  });
});

describe('W69 — invariants : footprint / besoin tiennent, comptage ≤ lattice', () => {
  const cells = gridCells(4, 3);
  it('le comptage ne dépasse jamais la lattice ni le plafond', () => {
    const s = createLayoutState(cells, 12);
    expect(layoutIsValid(s)).toBe(true);
    // on ne peut pas occuper plus que la lattice
    expect(addFirstEmpty(s).ok).toBe(false);
    expect(occupiedCount(s)).toBeLessThanOrEqual(cells.length);
    // sous un plafond donné, la validité le reflète
    const s2 = createLayoutState(cells, 5);
    expect(layoutIsValid(s2, 5)).toBe(true);
    expect(layoutIsValid(s2, 4)).toBe(false); // 5 occupés > cap 4
  });

  it('un déplacement préserve le comptage (même plan → même rendement/panneau)', () => {
    const s = createLayoutState(cells, 8);
    const n0 = occupiedCount(s);
    movePanelToPoint(s, 0, 0.1, 2.0);
    expect(occupiedCount(s)).toBe(n0); // SEUL le nombre change la production : ici inchangé
  });

  it('nearestCell renvoie -1 sur une lattice vide', () => {
    const s = createLayoutState([], 0);
    expect(nearestCell(s, 0, 0)).toBe(-1);
    expect(nearestEmptyCell(s, 0, 0)).toBe(-1);
  });
});

// W79 — re-snap d'une disposition personnalisée sur une NOUVELLE lattice (après l'édition
// d'un obstacle / d'un axe pendant que l'éditeur est ouvert) : c'est l'algorithme pur que
// reenterCustomLayout applique (capture des centres → rebuild de la lattice → re-snap au
// plus proche). Les panneaux survivent, re-snappés, jamais effacés.
describe('W79 — re-snap d\'une disposition après re-pavage (lattice changée)', () => {
  // Reproduit reenterCustomLayout en pur : centres posés + lattice fraîche → occupation.
  function reSnap(centers: { cx: number; cy: number }[], packed: PackedLike[]) {
    const st = createLayoutState(packed, 0); // lattice fraîche, rien d'occupé
    for (const c of centers) {
      const idx = nearestEmptyCell(st, c.cx, c.cy);
      if (idx >= 0) st.occupied.add(idx);
    }
    return st;
  }

  it('une pose personnalisée survit à un re-pavage IDENTIQUE (même comptage, mêmes cellules)', () => {
    const cells = gridCells(4, 3);
    const s = createLayoutState(cells, 12);
    // pose personnalisée non contiguë : on retire 2 panneaux du milieu
    removePanel(s, 5);
    removePanel(s, 6);
    const centers = occupiedIndices(s).map((i) => ({ cx: cells[i].cx, cy: cells[i].cy }));
    const re = reSnap(centers, gridCells(4, 3));
    expect(occupiedCount(re)).toBe(occupiedCount(s)); // 10 panneaux survivent
    // ce sont les MÊMES cellules (re-snap au plus proche sur une lattice identique).
    expect(occupiedIndices(re)).toEqual(occupiedIndices(s));
    expect(layoutIsValid(re)).toBe(true);
  });

  it('chaque panneau re-snappe vers une cellule VIDE valide (aucun doublon, jamais hors lattice)', () => {
    const cells = gridCells(4, 3);
    const s = createLayoutState(cells, 8);
    const centers = occupiedIndices(s).map((i) => ({ cx: cells[i].cx + 0.1, cy: cells[i].cy + 0.1 }));
    // re-pavage LÉGÈREMENT décalé (obstacle ajouté ailleurs) : la grille reste 4×3.
    const re = reSnap(centers, gridCells(4, 3));
    expect(occupiedCount(re)).toBe(8); // 8 panneaux, chacun sur une cellule distincte
    expect(new Set(occupiedIndices(re)).size).toBe(8); // pas de collision (cellule vide la + proche)
    expect(layoutIsValid(re)).toBe(true);
  });

  it('si le toit RÉTRÉCIT (moins de cellules), les panneaux en trop sont perdus honnêtement', () => {
    const before = gridCells(4, 3); // 12 cellules
    const s = createLayoutState(before, 12); // toutes occupées
    const centers = occupiedIndices(s).map((i) => ({ cx: before[i].cx, cy: before[i].cy }));
    // un obstacle réduit le toit à une grille 3×2 (6 cellules) : 6 panneaux au plus.
    const re = reSnap(centers, gridCells(3, 2));
    expect(occupiedCount(re)).toBeLessThanOrEqual(6); // jamais au-delà de ce qui tient
    expect(layoutIsValid(re)).toBe(true);
  });
});

// WJ20 — Tests PURS du remplissage automatique (« Remplir automatiquement ») de
// l'estimateur pro-11. La lattice EST le pavage géométrique validé par l'optimiseur
// (retraits de rive + zones d'obstacle déjà exclus). fillAll doit occuper CHAQUE cellule
// valide (le maximum qui tient) sans jamais dépasser la lattice — donc Σ empreintes ≤
// surface utile tient par construction. Aucun DOM, aucune 3D.
import { describe, expect, it } from 'vitest';
import {
  createLayoutState,
  fillAll,
  occupiedCount,
  emptyIndices,
  layoutIsValid,
  type PackedLike,
} from '../src/lib/layoutVariability';
import { packConfig } from '../src/lib/estimatorBrainV2';
import type { LngLat } from '../src/lib/roof';

function gridCells(cols: number, rows: number): PackedLike[] {
  const out: PackedLike[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) out.push({ cx: c, cy: r });
  return out;
}

describe('WJ20 — fillAll : remplissage automatique du toit', () => {
  it('occupe TOUTES les cellules de la lattice depuis un optimum partiel', () => {
    const state = createLayoutState(gridCells(4, 3), 3); // 12 cellules, 3 occupées
    expect(occupiedCount(state)).toBe(3);
    const r = fillAll(state);
    expect(r.ok).toBe(true);
    expect(r.count).toBe(12);
    expect(occupiedCount(state)).toBe(12);
    expect(emptyIndices(state).length).toBe(0);
  });

  it('ne dépasse JAMAIS la lattice (comptage ≤ cells.length) — borne empreinte', () => {
    const state = createLayoutState(gridCells(5, 4), 0); // 20 cellules
    const r = fillAll(state);
    expect(r.count).toBe(state.cells.length);
    expect(r.count).toBe(20);
    expect(layoutIsValid(state)).toBe(true);
  });

  it('est idempotent : un 2e remplissage n’ajoute rien (ok=false)', () => {
    const state = createLayoutState(gridCells(3, 3), 9); // déjà plein
    const r = fillAll(state);
    expect(r.ok).toBe(false);
    expect(r.count).toBe(9);
    expect(occupiedCount(state)).toBe(9);
  });

  it('lattice vide → aucun panneau, aucune erreur', () => {
    const state = createLayoutState([], 0);
    const r = fillAll(state);
    expect(r.ok).toBe(false);
    expect(r.count).toBe(0);
  });

  it('sur un vrai pavage estimatorBrainV2, fillAll = tous les emplacements pavés', () => {
    const ring: LngLat[] = [
      [-7.62, 33.59],
      [-7.6198, 33.59],
      [-7.6198, 33.5902],
      [-7.62, 33.5902],
    ];
    const pack = packConfig(ring, 33.59, { family: 'south', tiltDeg: 15 });
    const cells = pack.best.panels;
    const state = createLayoutState(cells, Math.min(2, cells.length));
    const r = fillAll(state);
    expect(r.count).toBe(cells.length); // tout ce qui tient physiquement
    expect(layoutIsValid(state)).toBe(true);
    // chaque index occupé est une vraie cellule pavée (valide par construction)
    for (const idx of state.occupied) {
      expect(idx).toBeGreaterThanOrEqual(0);
      expect(idx).toBeLessThan(cells.length);
    }
  });
});

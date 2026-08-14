// PV25 — SÉLECTION MULTIPLE + déplacement de GROUPE (tout ou rien) + déplacement de
// RANGÉE (contraint à son axe) + nudge d'azimut. Logique PURE (layoutVariability) : la
// sécurité vient de la lattice — on ne fait que changer des index de cellules VALIDES.
import { describe, expect, it } from 'vitest';
import {
  createLayoutState,
  cellsInRect,
  moveGroup,
  rowMembers,
  moveRowBy,
  nudgeAzimuthDeg,
  occupiedIndices,
  layoutIsValid,
  ROW_EPSILON_M,
} from '../src/lib/layoutVariability';

/** Lattice régulière 4 colonnes × 3 rangées, pas de 1 m (index = r * 4 + c). */
function grid(cols = 4, rows = 3, occupied = cols * rows) {
  const cells: { cx: number; cy: number }[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push({ cx: c, cy: r });
  return createLayoutState(cells, occupied);
}

describe('PV25 — sélection rectangulaire (marquee)', () => {
  it('ne retient que les panneaux dont le CENTRE est dans le rectangle', () => {
    const st = grid();
    // Rectangle sur la rangée du bas, colonnes 1 et 2.
    expect(cellsInRect(st, { x0: 0.5, y0: -0.5, x1: 2.5, y1: 0.5 })).toEqual([1, 2]);
  });

  it('accepte les coins dans n’importe quel ordre', () => {
    const st = grid();
    const a = cellsInRect(st, { x0: 2.5, y0: 0.5, x1: 0.5, y1: -0.5 });
    expect(a).toEqual([1, 2]);
  });

  it('ignore les emplacements LIBRES (on sélectionne des panneaux)', () => {
    const st = grid(4, 3, 4); // seule la rangée du bas est posée
    expect(cellsInRect(st, { x0: -1, y0: -1, x1: 5, y1: 5 })).toEqual([0, 1, 2, 3]);
    // …sauf si on demande explicitement toutes les cellules.
    expect(cellsInRect(st, { x0: -1, y0: -1, x1: 5, y1: 5 }, false).length).toBe(12);
  });

  it('rectangle vide → sélection vide', () => {
    expect(cellsInRect(grid(), { x0: 10, y0: 10, x1: 11, y1: 11 })).toEqual([]);
  });
});

describe('PV25 — déplacement de GROUPE : tout ou rien', () => {
  it('translate tout le groupe quand chaque membre a un emplacement valide', () => {
    const st = grid(4, 3, 4); // rangée du bas occupée (0,1,2,3)
    const res = moveGroup(st, [0, 1], 0, 1); // monte de 1 m → cellules 4 et 5
    expect(res.ok).toBe(true);
    expect(res.targets).toEqual([4, 5]);
    expect(occupiedIndices(st)).toEqual([2, 3, 4, 5]);
    expect(layoutIsValid(st)).toBe(true);
  });

  it('REFUSE tout le déplacement si UN membre n’a pas d’emplacement valide', () => {
    const st = grid(4, 3, 4);
    const before = occupiedIndices(st);
    // 10 m à droite : hors lattice → aucun membre ne trouve de cellule dans la tolérance.
    const res = moveGroup(st, [0, 1], 10, 0, { maxSnapM: 1 });
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('no-target');
    expect(occupiedIndices(st)).toEqual(before); // état INTACT
  });

  it('deux membres ne peuvent jamais atterrir sur la MÊME cellule', () => {
    const st = grid(4, 3, 12);
    const res = moveGroup(st, [0, 1, 2, 3], 0, 1);
    expect(res.ok).toBe(true);
    expect(new Set(res.targets).size).toBe(res.targets.length);
    expect(occupiedIndices(st).length).toBe(12); // aucun panneau perdu
  });

  it('un groupe peut glisser DANS ses propres cellules (elles se libèrent)', () => {
    const st = grid(4, 1, 4);
    st.occupied.delete(3); // la place à droite est libre
    const res = moveGroup(st, [0, 1, 2], 1, 0);
    expect(res.ok).toBe(true);
    expect(res.targets).toEqual([1, 2, 3]);
  });

  it('avec une tolérance, un groupe coincé est REFUSÉ au lieu de se replier n’importe où', () => {
    const st = grid(4, 1, 4); // rangée pleine : rien à droite
    const before = occupiedIndices(st);
    const res = moveGroup(st, [0, 1, 2], 1, 0, { maxSnapM: 1.5 });
    expect(res.ok).toBe(false);
    expect(occupiedIndices(st)).toEqual(before);
  });

  it('refuse un groupe vide, un membre non occupé, ou un delta non fini', () => {
    const st = grid(4, 3, 4);
    expect(moveGroup(st, [], 1, 0).ok).toBe(false);
    expect(moveGroup(st, [7], 1, 0).reason).toBe('not-occupied');
    expect(moveGroup(st, [0], Number.NaN, 0).ok).toBe(false);
    expect(occupiedIndices(st)).toEqual([0, 1, 2, 3]);
  });
});

describe('PV25 — déplacement de RANGÉE', () => {
  it('la rangée = les panneaux qui partagent la même coordonnée d’empilement', () => {
    const st = grid(4, 3, 12);
    expect(rowMembers(st, 0)).toEqual([0, 1, 2, 3]);
    expect(rowMembers(st, 5)).toEqual([4, 5, 6, 7]);
    expect(rowMembers(st, 99)).toEqual([]); // hors lattice
  });

  it('la tolérance de rangée regroupe des cy très proches, pas la rangée suivante', () => {
    const cells = [
      { cx: 0, cy: 0 },
      { cx: 1, cy: ROW_EPSILON_M / 2 }, // même rangée (bruit)
      { cx: 2, cy: 1 }, // rangée suivante
    ];
    const st = createLayoutState(cells, 3);
    expect(rowMembers(st, 0)).toEqual([0, 1]);
  });

  it('glisse la rangée le long de SON axe, sans dériver d’une rangée à l’autre', () => {
    const st = grid(4, 3, 12);
    // Libère la colonne 3 de la rangée du bas pour laisser de la place au décalage.
    st.occupied.delete(3);
    const res = moveRowBy(st, 0, 1);
    expect(res.ok).toBe(true);
    expect(res.targets).toEqual([1, 2, 3]);
    // Les rangées du dessus n'ont pas bougé.
    expect(rowMembers(st, 4)).toEqual([4, 5, 6, 7]);
  });

  it('rangée bloquée → RIEN ne bouge', () => {
    const st = grid(4, 3, 12); // tout est plein
    const before = occupiedIndices(st);
    const res = moveRowBy(st, 0, 1, { maxSnapM: 0.5 });
    expect(res.ok).toBe(false);
    expect(occupiedIndices(st)).toEqual(before);
  });
});

describe('PV25 — nudge d’azimut', () => {
  it('ajoute le delta et reste dans [0, 360)', () => {
    expect(nudgeAzimuthDeg(180, 1)).toBe(181);
    expect(nudgeAzimuthDeg(359.5, 1)).toBeCloseTo(0.5, 9);
    expect(nudgeAzimuthDeg(0, -1)).toBe(359);
    expect(nudgeAzimuthDeg(180, -0.5)).toBe(179.5); // JAMAIS arrondi à un pas imposé
  });

  it('entrée non finie → traitée comme 0, jamais NaN', () => {
    expect(nudgeAzimuthDeg(Number.NaN, 5)).toBe(5);
    expect(nudgeAzimuthDeg(90, Number.NaN)).toBe(90);
  });
});

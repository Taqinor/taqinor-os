// PV26 — ANNULER / RÉTABLIR par SNAPSHOTS. Pile d'occupations photographiées, tampon
// CIRCULAIRE (la plus ancienne est oubliée), pile « rétablir » vidée dès qu'une nouvelle
// action ouvre une branche. Module PUR : testé hors DOM.
import { describe, expect, it } from 'vitest';
import { createLayoutHistory, LAYOUT_HISTORY_LIMIT } from '../src/scripts/roofPro11/layoutHistory';

const set = (...v: number[]) => new Set(v);

describe('PV26 — pile d’annulation', () => {
  it('annule dans l’ordre inverse des actions', () => {
    const h = createLayoutHistory();
    h.push(set(0, 1)); // avant action 1
    h.push(set(0, 1, 2)); // avant action 2
    expect(h.canUndo()).toBe(true);
    expect(h.undo(set(0, 1, 2, 3))).toEqual([0, 1, 2]);
    expect(h.undo(set(0, 1, 2))).toEqual([0, 1]);
    expect(h.undo(set(0, 1))).toBeNull();
    expect(h.canUndo()).toBe(false);
  });

  it('rétablit ce qui vient d’être annulé', () => {
    const h = createLayoutHistory();
    h.push(set(0, 1));
    const undone = h.undo(set(0, 1, 2));
    expect(undone).toEqual([0, 1]);
    expect(h.canRedo()).toBe(true);
    expect(h.redo(set(0, 1))).toEqual([0, 1, 2]);
    expect(h.canRedo()).toBe(false);
    // …et l'aller-retour est de nouveau annulable.
    expect(h.canUndo()).toBe(true);
  });

  it('une NOUVELLE action vide la pile « rétablir »', () => {
    const h = createLayoutHistory();
    h.push(set(0));
    h.undo(set(0, 1));
    expect(h.canRedo()).toBe(true);
    h.push(set(0, 5)); // nouvelle branche
    expect(h.canRedo()).toBe(false);
    expect(h.size()).toEqual({ undo: 1, redo: 0 });
  });

  it('les photos sont des COPIES : muter l’état vivant ne réécrit pas l’historique', () => {
    const h = createLayoutHistory();
    const live = set(0, 1);
    h.push(live);
    live.add(2);
    live.delete(0);
    expect(h.undo(live)).toEqual([0, 1]); // la photo d'origine, intacte
  });

  it('photo TRIÉE et JSON-sûre (comparable, sérialisable)', () => {
    const h = createLayoutHistory();
    h.push(set(5, 1, 3));
    expect(h.undo(set())).toEqual([1, 3, 5]);
  });
});

describe('PV26 — tampon circulaire', () => {
  it('au-delà de la limite, la photo la PLUS ANCIENNE est oubliée', () => {
    const h = createLayoutHistory(3);
    for (let i = 0; i < 5; i++) h.push(set(i));
    expect(h.size().undo).toBe(3);
    // Il ne reste que les 3 dernières : 4, 3, 2 (dans cet ordre d'annulation).
    expect(h.undo(set(9))).toEqual([4]);
    expect(h.undo(set(9))).toEqual([3]);
    expect(h.undo(set(9))).toEqual([2]);
    expect(h.undo(set(9))).toBeNull();
  });

  it('la limite par défaut est bornée et une limite absurde retombe dessus', () => {
    expect(LAYOUT_HISTORY_LIMIT).toBeGreaterThan(0);
    const h = createLayoutHistory(Number.NaN);
    for (let i = 0; i < LAYOUT_HISTORY_LIMIT + 5; i++) h.push(set(i));
    expect(h.size().undo).toBe(LAYOUT_HISTORY_LIMIT);
  });

  it('clear() oublie les deux piles', () => {
    const h = createLayoutHistory();
    h.push(set(1));
    h.undo(set(1, 2));
    h.clear();
    expect(h.size()).toEqual({ undo: 0, redo: 0 });
    expect(h.canUndo()).toBe(false);
    expect(h.canRedo()).toBe(false);
  });

  it('annuler/rétablir sur une pile vide ne casse rien', () => {
    const h = createLayoutHistory();
    expect(h.undo(set(1))).toBeNull();
    expect(h.redo(set(1))).toBeNull();
  });
});

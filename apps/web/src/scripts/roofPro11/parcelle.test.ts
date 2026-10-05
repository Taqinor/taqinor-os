import { describe, expect, it, vi } from 'vitest';
import { createParcelleUi, lireParcelle, sommetParcelleAcceptable, validerParcelle } from './parcelle';
import { type Ctx } from './context';

const CARRE: Array<[number, number]> = [[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001]];

describe('ACAL233 — validation de la parcelle', () => {
  it('refuse moins de 3 sommets', () => {
    expect(validerParcelle([[0, 0], [1, 1]]).ok).toBe(false);
    expect(validerParcelle(CARRE).ok).toBe(true);
  });

  it('refuse un polygone croisé (nœud papillon) et le point qui le crée', () => {
    const papillon: Array<[number, number]> = [[0, 0], [1, 1], [1, 0], [0, 1]];
    expect(validerParcelle(papillon).ok).toBe(false);
    // 3 sommets déjà posés ; le 4e fait croiser le contour.
    expect(sommetParcelleAcceptable(papillon.slice(0, 3), [0, 1]).ok).toBe(false);
    expect(sommetParcelleAcceptable(CARRE.slice(0, 3), CARRE[3]).ok).toBe(true);
  });

  it('lireParcelle : absente ou inexploitable → null, jamais une parcelle inventée', () => {
    expect(lireParcelle({})).toBeNull();
    expect(lireParcelle({ parcelle: { vertices: [[0, 0], [1, 1]] } })).toBeNull();
    expect(lireParcelle({ parcelle: { vertices: CARRE } })?.vertices).toEqual(CARRE);
  });
});

describe('ACAL233 — la session de tracé', () => {
  const nouveau = () => {
    const ctx = {} as Ctx;
    const setStatus = vi.fn();
    return { ctx, setStatus, ui: createParcelleUi(ctx, { setStatus }) };
  };

  it('poser 4 sommets puis terminer écrit ctx.parcelle ; effacer la retire', () => {
    const { ctx, ui } = nouveau();
    ui.begin();
    for (const p of CARRE) expect(ui.addPoint(p)).toBe(true);
    expect(ui.finish().ok).toBe(true);
    expect(ctx.parcelle?.vertices).toEqual(CARRE);
    expect(ui.isActive()).toBe(false);
    ui.clear();
    expect(ctx.parcelle).toBeNull();
  });

  it('terminer sous 3 sommets est refusé sans rien écrire ; un point croisé n’est pas posé', () => {
    const { ctx, ui, setStatus } = nouveau();
    ui.begin();
    ui.addPoint([0, 0]);
    ui.addPoint([1, 1]);
    expect(ui.finish().ok).toBe(false);
    expect(ctx.parcelle).toBeUndefined();
    ui.addPoint([1, 0]);
    expect(ui.addPoint([0, 1])).toBe(false);
    expect(ui.sessionPoints()).toHaveLength(3);
    expect(setStatus).toHaveBeenCalled();
  });
});

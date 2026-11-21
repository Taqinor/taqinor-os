// ACAL584 — alignement des rangées par post-traitement du pavage (fonction pure, sans DOM).
import { describe, expect, it } from 'vitest';
import { alignerRangees } from './alignementRangees';
import { type FreeGeom } from '../../lib/freeLayout';

const W = 1.13;
/** Tronçon libre de 10,30 m (x de 0 à 10,30), 6 m de profondeur ; u = x, v = y. */
const geom = (obstacles: FreeGeom['obstacles'] = []): FreeGeom => ({
  u: [1, 0], s: [0, 1], widthM: W, depthM: 1,
  ringENU: [[0, -3], [10.3, -3], [10.3, 3], [0, 3]], obstacles,
});
const rangee = (n: number, x0 = W / 2, y = 0) => Array.from({ length: n }, (_, k) => ({ cx: x0 + k * W, cy: y }));
const bords = (p: { cx: number }[]) => ({ g: p[0].cx - W / 2, d: 10.3 - (p[p.length - 1].cx + W / 2) });

describe('ACAL584 — alignerRangees', () => {
  it('Centre : 9 modules jointifs de 1,13 m dans 10,30 m ⇒ 0,065 m de chaque côté (1 cm), compte constant', () => {
    const r = alignerRangees(geom(), rangee(9), 'centre');
    expect(r.panels).toHaveLength(9);
    const b = bords(r.panels);
    expect(Math.abs(b.g - 0.065)).toBeLessThan(0.01);
    expect(Math.abs(b.d - 0.065)).toBeLessThan(0.01);
    expect(r.immobiles).toEqual([]);
  });
  it('Droite colle la rangée au bout du tronçon', () => {
    const b = bords(alignerRangees(geom(), rangee(9), 'droite').panels);
    expect(b.d).toBeLessThan(0.01);
  });
  it('Justifié : premier et dernier aux bouts, jeux égaux', () => {
    const p = alignerRangees(geom(), rangee(5), 'justifie').panels;
    const b = bords(p);
    expect(b.g).toBeLessThan(0.01);
    expect(b.d).toBeLessThan(0.01);
    const jeux = p.slice(1).map((q, k) => q.cx - p[k].cx);
    for (const j of jeux) expect(j).toBeCloseTo(jeux[0], 6);
  });
  it('Gauche ⇒ positions identiques', () => {
    const p = rangee(4);
    expect(alignerRangees(geom(), p, 'gauche').panels).toEqual(p);
  });
  it('un obstacle bloque la translation ⇒ rangée en place + motif nommé', () => {
    const obs = [{ ring: [[9.9, -0.5], [10.2, -0.5], [10.2, 0.5], [9.9, 0.5]] as [number, number][], clearanceM: 0 }];
    const p = rangee(8); // se termine à 9,04 m ; 0,86 m jusqu'à l'obstacle
    const r = alignerRangees(geom(obs), p, 'droite');
    const b = bords(r.panels);
    expect(b.d).toBeGreaterThan(0.2); // bloqué avant le bout du tronçon, jamais dans l'obstacle
    expect(r.panels.every((q) => q.cx + W / 2 <= 9.9 + 1e-6)).toBe(true);
    const bloque = alignerRangees(geom(obs), rangee(9), 'justifie'); // 9 modules : jusqu'à 10,17 m, sur l'obstacle
    expect(bloque.immobiles[0]?.motif).toContain('rangée 1 : ne peut pas bouger');
    expect(bloque.panels).toEqual(rangee(9));
  });
  it('le décalage n’est pas arrondi au module (mutant)', () => {
    const r = alignerRangees(geom(), rangee(9), 'centre');
    expect(r.panels[0].cx - W / 2).not.toBe(0); // un décalage fin, pas un module entier
    expect(r.panels[0].cx - W / 2).toBeLessThan(W / 2);
  });
});

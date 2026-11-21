// ACAL579 — pieds du châssis de toit plat à la portée saisie (contrat ACAL587).
import { describe, expect, it } from 'vitest';
import { emettrePortee, jointuresPortantes, lirePortee, poserTrianglesDeRangee, validerPortee } from './piedsChassis';

const PAS = 1.15;
const rangee = (m: number, depart = 0) => Array.from({ length: m }, (_, i) => ({ la: depart + i * PAS, halfA: 0.565 }));
const compter = (row: { la: number; halfA: number }[], portee: number | null) => {
  const xs: number[] = [];
  poserTrianglesDeRangee(row, 0.25, portee, (xa) => xs.push(xa));
  return xs;
};

describe('ACAL579 — jointuresPortantes', () => {
  it('12 modules, pas 1,15 m, portée 2,4 m ⇒ jointures 0, 2, 4, 6, 8, 10, 12 (7)', () => {
    expect(jointuresPortantes(12, PAS, 2.4)).toEqual([0, 2, 4, 6, 8, 10, 12]);
    expect(compter(rangee(12), 2.4)).toHaveLength(7);
  });
  it('portée < pas ⇒ 13 ; sans portée ⇒ 13 (scène d’aujourd’hui, mêmes abscisses)', () => {
    expect(jointuresPortantes(12, PAS, 1)).toHaveLength(13);
    expect(jointuresPortantes(12, PAS, null)).toHaveLength(13);
    expect(compter(rangee(12), 1)).toEqual(compter(rangee(12), null));
    expect(compter(rangee(12), null)).toHaveLength(13);
  });
  it('tronçon interrompu ⇒ règle par tronçon (5 + 7 modules, portée 2,4 m : 4 + 5 pieds)', () => {
    const row = [...rangee(5), ...rangee(7, 5 * PAS + 3)];
    expect(compter(row, 2.4)).toHaveLength(4 + 5);
    expect(compter(row, null)).toHaveLength(6 + 8);
  });
  it('lecture, émission et saisie : valeur ≤ 0 ou source vide refusées en nommant le champ', () => {
    expect(lirePortee({ valeurM: 2.4, source: 'notice p. 4' })).toEqual({ valeurM: 2.4, source: 'notice p. 4' });
    expect(lirePortee({ valeurM: 0, source: 'x' })).toBeNull();
    expect(emettrePortee(undefined)).toEqual({});
    const r = validerPortee('0', 'notice');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.motif).toContain('Portée entre pieds (m)');
    const s = validerPortee('2,4', '');
    expect(s.ok).toBe(false);
    if (!s.ok) expect(s.motif).toContain('Source');
    expect(validerPortee('', '')).toEqual({ ok: true, portee: null });
  });
});

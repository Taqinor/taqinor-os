// ACAL728 — tri par ensoleillement : valeurs écrites à la main.
import { describe, expect, it } from 'vitest';
import { accesMoyenDuPan, mentionAcces, trierPansParAcces } from './triPans';

const pan = (id: string, values?: (number | null)[]) =>
  ({ id, geometrieEnregistree: values ? { solarAccess: { values } } : undefined }) as unknown as Parameters<typeof accesMoyenDuPan>[0] & { id: string };

describe('ACAL728 — trierPansParAcces', () => {
  it('0,62 / 0,91 / non calculé ⇒ 0,91, 0,62, puis le pan sans calcul', () => {
    const a = pan('a', [0.62]);
    const b = pan('b', [0.91]);
    const c = pan('c');
    expect(trierPansParAcces([a, c, b]).map((p) => p.id)).toEqual(['b', 'a', 'c']);
  });
  it('un null n’entre pas dans la moyenne (pas compté 0)', () => {
    expect(accesMoyenDuPan(pan('x', [0.8, null, 1]))).toBeCloseTo(0.9, 9);
    expect(accesMoyenDuPan(pan('x', [null, null]))).toBeNull();
    expect(trierPansParAcces([pan('n', [null]), pan('p', [0.1])]).map((p) => p.id)).toEqual(['p', 'n']);
  });
  it('le pan actif prend sa valeur vivante ; l’ordre d’origine est gardé à égalité', () => {
    const a = pan('a', [0.5]);
    const b = pan('b', [0.7]);
    expect(trierPansParAcces([a, b], (p) => (p === a ? 0.95 : null)).map((p) => p.id)).toEqual(['a', 'b']);
    expect(trierPansParAcces([pan('p', [0.5]), pan('q', [0.5])]).map((p) => p.id)).toEqual(['p', 'q']);
  });
  it('la mention dit le pourcentage ou « non calculé »', () => {
    expect(mentionAcces(0.91)).toBe('accès solaire 91 %');
    expect(mentionAcces(null)).toBe('non calculé');
  });
});

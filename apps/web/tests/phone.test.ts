import { describe, expect, it } from 'vitest';
import { normalizeMoroccanPhone } from '../src/lib/phone';

describe('normalizeMoroccanPhone', () => {
  it.each([
    ['0612345678', '+212612345678'],
    ['06 12 34 56 78', '+212612345678'],
    ['06-12-34-56-78', '+212612345678'],
    ['06.12.34.56.78', '+212612345678'],
    ['+212612345678', '+212612345678'],
    ['+212 6 12 34 56 78', '+212612345678'],
    ['00212612345678', '+212612345678'],
    ['212612345678', '+212612345678'],
    ['0712345678', '+212712345678'],
    ['0522123456', '+212522123456'],
    ['(06) 12 34 56 78', '+212612345678'],
  ])('normalise %s → %s', (input, expected) => {
    const r = normalizeMoroccanPhone(input);
    expect(r.ok).toBe(true);
    expect(r.e164).toBe(expected);
  });

  it.each([
    [''],
    ['abc'],
    ['061234567'], // trop court
    ['06123456789'], // trop long
    ['0812345678'], // préfixe 8 invalide
    ['0112345678'], // préfixe 1 invalide
    ['+33612345678'], // numéro français
    ['06 12 34 56 7x'],
  ])('rejette %s', (input) => {
    expect(normalizeMoroccanPhone(input).ok).toBe(false);
  });
});

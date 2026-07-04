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
    ['06 12 34 56 7x'],
  ])('rejette %s', (input) => {
    expect(normalizeMoroccanPhone(input).ok).toBe(false);
  });
});

// ——— WJ64 — la diaspora (E.164 étranger, +33/+34…) est désormais ACCEPTÉE ———
describe('normalizeMoroccanPhone — WJ64 numéros étrangers (diaspora)', () => {
  it.each([
    ['+33612345678', '+33612345678'], // France
    ['+34612345678', '+34612345678'], // Espagne
    ['+1 415 555 0100', '+14155550100'], // international générique
    ['0033612345678', '+33612345678'], // 00 international français
  ])('accepte %s → %s, flaggé phoneIsForeign', (input, expected) => {
    const r = normalizeMoroccanPhone(input);
    expect(r.ok).toBe(true);
    expect(r.e164).toBe(expected);
    expect(r.phoneIsForeign).toBe(true);
  });

  it('un numéro marocain reste SANS phoneIsForeign (chemin historique inchangé)', () => {
    const r = normalizeMoroccanPhone('0612345678');
    expect(r.ok).toBe(true);
    expect(r.e164).toBe('+212612345678');
    expect(r.phoneIsForeign).toBeUndefined();
  });

  it.each([
    ['+2125'], // trop court pour être un étranger plausible ET pas un marocain valide
    ['+'],
    ['+abc123'],
  ])('rejette encore le garbage %s', (input) => {
    expect(normalizeMoroccanPhone(input).ok).toBe(false);
  });
});

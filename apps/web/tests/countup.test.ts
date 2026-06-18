import { describe, expect, it } from 'vitest';
import { formatFrame, frFormat, isCompound, parseTokens, shouldDigitRoll } from '../src/lib/countup';

// Espaces composés des chaînes réelles de la page d'accueil : insécable + fine.
const NBSP = String.fromCharCode(0xa0);
const NNBSP = String.fromCharCode(0x202f);

describe('shouldDigitRoll — valeurs simples animées, plages/composés jamais roulés', () => {
  it('roule les valeurs simples (un seul nombre, unité optionnelle)', () => {
    expect(shouldDigitRoll('25 ans')).toBe(true);
    expect(shouldDigitRoll('0 MAD')).toBe(true);
    expect(shouldDigitRoll('21 406 kWh/an')).toBe(true);
    expect(shouldDigitRoll('43,48 kWc')).toBe(true);
    expect(shouldDigitRoll('17,04 kWc')).toBe(true);
  });

  it('ne roule JAMAIS une plage ou une valeur composée', () => {
    expect(shouldDigitRoll('60–90 %')).toBe(false); // tiret demi-cadratin
    expect(shouldDigitRoll('3–7 ans')).toBe(false);
    expect(shouldDigitRoll('3 à 5 kWc')).toBe(false);
    expect(shouldDigitRoll('50 000 MAD – 115 000 MAD')).toBe(false);
    expect(shouldDigitRoll('60-90 %')).toBe(false); // tiret simple
  });

  it('considère un nombre groupé par espace (« 21 406 ») comme une seule valeur', () => {
    // Un séparateur de milliers n'est PAS une plage : doit rester un seul jeton.
    expect(parseTokens('21 406 kWh/an')).toHaveLength(1);
    expect(parseTokens(`50${NBSP}000 MAD`)).toHaveLength(1);
    expect(parseTokens(`12${NNBSP}500 MAD`)).toHaveLength(1);
  });
});

describe('isCompound', () => {
  it('détecte les plages et les multi-nombres', () => {
    expect(isCompound('60–90 %')).toBe(true);
    expect(isCompound('3 à 5 kWc')).toBe(true);
    expect(isCompound('50 000 MAD – 115 000 MAD')).toBe(true);
    expect(isCompound('25 ans')).toBe(false);
    expect(isCompound('21 406 kWh/an')).toBe(false);
  });
});

describe('formatFrame — image finale exacte', () => {
  it('reproduit EXACTEMENT le texte final à progress = 1 (valeurs simples)', () => {
    for (const t of ['25 ans', '0 MAD', '21 406 kWh/an', '43,48 kWc', '17,04 kWc']) {
      expect(formatFrame(t, 1)).toBe(t);
    }
  });

  it('reproduit EXACTEMENT le texte final à progress = 1 (valeurs composées)', () => {
    for (const t of ['60–90 %', '3–7 ans', '3 à 5 kWc', '50 000 MAD – 115 000 MAD']) {
      expect(formatFrame(t, 1)).toBe(t);
    }
  });

  it('ne touche jamais une valeur composée, même à mi-animation', () => {
    // Aucune image intermédiaire absurde : la plage reste intacte à toute progression.
    expect(formatFrame('60–90 %', 0)).toBe('60–90 %');
    expect(formatFrame('60–90 %', 0.5)).toBe('60–90 %');
    expect(formatFrame('3 à 5 kWc', 0.37)).toBe('3 à 5 kWc');
  });
});

describe('formatFrame — image intermédiaire propre pour une valeur simple', () => {
  it('conserve le suffixe « kWh/an » et un nombre bien formé, sans caractère parasite', () => {
    const mid = formatFrame('21 406 kWh/an', 0.5);
    expect(mid.endsWith(' kWh/an')).toBe(true);
    // La partie numérique : chiffres + éventuels espaces de groupe uniquement.
    const numPart = mid.slice(0, mid.length - ' kWh/an'.length);
    expect(numPart).toMatch(new RegExp('^[0-9 ' + NBSP + NNBSP + ']+$'));
    // Pas de séparateur de plage parasite ni de virgule (valeur entière).
    expect(mid).not.toMatch(/[–-]/);
    expect(mid).not.toContain(',');
    // À mi-course la valeur est ~10 703 (la moitié de 21 406).
    expect(numPart.replace(new RegExp('[ ' + NBSP + NNBSP + ']', 'g'), '')).toBe('10703');
  });

  it('préserve l’unité « ans » sur une valeur simple à mi-course', () => {
    const mid = formatFrame('25 ans', 0.4);
    expect(mid.endsWith(' ans')).toBe(true);
    expect(mid).toBe('10 ans');
  });
});

describe('frFormat — formatage français (virgule décimale, espace milliers)', () => {
  it('groupe les milliers avec un espace et garde la virgule décimale', () => {
    expect(frFormat(21406, 0, true)).toBe('21 406');
    expect(frFormat(115000, 0, true)).toBe('115 000');
    expect(frFormat(43.48, 2, false)).toBe('43,48');
    expect(frFormat(17.04, 2, false)).toBe('17,04');
    expect(frFormat(0, 0, false)).toBe('0');
  });

  it('conserve la virgule décimale même avec groupement des milliers', () => {
    expect(frFormat(1234.5, 1, true)).toBe('1 234,5');
  });
});

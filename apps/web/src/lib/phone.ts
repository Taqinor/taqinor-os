/**
 * Normalisation des numéros marocains vers E.164 : +212XXXXXXXXX.
 * Accepte 06XX..., 07XX..., 05XX..., +212..., 00212..., 212..., avec
 * espaces, points, tirets ou parenthèses.
 */
export interface PhoneResult {
  ok: boolean;
  e164?: string;
  error?: string;
}

const INVALID: PhoneResult = {
  ok: false,
  error: 'Numéro invalide — format attendu : 06 XX XX XX XX ou +212 6 XX XX XX XX',
};

export function normalizeMoroccanPhone(raw: string): PhoneResult {
  if (!raw) return INVALID;
  let d = raw.replace(/[\s.\-()]/g, '');
  if (d.startsWith('+')) d = d.slice(1);
  if (/\D/.test(d)) return INVALID;

  if (d.startsWith('00212')) d = d.slice(5);
  else if (d.startsWith('212')) d = d.slice(3);
  else if (d.startsWith('0')) d = d.slice(1);

  // 9 chiffres : mobile (6, 7) ou fixe (5)
  if (!/^[5-7]\d{8}$/.test(d)) return INVALID;
  return { ok: true, e164: `+212${d}` };
}

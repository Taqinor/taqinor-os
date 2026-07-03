/**
 * Normalisation des numéros marocains vers E.164 : +212XXXXXXXXX.
 * Accepte 06XX..., 07XX..., 05XX..., +212..., 00212..., 212..., avec
 * espaces, points, tirets ou parenthèses.
 *
 * WJ64 — DIASPORA : un numéro marocain reste le chemin PRINCIPAL (inchangé
 * ci-dessous, `phoneIsForeign` absent). Un numéro E.164 ÉTRANGER valide (ex.
 * +33/+34…, indicatif ≠ 212) est désormais ACCEPTÉ EN PLUS — plus jamais un
 * simple « Numéro invalide » qui verrouille tout le segment marocains-du-monde
 * hors du formulaire. Champ additif : `phoneIsForeign: true` uniquement sur ce
 * second chemin, `e164` reste toujours la forme E.164 complète (indicatif
 * inclus) — la logique 1 000 MAD (billRange.ts) ne lit jamais ce champ et
 * reste intacte.
 */
export interface PhoneResult {
  ok: boolean;
  e164?: string;
  error?: string;
  /** WJ64 — présent et `true` UNIQUEMENT quand le numéro validé est un E.164
   *  étranger (indicatif ≠ 212) ; absent pour un numéro marocain (comportement
   *  historique inchangé). */
  phoneIsForeign?: boolean;
}

const INVALID: PhoneResult = {
  ok: false,
  error: 'Numéro invalide — format attendu : 06 XX XX XX XX ou +212 6 XX XX XX XX',
};

/**
 * E.164 générique (hors Maroc) : indicatif pays 1 à 3 chiffres (jamais 212,
 * déjà couvert par le chemin marocain ci-dessus) + le numéro national, total
 * borné à la longueur E.164 max (15 chiffres, recommandation UIT). Garde-fou
 * anti-garbage minimal — pas une validation par-pays complète (aucune table de
 * plans de numérotation nationaux ici), simplement un format E.164 plausible.
 */
function normalizeForeignE164(digits: string): PhoneResult {
  if (digits.startsWith('212')) return INVALID; // le Maroc a déjà son propre chemin
  if (!/^[1-9]\d{6,14}$/.test(digits)) return INVALID;
  return { ok: true, e164: `+${digits}`, phoneIsForeign: true };
}

export function normalizeMoroccanPhone(raw: string): PhoneResult {
  if (!raw) return INVALID;
  const trimmed = raw.replace(/[\s.\-()]/g, '');
  const hadPlus = trimmed.startsWith('+');
  let d = hadPlus ? trimmed.slice(1) : trimmed;
  if (/\D/.test(d)) return INVALID;

  if (d.startsWith('00212')) d = d.slice(5);
  else if (d.startsWith('212')) d = d.slice(3);
  else if (!hadPlus && d.startsWith('0')) d = d.slice(1);

  // 9 chiffres : mobile (6, 7) ou fixe (5) → chemin marocain, inchangé.
  if (/^[5-7]\d{8}$/.test(d)) return { ok: true, e164: `+212${d}` };

  // WJ64 — pas un numéro marocain : tenter un E.164 étranger AVANT de rejeter.
  // Seul un « + » explicite (ou 00 international) engage ce chemin — un numéro
  // local à 10 chiffres commençant par 0 reste jugé comme un marocain malformé
  // (comportement de rejet historique inchangé pour ce cas).
  if (hadPlus) {
    const foreign = normalizeForeignE164(d);
    if (foreign.ok) return foreign;
  } else if (trimmed.startsWith('00')) {
    const foreign = normalizeForeignE164(trimmed.slice(2));
    if (foreign.ok) return foreign;
  }

  return INVALID;
}

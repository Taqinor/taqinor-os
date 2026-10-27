/**
 * RWEB1 — retour sur investissement affiché sur /proposition (résidentiel).
 *
 * Deux règles, alignées sur le PDF (`quote_engine/i18n_labels.py`) :
 * - quand le moteur lève `roi_s_jamais` / `roi_a_jamais` (pricing.py :
 *   jamais remboursé sur 25 ans), la page n'imprime AUCUNE année — la
 *   sentinelle `roi_* = 25` n'est jamais montrée — et écrit le même libellé
 *   que le PDF (`res_non_rentabilise_25`) ;
 * - l'unité suit la langue (« 7,5 ans » / « 7.5 years » / « 7,5 سنوات ») au
 *   lieu d'un « ans » français imprimé dans les versions EN/AR.
 */

export type Langue = 'fr' | 'en' | 'ar';
export type Libelles = Record<Langue, string>;

/** Libellé PDF `res_non_rentabilise_25` (i18n_labels.py), mot pour mot. */
export const NON_RENTABILISE_25: Libelles = {
  fr: 'Non rentabilisé sur 25 ans',
  en: 'Not paid back within 25 years',
  ar: 'غير مسترد خلال 25 سنة',
};

function nombre(roi: number, langue: Langue): string {
  const arrondi = Math.round(roi * 10) / 10;
  const texte = Number.isInteger(arrondi) ? String(arrondi) : arrondi.toFixed(1);
  return langue === 'en' ? texte : texte.replace('.', ',');
}

/**
 * Durée de retour dans les trois langues, ou `null` quand elle n'est pas
 * réelle (absente, ≤ 0, non finie, ou drapeau « jamais » levé). Une chaîne déjà
 * formatée par le serveur est reprise telle quelle dans les trois langues.
 */
export function libellesRetour(
  roi: number | string | null | undefined,
  jamais = false,
): Libelles | null {
  if (jamais || roi === null || roi === undefined || roi === '') return null;
  if (typeof roi === 'number') {
    if (!Number.isFinite(roi) || roi <= 0) return null;
    return {
      fr: `${nombre(roi, 'fr')} ans`,
      en: `${nombre(roi, 'en')} years`,
      ar: `${nombre(roi, 'ar')} سنوات`,
    };
  }
  const t = String(roi).trim();
  return t.length ? { fr: t, en: t, ar: t } : null;
}

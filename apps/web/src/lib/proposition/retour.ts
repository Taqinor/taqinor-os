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
      // Accord arabe : 3-10 → سنوات, au-delà → سنة (même règle que `anneesAr` de la page).
      ar: `${nombre(roi, 'ar')} ${roi > 10 ? 'سنة' : 'سنوات'}`,
    };
  }
  const t = String(roi).trim();
  return t.length ? { fr: t, en: t, ar: t } : null;
}

/**
 * RWEB20 — mot de l'économie annuelle selon le modèle de l'option, comme le PDF
 * (`res_opt_eco_calculee` / `res_opt_eco_estimee`, i18n_labels.py) : « horaire » → calculée,
 * tout autre modèle servi → estimée ; modèle absent → `null` (libellé actuel de la page inchangé).
 * `valeur` (« 12 000 MAD ») absente → intitulé de carte « … / an » ; présente → « … ≈ 12 000 MAD/an ».
 */
export function libellesEconomie(modele: string | null | undefined, valeur: string | null = null): Libelles | null {
  if (!modele) return null;
  const mot: Libelles = modele === 'horaire'
    ? { fr: 'Économie calculée', en: 'Calculated savings', ar: 'الوفورات المحسوبة' }
    : { fr: 'Économie estimée', en: 'Estimated savings', ar: 'الوفورات المقدرة' };
  return valeur === null
    ? { fr: `${mot.fr} / an`, en: `${mot.en} / year`, ar: `${mot.ar} / سنة` }
    : { fr: `${mot.fr} ≈ ${valeur}/an`, en: `${mot.en} ≈ ${valeur}/yr`, ar: `${mot.ar} ≈ ${valeur}/سنة` };
}

/**
 * RWEB21/22 — phrase « Rentabilisé en N ans » (FR/EN/AR) autour d'une durée de `libellesRetour`,
 * ou le libellé PDF « Non rentabilisé sur 25 ans » quand le drapeau « jamais » est levé ;
 * `null` quand la durée n'est pas réelle (rien n'est alors imprimé).
 */
export function phraseRentabilise(duree: Libelles | null, jamais = false): Libelles | null {
  if (jamais) return NON_RENTABILISE_25;
  return duree ? { fr: `Rentabilisé en ${duree.fr}`, en: `Paid back in ${duree.en}`, ar: `يُسترد خلال ${duree.ar}` } : null;
}

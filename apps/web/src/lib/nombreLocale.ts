/**
 * WAUD44 — format des nombres par langue de page, UNE source : `fr-FR` pour FR et AR (règle AR
 * existante : chiffres latins au format français), `en-GB` pour EN (« 1,500 », « 44.19 »).
 * `LOCALE_NOMBRE` vivait dans lib/tunnel/estimationResidentielle.ts (ré-exporté de là, inchangé) ;
 * il est ici pour que lib/realisations.ts et les composants l'importent sans cycle.
 * Les VALEURS ne changent jamais : seul le séparateur suit la langue.
 */
export type LocaleNombre = 'fr' | 'en' | 'ar';

export const LOCALE_NOMBRE: Record<LocaleNombre, string> = { fr: 'fr-FR', ar: 'fr-FR', en: 'en-GB' };

/** Nombres au format français dans un texte publié (« 1 000 – 1 500 MAD », « 17,04 kWc »). */
const NOMBRE_FR = /(?<![\d.,])\d{1,3}(?:[   ]\d{3})+(?:,\d+)?(?![\d])|(?<![\d.,])\d+,\d+(?![\d])/g;

/**
 * Réécrit les nombres d'un libellé publié en français dans le format de la langue : même valeur,
 * mêmes décimales, seul le séparateur change (EN « 1,000 – 1,500 MAD »). FR/AR : texte inchangé.
 */
export function nombresVersLocale(texte: string, locale: LocaleNombre): string {
  if (LOCALE_NOMBRE[locale] === LOCALE_NOMBRE.fr) return texte;
  return texte.replace(NOMBRE_FR, (brut) => {
    const [entier, dec = ''] = brut.split(',');
    const valeur = Number(`${entier.replace(/[   ]/g, '')}.${dec || '0'}`);
    return formatNombreLocale(valeur, locale, dec.length);
  });
}

/** Nombre au format de la langue, avec exactement `decimales` chiffres après la virgule/le point. */
export function formatNombreLocale(n: number, locale: LocaleNombre, decimales = 0): string {
  return n.toLocaleString(LOCALE_NOMBRE[locale] ?? LOCALE_NOMBRE.fr, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}

/**
 * Configuration i18n (YBW13) — français par défaut à `/`, anglais sous `/en/`.
 *
 * `LOCALES_ACTIVES` est une constante de BUILD : tant que `en` n'y figure pas
 * (jusqu'à YBW70, après l'accord de Reda sur le texte français) :
 *  - aucune route `/en/*` n'est construite (retirée du build, astro.config.mjs) ;
 *  - aucun lien hreflang ni sélecteur de langue vers l'anglais n'est émis ;
 *  - les dictionnaires anglais ne sont PAS exigés (type `DictEn` partiel).
 * Dès que `en` est active, une clé anglaise manquante fait échouer `npm run check`.
 *
 * Règles de mise en page : CSS LOGIQUE seulement (`inset-inline`,
 * `margin-inline`, `padding-inline`…) ; les nombres sont rendus dans un
 * élément `dir="ltr"`.
 */

export const LOCALES = ['fr', 'en'] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = 'fr';

export const LOCALES_ACTIVES = ['fr', 'en'] as const satisfies readonly Locale[];

/** Valeur de l'attribut `<html lang>` par locale. */
export const LANG_HTML: Record<Locale, string> = { fr: 'fr', en: 'en' };

/** Nom de chaque langue dans SA langue (sélecteur). */
export const NOM_LANGUE: Record<Locale, string> = { fr: 'Français', en: 'English' };

export function estLocale(x: string): x is Locale {
  return (LOCALES as readonly string[]).includes(x);
}

export function estActive(locale: Locale, actives: readonly Locale[] = LOCALES_ACTIVES): boolean {
  return actives.includes(locale);
}

/** Chaînes d'un dictionnaire, élargies à `string` (le FR est écrit `as const`). */
export type Chaines<T> = { [K in keyof T]: T[K] extends string ? string : Chaines<T[K]> };
type Partiel<T> = { [K in keyof T]?: T[K] extends string ? string : Partiel<T[K]> };

/**
 * Type d'un dictionnaire anglais : COMPLET (mêmes clés que le FR) dès que `en`
 * est active, partiel sinon. Usage : `const en: DictEn<typeof fr> = { … }`.
 */
export type DictEn<T, A extends readonly Locale[] = typeof LOCALES_ACTIVES> = 'en' extends A[number] ? Chaines<T> : Partiel<T>;

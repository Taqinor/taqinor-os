/**
 * Configuration i18n du site public — FR par défaut (racine, sans préfixe),
 * EN sous /en/, AR sous /ar/ (droite-à-gauche). Source unique de vérité pour
 * les locales, leur sens d'écriture et leur libellé dans le sélecteur.
 *
 * NB : le FR reste servi à la racine (`prefixDefaultLocale: false` dans
 * astro.config.mjs) et son rendu doit rester IDENTIQUE — toute traduction est
 * additive (EN/AR), jamais une réécriture du FR. Les chiffres et le texte légal
 * (loi 82-21) restent EXACTS dans toutes les langues.
 */
export const DEFAULT_LOCALE = 'fr' as const;

export const LOCALES = ['fr', 'en', 'ar'] as const;
export type Locale = (typeof LOCALES)[number];

/** Sens d'écriture par locale (AR = droite-à-gauche). */
export const LOCALE_DIR: Record<Locale, 'ltr' | 'rtl'> = {
  fr: 'ltr',
  en: 'ltr',
  ar: 'rtl',
};

/** Libellé affiché dans le sélecteur de langue (endonyme). */
export const LOCALE_LABEL: Record<Locale, string> = {
  fr: 'Français',
  en: 'English',
  ar: 'العربية',
};

/** Code court affiché dans la barre (FR / EN / ع). */
export const LOCALE_SHORT: Record<Locale, string> = {
  fr: 'FR',
  en: 'EN',
  ar: 'ع',
};

/** Code BCP-47 pour l'attribut lang / hreflang. */
export const LOCALE_BCP47: Record<Locale, string> = {
  fr: 'fr',
  en: 'en',
  ar: 'ar',
};

export const isLocale = (value: string): value is Locale =>
  (LOCALES as readonly string[]).includes(value);

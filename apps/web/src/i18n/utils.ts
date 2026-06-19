/**
 * Helpers i18n — déduire la locale depuis l'URL, traduire une clé, préfixer un
 * chemin par la locale (FR sans préfixe). Pur, testable sans navigateur.
 */
import { DEFAULT_LOCALE, isLocale, LOCALE_DIR, type Locale } from './config';
import { ui } from './ui';

/** Locale d'une URL : /en/... → en, /ar/... → ar, sinon fr (racine). */
export function getLocaleFromPath(pathname: string): Locale {
  const seg = pathname.split('/').filter(Boolean)[0];
  return seg && isLocale(seg) ? seg : DEFAULT_LOCALE;
}

/** Chemin sans le préfixe de locale (ex. /en/contact → /contact). */
export function stripLocale(pathname: string): string {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] && isLocale(parts[0]) && parts[0] !== DEFAULT_LOCALE) {
    return '/' + parts.slice(1).join('/');
  }
  return pathname.startsWith('/') ? pathname : '/' + pathname;
}

/** Préfixe un chemin racine (/contact) pour une locale (FR = pas de préfixe). */
export function localizePath(path: string, locale: Locale): string {
  const clean = path.startsWith('/') ? path : '/' + path;
  if (locale === DEFAULT_LOCALE) return clean;
  return `/${locale}${clean === '/' ? '' : clean}`;
}

/** Sens d'écriture de la locale (AR = rtl). */
export function dirOf(locale: Locale): 'ltr' | 'rtl' {
  return LOCALE_DIR[locale];
}

/**
 * Fabrique une fonction de traduction t('section.cle') pour une locale, avec
 * repli sur le FR si une clé n'est pas encore traduite (jamais de clé brute
 * affichée). Retourne la clé elle-même en tout dernier recours.
 */
export function useTranslations(locale: Locale) {
  return function t(key: string): string {
    const dict = ui[locale] as Record<string, string>;
    const frDict = ui[DEFAULT_LOCALE] as Record<string, string>;
    return dict[key] ?? frDict[key] ?? key;
  };
}

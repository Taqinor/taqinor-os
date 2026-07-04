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

/**
 * Chemin sans le préfixe de locale (ex. /en/contact → /contact).
 *
 * SLASH-CONSISTANT (ERR70) : la barre finale du chemin d'origine est préservée
 * à l'identique dans les deux branches (avec ou sans préfixe de locale). Ainsi
 * les alternates hreflang émises depuis /contact/ et depuis /en/contact/
 * concordent toutes (toutes avec barre, ou toutes sans) et ne déclenchent
 * jamais le 301 de canonicalisation de la barre finale (worker/redirects.mjs).
 */
export function stripLocale(pathname: string): string {
  const normalized = pathname.startsWith('/') ? pathname : '/' + pathname;
  const parts = normalized.split('/').filter(Boolean);
  // La forme canonique du site est AVEC barre finale ; on la conserve telle
  // quelle (racine `/` exclue) pour que toutes les locales s'accordent.
  const hadTrailingSlash = normalized.length > 1 && normalized.endsWith('/');
  if (parts[0] && isLocale(parts[0]) && parts[0] !== DEFAULT_LOCALE) {
    const rest = parts.slice(1).join('/');
    if (!rest) return '/';
    return '/' + rest + (hadTrailingSlash ? '/' : '');
  }
  return normalized;
}

/**
 * Préfixe un chemin racine (/contact) pour une locale (FR = pas de préfixe).
 *
 * WB16 — la racine (/) préfixée en EN/AR DOIT garder sa barre finale
 * (`/en/`, `/ar/`), sinon la forme émise (`/en`, `/ar`) est 301-redirigée vers
 * elle-même AVEC barre par `trailingSlashRedirect` (worker/redirects.mjs) : un
 * hreflang ne doit jamais cibler une URL qui redirige. Les chemins non-racine
 * sont inchangés (jamais de barre ajoutée par ce helper).
 */
export function localizePath(path: string, locale: Locale): string {
  const clean = path.startsWith('/') ? path : '/' + path;
  if (locale === DEFAULT_LOCALE) return clean;
  if (clean === '/') return `/${locale}/`;
  return `/${locale}${clean}`;
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

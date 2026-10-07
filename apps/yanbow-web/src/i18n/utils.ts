/**
 * Aides i18n (YBW13) — pures, testables sans navigateur. AUCUN REPLI : une
 * clé absente ou vide lève une erreur (jamais de retombée silencieuse sur le
 * français ou sur la clé, qui masquerait une fuite).
 */
import { DEFAULT_LOCALE, LOCALES, LOCALES_ACTIVES, type Locale } from './config';
import { PAGES, type CheminsParLocale, type PageId } from './pages';

/**
 * Lit `cle` (chemin pointé, ex. « hero.titre ») dans `dict`. Lève si la clé
 * est absente, vide ou n'est pas une chaîne.
 */
export function t(dict: unknown, cle: string, locale: Locale = DEFAULT_LOCALE): string {
  let v: unknown = dict;
  for (const morceau of cle.split('.')) {
    v = v !== null && typeof v === 'object' ? (v as Record<string, unknown>)[morceau] : undefined;
  }
  if (typeof v !== 'string' || v.trim() === '') {
    throw new Error(`i18n : clé « ${cle} » manquante ou vide pour la langue « ${locale} »`);
  }
  return v;
}

/** Chemin d'une page du registre dans une langue (helper de liens). */
export function L(page: PageId, locale: Locale = DEFAULT_LOCALE): string {
  return PAGES[page][locale];
}

export interface Alternate {
  hreflang: string;
  href: string;
}

/**
 * Liens `<link rel="alternate" hreflang>` pour une page : une entrée par langue
 * ACTIVE + `x-default` (= le français). Une seule langue active = aucun lien.
 */
export function alternates(chemins: CheminsParLocale, actives: readonly Locale[] = LOCALES_ACTIVES): Alternate[] {
  const langues = LOCALES.filter((l) => actives.includes(l));
  if (langues.length < 2) return [];
  return [...langues.map((l) => ({ hreflang: l, href: chemins[l] })), { hreflang: 'x-default', href: chemins[DEFAULT_LOCALE] }];
}

export interface LienLangue {
  locale: Locale;
  href: string;
}

/** Entrées du sélecteur de langue : les AUTRES langues actives, vers la page équivalente. */
export function selecteurLangue(chemins: CheminsParLocale, courante: Locale, actives: readonly Locale[] = LOCALES_ACTIVES): LienLangue[] {
  return LOCALES.filter((l) => l !== courante && actives.includes(l)).map((l) => ({ locale: l, href: chemins[l] }));
}

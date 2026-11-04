/**
 * ENF19 — contexte de locale PARTAGÉ par les composants à libellés traduits (FounderPortrait,
 * GarantiesTeaser…) : la locale déduite du chemin et le localisateur de liens de navigation.
 * Une seule copie (garde ACAL345, scripts/check_duplicats_litteraux.py).
 */
import { getLocaleFromPath } from '../i18n/utils';
import { localizeNavHref } from '../i18n/pages';
import type { Locale } from '../i18n/config';

export function contexteLocale(pathname: string): { locale: Locale; L: (href: string) => string } {
  const locale = getLocaleFromPath(pathname);
  return { locale, L: (href: string) => localizeNavHref(href, locale) };
}

/** Champs communs des cartes à libellés traduits (accroche, titre, lien d'action). */
export type ChampsCarte = { eyebrow: string; title: string; cta: string };

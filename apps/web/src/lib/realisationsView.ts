/**
 * ENF19 — helpers communs aux pages /realisations traduites (EN / AR).
 * Données 100 % issues de realisations.ts / caseStudies.ts (lecture seule).
 */
import type { Locale } from '../i18n/config';
import { caseStudyBySlug } from './caseStudies';
import { NAP } from './nap';
import { pageLocale } from './pageCtx';
import { REALISATIONS } from './realisations';

export const villesUniques = [...new Set(REALISATIONS.map((r) => r.ville))];

/** Alt localisé (repli FR si absent dans la map de l'étude de cas). */
export function realisationAlt(locale: Locale) {
  return (r: (typeof REALISATIONS)[number]) =>
    caseStudyBySlug(r.slug, locale).alts[r.photos[0].name] ?? r.photos[0].alt;
}

/** Schéma ItemList (W289) : même forme que FR, nom/description traduits. */
export function realisationsItemListJsonLd(
  L: (href: string) => string,
  site: URL | undefined,
  name: string,
  description: string,
  itemName: (r: (typeof REALISATIONS)[number]) => string,
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    description,
    itemListElement: REALISATIONS.map((r, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      url: new URL(L(`/realisations/${r.slug}`), site).href,
      name: itemName(r),
    })),
    provider: { '@type': 'LocalBusiness', name: NAP.name, url: NAP.url },
  };
}

/** Contexte d'une page étude de cas traduite : locale, L et prose de l'étude. */
export function caseStudyPage(pathname: string, slug: string) {
  const ctx = pageLocale(pathname);
  return { ...ctx, cs: caseStudyBySlug(slug, ctx.locale) };
}

/** Contexte de la page liste /realisations traduite : locale, L et alt localisé. */
export function realisationsPage(pathname: string) {
  const ctx = pageLocale(pathname);
  return { ...ctx, altOf: realisationAlt(ctx.locale) };
}

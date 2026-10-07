/**
 * Registre des pages du site (YBW13) — pilote hreflang (+ x-default), le
 * sélecteur de langue et le sitemap. Les 8 pages du plan de site sont
 * déclarées D'EMBLÉE ; chaque fichier de page est créé par SA tâche.
 * Slugs ASCII, forme canonique AVEC barre finale (le Worker redirige l'autre).
 */
import type { Locale } from './config';

export type CheminsParLocale = Record<Locale, string>;

export const PAGES = {
  accueil: { fr: '/', en: '/en/' },
  solarbow: { fr: '/solarbow/', en: '/en/solarbow/' },
  marketingbow: { fr: '/marketingbow/', en: '/en/marketingbow/' },
  surMesure: { fr: '/sur-mesure/', en: '/en/custom-software/' },
  societe: { fr: '/societe/', en: '/en/company/' },
  rendezVous: { fr: '/rendez-vous/', en: '/en/book-a-meeting/' },
  confidentialite: { fr: '/confidentialite/', en: '/en/privacy/' },
  mentionsLegales: { fr: '/mentions-legales/', en: '/en/legal/' },
} as const satisfies Record<string, CheminsParLocale>;

export type PageId = keyof typeof PAGES;

/** Page sonde technique (noindex, hors sitemap, supprimée par YBW61). */
export const SONDE: CheminsParLocale = { fr: '/bonjour/', en: '/en/bonjour/' };

/** Toutes les URL du registre (pages du plan de site seulement). */
export function toutesLesUrl(): string[] {
  return Object.values(PAGES).flatMap((p) => [p.fr, p.en]);
}

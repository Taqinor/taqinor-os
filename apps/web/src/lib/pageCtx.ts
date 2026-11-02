/**
 * ENF19 — contexte de page commun aux pages localisées (FR / EN / AR).
 *
 * Remplace le préambule recopié dans ~85 pages :
 *   const locale = getLocaleFromPath(Astro.url.pathname);
 *   const L = (href: string) => localizeNavHref(href, locale);
 * `devisHref` est le lien localisé vers le simulateur, repris tel quel par les
 * pages qui le déclaraient (`L('/devis/mon-toit')`). Aucune sortie ne change.
 */
import { localizeNavHref } from '../i18n/pages';
import { getLocaleFromPath } from '../i18n/utils';
import { estimateReadingTime } from './readingTime';

export function pageLocale(pathname: string) {
  const locale = getLocaleFromPath(pathname);
  const L = (href: string) => localizeNavHref(href, locale);
  return { locale, L, devisHref: L('/devis/mon-toit') };
}

/**
 * Variante « article / guide » : ajoute l'URL canonique de la page et l'URL
 * absolue de l'image de partage (`ogPng`, ex. '/og/equipement.png') utilisées
 * par le JSON-LD Article.
 */
export function articlePage(pathname: string, site: URL | undefined, ogPng: string) {
  return {
    ...pageLocale(pathname),
    url: new URL(pathname, site).href,
    schemaImageUrl: new URL(ogPng, site).href,
  };
}

/**
 * Métadonnées d'article communes aux guides / billets (FR, EN, AR) : temps de
 * lecture du corps, URL canonique et URL absolue de l'image de partage.
 */
export function articleMeta(bodyText: string, pathname: string, site: URL | undefined, ogPng: string) {
  return {
    readingMinutes: estimateReadingTime(bodyText),
    url: new URL(pathname, site).href,
    schemaImageUrl: new URL(ogPng, site).href,
  };
}

/** Fil d'Ariane JSON-LD des billets de blog traduits : Accueil > Blog > billet. */
export function blogBreadcrumbLd(
  L: (href: string) => string,
  site: URL | undefined,
  homeLabel: string,
  blogLabel: string,
  title: string,
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: homeLabel, item: new URL(L('/'), site).href },
      { '@type': 'ListItem', position: 2, name: blogLabel, item: new URL(L('/blog'), site).href },
      { '@type': 'ListItem', position: 3, name: title },
    ],
  };
}

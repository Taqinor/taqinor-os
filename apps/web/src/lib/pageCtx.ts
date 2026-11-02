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

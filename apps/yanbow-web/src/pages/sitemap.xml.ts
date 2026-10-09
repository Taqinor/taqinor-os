import type { APIRoute } from 'astro';
import { DEFAULT_LOCALE, LOCALES, LOCALES_ACTIVES, type Locale } from '../i18n/config';
import { PAGES, type CheminsParLocale } from '../i18n/pages';
import { routesJuridiquesCompletes } from '../lib/legal';
import { ORIGINE_CANONIQUE } from '../lib/site';

/**
 * Sitemap (YBW75) généré depuis le registre `pages.ts` — jamais à la main.
 *
 * - Servi SEULEMENT quand le site est ouvert : tant que `SITE_PUBLIC` n'est pas
 *   `1`, la porte de lancement du Worker (YBW12) répond 404 à `/sitemap*.xml`
 *   avant d'atteindre cette route ; et sans domaine canonique posé
 *   (`src/lib/site.ts`, YBWM10) la route répond 404 aussi (aucune URL absolue
 *   inventée).
 * - Seules les langues ACTIVES, les pages du registre (donc ni les pages
 *   utilitaires ni les pages `noindex`) et les pages juridiques déclarées
 *   COMPLÈTES (donc routables) y figurent.
 * - Aucune date `lastmod` : aucune date inventée.
 */
export const prerender = false;

export interface OptionsSitemap {
  origine: string | null;
  locales?: readonly Locale[];
  pages?: Record<string, CheminsParLocale>;
  juridiquesCompletes?: readonly string[];
}

const ROUTES_JURIDIQUES = ['/mentions-legales', '/en/legal', '/confidentialite', '/en/privacy'];

const sansBarre = (chemin: string) => (chemin.length > 1 ? chemin.replace(/\/+$/, '') : chemin);
const echapper = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export interface EntreeSitemap {
  loc: string;
  alternates: { hreflang: string; href: string }[];
}

/** URL listées : une entrée par page et par langue active, avec ses alternates. */
export function entreesSitemap(opt: OptionsSitemap): EntreeSitemap[] {
  const { origine, locales = LOCALES_ACTIVES, pages = PAGES, juridiquesCompletes = routesJuridiquesCompletes() } = opt;
  if (!origine) return [];
  const actives = LOCALES.filter((l) => locales.includes(l));
  const abs = (chemin: string) => new URL(chemin, origine).href;
  const completes = juridiquesCompletes.map(sansBarre);
  const sorties: EntreeSitemap[] = [];
  for (const chemins of Object.values(pages)) {
    for (const l of actives) {
      const chemin = chemins[l];
      if (ROUTES_JURIDIQUES.includes(sansBarre(chemin)) && !completes.includes(sansBarre(chemin))) continue;
      const alternates =
        actives.length < 2
          ? []
          : [
              ...actives.map((a) => ({ hreflang: a, href: abs(chemins[a]) })),
              { hreflang: 'x-default', href: abs(chemins[DEFAULT_LOCALE]) },
            ];
      sorties.push({ loc: abs(chemin), alternates });
    }
  }
  return sorties;
}

/** Document XML du sitemap, ou `null` quand aucun domaine n'est posé. */
export function construireSitemap(opt: OptionsSitemap): string | null {
  if (!opt.origine) return null;
  const lignes = entreesSitemap(opt).map(
    (e) =>
      `  <url>\n    <loc>${echapper(e.loc)}</loc>\n` +
      e.alternates.map((a) => `    <xhtml:link rel="alternate" hreflang="${a.hreflang}" href="${echapper(a.href)}"/>\n`).join('') +
      `  </url>`,
  );
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' +
    lignes.join('\n') +
    '\n</urlset>\n'
  );
}

export const GET: APIRoute = () => {
  const xml = construireSitemap({ origine: ORIGINE_CANONIQUE });
  if (xml === null) return new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain; charset=utf-8' } });
  return new Response(xml, { headers: { 'content-type': 'application/xml; charset=utf-8' } });
};

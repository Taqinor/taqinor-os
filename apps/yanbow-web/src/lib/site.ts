/**
 * Constantes du site (YBW11) — SOURCE UNIQUE de l'origine canonique.
 *
 * `ORIGINE_CANONIQUE` reste `null` tant que Reda n'a pas choisi ni acheté le
 * domaine (YBWM10). Tant qu'elle est nulle : aucune redirection canonique,
 * aucune URL absolue émise (ni `<link rel="canonical">`, ni sitemap).
 * Le build (astro.config.mjs) recopie cette valeur dans le Worker.
 */
export const ORIGINE_CANONIQUE: string | null = null;

import { avecBarreFinale } from '../i18n/pages';

/**
 * WAUD70 — forme canonique UNIQUE d'une URL du site (RSS, llms.txt, JSON-LD) :
 * origine https://taqinor.ma, chemin encodé en UTF-8 (%C3%A9) et barre finale
 * (sauf fichiers à extension et /api), ancre et query préservées. Une URL qui
 * sort d'ici répond 200 sans passer par le 301 de trailingSlashRedirect.
 */
export const SITE_ORIGIN = 'https://taqinor.ma';

export function canonicalUrl(pathOrUrl: string, site: string | URL = SITE_ORIGIN): string {
  const u = new URL(pathOrUrl, site);
  const chemin = avecBarreFinale(u.pathname);
  return `${u.origin}${chemin}${u.search}${u.hash}`;
}

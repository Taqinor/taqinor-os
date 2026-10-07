/**
 * Redirections de chemin (YBW11). Module pur, copié dans dist/server/ au build.
 *
 * Une seule règle : la barre finale des PAGES (forme canonique = avec barre).
 * Exemptés : requêtes non GET/HEAD, racine, chemins déjà terminés par « / »,
 * `/api/*`, et tout fichier à extension (robots.txt, favicon.svg, assets).
 */

/**
 * @param {string} requestUrl
 * @param {string} [method]
 * @returns {{ target: string, status: number } | null}
 */
export function trailingSlashRedirect(requestUrl, method = 'GET') {
  const m = method.toUpperCase();
  if (m !== 'GET' && m !== 'HEAD') return null;
  const url = new URL(requestUrl);
  const p = url.pathname;
  if (p === '/' || p.endsWith('/')) return null;
  if (p === '/api' || p.startsWith('/api/')) return null;
  const dernier = p.slice(p.lastIndexOf('/') + 1);
  if (dernier.includes('.')) return null;
  return { target: url.origin + p + '/' + url.search, status: 301 };
}

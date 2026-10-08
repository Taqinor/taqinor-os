/**
 * En-têtes de cache (YBW11). Module pur, copié dans dist/server/ au build.
 *
 * - Documents HTML : revalidés à chaque requête (un déploiement est servi
 *   immédiatement, sans purge).
 * - `/fonts/`, `/brand/`, `/og/`, `/_astro/` : immuables 1 an — leurs noms de
 *   fichiers sont VERSIONNÉS (changer un fichier = changer son nom).
 * - Tout le reste (API JSON, robots.txt…) : inchangé.
 */

export const HTML_CACHE_CONTROL = 'public, max-age=0, must-revalidate';
export const IMMUTABLE_CACHE_CONTROL = 'public, max-age=31536000, immutable';
export const IMMUTABLE_PREFIXES = ['/fonts/', '/brand/', '/og/', '/_astro/'];

/**
 * Valeur de Cache-Control à imposer, ou null pour laisser la réponse intacte.
 * @param {string} pathname
 * @param {string} contentType
 * @returns {string | null}
 */
export function cacheControlFor(pathname, contentType) {
  if (IMMUTABLE_PREFIXES.some((p) => pathname.startsWith(p))) return IMMUTABLE_CACHE_CONTROL;
  if ((contentType || '').toLowerCase().includes('text/html')) return HTML_CACHE_CONTROL;
  return null;
}

/**
 * Applique la règle de cache à une réponse GET/HEAD réussie (2xx/304) ; sinon
 * renvoie la réponse d'origine.
 * @param {Request} request
 * @param {Response} response
 * @returns {Response}
 */
export function applyCacheControl(request, response) {
  const method = (request.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') return response;
  if (!(response.ok || response.status === 304)) return response;
  const valeur = cacheControlFor(new URL(request.url).pathname, response.headers.get('content-type') || '');
  if (!valeur) return response;
  const headers = new Headers(response.headers);
  headers.set('Cache-Control', valeur);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

/**
 * En-têtes de cache des DOCUMENTS HTML (W33).
 *
 * Problème : après un déploiement, l'accueil et les pages HTML pouvaient encore
 * servir une version périmée parce que le document HTML était mis en cache
 * « en dur » au bord. On force donc chaque document HTML à se revalider, pour
 * qu'un nouveau déploiement soit reflété immédiatement sur `/`.
 *
 * Ce qui n'est PAS touché :
 *  - les assets hashés (CSS/JS/fontes/images) — servis asset-first, ils ne
 *    passent même pas par le Worker (run_worker_first les exclut) et gardent
 *    leur cache long ;
 *  - `/api/*` et toute réponse NON `text/html` (JSON du formulaire live,
 *    estimateur, sitemap…) — renvoyées telles quelles, byte-for-byte.
 *
 * Module volontairement pur (aucun import) : testé par tests/cache.test.ts et
 * copié tel quel dans dist/server/ au build (voir astro.config.mjs).
 */

/** Valeur de Cache-Control appliquée aux documents HTML : revalidation à chaque
 * requête → un déploiement est servi sans purge manuelle, sans casser le cache
 * des assets hashés. */
export const HTML_CACHE_CONTROL = 'public, max-age=0, must-revalidate';

/**
 * Renvoie une réponse dont le Cache-Control force la revalidation si (et
 * seulement si) c'est un document HTML servi en GET/HEAD. Sinon renvoie la
 * réponse d'origine inchangée.
 */
export function applyHtmlCacheControl(request, response) {
  const method = (request && request.method ? request.method : 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') return response;

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('text/html')) return response;

  const headers = new Headers(response.headers);
  headers.set('Cache-Control', HTML_CACHE_CONTROL);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

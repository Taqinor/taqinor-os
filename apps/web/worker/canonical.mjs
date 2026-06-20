/**
 * Hôte canonique du site public. Toute requête arrivant par un sous-domaine
 * *.workers.dev doit être redirigée en 301 vers https://taqinor.ma (chemin et
 * querystring préservés) pour que Google n'indexe jamais deux copies du site.
 *
 * Module volontairement pur (aucun import) : testé par tests/redirect.test.ts
 * et copié tel quel dans dist/server/ au build (voir astro.config.mjs).
 */
export const CANONICAL_ORIGIN = 'https://taqinor.ma';

/**
 * URL canonique cible si la requête vient d'un hôte *.workers.dev,
 * sinon null (la requête continue vers l'app Astro).
 */
export function canonicalTarget(requestUrl, canonicalOrigin = CANONICAL_ORIGIN) {
  const url = new URL(requestUrl);
  if (!url.hostname.endsWith('.workers.dev')) return null;
  return canonicalOrigin + url.pathname + url.search;
}

/**
 * Statut HTTP de la redirection canonique workers.dev selon la méthode (ERR109).
 * GET/HEAD → 301 (indexable, mis en cache). Toute autre méthode (POST du
 * formulaire / de l'API) → 308 : un 308 préserve la MÉTHODE et le CORPS, alors
 * qu'un 301 autorise le client à repasser en GET et à perdre le corps — ce qui
 * abandonnerait silencieusement un lead posté sur le sous-domaine workers.dev.
 */
export function canonicalRedirectStatus(method = 'GET') {
  return method === 'GET' || method === 'HEAD' ? 301 : 308;
}

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

/**
 * Hôte canonique (YBW11). Module pur, copié tel quel dans dist/server/ au build.
 *
 * L'origine vient de `src/lib/site.ts` (ORIGINE_CANONIQUE), recopiée par le
 * build dans `site-config.mjs`. Tant qu'elle est nulle, AUCUNE redirection :
 * le site reste servi sur son adresse workers.dev (fermé, voir launchGate.mjs).
 */

/**
 * URL canonique cible si la requête arrive par un sous-domaine *.workers.dev
 * ET qu'une origine canonique est posée ; sinon null.
 * @param {string} requestUrl
 * @param {string | null | undefined} canonicalOrigin
 * @returns {string | null}
 */
export function canonicalTarget(requestUrl, canonicalOrigin) {
  if (!canonicalOrigin) return null;
  const url = new URL(requestUrl);
  if (!url.hostname.endsWith('.workers.dev')) return null;
  return canonicalOrigin.replace(/\/+$/, '') + url.pathname + url.search;
}

/**
 * GET/HEAD → 301 ; toute autre méthode → 308 (préserve méthode ET corps : un
 * formulaire posté sur l'ancienne adresse n'est jamais perdu).
 * @param {string} [method]
 */
export function canonicalRedirectStatus(method = 'GET') {
  const m = method.toUpperCase();
  return m === 'GET' || m === 'HEAD' ? 301 : 308;
}

/**
 * En-têtes de sécurité (YBW11). Module pur, copié dans dist/server/ au build.
 *
 * La CSP est construite depuis le registre `src/lib/subprocessors.ts` (recopié
 * par le build dans `site-config.mjs`) : registre vide = `'self'` seulement.
 * Aucun hôte tiers n'est écrit en dur ici — on l'ajoute au registre (YBW26).
 * `worker-src 'none'` interdit tout service worker ; `object-src 'none'`.
 */

/** Directives de base ; les sources du registre s'ajoutent après `'self'`. */
const BASE = [
  ['default-src', ["'self'"]],
  ['script-src', ["'self'"]],
  ['style-src', ["'self'", "'unsafe-inline'"]],
  ['img-src', ["'self'", 'data:']],
  ['font-src', ["'self'"]],
  ['connect-src', ["'self'"]],
  ['frame-src', ["'none'"]],
  ['worker-src', ["'none'"]],
  ['object-src', ["'none'"]],
  ['manifest-src', ["'self'"]],
  ['frame-ancestors', ["'none'"]],
  ['base-uri', ["'self'"]],
  ['form-action', ["'self'"]],
];

/**
 * @param {Record<string, string[] | undefined>} [sources] hôtes par directive (registre)
 * @returns {string}
 */
export function buildCsp(sources = {}) {
  return BASE.map(([directive, base]) => {
    const extra = sources[/** @type {string} */ (directive)] || [];
    // `'none'` ne se combine avec rien : un hôte ajouté le remplace.
    const valeurs = extra.length && base[0] === "'none'" ? extra : [...base, ...extra];
    return `${directive} ${[...new Set(valeurs)].join(' ')}`;
  }).join('; ');
}

export const STRICT_TRANSPORT_SECURITY = 'max-age=31536000; includeSubDomains';
export const REFERRER_POLICY = 'strict-origin-when-cross-origin';
export const PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()';

/**
 * Applique les en-têtes : HSTS, nosniff et Referrer-Policy sur TOUTE réponse ;
 * CSP, X-Frame-Options et Permissions-Policy sur les documents HTML.
 * @param {Request} _request
 * @param {Response} response
 * @param {string} csp
 * @returns {Response}
 */
export function applySecurityHeaders(_request, response, csp) {
  const headers = new Headers(response.headers);
  headers.set('Strict-Transport-Security', STRICT_TRANSPORT_SECURITY);
  headers.set('X-Content-Type-Options', 'nosniff');
  headers.set('Referrer-Policy', REFERRER_POLICY);
  const contentType = (headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('text/html')) {
    headers.set('Content-Security-Policy', csp);
    headers.set('X-Frame-Options', 'DENY');
    headers.set('Permissions-Policy', PERMISSIONS_POLICY);
  }
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

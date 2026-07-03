/**
 * En-têtes de sécurité (W315) — appliqués à TOUTE réponse HTML sortante.
 *
 * Constat : aucune réponse ne portait de durcissement (CSP/HSTS/etc.) avant ce
 * module. Le Referrer-Policy protège aussi le token de /proposition/<token>
 * (ERR-like : un Referer complet fuiterait le token vers un tuile MapTiler ou
 * tout lien externe cliqué depuis la page).
 *
 * CSP volontairement conservatrice plutôt que stricte : le site sert un
 * <script is:inline> (capture fbclid/UTM, src/layouts/Layout.astro) et des
 * <script type="application/ld+json"> sur presque toutes les pages, plus des
 * balises <style> scopées Astro sur de nombreux composants — donc
 * 'unsafe-inline' est nécessaire pour script-src ET style-src tant qu'aucune
 * infrastructure de nonce/hash n'est en place (pas dans le scope de W315).
 * connect-src/img-src/style-src autorisent api.maptiler.com (tuiles + geocodage
 * appelés depuis le navigateur par les outils toiture/roofPro*) et
 * api.taqinor.ma (API ERP). PVGIS (re.jrc.ec.europa.eu) n'est JAMAIS appelé
 * depuis le navigateur (proxy serveur strict, voir src/lib/roofEstimate.ts +
 * src/pages/api/roof-*.ts) donc n'a pas besoin de figurer en connect-src.
 *
 * Module volontairement pur (aucun import) : testé par tests/headers.test.ts
 * et copié tel quel dans dist/server/ au build (voir astro.config.mjs).
 */

const CSP_DIRECTIVES = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://api.maptiler.com",
  "font-src 'self' data:",
  "connect-src 'self' https://api.taqinor.ma https://api.maptiler.com",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self' https://api.taqinor.ma",
];

/** Valeur de Content-Security-Policy appliquée aux documents HTML. */
export const CONTENT_SECURITY_POLICY = CSP_DIRECTIVES.join('; ');

/** HSTS : 1 an, sous-domaines inclus (le site n'est servi qu'en HTTPS). */
export const STRICT_TRANSPORT_SECURITY = 'max-age=31536000; includeSubDomains';

/** Referrer-Policy : n'envoie l'URL complète qu'en same-origin / HTTPS→HTTPS
 * de même sécurité — protège notamment le token de /proposition/<token>. */
export const REFERRER_POLICY = 'strict-origin-when-cross-origin';

/** Permissions-Policy : géolocalisation autorisée en self uniquement (outil
 * toiture), tout le reste des API sensibles désactivé par défaut du navigateur. */
export const PERMISSIONS_POLICY = 'geolocation=(self)';

/**
 * Applique l'ensemble des en-têtes de sécurité à une réponse HTML (GET/HEAD
 * uniquement — un POST /api/* ou tout non-HTML repart inchangé, comme
 * applyHtmlCacheControl dans cache.mjs).
 */
export function applySecurityHeaders(request, response) {
  const method = (request && request.method ? request.method : 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') return response;

  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('text/html')) return response;

  const headers = new Headers(response.headers);
  headers.set('Content-Security-Policy', CONTENT_SECURITY_POLICY);
  headers.set('Strict-Transport-Security', STRICT_TRANSPORT_SECURITY);
  headers.set('Referrer-Policy', REFERRER_POLICY);
  headers.set('Permissions-Policy', PERMISSIONS_POLICY);
  headers.set('X-Content-Type-Options', 'nosniff');
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

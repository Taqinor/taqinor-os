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
 * appelés depuis le navigateur par les outils toiture/roofPro*), api.mapbox.com
 * (tuiles satellite haute résolution — chargées par buildSatelliteStyle dès que
 * PUBLIC_MAPBOX_TOKEN est défini ; sans cette autorisation le navigateur bloque
 * toutes les tuiles Mapbox et la carte reste vide) et api.taqinor.ma (API ERP).
 * PVGIS (re.jrc.ec.europa.eu) n'est JAMAIS appelé
 * depuis le navigateur (proxy serveur strict, voir src/lib/roofEstimate.ts +
 * src/pages/api/roof-*.ts) donc n'a pas besoin de figurer en connect-src.
 *
 * Module volontairement pur (aucun import) : testé par tests/headers.test.ts
 * et copié tel quel dans dist/server/ au build (voir astro.config.mjs).
 */

/**
 * Google tag (gtag.js — Google Ads + GA4, components/GoogleTag.astro) : hôtes
 * documentés par Google (developers.google.com/tag-platform/security/guides/csp,
 * sections Google tag, GA4 et Google Ads). Sans eux la CSP bloquerait gtag.js et
 * les pings de conversion. `www.google.co.ma` = le `www.google.<TLD>` du Maroc.
 */
const GOOGLE_TAG_SCRIPT = 'https://www.googletagmanager.com https://www.googleadservices.com https://www.google.com';
const GOOGLE_TAG_IMG =
  'https://www.googletagmanager.com https://*.google-analytics.com https://www.googleadservices.com ' +
  'https://*.g.doubleclick.net https://pagead2.googlesyndication.com https://www.google.com https://www.google.co.ma';
const GOOGLE_TAG_CONNECT =
  'https://www.googletagmanager.com https://www.google-analytics.com https://*.google-analytics.com ' +
  'https://*.analytics.google.com https://www.googleadservices.com https://*.g.doubleclick.net ' +
  'https://pagead2.googlesyndication.com https://www.google.com https://www.google.co.ma https://ad.doubleclick.net';
const GOOGLE_TAG_FRAME = 'https://www.googletagmanager.com';

const CSP_DIRECTIVES = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${GOOGLE_TAG_SCRIPT}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: https://api.maptiler.com https://api.mapbox.com ${GOOGLE_TAG_IMG}`,
  "font-src 'self' data:",
  `connect-src 'self' https://api.taqinor.ma https://api.maptiler.com https://api.mapbox.com ${GOOGLE_TAG_CONNECT}`,
  // frame-src explicite : 'self' conserve le repli default-src d'avant.
  `frame-src 'self' ${GOOGLE_TAG_FRAME}`,
  // WJCSP (21/08/2026) — MapLibre rend les sources GeoJSON (repère maison,
  // contour du toit dessiné : rp9-pin/rp9-line/rp9-pts) dans un WEB WORKER
  // qu'il crée depuis un blob:. Sans worker-src, la directive de repli est
  // script-src (sans blob:) : le worker est bloqué SILENCIEUSEMENT — la
  // carte satellite (tuiles images) s'affiche, mais le client ne VOIT jamais
  // ni son repère ni son tracé (régression du 03/07, W315 ; le nginx de
  // l'ERP porte déjà cette directive avec le même diagnostic —
  // backend/nginx/security-headers.conf.template).
  "worker-src 'self' blob:",
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
 * toiture) ; caméra/micro/paiement explicitement désactivés (WB35 — le site
 * n'utilise aucune de ces API), le reste des API sensibles reste désactivé par
 * défaut du navigateur. */
export const PERMISSIONS_POLICY = 'geolocation=(self), camera=(), microphone=(), payment=()';

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
  // WB34 — défense en profondeur clickjacking pour les anciens agents/scanners
  // qui n'honorent pas `frame-ancestors` (CSP) : DENY reflète la même politique.
  headers.set('X-Frame-Options', 'DENY');
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

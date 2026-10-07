/**
 * Porte de lancement (YBW12) — FERMÉE par défaut, échec = fermé.
 * Module pur, copié dans dist/server/ au build.
 *
 * Ouvert UNIQUEMENT si la variable d'exécution `SITE_PUBLIC` vaut exactement
 * la chaîne « 1 » (posée par Reda au tableau de bord, jamais dans
 * wrangler.jsonc). Absente, vide, illisible, « true », « 1 » avec espaces… =
 * FERMÉ :
 *  - CHAQUE réponse porte `X-Robots-Tag: noindex, nofollow` ;
 *  - `/robots.txt` est servi ici : `Disallow: /` ;
 *  - aucun sitemap (`/sitemap*.xml` → 404) ;
 *  - aucun `<link rel="canonical">` dans les pages (retiré du HTML).
 * Dans les DEUX états, une page juridique qui n'est pas déclarée complète
 * (YBW28, liste fournie par le build) n'est pas routable (404).
 */

export const ROBOTS_FERME = 'User-agent: *\nDisallow: /\n';
export const X_ROBOTS_FERME = 'noindex, nofollow';

/** Routes juridiques (FR + EN), sans barre finale. */
export const ROUTES_JURIDIQUES = ['/confidentialite', '/mentions-legales', '/en/privacy', '/en/legal'];

/**
 * @param {Record<string, unknown> | null | undefined} env
 * @returns {boolean}
 */
export function sitePublic(env) {
  try {
    return !!env && typeof env.SITE_PUBLIC === 'string' && env.SITE_PUBLIC === '1';
  } catch {
    return false;
  }
}

/** @param {string} pathname */
function sansBarre(pathname) {
  return pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname;
}

/**
 * @param {string} pathname
 * @param {readonly string[]} completes routes juridiques déclarées complètes
 */
export function routeJuridiqueFermee(pathname, completes) {
  const p = sansBarre(pathname);
  return ROUTES_JURIDIQUES.includes(p) && !completes.map(sansBarre).includes(p);
}

/** @param {string} html */
export function retirerCanonique(html) {
  return html.replace(/<link\b[^>]*\brel=["']?canonical["']?[^>]*>/gi, '');
}

/**
 * Enveloppe un gestionnaire avec la porte.
 * @param {Request} request
 * @param {Record<string, unknown>} env
 * @param {() => Promise<Response>} suivant
 * @param {{ routesJuridiquesCompletes?: readonly string[] }} [options]
 * @returns {Promise<Response>}
 */
export async function appliquerPorte(request, env, suivant, options = {}) {
  const completes = options.routesJuridiquesCompletes || [];
  const ouvert = sitePublic(env);
  const pathname = new URL(request.url).pathname;

  if (routeJuridiqueFermee(pathname, completes)) {
    return fermer(new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain; charset=utf-8' } }), ouvert);
  }
  if (!ouvert) {
    if (pathname === '/robots.txt') {
      return fermer(new Response(ROBOTS_FERME, { headers: { 'content-type': 'text/plain; charset=utf-8' } }), false);
    }
    if (/^\/sitemap[^/]*\.xml$/.test(pathname)) {
      return fermer(new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain; charset=utf-8' } }), false);
    }
  }
  const reponse = await suivant();
  if (ouvert) return reponse;

  const type = (reponse.headers.get('content-type') || '').toLowerCase();
  if (type.includes('text/html') && reponse.body) {
    const html = retirerCanonique(await reponse.text());
    const headers = new Headers(reponse.headers);
    headers.delete('content-length');
    return fermer(new Response(html, { status: reponse.status, statusText: reponse.statusText, headers }), false);
  }
  return fermer(reponse, false);
}

/**
 * @param {Response} reponse
 * @param {boolean} ouvert
 */
function fermer(reponse, ouvert) {
  if (ouvert) return reponse;
  const headers = new Headers(reponse.headers);
  headers.set('X-Robots-Tag', X_ROBOTS_FERME);
  return new Response(reponse.body, { status: reponse.status, statusText: reponse.statusText, headers });
}

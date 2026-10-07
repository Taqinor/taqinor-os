/**
 * Chaîne du Worker (YBW11) — composée ici pour être testable sans l'app Astro
 * générée ; `redirect-entry.mjs` ne fait que la brancher sur `./entry.mjs`.
 *
 * Ordre : 1) hôte canonique (no-op tant qu'aucun domaine n'est posé) ;
 * 2) barre finale des pages ; 3) app Astro ; 4) cache + en-têtes de sécurité.
 */
import { canonicalTarget, canonicalRedirectStatus } from './canonical.mjs';
import { trailingSlashRedirect } from './redirects.mjs';
import { applyCacheControl } from './cache.mjs';
import { applySecurityHeaders, buildCsp } from './headers.mjs';

/**
 * @typedef {{ fetch: (request: Request, env: any, ctx: any) => Promise<Response> | Response }} App
 * @typedef {{ CANONICAL_ORIGIN: string | null, CSP_SOURCES: Record<string, string[]> }} SiteConfig
 */

/**
 * @param {App} app
 * @param {SiteConfig} site
 */
export function creerWorker(app, site) {
  const csp = buildCsp(site.CSP_SOURCES);
  /** @param {Response} r @param {Request} request */
  const finir = (request, r) => applySecurityHeaders(request, applyCacheControl(request, r), csp);

  return {
    /** @param {Request} request @param {any} env @param {any} ctx */
    async fetch(request, env, ctx) {
      const cible = canonicalTarget(request.url, site.CANONICAL_ORIGIN);
      if (cible) {
        const status = canonicalRedirectStatus(request.method);
        /** @type {Record<string, string>} */
        const h = { location: cible };
        if (status === 301) h['cache-control'] = 'public, max-age=3600';
        return finir(request, new Response(null, { status, headers: h }));
      }
      const slash = trailingSlashRedirect(request.url, request.method);
      if (slash) {
        return finir(
          request,
          new Response(null, { status: slash.status, headers: { location: slash.target, 'cache-control': 'public, max-age=3600' } }),
        );
      }
      const reponse = await app.fetch(request, env, ctx);
      return finir(request, reponse);
    },
  };
}

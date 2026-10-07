/**
 * Chaîne du Worker (YBW11) — composée ici pour être testable sans l'app Astro
 * générée ; `redirect-entry.mjs` ne fait que la brancher sur `./entry.mjs`.
 *
 * Ordre : 0) porte de lancement (YBW12, enveloppe TOUT, y compris les
 * redirections) ; 1) hôte canonique (no-op tant qu'aucun domaine n'est posé) ;
 * 2) barre finale des pages ; 3) app Astro ; 4) cache + en-têtes de sécurité.
 */
import { canonicalTarget, canonicalRedirectStatus } from './canonical.mjs';
import { trailingSlashRedirect } from './redirects.mjs';
import { applyCacheControl } from './cache.mjs';
import { applySecurityHeaders, buildCsp } from './headers.mjs';
import { appliquerPorte } from './launchGate.mjs';

/**
 * @typedef {{ fetch: (request: Request, env: any, ctx: any) => Promise<Response> | Response }} App
 * @typedef {{ CANONICAL_ORIGIN: string | null, CSP_SOURCES: Record<string, string[]>, ROUTES_JURIDIQUES_COMPLETES?: readonly string[] }} SiteConfig
 */

/**
 * @param {App} app
 * @param {SiteConfig} site
 */
export function creerWorker(app, site) {
  const csp = buildCsp(site.CSP_SOURCES);
  /** @param {Request} request @param {Response} r */
  const finir = (request, r) => applySecurityHeaders(request, applyCacheControl(request, r), csp);

  /** @param {Request} request @param {any} env @param {any} ctx */
  async function interne(request, env, ctx) {
    const cible = canonicalTarget(request.url, site.CANONICAL_ORIGIN);
    if (cible) {
      const status = canonicalRedirectStatus(request.method);
      /** @type {Record<string, string>} */
      const h = { location: cible };
      if (status === 301) h['cache-control'] = 'public, max-age=3600';
      return new Response(null, { status, headers: h });
    }
    const slash = trailingSlashRedirect(request.url, request.method);
    if (slash) {
      return new Response(null, { status: slash.status, headers: { location: slash.target, 'cache-control': 'public, max-age=3600' } });
    }
    return app.fetch(request, env, ctx);
  }

  return {
    /** @param {Request} request @param {any} env @param {any} ctx */
    async fetch(request, env, ctx) {
      const reponse = await appliquerPorte(request, env, async () => interne(request, env, ctx), {
        routesJuridiquesCompletes: site.ROUTES_JURIDIQUES_COMPLETES || [],
      });
      // Cache + en-têtes de sécurité sur TOUTE réponse, y compris celles de la porte.
      return finir(request, reponse);
    },
  };
}

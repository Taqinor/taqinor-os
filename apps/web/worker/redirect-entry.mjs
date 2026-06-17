/**
 * Entrée Worker de production — enveloppe l'app Astro générée (./entry.mjs).
 *
 * Ce fichier est committé dans apps/web/worker/ et COPIÉ dans dist/server/
 * par le hook astro:build:done (astro.config.mjs), qui pointe aussi le
 * wrangler.json généré vers cette entrée et active run_worker_first sur les
 * routes HTML. Rôles : 301 canonique workers.dev → taqinor.ma ; et (W33)
 * forcer la revalidation des documents HTML pour qu'un déploiement ne serve
 * jamais une page périmée. Le reste passe à l'app Astro inchangé.
 */
import astro from './entry.mjs';
import { canonicalTarget } from './canonical.mjs';
import { pathRedirect, trailingSlashRedirect } from './redirects.mjs';
import { applyHtmlCacheControl } from './cache.mjs';

export default {
  async fetch(request, env, ctx) {
    // 1) Hôte canonique : *.workers.dev → taqinor.ma (chemin + query préservés).
    const target = canonicalTarget(request.url);
    if (target) {
      return new Response(null, {
        status: 301,
        headers: { location: target, 'cache-control': 'public, max-age=3600' },
      });
    }
    // 2) Redirections de chemin (anciennes URL / variantes sans accent).
    const redirect = pathRedirect(request.url);
    if (redirect) {
      return new Response(null, {
        status: redirect.status,
        headers: {
          location: redirect.target,
          // 301 mis en cache 1 h ; 302 (repli temporaire) caché 5 min seulement.
          'cache-control': redirect.status === 301 ? 'public, max-age=3600' : 'public, max-age=300',
        },
      });
    }
    // 3) Canonicalisation de la barre finale (pages HTML, GET/HEAD ; /api et
    //    fichiers exemptés) → une seule forme indexable.
    const slash = trailingSlashRedirect(request.url, request.method);
    if (slash) {
      return new Response(null, {
        status: slash.status,
        headers: { location: slash.target, 'cache-control': 'public, max-age=3600' },
      });
    }
    // 4) App Astro. Les documents HTML sont forcés à se revalider (W33) ;
    //    /api/* et toute réponse non-HTML repartent inchangés.
    const response = await astro.fetch(request, env, ctx);
    return applyHtmlCacheControl(request, response);
  },
};

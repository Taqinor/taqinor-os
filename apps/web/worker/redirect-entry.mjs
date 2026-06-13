/**
 * Entrée Worker de production — enveloppe l'app Astro générée (./entry.mjs).
 *
 * Ce fichier est committé dans apps/web/worker/ et COPIÉ dans dist/server/
 * par le hook astro:build:done (astro.config.mjs), qui pointe aussi le
 * wrangler.json généré vers cette entrée et active run_worker_first sur les
 * routes HTML. Rôle unique : 301 canonique workers.dev → taqinor.ma, le
 * reste passe à l'app Astro inchangé.
 */
import astro from './entry.mjs';
import { canonicalTarget } from './canonical.mjs';

export default {
  async fetch(request, env, ctx) {
    const target = canonicalTarget(request.url);
    if (target) {
      return new Response(null, {
        status: 301,
        headers: { location: target, 'cache-control': 'public, max-age=3600' },
      });
    }
    return astro.fetch(request, env, ctx);
  },
};

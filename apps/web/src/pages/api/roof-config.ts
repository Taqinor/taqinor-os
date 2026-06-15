/**
 * GET /api/roof-config — expose la clé MapTiler PUBLIQUE (PUBLIC_MAPTILER_KEY)
 * et, en option, le token Mapbox PUBLIC (PUBLIC_MAPBOX_TOKEN) au navigateur de
 * l'estimateur de toiture (preview privé).
 *
 * Ces deux valeurs sont PUBLIQUES et restreintes par domaine (taqinor.ma) côté
 * fournisseur — ce ne sont PAS des secrets. Elles sont lues à l'exécution depuis
 * l'environnement Worker (cf.env), jamais codées en dur. MapTiler absente →
 * `available: false` et l'outil affiche un repli gracieux (« momentanément
 * indisponible »), jamais une carte cassée. Le token Mapbox est facultatif :
 * absent → l'imagerie reste sur le style hybride MapTiler, inchangé.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { resolveMaptilerKey, resolveMapboxToken } from '../../lib/roofConfig';

export const GET: APIRoute = async () => {
  // Deux sources acceptées (cf. roofConfig.ts) : variable RUNTIME (cf.env) OU
  // variable de BUILD (inlinée par Vite dans import.meta.env). Lire les deux
  // évite le bug « clé posée en variable de build mais ignorée au runtime ».
  const env = (cf.env ?? {}) as { PUBLIC_MAPTILER_KEY?: string; PUBLIC_MAPBOX_TOKEN?: string };
  const key = resolveMaptilerKey(env.PUBLIC_MAPTILER_KEY, import.meta.env.PUBLIC_MAPTILER_KEY);
  // Même plomberie pour le token Mapbox (imagerie satellite plus nette) : runtime
  // OU build. Facultatif — son absence ne change PAS `available` (carte MapTiler).
  const mapboxToken = resolveMapboxToken(env.PUBLIC_MAPBOX_TOKEN, import.meta.env.PUBLIC_MAPBOX_TOKEN);
  return new Response(JSON.stringify({ maptilerKey: key, mapboxToken, available: key.length > 0 }), {
    headers: {
      'content-type': 'application/json',
      // Pas de cache : l'état (clé présente/absente) doit refléter immédiatement
      // un changement de configuration — sinon un available:false périmé peut
      // masquer la carte plusieurs minutes après correction.
      'cache-control': 'no-store',
    },
  });
};

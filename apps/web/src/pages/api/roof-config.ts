/**
 * GET /api/roof-config — expose la clé MapTiler PUBLIQUE (PUBLIC_MAPTILER_KEY)
 * au navigateur de l'estimateur de toiture (preview privé).
 *
 * Cette clé est PUBLIQUE et restreinte par domaine (taqinor.ma) côté MapTiler —
 * ce n'est PAS un secret. Elle est lue à l'exécution depuis l'environnement
 * Worker (cf.env), jamais codée en dur. Absente → `available: false` et l'outil
 * affiche un repli gracieux (« momentanément indisponible »), jamais une carte
 * cassée.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { resolveMaptilerKey } from '../../lib/roofConfig';

export const GET: APIRoute = async () => {
  // Deux sources acceptées (cf. roofConfig.ts) : variable RUNTIME (cf.env) OU
  // variable de BUILD (inlinée par Vite dans import.meta.env). Lire les deux
  // évite le bug « clé posée en variable de build mais ignorée au runtime ».
  const env = (cf.env ?? {}) as { PUBLIC_MAPTILER_KEY?: string };
  const key = resolveMaptilerKey(env.PUBLIC_MAPTILER_KEY, import.meta.env.PUBLIC_MAPTILER_KEY);
  return new Response(JSON.stringify({ maptilerKey: key, available: key.length > 0 }), {
    headers: {
      'content-type': 'application/json',
      // Pas de cache : l'état (clé présente/absente) doit refléter immédiatement
      // un changement de configuration — sinon un available:false périmé peut
      // masquer la carte plusieurs minutes après correction.
      'cache-control': 'no-store',
    },
  });
};

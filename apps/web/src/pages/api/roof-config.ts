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

export const GET: APIRoute = async () => {
  const env = (cf.env ?? {}) as { PUBLIC_MAPTILER_KEY?: string };
  const key = env.PUBLIC_MAPTILER_KEY?.trim() || '';
  return new Response(JSON.stringify({ maptilerKey: key, available: key.length > 0 }), {
    headers: {
      'content-type': 'application/json',
      // Clé publique restreinte par domaine — cacheable brièvement côté edge.
      'cache-control': 'public, max-age=300',
    },
  });
};

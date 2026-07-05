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
 *
 * WJ96(b) — Une clé MapTiler VIDE au runtime était jusqu'ici totalement
 * SILENCIEUSE côté serveur (seul le repli client apparaissait, gracieux mais
 * invisible dans les logs) : un mauvais déploiement de variable pouvait passer
 * inaperçu indéfiniment. On journalise désormais un avertissement Worker
 * explicite dans tous les environnements (`console.warn`, jamais bloquant), et
 * on ajoute un champ de diagnostic `debug` dans la réponse JSON UNIQUEMENT hors
 * production (`import.meta.env.PROD === false`) — jamais exposé aux visiteurs
 * du site en production, le repli client reste inchangé dans tous les cas.
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
  const available = key.length > 0;

  if (!available) {
    // WJ96(b) — un avertissement clair dans les logs Worker : une config
    // manquante en production ne doit plus jamais être invisible. Jamais de
    // secret journalisé (les deux valeurs sont déjà publiques par nature, mais
    // on ne loggue même pas leur valeur — seulement l'ABSENCE).
    console.warn(
      '[roof-config] PUBLIC_MAPTILER_KEY est vide (runtime ET build) — la carte satellite affichera son repli gracieux.',
    );
  }

  const body: Record<string, unknown> = { maptilerKey: key, mapboxToken, available };
  // Diagnostic non-prod UNIQUEMENT (jamais exposé en production) : quelle(s)
  // source(s) manquaient, pour un debug local/preview rapide sans avoir à
  // relire les logs Worker.
  if (!available && !import.meta.env.PROD) {
    body.debug = {
      runtimeKeyPresent: !!env.PUBLIC_MAPTILER_KEY?.trim(),
      buildKeyPresent: !!import.meta.env.PUBLIC_MAPTILER_KEY?.trim(),
    };
  }

  return new Response(JSON.stringify(body), {
    headers: {
      'content-type': 'application/json',
      // Pas de cache : l'état (clé présente/absente) doit refléter immédiatement
      // un changement de configuration — sinon un available:false périmé peut
      // masquer la carte plusieurs minutes après correction.
      'cache-control': 'no-store',
    },
  });
};

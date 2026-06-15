/**
 * Résolution de la clé MapTiler PUBLIQUE exposée par /api/roof-config.
 *
 * Module pur (aucun import Cloudflare) → testé unitairement.
 *
 * Deux sources possibles, par robustesse :
 *  - RUNTIME : variable/secret Worker (cf.env.PUBLIC_MAPTILER_KEY) — modifiable
 *    sans rebuild ;
 *  - BUILD : variable de build Cloudflare, inlinée par Vite dans
 *    import.meta.env.PUBLIC_MAPTILER_KEY au moment du build.
 *
 * Le bug du 13/06/2026 : la clé était posée en variable de BUILD, mais
 * l'endpoint ne lisait que le runtime → toujours vide → repli affiché à tort.
 * On accepte désormais l'une OU l'autre ; le repli ne reste légitime que si
 * AUCUNE des deux n'apporte de clé.
 */
export function resolveMaptilerKey(runtime?: string, build?: string): string {
  return (runtime?.trim() || build?.trim() || '');
}

/**
 * Token Mapbox PUBLIC (imagerie satellite Maxar Vivid, ~0,3–0,6 m, plus nette
 * que MapTiler sur le Maroc), résolu EXACTEMENT comme la clé MapTiler : runtime
 * (cf.env) d'abord, sinon build (import.meta.env). Ce token est PUBLIC (restreint
 * par domaine côté Mapbox) — jamais codé en dur. Absent → repli MapTiler inchangé.
 */
export function resolveMapboxToken(runtime?: string, build?: string): string {
  return (runtime?.trim() || build?.trim() || '');
}

/** URL du style hybride MapTiler (satellite + libellés) — comportement historique. */
export function maptilerHybridStyleUrl(key: string): string {
  return `https://api.maptiler.com/maps/hybrid/style.json?key=${encodeURIComponent(key)}`;
}

/**
 * Endpoint Raster Tiles v4 de Mapbox Satellite. `@2x` = tuiles retina (haute
 * densité) servies sur le schéma 256. Les styles `mapbox://` ne sont PAS supportés
 * par MapLibre : on passe par l'endpoint HTTPS et une source raster TileJSON.
 */
export function mapboxSatelliteTileUrl(token: string): string {
  return `https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90?access_token=${encodeURIComponent(token)}`;
}

/**
 * Style de la carte de l'estimateur, choisi par la PRÉSENCE du token Mapbox :
 *  - token présent → style MapLibre minimal avec une source RASTER Mapbox
 *    Satellite (imagerie Maxar nette) + attribution visible exigée par Mapbox ;
 *  - token absent/vide → REPLI sur le style hybride MapTiler historique (URL
 *    inchangée), donc l'ordre de pose des variables Cloudflare est indifférent
 *    et « pas de token » = comportement actuel, à l'identique.
 *
 * Renvoie soit une chaîne (URL de style MapTiler), soit un objet de style
 * MapLibre (StyleSpecification) ; le type reste volontairement large pour garder
 * ce module pur (aucun import maplibre-gl, cf. test du périmètre des imports).
 */
export function buildSatelliteStyle(opts: { maptilerKey: string; mapboxToken?: string }): string | object {
  const token = (opts.mapboxToken ?? '').trim();
  if (!token) return maptilerHybridStyleUrl(opts.maptilerKey);
  return {
    version: 8,
    sources: {
      'mapbox-satellite': {
        type: 'raster',
        tiles: [mapboxSatelliteTileUrl(token)],
        tileSize: 256,
        attribution:
          '© <a href="https://www.mapbox.com/about/maps/" target="_blank" rel="noopener">Mapbox</a> © <a href="https://www.maxar.com/" target="_blank" rel="noopener">Maxar</a>',
      },
    },
    layers: [{ id: 'mapbox-satellite', type: 'raster', source: 'mapbox-satellite' }],
  };
}

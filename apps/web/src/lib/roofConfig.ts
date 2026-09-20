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
 * Dimensions (px) d'une image satellite préservant l'aspect géographique d'un toit
 * (envergure est-ouest × nord-sud, en mètres) : le plus grand côté vaut `maxPx`,
 * l'autre suit le ratio. Faire correspondre l'aspect de l'image à celui de la bbox
 * évite que l'API Static n'ajoute du remplissage (padding) — condition de
 * l'alignement géographique exact. Bornes Mapbox Static : 1–1280 px par côté.
 */
export function roofImageSize(widthSpanM: number, heightSpanM: number, maxPx = 1024): { w: number; h: number } {
  const cap = Math.max(1, Math.min(1280, Math.round(maxPx)));
  const w = Math.max(1e-6, widthSpanM);
  const h = Math.max(1e-6, heightSpanM);
  if (w >= h) return { w: cap, h: Math.max(1, Math.min(1280, Math.round((cap * h) / w))) };
  return { w: Math.max(1, Math.min(1280, Math.round((cap * w) / h))), h: cap };
}

// — Web Mercator (EPSG:3857), normalisé [0,1] sur le monde — utilisé pour CALCULER
//   l'étendue exacte que couvre une image Static demandée par centre+zoom. Mapbox
//   rend en Mercator ; c'est la seule projection où l'étendue d'une image
//   centre+zoom est déterministe (donc des UV alignables au pixel près).
export function lngToMercX(lng: number): number {
  return (lng + 180) / 360;
}
export function latToMercY(lat: number): number {
  const clamped = Math.max(-85.05112878, Math.min(85.05112878, lat));
  const s = Math.sin((clamped * Math.PI) / 180);
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
}
export function mercXToLng(x: number): number {
  return x * 360 - 180;
}
export function mercYToLat(y: number): number {
  return (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI;
}

export interface RoofImageRequest {
  /** Centre géographique demandé à l'API Static. */
  center: [number, number];
  /** Zoom (fractionnaire) demandé. */
  zoom: number;
  /** Dimensions logiques de l'image (px ; `@2x` double la densité, pas l'étendue). */
  w: number;
  h: number;
  /** Étendue géographique RÉELLEMENT couverte [minLng,minLat,maxLng,maxLat]. */
  extent: [number, number, number, number];
}

/**
 * Requête d'image satellite DÉTERMINISTE pour un toit, par centre + zoom (et NON
 * par `[bbox]`, dont l'endpoint Static élargit l'étendue — padding/cadrage — ce qui
 * faisait « déborder » l'imagerie des voisins sur le toit). On choisit le zoom le
 * plus serré qui contient la bbox du toit, puis on CALCULE l'étendue exacte que
 * l'image couvrira : les UV peuvent alors mapper chaque sommet à sa vraie position
 * dans l'image. Le toit étant rendu comme le POLYGONE tracé, seule l'imagerie du
 * contour est peinte. Borne de zoom 22 (max imagerie satellite).
 */
export function roofImageRequest(
  bbox: [number, number, number, number],
  maxPx = 1024,
  tile = 512,
  maxZoom = 22,
): RoofImageRequest {
  const [minLng, minLat, maxLng, maxLat] = bbox;
  const xMin = lngToMercX(minLng);
  const xMax = lngToMercX(maxLng);
  const yNorth = latToMercY(maxLat); // plus PETIT y (le nord est en haut)
  const ySouth = latToMercY(minLat); // plus GRAND y
  const mercW = Math.max(1e-12, xMax - xMin);
  const mercH = Math.max(1e-12, ySouth - yNorth);
  // Dimensions de l'image en aspect Mercator de la bbox (longue côté = maxPx).
  const { w, h } = roofImageSize(mercW, mercH, maxPx);
  // Zoom tel que w×h px (logiques, tuiles `tile`) contiennent la bbox ; borné.
  const zFit = Math.log2(Math.min(w / mercW, h / mercH) / tile);
  const zoom = Math.max(0, Math.min(maxZoom, zFit));
  const scale = tile * Math.pow(2, zoom); // px par unité Mercator
  const cx = (xMin + xMax) / 2;
  const cy = (yNorth + ySouth) / 2;
  const exMinX = cx - w / 2 / scale;
  const exMaxX = cx + w / 2 / scale;
  const exMinY = cy - h / 2 / scale; // vers le nord (y plus petit)
  const exMaxY = cy + h / 2 / scale; // vers le sud (y plus grand)
  return {
    center: [mercXToLng(cx), mercYToLat(cy)],
    zoom,
    w,
    h,
    extent: [mercXToLng(exMinX), mercYToLat(exMaxY), mercXToLng(exMaxX), mercYToLat(exMinY)],
  };
}

/**
 * UV (u,v) ∈ [0,1] d'un point lng/lat dans une image satellite couvrant EXACTEMENT
 * `extent` (étendue calculée par roofImageRequest), en Web Mercator. u suit l'est ;
 * v suit le nord (avec THREE.Texture flipY par défaut, v=1 = nord = haut de l'image)
 * → la photo se pose géographiquement alignée sur le toit et le calepinage.
 */
export function roofVertexUV(
  lng: number,
  lat: number,
  extent: [number, number, number, number],
): [number, number] {
  const [exMinLng, exMinLat, exMaxLng, exMaxLat] = extent;
  const x0 = lngToMercX(exMinLng);
  const x1 = lngToMercX(exMaxLng);
  const ySouth = latToMercY(exMinLat); // y max
  const yNorth = latToMercY(exMaxLat); // y min
  const u = (lngToMercX(lng) - x0) / Math.max(1e-12, x1 - x0);
  const v = (ySouth - latToMercY(lat)) / Math.max(1e-12, ySouth - yNorth);
  return [u, v];
}

/**
 * URL Mapbox Static Images pour l'imagerie satellite Maxar centrée (centre+zoom →
 * étendue déterministe, cf. roofImageRequest), aux dimensions WxH. RÉUTILISE le
 * MÊME token public Mapbox que les tuiles de la carte (aucune nouvelle dépendance,
 * même fournisseur/imagerie). `@2x` = sortie haute densité ; logo/attribution
 * retirés de l'image (l'attribution Mapbox/Maxar reste visible sur la carte). La
 * netteté plafonne à celle de l'imagerie (~0,3–0,6 m sur Casablanca).
 */
export function mapboxStaticRoofImageUrl(
  token: string,
  center: [number, number],
  zoom: number,
  w: number,
  h: number,
): string {
  const [lng, lat] = center;
  const z = Math.max(0, Math.min(22, zoom));
  const W = Math.max(1, Math.min(1280, Math.round(w)));
  const H = Math.max(1, Math.min(1280, Math.round(h)));
  const pos = `${lng},${lat},${z.toFixed(4)},0`;
  return `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/${pos}/${W}x${H}@2x?access_token=${encodeURIComponent(token)}&attribution=false&logo=false`;
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
export function buildSatelliteStyle(opts: {
  maptilerKey: string;
  mapboxToken?: string;
  /** CAL48 — section `imagerie` des réglages société. ABSENTE ⇒ le style produit est
   *  strictement celui d'avant CAL48 (aucune lecture du registre). */
  imagery?: ImagerySettings | null;
}): string | object {
  // CAL48 — un contexte d'imagerie RENSEIGNÉ passe par le registre de fournisseurs
  // (attribution du fournisseur actif incluse). Sans contexte, la logique historique
  // est conservée telle quelle.
  if (opts.imagery && Object.keys(opts.imagery).length > 0) {
    const provider = resolveImageryProvider(opts.imagery, {
      maptilerKey: opts.maptilerKey,
      mapboxToken: opts.mapboxToken,
    });
    if (provider) {
      const style = buildProviderStyle(
        provider,
        { maptilerKey: opts.maptilerKey, mapboxToken: opts.mapboxToken },
        opts.imagery,
      );
      if (style) return style;
    }
  }
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

// ————————————————————————————————————————————————————————————————————————
// CAL48 — REGISTRE DE FOURNISSEURS D'IMAGERIE
//
// Jusqu'ici `buildSatelliteStyle` connaissait DEUX fournisseurs codés en dur et
// choisissait par la seule présence d'un jeton : aucun point d'entrée pour un
// troisième (parité SolarEdge Designer / Aurora, qui laissent choisir la source
// d'imagerie). Le registre ci-dessous déclare chaque fournisseur avec son
// identifiant, ses tuiles (ou son style), son ATTRIBUTION OBLIGATOIRE et sa
// résolution ANNONCÉE par le fournisseur (jamais estimée : inconnue ⇒ `null`).
//
// Le contexte vient des réglages société (CAL47, section `imagerie` de
// `GET /api/django/calepinage/parametres/` — voir `contract_samples/site_imagerie.json`) :
// `pays`, `fournisseur_imagerie`, `fournisseurs_autorises`, `attribution`.
// Section vide/absente ⇒ `buildSatelliteStyle` produit EXACTEMENT le style
// d'aujourd'hui (Mapbox si jeton, sinon MapTiler hybride).
//
// AUCUN fournisseur n'est ajouté par CAL48 : seuls `maptiler` et `mapbox`, déjà
// en place, y sont déclarés.
// ————————————————————————————————————————————————————————————————————————

/** Jetons/clés publics disponibles pour construire l'URL d'un fournisseur. */
export interface ImageryKeys {
  maptilerKey?: string;
  mapboxToken?: string;
}

export interface ImageryProvider {
  /** Identifiant stable, celui que la société pose dans `fournisseur_imagerie`. */
  id: string;
  /** Libellé affiché dans le sélecteur de l'atelier. */
  label: string;
  /** Mention légale du fournisseur, OBLIGATOIRE et affichée sur la carte. */
  attribution: string;
  /** Résolution ANNONCÉE par le fournisseur (m/pixel). `null` = non annoncée —
   *  jamais un chiffre estimé. */
  resolutionM: number | null;
  /** Pays (ISO 3166-1 alpha-2, minuscules) où le fournisseur est proposé.
   *  `null` = partout. */
  countries: readonly string[] | null;
  /** Modèles de tuiles `{z}/{x}/{y}` ; `null` = clé/jeton manquant ⇒ indisponible. */
  tiles?: (keys: ImageryKeys) => string[] | null;
  /** Style MapLibre complet servi par le fournisseur ; alternative à `tiles`. */
  styleUrl?: (keys: ImageryKeys) => string | null;
  tileSize?: number;
  maxzoom?: number;
  /** Quotas/conditions d'usage documentés, affichables à l'utilisateur. */
  quotas?: string;
}

const PROVIDERS = new Map<string, ImageryProvider>();

/** Déclare (ou remplace) un fournisseur dans le registre. */
export function registerImageryProvider(p: ImageryProvider): void {
  PROVIDERS.set(p.id, p);
}

export function getImageryProvider(id: string | null | undefined): ImageryProvider | null {
  if (!id) return null;
  return PROVIDERS.get(id) ?? null;
}

/** Tous les fournisseurs déclarés, dans l'ordre de déclaration. */
export function imageryProviders(): ImageryProvider[] {
  return [...PROVIDERS.values()];
}

registerImageryProvider({
  id: 'maptiler',
  label: 'MapTiler — hybride satellite',
  attribution:
    '© <a href="https://www.maptiler.com/copyright/" target="_blank" rel="noopener">MapTiler</a> © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  resolutionM: null,
  countries: null,
  styleUrl: (k) => (k.maptilerKey?.trim() ? maptilerHybridStyleUrl(k.maptilerKey.trim()) : null),
});

registerImageryProvider({
  id: 'mapbox',
  label: 'Mapbox Satellite (Maxar Vivid)',
  attribution:
    '© <a href="https://www.mapbox.com/about/maps/" target="_blank" rel="noopener">Mapbox</a> © <a href="https://www.maxar.com/" target="_blank" rel="noopener">Maxar</a>',
  resolutionM: null,
  countries: null,
  tiles: (k) => (k.mapboxToken?.trim() ? [mapboxSatelliteTileUrl(k.mapboxToken.trim())] : null),
  tileSize: 256,
});

/** Section `imagerie` des réglages société (CAL47), telle que servie. Toutes les
 *  clés peuvent être nulles : section vide = comportement d'aujourd'hui. */
export interface ImagerySettings {
  pays?: string | null;
  fournisseur_imagerie?: string | null;
  fournisseurs_autorises?: readonly string[] | null;
  calques_optionnels?: readonly string[] | null;
  attribution?: string | null;
}

/** Fournisseurs PROPOSABLES : ceux admis par la société (dans SON ordre), déclarés
 *  au registre, disponibles avec les clés en main et admis dans le pays du projet.
 *  Société muette ⇒ tous les fournisseurs déclarés que le pays admet. */
export function availableImageryProviders(
  settings: ImagerySettings | null | undefined,
  keys: ImageryKeys,
): ImageryProvider[] {
  const country = (settings?.pays ?? '').trim().toLowerCase() || null;
  const allowed = settings?.fournisseurs_autorises?.length
    ? settings.fournisseurs_autorises
        .map((id) => getImageryProvider(id))
        .filter((p): p is ImageryProvider => !!p)
    : imageryProviders();
  return allowed.filter((p) => {
    if (p.countries && (!country || !p.countries.includes(country))) return false;
    const tiles = p.tiles?.(keys) ?? null;
    const style = p.styleUrl?.(keys) ?? null;
    return !!(tiles?.length || style);
  });
}

/** Fournisseur ACTIF : celui nommé par la société s'il est proposable, sinon le
 *  premier proposable, sinon `null` (⇒ repli historique). */
export function resolveImageryProvider(
  settings: ImagerySettings | null | undefined,
  keys: ImageryKeys,
): ImageryProvider | null {
  const list = availableImageryProviders(settings, keys);
  const wanted = (settings?.fournisseur_imagerie ?? '').trim();
  if (wanted) {
    const hit = list.find((p) => p.id === wanted);
    if (hit) return hit;
  }
  return list[0] ?? null;
}

/** Attribution AFFICHÉE pour un fournisseur : celle du fournisseur, complétée de la
 *  mention SAISIE par la société quand elle en pose une (l'IGN impose la sienne). */
export function imageryAttribution(
  provider: ImageryProvider | null,
  settings?: ImagerySettings | null,
): string {
  const societe = (settings?.attribution ?? '').trim();
  const base = provider?.attribution ?? '';
  if (societe && base && !base.includes(societe)) return `${base} ${societe}`;
  return societe || base;
}

/** Style MapLibre (ou URL de style) d'un fournisseur du registre, attribution
 *  incluse. `null` si le fournisseur n'est pas servable avec ces clés. */
export function buildProviderStyle(
  provider: ImageryProvider,
  keys: ImageryKeys,
  settings?: ImagerySettings | null,
): string | object | null {
  const attribution = imageryAttribution(provider, settings);
  const tiles = provider.tiles?.(keys) ?? null;
  if (tiles?.length) {
    return {
      version: 8,
      sources: {
        [provider.id]: {
          type: 'raster',
          tiles,
          tileSize: provider.tileSize ?? 256,
          ...(provider.maxzoom != null ? { maxzoom: provider.maxzoom } : {}),
          attribution,
        },
      },
      layers: [{ id: provider.id, type: 'raster', source: provider.id }],
    };
  }
  const url = provider.styleUrl?.(keys) ?? null;
  return url ?? null;
}

/**
 * ═══════════════════════════════════════════════════════════════════════════
 * CONTRAT PUBLIC — DRAPÉ SATELLITE (parcours /devis/mon-toit, étape 2)
 * ═══════════════════════════════════════════════════════════════════════════
 * La page appelle DEUX choses, rien d'autre :
 *
 *   1) const spec = await buildPublicRoofImageSpec({ outline: captureOutline });
 *      — `outline` : le contour tracé, **[lat,lng]** (MÊME convention que
 *        `captureOutline` / `capturePreviewLayout`). Peut se lancer en
 *        Promise.all avec les import() dynamiques.
 *      — Renvoie `RoofImageSpec | null`. `null` = pas de photo (pas de clé
 *        imagerie, contour absent/invalide, /api/roof-config en échec, image
 *        non chargée ou délai dépassé) : c'est TOUJOURS propre, jamais un
 *        throw, jamais une texture cassée ni une erreur CORS visible.
 *
 *   2) createRoofViewer(stage, model, { reducedMotion, lowEnd,
 *        roofImage: spec,            // ← optionnel ; null/absent = rendu
 *        onReady, onFail });         //   abstrait actuel, inchangé
 *
 * Quand `roofImage` est fourni : la photo satellite du visiteur est drapée
 * sur la dalle du toit (UV géo-alignés au contour tracé, panneaux par-dessus,
 * même pipeline que l'outil interne scene3d.ts) + un plan de sol avec la même
 * image autour du bâtiment + une ligne d'attribution visible (« © Mapbox
 * © Maxar » ou « © MapTiler © Maxar ») en surimpression du canvas.
 *
 * Fournisseurs (même ordre de repli que la carte de l'étape 0,
 * buildSatelliteStyle) : token Mapbox présent → Static Images Mapbox
 * (satellite-v9, imagerie Maxar) ; sinon clé MapTiler → Static Maps MapTiler
 * (map `satellite` — pure imagerie, pas d'étiquettes drapées sur le toit) ;
 * sinon → null.
 *
 * Limite documentée : PAS de mode « pin seul » — la page n'affiche le bloc 3D
 * que si un contour ≥3 sommets existe (updatePanels3dVisibility) et
 * buildViewerModel exige lui-même un polygone ; un drapé centré sur un simple
 * repère n'aurait donc aucun point d'entrée aujourd'hui.
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * WJ25/WJ27 — VISIONNEUSE 3D EN LECTURE SEULE du toit du client (proposition).
 *
 * Dessine le `ViewerModel` PUR calculé côté serveur par lib/proposition.ts
 * (buildViewerModel) : bâtiment + pans + panneaux, avec orbite/zoom/pan
 * (souris + tactile via OrbitControls). AUCUNE UI d'édition, AUCUNE carte,
 * AUCUN optimiseur — et AUCUN import de scene3d.ts / du builder : ce module
 * est volontairement AUTONOME (la géométrie/les teintes minimales nécessaires
 * sont dupliquées ici, cf. consigne de lane).
 *
 * Chargé par import() DYNAMIQUE depuis /proposition/[token] (jamais dans le
 * bundle initial). Durcissement WJ27 :
 *  - DPR plafonné (1,5 bas de gamme / 2 sinon), antialias coupé en bas de gamme ;
 *  - rendu À LA DEMANDE (aucune boucle RAF permanente : on ne rend que pendant
 *    l'interaction + l'amortissement, et à l'init/resize) ;
 *  - récupération de PERTE DE CONTEXTE WebGL (preventDefault + rebuild) ;
 *  - prefers-reduced-motion : aucun amortissement, aucune rotation automatique
 *    (orbite manuelle uniquement) ;
 *  - dispose() libère TOUT (géométries, matériaux, renderer, écouteurs).
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { ViewerModel, ViewerZone } from '../../lib/proposition';
// Drapé satellite : on RÉUTILISE la géométrie d'image pure de lib/roofConfig.ts
// (mêmes fonctions que l'outil interne scene3d.ts — centre+zoom déterministes,
// étendue calculée, UV Mercator). Module PUR (~200 lignes, zéro dépendance) :
// le chunk lazy reste sans scene3d/maplibre/moteur de calepinage.
import {
  roofImageRequest,
  roofVertexUV,
  mapboxStaticRoofImageUrl,
  type RoofImageRequest,
} from '../../lib/roofConfig';

/** Hauteur de mur (m) — même lecture visuelle que le builder (2 niveaux × 3 m),
 *  valeur dupliquée (constants.ts appartient au builder — non importé). */
const WALL_H_M = 6;
const PANEL_THICK_M = 0.04;
const FLAT_STAND_M = 0.12;
const DEG2RAD = Math.PI / 180;
/** Mètres par degré de latitude — DOIT valoir VIEWER_DEG2M (lib/proposition.ts,
 *  111 320, non exporté) : c'est l'inverse exact du `toENU` de buildViewerModel,
 *  condition de l'alignement pixel de la photo sur le contour tracé. */
const DEG2M = 111_320;

export interface ViewerInitOptions {
  /** prefers-reduced-motion : pas d'amortissement, pas d'auto-rotation. */
  reducedMotion: boolean;
  /** Appareil modeste (mémoire ≤ 4 Go ou ≤ 4 cœurs) : DPR/AA réduits. */
  lowEnd: boolean;
  /** Appelé quand la 3D est PRÊTE (premier rendu peint) — masque le poster. */
  onReady?: () => void;
  /** Appelé si le contexte WebGL est perdu sans restauration possible. */
  onFail?: () => void;
  /** Photo satellite du toit du visiteur (buildPublicRoofImageSpec). Absent ou
   *  null → rendu abstrait actuel, strictement inchangé. */
  roofImage?: RoofImageSpec | null;
}

export interface ViewerHandle {
  dispose: () => void;
}

// ═════════════════════════════════════════════════════════════════════════════
// Drapé satellite public — types + helpers PURS (testés) + constructeur async.
// Même pipeline que l'outil interne (scene3d.ts) : roofImageRequest (centre+zoom
// déterministes) → URL Static → préchargement crossOrigin → UV via roofVertexUV.
// ═════════════════════════════════════════════════════════════════════════════

/** Fournisseur d'imagerie retenu — pilote la ligne d'attribution affichée. */
export type RoofImageryProvider = 'mapbox' | 'maptiler';

/** Réponse (partielle) de GET /api/roof-config — mêmes clés que la carte étape 0. */
export interface PublicRoofImageConfig {
  maptilerKey?: string;
  mapboxToken?: string;
}

/** Photo satellite PRÊTE À DRAPER : image déjà chargée (crossOrigin anonymous,
 *  résolue uniquement sur succès) + étendue géographique exacte + origine ENU. */
export interface RoofImageSpec {
  /** Image préchargée et décodable — jamais une URL à charger dans la scène. */
  image: HTMLImageElement;
  /** Étendue RÉELLEMENT couverte [minLng,minLat,maxLng,maxLat] (roofImageRequest). */
  extent: [number, number, number, number];
  /** Origine lng/lat de la frame ENU du modèle = centroïde du contour filtré —
   *  STRICTEMENT le même calcul que buildViewerModel (lib/proposition.ts). */
  origin: [number, number];
  provider: RoofImageryProvider;
  /** Texte d'attribution affiché en surimpression (obligation fournisseur). */
  attribution: string;
}

/** Options de buildPublicRoofImageSpec. Seul `outline` est requis. */
export interface BuildPublicRoofImageSpecOptions {
  /** Contour tracé, **[lat,lng]** — même convention que `captureOutline`. */
  outline: Array<[number, number]>;
  /** Élargissement du sol autour du toit (multiple de l'envergure). Défaut 2.5. */
  groundFactor?: number;
  /** Envergure minimale du sol (m) — un petit toit garde du contexte. Défaut 40. */
  minGroundSpanM?: number;
  /** Endpoint de configuration. Défaut '/api/roof-config' (même que la carte). */
  configUrl?: string;
  /** Délai max du fetch config (ms). Défaut 10 000 (même valeur que le boot carte). */
  fetchTimeoutMs?: number;
  /** Délai max du chargement de l'image (ms). Défaut 12 000. */
  imageTimeoutMs?: number;
  /** Injections de test — jamais nécessaires en production. */
  fetchImpl?: typeof fetch;
  loadImageImpl?: (url: string, timeoutMs: number) => Promise<HTMLImageElement | null>;
}

/** Contour [lat,lng] → sommets [lng,lat] valides — MÊME filtrage que
 *  capturePreviewLayout (lib/proposition.ts), pour que le centroïde (origine
 *  ENU du modèle) soit identique au sommet près. */
function sanitizeOutlineLatLng(outline: Array<[number, number]> | null | undefined): Array<[number, number]> {
  const pts: Array<[number, number]> = [];
  if (!Array.isArray(outline)) return pts;
  for (const pt of outline) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const [lat, lng] = pt;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    pts.push([lng, lat]);
  }
  return pts;
}

/** Origine ENU [lng,lat] du modèle pour un contour [lat,lng] donné — reproduit
 *  buildViewerModel (moyenne des sommets filtrés, même ordre). Exporté pour test.
 *  Renvoie null si moins de 3 sommets valides (aucun modèle dessinable). */
export function publicRoofOutlineOrigin(outlineLatLng: Array<[number, number]>): [number, number] | null {
  const pts = sanitizeOutlineLatLng(outlineLatLng);
  if (pts.length < 3) return null;
  let lng = 0;
  let lat = 0;
  for (const [x, y] of pts) {
    lng += x;
    lat += y;
  }
  return [lng / pts.length, lat / pts.length];
}

/** Élargit la bbox du toit pour donner du CONTEXTE au sol (même image drapée
 *  sur le plan de sol) : envergure cible = max(factor × envergure, minSpanM)
 *  par axe, centrée sur la bbox. Pure, exportée pour test. */
export function expandRoofBBox(
  bbox: [number, number, number, number],
  factor = 2.5,
  minSpanM = 40,
): [number, number, number, number] {
  const [minLng, minLat, maxLng, maxLat] = bbox;
  const midLat = (minLat + maxLat) / 2;
  const cosLat = Math.max(0.1, Math.cos(midLat * DEG2RAD));
  const spanLngM = Math.max(0, (maxLng - minLng) * DEG2M * cosLat);
  const spanLatM = Math.max(0, (maxLat - minLat) * DEG2M);
  const padLngM = (Math.max(spanLngM * factor, minSpanM) - spanLngM) / 2;
  const padLatM = (Math.max(spanLatM * factor, minSpanM) - spanLatM) / 2;
  const padLng = padLngM / (DEG2M * cosLat);
  const padLat = padLatM / DEG2M;
  return [minLng - padLng, minLat - padLat, maxLng + padLng, maxLat + padLat];
}

/** URL Static Maps MapTiler (map `satellite` — PURE imagerie : la variante
 *  hybrid draperait rues/étiquettes sur le toit), mêmes sémantiques centre+zoom
 *  512px que Mapbox Static (rendu MapLibre) → roofImageRequest s'applique tel
 *  quel. `attribution=false` retire le cachet incrusté dans l'image (il serait
 *  peint SUR le toit) ; l'attribution reste affichée par la visionneuse. Bornes
 *  miroir de mapboxStaticRoofImageUrl (1–1280 px, zoom ≤ 22 — sous-ensemble sûr
 *  des limites MapTiler). Exportée pour test. */
export function maptilerStaticRoofImageUrl(
  key: string,
  center: [number, number],
  zoom: number,
  w: number,
  h: number,
): string {
  const [lng, lat] = center;
  const z = Math.max(0, Math.min(22, zoom));
  const W = Math.max(1, Math.min(1280, Math.round(w)));
  const H = Math.max(1, Math.min(1280, Math.round(h)));
  return `https://api.maptiler.com/maps/satellite/static/${lng},${lat},${z.toFixed(4)}/${W}x${H}@2x.jpg?key=${encodeURIComponent(key)}&attribution=false`;
}

/** Choisit le fournisseur d'imagerie + construit l'URL Static — MÊME ordre de
 *  repli que la carte de l'étape 0 (buildSatelliteStyle) : Mapbox si token,
 *  sinon MapTiler si clé, sinon null (le rendu abstrait reste). Pure, exportée
 *  pour test. */
export function publicRoofImageUrl(
  cfg: PublicRoofImageConfig,
  req: RoofImageRequest,
): { url: string; provider: RoofImageryProvider; attribution: string } | null {
  const token = (cfg.mapboxToken ?? '').trim();
  if (token) {
    return {
      url: mapboxStaticRoofImageUrl(token, req.center, req.zoom, req.w, req.h),
      provider: 'mapbox',
      attribution: '© Mapbox © Maxar',
    };
  }
  const key = (cfg.maptilerKey ?? '').trim();
  if (key) {
    return {
      url: maptilerStaticRoofImageUrl(key, req.center, req.zoom, req.w, req.h),
      provider: 'maptiler',
      attribution: '© MapTiler © Maxar',
    };
  }
  return null;
}

/** Précharge l'image satellite (crossOrigin anonymous — impératif pour une
 *  texture WebGL non « tainted ») ; résout null sur erreur OU délai dépassé,
 *  jamais de rejet. */
function loadRoofImage(url: string, timeoutMs: number): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    if (typeof Image === 'undefined') {
      resolve(null);
      return;
    }
    let settled = false;
    const settle = (v: HTMLImageElement | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(v);
    };
    const timer = setTimeout(() => settle(null), timeoutMs);
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => settle(img);
    img.onerror = () => settle(null);
    img.src = url;
  });
}

/**
 * Construit le RoofImageSpec du parcours public : (a) lit /api/roof-config
 * (mêmes clés que la carte étape 0) ; (b) calcule la requête d'image
 * déterministe sur la bbox ÉLARGIE du contour (toit + contexte sol, une seule
 * image pour les deux) ; (c) précharge l'image. TOUT échec → null, silencieux :
 * pas de contour valide, pas de clé, réseau/HTTP en échec, image cassée ou
 * trop lente — la visionneuse garde alors son rendu abstrait actuel.
 */
export async function buildPublicRoofImageSpec(
  opts: BuildPublicRoofImageSpecOptions,
): Promise<RoofImageSpec | null> {
  try {
    const pts = sanitizeOutlineLatLng(opts.outline);
    const origin = publicRoofOutlineOrigin(opts.outline);
    if (pts.length < 3 || !origin) return null;

    const doFetch =
      opts.fetchImpl ?? ((input: RequestInfo | URL, init?: RequestInit) => fetch(input, init));
    let cfg: PublicRoofImageConfig | null = null;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.fetchTimeoutMs ?? 10_000);
    try {
      const res = await doFetch(opts.configUrl ?? '/api/roof-config', { signal: ctrl.signal });
      if (!res.ok) return null;
      cfg = (await res.json()) as PublicRoofImageConfig;
    } finally {
      clearTimeout(timer);
    }
    if (!cfg) return null;

    let minLng = Infinity;
    let minLat = Infinity;
    let maxLng = -Infinity;
    let maxLat = -Infinity;
    for (const [lng, lat] of pts) {
      if (lng < minLng) minLng = lng;
      if (lat < minLat) minLat = lat;
      if (lng > maxLng) maxLng = lng;
      if (lat > maxLat) maxLat = lat;
    }
    const req = roofImageRequest(
      expandRoofBBox([minLng, minLat, maxLng, maxLat], opts.groundFactor, opts.minGroundSpanM),
    );
    const picked = publicRoofImageUrl(cfg, req);
    if (!picked) return null;

    const load = opts.loadImageImpl ?? loadRoofImage;
    const image = await load(picked.url, opts.imageTimeoutMs ?? 12_000);
    if (!image) return null;

    return { image, extent: req.extent, origin, provider: picked.provider, attribution: picked.attribution };
  } catch {
    // Réseau, JSON invalide, AbortError… — repli abstrait, jamais d'erreur visible.
    return null;
  }
}

/** ENU (m, origine [lng,lat]) → lng/lat — inverse EXACT du `toENU` de
 *  buildViewerModel. Exporté pour test (aller-retour au sommet près). */
export function enuToLngLat(x: number, y: number, origin: [number, number]): [number, number] {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return [origin[0] + x / (DEG2M * cosLat), origin[1] + y / DEG2M];
}

/** Pose les UV géo-alignés d'une géométrie dont les positions sont en ENU :
 *  chaque sommet est reprojeté en lng/lat (via l'origine du modèle) puis en UV
 *  dans l'étendue EXACTE de l'image — même logique que setDeckUVs (scene3d.ts). */
function setEnuUVs(geo: THREE.BufferGeometry, spec: RoofImageSpec): void {
  const pos = geo.attributes.position as THREE.BufferAttribute;
  const uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {
    const [lng, lat] = enuToLngLat(pos.getX(i), pos.getY(i), spec.origin);
    const [u, v] = roofVertexUV(lng, lat, spec.extent);
    uv[i * 2] = u;
    uv[i * 2 + 1] = v;
  }
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
}

/**
 * WJ90 — Pas de rotation au clavier (radians par pression de flèche). ≈ 6°,
 * un cran de lecture confortable (ni trop lent à explorer, ni un saut brutal).
 */
export const KEY_ROTATE_RAD = (6 * Math.PI) / 180;

/**
 * WJ90 — Facteur de zoom au clavier (+/-), même échelle qu'un cran de molette
 * standard (`dollyIn`/`dollyOut` attendent un facteur multiplicatif > 1).
 */
export const KEY_ZOOM_SCALE = 1.12;

/** Cap DPR : net sur mobile sans surcharger le GPU (WJ27). Exporté pour test. */
export function viewerDprCap(devicePixelRatio: number, lowEnd: boolean): number {
  const dpr = Number.isFinite(devicePixelRatio) && devicePixelRatio > 0 ? devicePixelRatio : 1;
  return Math.min(dpr, lowEnd ? 1.5 : 2);
}

/** Sonde WebGL SANS créer de renderer (repli poster propre quand absent). */
export function webglAvailable(): boolean {
  try {
    const probe = document.createElement('canvas');
    return !!(probe.getContext('webgl2') || probe.getContext('webgl'));
  } catch {
    return false;
  }
}

// ── WJ27 — décisions de démarrage PURES (device/réseau) ─────────────────────
// Extraites du script inline de [token].astro pour être testables sans DOM :
// même logique, une seule source de vérité, zéro divergence entre les deux.

/** Signaux navigateur bruts consommés par `detectLowEnd` / `viewerBootStrategy`. */
export interface ViewerDeviceSignals {
  /** navigator.deviceMemory (Go), absent sur beaucoup de navigateurs. */
  deviceMemory?: number;
  /** navigator.hardwareConcurrency (cœurs logiques). */
  hardwareConcurrency?: number;
  /** navigator.connection.saveData (Data Saver activé). */
  saveData?: boolean;
  /** prefers-reduced-motion: reduce. */
  reducedMotion?: boolean;
  /** WebGL (1 ou 2) disponible sur cet appareil. */
  webglAvailable?: boolean;
}

/**
 * WJ27 — Appareil « bas de gamme » : ≤ 4 Go de RAM déclarés OU ≤ 4 cœurs
 * logiques. `hardwareConcurrency` absent est traité comme 8 (repli neutre,
 * ne déclenche pas le mode bas de gamme sur un navigateur qui ne l'expose pas).
 */
export function detectLowEnd(signals: ViewerDeviceSignals): boolean {
  const mem = signals.deviceMemory;
  const cores = signals.hardwareConcurrency ?? 8;
  return (mem != null && mem <= 4) || cores <= 4;
}

/** Décision finale de démarrage/repli de la visionneuse 3D (WJ27). */
export interface ViewerBootStrategy {
  /** Faux → la visionneuse ne se lance JAMAIS (repli poster PNG immédiat). */
  canBoot: boolean;
  /** Message FR de repli à afficher quand `canBoot` est faux. */
  fallbackMessage: string | null;
  /** Vrai → préchargement automatique au scroll (IntersectionObserver). */
  autoPreload: boolean;
  /** Vrai → amortissement/inertie de la caméra activé (désactivé en reduced-motion). */
  damping: boolean;
  /** Vrai → DPR/anti-aliasing réduits (appareil bas de gamme). */
  lowEnd: boolean;
}

/**
 * WJ27 — Traduit les signaux navigateur en stratégie de démarrage, SANS DOM :
 *  - WebGL absent → jamais de boot, repli PNG immédiat (poster déjà affiché) ;
 *  - reduced-motion → orbite manuelle uniquement (aucun amortissement/auto-lancement
 *    au scroll) : le visiteur doit taper « Explorer » explicitement ;
 *  - Save-Data actif → jamais de préchargement au scroll (même logique que
 *    reduced-motion : geste explicite requis), pour ne pas gaspiller de data ;
 *  - sinon → préchargement au scroll, amortissement actif.
 * Pure et déterministe — c'est la même logique que le script inline de
 * [token].astro, extraite ici pour rester testable et pour n'avoir qu'une seule
 * source de vérité.
 */
export function viewerBootStrategy(signals: ViewerDeviceSignals): ViewerBootStrategy {
  const lowEnd = detectLowEnd(signals);
  const reduced = signals.reducedMotion === true;
  const saveData = signals.saveData === true;
  if (signals.webglAvailable === false) {
    return {
      canBoot: false,
      fallbackMessage: 'Vue 3D indisponible sur cet appareil — voici la photo de votre étude.',
      autoPreload: false,
      damping: false,
      lowEnd,
    };
  }
  return {
    canBoot: true,
    fallbackMessage: null,
    // Reduced-motion ET Save-Data exigent un geste explicite (bouton « Explorer »)
    // avant tout chargement — jamais de préchargement silencieux dans ces deux cas.
    autoPreload: !reduced && !saveData,
    damping: !reduced,
    lowEnd,
  };
}

/** Hauteur du plan incliné au point (x,y) d'un pan (0 à l'égout, monte vers l'amont). */
function pitchedRiseAt(
  x: number,
  y: number,
  f: [number, number],
  dEave: number,
  tiltRad: number,
): number {
  const d = x * f[0] + y * f[1];
  return Math.max(0, (dEave - d) * Math.tan(tiltRad));
}

/** Drapé prêt à l'emploi passé à buildZone : spec géo + texture THREE partagée. */
interface RoofDrape {
  spec: RoofImageSpec;
  texture: THREE.Texture;
}

/** Plan de sol drapé de la MÊME image satellite que le toit : rectangle ENU de
 *  l'étendue exacte de l'image (UV 0→1 par construction géo, même helper que la
 *  dalle → alignement identique), posé juste sous le bâtiment. L'outil interne
 *  n'en a pas besoin (la carte MapLibre EST son sol) ; ici il restitue le
 *  quartier du visiteur autour de sa maison. */
function buildGroundPlane(
  root: THREE.Group,
  drape: RoofDrape,
  disposables: Array<{ dispose: () => void }>,
): void {
  const [minLng, minLat, maxLng, maxLat] = drape.spec.extent;
  const [lng0, lat0] = drape.spec.origin;
  const cosLat = Math.cos(lat0 * DEG2RAD);
  const x0 = (minLng - lng0) * DEG2M * cosLat;
  const x1 = (maxLng - lng0) * DEG2M * cosLat;
  const y0 = (minLat - lat0) * DEG2M;
  const y1 = (maxLat - lat0) * DEG2M;
  if (!(x1 > x0) || !(y1 > y0)) return;
  const shape = new THREE.Shape();
  shape.moveTo(x0, y0);
  shape.lineTo(x1, y0);
  shape.lineTo(x1, y1);
  shape.lineTo(x0, y1);
  shape.closePath();
  const geo = new THREE.ShapeGeometry(shape);
  setEnuUVs(geo, drape.spec);
  const mat = new THREE.MeshStandardMaterial({ color: 0xffffff, map: drape.texture, roughness: 1, metalness: 0 });
  const ground = new THREE.Mesh(geo, mat);
  ground.position.z = -0.02; // juste sous le pied du bâtiment (z=0)
  root.add(ground);
  disposables.push(geo, mat);
}

/** Construit tous les meshes d'une zone dans `root`. Renvoie les ressources à libérer. */
function buildZone(
  root: THREE.Group,
  zone: ViewerZone,
  disposables: Array<{ dispose: () => void }>,
  drape: RoofDrape | null = null,
): void {
  const ring = zone.ringENU;
  if (ring.length < 3) return;

  const shape = new THREE.Shape();
  ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();

  // Bâtiment (mêmes teintes de lecture que le builder — valeurs dupliquées).
  const buildingMat = new THREE.MeshStandardMaterial({ color: 0xe2e7f2, roughness: 0.85, metalness: 0 });
  const buildingGeo = new THREE.ExtrudeGeometry(shape, { depth: WALL_H_M, bevelEnabled: false });
  const building = new THREE.Mesh(buildingGeo, buildingMat);
  root.add(building);
  disposables.push(buildingGeo, buildingMat);

  const az = zone.azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(az), Math.cos(az)];
  const tiltRad = zone.tiltDeg * DEG2RAD;
  const pitched = zone.roofType === 'pitched';
  // Égout = point le plus AVAL (projection max sur la direction de face).
  let dEave = -Infinity;
  for (const [x, y] of ring) dEave = Math.max(dEave, x * f[0] + y * f[1]);

  // Dalle / pan : plan horizontal (plat) ou incliné (pente) — sommets relevés.
  const deckGeo = new THREE.ShapeGeometry(shape);
  if (pitched) {
    const pos = deckGeo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      pos.setZ(i, pitchedRiseAt(pos.getX(i), pos.getY(i), f, dEave, tiltRad));
    }
    pos.needsUpdate = true;
    deckGeo.computeVertexNormals();
  }
  // Drapé satellite : la VRAIE photo du toit, UV géo-alignés au contour tracé
  // (même pipeline que applyRoofPhoto/setDeckUVs de l'outil interne) ; sans
  // drapé → dalle grise historique, inchangée.
  if (drape) setEnuUVs(deckGeo, drape.spec);
  const deckMat = drape
    ? new THREE.MeshStandardMaterial({ color: 0xffffff, map: drape.texture, roughness: 0.95, metalness: 0 })
    : new THREE.MeshStandardMaterial({ color: 0xb9bfca, roughness: 0.95, metalness: 0 });
  const deck = new THREE.Mesh(deckGeo, deckMat);
  deck.position.z = WALL_H_M + 0.02;
  root.add(deck);
  disposables.push(deckGeo, deckMat);

  // Pente : jupe périmétrique simple pour fermer le volume sous le pan incliné.
  if (pitched) {
    const positions: number[] = [];
    const n = ring.length;
    for (let i = 0; i < n; i++) {
      const [ax, ay] = ring[i];
      const [bx, by] = ring[(i + 1) % n];
      const za = 0.02 + pitchedRiseAt(ax, ay, f, dEave, tiltRad);
      const zb = 0.02 + pitchedRiseAt(bx, by, f, dEave, tiltRad);
      positions.push(ax, ay, 0, bx, by, 0, bx, by, zb);
      positions.push(ax, ay, 0, bx, by, zb, ax, ay, za);
    }
    const skirtGeo = new THREE.BufferGeometry();
    skirtGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(positions), 3));
    skirtGeo.computeVertexNormals();
    const skirtMat = new THREE.MeshStandardMaterial({
      color: 0xe2e7f2,
      roughness: 0.85,
      metalness: 0,
      side: THREE.DoubleSide,
    });
    const skirt = new THREE.Mesh(skirtGeo, skirtMat);
    skirt.position.z = WALL_H_M;
    root.add(skirt);
    disposables.push(skirtGeo, skirtMat);
  }

  // Obstacles : boîtes discrètes (lecture seule, non manipulables).
  for (const o of zone.obstaclesENU) {
    const geo = new THREE.BoxGeometry(o.widthM, o.lengthM, 0.9);
    const mat = new THREE.MeshStandardMaterial({ color: 0x9aa3b4, roughness: 0.8, metalness: 0 });
    const mesh = new THREE.Mesh(geo, mat);
    const zTop = pitched ? pitchedRiseAt(o.x, o.y, f, dEave, tiltRad) : 0;
    mesh.position.set(o.x, o.y, WALL_H_M + zTop + 0.45);
    root.add(mesh);
    disposables.push(geo, mat);
  }

  // Panneaux : InstancedMesh unique (verre sombre — lecture immédiate « panneau »).
  if (zone.panels.length > 0) {
    const panelGeo = new THREE.BoxGeometry(zone.panelAlongM, zone.panelDepthM / Math.cos(tiltRad) || zone.panelDepthM, PANEL_THICK_M);
    const panelMat = new THREE.MeshStandardMaterial({ color: 0x14263f, roughness: 0.25, metalness: 0.35 });
    const im = new THREE.InstancedMesh(panelGeo, panelMat, zone.panels.length);
    const rowAngle = Math.atan2(f[0], -f[1]); // rangée ⟂ face
    const qz = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), rowAngle);
    const qx = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), tiltRad);
    const q = qz.clone().multiply(qx);
    const scl = new THREE.Vector3(1, 1, 1);
    const rise = (zone.panelDepthM / Math.cos(tiltRad) || zone.panelDepthM) * Math.sin(tiltRad);
    const m = new THREE.Matrix4();
    for (let i = 0; i < zone.panels.length; i++) {
      const p = zone.panels[i];
      const zBase = pitched
        ? WALL_H_M + 0.02 + pitchedRiseAt(p.x, p.y, f, dEave, tiltRad) + 0.06
        : WALL_H_M + FLAT_STAND_M + rise / 2 + 0.07;
      m.compose(new THREE.Vector3(p.x, p.y, zBase), q, scl);
      im.setMatrixAt(i, m);
    }
    im.instanceMatrix.needsUpdate = true;
    root.add(im);
    disposables.push(panelGeo, panelMat, im);
  }
}

/**
 * Monte la visionneuse dans `container` (le canvas est créé ici, positionné en
 * absolu — le conteneur DOIT déjà réserver sa hauteur : zéro CLS). Renvoie un
 * handle `dispose()` ou `null` si WebGL est indisponible.
 */
export function createRoofViewer(
  container: HTMLElement,
  model: ViewerModel,
  opts: ViewerInitOptions,
): ViewerHandle | null {
  if (!webglAvailable()) return null;
  if (!model || !Array.isArray(model.zones) || model.zones.length === 0) return null;

  const canvas = document.createElement('canvas');
  canvas.style.position = 'absolute';
  canvas.style.inset = '0';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  // WJ90 — le canvas est désormais FOCUSABLE (tabindex) : un visiteur clavier
  // (Tab jusqu'ici) peut tourner/zoomer sans souris ni tactile (voir le
  // gestionnaire keydown ci-dessous). aria-label documente les DEUX modes.
  canvas.setAttribute(
    'aria-label',
    'Vue 3D interactive de votre toiture — faites glisser pour tourner, pincez ou molette pour zoomer ; flèches pour tourner, + ou − pour zoomer au clavier',
  );
  canvas.setAttribute('role', 'img');
  canvas.tabIndex = 0;
  container.appendChild(canvas);

  // ── Drapé satellite (optionnel) : texture partagée dalle+sol + attribution.
  const roofImage = opts.roofImage ?? null;
  let drape: RoofDrape | null = null;
  if (roofImage) {
    const texture = new THREE.Texture(roofImage.image);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8; // même réglage que l'outil interne (applyRoofPhoto)
    texture.needsUpdate = true;
    drape = { spec: roofImage, texture };
  }
  // Attribution fournisseur VISIBLE dès qu'une imagerie est affichée (exigence
  // Mapbox/MapTiler — l'image Static est demandée sans cachet incrusté, sinon
  // il serait peint sur le toit). Même esprit que l'AttributionControl de la
  // carte étape 0, en surimpression discrète du canvas.
  let attributionEl: HTMLElement | null = null;
  if (drape) {
    attributionEl = document.createElement('div');
    attributionEl.textContent = drape.spec.attribution;
    const s = attributionEl.style;
    s.position = 'absolute';
    s.right = '6px';
    s.bottom = '4px';
    s.font = '10px/1.5 system-ui, sans-serif';
    s.color = 'rgba(255,255,255,0.85)';
    s.background = 'rgba(7,11,29,0.55)';
    s.padding = '1px 6px';
    s.borderRadius = '4px';
    s.pointerEvents = 'none';
    container.appendChild(attributionEl);
  }

  let renderer: THREE.WebGLRenderer | null = null;
  let glLost = false;
  let disposed = false;

  const scene = new THREE.Scene();
  const root = new THREE.Group();
  scene.add(root);
  scene.add(new THREE.AmbientLight(0xb9c8ee, 0.55));
  scene.add(new THREE.HemisphereLight(0xcfe0ff, 0x20242e, 0.6));
  const sun = new THREE.DirectionalLight(0xfff2d6, 2.2);
  sun.position.set(-40, -60, 80);
  scene.add(sun);

  const disposables: Array<{ dispose: () => void }> = [];
  if (drape) {
    disposables.push(drape.texture);
    buildGroundPlane(root, drape, disposables);
  }
  for (const zone of model.zones) buildZone(root, zone, disposables, drape);

  const radius = Math.max(model.radiusM, 6);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, radius * 40);
  camera.up.set(0, 0, 1); // Z vertical (frame ENU)
  camera.position.set(radius * 1.2, -radius * 1.6, radius * 1.3 + WALL_H_M);

  function buildRenderer(): boolean {
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: !opts.lowEnd, alpha: true });
    } catch {
      return false;
    }
    renderer.setPixelRatio(viewerDprCap(window.devicePixelRatio, opts.lowEnd));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    if (drape) {
      // Même pipeline de rendu que l'outil interne quand une PHOTO est affichée
      // (scene3d.ts) : le tone mapping filmique compresse les hautes lumières —
      // sans lui, l'éclairage de la scène surexpose la photo. Le rendu abstrait
      // (sans drapé) reste strictement inchangé (NoToneMapping par défaut).
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
    }
    resize();
    return true;
  }

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 0, WALL_H_M);
  controls.enableDamping = !opts.reducedMotion;
  controls.dampingFactor = 0.08;
  controls.autoRotate = false; // jamais de rotation automatique (lecture calme)
  controls.minDistance = Math.max(4, radius * 0.5);
  controls.maxDistance = radius * 8;
  controls.maxPolarAngle = Math.PI / 2 - 0.05; // jamais sous le sol
  controls.enablePan = true;
  controls.update();

  // ── Rendu À LA DEMANDE (WJ27) : on ne rend que quand quelque chose a changé.
  let rafId = 0;
  let dampingUntil = 0;
  function renderOnce(): void {
    if (disposed || glLost || !renderer) return;
    renderer.render(scene, camera);
  }
  function tick(): void {
    rafId = 0;
    if (disposed || glLost) return;
    const damping = controls.enableDamping && performance.now() < dampingUntil;
    controls.update();
    renderOnce();
    if (damping) scheduleRender();
  }
  function scheduleRender(): void {
    if (!rafId && !disposed) rafId = requestAnimationFrame(tick);
  }
  controls.addEventListener('change', scheduleRender);
  controls.addEventListener('start', () => {
    dampingUntil = Number.MAX_SAFE_INTEGER;
    scheduleRender();
  });
  controls.addEventListener('end', () => {
    // Laisse l'amortissement s'éteindre (~1 s) puis stoppe toute boucle.
    dampingUntil = performance.now() + (controls.enableDamping ? 1000 : 0);
    scheduleRender();
  });

  function resize(): void {
    if (!renderer) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w === 0 || h === 0) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    scheduleRender();
  }
  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
  ro?.observe(container);

  // ── WJ27 — perte / restauration de contexte WebGL (mobile arrière-plan).
  function onContextLost(e: Event): void {
    e.preventDefault(); // impératif : sans lui, jamais de webglcontextrestored
    glLost = true;
    renderer?.dispose();
    renderer = null;
  }
  function onContextRestored(): void {
    if (disposed) return;
    if (buildRenderer()) {
      glLost = false;
      scheduleRender();
    } else {
      opts.onFail?.();
    }
  }
  canvas.addEventListener('webglcontextlost', onContextLost, false);
  canvas.addEventListener('webglcontextrestored', onContextRestored, false);

  // ── WJ90 — clavier : flèches tournent la caméra, +/- (ou =/_) zooment.
  // Le canvas est focusable (tabindex, ci-dessus) ; on n'utilise PAS le
  // key-handling intégré d'OrbitControls (pan par défaut sur les flèches,
  // sans zoom clavier) mais les méthodes publiques rotateLeft/rotateUp/
  // dollyIn/dollyOut, qui appellent déjà controls.update() en interne.
  function onKeyDown(e: KeyboardEvent): void {
    let handled = true;
    switch (e.key) {
      case 'ArrowLeft':
        controls.rotateLeft(-KEY_ROTATE_RAD);
        break;
      case 'ArrowRight':
        controls.rotateLeft(KEY_ROTATE_RAD);
        break;
      case 'ArrowUp':
        controls.rotateUp(KEY_ROTATE_RAD);
        break;
      case 'ArrowDown':
        controls.rotateUp(-KEY_ROTATE_RAD);
        break;
      case '+':
      case '=':
        controls.dollyIn(KEY_ZOOM_SCALE);
        break;
      case '-':
      case '_':
        controls.dollyOut(KEY_ZOOM_SCALE);
        break;
      default:
        handled = false;
    }
    if (handled) {
      e.preventDefault(); // empêche le défilement de page sur les flèches
      scheduleRender();
    }
  }
  canvas.addEventListener('keydown', onKeyDown);

  if (!buildRenderer()) {
    canvas.remove();
    attributionEl?.remove();
    controls.dispose();
    for (const d of disposables) d.dispose();
    return null;
  }
  renderOnce();
  opts.onReady?.();

  function dispose(): void {
    if (disposed) return;
    disposed = true;
    if (rafId) cancelAnimationFrame(rafId);
    ro?.disconnect();
    canvas.removeEventListener('webglcontextlost', onContextLost, false);
    canvas.removeEventListener('webglcontextrestored', onContextRestored, false);
    canvas.removeEventListener('keydown', onKeyDown);
    controls.dispose();
    for (const d of disposables) d.dispose();
    renderer?.dispose();
    renderer = null;
    canvas.remove();
    attributionEl?.remove();
  }

  return { dispose };
}

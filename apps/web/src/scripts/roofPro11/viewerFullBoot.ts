/**
 * ═══════════════════════════════════════════════════════════════════════════
 * VISIONNEUSE PLEINE — le VRAI builder, en lecture seule, pour le client
 * ═══════════════════════════════════════════════════════════════════════════
 * Le client qui ouvre sa proposition doit voir EXACTEMENT le toit conçu dans
 * l'ERP : la même carte satellite, le même bâtiment, les mêmes panneaux (verre,
 * cadres, rails, châssis de toit plat, ombres portées) — et pouvoir tourner,
 * pencher, dézoomer jusqu'à la ville entière. Ce qu'il ne doit PAS pouvoir
 * faire : changer quoi que ce soit. Le calepinage est FIGÉ.
 *
 * COMMENT — un boot PARTIEL du builder, sur le précédent exact de
 * `captureBoot.ts` (mode W112 « capture », carte seule, sans 3D) : on construit
 * la carte MapLibre + `createScene3d` et RIEN D'AUTRE. Ni `createMapDraw` (tracé
 * / géocodeur), ni `createObstaclesUi`, ni `createLayoutEditor`, ni
 * `createOptimizer`, ni `createMatrix`, ni `createProdWindow` : ces modules ne
 * sont même pas importés, donc aucun geste d'édition n'existe dans ce mode. Le
 * SEUL écouteur posé sur la carte est `load` (+ `error`) ; aucun `click`,
 * `dblclick`, `mousedown` ni `touchstart` — dessiner, déplacer un sommet,
 * poser un obstacle ou sélectionner un panneau est IMPOSSIBLE, pas seulement
 * désactivé. Restent les gestes CAMÉRA natifs de MapLibre (orbite, inclinaison,
 * translation, zoom/dézoom sans borne).
 *
 * AUCUN COPIER-COLLER : la scène est `roofPro11/scene3d.ts` lui-même — le
 * module que l'ERP utilise. Il reçoit `readOnly: true` (option additive, cf.
 * `Scene3dDeps`) qui retire les seules marques d'ÉDITION du rendu : pans non
 * actifs plus atténués, et pas d'étiquette de cote sur les obstacles.
 *
 * HYDRATATION — depuis le `roof_layout` public (celui de `parseRoofLayout`,
 * lib/proposition.ts). Toute la traduction layout → plans de rendu vit dans
 * `viewerFullModel.ts` (pur, testé) ; sans calepinage réel (`geometry`, anciens
 * liens) `boot` renvoie `null` et l'appelant garde `viewerOnly.ts`.
 *
 * POIDS — ce module tire Three.js + MapLibre : il ne doit JAMAIS être importé
 * statiquement par une page. Même discipline que WJ27/WJ47 : `await
 * import('../../scripts/roofPro11/viewerFullBoot')` au tap/scroll, jamais dans
 * le chunk initial.
 */
import maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { type RoofLayout } from '../../lib/proposition';
import { buildSatelliteStyle } from '../../lib/roofConfig';
import { PITCH_VIEW } from './constants';
import { type Ctx } from './context';
import { createScene3d } from './scene3d';
import { type InitOptions } from './types';
import { buildViewerFullPlan, viewerAreaRecords, zoomForSpanM } from './viewerFullModel';

/** Jour de l'année du solstice d'hiver — MÊME soleil par défaut que le builder
 *  (midi au solstice : l'élévation de design de l'espacement anti-ombrage, où
 *  les rangées se dégagent visiblement). Aucun réglage n'est offert au client. */
const WINTER_SOLSTICE_DAY = 355;
const DEFAULT_SUN_HOUR = 12;

export interface ViewerFullOptions {
  /** Clé MapTiler PUBLIQUE (/api/roof-config) — repli imagerie si pas de Mapbox. */
  maptilerKey?: string;
  /** Token Mapbox PUBLIC (/api/roof-config) — imagerie Maxar + photo drapée sur la dalle. */
  mapboxToken?: string;
  /** `prefers-reduced-motion` : aucun vol de caméra, aucun fondu de tuiles. */
  reducedMotion?: boolean;
  /** Appareil modeste → antialias coupé + ombres 1024 (même règle que l'ERP). */
  lowEnd?: boolean;
  /** Inclinaison initiale (°). Défaut : la vue 3D du builder (PITCH_VIEW = 58). */
  pitchDeg?: number;
  /** Orientation initiale (°, 0 = Nord en haut, comme l'ERP). */
  bearingDeg?: number;
  /**
   * Gestes coopératifs (défaut TRUE) : sur mobile la carte ne bouge qu'à DEUX
   * doigts et sur desktop le zoom molette demande Ctrl/⌘ — sans quoi une carte
   * plein cadre au milieu d'une page longue capture le défilement du visiteur.
   * Passer `false` pour des gestes directs.
   */
  cooperativeGestures?: boolean;
  /** Appelé une fois la carte prête ET la scène rendue (masque le voile de chargement). */
  onReady?: () => void;
  /**
   * Panne carte : soit une erreur SURVENUE EN SESSION (tuiles/style, après un
   * premier rendu), soit une carte qui ne se charge JAMAIS (réseau muet) —
   * sans ce second cas, un visiteur hors couverture resterait devant un voile
   * de chargement éternel. La page peut alors replier sur sa photo d'étude.
   */
  onMapError?: () => void;
  /** Délai au-delà duquel une carte qui n'a pas chargé est déclarée en panne
   *  (ms, défaut 15 000 — même ordre que le fetch de config du parcours). */
  loadTimeoutMs?: number;
}

export interface ViewerFullHandle {
  /** Libère TOUT (couche 3D → onRemove de scene3d : meshes, textures, renderer ; puis la carte). */
  destroy: () => void;
  /** Nombre de panneaux RÉELLEMENT dessinés (somme des pans) — pour un test/diagnostic. */
  panelCount: number;
}

/** La feuille MapLibre n'est injectée qu'UNE fois par document (idempotent). */
function ensureMaplibreCss(): void {
  if (typeof document === 'undefined') return;
  if (document.querySelector('link[data-rp9-maplibre-css]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = maplibreCssUrl;
  link.dataset.rp9MaplibreCss = '1';
  document.head.appendChild(link);
}

/** WebGL disponible ? (même sonde que `initRoofToolPro8`, sans jeter.) */
function hasWebgl(): boolean {
  try {
    const probe = document.createElement('canvas');
    return !!(probe.getContext('webgl2') || probe.getContext('webgl'));
  } catch {
    return false;
  }
}

/**
 * Démarre la visionneuse pleine dans `el` à partir d'un `roof_layout` validé.
 *
 * Renvoie `null` — refus PROPRE, jamais un throw, l'appelant garde alors la
 * visionneuse simplifiée `viewerOnly.ts` — quand : le conteneur manque, WebGL
 * est indisponible, aucune clé d'imagerie n'est fournie (pas de carte possible),
 * ou le layout ne porte aucun calepinage réel (anciens liens sans `geometry`).
 */
export function bootViewerFull(
  el: HTMLElement | null,
  layout: RoofLayout | null | undefined,
  opts: ViewerFullOptions = {},
): ViewerFullHandle | null {
  if (!el) return null;
  const plan = buildViewerFullPlan(layout);
  if (!plan) return null;
  const maptilerKey = (opts.maptilerKey ?? '').trim();
  const mapboxToken = (opts.mapboxToken ?? '').trim();
  if (!maptilerKey && !mapboxToken) return null; // aucune imagerie → pas de carte
  if (!hasWebgl()) return null;

  const active = plan.zones[plan.activeIndex];
  const activePlan = active.plan;
  if (!activePlan) return null; // garanti par buildViewerFullPlan — ceinture + bretelles

  const reducedMotion = opts.reducedMotion === true;
  const lowEnd = opts.lowEnd === true;
  const shadowSize = lowEnd ? 1024 : 2048;

  ensureMaplibreCss();

  // — Contexte builder MINIMAL : scene3d ne lit qu'une quinzaine de champs
  //   (opts.mapboxToken, vertices, obstacles, areas, activeAreaId, activeArea,
  //   sceneOrigin, obstacleMeshes, activePanel*, selectedObsId, layout*, sunHour,
  //   sunDay, shadeObstructions). On caste un objet partiel, MÊME procédé que
  //   `captureBoot.ts` : aucun autre champ n'existe dans ce mode.
  const toolOpts: InitOptions = { maptilerKey, mapboxToken, reducedMotion };
  const areas = viewerAreaRecords(plan);
  const ctx = {
    opts: toolOpts,
    // Contour du pan ACTIF : c'est lui qui borne la photo satellite drapée sur
    // la dalle (`applyRoofPhoto` lit `ctx.vertices`), exactement comme l'ERP.
    vertices: active.vertices,
    closed: true,
    obstacles: active.obstacles,
    centroid: plan.center,
    selectedObsId: null,
    obstacleMeshes: new Map(),
    sceneOrigin: activePlan.pack.origin,
    activePanelMesh: null,
    activePanelCellIndex: [],
    areas,
    activeAreaId: active.id,
    activeArea: () => areas.find((a) => a.id === active.id),
    // Aucun éditeur de disposition n'existe ici ; renderScene écrit ces champs
    // (plan gagnant mémorisé) et rien ne les relit.
    layoutMode: false,
    layoutState: null,
    layoutPlan: null,
    layoutOptimalCount: 0,
    layoutSel: null,
    // Aucune ombre voisine tracée (fonction d'étude, pas de rendu client).
    shadeObstructions: [],
    shadeFactors: null,
    shadeAnnualFactor: 1,
    // Soleil : les valeurs par défaut du builder (midi, solstice d'hiver).
    sunHour: DEFAULT_SUN_HOUR,
    sunDay: WINTER_SOLSTICE_DAY,
    centroidLat: plan.center[1],
  } as unknown as Ctx;

  // — Carte : MÊME imagerie que les pages mon-toit et que l'ERP
  //   (`buildSatelliteStyle` de lib/roofConfig.ts : tuiles Mapbox Satellite
  //   /Maxar si un token public est fourni, sinon style hybride MapTiler).
  const viewportPx = Math.max(240, Math.min(el.clientWidth || 0, el.clientHeight || 0) || el.clientWidth || 640);
  const zoom = zoomForSpanM(plan.spanM, viewportPx, plan.center[1]);
  let map: maplibregl.Map;
  try {
    map = new maplibregl.Map({
      container: el,
      style: buildSatelliteStyle({ maptilerKey, mapboxToken }) as maplibregl.StyleSpecification | string,
      center: plan.center as [number, number],
      zoom,
      // Vue 3D d'emblée (le client « reçoit l'image finale »), inclinaison de la
      // vue 3D du builder. Il reste libre de revenir à plat (pitch 0).
      pitch: Math.max(0, Math.min(75, opts.pitchDeg ?? PITCH_VIEW)),
      bearing: opts.bearingDeg ?? 0,
      maxPitch: 75,
      attributionControl: { compact: true },
      fadeDuration: reducedMotion ? 0 : 300,
      // Aucun `maxBounds`, aucun `minZoom` : dézoom libre jusqu'à la ville, le
      // pays, le monde — la carte complète, comme dans l'ERP.
      cooperativeGestures: opts.cooperativeGestures !== false,
    });
  } catch {
    return null;
  }

  // Contrôles CAMÉRA seulement (zoom + boussole/inclinaison). Pas de
  // géolocalisation : la position du visiteur n'a rien à faire ici.
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

  let hasRenderedOnce = false;
  // Chien de garde : une carte qui ne charge JAMAIS (réseau muet, style
  // injoignable) ne doit pas laisser le visiteur devant un voile éternel.
  let loadTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
    loadTimer = null;
    if (!hasRenderedOnce) opts.onMapError?.();
  }, opts.loadTimeoutMs ?? 15_000);
  const clearLoadTimer = () => {
    if (loadTimer !== null) {
      clearTimeout(loadTimer);
      loadTimer = null;
    }
  };
  map.once('load', () => {
    hasRenderedOnce = true;
    clearLoadTimer();
  });
  const onError = (e: unknown) => {
    const msg = (e as { error?: { message?: string } } | undefined)?.error?.message ?? e;
    console.warn('[visionneuse-toit] erreur carte :', msg);
    if (hasRenderedOnce) opts.onMapError?.();
  };
  map.on('error', onError);

  // — Scène 3D : le module de l'ERP, en lecture seule —
  const scene3d = createScene3d(ctx, { map, lowEnd, shadowSize, readOnly: true });

  map.on('load', () => {
    // `addLayer` déclenche `onAdd` (renderer + scène + soleil) : renderScene ne
    // peut être appelé qu'APRÈS.
    map.addLayer(scene3d.customLayer);
    // Le conteneur peut n'avoir sa taille finale qu'à l'ouverture du bloc 3D
    // (voile masqué, section dépliée) — même précaution qu'à l'hydratation ERP.
    map.resize();
    // Pan ACTIF : bâtiment + dalle (photo satellite drapée) + panneaux + obstacles
    // + soleil. Les AUTRES pans sont ajoutés par `appendOtherZones` DEPUIS
    // renderScene (il lit `ctx.areas`), avec les mêmes matériaux (readOnly).
    // `maxCount` = tous les panneaux posés ; aucun `occupiedSet` : la géométrie
    // publiée EST déjà la liste des cellules réellement occupées.
    scene3d.renderScene(
      activePlan.pack,
      activePlan.grid,
      activePlan.tiltDeg,
      activePlan.family,
      activePlan.grid.panels.length,
      activePlan.flush,
    );
    opts.onReady?.();
  });

  let destroyed = false;
  return {
    panelCount: plan.totalPanels,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      clearLoadTimer();
      map.off('error', onError);
      try {
        // `remove()` retire les couches → `onRemove` de scene3d libère meshes,
        // matériaux, textures partagées et le WebGLRenderer (garde W70).
        map.remove();
      } catch {
        /* carte déjà démontée : rien à libérer */
      }
    },
  };
}

/** Alias court (`boot(el, layout, opts)`) — l'API minimale demandée. */
export const boot = bootViewerFull;

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
import * as maplibregl from 'maplibre-gl';
import maplibreCssUrl from 'maplibre-gl/dist/maplibre-gl.css?url';
import { type RoofLayout } from '../../lib/proposition';
import { buildSatelliteStyle } from '../../lib/roofConfig';
import { PITCH_VIEW } from './constants';
import { type Ctx } from './context';
import { createScene3d } from './scene3d';
import { type CouleurDe } from './canalTeinte';
import { type EnvironmentObject } from './environment';
import { type InitOptions } from './types';
import { buildViewerFullPlan, viewerAreaRecords, zoomForSpanM } from './viewerFullModel';

/** Jour de l'année du solstice d'hiver — MÊME soleil par défaut que le builder
 *  (midi au solstice : l'élévation de design de l'espacement anti-ombrage, où
 *  les rangées se dégagent visiblement). Aucun réglage n'est offert au client
 *  hors de la visionneuse au soleil des liens de confiance (`viewerSoleil.ts`). */
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
   * Lot 8 — avec `onFail`, ces pannes démontent la carte et passent par `onFail` (la page monte alors la
   * visionneuse simplifiée ou laisse voir sa photo) : `onMapError` ne sert plus qu'aux appelants sans `onFail`.
   */
  onMapError?: () => void;
  /** Lot 8 — la SCÈNE a jeté (premier rendu ou pas de soleil) : la visionneuse s'est déjà démontée et
   *  `onReady` n'est pas (ou plus) appelé ; l'appelant monte son repli. Appelé une fois au plus. */
  onFail?: (raison: unknown) => void;
  /** Délai au-delà duquel une carte qui n'a pas chargé est déclarée en panne
   *  (ms, défaut 15 000 — même ordre que le fetch de config du parcours). */
  loadTimeoutMs?: number;
  /** LOT 6 (D-ACAL-135) — instant d'ouverture (jour 1-366, heure solaire). Absent = midi au solstice d'hiver. */
  instant?: { jour: number; heure: number };
  /** LOT 6 (D-ACAL-137) — objets voisins à hauteur saisie (géométrie seule). Absent = aucun, comme avant. */
  environnement?: EnvironmentObject[];
  /** LOT 6 (D-ACAL-136) — index des pans que la visionneuse au soleil TEINTERA. Le pan actif en fait partie ⇒ la scène
   *  prend le verre et l'œil de l'atelier (`teinteAccesVisible`, sinon la teinte reste invisible). Absent = inchangé. */
  indexTeintes?: readonly number[];
  /** Lot 8 (D-ACAL-132) — lien de CONFIANCE (`visionneuse_soleil` servie) : l'habit « Montrer au client » de l'ERP
   *  (`types.ts::InitOptions.presentationClient`). Absent = la visionneuse d'aujourd'hui (liens standard). */
  presentationClient?: boolean;
}

export interface ViewerFullHandle {
  /** Libère TOUT (couche 3D → onRemove de scene3d : meshes, textures, renderer ; puis la carte). */
  destroy: () => void;
  /** Nombre de panneaux RÉELLEMENT dessinés (somme des pans) — pour un test/diagnostic. */
  panelCount: number;
  /** LOT 6 — poignée ADDITIVE de la visionneuse au soleil (`viewerSoleil.ts`), inutilisée ailleurs. */
  carte: maplibregl.Map;
  zoomInitial: number;
  /** Index (dans `roof_layout.zones`) du pan actif : le seul que la scène teinte. */
  indexActif: number;
  /** Écrit le soleil (jour, heure) et repose le soleil seul (lumière, ombres, ciel) : aucun maillage reconstruit. */
  poserInstant: (jour: number, heure: number) => void;
  /** `scene3d.setSolarAccessHeatmap` (pan actif), reposée après chaque rendu ; `null` l'éteint. */
  teinter: (colorFor: CouleurDe) => void;
}

/** Lot 8 (B0) — délai laissé au navigateur pour restaurer un contexte WebGL perdu avant de déclarer la scène morte. */
export const DELAI_RESTAURATION_GL_MS = 5_000;

/**
 * Lot 8 (B0) — une erreur MapLibre rend-elle la scène INUTILISABLE ? Non pour ce qui touche une source ou une
 * tuile (`sourceId`, `tile` : une image satellite manquante, un 429 du fournisseur) ni pour une réponse HTTP
 * (`error.status` : glyphe, sprite, tuile) — la carte et la 3D continuent. Oui pour le reste (style qui ne se
 * charge plus, panne interne sans source).
 */
export function erreurCarteFatale(e: unknown): boolean {
  if (!e || typeof e !== 'object') return true;
  const ev = e as { sourceId?: unknown; tile?: unknown; error?: { status?: unknown } | null };
  if (ev.sourceId != null || ev.tile != null) return false;
  return typeof ev.error?.status !== 'number';
}

/** Lot 8 — l'erreur dit-elle que le STYLE de la carte est refusé (403, 404 : même adresse que le style demandé) ?
 *  Une tuile ou une source n'est jamais un refus de style. */
export function erreurDeStyle(e: unknown, styleUrl: string | null): boolean {
  if (!styleUrl || !e || typeof e !== 'object') return false;
  const ev = e as { sourceId?: unknown; tile?: unknown; error?: { url?: unknown } | null };
  if (ev.sourceId != null || ev.tile != null) return false;
  const url = ev.error?.url;
  return typeof url === 'string' && url.split('?')[0] === styleUrl.split('?')[0];
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
  // LOT 6 (P1) — verre et œil de l'atelier SEULEMENT quand le pan actif sera teinté (ACAL1984) ; sinon aucune clé.
  const teinteAccesVisible = opts.indexTeintes?.includes(plan.activeIndex) === true;
  const toolOpts: InitOptions = { maptilerKey, mapboxToken, reducedMotion, ...(teinteAccesVisible ? { teinteAccesVisible } : {}) };
  if (opts.presentationClient === true) toolOpts.presentationClient = true; // lot 8 — lien de confiance seulement
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
    sunHour: opts.instant?.heure ?? DEFAULT_SUN_HOUR,
    sunDay: opts.instant?.jour ?? WINTER_SOLSTICE_DAY,
    ...(opts.environnement?.length ? { environment: opts.environnement } : {}),
    centroidLat: plan.center[1],
    // ACAL262 — surfaces de pose publiées (tables moteur) : scene3d les dessine.
    surfacesPose: plan.surfacesPose,
    // Lot 8 — `buildZoneMeshes` lit `ctx.dom.areasWindowEl` (hôte du contrôle de numérotation, CALX111) à CHAQUE
    // rendu : sans `dom`, le premier rendu jetait (TypeError) depuis le 21/09 — scène à moitié bâtie, soleil
    // figé. Aucun hôte ici : `monterControleNumerotation(undefined)` ne monte rien, la page reste sans contrôle.
    dom: {},
  } as unknown as Ctx;

  // — Carte : MÊME imagerie que les pages mon-toit et que l'ERP
  //   (`buildSatelliteStyle` de lib/roofConfig.ts : tuiles Mapbox Satellite
  //   /Maxar si un token public est fourni, sinon style hybride MapTiler).
  const viewportPx = Math.max(240, Math.min(el.clientWidth || 0, el.clientHeight || 0) || el.clientWidth || 640);
  const zoom = zoomForSpanM(plan.spanM, viewportPx, plan.center[1]);
  const style = buildSatelliteStyle({ maptilerKey, mapboxToken });
  let map: maplibregl.Map;
  try {
    map = new maplibregl.Map({
      container: el,
      style: style as maplibregl.StyleSpecification | string,
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
  // Lot 8 — seulement si la carte n'a fait AUCUN progrès (ni style ni source reçus) : une carte lente dont le style
  // est arrivé (tuiles satellite sur un téléphone en 3G) continue de charger jusqu'à `load`, sans autre délai,
  // comme avant — la visionneuse pleine et la barre au soleil arrivent alors en retard, jamais retirées.
  let progres = false;
  const marquerProgres = () => { progres = true; };
  map.once('styledata', marquerProgres);
  map.once('sourcedata', marquerProgres);
  let loadTimer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
    loadTimer = null;
    if (!hasRenderedOnce && !progres) panneCarte('carte jamais chargée');
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
    // Lot 8 (B0) — une tuile refusée (429, réseau) laisse la scène utilisable : seule une panne qui la rend
    // inutilisable replie la page (et cache la barre au soleil). Avant le premier chargement, un style refusé
    // (403, 404) ou une panne interne replie TOUT DE SUITE, sans attendre le chien de garde.
    if (hasRenderedOnce ? erreurCarteFatale(e) : erreurCarteFatale(e) || erreurDeStyle(e, typeof style === 'string' ? style : null)) panneCarte(e);
  };
  map.on('error', onError);
  // Contexte WebGL perdu : MapLibre détruit son style, couche 3D comprise, et à la restauration ne remet qu'un style
  // SANS elle (une couche personnalisée ne se restaure pas seule ; le W89 de scene3d ne refait que le renderer Three).
  // Jamais restauré = scène morte → repli. Restauré = style revenu, couche reposée, scène rejouée (instant et teinte
  // courants) ; si la couche ne revient pas, repli (visionneuse simplifiée ou photo, barre débranchée).
  let perteGl: ReturnType<typeof setTimeout> | null = null;
  const surPerteGl = () => {
    if (perteGl === null) perteGl = setTimeout(() => panneCarte('contexte WebGL jamais restauré'), DELAI_RESTAURATION_GL_MS);
  };
  const annulerPerteGl = () => {
    if (perteGl !== null) clearTimeout(perteGl);
    perteGl = null;
  };
  const surRestaurationGl = () => {
    annulerPerteGl();
    if (destroyed || !charge) return; // pas encore chargée : `load` posera la couche
    const garde = setTimeout(() => panneCarte('style non revenu après la restauration du contexte'), DELAI_RESTAURATION_GL_MS);
    const reprendre = () => {
      clearTimeout(garde);
      if (destroyed) return;
      try {
        const id = scene3d.customLayer.id;
        if (!map.getLayer(id)) map.addLayer(scene3d.customLayer);
        if (!map.getLayer(id)) throw new Error('couche 3D non reposée après la restauration du contexte');
        rendre();
        map.triggerRepaint();
      } catch (e) {
        echouer(e);
      }
    };
    if (map.isStyleLoaded()) reprendre();
    else map.once('style.load', reprendre);
  };
  map.on('webglcontextlost', surPerteGl);
  map.on('webglcontextrestored', surRestaurationGl);

  // — Scène 3D : le module de l'ERP, en lecture seule —
  const scene3d = createScene3d(ctx, { map, lowEnd, shadowSize, readOnly: true });

  let charge = false;
  let teinte: CouleurDe = null;
  const rendre = () => {
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
    if (teinte) scene3d.setSolarAccessHeatmap(teinte);
  };

  let destroyed = false;
  // Lot 8 — une scène qui jette ne reste JAMAIS à moitié bâtie derrière des commandes vivantes : on la
  // démonte, on le dit une fois dans la console, et l'appelant replie (visionneuse simplifiée ou photo).
  const echouer = (raison: unknown) => {
    if (destroyed) return;
    console.warn('[visionneuse-toit] rendu 3D impossible, repli :', raison);
    poignee.destroy();
    opts.onFail?.(raison);
  };
  // Lot 8 — carte en panne (style refusé, jamais chargée, panne fatale, contexte perdu) : avec `onFail`, la carte
  // est démontée (plus de boîte sombre devant la photo) et l'appelant replie ; sans, l'ancien `onMapError`.
  function panneCarte(raison: unknown): void {
    if (destroyed) return;
    if (opts.onFail) echouer(raison);
    else opts.onMapError?.();
  }
  const essayer = (geste: () => void) => {
    if (!charge || destroyed) return;
    try {
      geste();
    } catch (e) {
      echouer(e);
    }
  };

  map.on('load', () => {
    if (destroyed) return; // démontée avant son chargement (panne de style, délai) : plus rien à rendre
    try {
      // `addLayer` déclenche `onAdd` (renderer + scène + soleil) : renderScene ne
      // peut être appelé qu'APRÈS.
      map.addLayer(scene3d.customLayer);
      // Le conteneur peut n'avoir sa taille finale qu'à l'ouverture du bloc 3D
      // (voile masqué, section dépliée) — même précaution qu'à l'hydratation ERP.
      map.resize();
      rendre();
    } catch (e) {
      echouer(e);
      return;
    }
    charge = true;
    opts.onReady?.();
  });

  const poignee: ViewerFullHandle = {
    panelCount: plan.totalPanels,
    carte: map,
    zoomInitial: zoom,
    indexActif: plan.activeIndex,
    poserInstant(jour, heure) {
      ctx.sunDay = jour;
      ctx.sunHour = heure;
      // Lot 8 (B3) — le soleil SEUL (lumière, ombres, ciel) : aucun maillage reconstruit, la teinte reste posée.
      essayer(() => scene3d.poserSoleil());
    },
    teinter(colorFor) {
      teinte = colorFor;
      essayer(() => scene3d.setSolarAccessHeatmap(colorFor));
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      clearLoadTimer();
      annulerPerteGl();
      map.off('error', onError);
      map.off('webglcontextlost', surPerteGl);
      map.off('webglcontextrestored', surRestaurationGl);
      try {
        // `remove()` retire les couches → `onRemove` de scene3d libère meshes,
        // matériaux, textures partagées et le WebGLRenderer (garde W70).
        map.remove();
      } catch {
        /* carte déjà démontée : rien à libérer */
      }
    },
  };
  return poignee;
}

/** Lot 8 — ce que la page branche autour de la visionneuse pleine. */
export interface SuiteVisionneuse {
  /** Barre au soleil (liens de confiance) : cachée tant que la scène n'a pas VRAIMENT rendu, recachée au repli. */
  barre?: HTMLElement | null;
  /** Branche la barre sur la poignée (`viewerSoleil.attacherSoleil`), appelé SEULEMENT après `onReady` ; renvoie le débrancheur. */
  brancherSoleil?: (poignee: ViewerFullHandle) => Promise<() => void>;
  /** La scène a échoué après son démarrage : la page monte son repli, comme sans WebGL ni clé d'imagerie. */
  replier: (raison: unknown) => void;
  /** Le cadre de la scène et l'aide des gestes : habillés pour la CARTE une fois la scène rendue, rendus tels qu'avant
   *  au repli (la visionneuse simplifiée a ses propres gestes : un doigt tourne, il ne fait pas défiler la page). */
  scene?: HTMLElement | null;
  aide?: HTMLElement | null;
}

/** Les gestes de la CARTE (≠ ceux de la visionneuse simplifiée), dans les trois langues de la page. */
const AIDE_GESTES_CARTE = {
  fr: 'Deux doigts pour déplacer et zoomer · clic droit ou Ctrl + glisser pour tourner',
  en: 'Two fingers to pan and zoom · right-click or Ctrl + drag to rotate',
  ar: 'إصبعان للتحريك والتكبير · زر أيمن أو Ctrl + سحب للتدوير',
} as const;
const CLASSES_CARTE = ['roof3d-stage--sky', 'roof3d-stage--map'] as const;

const LANGUES_AIDE = ['fr', 'en', 'ar'] as const;
type TextesAide = { fr?: string; en?: string; ar?: string };

/** Les trois portées de langue que la page pose dans un nœud `data-i18n` (`prepareI18n` : fr, en, ar, dans cet ordre ;
 *  son sélecteur de langue ne fait ensuite que les montrer ou les cacher). `null` si le nœud n'a pas été préparé. */
function porteesDeLangue(el: HTMLElement): HTMLElement[] | null {
  const k = [...el.children] as HTMLElement[];
  return el.childNodes.length === 3 && k.length === 3 && k.every((c) => c.tagName === 'SPAN') ? k : null;
}

/** La langue affichée par la page (attribut `lang` du document, posé par son sélecteur). */
function langueDeLaPage(): 'fr' | 'en' | 'ar' {
  const l = typeof document !== 'undefined' ? document.documentElement.lang : '';
  return l === 'en' || l === 'ar' ? l : 'fr';
}

/** Écrit l'aide : data-i18n, puis les trois portées EN PLACE quand la page les a posées (le sélecteur de langue continue
 *  de les basculer), sinon `texteNu` ou le texte de la langue de la page. */
function ecrireAide(el: HTMLElement, textes: TextesAide, portees: readonly string[] | null, texteNu: string | null): void {
  for (const l of LANGUES_AIDE) {
    if (textes[l] === undefined) delete el.dataset[l];
    else el.dataset[l] = textes[l];
  }
  const cibles = porteesDeLangue(el);
  if (cibles) cibles.forEach((c, i) => { c.textContent = portees?.[i] ?? textes[LANGUES_AIDE[i]] ?? ''; });
  else el.textContent = texteNu ?? textes[langueDeLaPage()] ?? textes.fr ?? '';
}

/** Habille la scène pour la carte (classes du cadre ; aide des gestes CARTE dans les trois langues, qui suit la langue
 *  de la page au chargement comme après une bascule) ; renvoie la fonction qui remet le cadre et l'aide comme avant. */
export function habillerPourCarte(scene: HTMLElement | null | undefined, aide: HTMLElement | null | undefined): () => void {
  const avant = aide
    ? { hidden: aide.hidden, textes: { fr: aide.dataset.fr, en: aide.dataset.en, ar: aide.dataset.ar }, portees: porteesDeLangue(aide)?.map((p) => p.textContent ?? '') ?? null, texte: aide.textContent }
    : null;
  const avaitClasse = CLASSES_CARTE.map((c) => scene?.classList.contains(c) === true);
  if (aide) {
    aide.hidden = false;
    ecrireAide(aide, AIDE_GESTES_CARTE, null, null);
  }
  scene?.classList.add(...CLASSES_CARTE);
  return () => {
    CLASSES_CARTE.forEach((c, i) => { if (!avaitClasse[i]) scene?.classList.remove(c); });
    if (!aide || !avant) return;
    aide.hidden = avant.hidden;
    ecrireAide(aide, avant.textes, avant.portees, avant.texte);
  };
}

/**
 * Lot 8 — la visionneuse pleine ET sa barre au soleil, sans commande morte : la barre n'est branchée (donc
 * montrée, `attacherSoleil` la démasque) qu'une fois la scène rendue ; une scène qui jette la débranche, la
 * cache et passe la main au repli. `null` = refus propre de `bootViewerFull` (l'appelant replie tout de suite).
 */
export function monterVisionneusePleine(
  el: HTMLElement | null,
  layout: RoofLayout | null | undefined,
  opts: ViewerFullOptions,
  suite: SuiteVisionneuse,
): { dispose: () => void } | null {
  let fini = false;
  let debrancher: (() => void) | null = null;
  let poignee: ViewerFullHandle | null = null;
  let deshabiller: (() => void) | null = null;
  const cacherBarre = () => {
    if (suite.barre) suite.barre.hidden = true;
  };
  const arreterSoleil = () => {
    debrancher?.();
    debrancher = null;
  };
  poignee = bootViewerFull(el, layout, {
    ...opts,
    onReady: () => {
      opts.onReady?.();
      if (!fini && (suite.scene || suite.aide)) deshabiller = habillerPourCarte(suite.scene, suite.aide);
      const p = poignee;
      if (!p || fini || !suite.brancherSoleil) return;
      suite.brancherSoleil(p).then((d) => (fini ? d() : (debrancher = d)), cacherBarre);
    },
    onFail: (raison) => {
      if (fini) return;
      fini = true;
      arreterSoleil();
      cacherBarre();
      deshabiller?.(); // le repli retrouve le cadre et l'aide de la visionneuse simplifiée
      deshabiller = null;
      opts.onFail?.(raison);
      suite.replier(raison);
    },
  });
  if (!poignee) return null;
  const monte = poignee;
  return {
    dispose: () => {
      fini = true;
      arreterSoleil();
      monte.destroy();
    },
  };
}

/** Alias court (`boot(el, layout, opts)`) — l'API minimale demandée. */
export const boot = bootViewerFull;

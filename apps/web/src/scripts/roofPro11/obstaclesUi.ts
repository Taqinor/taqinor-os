/**
 * Interface des OBSTACLES (zones d'exclusion) du builder pro-11 — sélection,
 * glissé-dessin, glissé-déplacement (avec mise à jour 3D en direct du mesh), et
 * édition (saisie exacte longueur/largeur + boutons + / − + suppression). Extrait
 * de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * NB : ne PAS confondre avec la lib PURE `src/lib/obstacles.ts` (géométrie des
 * rectangles d'obstruction) — ce module n'est que l'UI/3D qui la pilote.
 *
 * Le DISPATCHER d'événements carte (mousedown/move/up, touch, click, dblclick)
 * reste dans l'entrée car il est PARTAGÉ avec le tracé ; il route vers les
 * fonctions exportées ici (beginDraw/moveDraw/endDraw/tryBeginMove/doMove/endMove).
 */
import maplibregl from 'maplibre-gl';
import {
  obstacleFromDrag,
  defaultObstacle,
  scaledObstacle,
  resizedObstacle,
  withHeight,
  withProvenance,
  duplicatedObstacle,
  gridPositions,
  isNonEngageable,
  OBSTACLE_STEP_FACTOR,
  type Obstacle,
  type ObstacleType,
  type ObstacleProvenance,
} from '../../lib/obstacles';
import { type LngLat } from '../../lib/roof';
import { OBSTACLE_TAP_PX, VERTEX_GRAB_PX, DEG2RAD, DEG2M } from './constants';
import { insertionSurContour, supprimerSommet, metresParPixel } from './snap';
import { $, esc } from './dom';
import { type Ctx } from './context';
import {
  OBSTACLE_TYPES,
  aireObstacleM2,
  anneauObstacle,
  clearanceForType,
  degagementObstacle,
  formeObstacle,
  obstaclePolygone,
  type ObstacleEtendu,
} from './types';
import {
  newEnvironmentObject,
  environmentNeedsFootprint,
  deplacerEnvironment,
  withEnvHeight,
  withCrownDiameter,
  withFootprintDims,
  withEvergreen,
  type EnvironmentObject,
  type EnvironmentKind,
} from './environment';
import {
  EXCLUSION_NATURES,
  exclusionColor,
  exclusionZoneFromDrag,
  exclusionZoneRing,
  withZoneNature,
  withZoneSetback,
  withZoneHeight,
  withZoneLabel,
  type ExclusionZone,
  type ExclusionNature,
} from './zones';

/** CAL72 — provenances proposées (vocabulaire `core.calepinage.types.Provenance`), avec
 *  libellé FR + note « bloque le compte » pour PLAN/DEVINE. */
const OBSTACLE_PROVENANCES: { id: ObstacleProvenance; label: string }[] = [
  { id: 'RELEVE', label: 'Relevé sur place' },
  { id: 'RELEVE_DOUTEUX', label: 'Relevé douteux' },
  { id: 'DECLARE_CLIENT', label: 'Déclaré par le client' },
  { id: 'PLAN', label: 'Depuis un plan (bloque le compte)' },
  { id: 'DEVINE', label: 'Deviné (bloque le compte)' },
  { id: 'ECARTE', label: 'Écarté' },
];

// ————————————————————————————————————————————————————————————————————————
// CALX91 — GESTES SUR LES SOMMETS D'UN CONTOUR FERMÉ
//
// Le glissé d'un sommet existant était le SEUL geste possible après fermeture. On ajoute
// deux gestes (parité Aurora SmartRoof) : double-clic sur une arête = insertion d'un sommet
// au projeté orthogonal, Alt+clic sur un sommet = suppression. La décision « quel geste »
// est isolée ici, PURE, pour être prouvée sans carte ni DOM.
// ————————————————————————————————————————————————————————————————————————

/** Geste déclenché par un appui sur un sommet du tracé. */
export type GesteSommet = 'deplacer' | 'supprimer' | 'aucun';

/**
 * CALX91 — quel geste un appui sur un sommet déclenche. Alt maintenue = SUPPRESSION, jamais
 * un glissé (sinon les deux partent ensemble et le contour part à la dérive). Hors contour
 * fermé, ou en mode obstacle / disposition, aucun geste sommet n'existe : gardes identiques
 * à celles du glissé de sommet W92, donc le comportement d'aujourd'hui est inchangé tant
 * qu'Alt n'est pas maintenue.
 */
export function gesteSommet(etat: {
  sommet: number | null;
  altEnfoncee: boolean;
  ferme: boolean;
  modeObstacle: boolean;
  modeDisposition: boolean;
}): GesteSommet {
  if (!etat.ferme || etat.modeObstacle || etat.modeDisposition) return 'aucun';
  if (etat.sommet == null) return 'aucun';
  return etat.altEnfoncee ? 'supprimer' : 'deplacer';
}

// ————————————————————————————————————————————————————————————————————————
// CALX105 — POSER UN ARBRE OU UN BÂTIMENT VOISIN AU CLIC, LE DÉPLACER AU GLISSÉ
//
// Un objet d'environnement atterrissait TOUJOURS au même endroit — 10 m au sud du centroïde
// — et ne se repositionnait ensuite que par saisie numérique ; le message le disait mot pour
// mot (« posé au sud du toit »). Parité PV*SOL : les objets d'ombrage se placent à l'échelle
// réelle sur la carte. Le clic donne le CENTRE, le glissé du marqueur le déplace.
//
// LES DIMENSIONS RESTENT SAISIES : poser ou déplacer un objet ne lui invente ni hauteur ni
// emprise — un objet sans hauteur saisie ne porte toujours AUCUNE ombre.
// ————————————————————————————————————————————————————————————————————————

/** Geste déclenché par un appui sur la carte, côté objets d'environnement. */
export type GesteEnvironnement = 'poser' | 'deplacer' | 'aucun';

/**
 * CALX105 — quel geste d'environnement un appui déclenche. Un mode de pose ARMÉ l'emporte
 * (le clic suivant pose l'objet) ; sinon un marqueur sous le doigt se glisse. Les modes
 * obstacle et disposition gardent la main sur le geste : rien ne change pour eux.
 */
export function gesteEnvironnement(etat: {
  poseArmee: EnvironmentKind | null;
  marqueur: string | null;
  modeObstacle: boolean;
  modeDisposition: boolean;
}): GesteEnvironnement {
  if (etat.modeObstacle || etat.modeDisposition) return 'aucun';
  if (etat.poseArmee) return 'poser';
  return etat.marqueur != null ? 'deplacer' : 'aucun';
}

/** Glissé d'un marqueur d'environnement en cours (mêmes champs que `ctx.moveObs`). */
export interface GlisseEnvironnement {
  id: string;
  startLng: number;
  startLat: number;
  centerLng: number;
  centerLat: number;
  moved: boolean;
}

/** CALX105 — ouvre un glissé sur l'objet `o`, depuis le point saisi. */
export function debutGlisseEnvironnement(o: EnvironmentObject, lngLat: LngLat): GlisseEnvironnement {
  return {
    id: o.id,
    startLng: lngLat[0],
    startLat: lngLat[1],
    centerLng: o.centerLng,
    centerLat: o.centerLat,
    moved: false,
  };
}

/**
 * CALX105 — avance un glissé : rend le nouveau centre (delta lng/lat, qui annule le
 * parallaxe de la vue inclinée — même règle que le glissé d'obstacle) et dit s'il faut
 * pousser un pas d'historique. CAL100 : UNE SEULE photo pour tout le glissé, juste avant le
 * PREMIER mouvement réel — un simple tap de sélection ne laisse donc rien à annuler.
 */
export function avancerGlisseEnvironnement(
  glisse: GlisseEnvironnement,
  lngLat: LngLat,
): { centre: LngLat; pousserHistorique: boolean } {
  const pousserHistorique = !glisse.moved;
  glisse.moved = true;
  return {
    centre: [
      glisse.centerLng + (lngLat[0] - glisse.startLng),
      glisse.centerLat + (lngLat[1] - glisse.startLat),
    ],
    pousserHistorique,
  };
}

/** Dépendances injectées (carte + recalcul complet + bandeau de statut). */
export interface ObstaclesUiDeps {
  /** La carte MapLibre (sources GeoJSON + requêtes de features + pan/curseur). */
  map: maplibregl.Map;
  /** Recalcul complet (re-pavage + production) après modification d'obstacle. */
  recalc: () => void;
  /** Affiche un message dans le bandeau de statut. */
  setStatus: (msg: string) => void;
  /** W92 — re-dessine la ligne + les pastilles de sommets après un glissé/undo. */
  redrawTrace: () => void;
  /** CAL66/CAL67 — recalcule l'ombrage VIVANT (matrice de dérate + facteur annuel +
   *  carte d'accès solaire) après un changement de hauteur d'obstacle ou d'objet
   *  d'environnement : ces deux-là ombrent désormais réellement. Optionnel — absent,
   *  seul le re-pavage (`recalc`) a lieu, comportement d'avant CAL66. */
  recomputeShading?: () => void;
}

export interface ObstaclesUi {
  redrawObstacles: () => void;
  /** CAL69 — re-dessine le calque des zones d'exclusion. */
  redrawExclusionZones: () => void;
  /** CAL69 — arme le tracé d'une zone de cette nature (le glissé suivant la crée). */
  beginZone: (nature: ExclusionNature) => void;
  setPreviewRect: (a: LngLat, b: LngLat) => void;
  clearPreview: () => void;
  syncObsEdit: () => void;
  selectObstacle: (id: string | null) => void;
  updateSelected: (transform: (o: Obstacle) => Obstacle) => void;
  deleteSelected: () => void;
  addObstacle: (o: Obstacle) => void;
  obstacleAtPoint: (pt: maplibregl.Point) => string | null;
  setObstacleMode: (on: boolean) => void;
  beginDraw: (lngLat: LngLat, point: maplibregl.Point) => void;
  moveDraw: (lngLat: LngLat) => void;
  endDraw: (lngLat: LngLat, point: maplibregl.Point) => void;
  tryBeginMove: (lngLat: LngLat, point: maplibregl.Point) => boolean;
  doMove: (lngLat: LngLat) => void;
  endMove: () => void;
  // W92 — glissé d'un SOMMET du tracé (généralisation du glissé d'obstacle).
  vertexAtPoint: (pt: maplibregl.Point) => number | null;
  tryBeginVertexMove: (lngLat: LngLat, point: maplibregl.Point) => boolean;
  doVertexMove: (lngLat: LngLat) => void;
  endVertexMove: () => void;
  // CALX105 — pose au clic + glissé d'un marqueur d'objet d'environnement. Le module câble
  // lui-même la carte ; ces méthodes restent exposées pour l'hôte qui préfère router.
  /** Marqueur d'environnement touché au point écran, ou null. */
  envAtPoint: (pt: maplibregl.Point) => string | null;
  /** Arme la pose d'un arbre/bâtiment (le clic carte suivant donne le centre) ; null désarme. */
  armerPoseEnvironment: (kind: EnvironmentKind | null) => void;
  /** Pose l'objet au point donné (aucune dimension n'est déduite). */
  poserEnvironment: (kind: EnvironmentKind, centre: LngLat) => void;
  tryBeginEnvMove: (lngLat: LngLat, point: maplibregl.Point) => boolean;
  doEnvMove: (lngLat: LngLat) => void;
  endEnvMove: () => void;
  /** Re-dessine les marqueurs d'environnement. */
  redrawEnvironment: () => void;
  // CALX103 — mode de tracé « à la volée » (clics successifs, double-clic pour fermer).
  /** Arme (ou désarme, `null`) un tracé d'obstacle polygonal. */
  armerTrace: (mode: ModeTrace | null) => void;
  /** Le mode de tracé armé, ou null. */
  modeTraceArme: () => ModeTrace | null;
}

/** CALX103 — les tracés « à la volée » que l'atelier sait armer. */
export type ModeTrace = 'polygone';

export function createObstaclesUi(ctx: Ctx, deps: ObstaclesUiDeps): ObstaclesUi {
  const { map, recalc, setStatus, redrawTrace } = deps;

  /** CAL66/CAL67 — re-pavage PUIS recalcul de l'ombrage vivant : une hauteur d'obstacle
   *  ou un objet d'environnement change à la fois la surface utile ET les ombres. */
  function recalcWithShading() {
    deps.recalc();
    deps.recomputeShading?.();
  }

  // FeatureCollection vide réutilisable (efface une source) — identique à l'entrée.
  const empty = { type: 'FeatureCollection', features: [] } as const;
  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  /** Décimal à 1 chiffre, à la française (identique à l'entrée). */
  const fmt1 = (n: number): string =>
    n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  /** CALX103/CALX104 — les cotes AFFICHÉES suivent la forme réelle : le rayon SAISI d'un
   *  disque, le nombre de sommets et l'aire d'un polygone, et le rectangle sinon. La boîte
   *  `lengthM × widthM` reste rappelée pour les formes qui ne sont pas des rectangles —
   *  c'est le repli que tout lecteur du document retrouve. */
  const dimsLabel = (obs: Obstacle) => {
    const o = obs as ObstacleEtendu;
    const boite = `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;
    const forme = formeObstacle(o);
    if (forme === 'cercle' && o.rayonM != null) {
      return `disque r = ${fmt1(o.rayonM)} m (boîte ${boite})`;
    }
    if (forme === 'polygone' && Array.isArray(o.contour)) {
      return `polygone ${o.contour.length} sommets · ${fmt1(aireObstacleM2(o))} m² (boîte ${boite})`;
    }
    return boite;
  };

  // — DOM des obstacles —
  const obstacleBtn = $<HTMLButtonElement>('rp9-obstacle');
  const obstacleClearBtn = $<HTMLButtonElement>('rp9-obstacle-clear');
  const obsEditPanel = $('rp9-obs-edit');
  const obsLengthEl = $<HTMLInputElement>('rp9-obs-length');
  const obsWidthEl = $<HTMLInputElement>('rp9-obs-width');
  const obsDimsEl = $('rp9-obs-dims');
  const obsDeleteBtn = $<HTMLButtonElement>('rp9-obs-delete');
  const obsPlusBtn = $<HTMLButtonElement>('rp9-obs-plus');
  const obsMinusBtn = $<HTMLButtonElement>('rp9-obs-minus');
  // CAL66 — hauteur saisie.
  const obsHeightEl = $<HTMLInputElement>('rp9-obs-height');
  // CAL72 — provenance + bandeau de non-engageabilité.
  const obsEngageEl = $('rp9-obs-engage');
  // CAL73 — duplication + pose en trame.
  const obsDuplicateBtn = $<HTMLButtonElement>('rp9-obs-duplicate');
  const obsGridSpacingEl = $<HTMLInputElement>('rp9-obs-grid-spacing');
  const obsGridColsEl = $<HTMLInputElement>('rp9-obs-grid-cols');
  const obsGridRowsEl = $<HTMLInputElement>('rp9-obs-grid-rows');
  const obsGridPlaceBtn = $<HTMLButtonElement>('rp9-obs-grid-place');

  // PV61 — SÉLECTEUR « type d'obstacle ». Le type ne change pas la géométrie du
  // rectangle : il fixe le DÉGAGEMENT laissé autour (cheminée 0,50 m ↔ antenne 0,30 m).
  // Le sélecteur est créé ICI s'il n'existe pas déjà dans la page (le panneau d'édition
  // d'obstacle est partagé par plusieurs pages) — aucune page n'a à être modifiée, et une
  // page qui fournit déjà `#rp9-obs-type` garde SON markup.
  const obsTypeEl = ensureTypePicker();
  function ensureTypePicker(): HTMLSelectElement | null {
    const existing = $<HTMLSelectElement>('rp9-obs-type');
    if (existing) return existing;
    if (!obsEditPanel || typeof document.createElement !== 'function') return null;
    const label = document.createElement('label');
    label.className = 'rp9-obs-type-row';
    label.setAttribute('for', 'rp9-obs-type');
    label.textContent = 'Type d’obstacle ';
    const select = document.createElement('select');
    select.id = 'rp9-obs-type';
    select.className = 'rp9-input';
    for (const t of OBSTACLE_TYPES) {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.label;
      select.appendChild(opt);
    }
    label.appendChild(select);
    obsEditPanel.insertBefore(label, obsEditPanel.firstChild);
    return select;
  }
  /** Libellé du dégagement courant (m), affiché sous le sélecteur. */
  const clearanceLabel = (o: Obstacle): string =>
    `Dégagement autour : ${fmt1(clearanceForType(o.type))} m`;

  // CAL72 — SÉLECTEUR « provenance ». Même pattern que le sélecteur de type (PV61) : créé
  // ICI s'il n'existe pas déjà (aucune page n'a à être modifiée).
  const obsProvenanceEl = ensureProvenancePicker();
  function ensureProvenancePicker(): HTMLSelectElement | null {
    const existing = $<HTMLSelectElement>('rp9-obs-provenance');
    if (existing) return existing;
    if (!obsEditPanel || typeof document.createElement !== 'function') return null;
    const label = document.createElement('label');
    label.className = 'rp9-obs-provenance-row';
    label.setAttribute('for', 'rp9-obs-provenance');
    label.textContent = 'Provenance ';
    const select = document.createElement('select');
    select.id = 'rp9-obs-provenance';
    select.className = 'rp9-input';
    const noneOpt = document.createElement('option');
    noneOpt.value = '';
    noneOpt.textContent = 'Non renseignée';
    select.appendChild(noneOpt);
    for (const p of OBSTACLE_PROVENANCES) {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.label;
      select.appendChild(opt);
    }
    label.appendChild(select);
    obsEditPanel.insertBefore(label, obsEditPanel.firstChild);
    return select;
  }

  // ═══════════ CAL67 — objets d'ENVIRONNEMENT (arbres/bâtiments voisins, HORS contour) ═══
  // Panneau créé UNE fois si l'hôte ne le fournit pas déjà (même pattern que le sélecteur
  // de type d'obstacle) : deux boutons « Ajouter » + une liste éditable (hauteur/diamètre
  // ou longueur×largeur/feuillage + suppression). Position de pose : décalée au SUD du
  // centroïde du tracé (hors contour, sans détection automatique — l'utilisateur ajuste
  // ensuite la position via les coordonnées affichées).
  ensureEnvPanel();
  function ensureEnvPanel(): HTMLElement | null {
    const existing = $('rp9-env-panel');
    if (existing) return existing;
    const anchor = obstacleBtn?.parentElement ?? obsEditPanel?.parentElement ?? null;
    if (!anchor || typeof document.createElement !== 'function') return null;
    const panel = document.createElement('div');
    panel.id = 'rp9-env-panel';
    panel.className = 'rp9-env-panel mt-2';
    // CALX105 — les boutons ARMENT la pose : c'est le clic sur la carte qui donne le centre.
    panel.innerHTML =
      `<div class="flex gap-2">` +
      `<button type="button" id="rp9-env-add-tree" class="rp9-btn" aria-pressed="false">🌳 Poser un arbre</button>` +
      `<button type="button" id="rp9-env-add-building" class="rp9-btn" aria-pressed="false">🏢 Poser un bâtiment voisin</button>` +
      `</div><ul id="rp9-env-list" class="mt-2 flex flex-col gap-1 text-xs"></ul>`;
    anchor.appendChild(panel);
    return panel;
  }
  const envAddTreeBtn = $<HTMLButtonElement>('rp9-env-add-tree');
  const envAddBuildingBtn = $<HTMLButtonElement>('rp9-env-add-building');
  const envListEl = $('rp9-env-list');

  function envList(): EnvironmentObject[] {
    if (!ctx.environment) ctx.environment = [];
    return ctx.environment;
  }

  // CALX105 — mode de pose ARMÉ (le prochain clic carte pose l'objet), et glissé en cours.
  let poseArmee: EnvironmentKind | null = null;
  let glisseEnv: GlisseEnvironnement | null = null;

  const envKindLabel = (kind: EnvironmentKind) => (kind === 'arbre' ? 'Arbre' : 'Bâtiment voisin');

  /** Arme/désarme la pose d'un objet : le clic suivant sur la carte donnera son centre. */
  function armerPose(kind: EnvironmentKind | null) {
    poseArmee = kind;
    envAddTreeBtn?.setAttribute('aria-pressed', String(kind === 'arbre'));
    envAddBuildingBtn?.setAttribute('aria-pressed', String(kind === 'batiment'));
    if (typeof map.getCanvas === 'function') {
      const canvas = map.getCanvas();
      if (canvas) canvas.style.cursor = kind ? 'crosshair' : '';
    }
  }

  /** CALX105 — pose l'objet AU POINT CLIQUÉ. Aucune dimension n'est déduite : l'objet naît
   *  sans hauteur ni emprise, et l'écran demande de les saisir. */
  function poserEnvironment(kind: EnvironmentKind, centre: LngLat) {
    ctx.pushWorkshopHistory?.();
    ctx.envCounter = (ctx.envCounter ?? 0) + 1;
    const id = `env-${ctx.envCounter}`;
    envList().push(newEnvironmentObject(id, kind, centre));
    armerPose(null);
    renderEnvList();
    redrawEnvironment();
    recalcWithShading();
    setStatus(`${envKindLabel(kind)} posé à l’endroit cliqué — saisissez sa hauteur et ses dimensions (sans elles, il ne porte aucune ombre).`);
  }

  function updateEnvironment(id: string, transform: (o: EnvironmentObject) => EnvironmentObject) {
    const list = envList();
    const idx = list.findIndex((x) => x.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list[idx] = transform(list[idx]);
    renderEnvList();
    redrawEnvironment();
    recalcWithShading();
  }

  function deleteEnvironment(id: string) {
    const list = envList();
    const idx = list.findIndex((x) => x.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list.splice(idx, 1);
    renderEnvList();
    redrawEnvironment();
    recalcWithShading();
  }

  // ————————————————————————————————————————————————————————————————————
  // CALX105 — MARQUEURS DES OBJETS D'ENVIRONNEMENT SUR LA CARTE
  // Ils n'existaient nulle part sur la carte (seulement dans la liste et la 3D) : sans
  // marqueur, il n'y a rien à cliquer ni à glisser. La source et la couche sont créées ICI,
  // défensivement (style pas encore chargé, mode capture… = no-op silencieux).
  // ————————————————————————————————————————————————————————————————————
  function ensureEnvLayer(): boolean {
    if (typeof map.getSource !== 'function' || typeof map.addSource !== 'function') return false;
    try {
      if (!map.getSource('rp9-env')) map.addSource('rp9-env', { type: 'geojson', data: empty } as never);
      if (!map.getLayer?.('rp9-env')) {
        map.addLayer({
          id: 'rp9-env',
          type: 'circle',
          source: 'rp9-env',
          paint: {
            'circle-radius': 7,
            // Vert pour un arbre, gris pour un bâtiment : deux objets qu'on ne doit pas
            // confondre à l'œil, et deux couleurs distinctes de celles des obstacles/zones.
            'circle-color': ['case', ['==', ['get', 'kind'], 'arbre'], '#22c55e', '#94a3b8'],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#0f172a',
          },
        } as never);
      }
      return true;
    } catch {
      return false; // style pas prêt : le prochain appel retrouvera la carte
    }
  }

  /** CALX105 — (re)dessine un marqueur par objet d'environnement. */
  function redrawEnvironment() {
    if (!ensureEnvLayer()) return;
    srcOf('rp9-env')?.setData({
      type: 'FeatureCollection',
      features: envList().map((o) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [o.centerLng, o.centerLat] },
        properties: { id: o.id, kind: o.kind },
      })),
    } as never);
  }

  /** Marqueur d'environnement touché au point écran `pt` — MÊME tolérance de saisie que le
   *  glissé de sommet (`VERTEX_GRAB_PX`, doigt ⊃ pastille). */
  function envAtPoint(pt: maplibregl.Point): string | null {
    if (typeof map.queryRenderedFeatures !== 'function' || !map.getLayer?.('rp9-env')) return null;
    const box: [maplibregl.Point, maplibregl.Point] = [
      { x: pt.x - VERTEX_GRAB_PX, y: pt.y - VERTEX_GRAB_PX } as maplibregl.Point,
      { x: pt.x + VERTEX_GRAB_PX, y: pt.y + VERTEX_GRAB_PX } as maplibregl.Point,
    ];
    const hits = map.queryRenderedFeatures(box, { layers: ['rp9-env'] });
    const id = hits[0]?.properties?.id;
    return typeof id === 'string' ? id : null;
  }

  /** Tente de saisir un marqueur d'environnement pour le déplacer. */
  function tryBeginEnvMove(lngLat: LngLat, point: maplibregl.Point): boolean {
    const marqueur = envAtPoint(point);
    const geste = gesteEnvironnement({
      poseArmee,
      marqueur,
      modeObstacle: ctx.obstacleMode,
      modeDisposition: ctx.layoutMode,
    });
    if (geste !== 'deplacer' || !marqueur) return false;
    const o = envList().find((x) => x.id === marqueur);
    if (!o) return false;
    glisseEnv = debutGlisseEnvironnement(o, lngLat);
    map.dragPan?.disable?.();
    return true;
  }

  function doEnvMove(lngLat: LngLat) {
    if (!glisseEnv) return;
    const list = envList();
    const idx = list.findIndex((x) => x.id === glisseEnv!.id);
    if (idx < 0) return;
    const { centre, pousserHistorique } = avancerGlisseEnvironnement(glisseEnv, lngLat);
    if (pousserHistorique) ctx.pushWorkshopHistory?.(); // CAL100 — une seule photo par glissé
    list[idx] = deplacerEnvironment(list[idx], centre);
    redrawEnvironment();
  }

  function endEnvMove() {
    if (!glisseEnv) return;
    const bouge = glisseEnv.moved;
    glisseEnv = null;
    map.dragPan?.enable?.();
    ctx.suppressClick = true; // pas de pose/désélection parasite au click de synthèse
    // L'ombrage ne change que si l'objet a RÉELLEMENT bougé.
    if (bouge) {
      renderEnvList();
      recalcWithShading();
    }
  }

  function renderEnvList() {
    if (!envListEl) return;
    const list = envList();
    if (!list.length) {
      envListEl.innerHTML = '';
      return;
    }
    envListEl.innerHTML = list
      .map((o) => {
        const kindLabel = o.kind === 'arbre' ? 'Arbre' : 'Bâtiment voisin';
        const dimsInputs =
          o.kind === 'arbre'
            ? `<input type="text" data-env-crown="${o.id}" value="${o.crownDiameterM != null ? fmt1(o.crownDiameterM) : ''}" placeholder="Ø houppier m" class="rp9-input w-24" />
               <label class="flex items-center gap-1"><input type="checkbox" data-env-evergreen="${o.id}" ${o.evergreen ? 'checked' : ''} /> persistant</label>`
            : `<input type="text" data-env-length="${o.id}" value="${o.lengthM != null ? fmt1(o.lengthM) : ''}" placeholder="longueur m" class="rp9-input w-24" />
               <input type="text" data-env-width="${o.id}" value="${o.widthM != null ? fmt1(o.widthM) : ''}" placeholder="largeur m" class="rp9-input w-24" />`;
        // CORRECTIF — hauteur saisie mais AUCUNE emprise : l'objet ne porte aucune ombre
        // (aucune demi-largeur de repli n'est inventée) et l'écran le dit explicitement.
        const emprise = environmentNeedsFootprint(o)
          ? `<span data-env-emprise="${o.id}" class="text-alert-300">emprise à saisir — aucune ombre calculée</span>`
          : '';
        return `<li data-env-row="${o.id}" class="flex flex-wrap items-center gap-2 border border-white/10 p-2">
          <span class="font-semibold">${esc(kindLabel)}</span>
          <input type="text" data-env-height="${o.id}" value="${o.heightM != null ? fmt1(o.heightM) : ''}" placeholder="hauteur m" class="rp9-input w-24" />
          ${dimsInputs}
          ${emprise}
          <button type="button" data-env-del="${o.id}" class="ml-auto border border-alert-300/60 px-2 py-1 text-alert-300">× Supprimer</button>
        </li>`;
      })
      .join('');
  }

  // CALX105 — les boutons ARMENT la pose ; le clic sur la carte donne le centre.
  envAddTreeBtn?.addEventListener('click', () => {
    const on = poseArmee === 'arbre';
    armerPose(on ? null : 'arbre');
    setStatus(on ? 'Pose annulée.' : 'Cliquez sur la carte à l’endroit de l’arbre.');
  });
  envAddBuildingBtn?.addEventListener('click', () => {
    const on = poseArmee === 'batiment';
    armerPose(on ? null : 'batiment');
    setStatus(on ? 'Pose annulée.' : 'Cliquez sur la carte à l’endroit du bâtiment voisin.');
  });
  envListEl?.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement;
    const heightId = t.dataset.envHeight;
    const crownId = t.dataset.envCrown;
    const lengthId = t.dataset.envLength;
    const widthId = t.dataset.envWidth;
    const evergreenId = t.dataset.envEvergreen;
    if (heightId) updateEnvironment(heightId, (o) => withEnvHeight(o, t.value.trim() ? parseNum(t.value) : null));
    else if (crownId) updateEnvironment(crownId, (o) => withCrownDiameter(o, t.value.trim() ? parseNum(t.value) : null));
    else if (lengthId) updateEnvironment(lengthId, (o) => withFootprintDims(o, t.value.trim() ? parseNum(t.value) : null, o.widthM ?? null));
    else if (widthId) updateEnvironment(widthId, (o) => withFootprintDims(o, o.lengthM ?? null, t.value.trim() ? parseNum(t.value) : null));
    else if (evergreenId) updateEnvironment(evergreenId, (o) => withEvergreen(o, t.checked));
  });
  envListEl?.addEventListener('click', (e) => {
    const del = (e.target as HTMLElement).closest<HTMLElement>('[data-env-del]');
    if (del?.dataset.envDel) deleteEnvironment(del.dataset.envDel);
  });
  renderEnvList(); // état initial (dossier rechargé avec des objets d'environnement)
  redrawEnvironment(); // CALX105 — marqueurs du dossier rechargé

  // CALX105 — câblage carte : le clic POSE quand un mode est armé, le glissé DÉPLACE un
  // marqueur. Enregistré ici (le dispatcher de l'entrée n'est pas modifié) ; ces écouteurs
  // sont posés AVANT les siens, donc `tryBeginEnvMove` prend la main avant le glissé de
  // sommet/obstacle — ceux-ci refusent d'ailleurs de démarrer pendant un glissé d'objet.
  map.on?.('click', (e: maplibregl.MapMouseEvent) => {
    if (!poseArmee) return;
    poserEnvironment(poseArmee, [e.lngLat.lng, e.lngLat.lat]);
  });
  map.on?.('mousedown', (e: maplibregl.MapMouseEvent) => {
    tryBeginEnvMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on?.('mousemove', (e: maplibregl.MapMouseEvent) => {
    doEnvMove([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on?.('mouseup', () => endEnvMove());
  map.on?.('touchstart', (e: maplibregl.MapTouchEvent) => {
    if (e.points && e.points.length !== 1) return;
    tryBeginEnvMove([e.lngLat.lng, e.lngLat.lat], e.point);
  });
  map.on?.('touchmove', (e: maplibregl.MapTouchEvent) => {
    if (!glisseEnv) return;
    e.preventDefault?.();
    doEnvMove([e.lngLat.lng, e.lngLat.lat]);
  });
  map.on?.('touchend', () => endEnvMove());

  // ————————————————————————————————————————————————————————————————————
  // CAL69 — TRACÉ DES ZONES INTERDITE / RÉSERVÉE / PRÉFÉRÉE
  // Trois boutons arment le tracé (le glissé rectangulaire déjà en place sert de geste,
  // exactement comme pour un obstacle), puis chaque zone est rééditable : nature,
  // retrait SAISI, hauteur, repère. Écrit le contrat CAL68 (`exclusionZones`), relu tel
  // quel au rechargement du dossier.
  // ————————————————————————————————————————————————————————————————————
  ensureZonePanel();
  function ensureZonePanel(): HTMLElement | null {
    const existing = $('rp9-zone-panel');
    if (existing) return existing;
    const anchorEl = obstacleBtn?.parentElement ?? obsEditPanel?.parentElement ?? null;
    if (!anchorEl || typeof document.createElement !== 'function') return null;
    const panel = document.createElement('div');
    panel.id = 'rp9-zone-panel';
    panel.className = 'rp9-zone-panel mt-2';
    panel.innerHTML =
      `<div class="flex flex-wrap gap-2">` +
      EXCLUSION_NATURES.map(
        (n) =>
          `<button type="button" data-zone-add="${n.id}" class="rp9-btn" title="${esc(n.note)}" ` +
          `style="border-color:${exclusionColor(n.id)}">Zone ${esc(n.label.toLowerCase())}</button>`,
      ).join('') +
      `</div><ul id="rp9-zone-list" class="mt-2 flex flex-col gap-1 text-xs"></ul>`;
    anchorEl.appendChild(panel);
    return panel;
  }
  const zoneListEl = $('rp9-zone-list');

  function zoneList(): ExclusionZone[] {
    if (!ctx.exclusionZones) ctx.exclusionZones = [];
    return ctx.exclusionZones;
  }

  function beginZone(nature: ExclusionNature) {
    ctx.pendingZoneNature = nature;
    setObstacleMode(true);
    setStatus(`Tracez la zone ${nature.toLowerCase()} : glissez un rectangle sur la carte.`);
  }

  function updateZone(id: string, transform: (z: ExclusionZone) => ExclusionZone) {
    const list = zoneList();
    const idx = list.findIndex((z) => z.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list[idx] = transform(list[idx]);
    renderZoneList();
    redrawExclusionZones();
    recalcWithShading();
  }

  function deleteZone(id: string) {
    const list = zoneList();
    const idx = list.findIndex((z) => z.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list.splice(idx, 1);
    renderZoneList();
    redrawExclusionZones();
    recalcWithShading();
  }

  function renderZoneList() {
    if (!zoneListEl) return;
    const list = zoneList();
    if (!list.length) {
      zoneListEl.innerHTML = '';
      return;
    }
    zoneListEl.innerHTML = list
      .map((z) => {
        const opts = EXCLUSION_NATURES.map(
          (n) => `<option value="${n.id}" ${n.id === z.nature ? 'selected' : ''}>${esc(n.label)} — ${esc(n.note)}</option>`,
        ).join('');
        return `<li data-zone-row="${z.id}" class="flex flex-wrap items-center gap-2 border p-2" style="border-color:${exclusionColor(z.nature)}">
          <select data-zone-nature="${z.id}" class="rp9-input">${opts}</select>
          <input type="text" data-zone-label="${z.id}" value="${esc(z.label ?? '')}" placeholder="repère" class="rp9-input w-28" />
          <input type="text" data-zone-setback="${z.id}" value="${z.setbackM > 0 ? fmt1(z.setbackM) : ''}" placeholder="retrait m" class="rp9-input w-24" />
          <input type="text" data-zone-height="${z.id}" value="${z.heightM != null ? fmt1(z.heightM) : ''}" placeholder="hauteur m" class="rp9-input w-24" />
          <button type="button" data-zone-del="${z.id}" class="ml-auto border border-alert-300/60 px-2 py-1 text-alert-300">× Supprimer</button>
        </li>`;
      })
      .join('');
  }

  /** CAL69 — calque des zones : anneau DILATÉ du retrait saisi, couleur par nature. */
  function redrawExclusionZones() {
    srcOf('rp9-zones')?.setData({
      type: 'FeatureCollection',
      features: zoneList()
        .map((z) => {
          const ring = exclusionZoneRing(z);
          if (!ring) return null;
          return {
            type: 'Feature',
            geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] },
            properties: {
              id: z.id,
              color: exclusionColor(z.nature),
              title: z.label ? `${z.label} — ${z.nature}` : z.nature,
            },
          };
        })
        .filter(Boolean),
    } as never);
  }

  const zonePanelEl = $('rp9-zone-panel');
  zonePanelEl?.addEventListener('click', (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLElement>('[data-zone-add]');
    const nature = btn?.dataset.zoneAdd as ExclusionNature | undefined;
    if (nature) beginZone(nature);
  });
  zoneListEl?.addEventListener('change', (e) => {
    const t = e.target as HTMLInputElement & HTMLSelectElement;
    if (t.dataset.zoneNature) updateZone(t.dataset.zoneNature, (z) => withZoneNature(z, t.value as ExclusionNature));
    else if (t.dataset.zoneLabel) updateZone(t.dataset.zoneLabel, (z) => withZoneLabel(z, t.value));
    else if (t.dataset.zoneSetback) updateZone(t.dataset.zoneSetback, (z) => withZoneSetback(z, t.value.trim() ? parseNum(t.value) : null));
    else if (t.dataset.zoneHeight) updateZone(t.dataset.zoneHeight, (z) => withZoneHeight(z, t.value.trim() ? parseNum(t.value) : null));
  });
  zoneListEl?.addEventListener('click', (e) => {
    const del = (e.target as HTMLElement).closest<HTMLElement>('[data-zone-del]');
    if (del?.dataset.zoneDel) deleteZone(del.dataset.zoneDel);
  });
  renderZoneList(); // état initial (dossier rechargé avec des zones)

  // ————————————————————————————————————————————————————————————————————
  // CALX103 — TRACER UN OBSTACLE POLYGONAL AU CLIC
  //
  // Un obstacle était TOUJOURS un rectangle tiré au glissé : une souche en L ou un édicule
  // biscornu ne se saisissait pas. Parité HelioScope (les keepouts sont des polygones). Le
  // geste est celui du tracé du toit — clics successifs, double-clic pour fermer — donc
  // rien de neuf à apprendre, et la MÊME garde `isSimplePolygon` refuse un tracé croisé.
  //
  // Le panneau est créé ICI si la page hôte ne le fournit pas (patron `ensureTypePicker`) :
  // aucune page n'a à être modifiée.
  // ————————————————————————————————————————————————————————————————————

  let modeTrace: ModeTrace | null = null;
  let pointsEnCours: LngLat[] = [];

  function ensureFormePanel(): HTMLElement | null {
    const existing = $('rp9-forme-panel');
    if (existing) return existing;
    const anchorEl = obstacleBtn?.parentElement ?? obsEditPanel?.parentElement ?? null;
    if (!anchorEl || typeof document.createElement !== 'function') return null;
    const panel = document.createElement('div');
    panel.id = 'rp9-forme-panel';
    panel.className = 'rp9-forme-panel mt-2 flex flex-col gap-2 text-xs';
    panel.innerHTML =
      `<div class="flex flex-wrap items-center gap-2">` +
      `<button type="button" id="rp9-obs-polygone" class="rp9-btn" aria-pressed="false">Obstacle polygonal</button>` +
      `</div>` +
      `<span id="rp9-forme-motif" class="text-alert-300" role="alert" hidden></span>`;
    anchorEl.appendChild(panel);
    return panel;
  }
  ensureFormePanel();
  const obsPolygoneBtn = $<HTMLButtonElement>('rp9-obs-polygone');
  const formeMotifEl = $('rp9-forme-motif');

  /** Affiche (ou efface) un refus NOMMÉ, dans le panneau ET dans le bandeau de statut. */
  function direRefusForme(motif: string | null) {
    if (formeMotifEl) {
      formeMotifEl.textContent = motif ?? '';
      formeMotifEl.hidden = !motif;
    }
    if (motif) setStatus(motif);
  }

  /** Points du tracé en cours, sans doublon consécutif (le double-clic de fermeture émet
   *  deux clics au MÊME endroit : on ne garde pas le point en double). */
  function pointsPropres(): LngLat[] {
    const out: LngLat[] = [];
    for (const p of pointsEnCours) {
      const d = out[out.length - 1];
      if (d && Math.abs(d[0] - p[0]) < 1e-9 && Math.abs(d[1] - p[1]) < 1e-9) continue;
      out.push(p);
    }
    return out;
  }

  /** Aperçu du contour en cours de tracé. */
  function apercuTrace() {
    const pts = pointsPropres();
    if (pts.length < 2) {
      clearPreview();
      return;
    }
    srcOf('rp9-obs-preview')?.setData({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: pts },
      properties: {},
    } as never);
  }

  const LIBELLE_MODE: Record<ModeTrace, string> = {
    polygone: 'Cliquez les sommets de l’obstacle, double-clic pour fermer.',
  };

  /** Arme (ou désarme) un tracé à la volée. Réarmer le même mode le désarme. Le mode de
   *  tracé NEUTRALISE les glissés (sommet, obstacle) tant qu'il est armé — sinon deux
   *  gestes partiraient ensemble. */
  function armerTrace(mode: ModeTrace | null) {
    modeTrace = mode;
    pointsEnCours = [];
    clearPreview();
    direRefusForme(null);
    obsPolygoneBtn?.setAttribute('aria-pressed', String(mode === 'polygone'));
    if (typeof map.getCanvas === 'function') {
      const canvas = map.getCanvas();
      if (canvas) canvas.style.cursor = mode ? 'crosshair' : '';
    }
    if (mode) setStatus(LIBELLE_MODE[mode]);
  }

  /** CALX103 — ferme le contour tracé et crée l'obstacle polygonal, ou REFUSE en nommant
   *  la raison (moins de trois points, ou tracé qui se croise). */
  function fermerObstaclePolygone(): boolean {
    const pts = pointsPropres();
    const verdict = obstaclePolygone(`obs-${ctx.obsCounter + 1}`, pts);
    if (!verdict.ok) {
      direRefusForme(verdict.motif);
      return false;
    }
    ctx.obsCounter += 1;
    armerTrace(null);
    addObstacle(verdict.obstacle);
    setStatus(
      `Obstacle polygonal ajouté (${pts.length} sommets) — le calepinage évite sa forme réelle, ` +
        `dégagement ${fmt1(degagementObstacle(verdict.obstacle))} m compris.`,
    );
    return true;
  }

  obsPolygoneBtn?.addEventListener('click', () => armerTrace(modeTrace === 'polygone' ? null : 'polygone'));

  map.on?.('click', (e: maplibregl.MapMouseEvent) => {
    if (!modeTrace) return;
    pointsEnCours.push([e.lngLat.lng, e.lngLat.lat]);
    apercuTrace();
  });

  map.on?.('dblclick', (e: maplibregl.MapMouseEvent) => {
    if (modeTrace !== 'polygone') return;
    e.preventDefault?.();
    fermerObstaclePolygone();
  });


  function redrawObstacles() {
    srcOf('rp9-obs')?.setData({
      type: 'FeatureCollection',
      features: ctx.obstacles.map((o) => {
        // CALX103/CALX104 — la carte dessine la forme RÉELLE (contour polygonal, disque),
        // pas sa boîte englobante ; un obstacle sans forme reste le rectangle d'hier.
        const ring = anneauObstacle(o as ObstacleEtendu);
        return {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] },
          properties: { id: o.id, selected: o.id === ctx.selectedObsId, dims: dimsLabel(o) },
        };
      }),
    } as never);
  }

  function setPreviewRect(a: LngLat, b: LngLat) {
    const ring: LngLat[] = [a, [b[0], a[1]], b, [a[0], b[1]], a];
    srcOf('rp9-obs-preview')?.setData({ type: 'Feature', geometry: { type: 'LineString', coordinates: ring }, properties: {} } as never);
  }
  function clearPreview() {
    srcOf('rp9-obs-preview')?.setData(empty as never);
  }

  // — Sélection + édition d'un obstacle —
  function syncObsEdit() {
    const o = ctx.obstacles.find((x) => x.id === ctx.selectedObsId) ?? null;
    if (obsEditPanel) obsEditPanel.hidden = !o;
    syncEngageBanner(); // CAL72 — visible même sans sélection (porte sur TOUS les obstacles)
    if (!o) return;
    if (obsLengthEl && document.activeElement !== obsLengthEl) obsLengthEl.value = fmt1(o.lengthM);
    if (obsWidthEl && document.activeElement !== obsWidthEl) obsWidthEl.value = fmt1(o.widthM);
    // PV61 — le sélecteur reflète le type courant (défaut « autre ») et la ligne de
    // dimensions annonce le dégagement que ce type impose au calepinage.
    if (obsTypeEl && document.activeElement !== obsTypeEl) obsTypeEl.value = o.type ?? 'autre';
    if (obsDimsEl) obsDimsEl.textContent = `${dimsLabel(o)} · ${clearanceLabel(o)}`;
    // CAL66 — hauteur saisie (vide = obstacle plan, jamais un 0 inventé).
    if (obsHeightEl && document.activeElement !== obsHeightEl) obsHeightEl.value = o.heightM != null ? fmt1(o.heightM) : '';
    // CAL72 — provenance courante.
    if (obsProvenanceEl && document.activeElement !== obsProvenanceEl) obsProvenanceEl.value = o.provenance ?? '';
  }

  /** CAL72 — bandeau « compte non engageable » : visible dès qu'AU MOINS un obstacle de la
   *  zone porte une provenance PLAN/DEVINE (le moteur refuse d'engager un compte reposant
   *  sur un plan ou une supposition), avec la RAISON en clair. Passer l'obstacle en MESURÉ
   *  (ou toute autre provenance) lève le blocage. */
  function syncEngageBanner() {
    if (!obsEngageEl) return;
    const blockers = ctx.obstacles.filter((o) => isNonEngageable(o.provenance));
    if (!blockers.length) {
      obsEngageEl.textContent = '';
      obsEngageEl.hidden = true;
      return;
    }
    const labelFor = (p?: Obstacle['provenance']) => OBSTACLE_PROVENANCES.find((x) => x.id === p)?.label ?? p;
    const names = blockers.map((o) => `${esc(o.type ? OBSTACLE_TYPES.find((t) => t.id === o.type)?.label ?? o.type : 'obstacle')} (${esc(String(labelFor(o.provenance)))})`);
    obsEngageEl.hidden = false;
    obsEngageEl.textContent =
      `Compte NON engageable : ${blockers.length} obstacle(s) reposent sur une provenance non mesurée — ${names.join(', ')}. Passez-les en « Relevé sur place » (ou toute provenance mesurée) pour lever le blocage.`;
  }

  function selectObstacle(id: string | null) {
    ctx.selectedObsId = id;
    redrawObstacles();
    syncObsEdit();
  }

  /** Remplace l'obstacle sélectionné par une version transformée, puis recalcule. */
  function updateSelected(transform: (o: Obstacle) => Obstacle) {
    const idx = ctx.obstacles.findIndex((x) => x.id === ctx.selectedObsId);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.obstacles[idx] = transform(ctx.obstacles[idx]);
    redrawObstacles();
    syncObsEdit();
    recalcWithShading();
  }

  function deleteSelected() {
    if (!ctx.selectedObsId) return;
    ctx.pushWorkshopHistory?.(); // CAL100 — Ctrl+Z restaure l'obstacle À L'IDENTIQUE
    ctx.obstacles = ctx.obstacles.filter((x) => x.id !== ctx.selectedObsId);
    ctx.selectedObsId = null;
    redrawObstacles();
    syncObsEdit();
    recalcWithShading();
  }

  function addObstacle(o: Obstacle) {
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.obstacles.push(o);
    ctx.selectedObsId = o.id;
    redrawObstacles();
    syncObsEdit();
    recalcWithShading();
  }

  /** Obstacle touché au point écran `pt`, ou null. CAL107 — boîte de tolérance autour du
   *  point (doigt ⊃ trait fin), même principe que `vertexAtPoint` : au clic souris précis,
   *  la boîte ne change rien (un rectangle d'obstacle est toujours plus grand que le doigt) ;
   *  au doigt, elle évite de manquer un obstacle fin ou son bord. */
  function obstacleAtPoint(pt: maplibregl.Point): string | null {
    const box: [maplibregl.Point, maplibregl.Point] = [
      { x: pt.x - OBSTACLE_TAP_PX, y: pt.y - OBSTACLE_TAP_PX } as maplibregl.Point,
      { x: pt.x + OBSTACLE_TAP_PX, y: pt.y + OBSTACLE_TAP_PX } as maplibregl.Point,
    ];
    const hits = map.queryRenderedFeatures(box, { layers: ['rp9-obs'] });
    const id = hits[0]?.properties?.id;
    return typeof id === 'string' ? id : null;
  }

  // — Mode obstacle : on désactive le pan pour glisser-dessiner le rectangle —
  function setObstacleMode(on: boolean) {
    ctx.obstacleMode = on;
    obstacleBtn?.setAttribute('aria-pressed', String(on));
    if (on) {
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
    } else {
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      ctx.drawing = false;
      ctx.drawStart = null;
      clearPreview();
    }
  }

  function beginDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!ctx.obstacleMode || !ctx.closed) return;
    ctx.drawStart = { lngLat, point };
    ctx.drawing = true;
    ctx.lastDraw = lngLat;
  }
  function moveDraw(lngLat: LngLat) {
    if (!ctx.drawing || !ctx.drawStart) return;
    ctx.lastDraw = lngLat;
    setPreviewRect(ctx.drawStart.lngLat, lngLat);
  }
  function endDraw(lngLat: LngLat, point: maplibregl.Point) {
    if (!ctx.drawing || !ctx.drawStart) return;
    ctx.drawing = false;
    clearPreview();
    const start = ctx.drawStart;
    ctx.drawStart = null;
    ctx.suppressClick = true;
    const end = lngLat ?? ctx.lastDraw ?? start.lngLat;
    const dx = Math.abs(point.x - start.point.x);
    const dy = Math.abs(point.y - start.point.y);
    // CAL69 — une nature armée détourne le glissé vers une ZONE d'exclusion. Un simple
    // tap n'en crée AUCUNE : une zone sans surface n'a pas de sens (on désarme et on le dit).
    if (ctx.pendingZoneNature) {
      const nature = ctx.pendingZoneNature;
      ctx.pendingZoneNature = null;
      setObstacleMode(false);
      if (dx < OBSTACLE_TAP_PX && dy < OBSTACLE_TAP_PX) {
        setStatus('Zone non créée : glissez pour lui donner une surface.');
        return;
      }
      ctx.pushWorkshopHistory?.();
      ctx.zoneCounter = (ctx.zoneCounter ?? 0) + 1;
      zoneList().push(exclusionZoneFromDrag(`zone-${ctx.zoneCounter}`, nature, start.lngLat, end));
      renderZoneList();
      redrawExclusionZones();
      recalcWithShading();
      setStatus(
        nature === 'PREFEREE'
          ? 'Zone préférée ajoutée — elle ne change jamais le compte de modules.'
          : `Zone ${nature.toLowerCase()} ajoutée — sa surface est retirée du posable.`,
      );
      return;
    }
    const id = `obs-${++ctx.obsCounter}`;
    if (dx < OBSTACLE_TAP_PX && dy < OBSTACLE_TAP_PX) {
      // simple tap : sélectionne un obstacle existant, sinon en crée un par défaut
      const hit = obstacleAtPoint(point);
      if (hit) {
        setObstacleMode(false);
        selectObstacle(hit);
        setStatus('Obstacle sélectionné — ajustez sa taille au doigt ou au clavier.');
        return;
      }
      addObstacle(defaultObstacle(id, end));
    } else {
      addObstacle(obstacleFromDrag(id, start.lngLat, end));
    }
    setObstacleMode(false);
    setStatus('Obstacle ajouté — le calepinage l’évite. Touchez-le pour l’ajuster, ou ajoutez-en un autre.');
  }

  // — Déplacement d'un obstacle (glissé), Change C —
  /** Tente de saisir un obstacle sous le pointeur pour le déplacer. Renvoie true si
   *  un glissé de déplacement démarre (→ on neutralise le pan de la carte). */
  function tryBeginMove(lngLat: LngLat, point: maplibregl.Point): boolean {
    // W69 — en mode « Personnaliser la disposition », le glissé sert à déplacer un
    // PANNEAU (handlers dédiés plus bas). On ne saisit donc PAS un obstacle ici, sinon
    // les deux drags démarrent ensemble et relâcher déclenche un recalc qui efface la
    // disposition personnalisée.
    if (!ctx.closed || ctx.obstacleMode || ctx.layoutMode) return false;
    if (glisseEnv) return false; // CALX105 — un marqueur d'environnement est déjà saisi
    if (modeTrace) return false; // CALX103/104/403 — un tracé à la volée est armé
    const hit = obstacleAtPoint(point);
    if (!hit) return false;
    const o = ctx.obstacles.find((x) => x.id === hit);
    if (!o) return false;
    selectObstacle(hit);
    ctx.moveObs = { id: hit, startLng: lngLat[0], startLat: lngLat[1], centerLng: o.centerLng, centerLat: o.centerLat, moved: false };
    map.dragPan.disable();
    return true;
  }
  function doMove(lngLat: LngLat) {
    const moveObs = ctx.moveObs;
    if (!moveObs) return;
    const idx = ctx.obstacles.findIndex((x) => x.id === moveObs.id);
    if (idx < 0) return;
    // CAL100 — UNE SEULE photo pour tout le glissé, juste avant le PREMIER mouvement réel
    // (un simple tap de sélection, sans glissé, ne pousse donc rien à annuler).
    if (!moveObs.moved) ctx.pushWorkshopHistory?.();
    // Delta lng/lat : annule le parallaxe absolu de la vue inclinée.
    const centerLng = moveObs.centerLng + (lngLat[0] - moveObs.startLng);
    const centerLat = moveObs.centerLat + (lngLat[1] - moveObs.startLat);
    moveObs.moved = true;
    ctx.obstacles[idx] = { ...ctx.obstacles[idx], centerLng, centerLat };
    redrawObstacles();
    // Déplacement 3D EN DIRECT du seul mesh concerné (pas de re-pavage par image).
    const mesh = ctx.obstacleMeshes.get(moveObs.id);
    if (mesh) {
      const cosLat = Math.cos(ctx.sceneOrigin[1] * DEG2RAD);
      mesh.position.x = (centerLng - ctx.sceneOrigin[0]) * DEG2M * cosLat;
      mesh.position.y = (centerLat - ctx.sceneOrigin[1]) * DEG2M;
      map.triggerRepaint();
    }
  }
  function endMove() {
    const moveObs = ctx.moveObs;
    if (!moveObs) return;
    const moved = moveObs.moved;
    ctx.moveObs = null;
    map.dragPan.enable();
    ctx.suppressClick = true; // évite la désélection au click de synthèse
    // Re-pavage + recalcul seulement si l'obstacle a réellement bougé.
    if (moved) recalc();
  }

  // — W92 — Déplacement d'un SOMMET du tracé (généralisation du glissé d'obstacle) —
  /** Sommet du tracé touché au point écran `pt`, ou null (lit la propriété `idx`). */
  function vertexAtPoint(pt: maplibregl.Point): number | null {
    // Boîte de tolérance (rayon doigt ⊃ pastille) autour du point, comme un hit-test élargi.
    const box: [maplibregl.Point, maplibregl.Point] = [
      { x: pt.x - VERTEX_GRAB_PX, y: pt.y - VERTEX_GRAB_PX } as maplibregl.Point,
      { x: pt.x + VERTEX_GRAB_PX, y: pt.y + VERTEX_GRAB_PX } as maplibregl.Point,
    ];
    const hits = map.queryRenderedFeatures(box, { layers: ['rp9-pts'] });
    const idx = hits[0]?.properties?.idx;
    return typeof idx === 'number' ? idx : null;
  }

  /** Tente de saisir un SOMMET sous le pointeur pour le déplacer. Renvoie true si un glissé
   *  démarre (→ on neutralise le pan de la carte). N'opère que sur un tracé FERMÉ, hors mode
   *  obstacle / disposition (mêmes gardes que le glissé d'obstacle). */
  function tryBeginVertexMove(lngLat: LngLat, point: maplibregl.Point): boolean {
    if (!ctx.closed || ctx.obstacleMode || ctx.layoutMode) return false;
    if (glisseEnv) return false; // CALX105 — un marqueur d'environnement est déjà saisi
    if (modeTrace) return false; // CALX103/104/403 — un tracé à la volée est armé
    const idx = vertexAtPoint(point);
    // CALX91 — Alt maintenue : le geste est une SUPPRESSION (déjà traitée au mousedown),
    // jamais un glissé — sinon les deux partiraient ensemble.
    if (gesteSommet({ sommet: idx, altEnfoncee, ferme: ctx.closed, modeObstacle: ctx.obstacleMode, modeDisposition: ctx.layoutMode }) !== 'deplacer') {
      return false;
    }
    if (idx == null) return false;
    const v = ctx.vertices[idx];
    if (!v) return false;
    ctx.moveVertex = { idx, startLng: lngLat[0], startLat: lngLat[1], vLng: v[0], vLat: v[1], moved: false };
    map.dragPan.disable();
    return true;
  }
  function doVertexMove(lngLat: LngLat) {
    const mv = ctx.moveVertex;
    if (!mv) return;
    if (mv.idx < 0 || mv.idx >= ctx.vertices.length) return;
    // CAL100 — même photo unique que le glissé d'obstacle, juste avant le premier mouvement.
    if (!mv.moved) ctx.pushWorkshopHistory?.();
    // Delta lng/lat (annule le parallaxe de la vue inclinée), comme le glissé d'obstacle.
    const lng = mv.vLng + (lngLat[0] - mv.startLng);
    const lat = mv.vLat + (lngLat[1] - mv.startLat);
    mv.moved = true;
    ctx.vertices[mv.idx] = [lng, lat];
    redrawTrace(); // ligne + pastilles suivent le doigt en direct
  }
  function endVertexMove() {
    const mv = ctx.moveVertex;
    if (!mv) return;
    const moved = mv.moved;
    ctx.moveVertex = null;
    map.dragPan.enable();
    ctx.suppressClick = true; // évite une désélection/sélection parasite au click de synthèse
    // Re-pavage + recalcul seulement si le sommet a réellement bougé.
    if (moved) recalc();
  }

  // ————————————————————————————————————————————————————————————————————
  // CALX91 — INSERTION (double-clic sur une arête) ET SUPPRESSION (Alt+clic sur un sommet)
  //
  // Les deux gestes sont écoutés ICI, sur la carte : le dispatcher de l'entrée n'a pas à
  // être modifié. Sur un contour FERMÉ, son `dblclick` appelle `close()`, qui sort
  // immédiatement puisque le contour est déjà fermé — aucun conflit. Chaque geste pousse UN
  // pas d'historique (CAL100), donc Ctrl+Z le défait.
  // ————————————————————————————————————————————————————————————————————

  /** Alt maintenue ? Suivi au clavier ET relu sur chaque événement souris (source sûre). */
  let altEnfoncee = false;
  if (typeof document.addEventListener === 'function') {
    document.addEventListener('keydown', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') altEnfoncee = true;
    });
    document.addEventListener('keyup', (e) => {
      if ((e as KeyboardEvent).key === 'Alt') altEnfoncee = false;
    });
    window.addEventListener?.('blur', () => {
      altEnfoncee = false; // Alt+Tab : on ne garde jamais l'état
    });
  }

  /** Tolérance de SAISIE d'une arête, en mètres : le rayon pixel du sommet (`VERTEX_GRAB_PX`,
   *  convention de dessin déjà en place) lu au zoom courant. 0 = carte pas prête, aucun geste. */
  function toleranceSaisieM(lat: number): number {
    const zoom = typeof map.getZoom === 'function' ? map.getZoom() : Number.NaN;
    if (!Number.isFinite(zoom)) return 0;
    return VERTEX_GRAB_PX * metresParPixel(lat, zoom);
  }

  /** CALX91 — insère un sommet au projeté orthogonal du point sur l'arête la plus proche. */
  function insererSommetAu(lngLat: LngLat): boolean {
    if (!ctx.closed || ctx.obstacleMode || ctx.layoutMode) return false;
    // CALX103/104/403 — pendant un tracé à la volée, le double-clic FERME le tracé : il
    // n'insère surtout pas un sommet dans le contour du toit.
    if (modeTrace) return false;
    const trouve = insertionSurContour(ctx.vertices, lngLat, toleranceSaisieM(lngLat[1]));
    if (!trouve) return false;
    ctx.pushWorkshopHistory?.(); // CAL100 — un pas d'historique par geste
    ctx.vertices.splice(trouve.index + 1, 0, trouve.point);
    redrawTrace();
    recalc();
    setStatus('Sommet inséré sur le côté — glissez-le pour ajuster le contour.');
    return true;
  }

  /** CALX91 — supprime le sommet `idx`, ou explique en clair pourquoi c'est refusé. */
  function supprimerSommetDuContour(idx: number): boolean {
    const verdict = supprimerSommet(ctx.vertices, idx);
    if (!verdict.ok) {
      setStatus(verdict.motif);
      return false;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — un pas d'historique par geste
    ctx.vertices.splice(0, ctx.vertices.length, ...verdict.anneau);
    redrawTrace();
    recalc();
    setStatus(`Sommet supprimé — le contour garde ${ctx.vertices.length} sommets.`);
    return true;
  }

  map.on?.('mousedown', (e: maplibregl.MapMouseEvent) => {
    const alt = (e.originalEvent as MouseEvent | undefined)?.altKey;
    if (typeof alt === 'boolean') altEnfoncee = alt; // la source la plus sûre
    if (!altEnfoncee) return;
    const idx = vertexAtPoint(e.point);
    const geste = gesteSommet({
      sommet: idx,
      altEnfoncee,
      ferme: ctx.closed,
      modeObstacle: ctx.obstacleMode,
      modeDisposition: ctx.layoutMode,
    });
    if (geste !== 'supprimer' || idx == null) return;
    e.preventDefault?.();
    ctx.suppressClick = true; // pas de sélection/désélection parasite au click de synthèse
    supprimerSommetDuContour(idx);
  });

  map.on?.('dblclick', (e: maplibregl.MapMouseEvent) => {
    if (!ctx.closed) return; // pendant le tracé, le double-clic FERME (comportement inchangé)
    if (insererSommetAu([e.lngLat.lng, e.lngLat.lat])) e.preventDefault?.();
  });

  // — Câblage : bouton « ajouter », bouton « effacer », et édition de l'obstacle —
  obstacleBtn?.addEventListener('click', () => {
    if (!ctx.closed) {
      setStatus('Fermez d’abord le tracé du toit, puis ajoutez vos obstacles.');
      return;
    }
    setObstacleMode(!ctx.obstacleMode);
    selectObstacle(null);
    setStatus(
      ctx.obstacleMode
        ? 'Glissez sur le toit pour dessiner un obstacle (cheminée, climatiseur, lanterneau…).'
        : 'Ajout d’obstacle annulé.',
    );
  });
  obstacleClearBtn?.addEventListener('click', () => {
    if (!ctx.obstacles.length) return;
    ctx.obstacles = [];
    ctx.selectedObsId = null;
    setObstacleMode(false);
    redrawObstacles();
    syncObsEdit();
    if (ctx.closed) recalc();
    setStatus('Obstacles effacés — le calepinage reprend tout le toit.');
  });

  // — Édition de l'obstacle sélectionné (saisie exacte + boutons + / − + suppr.) —
  // W81 — on borne (clampDim, snap <0,5 → 0,5) et on recalcule à la VALIDATION
  // (`change` : blur ou Entrée), JAMAIS à chaque frappe. Sur `input`, écraser un
  // « 0. » ou un « 0,7 » en cours de saisie le ramenait à 0,5 au milieu de la
  // frappe et relançait le re-pavage. Aucune saisie n'est rejetée : la valeur
  // tapée vit librement dans le champ et n'est bornée qu'au commit.
  const parseNum = (s: string): number => parseFloat((s || '').replace(/\s/g, '').replace(',', '.'));
  obsLengthEl?.addEventListener('change', () => {
    if (!ctx.selectedObsId) return;
    const L = parseNum(obsLengthEl.value);
    if (!Number.isFinite(L)) return;
    updateSelected((o) => resizedObstacle(o, L, o.widthM));
  });
  obsWidthEl?.addEventListener('change', () => {
    if (!ctx.selectedObsId) return;
    const w = parseNum(obsWidthEl.value);
    if (!Number.isFinite(w)) return;
    updateSelected((o) => resizedObstacle(o, o.lengthM, w));
  });
  // PV61 — changer le TYPE ne touche pas la géométrie : il ne change que le dégagement,
  // donc on re-pave (recalc) pour que le calepinage reflète le nouveau recul.
  obsTypeEl?.addEventListener('change', () => {
    if (!ctx.selectedObsId) return;
    const type = obsTypeEl.value as ObstacleType;
    if (!OBSTACLE_TYPES.some((t) => t.id === type)) return;
    updateSelected((o) => ({ ...o, type }));
  });
  obsLengthEl?.addEventListener('blur', syncObsEdit);
  obsWidthEl?.addEventListener('blur', syncObsEdit);
  obsPlusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, OBSTACLE_STEP_FACTOR)));
  obsMinusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, 1 / OBSTACLE_STEP_FACTOR)));
  obsDeleteBtn?.addEventListener('click', deleteSelected);

  // CAL66 — hauteur saisie (même règle W81 : au `change`, jamais à chaque frappe ; vide ⇒
  // efface la hauteur, retour à « obstacle plan », jamais un 0 inventé).
  obsHeightEl?.addEventListener('change', () => {
    if (!ctx.selectedObsId) return;
    const raw = obsHeightEl.value.trim();
    const h = raw ? parseNum(raw) : null;
    updateSelected((o) => withHeight(o, h));
  });
  obsHeightEl?.addEventListener('blur', syncObsEdit);

  // CAL72 — provenance : ne change ni géométrie ni dégagement, mais peut lever/poser le
  // blocage « compte non engageable » (syncEngageBanner, via updateSelected → syncObsEdit).
  obsProvenanceEl?.addEventListener('change', () => {
    if (!ctx.selectedObsId) return;
    const v = obsProvenanceEl.value as ObstacleProvenance | '';
    updateSelected((o) => withProvenance(o, v || null));
  });

  // CAL73 — duplication d'un clic : copie l'obstacle sélectionné (dimensions/type/hauteur/
  // provenance), posée juste à côté (est), sélectionnée pour ajustement immédiat.
  obsDuplicateBtn?.addEventListener('click', () => {
    const o = ctx.obstacles.find((x) => x.id === ctx.selectedObsId);
    if (!o) {
      setStatus('Sélectionnez d’abord un obstacle à dupliquer.');
      return;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    const cosLat = Math.max(1e-6, Math.cos(o.centerLat * DEG2RAD));
    const dLng = (o.widthM + 1) / (DEG2M * cosLat);
    const dup = duplicatedObstacle(o, `obs-${++ctx.obsCounter}`, [o.centerLng + dLng, o.centerLat]);
    ctx.obstacles.push(dup);
    ctx.selectedObsId = dup.id;
    redrawObstacles();
    syncObsEdit();
    recalcWithShading();
    setStatus('Obstacle dupliqué — ajustez sa position, ou posez une trame régulière.');
  });

  // CAL73 — pose en trame régulière : N×M copies de l'obstacle sélectionné, au pas SAISI
  // (aucune détection automatique par vision — hors périmètre). Le premier point de la
  // trame REMPLACE l'original (même id) ; les suivants sont de NOUVEAUX obstacles — le tout
  // est UNE seule photo d'historique (un seul Ctrl+Z annule toute la trame).
  obsGridPlaceBtn?.addEventListener('click', () => {
    const o = ctx.obstacles.find((x) => x.id === ctx.selectedObsId);
    if (!o) {
      setStatus('Sélectionnez d’abord l’obstacle à poser en trame.');
      return;
    }
    const spacing = parseNum(obsGridSpacingEl?.value ?? '');
    const cols = Math.round(parseNum(obsGridColsEl?.value ?? ''));
    const rows = Math.round(parseNum(obsGridRowsEl?.value ?? ''));
    const positions = gridPositions([o.centerLng, o.centerLat], spacing, cols, rows);
    if (!positions.length) {
      setStatus('Pas ou nombre de trame invalide (saisissez un pas > 0 et des colonnes/lignes ≥ 1).');
      return;
    }
    ctx.pushWorkshopHistory?.(); // CAL100 — UNE SEULE photo pour toute la trame
    const [first, ...rest] = positions;
    const idx = ctx.obstacles.findIndex((x) => x.id === o.id);
    if (idx >= 0) ctx.obstacles[idx] = { ...o, centerLng: first[0], centerLat: first[1] };
    for (const p of rest) ctx.obstacles.push(duplicatedObstacle(o, `obs-${++ctx.obsCounter}`, p));
    redrawObstacles();
    syncObsEdit();
    recalcWithShading();
    setStatus(`${positions.length} obstacles posés en trame (${cols} × ${rows}, pas ${fmt1(spacing)} m).`);
  });

  syncEngageBanner(); // CAL72 — état initial (dossier rechargé avec des obstacles PLAN/DEVINE)

  return {
    redrawObstacles,
    redrawExclusionZones,
    beginZone,
    setPreviewRect,
    clearPreview,
    syncObsEdit,
    selectObstacle,
    updateSelected,
    deleteSelected,
    addObstacle,
    obstacleAtPoint,
    setObstacleMode,
    beginDraw,
    moveDraw,
    endDraw,
    tryBeginMove,
    doMove,
    endMove,
    vertexAtPoint,
    tryBeginVertexMove,
    doVertexMove,
    endVertexMove,
    envAtPoint,
    armerPoseEnvironment: armerPose,
    poserEnvironment,
    tryBeginEnvMove,
    doEnvMove,
    endEnvMove,
    redrawEnvironment,
    armerTrace,
    modeTraceArme: () => modeTrace,
  };
}

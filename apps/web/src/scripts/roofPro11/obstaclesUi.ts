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
  obstacleRing,
  obstacleFromDrag,
  defaultObstacle,
  scaledObstacle,
  resizedObstacle,
  OBSTACLE_STEP_FACTOR,
  type Obstacle,
} from '../../lib/obstacles';
import { type LngLat } from '../../lib/roof';
import { OBSTACLE_TAP_PX, VERTEX_GRAB_PX, DEG2RAD, DEG2M } from './constants';
import { $ } from './dom';
import { type Ctx } from './context';

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
}

export interface ObstaclesUi {
  redrawObstacles: () => void;
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
}

export function createObstaclesUi(ctx: Ctx, deps: ObstaclesUiDeps): ObstaclesUi {
  const { map, recalc, setStatus, redrawTrace } = deps;

  // FeatureCollection vide réutilisable (efface une source) — identique à l'entrée.
  const empty = { type: 'FeatureCollection', features: [] } as const;
  const srcOf = (id: string) => map.getSource(id) as maplibregl.GeoJSONSource | undefined;

  /** Décimal à 1 chiffre, à la française (identique à l'entrée). */
  const fmt1 = (n: number): string =>
    n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const dimsLabel = (o: Obstacle) => `${fmt1(o.lengthM)} × ${fmt1(o.widthM)} m`;

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

  function redrawObstacles() {
    srcOf('rp9-obs')?.setData({
      type: 'FeatureCollection',
      features: ctx.obstacles.map((o) => {
        const ring = obstacleRing(o);
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
    if (!o) return;
    if (obsLengthEl && document.activeElement !== obsLengthEl) obsLengthEl.value = fmt1(o.lengthM);
    if (obsWidthEl && document.activeElement !== obsWidthEl) obsWidthEl.value = fmt1(o.widthM);
    if (obsDimsEl) obsDimsEl.textContent = dimsLabel(o);
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
    ctx.obstacles[idx] = transform(ctx.obstacles[idx]);
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  function deleteSelected() {
    if (!ctx.selectedObsId) return;
    ctx.obstacles = ctx.obstacles.filter((x) => x.id !== ctx.selectedObsId);
    ctx.selectedObsId = null;
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  function addObstacle(o: Obstacle) {
    ctx.obstacles.push(o);
    ctx.selectedObsId = o.id;
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  /** Obstacle touché au point écran `pt`, ou null. */
  function obstacleAtPoint(pt: maplibregl.Point): string | null {
    const hits = map.queryRenderedFeatures(pt, { layers: ['rp9-obs'] });
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
    const idx = vertexAtPoint(point);
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
  obsLengthEl?.addEventListener('blur', syncObsEdit);
  obsWidthEl?.addEventListener('blur', syncObsEdit);
  obsPlusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, OBSTACLE_STEP_FACTOR)));
  obsMinusBtn?.addEventListener('click', () => updateSelected((o) => scaledObstacle(o, 1 / OBSTACLE_STEP_FACTOR)));
  obsDeleteBtn?.addEventListener('click', deleteSelected);

  return {
    redrawObstacles,
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
  };
}

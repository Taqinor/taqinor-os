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
import { $, esc } from './dom';
import { type Ctx } from './context';
import { OBSTACLE_TYPES, clearanceForType } from './types';
import {
  newEnvironmentObject,
  withEnvHeight,
  withCrownDiameter,
  withFootprintDims,
  withEvergreen,
  type EnvironmentObject,
  type EnvironmentKind,
} from './environment';

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
    panel.innerHTML =
      `<div class="flex gap-2">` +
      `<button type="button" id="rp9-env-add-tree" class="rp9-btn">🌳 Ajouter un arbre</button>` +
      `<button type="button" id="rp9-env-add-building" class="rp9-btn">🏢 Ajouter un bâtiment voisin</button>` +
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

  /** Position de pose par défaut : décalée au SUD du centroïde du tracé (hors contour),
   *  ou de l'origine [0,0] si aucun tracé n'existe encore. */
  function defaultEnvPosition(): LngLat {
    const c = ctx.centroid ?? ([0, 0] as LngLat);
    const dLat = 10 / DEG2M; // 10 m au sud, hors du contour dans la quasi-totalité des cas
    return [c[0], c[1] - dLat] as LngLat;
  }

  function addEnvironment(kind: EnvironmentKind) {
    ctx.pushWorkshopHistory?.();
    ctx.envCounter = (ctx.envCounter ?? 0) + 1;
    const id = `env-${ctx.envCounter}`;
    envList().push(newEnvironmentObject(id, kind, defaultEnvPosition()));
    renderEnvList();
    recalc();
    setStatus(`${kind === 'arbre' ? 'Arbre' : 'Bâtiment voisin'} posé au sud du toit — saisissez sa hauteur et ses dimensions.`);
  }

  function updateEnvironment(id: string, transform: (o: EnvironmentObject) => EnvironmentObject) {
    const list = envList();
    const idx = list.findIndex((x) => x.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list[idx] = transform(list[idx]);
    renderEnvList();
    recalc();
  }

  function deleteEnvironment(id: string) {
    const list = envList();
    const idx = list.findIndex((x) => x.id === id);
    if (idx < 0) return;
    ctx.pushWorkshopHistory?.();
    list.splice(idx, 1);
    renderEnvList();
    recalc();
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
        return `<li data-env-row="${o.id}" class="flex flex-wrap items-center gap-2 border border-white/10 p-2">
          <span class="font-semibold">${esc(kindLabel)}</span>
          <input type="text" data-env-height="${o.id}" value="${o.heightM != null ? fmt1(o.heightM) : ''}" placeholder="hauteur m" class="rp9-input w-24" />
          ${dimsInputs}
          <button type="button" data-env-del="${o.id}" class="ml-auto border border-alert-300/60 px-2 py-1 text-alert-300">× Supprimer</button>
        </li>`;
      })
      .join('');
  }

  envAddTreeBtn?.addEventListener('click', () => addEnvironment('arbre'));
  envAddBuildingBtn?.addEventListener('click', () => addEnvironment('batiment'));
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
    recalc();
  }

  function deleteSelected() {
    if (!ctx.selectedObsId) return;
    ctx.pushWorkshopHistory?.(); // CAL100 — Ctrl+Z restaure l'obstacle À L'IDENTIQUE
    ctx.obstacles = ctx.obstacles.filter((x) => x.id !== ctx.selectedObsId);
    ctx.selectedObsId = null;
    redrawObstacles();
    syncObsEdit();
    recalc();
  }

  function addObstacle(o: Obstacle) {
    ctx.pushWorkshopHistory?.(); // CAL100 — annulable comme le reste de l'atelier
    ctx.obstacles.push(o);
    ctx.selectedObsId = o.id;
    redrawObstacles();
    syncObsEdit();
    recalc();
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
    recalc();
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
    recalc();
    setStatus(`${positions.length} obstacles posés en trame (${cols} × ${rows}, pas ${fmt1(spacing)} m).`);
  });

  syncEngageBanner(); // CAL72 — état initial (dossier rechargé avec des obstacles PLAN/DEVINE)

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

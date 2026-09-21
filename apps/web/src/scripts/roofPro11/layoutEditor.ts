/**
 * W69 — « Personnaliser la disposition ». Extrait de roof-tool-pro11.ts (split
 * modulaire 2026-06-20) — comportement INCHANGÉ.
 *
 * Édition manuelle du calepinage gagnant : plan tactile des emplacements (tap-
 * sélection puis tap-cible), boutons + / − / réinitialiser, et glissé-déplacer sur
 * la 3D (raycast par déprojection écran→toit). Seul le NOMBRE/placement des
 * panneaux change ; le rendement par panneau et le pavage restent ceux de
 * l'optimiseur (recompute par COMPTAGE via la fenêtre de production).
 */
import maplibregl from 'maplibre-gl';
import {
  createLayoutState,
  occupiedCount,
  emptyIndices,
  nearestEmptyCell,
  movePanelToPoint,
  movePanelToCell,
  addFirstEmpty,
  removeLast,
  removePanel,
  resetToOptimal,
  fillAll,
  hasManualEdits as hasManualEditsPure,
  cellsInRect,
  moveGroup,
  planGroupMove,
  occupiedIndices,
  rowMembers,
  moveRowBy,
  nudgeAzimuthDeg,
} from '../../lib/layoutVariability';
// PV34 — sélection FACILE : géométrie PURE du cadre traversant, de la rangée et de
// l'accumulation (aucun état, aucun DOM — testée hors navigateur).
import {
  applySelectionGesture,
  normalizeSelectRect,
  panelsCrossingRect,
  pointInLayoutArea,
  rowMembersOf,
  type PanelFootprint,
} from '../../lib/panelSelection';
import { PANEL2_LONG_M } from '../../lib/roofPro2';
import { PANEL_KWC } from '../../lib/productionEngine';
import { type PackResult, type PanelGrid, type ConfigFamily } from '../../lib/estimatorBrainV2';
import {
  PITCH_VIEW,
  LAYOUT_GRAB_PX,
  DEG2RAD,
  DEG2M,
} from './constants';
import { $, fmt } from './dom';
import { type Ctx } from './context';
import { type LngLat, pointInPolygon } from '../../lib/roof';
import { type ProdConfig } from './types';
import { createLayoutHistory, createValueHistory, createWorkshopHistory, type WorkshopSnapshot } from './layoutHistory';
// PV30 — placement libre : géométrie PURE + pont vers le pavage gagnant.
import {
  moveFreePanels,
  placeFreePanels,
  addFreePanel,
  removeFreePanel,
  checkPanelAt,
  findFreeSpot,
  copyFreeState,
  rotateFreePanels,
  snapCandidateForPanel,
  alignPanels,
  distributePanels,
  toUV,
  toENU,
  rectAt,
  // CALX112/113 — primitives EXPORTÉES de la lib partagée, recomposées LOCALEMENT (le
  // fichier n'est pas dans le périmètre de cette lane, cf. LOT2_RECIPE.md) pour valider un
  // panneau dont le centre ET l'angle propre changent EN MÊME TEMPS (translation, réflexion) —
  // `checkPanelAt`/`checkPanelRotation` de la lib ne couvrent que l'un OU l'autre séparément.
  panelCornersUV,
  polyOverlap,
  polySeparation,
  type FreeGeom,
  type FreeCheck,
  type FreeLayoutState,
  type FreePanel,
  type FreeViolation,
  type FreeMargins,
  type RectUV,
  type Vec2,
} from '../../lib/freeLayout';
import { DEFAULT_FREE_MARGINS, FREE_STEP_M, freeGeomFrom, freeStateFromCenters, quantizeFree } from './freeMode';

/** Décimal à 1 chiffre, à la française (identique à l'entrée). */
const fmt1 = (n: number): string =>
  n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Dépendances injectées (3D + fenêtre de production + zones + recalcul actif). */
export interface LayoutEditorDeps {
  /** La carte MapLibre (déprojection écran→toit, vue de dessus, pan). */
  map: maplibregl.Map;
  /** Re-rend la 3D avec une occupation personnalisée (mêmes pack/grid/tilt/family). */
  renderScene: (
    pack: PackResult,
    grid: PanelGrid,
    tiltDeg: number,
    family: ConfigFamily,
    maxCount: number,
    flush?: boolean,
    occupiedSet?: Set<number>,
  ) => void;
  /** Config de production du plan courant (pour le recompute par comptage) ou null. */
  prodConfigFromState: () => ProdConfig | null;
  /** Met à jour la fenêtre de production au comptage demandé. */
  updateProductionWindow: (cfg: ProdConfig) => void;
  /** Instantané du résultat de la zone active (« Plusieurs zones »). */
  snapshotActiveAreaResult: () => void;
  /** Rendu du panneau « Plusieurs zones ». */
  renderAreasPanel: () => void;
  /** Recalcul complet de la zone active (sortie de mode). */
  renderActive: () => void;
  /** Le mode obstacle est-il actif ? (le glissé 3D le respecte). */
  isObstacleMode: () => boolean;
  /** W88 — surligne (or) le panneau 3D de la cellule donnée, ou efface tout (null). */
  setPanelHighlight: (cellIndex: number | null) => void;
  /** PV29 — surligne une SÉLECTION 3D (plusieurs cellules) + le survol, et la passe en
   *  ROUGE quand `refused` (déplacement impossible : rien n'a bougé). OPTIONNEL : absent,
   *  l'éditeur retombe sur `setPanelHighlight` (une seule cellule à la fois, W88). */
  setPanelSelection?: (selected: readonly number[] | null, hover: number | null, refused: boolean) => void;
  /** PV28 — demande de confirmation (injectable pour les tests). Défaut : `window.confirm`.
   *  Doit renvoyer true si l'utilisateur accepte de PERDRE sa disposition personnalisée. */
  confirmDiscard?: (message: string) => boolean;
  /** PV25 — recalcul COMPLET de la zone active (re-pavage) qui re-entre ensuite la
   *  disposition personnalisée (capture des centres → re-snap). C'est le `recalc()` de
   *  l'entrée. Optionnel : absent → le nudge d'azimut retombe sur `renderActive`. */
  recalcWithReenter?: () => void;
}

export interface LayoutEditor {
  layoutCap: () => number;
  ensureLayoutState: () => void;
  renderCustomLayout: () => void;
  screenToENU: (point: maplibregl.Point) => { x: number; y: number } | null;
  renderLayoutPanel: () => void;
  setLayoutMode: (on: boolean) => void;
  /** W79 — centres ENU des panneaux POSÉS de la disposition courante (avant un recalc qui
   *  va remplacer la lattice), pour les re-snapper sur la nouvelle lattice ensuite. */
  occupiedCenters: () => { cx: number; cy: number }[];
  /** W79 — après un recalc (nouvelle lattice), re-entre la disposition personnalisée en
   *  re-snappant les centres fournis vers les cellules valides les plus proches. */
  reenterCustomLayout: (prevCenters: { cx: number; cy: number }[]) => void;
  /** PV25 — indices actuellement SÉLECTIONNÉS (sélection multiple), triés. */
  selection: () => number[];
  /** PV25 — remplace la sélection multiple (indices non occupés ignorés). */
  setSelection: (indices: readonly number[]) => void;
  /** CAL235 — RETIRE des modules de la disposition lattice (geste explicite venu d'une
   *  proposition d'ombrage). Photographie l'atelier AVANT (donc Ctrl+Z l'annule, CAL100),
   *  puis re-rend. Renvoie le nombre RÉELLEMENT retiré ; 0 = rien n'a changé (pas d'état
   *  de disposition, placement libre actif, ou aucun index occupé visé). */
  removeCells: (indices: readonly number[]) => number;
  /** PV26 — annule / rétablit la dernière action de disposition (true si effectué). */
  undo: () => boolean;
  redo: () => boolean;
  /** PV28 — la disposition courante diverge-t-elle de l'optimum (édition manuelle) ? */
  hasManualEdits: () => boolean;
  /** PV28 — à appeler AVANT tout ré-agencement automatique : true = on peut continuer
   *  (aucune édition manuelle, ou l'utilisateur a accepté de la perdre). */
  confirmDiscardEdits: () => boolean;
  /** PV29 — sélectionne TOUTE la rangée du panneau donné (le geste « rangée » en un coup).
   *  Renvoie les membres sélectionnés ([] si la cellule n'est pas occupée). */
  selectRow: (cellIndex: number) => number[];
  /** PV30 — le mode PLACEMENT LIBRE est-il actif ? */
  isFreeMode: () => boolean;
  /** PV30 — bascule de mode. `false` revient à la lattice SANS demander (l'appelant a déjà
   *  décidé) ; le bouton d'interface, lui, passe par la demande de confirmation. */
  setFreeMode: (on: boolean) => boolean;
  /** PV30 — copie des panneaux posés librement (centres ENU). */
  freePanels: () => { cx: number; cy: number; face?: 'E' | 'W' }[];
  /** PV30 — marges RELÂCHABLES courantes (m). */
  freeMargins: () => { setbackM: number; gapM: number };
  /** PV30 — fixe les marges relâchables (m). Une valeur absente laisse la sienne. */
  setFreeMargins: (m: { setbackM?: number; gapM?: number }) => void;
  /** PV27 — HYDRATE la disposition depuis les centres de panneaux d'un layout exporté
   *  (leur repère d'origine si différent de celui du pavage courant). Re-snappe chaque
   *  centre sur la lattice courante et rend la 3D avec CETTE occupation. Renvoie true si
   *  la disposition a été appliquée. */
  hydrateLayout: (centers: readonly { cx: number; cy: number }[], origin?: readonly [number, number], mode?: 'lattice' | 'free') => boolean;
  /** CAL80 — tourne la sélection libre donnée (angle ABSOLU, °). Tout ou rien ; refusée
   *  SEULEMENT sur une contrainte DURE réelle (chevauchement, sortie de contour, obstacle). */
  freeRotateSelection: (angleDeg: number, members: readonly number[]) => boolean;
  /** CAL81 — position AIMANTÉE (bord de toit / autre panneau) pour un glissé en cours ; ne
   *  modifie rien, l'appelant applique ensuite le déplacement normalement. */
  freeSnapCandidate: (idx: number, cx: number, cy: number) => { cx: number; cy: number; snapped: boolean };
  /** CAL81 — « aligner » la sélection libre (rangée ou colonne droite). Tout ou rien. */
  freeAlignSelection: (axis: 'row' | 'col', members: readonly number[]) => boolean;
  /** CAL81 — « distribuer » la sélection libre à écart égal. Tout ou rien. */
  freeDistributeSelection: (members: readonly number[]) => boolean;
  /** CALX112 — duplique la sélection libre, collée au décalage SAISI (m, le long de l'axe
   *  des rangées). Un seul pas d'historique pour tout le geste ; tout ou rien. */
  dupliquerSelection: (members: readonly number[], decalageM: number) => boolean;
  /** CALX113 — symétrise la sélection libre par rapport à l'axe donné (droite ENU définie
   *  par deux points). Tout ou rien ; refusée seulement sur une contrainte DURE réelle. */
  symetriserSelection: (members: readonly number[], axis: { a: readonly [number, number]; b: readonly [number, number] }) => boolean;
  /** CALX116 — panneaux dont le CENTRE tombe dans l'anneau lasso (ENU), dans le mode courant. */
  panelsInLasso: (ring: readonly [number, number][]) => number[];
  /** CALX116 — le mode de sélection tracé courant est-il le LASSO (vs le cadre, défaut) ? */
  isLassoMode: () => boolean;
}

/**
 * PV29 — ÉCHAFAUDAGE DE SECOURS du panneau « Personnaliser la disposition ».
 *
 * La page astro publique porte ce balisage dans son HTML ; l'écran ERP (ToitureDesign)
 * a copié l'échafaudage `rp9-*` SANS cette fenêtre — l'éditeur y était donc totalement
 * injoignable (aucun bouton pour passer `ctx.layoutMode` à true, donc ni glissé, ni
 * sélection, ni flèches). On construit ici la MÊME structure d'identifiants, en surcouche
 * du conteneur de la carte, UNIQUEMENT quand la page hôte ne l'a pas fournie : la page
 * astro reste strictement inchangée (le `getElementById` trouve son propre balisage et on
 * ne crée rien), et l'ERP gagne la fonctionnalité sans toucher au code React.
 *
 * Volontairement sobre : replié sur un seul bouton tant que l'utilisateur ne l'ouvre pas.
 */
function buildFallbackLayoutDom(container: HTMLElement | null): void {
  if (typeof document === 'undefined' || !container) return;
  if (document.getElementById('rp9-layout-window')) return; // la page hôte a son balisage
  if (!document.getElementById('rp9-layout-fallback-style')) {
    const style = document.createElement('style');
    style.id = 'rp9-layout-fallback-style';
    style.textContent = [
      '#rp9-layout-window.rp9-layout-fallback{position:absolute;left:8px;bottom:8px;z-index:5;',
      'max-width:340px;max-height:70%;overflow:auto;padding:10px 12px;border:1px solid rgba(255,255,255,.25);',
      'background:rgba(12,17,28,.92);color:#fff;font:12px/1.45 system-ui,sans-serif}',
      '#rp9-layout-window.rp9-layout-fallback[hidden]{display:none}',
      '.rp9-layout-fallback button{border:1px solid rgba(255,255,255,.3);background:transparent;color:inherit;',
      'padding:5px 9px;font:inherit;font-weight:600;cursor:pointer;min-height:30px}',
      '.rp9-layout-fallback button:disabled{opacity:.4;cursor:not-allowed}',
      '.rp9-layout-fallback button[aria-pressed="true"]{border-color:#e0b25c;color:#e0b25c}',
      '.rp9-layout-fallback .rp9-fb-row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:8px}',
      '.rp9-layout-fallback dl{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin:8px 0 0}',
      '.rp9-layout-fallback dt{opacity:.65;font-size:10px;text-transform:uppercase}',
      '.rp9-layout-fallback dd{margin:0;font-weight:700}',
      '.rp9-layout-fallback .rp9-layout-grid{display:flex;flex-wrap:wrap;gap:2px;margin-top:6px}',
      '.rp9-layout-fallback .rp9-layout-cell{width:14px;height:14px;min-height:0;padding:0;',
      'border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.08)}',
      '.rp9-layout-fallback .rp9-layout-cell[data-occupied="true"]{background:#3f7fd0}',
      '.rp9-layout-fallback .rp9-layout-cell[aria-pressed="true"]{background:#e0b25c}',
      '.rp9-layout-fallback label{opacity:.7}',
      '.rp9-layout-fallback input{width:4.5em;border:1px solid rgba(255,255,255,.3);background:transparent;',
      'color:inherit;font:inherit;padding:4px 6px}',
      '#rp9-free-controls[hidden]{display:none}',
      '#rp9-free-measure{font-variant-numeric:tabular-nums;opacity:.85}',
    ].join('');
    document.head.appendChild(style);
  }
  const win = document.createElement('div');
  win.id = 'rp9-layout-window';
  win.className = 'rp9-layout-fallback';
  win.hidden = true;
  win.innerHTML = [
    '<button type="button" id="rp9-layout-toggle" aria-pressed="false">Déplacer les panneaux</button>',
    '<div id="rp9-layout-panel" hidden>',
    // PV30 — les deux modes, côte à côte. La lattice reste le mode d'entrée.
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-mode-lattice" aria-pressed="true">Emplacements validés</button>',
    '<button type="button" id="rp9-layout-mode-free" aria-pressed="false">Placement libre</button>',
    '</div>',
    '<div id="rp9-free-controls" hidden>',
    '<div class="rp9-fb-row">',
    '<label for="rp9-free-setback">Retrait de rive (cm)</label>',
    '<input id="rp9-free-setback" type="text" inputmode="decimal" step="any" size="4">',
    '<label for="rp9-free-gap">Écart panneaux (cm)</label>',
    '<input id="rp9-free-gap" type="text" inputmode="decimal" step="any" size="4">',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-free-add" aria-pressed="false">＋ Ajouter un panneau</button>',
    '<span id="rp9-free-measure" aria-live="polite"></span>',
    '</div>',
    '</div>',
    '<dl>',
    '<div><dd id="rp9-layout-count">—</dd><dt>Posés</dt></div>',
    '<div><dd id="rp9-layout-kwc">—</dd><dt>Puissance</dt></div>',
    '<div><dd id="rp9-layout-free">—</dd><dt>Libres</dt></div>',
    '<div><dd id="rp9-layout-cover">—</dd><dt>Couverture</dt></div>',
    '</dl>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-minus" aria-label="Retirer un panneau">−</button>',
    '<button type="button" id="rp9-layout-plus" aria-label="Ajouter un panneau">+</button>',
    '<button type="button" id="rp9-layout-fill">Remplir</button>',
    '<button type="button" id="rp9-layout-reset">↺ Optimale</button>',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-select" aria-pressed="false">▭ Sélection</button>',
    '<button type="button" id="rp9-layout-row" aria-pressed="false">⇔ Rangée</button>',
    '<button type="button" id="rp9-layout-clear-sel">✕ Effacer</button>',
    // PV34 — compteur TOUJOURS visible : on doit savoir à tout instant combien de
    // panneaux on tient, sans relire une note qui change à chaque geste.
    '<span id="rp9-layout-selcount" data-rp9-selcount="0" aria-live="polite">Aucun panneau sélectionné</span>',
    '</div>',
    '<div class="rp9-fb-row">',
    '<button type="button" id="rp9-layout-undo" disabled>↶ Annuler</button>',
    '<button type="button" id="rp9-layout-redo" disabled>↷ Rétablir</button>',
    '</div>',
    '<div class="rp9-fb-row" id="rp9-layout-azimuth" hidden>',
    '<span>Azimut</span>',
    '<button type="button" id="rp9-layout-az-minus" aria-label="Diminuer l’azimut d’un degré">−</button>',
    '<span id="rp9-layout-az-value">—</span>',
    '<button type="button" id="rp9-layout-az-plus" aria-label="Augmenter l’azimut d’un degré">+</button>',
    '</div>',
    '<div id="rp9-layout-grid" class="rp9-layout-grid" role="group" aria-label="Plan des emplacements de panneaux"></div>',
    '<p id="rp9-layout-note" aria-live="polite"></p>',
    '</div>',
  ].join('');
  container.appendChild(win);
}

// ═══════════ CALX112/113 — contrôles DURS d'un panneau CANDIDAT (centre ET angle propre
// changés EN MÊME TEMPS par une translation ou une réflexion) ═══════════
// `lib/freeLayout.ts` expose `checkRect` (translation, jamais d'angle) et
// `checkPanelRotation` (angle, jamais de centre) mais aucune primitive ne couvre les DEUX à
// la fois — et ce fichier n'est PAS dans le périmètre de cette lane (LOT2_RECIPE.md : fichiers
// CHAUDS, `rp11/layoutEditor.ts`/`freeMode.ts` seulement). Les fonctions ci-dessous
// RECOMPOSENT donc les trois contraintes DURES (contour / panneau / obstacle — jamais les
// deux RELÂCHABLES retrait/écart, hors du texte de CALX112/113) à partir des seules
// primitives déjà EXPORTÉES (`panelCornersUV`, `polyOverlap`, `polySeparation`) plus
// `pointInPolygon` (déjà la primitive du lasso CALX116 plus bas) — aucune règle métier
// neuve, seulement de la géométrie publique assemblée différemment.

/** 4 coins (u, v) d'un rectangle AXÉ — équivalent local du `rectCorners` privé de la lib. */
function cornersOfRect(r: RectUV): Vec2[] {
  return [
    [r.u0, r.v0],
    [r.u1, r.v0],
    [r.u1, r.v1],
    [r.u0, r.v1],
  ];
}

/** 4 coins (u, v) d'un panneau EXISTANT, à sa position/angle ACTUELS. */
function panelCornersFor(g: FreeGeom, p: Pick<FreePanel, 'cx' | 'cy' | 'angleDeg'>): Vec2[] {
  const [cu, cv] = toUV(g, p.cx, p.cy);
  return p.angleDeg ? panelCornersUV(g, cu, cv, p.angleDeg) : cornersOfRect(rectAt(g, cu, cv));
}

/** Deux segments [p1,p2] / [p3,p4] se croisent-ils vraiment ? (copie locale de la primitive
 *  privée `segmentsCross` de la lib — même algèbre, aucune règle neuve). */
function segCross(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2): boolean {
  const d = (a: Vec2, b: Vec2, c: Vec2) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(p3, p4, p1);
  const d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3);
  const d4 = d(p1, p2, p4);
  return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
}

/** Un coin du panneau est hors contour, OU une arête du contour traverse le panneau (le cas
 *  du toit CONCAVE : 4 coins dedans et une encoche qui coupe quand même le rectangle). */
function panelOutsideOutline(corners: readonly Vec2[], ringUV: readonly Vec2[]): boolean {
  for (const c of corners) if (!pointInPolygon(c, ringUV as [number, number][])) return true;
  for (let i = 0; i < corners.length; i++) {
    const a = corners[i];
    const b = corners[(i + 1) % corners.length];
    for (let j = 0, k = ringUV.length - 1; j < ringUV.length; k = j++) {
      if (segCross(ringUV[k], ringUV[j], a, b)) return true;
    }
  }
  return false;
}

/** Les trois contraintes DURES d'un panneau candidat (contour / panneaux / obstacles),
 *  renvoyées comme la liste des `FreeViolation` déjà nommées ailleurs dans ce fichier
 *  (`violationLabel`) — jamais un refus muet. `extra` = panneaux du MÊME geste déjà
 *  validés (copies, membres réfléchis) : ils s'excluent aussi entre eux. */
function hardViolationsFor(
  g: FreeGeom,
  ringUV: readonly Vec2[],
  corners: readonly Vec2[],
  othersCorners: readonly (readonly Vec2[])[],
  extra: readonly (readonly Vec2[])[],
): FreeViolation[] {
  const violations: FreeViolation[] = [];
  if (panelOutsideOutline(corners, ringUV)) violations.push('outline');
  let overlaps = false;
  for (const oc of othersCorners) if (polyOverlap(corners as Vec2[], oc as Vec2[])) overlaps = true;
  for (const oc of extra) if (polyOverlap(corners as Vec2[], oc as Vec2[])) overlaps = true;
  if (overlaps) violations.push('overlap');
  for (const o of g.obstacles) {
    if (o.ring.length < 3) continue;
    const ringO = o.ring.map(([x, y]) => toUV(g, x, y));
    const d = polyOverlap(corners as Vec2[], ringO) ? 0 : polySeparation(corners as Vec2[], ringO);
    if (d <= o.clearanceM) {
      violations.push('obstacle');
      break;
    }
  }
  return violations;
}

export function createLayoutEditor(ctx: Ctx, deps: LayoutEditorDeps): LayoutEditor {
  const {
    map,
    renderScene,
    prodConfigFromState,
    updateProductionWindow,
    snapshotActiveAreaResult,
    renderAreasPanel,
    renderActive,
    isObstacleMode,
  } = deps;
  const opts = ctx.opts;

  // PV29 — l'écran ERP ne fournit pas le balisage de la fenêtre : on le construit avant
  // toute recherche d'élément (no-op quand la page hôte l'a déjà, comme la page astro).
  buildFallbackLayoutDom(typeof map.getContainer === 'function' ? map.getContainer() : null);

  // ── PV34 — LA CAUSE RÉELLE du « je n'arrive pas à sélectionner un groupe » ──────
  // MapLibre embarque son PROPRE geste Maj + glissé : `BoxZoomHandler`, actif par défaut,
  // qui ne regarde QUE `e.shiftKey && e.button === 0` et zoome la caméra sur le rectangle
  // au relâchement (`fitScreenCoordinates`). Le `preventDefault()` d'un événement de carte
  // ne l'arrête PAS (le gestionnaire de MapLibre ne consulte jamais `defaultPrevented`).
  // Résultat vécu par le fondateur : le Maj + glissé de PV31 traçait bien le cadre doré,
  // mais le toit LUI ÉCHAPPAIT sous le curseur — le geste de sélection était mécaniquement
  // impossible à réussir. Le Maj + glissé appartient à l'éditeur : on éteint le box-zoom
  // (la molette, la navigation et le contrôle de zoom restent intacts).
  map.boxZoom?.disable?.();

  // — DOM du panneau « Personnaliser la disposition » —
  const layoutWindowEl = $('rp9-layout-window');
  const layoutToggleEl = $<HTMLButtonElement>('rp9-layout-toggle');
  const layoutPanelEl = $('rp9-layout-panel');
  const layoutCountEl = $('rp9-layout-count');
  const layoutKwcEl = $('rp9-layout-kwc');
  const layoutFreeEl = $('rp9-layout-free');
  const layoutCoverEl = $('rp9-layout-cover');
  const layoutMinusEl = $<HTMLButtonElement>('rp9-layout-minus');
  const layoutPlusEl = $<HTMLButtonElement>('rp9-layout-plus');
  const layoutResetEl = $<HTMLButtonElement>('rp9-layout-reset');
  const layoutFillEl = $<HTMLButtonElement>('rp9-layout-fill');
  const layoutGridEl = $('rp9-layout-grid');
  const layoutNoteEl = $('rp9-layout-note');
  // PV25 — sélection multiple / rangée / nudge d'azimut.
  const layoutSelectBtn = $<HTMLButtonElement>('rp9-layout-select');
  const layoutRowBtn = $<HTMLButtonElement>('rp9-layout-row');
  const layoutClearSelBtn = $<HTMLButtonElement>('rp9-layout-clear-sel');
  // CALX116 — bascule CADRE/LASSO, créée par le module si la page hôte ne la fournit pas
  // (même patron que `ensureTypePicker`/`ensureProvenancePicker`, obstaclesUi.ts:155-180).
  // Par défaut sur CADRE (comportement d'aujourd'hui inchangé).
  function ensureLassoToggle(): HTMLButtonElement | null {
    const existing = $<HTMLButtonElement>('rp9-layout-lasso');
    if (existing) return existing;
    if (typeof document === 'undefined' || typeof document.createElement !== 'function') return null;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'rp9-layout-lasso';
    btn.setAttribute('aria-pressed', 'false');
    btn.textContent = '◔ Lasso';
    if (layoutClearSelBtn?.parentElement) layoutClearSelBtn.insertAdjacentElement('afterend', btn);
    else if (layoutPanelEl) layoutPanelEl.appendChild(btn);
    else return null;
    return btn;
  }
  const layoutLassoBtn = ensureLassoToggle();
  // PV34 — compteur permanent « N panneaux sélectionnés ».
  const layoutSelCountEl = $('rp9-layout-selcount');
  const layoutAzWrapEl = $('rp9-layout-azimuth');
  const layoutAzMinusEl = $<HTMLButtonElement>('rp9-layout-az-minus');
  const layoutAzPlusEl = $<HTMLButtonElement>('rp9-layout-az-plus');
  const layoutAzValueEl = $('rp9-layout-az-value');
  // PV26 — annuler / rétablir.
  const layoutUndoBtn = $<HTMLButtonElement>('rp9-layout-undo');
  const layoutRedoBtn = $<HTMLButtonElement>('rp9-layout-redo');
  // PV30 — bascule de MODE + réglages du placement libre.
  const modeLatticeBtn = $<HTMLButtonElement>('rp9-layout-mode-lattice');
  const modeFreeBtn = $<HTMLButtonElement>('rp9-layout-mode-free');
  const freeControlsEl = $('rp9-free-controls');
  const freeSetbackEl = $<HTMLInputElement>('rp9-free-setback');
  const freeGapEl = $<HTMLInputElement>('rp9-free-gap');
  const freeAddBtn = $<HTMLButtonElement>('rp9-free-add');
  const freeMeasureEl = $('rp9-free-measure');

  // CALX112 — champ « décalage » + bouton « Dupliquer », créés par le module (même patron)
  // dans les réglages du placement libre : la duplication n'existe qu'en placement libre.
  // Le bouton reste INACTIF tant qu'aucun pas > 0 n'est saisi (jamais un décalage deviné).
  function ensureDuplicateControls(): { input: HTMLInputElement; btn: HTMLButtonElement } | null {
    const existingBtn = $<HTMLButtonElement>('rp9-free-dup-btn');
    const existingInput = $<HTMLInputElement>('rp9-free-dup-step');
    if (existingBtn && existingInput) return { input: existingInput, btn: existingBtn };
    if (typeof document === 'undefined' || !freeControlsEl) return null;
    const row = document.createElement('div');
    row.className = 'rp9-fb-row';
    const label = document.createElement('label');
    label.setAttribute('for', 'rp9-free-dup-step');
    label.textContent = 'Dupliquer, décalage (cm) ';
    const input = document.createElement('input');
    input.id = 'rp9-free-dup-step';
    input.type = 'text';
    input.inputMode = 'decimal';
    input.setAttribute('step', 'any');
    input.size = 5;
    label.appendChild(input);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'rp9-free-dup-btn';
    btn.textContent = '⧉ Dupliquer';
    btn.disabled = true;
    row.appendChild(label);
    row.appendChild(btn);
    freeControlsEl.appendChild(row);
    return { input, btn };
  }
  const dupControls = ensureDuplicateControls();
  const freeDupStepEl = dupControls?.input ?? null;
  const freeDupBtn = dupControls?.btn ?? null;

  // CALX113 — bouton « Symétrie », créé par le module (même patron), réglages du placement
  // libre. Armé : les DEUX prochains clics sur le toit désignent l'axe (droite définie par
  // deux points cliqués — la généralisation d'« une arête désignée au clic »).
  function ensureMirrorButton(): HTMLButtonElement | null {
    const existing = $<HTMLButtonElement>('rp9-free-mirror');
    if (existing) return existing;
    if (typeof document === 'undefined' || !freeControlsEl) return null;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'rp9-free-mirror';
    btn.setAttribute('aria-pressed', 'false');
    btn.textContent = '⇄ Symétrie';
    freeControlsEl.appendChild(btn);
    return btn;
  }
  const freeMirrorBtn = ensureMirrorButton();

  // PV25 — ÉTAT de la sélection multiple. Il vit dans ce module (rien à ajouter au ctx
  // partagé) : c'est une intention d'édition, pas un état de design.
  let selection: number[] = [];
  /** Mode « sélection » (tactile) : le glissé trace un rectangle au lieu de déplacer. */
  let selectMode = false;
  /** Mode « rangée » : le glissé sur un panneau emmène TOUTE sa rangée (axe contraint). */
  let rowMode = false;
  /** Marquee en cours (coin de départ en ENU) ou null. `moved` : le doigt/la souris a-t-il
   *  franchi le seuil de glissé ? (PV29 — sinon le geste est un Maj + CLIC, pas un cadre.) */
  let marquee:
    | {
        x0: number;
        y0: number;
        x1: number;
        y1: number;
        moved: boolean;
        startPoint: maplibregl.Point;
        /** PV34 — le lot encadré s'AJOUTE à la sélection (Maj) au lieu de la remplacer. */
        additive: boolean;
      }
    | null = null;
  /** Tolérance de « snap » d'un déplacement de groupe/rangée : chaque membre doit
   *  atterrir à moins d'un DEMI-panneau de l'endroit visé. Au-delà, le geste sort du toit
   *  (ou le groupe se replierait n'importe où) → refus, et rien ne bouge. */
  const GROUP_SNAP_M = PANEL2_LONG_M / 2;
  /** Pas du nudge d'azimut (°) — jamais un arrondi imposé, juste l'incrément du bouton. */
  const AZIMUTH_NUDGE_DEG = 1;
  /** PV29 — durée du clignotement ROUGE d'un déplacement REFUSÉ (ms). */
  const REFUSAL_FLASH_MS = 900;

  // ── PV31 — RECTANGLE DE SÉLECTION VISIBLE ────────────────────────────────────
  // Le cadre existait depuis PV25 mais n'était DESSINÉ nulle part : on ne voyait que le
  // compte en texte. On le peint ici en surcouche DOM du conteneur de carte, en pixels
  // ÉCRAN (les deux coins du geste) — volontairement PAS une source GeoJSON MapLibre ni un
  // objet Three.js : un simple <div> ne dépend d'aucun worker, d'aucun contexte WebGL, et
  // reste visible quoi qu'il arrive à la couche 3D.
  let marqueeEl: HTMLDivElement | null = null;
  function marqueeLayer(): HTMLDivElement | null {
    if (typeof document === 'undefined') return null;
    if (marqueeEl) return marqueeEl;
    const container = typeof map.getContainer === 'function' ? map.getContainer() : null;
    if (!container) return null;
    const el = document.createElement('div');
    el.id = 'rp9-marquee';
    el.setAttribute('aria-hidden', 'true'); // pur retour visuel : le compte est annoncé en texte
    el.style.cssText = [
      'position:absolute',
      'pointer-events:none', // ne vole jamais un événement à la carte
      'z-index:6',
      'display:none',
      'border:2px dashed #e0b25c',
      'background:rgba(224,178,92,0.18)',
      'box-shadow:0 0 0 1px rgba(0,0,0,0.55)', // lisible aussi sur une photo satellite claire
    ].join(';');
    container.appendChild(el);
    marqueeEl = el;
    return el;
  }
  /** Peint le cadre entre les deux coins ÉCRAN du geste (dans n'importe quel sens). */
  function showMarquee(a: maplibregl.Point, b: maplibregl.Point) {
    const el = marqueeLayer();
    if (!el) return;
    el.style.left = `${Math.min(a.x, b.x)}px`;
    el.style.top = `${Math.min(a.y, b.y)}px`;
    el.style.width = `${Math.abs(a.x - b.x)}px`;
    el.style.height = `${Math.abs(a.y - b.y)}px`;
    el.style.display = 'block';
  }
  function hideMarquee() {
    if (marqueeEl) marqueeEl.style.display = 'none';
  }

  // ── CALX116 — LASSO (tracé à main levée), en plus du cadre ───────────────────────
  // Bascule cadre/lasso : FAUX par défaut = cadre, le comportement d'aujourd'hui inchangé
  // (`ensureLassoToggle` ci-dessus). Le geste réutilise le MÊME déclenchement que le cadre
  // (Maj + glissé, ou mode « ▭ Sélection ») ; seule la FORME tracée change.
  let lassoMode = false;
  /** Glissé lasso en cours : anneau ENU échantillonné + ses points ÉCRAN (pour le tracé
   *  visible) — même convention `additive`/`moved` que `marquee`. */
  let lasso:
    | {
        ring: Vec2[];
        screenPts: maplibregl.Point[];
        startPoint: maplibregl.Point;
        moved: boolean;
        additive: boolean;
      }
    | null = null;
  /** Distance ÉCRAN minimale (px) entre deux points échantillonnés — un lasso qui
   *  enregistrerait CHAQUE pixel gonflerait l'anneau pour rien. */
  const LASSO_SAMPLE_PX = 6;
  /** Garde-fou de mémoire : un anneau ne grossit pas indéfiniment (le geste le plus long
   *  reste un tracé net, pas un journal de chaque micro-mouvement). */
  const LASSO_MAX_POINTS = 600;
  let lassoSvg: SVGSVGElement | null = null;
  let lassoPoly: SVGPolygonElement | null = null;
  function lassoLayer(): SVGPolygonElement | null {
    if (typeof document === 'undefined' || typeof document.createElementNS !== 'function') return null;
    if (lassoPoly) return lassoPoly;
    const container = typeof map.getContainer === 'function' ? map.getContainer() : null;
    if (!container) return null;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement;
    svg.setAttribute('id', 'rp9-lasso-svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.style.cssText = 'position:absolute;inset:0;z-index:6;pointer-events:none;display:none;width:100%;height:100%;';
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon') as SVGPolygonElement;
    poly.setAttribute('fill', 'rgba(224,178,92,0.18)');
    poly.setAttribute('stroke', '#e0b25c');
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute('stroke-dasharray', '4 3');
    svg.appendChild(poly);
    container.appendChild(svg);
    lassoSvg = svg;
    lassoPoly = poly;
    return poly;
  }
  /** Peint l'anneau lasso entre les points ÉCRAN accumulés. */
  function showLasso(points: readonly maplibregl.Point[]) {
    const poly = lassoLayer();
    if (!poly || !lassoSvg) return;
    poly.setAttribute('points', points.map((p) => `${p.x},${p.y}`).join(' '));
    lassoSvg.style.display = 'block';
  }
  function hideLasso() {
    if (lassoSvg) lassoSvg.style.display = 'none';
  }

  // ── PV29 — PEINTURE de la 3D : sélection (or) + survol (or clair) + refus (rouge) ──
  // `deps.setPanelHighlight` (W88) ne connaît qu'UNE cellule : la sélection multiple et la
  // rangée étaient invisibles sur la 3D. On centralise donc TOUT le rendu de sélection ici,
  // derrière un unique `setPanelHighlight(cellIndex)` LOCAL (le survol) qui repeint aussi la
  // sélection courante — sinon un simple mouvement de souris effaçait le groupe doré.
  const sceneHighlight = deps.setPanelHighlight;
  const sceneSelection = deps.setPanelSelection;
  /** Cellule actuellement SURVOLÉE (or clair), ou null. */
  let hoverCell: number | null = null;
  /** Cellules à peindre en ROUGE (refus d'un déplacement) pendant le clignotement. */
  let refusedCells: number[] = [];
  let refusalTimer: ReturnType<typeof setTimeout> | null = null;

  /** Repeint la 3D : sélection + survol + refus. Sans `setPanelSelection` (déps anciennes),
   *  on retombe honnêtement sur le surlignage à UNE cellule de W88. */
  function paintScene() {
    if (sceneSelection) {
      const refused = refusedCells.length > 0;
      sceneSelection(refused ? refusedCells : selection, hoverCell, refused);
      return;
    }
    sceneHighlight(hoverCell ?? (selection.length ? selection[0] : null));
  }

  /** PV31 — peint une sélection CANDIDATE (les panneaux actuellement encadrés) sans la
   *  committer : `selection` ne change qu'au relâchement du cadre. Sans le peintre
   *  multi-cellules, on ne montre rien plutôt que de mentir avec une seule cellule. */
  function paintPreviewSelection(candidate: readonly number[]) {
    if (!sceneSelection) return;
    sceneSelection(candidate, hoverCell, false);
  }

  /** W88 — surlignage du panneau SURVOLÉ. PV29 : il ne remplace plus la sélection, il
   *  s'y ajoute (les deux vivent dans le même buffer d'instances). */
  function setPanelHighlight(cellIndex: number | null) {
    hoverCell = cellIndex;
    if (cellIndex == null) {
      refusedCells = [];
      if (refusalTimer) {
        clearTimeout(refusalTimer);
        refusalTimer = null;
      }
    }
    paintScene();
  }

  /** PV29 — RETIRE la photo prise juste avant un geste qui a finalement été REFUSÉ. Sans
   *  cela, « annuler » consommait un pas pour ne rien changer (l'utilisateur appuie et rien
   *  ne bouge) : un geste refusé n'est pas une action, il n'a rien à annuler. Même
   *  mécanique que le nudge clavier bloqué. */
  function dropHistoryPhoto() {
    history.drop();
    workshopHistory.drop(); // CAL100 — même geste refusé, même photo à jeter
  }

  /** PV29 — REFUS VISIBLE : les panneaux concernés virent au rouge un court instant, puis
   *  reprennent leur teinte. Aucun panneau n'a bougé — c'est exactement ce que ça dit. */
  function flashRefusal(cells: readonly number[]) {
    if (!cells.length) return;
    if (refusalTimer) clearTimeout(refusalTimer);
    refusedCells = [...cells];
    paintScene();
    refusalTimer = setTimeout(() => {
      refusalTimer = null;
      refusedCells = [];
      paintScene();
    }, REFUSAL_FLASH_MS);
  }

  /**
   * PV29 — QUANTIFIE un déplacement de groupe sur le PAS DU CALEPINAGE (largeur de rangée
   * sur l'axe u, pas de rangée sur l'axe d'empilement) — exactement les pas déjà utilisés
   * par les flèches du clavier, jamais un pas inventé. Un groupe/une rangée se pose donc
   * sur la grille au lieu d'atterrir « au plus près du curseur » : la forme interne du
   * groupe est préservée (une rangée reste une rangée). Pas de grille connu → delta brut
   * (comportement historique).
   */
  // ═══════════ PV30 — PLACEMENT LIBRE (second mode, jamais un remplacement) ═══════════
  // Le mode lattice reste le DÉFAUT et n'est touché nulle part : chaque fonction ci-dessous
  // est soit nouvelle, soit branchée derrière `ctx.freeMode`. Éteint, le fichier se
  // comporte exactement comme avant.

  /** Historique PROPRE au placement libre (positions continues, pas une occupation). */
  const freeHistory = createValueHistory<FreeLayoutState>(copyFreeState);
  /** Le prochain clic doit-il POSER un nouveau panneau ? (bouton « Ajouter »). */
  let freeAddArmed = false;
  /** CALX113 — la désignation de l'axe de symétrie est-elle ARMÉE ? (bouton « Symétrie »). */
  let mirrorArmed = false;
  /** CALX113 — premier point ENU cliqué de l'axe en cours de désignation, ou null. */
  let mirrorFirstPoint: { x: number; y: number } | null = null;

  /**
   * Marges RELACHABLES courantes, avec repli sur celles de l'etude. Un `ctx` fourni par
   * un hote anterieur a PV30 ne porte pas `freeMargins` : lire le champ en aveugle y
   * plantait le rendu du panneau (donc TOUT le mode disposition), y compris en mode
   * lattice ou le placement libre n'a rien a faire. On ne suppose donc rien du `ctx`.
   */
  function margins(): FreeMargins {
    const m = ctx.freeMargins;
    return {
      setbackM: Number.isFinite(m?.setbackM as number) ? m.setbackM : DEFAULT_FREE_MARGINS.setbackM,
      gapM: Number.isFinite(m?.gapM as number) ? m.gapM : DEFAULT_FREE_MARGINS.gapM,
    };
  }

  /** Contexte géométrique courant du placement libre (axes, dimensions, contour,
   *  obstacles), ou null si le plan ne permet pas de décrire un panneau. */
  function freeGeom(): FreeGeom | null {
    return freeGeomFrom(ctx.layoutPlan, ctx.obstacles ?? []);
  }
  /** État libre courant (jamais null quand `ctx.freeMode` est vrai). */
  function freeState(): FreeLayoutState | null {
    return ctx.freeState;
  }
  /** Le mode libre est-il RÉELLEMENT utilisable maintenant ? */
  function freeActive(): boolean {
    return !!ctx.freeMode && !!ctx.freeState;
  }
  function recordFreeHistory() {
    if (ctx.freeState) freeHistory.push(ctx.freeState);
    pushWorkshopHistory(); // CAL100 — même geste, historique généralisé EN PARALLÈLE
  }
  /** CAL100 — jette la photo libre ET sa contrepartie généralisée (même geste refusé) —
   *  sans ça `workshopHistory` garderait une photo qu'il n'y a rien à annuler. */
  function dropFreeHistory() {
    freeHistory.drop();
    workshopHistory.drop();
  }

  /** Libellé FR d'une contrainte violée — on NOMME ce qui bloque, jamais « impossible ». */
  function violationLabel(v: FreeViolation): string {
    switch (v) {
      case 'outline':
        return 'le panneau sortirait du toit';
      case 'overlap':
        return 'il chevaucherait un autre panneau';
      case 'obstacle':
        return 'il tomberait sur un obstacle (ou son dégagement)';
      case 'setback':
        return 'il passerait sous le retrait de rive que vous avez fixé';
      case 'gap':
        return 'il passerait sous l’écart entre panneaux que vous avez fixé';
      default:
        return 'placement invalide';
    }
  }
  const cm = (m: number): string => `${Math.round(m * 100)} cm`;

  /** Affiche les distances MESURÉES (rive / voisin) — c'est ce qui rend une marge réduite
   *  VISIBLE : l'utilisateur voit le chiffre auquel il descend, il ne le devine pas. */
  function showMeasure(chk: FreeCheck | null) {
    if (!freeMeasureEl) return;
    if (!chk) {
      freeMeasureEl.textContent = '';
      return;
    }
    const edge = Number.isFinite(chk.edgeM) ? cm(chk.edgeM) : '—';
    const near = chk.panelM === null ? '—' : cm(chk.panelM);
    const verdict = chk.ok ? '' : ` — ${chk.violations.map(violationLabel).join(', ')}`;
    freeMeasureEl.textContent = `Rive : ${edge} · Voisin : ${near}${verdict}`;
  }

  /** Panneau libre le plus proche d'un point écran (même seuil de saisie que la lattice). */
  function freePanelAt(point: maplibregl.Point): number | null {
    const st = freeState();
    const enu = screenToENU(point);
    if (!st || !enu) return null;
    let best = -1;
    let bestD = Infinity;
    for (let i = 0; i < st.panels.length; i++) {
      const d = (st.panels[i].cx - enu.x) ** 2 + (st.panels[i].cy - enu.y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    const grabR2 = (PANEL2_LONG_M * 0.7) ** 2;
    return best >= 0 && bestD <= grabR2 ? best : null;
  }

  /**
   * PV34 — EMPRISE d'un panneau du plan courant (axes du pavage + dimensions réelles),
   * ou null si le plan ne décrit pas de panneau. Disponible dans les DEUX modes : la
   * lattice est pavée par le même plan que le placement libre, on ne réinvente donc
   * aucune dimension. Sans elle, la sélection retombe sur le critère historique.
   */
  function panelFootprint(): PanelFootprint | null {
    const g = freeGeom();
    if (!g) return null;
    return { u: g.u, s: g.s, widthM: g.widthM, depthM: g.depthM };
  }

  /** PV34 — panneaux libres TRAVERSÉS par le cadre (et plus « centre dedans »). */
  function freeInRect(rect: { x0: number; y0: number; x1: number; y1: number }): number[] {
    const st = freeState();
    if (!st) return [];
    return panelsCrossingRect(st.panels, normalizeSelectRect(rect.x0, rect.y0, rect.x1, rect.y1), panelFootprint());
  }

  /**
   * PV34 — cellules OCCUPÉES traversées par le cadre, en mode lattice. On teste les
   * centres des cellules posées avec l'emprise du panneau, puis on retraduit vers les
   * index de cellules : le reste de l'éditeur continue de ne manipuler que des index.
   */
  function latticeInRect(rect: { x0: number; y0: number; x1: number; y1: number }): number[] {
    const st = ctx.layoutState;
    if (!st) return [];
    const fp = panelFootprint();
    if (!fp) return cellsInRect(st, rect); // repli EXACT sur le comportement d'avant
    const posed = occupiedIndices(st);
    const hits = panelsCrossingRect(
      posed.map((i) => st.cells[i]),
      normalizeSelectRect(rect.x0, rect.y0, rect.x1, rect.y1),
      fp,
    );
    return hits.map((k) => posed[k]);
  }

  /** PV34 — panneaux traversés par le cadre, dans le mode courant. */
  function panelsInMarquee(rect: { x0: number; y0: number; x1: number; y1: number }): number[] {
    return freeActive() ? freeInRect(rect) : latticeInRect(rect);
  }

  /**
   * CALX116 — panneaux dont le CENTRE tombe dans l'anneau lasso (ENU), dans le mode courant.
   * Critère « centre dedans » (et non « traversé », contrairement au cadre) : c'est le
   * critère annoncé par la tâche, et il laisse le lasso isoler une poche EXACTE sans
   * attraper un panneau que le tracé n'a qu'effleuré du bout du contour.
   */
  function panelsInLasso(ring: readonly Vec2[]): number[] {
    if (ring.length < 3) return [];
    if (freeActive()) {
      const st = freeState();
      if (!st) return [];
      const out: number[] = [];
      for (let i = 0; i < st.panels.length; i++) {
        if (pointInPolygon([st.panels[i].cx, st.panels[i].cy], ring as [number, number][])) out.push(i);
      }
      return out;
    }
    const st = ctx.layoutState;
    if (!st) return [];
    const posed = occupiedIndices(st);
    const out: number[] = [];
    for (const idx of posed) {
      const c = st.cells[idx];
      if (pointInPolygon([c.cx, c.cy], ring as [number, number][])) out.push(idx);
    }
    return out;
  }

  /**
   * PV34 — le point ENU tombe-t-il sur la ZONE DE CALEPINAGE ? Sert à trancher un glissé
   * ambigu à la souris : parti du toit → cadre de sélection ; parti d'ailleurs →
   * déplacement de carte (inchangé). On prend la lattice ENTIÈRE (emplacements vides
   * compris) : c'est la surface que l'optimiseur a validée, donc celle où éditer a un sens.
   */
  function pointOnLayoutArea(x: number, y: number): boolean {
    const fp = panelFootprint();
    const margin = fp ? Math.max(fp.widthM, fp.depthM) / 2 : PANEL2_LONG_M / 2;
    if (freeActive()) {
      const st = freeState();
      return !!st && pointInLayoutArea(st.panels, x, y, margin);
    }
    const st = ctx.layoutState;
    return !!st && pointInLayoutArea(st.cells, x, y, margin);
  }

  /** Membres de la RANGÉE d'un panneau libre : ceux qui partagent sa coordonnée
   *  d'empilement `v` (dans le repère du pavage) à une demi-profondeur près. La rangée
   *  reste une notion géométrique réelle, même sans lattice. */
  function freeRowMembers(idx: number): number[] {
    // PV34 — même règle, désormais dans le module PUR (testée hors navigateur) : la
    // rangée est la coordonnée d'empilement partagée à une demi-profondeur près.
    const st = freeState();
    if (!st) return [];
    return rowMembersOf(st.panels, idx, panelFootprint());
  }

  /** Déplace la sélection libre de (dx, dy) mètres — rigide, tout ou rien. */
  function freeMoveSelection(dx: number, dy: number, members: readonly number[]): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || !members.length) return false;
    recordFreeHistory();
    const res = moveFreePanels(st, g, members, quantizeFree(dx), quantizeFree(dy), margins());
    if (!res.ok) {
      dropFreeHistory();
      flashRefusal(members);
      if (res.blocked) showMeasure(res.blocked);
      if (layoutNoteEl) {
        const why = res.blocked ? res.blocked.violations.map(violationLabel).join(', ') : 'placement invalide';
        layoutNoteEl.textContent = `Déplacement refusé : ${why} — rien n’a bougé.`;
      }
      renderLayoutPanel();
      return false;
    }
    if (layoutNoteEl) layoutNoteEl.textContent = `Déplacé — ${fmt(members.length)} panneaux (placement libre).`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** POSE un panneau au point ENU visé (clic après « Ajouter »). */
  function freeAddAt(cx: number, cy: number): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g) return false;
    recordFreeHistory();
    const res = addFreePanel(st, g, quantizeFree(cx), quantizeFree(cy), margins());
    showMeasure(res.check);
    if (!res.ok) {
      dropFreeHistory();
      if (layoutNoteEl) {
        layoutNoteEl.textContent = `Impossible de poser un panneau ici : ${res.check.violations.map(violationLabel).join(', ')}.`;
      }
      renderLayoutPanel();
      return false;
    }
    setSelection([res.index]);
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Panneau ajouté — ${fmt(st.panels.length)} posés. Le devis suivra ce nombre à l’enregistrement.`;
    }
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** RETIRE un panneau libre (Alt + clic, ou le bouton « − »). */
  function freeRemoveAt(idx: number): boolean {
    const st = freeState();
    if (!st) return false;
    recordFreeHistory();
    if (!removeFreePanel(st, idx)) {
      dropFreeHistory();
      return false;
    }
    setSelection([]);
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Panneau retiré — ${fmt(st.panels.length)} posés. Le devis suivra ce nombre à l’enregistrement.`;
    }
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** CAL80 — tourne la sélection libre (angle ABSOLU, ° ; chaque membre autour de SON propre
   *  centre) — tout ou rien, refusée SEULEMENT sur une contrainte DURE réelle (chevauchement,
   *  sortie de contour, obstacle). */
  function freeRotateSelection(angleDeg: number, members: readonly number[]): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || !members.length) return false;
    recordFreeHistory();
    const res = rotateFreePanels(st, g, members, angleDeg, margins());
    if (!res.ok) {
      dropFreeHistory();
      flashRefusal(members);
      if (layoutNoteEl) {
        const why = res.blocked ? res.blocked.violations.map(violationLabel).join(', ') : 'rotation invalide';
        layoutNoteEl.textContent = `Rotation refusée : ${why} — rien n’a bougé.`;
      }
      renderLayoutPanel();
      return false;
    }
    if (layoutNoteEl) layoutNoteEl.textContent = `Tourné — ${fmt(members.length)} panneaux (placement libre).`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** CAL81 — position AIMANTÉE (bord de toit / autre panneau) pour un glissé libre en cours,
   *  dans le seuil `LAYOUT_GRAB_PX`-équivalent (même pas que `FREE_STEP_M`, ×10 = 10 cm). Ne
   *  MODIFIE rien : c'est une proposition que l'appelant valide ensuite normalement. */
  const FREE_SNAP_THRESHOLD_M = 0.1;
  function freeSnapCandidate(idx: number, cx: number, cy: number): { cx: number; cy: number; snapped: boolean } {
    const g = freeGeom();
    const st = freeState();
    if (!st || !g) return { cx, cy, snapped: false };
    const [u, v] = toUV(g, cx, cy);
    const snap = snapCandidateForPanel(st, g, idx, u, v, FREE_SNAP_THRESHOLD_M);
    const [scx, scy] = toENU(g, snap.cu, snap.cv);
    return { cx: snap.snapped ? scx : cx, cy: snap.snapped ? scy : cy, snapped: snap.snapped };
  }

  /** CAL81 — « aligner » la sélection libre (rangée ou colonne droite) — tout ou rien. */
  function freeAlignSelection(axis: 'row' | 'col', members: readonly number[]): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || members.length < 2) return false;
    recordFreeHistory();
    const res = alignPanels(st, g, members, axis, margins());
    if (!res.ok) {
      dropFreeHistory();
      flashRefusal(members);
      if (layoutNoteEl) layoutNoteEl.textContent = `Alignement refusé — rien n’a bougé.`;
      renderLayoutPanel();
      return false;
    }
    if (layoutNoteEl) layoutNoteEl.textContent = `Aligné — ${fmt(members.length)} panneaux (placement libre).`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** CAL81 — « distribuer » la sélection libre à écart égal — tout ou rien. */
  function freeDistributeSelection(members: readonly number[]): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || members.length < 3) return false;
    recordFreeHistory();
    const res = distributePanels(st, g, members, margins());
    if (!res.ok) {
      dropFreeHistory();
      flashRefusal(members);
      if (layoutNoteEl) layoutNoteEl.textContent = `Distribution refusée — rien n’a bougé.`;
      renderLayoutPanel();
      return false;
    }
    if (layoutNoteEl) layoutNoteEl.textContent = `Distribué — ${fmt(members.length)} panneaux (placement libre).`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /**
   * CALX112 — duplique la sélection libre et colle la copie au DÉCALAGE saisi (mètres, le
   * long de l'axe des rangées `u` — le même axe que la trame N×M des obstacles, CAL73). Un
   * seul pas d'historique pour tout le geste (une photo AVANT, un seul commit ensuite) ;
   * TOUT OU RIEN : si l'image d'UN SEUL membre sortirait du posable ou chevaucherait un
   * module existant (original ou copie déjà validée dans ce même geste), rien n'est copié.
   */
  function dupliquerSelection(members: readonly number[], decalageM: number): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g) return false;
    const src = [...new Set(members)].filter((i) => Number.isInteger(i) && i >= 0 && i < st.panels.length);
    if (!src.length || !Number.isFinite(decalageM) || decalageM === 0) return false;
    recordFreeHistory();
    const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
    const othersCorners = st.panels.map((p) => panelCornersFor(g, p));
    const placed: Vec2[][] = [];
    const startIdx = st.panels.length;
    const news: FreePanel[] = [];
    for (const i of src) {
      const p = st.panels[i];
      const [u, v] = toUV(g, p.cx, p.cy);
      const nu = u + decalageM;
      const angle = p.angleDeg ?? 0;
      const corners = panelCornersUV(g, nu, v, angle);
      const violations = hardViolationsFor(g, ringUV, corners, othersCorners, placed);
      if (violations.length) {
        dropFreeHistory();
        flashRefusal(src);
        if (layoutNoteEl) {
          layoutNoteEl.textContent = `Duplication refusée : ${violations.map(violationLabel).join(', ')} — rien n’a été copié.`;
        }
        renderLayoutPanel();
        return false;
      }
      placed.push(corners);
      const [cx, cy] = toENU(g, nu, v);
      const copy: FreePanel = { cx, cy };
      if (p.angleDeg) copy.angleDeg = p.angleDeg;
      if (p.face) copy.face = p.face;
      news.push(copy);
    }
    st.panels.push(...news);
    setSelection(news.map((_, k) => startIdx + k)); // les COPIES restent sélectionnées
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Dupliqué — ${fmt(news.length)} panneaux copiés à ${fmt1(Math.abs(decalageM))} m (${fmt(st.panels.length)} posés).`;
    }
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** CALX113 — axe de symétrie : une droite ENU définie par deux points DISTINCTS (cliqués,
   *  ou une arête du pan désignée). */
  interface MirrorAxis {
    a: readonly [number, number];
    b: readonly [number, number];
  }

  /**
   * CALX113 — symétrise la sélection libre par rapport à `axis` : le centre ET l'orientation
   * propre de chaque membre sont réfléchis ENSEMBLE (une réflexion est sa propre inverse :
   * symétriser deux fois de suite rend l'état initial). TOUT OU RIEN, refusée seulement sur
   * une contrainte DURE réelle (contour/panneau/obstacle) — jamais un simple écart/retrait
   * relâché, comme la rotation CAL80 dont ce geste reprend exactement le vocabulaire.
   */
  function symetriserSelection(members: readonly number[], axis: MirrorAxis): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || !members.length) return false;
    const src = [...new Set(members)].filter((i) => Number.isInteger(i) && i >= 0 && i < st.panels.length);
    if (!src.length) return false;
    const [au, av] = toUV(g, axis.a[0], axis.a[1]);
    const [bu, bv] = toUV(g, axis.b[0], axis.b[1]);
    const dirU = bu - au;
    const dirV = bv - av;
    const len2 = dirU * dirU + dirV * dirV;
    if (!(len2 > 1e-12)) return false; // deux points confondus : aucun axe défini
    const axisAngleDeg = (Math.atan2(dirV, dirU) * 180) / Math.PI;
    const reflectUV = (u: number, v: number): [number, number] => {
      const pu = u - au;
      const pv = v - av;
      const t = (pu * dirU + pv * dirV) / len2;
      return [au + 2 * t * dirU - pu, av + 2 * t * dirV - pv];
    };
    recordFreeHistory();
    const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
    const othersCorners = st.panels.filter((_, i) => !src.includes(i)).map((p) => panelCornersFor(g, p));
    const placed: Vec2[][] = [];
    const results: { idx: number; cx: number; cy: number; angleDeg: number }[] = [];
    for (const idx of src) {
      const p = st.panels[idx];
      const [pu, pv] = toUV(g, p.cx, p.cy);
      const [nu, nv] = reflectUV(pu, pv);
      const oldAngle = p.angleDeg ?? 0;
      const newAngle = ((2 * axisAngleDeg - oldAngle) % 360 + 360) % 360;
      const corners = panelCornersUV(g, nu, nv, newAngle);
      const violations = hardViolationsFor(g, ringUV, corners, othersCorners, placed);
      if (violations.length) {
        dropFreeHistory();
        flashRefusal(src);
        if (layoutNoteEl) {
          layoutNoteEl.textContent = `Symétrie refusée : ${violations.map(violationLabel).join(', ')} — rien n’a bougé.`;
        }
        renderLayoutPanel();
        return false;
      }
      placed.push(corners);
      const [ncx, ncy] = toENU(g, nu, nv);
      results.push({ idx, cx: ncx, cy: ncy, angleDeg: newAngle });
    }
    // Commit atomique : rien n'a été muté tant que tous les membres n'étaient pas validés.
    for (const r of results) st.panels[r.idx] = { ...st.panels[r.idx], cx: r.cx, cy: r.cy, angleDeg: r.angleDeg };
    if (layoutNoteEl) layoutNoteEl.textContent = `Symétrisé — ${fmt(src.length)} panneaux (placement libre).`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  function snapDeltaToGrid(dx: number, dy: number): { dx: number; dy: number } {
    const grid = ctx.layoutPlan?.grid;
    const stepU = grid && Number.isFinite(grid.rowWidthM) && grid.rowWidthM > 0 ? grid.rowWidthM : 0;
    const stepV = grid && Number.isFinite(grid.rowPitchM) && grid.rowPitchM > 0 ? grid.rowPitchM : 0;
    return {
      dx: stepU > 0 ? Math.round(dx / stepU) * stepU : dx,
      dy: stepV > 0 ? Math.round(dy / stepV) * stepV : dy,
    };
  }

  // PV26 — HISTORIQUE par snapshots : toute action qui MUTE l'occupation appelle d'abord
  // `recordHistory()`. Annuler ré-applique la photo précédente ; une nouvelle action vide
  // la pile « rétablir ».
  const history = createLayoutHistory();
  /** PV27 — une disposition a-t-elle été HYDRATÉE (ou éditée) sur le plan courant ? Si oui,
   *  entrer en mode « Personnaliser » la PRÉSERVE au lieu de repartir de l'optimum. */
  let hydrated = false;
  /** Photographie l'occupation AVANT de la muter (no-op sans état de disposition). */
  function recordHistory() {
    if (ctx.layoutState) history.push(ctx.layoutState.occupied);
    pushWorkshopHistory(); // CAL100 — même geste, historique généralisé EN PARALLÈLE
  }
  // CAL100 — `applySnapshot`/`applyFreeSnapshot` (restauration occupation-seule / état-libre-
  // seul) sont remplacées par `applyWorkshopSnapshot` ci-dessus : `undo()`/`redo()`
  // restaurent désormais TOUJOURS l'atelier ENTIER (dont l'occupation/l'état libre) en un
  // seul geste cohérent — cf. bloc CAL100 plus haut dans ce fichier.
  /** CAL100 — `workshopHistory` est la SEULE source de vérité de la restauration (elle est
   *  TOUJOURS poussée au moins autant que `history`/`freeHistory`, cf. `recordHistory`/
   *  `recordFreeHistory` ci-dessus) : un `undo()` restaure tracé/obstacles/zones/pose ET
   *  l'occupation lattice/l'état libre courants, en un seul geste cohérent. */
  /**
   * CAL235 — retire des modules de la disposition lattice, sur geste EXPLICITE (la
   * proposition d'ombrage ne s'applique jamais d'elle-même). L'atelier est photographié
   * AVANT (recordHistory → workshopHistory), donc Ctrl+Z restaure les modules retirés.
   * Renvoie le nombre réellement retiré ; 0 ⇒ rien n'a bougé.
   */
  function removeCells(indices: readonly number[]): number {
    if (ctx.freeMode) return 0; // placement libre : autre modèle, on ne devine pas
    ensureLayoutState();
    const st = ctx.layoutState;
    if (!st) return 0;
    const cibles = [...new Set(indices)].filter((i) => Number.isInteger(i) && st.occupied.has(i));
    if (!cibles.length) return 0;
    if (cibles.length >= st.occupied.size) return 0; // jamais vider le pan entier
    recordHistory(); // PV26 + CAL100 — annulable comme n'importe quelle édition
    for (const i of cibles) st.occupied.delete(i);
    ctx.layoutSel = null;
    renderCustomLayout();
    return cibles.length;
  }

  function undo(): boolean {
    if (!workshopHistory.canUndo()) return false;
    const prev = workshopHistory.undo(snapshotWorkshop());
    if (!prev) return false;
    applyWorkshopSnapshot(prev);
    renderCustomLayout();
    renderLayoutPanel();
    if (layoutNoteEl) {
      layoutNoteEl.textContent = freeActive()
        ? `Action annulée — ${fmt(ctx.freeState?.panels.length ?? 0)} panneaux posés.`
        : `Action annulée — ${fmt(ctx.layoutState?.occupied.size ?? 0)} panneaux posés.`;
    }
    return true;
  }
  function redo(): boolean {
    if (!workshopHistory.canRedo()) return false;
    const next = workshopHistory.redo(snapshotWorkshop());
    if (!next) return false;
    applyWorkshopSnapshot(next);
    renderCustomLayout();
    renderLayoutPanel();
    if (layoutNoteEl) {
      layoutNoteEl.textContent = freeActive()
        ? `Action rétablie — ${fmt(ctx.freeState?.panels.length ?? 0)} panneaux posés.`
        : `Action rétablie — ${fmt(ctx.layoutState?.occupied.size ?? 0)} panneaux posés.`;
    }
    return true;
  }

  // ═══════════ CAL100 — historique GÉNÉRALISÉ (tracé + obstacles + zones + pose) ═══════════
  // `history`/`freeHistory` ci-dessus ne couvraient que l'occupation de la disposition —
  // supprimer un obstacle ou une zone restait irréversible. `workshopHistory` (même mécanique,
  // `createWorkshopHistory`) photographie TOUT l'atelier — tracé/obstacles/zones/pose ET
  // l'occupation lattice/l'état libre courants — donc elle reste TOUJOURS un sur-ensemble de
  // ce que `history`/`freeHistory` couvrent seules : `undo()`/`redo()` ci-dessous s'appuient
  // désormais sur `workshopHistory` comme SEULE source de vérité (plus de risque de
  // désynchronisation entre deux piles poussées séparément). `history`/`freeHistory` restent
  // poussées pour leurs propres tests unitaires (layoutHistoryPV26/freePlacementPV30) mais ne
  // pilotent plus la restauration. `ctx.pushWorkshopHistory` s'auto-enregistre pour que les
  // modules qui mutent obstacles/tracé (obstaclesUi.ts) rendent, eux aussi, leur geste
  // annulable — AUCUN câblage supplémentaire requis côté entrée : `undo()`/`redo()` sont déjà
  // les fonctions branchées sur Ctrl+Z/Ctrl+Y et les boutons ↶/↷ (plus bas dans ce fichier).
  const workshopHistory = createWorkshopHistory();
  // CAL100 — un `ctx` de test/hôte antérieur peut ne PAS porter vertices/obstacles/areas
  // (fixtures allégées qui ne peuplent que ce dont le mode libre a besoin) : jamais lu en
  // aveugle, même garde que `margins()` pour `freeMargins` un peu plus haut dans ce fichier.
  function snapshotWorkshop(): WorkshopSnapshot {
    return {
      vertices: Array.isArray(ctx.vertices) ? ctx.vertices.map((v) => [v[0], v[1]]) : [],
      obstacles: Array.isArray(ctx.obstacles) ? ctx.obstacles.map((o) => ({ ...o })) : [],
      areas: Array.isArray(ctx.areas)
        ? ctx.areas.map((a) => ({ ...a, vertices: a.vertices.map((v) => [v[0], v[1]]), obstacles: a.obstacles.map((o) => ({ ...o })) }))
        : [],
      roofType: ctx.roofType,
      pitchDeg: ctx.pitchDeg,
      facingAzimuthDeg: ctx.facingAzimuthDeg,
      layoutOccupied: ctx.layoutState ? [...ctx.layoutState.occupied].sort((a, b) => a - b) : undefined,
      freeState: ctx.freeState ? { panels: ctx.freeState.panels.map((p) => ({ ...p })) } : undefined,
    };
  }
  function applyWorkshopSnapshot(s: WorkshopSnapshot) {
    if (Array.isArray(ctx.vertices)) ctx.vertices = s.vertices.map((v) => [v[0], v[1]]);
    if (Array.isArray(ctx.obstacles)) ctx.obstacles = s.obstacles.map((o) => ({ ...o }));
    // `ctx.areas` est `readonly` (référence stable, mutée EN PLACE partout ailleurs) —
    // jamais réassignée, toujours vidée + repeuplée.
    if (Array.isArray(ctx.areas)) {
      ctx.areas.length = 0;
      ctx.areas.push(...s.areas.map((a) => ({ ...a, vertices: a.vertices.map((v) => [v[0], v[1]] as LngLat), obstacles: a.obstacles.map((o) => ({ ...o })) })));
    }
    ctx.roofType = s.roofType;
    ctx.pitchDeg = s.pitchDeg;
    ctx.facingAzimuthDeg = s.facingAzimuthDeg;
    if (s.layoutOccupied && ctx.layoutState) {
      ctx.layoutState.occupied = new Set(s.layoutOccupied.filter((i) => i >= 0 && i < ctx.layoutState!.cells.length));
    }
    if (s.freeState) ctx.freeState = { panels: s.freeState.panels.map((p) => ({ ...p })) };
    ctx.layoutSel = null;
    pruneSelection();
  }
  /** Photographie TOUT l'atelier AVANT une mutation — à appeler par n'importe quel module
   *  (via `ctx.pushWorkshopHistory`) juste avant de retirer/ajouter/déplacer un obstacle,
   *  éditer le tracé, ou changer la pose du pan actif. */
  function pushWorkshopHistory() {
    workshopHistory.push(snapshotWorkshop());
  }
  ctx.pushWorkshopHistory = pushWorkshopHistory; // auto-enregistrement — cf. commentaire ci-dessus

  function layoutCap(): number {
    const fit = ctx.layoutPlan ? ctx.layoutPlan.grid.panels.length : 0;
    // Le besoin plafonne aussi (taille-au-besoin) : on autorise jusqu'au max(besoin, fit
    // optimal) mais jamais au-delà de ce qui tient — la lattice borne déjà tout.
    return fit;
  }

  /** (Re)crée l'état de disposition depuis le plan gagnant courant (toutes cellules
   *  valides occupées jusqu'au comptage optimal). */
  function ensureLayoutState() {
    if (!ctx.layoutPlan) {
      ctx.layoutState = null;
      return;
    }
    if (!ctx.layoutState) {
      ctx.layoutState = createLayoutState(ctx.layoutPlan.grid.panels, ctx.layoutOptimalCount);
      ctx.layoutSel = null;
    }
  }

  /**
   * PV31 — re-rendu 3D SEUL du placement libre (grille SYNTHÉTIQUE dont les panneaux sont
   * les positions libres : même chemin de rendu, mêmes matériaux, même mapping
   * instance→index, donc le surlignage de sélection marche à l'identique). Séparé de
   * `renderCustomLayout` parce que l'APERÇU VIVANT d'un glissé le rappelle à chaque image :
   * un déplacement ne change NI le nombre de panneaux NI la production, il serait donc
   * absurde (et lent) de recalculer la fenêtre de production 60 fois par seconde.
   */
  function renderFreeScene() {
    if (!ctx.layoutPlan || !ctx.freeState) return;
    const st = ctx.freeState;
    const grid = { ...ctx.layoutPlan.grid, panels: st.panels.map((p) => ({ ...p })), count: st.panels.length };
    const all = new Set(st.panels.map((_, i) => i));
    renderScene(ctx.layoutPlan.pack, grid, ctx.layoutPlan.tiltDeg, ctx.layoutPlan.family, st.panels.length, ctx.layoutPlan.flush, all);
    // Re-rendre la scène reconstruit les instances (teintes remises à blanc) : on REPEINT
    // la sélection juste après, sinon elle disparaîtrait à chaque image de l'aperçu.
    paintScene();
  }

  /** Re-rend la 3D avec l'occupation PERSONNALISÉE courante (même plan, même rendement
   *  par panneau ; seul le NOMBRE change), puis recompute la production/économies par le
   *  chemin PVGIS-par-comptage existant (la fenêtre de production suit prodPanels). */
  function renderCustomLayout() {
    if (!ctx.layoutPlan) return;
    // PV30 — en placement LIBRE, la 3D est rendue avec une grille SYNTHÉTIQUE dont les
    // panneaux sont les positions libres : même chemin de rendu, mêmes matériaux, même
    // mapping instance→index (donc le surlignage de sélection marche à l'identique). Le
    // rendement par panneau ne change pas — seul le NOMBRE pilote la production, comme
    // en mode lattice.
    if (freeActive()) {
      const st = ctx.freeState!;
      renderFreeScene();
      const cfgFree = prodConfigFromState();
      if (cfgFree) updateProductionWindow({ ...cfgFree, panels: st.panels.length });
      snapshotActiveAreaResult();
      renderAreasPanel();
      paintScene(); // PV29 — la sélection se repeint EN DERNIER (ordre historique préservé)
      return;
    }
    if (!ctx.layoutState) return;
    const occ = new Set(ctx.layoutState.occupied);
    renderScene(ctx.layoutPlan.pack, ctx.layoutPlan.grid, ctx.layoutPlan.tiltDeg, ctx.layoutPlan.family, occ.size, ctx.layoutPlan.flush, occ);
    // Recompute par COMPTAGE (jamais un rendement inventé) : on met prodPanels au nombre
    // posé et on laisse la fenêtre de production rescaler en kWc (linéaire) côté client.
    const count = occ.size;
    const cfg = prodConfigFromState();
    if (cfg) updateProductionWindow({ ...cfg, panels: count });
    // « Plusieurs zones » — garde l'instantané + le total à jour après chaque édition de
    // disposition (le résultat de zone suit le gagnant vivant, hook partagé).
    snapshotActiveAreaResult();
    renderAreasPanel();
    // PV29 — re-rendre la scène reconstruit les instances (teintes remises à blanc) : on
    // REPEINT la sélection juste après, sinon elle disparaîtrait à chaque déplacement.
    paintScene();
  }

  /** Convertit un point ÉCRAN (carte) en coordonnées ENU relatives à l'origine de la
   *  scène — c'est le « raycast sur le plan du toit » : on déprojette en lng/lat puis on
   *  passe en mètres locaux (même repère que PackedPanel.cx/cy). */
  function screenToENU(point: maplibregl.Point): { x: number; y: number } | null {
    if (!ctx.layoutPlan) return null;
    const ll = map.unproject(point);
    const origin = ctx.layoutPlan.pack.origin;
    const cosLat = Math.cos(origin[1] * DEG2RAD);
    return { x: (ll.lng - origin[0]) * DEG2M * cosLat, y: (ll.lat - origin[1]) * DEG2M };
  }

  /** Rendu du plan tactile des emplacements (cellules occupées/libres) + synthèse. */
  function renderLayoutPanel() {
    if (!layoutWindowEl) return;
    const ready = !!ctx.layoutPlan && ctx.layoutPlan.grid.panels.length > 0 && ctx.closed;
    layoutWindowEl.hidden = !ready;
    if (!ready) return;
    if (!ctx.layoutMode) return;
    ensureLayoutState();
    const layoutState = ctx.layoutState;
    if (!layoutState) return;

    // PV30 — en placement libre, les chiffres viennent des panneaux RÉELLEMENT posés (il
    // n'y a plus d'« emplacements libres » : le toit entier est disponible sous contrainte).
    const freeOn = freeActive();
    const count = freeOn ? ctx.freeState!.panels.length : occupiedCount(layoutState);
    const free = freeOn ? 0 : emptyIndices(layoutState).length;
    const kwc = count * PANEL_KWC;
    if (layoutCountEl) layoutCountEl.textContent = fmt(count);
    if (layoutKwcEl) layoutKwcEl.textContent = `${fmt1(kwc)} kWc`;
    if (layoutFreeEl) layoutFreeEl.textContent = fmt(free);
    const cover = ctx.neededPanels > 0 ? Math.round((count / ctx.neededPanels) * 100) : 0;
    if (layoutCoverEl) layoutCoverEl.textContent = ctx.neededPanels > 0 ? `${cover} %` : '—';
    if (layoutMinusEl) layoutMinusEl.disabled = count <= 0;
    // PV30 — en libre, « + » n'est jamais bloqué par un stock de cellules : c'est la
    // géométrie qui refusera (ou non) la pose, au moment de la pose.
    if (layoutPlusEl) layoutPlusEl.disabled = freeOn ? false : free <= 0 || count >= layoutCap();
    // WJ20 — « Remplir » n'a de sens que s'il reste des cellules libres.
    if (layoutFillEl) layoutFillEl.disabled = freeOn ? true : free <= 0;

    // Mini-plan des cellules : occupées (bleu) / libres (gris→vert au survol). PV30 — le
    // mini-plan DÉCRIT la lattice ; en placement libre il n'y a plus de cellules à montrer,
    // on le vide plutôt que d'afficher une grille qui ne gouverne plus rien.
    if (layoutGridEl && freeOn) {
      layoutGridEl.innerHTML = '';
    } else if (layoutGridEl) {
      layoutGridEl.innerHTML = layoutState.cells
        .map((c) => {
          const occupied = layoutState.occupied.has(c.index);
          // PV25 — une cellule est « pressée » si elle est le panneau saisi OU membre de
          // la sélection multiple (le même signal visuel pour les deux).
          const selected = ctx.layoutSel === c.index || selection.includes(c.index);
          return `<button type="button" class="rp9-layout-cell" data-cell="${c.index}" data-occupied="${occupied}" aria-pressed="${selected}" aria-label="${occupied ? 'Panneau' : 'Emplacement libre'} ${c.index + 1}"></button>`;
        })
        .join('');
    }
    pruneSelection();
    syncSelectionControls();
    syncFreeInputs(); // PV30
    if (layoutNoteEl && !layoutNoteEl.textContent) {
      // PV34 — l'aide dit d'abord le geste SANS modificateur (glisser sur le toit pour
      // encadrer), puis les raccourcis. C'est l'ordre dans lequel on les découvre.
      layoutNoteEl.textContent = freeOn
        ? 'Placement libre : glissez sur le toit (à côté des panneaux) pour ENCADRER un groupe ou une rangée ; double-clic sur un panneau = toute sa rangée ; Ctrl (⌘) + clic ajoute ou retire un panneau ; Maj + glissé ajoute un cadre au groupe. Glissez ensuite n’importe quel panneau sélectionné : tout le groupe suit le curseur. Flèches pour ajuster au centimètre, Échap pour lâcher, Alt + clic pour retirer. « Ajouter un panneau » puis un clic pose un panneau de plus.'
        : 'Sur la 3D : glissez sur le toit (à côté des panneaux) pour ENCADRER un groupe ou une rangée ; double-clic sur un panneau = toute sa rangée ; Ctrl (⌘) + clic ajoute ou retire un panneau ; Maj + glissé ajoute un cadre au groupe. Glissez ensuite n’importe quel panneau sélectionné : tout le groupe suit. Flèches pour ajuster, Échap pour lâcher, Alt + clic pour retirer. Ou touchez un panneau (bleu) puis un emplacement libre (vert) dans le plan ci-dessous.';
    }
  }

  /** PV25 — la sélection ne garde que des cellules RÉELLEMENT occupées (un panneau
   *  supprimé/déplacé ailleurs ne doit pas rester « sélectionné »). */
  function pruneSelection() {
    // PV30 — en placement libre, la sélection indexe la LISTE des panneaux libres : reste
    // valide tout index encore dans la liste (un panneau retiré disparaît de la sélection).
    if (ctx.freeMode) {
      const n = ctx.freeState ? ctx.freeState.panels.length : 0;
      selection = selection.filter((i) => Number.isInteger(i) && i >= 0 && i < n).sort((a, b) => a - b);
      return;
    }
    const st = ctx.layoutState;
    if (!st) {
      selection = [];
      return;
    }
    selection = selection.filter((i) => st.occupied.has(i)).sort((a, b) => a - b);
  }
  function setSelection(indices: readonly number[]) {
    selection = [...new Set(indices)];
    pruneSelection();
    paintScene(); // PV29 — la sélection est VISIBLE sur la 3D, pas seulement dans le mini-plan
  }

  /** PV29 — SÉLECTION D'UNE RANGÉE ENTIÈRE en un seul geste (double-clic sur un panneau).
   *  Rien à activer au préalable : c'est le geste « rangée » sans mode à retenir. */
  function selectRow(cellIndex: number): number[] {
    // PV30 — en libre, la « rangée » est géométrique (même coordonnée d'empilement).
    const members = freeActive() ? freeRowMembers(cellIndex) : ctx.layoutState ? rowMembers(ctx.layoutState, cellIndex) : [];
    if (!members.length) return [];
    setSelection(members);
    ctx.layoutSel = null;
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Rangée sélectionnée — ${fmt(members.length)} panneaux. Glissez-en un pour déplacer toute la rangée, ou utilisez les flèches.`;
    }
    renderLayoutPanel();
    return members;
  }

  /** PV29 — sélection d'UN SEUL panneau (clic simple), ou BASCULE de ce panneau dans la
   *  sélection courante (Maj + clic) : les deux gestes standard d'un éditeur. */
  function selectSinglePanel(cellIndex: number, toggle = false) {
    if (freeActive()) {
      const n = ctx.freeState!.panels.length;
      if (!Number.isInteger(cellIndex) || cellIndex < 0 || cellIndex >= n) return;
    } else {
      const st = ctx.layoutState;
      if (!st || !st.occupied.has(cellIndex)) return;
    }
    if (toggle) {
      // PV34 — la bascule passe par la primitive PURE (dédoublonnée + triée) : Maj + clic
      // et Ctrl/⌘ + clic partagent exactement la même règle.
      setSelection(applySelectionGesture(selection, [cellIndex], 'toggle'));
      if (layoutNoteEl) {
        layoutNoteEl.textContent = selection.length
          ? `${fmt(selection.length)} panneaux sélectionnés — glissez-en un pour déplacer tout le groupe.`
          : 'Sélection vide.';
      }
    } else {
      setSelection([cellIndex]);
      ctx.layoutSel = cellIndex;
      if (layoutNoteEl) {
        layoutNoteEl.textContent =
          'Panneau sélectionné — glissez-le pour le déplacer, flèches pour l’ajuster, double-clic pour prendre toute la rangée.';
      }
    }
    renderLayoutPanel();
  }

  /** PV25 — reflète l'état des boutons de sélection + le nudge d'azimut. */
  function syncSelectionControls() {
    if (layoutSelectBtn) layoutSelectBtn.setAttribute('aria-pressed', String(selectMode));
    if (layoutRowBtn) layoutRowBtn.setAttribute('aria-pressed', String(rowMode));
    if (layoutClearSelBtn) layoutClearSelBtn.disabled = selection.length === 0;
    // PV34 — compteur PERMANENT : combien de panneaux on tient, à tout instant. Le
    // `data-*` est le repère stable (e2e) ; le texte reste la version lisible.
    if (layoutSelCountEl) {
      const n = selection.length;
      layoutSelCountEl.setAttribute('data-rp9-selcount', String(n));
      layoutSelCountEl.textContent =
        n === 0 ? 'Aucun panneau sélectionné' : n === 1 ? '1 panneau sélectionné' : `${fmt(n)} panneaux sélectionnés`;
    }
    // CAL100 — `workshopHistory` pilote désormais `undo()`/`redo()` (sur-ensemble de
    // `history`/`freeHistory` — cf. bloc CAL100).
    if (layoutUndoBtn) layoutUndoBtn.disabled = !workshopHistory.canUndo();
    if (layoutRedoBtn) layoutRedoBtn.disabled = !workshopHistory.canRedo();
    // L'azimut n'est nudgeable que sur un toit en PENTE (face imposée par la toiture) ;
    // sur toit plat, l'azimut est un AXE de l'optimiseur, pas un réglage de disposition.
    if (layoutAzWrapEl) layoutAzWrapEl.hidden = ctx.roofType !== 'pitched';
    if (layoutAzValueEl) layoutAzValueEl.textContent = `${Math.round(ctx.facingAzimuthDeg)}°`;
  }

  // ── PV30 — BASCULE DE MODE ────────────────────────────────────────────────────
  /**
   * Passe en PLACEMENT LIBRE. Les panneaux posés gardent EXACTEMENT leur position : on ne
   * fait que changer la règle qui les gouverne (cellules validées → contrôles géométriques
   * réels). C'est pour ça que la bascule est sans risque et sans question.
   */
  function enterFreeMode(): boolean {
    if (!ctx.layoutPlan) return false;
    const g = freeGeom();
    if (!g) {
      if (layoutNoteEl) layoutNoteEl.textContent = 'Placement libre indisponible : ce toit n’a pas encore de calepinage.';
      return false;
    }
    ensureLayoutState();
    if (!ctx.freeState) {
      const st = ctx.layoutState;
      const centers = st ? [...st.occupied].sort((a, b) => a - b).map((i) => ({ ...st.cells[i] })) : [];
      ctx.freeState = freeStateFromCenters(centers.map((c) => ({ cx: c.cx, cy: c.cy, ...(c.face ? { face: c.face } : {}) })));
    }
    ctx.freeMode = true;
    freeHistory.clear();
    setSelection([]);
    ctx.layoutSel = null;
    syncFreeInputs();
    if (layoutNoteEl) {
      layoutNoteEl.textContent =
        'Placement libre : les panneaux se déplacent au millimètre. Seuls le contour du toit, les chevauchements et les obstacles sont interdits — le retrait de rive et l’écart entre panneaux sont réglables ci-dessus.';
    }
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /**
   * Retour au mode LATTICE. Les positions libres n'existent pas sur la lattice : on
   * re-snappe chaque panneau sur la cellule valide la plus proche, ce qui PERD le gain de
   * place obtenu à la main. On DEMANDE donc avant — même garde-fou que PV28, jamais un
   * effacement silencieux.
   */
  function exitFreeMode(ask = true): boolean {
    if (!ctx.freeMode) return true;
    const st = ctx.freeState;
    if (ask && st && st.panels.length) {
      const confirmFn =
        deps.confirmDiscard ??
        ((msg: string) => (typeof window !== 'undefined' && typeof window.confirm === 'function' ? window.confirm(msg) : true));
      const ok = confirmFn(
        `Revenir au mode « emplacements validés » va replacer vos ${st.panels.length} panneaux sur les emplacements calculés : les marges que vous avez réduites seront perdues. Continuer ?`,
      );
      if (!ok) {
        if (layoutNoteEl) layoutNoteEl.textContent = 'Retour annulé — votre placement libre est conservé.';
        return false;
      }
    }
    ctx.freeMode = false;
    // Re-snap : chaque position libre reprend la cellule VIDE valide la plus proche.
    ensureLayoutState();
    const lat = ctx.layoutState;
    if (lat && st) {
      lat.occupied.clear();
      // CAL106 — re-snap en masse INDEXÉ (même résultat, coût du voisinage au
      // lieu de la lattice entière ; l'équivalence est testée).
      for (const idx of resnapEnMasse(lat.cells, st.panels)) lat.occupied.add(idx);
    }
    ctx.freeState = null;
    freeHistory.clear();
    setSelection([]);
    ctx.layoutSel = null;
    syncFreeInputs();
    if (layoutNoteEl && lat) {
      layoutNoteEl.textContent = `Mode emplacements validés — ${fmt(lat.occupied.size)} panneaux replacés sur la grille de l’étude.`;
    }
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }

  /** Reflète l'état des contrôles de mode + les champs de marges. */
  function syncFreeInputs() {
    const on = !!ctx.freeMode;
    if (modeLatticeBtn) modeLatticeBtn.setAttribute('aria-pressed', String(!on));
    if (modeFreeBtn) modeFreeBtn.setAttribute('aria-pressed', String(on));
    if (freeControlsEl) freeControlsEl.hidden = !on;
    if (freeAddBtn) freeAddBtn.setAttribute('aria-pressed', String(freeAddArmed));
    // Les champs sont en CENTIMÈTRES (l'unité dans laquelle un poseur raisonne) ; on ne
    // réécrit pas la valeur pendant que l'utilisateur tape (sinon le curseur saute).
    if (freeSetbackEl && document.activeElement !== freeSetbackEl) {
      freeSetbackEl.value = String(Math.round(margins().setbackM * 100));
    }
    if (freeGapEl && document.activeElement !== freeGapEl) {
      freeGapEl.value = String(Math.round(margins().gapM * 100));
    }
    // CALX112 — « Dupliquer » reste INACTIF tant qu'aucun pas > 0 n'est saisi.
    if (freeDupBtn) {
      const raw = (freeDupStepEl?.value ?? '').toString().trim().replace(',', '.');
      const step = raw ? Number(raw) : NaN;
      freeDupBtn.disabled = !on || !Number.isFinite(step) || step <= 0;
    }
    if (freeMirrorBtn) freeMirrorBtn.setAttribute('aria-pressed', String(mirrorArmed));
  }

  /** Lit un champ de marge (cm → m). Règle fondateur : on n'IMPOSE aucun arrondi et on ne
   *  REJETTE aucune saisie — une valeur illisible laisse simplement la marge inchangée. */
  function readMarginCm(el: HTMLInputElement | null, current: number): number {
    if (!el) return current;
    const raw = (el.value ?? '').toString().trim().replace(',', '.');
    if (raw === '') return current;
    const v = Number(raw);
    if (!Number.isFinite(v) || v < 0) return current;
    return v / 100;
  }

  /** Applique les marges saisies. Les BAISSER est permis — c'est tout l'objet du mode ;
   *  ce qui compte, c'est que les distances réelles restent AFFICHÉES. */
  function applyMargins() {
    const before = margins();
    const next = {
      setbackM: readMarginCm(freeSetbackEl, before.setbackM),
      gapM: readMarginCm(freeGapEl, before.gapM),
    };
    if (next.setbackM === before.setbackM && next.gapM === before.gapM) return;
    // Un changement de marge est une action ANNULABLE comme une autre (elle change ce que
    // les gestes suivants accepteront) — on photographie l'état pour ne pas casser la
    // chronologie de « annuler ».
    recordFreeHistory();
    ctx.freeMargins = next;
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Marges : retrait de rive ${cm(next.setbackM)}, écart entre panneaux ${cm(next.gapM)}. Les panneaux déjà posés ne bougent pas ; ces valeurs s’appliquent aux prochains gestes.`;
    }
    renderLayoutPanel();
  }

  /** PV25 — recalcul complet après un changement d'azimut : re-pavage PUIS re-snap de la
   *  disposition personnalisée (le chemin `recalc()` de l'entrée), sinon repli renderActive. */
  function recalcAfterAxisChange() {
    if (deps.recalcWithReenter) deps.recalcWithReenter();
    else renderActive();
  }

  /** W79 — centres ENU des cellules POSÉES de la disposition courante. Capturé AVANT un
   *  recalc (qui va remplacer la lattice et nuller layoutState) pour pouvoir re-snapper la
   *  même intention de placement sur la nouvelle lattice. [] si pas de disposition. */
  function occupiedCenters(): { cx: number; cy: number }[] {
    // PV30 — en libre, les « centres posés » SONT les positions libres, telles quelles.
    if (freeActive()) return ctx.freeState!.panels.map((p) => ({ cx: p.cx, cy: p.cy }));
    const st = ctx.layoutState;
    if (!st) return [];
    const out: { cx: number; cy: number }[] = [];
    for (const c of st.cells) if (st.occupied.has(c.index)) out.push({ cx: c.cx, cy: c.cy });
    return out;
  }

  /** W79 — re-entre la disposition PERSONNALISÉE après un recalc (édition/ajout/suppression
   *  d'obstacle ou changement d'axe pendant que l'éditeur est ouvert). Le recalc a re-pavé
   *  le toit (nouvelle lattice via renderScene → layoutState nullé) ; sans cela les panneaux
   *  posés à la main retomberaient silencieusement sur l'optimum et les readouts se
   *  périmeraient. On reconstruit l'état sur la NOUVELLE lattice puis on re-snappe CHAQUE
   *  centre précédemment posé vers la cellule VIDE valide la plus proche (nearestEmptyCell) —
   *  les panneaux survivent (re-snappés, jamais effacés). Si un centre n'a plus de cellule
   *  valide proche (toit rétréci), le panneau est simplement perdu (honnête : moins de place).
   *  Puis on re-rend panneaux/grille/note. No-op hors mode disposition ou sans plan. */
  function reenterCustomLayout(prevCenters: { cx: number; cy: number }[]) {
    if (!ctx.layoutMode || !ctx.layoutPlan) return;
    // PV30 — en placement LIBRE, les positions sont absolues : un re-pavage ne les
    // concerne pas. On les garde telles quelles (aucun re-snap) et on re-rend.
    if (freeActive()) {
      if (layoutNoteEl) {
        layoutNoteEl.textContent = `Placement libre conservé — ${fmt(ctx.freeState!.panels.length)} panneaux inchangés.`;
      }
      renderCustomLayout();
      renderLayoutPanel();
      return;
    }
    // Reconstruit une lattice fraîche depuis le plan re-pavé, PUIS remplace l'occupation
    // par les re-snaps (chaque centre → cellule vide valide la plus proche, sans doublon).
    ensureLayoutState();
    const st = ctx.layoutState;
    if (!st) return;
    st.occupied.clear();
    // CAL106 — re-snap en masse INDEXÉ (équivalence stricte testée).
    for (const idx of resnapEnMasse(st.cells, prevCenters)) st.occupied.add(idx);
    ctx.layoutSel = null;
    if (layoutNoteEl) {
      layoutNoteEl.textContent = `Disposition personnalisée conservée — ${occupiedCount(st)} panneaux re-positionnés après la modification.`;
    }
    renderCustomLayout();
    renderLayoutPanel();
  }

  /**
   * PV27 — HYDRATATION de la disposition depuis un layout exporté. C'était le troisième
   * chemin par lequel une pose manuelle disparaissait : le JSON portait les panneaux, mais
   * personne ne les REPOSAIT au boot — l'outil réaffichait l'optimum. On re-snappe ici
   * chaque centre exporté sur la cellule VALIDE la plus proche (même mécanique que
   * `reenterCustomLayout` après un recalcul), puis on rend la 3D avec cette occupation.
   *
   * `origin` = le repère ENU dans lequel les centres ont été enregistrés. S'il diffère du
   * repère du pavage courant (centroïde légèrement différent), on translate d'abord — sans
   * ça, tout le champ serait décalé de quelques mètres.
   */
  function hydrateLayout(
    centers: readonly { cx: number; cy: number }[],
    origin?: readonly [number, number],
    mode?: 'lattice' | 'free',
  ): boolean {
    if (!centers.length || !ctx.layoutPlan) return false;
    ensureLayoutState();
    const st = ctx.layoutState;
    if (!st || !st.cells.length) return false;
    let dx = 0;
    let dy = 0;
    if (origin) {
      const cur = ctx.layoutPlan.pack.origin;
      const cosLat = Math.cos(cur[1] * DEG2RAD);
      dx = (origin[0] - cur[0]) * DEG2M * cosLat;
      dy = (origin[1] - cur[1]) * DEG2M;
    }
    // PV30 — un dossier enregistré en PLACEMENT LIBRE se recharge VERBATIM : re-snapper ses
    // positions sur la lattice détruirait exactement le gain de place qu'il enregistrait.
    if (mode === 'free') {
      ctx.freeState = freeStateFromCenters(centers.map((c) => ({ cx: c.cx + dx, cy: c.cy + dy })));
      ctx.freeMode = true;
      ctx.layoutSel = null;
      setSelection([]);
      freeHistory.clear();
      hydrated = true;
      syncFreeInputs();
      renderCustomLayout();
      renderLayoutPanel();
      if (layoutNoteEl) {
        layoutNoteEl.textContent = `Placement libre du dossier rechargé — ${fmt(centers.length)} panneaux reposés à l'identique.`;
      }
      return true;
    }
    st.occupied.clear();
    // CAL106 — re-snap en masse INDEXÉ (équivalence stricte testée).
    const reposes = resnapEnMasse(
      st.cells,
      centers.map((c) => ({ cx: c.cx + dx, cy: c.cy + dy })),
    );
    for (const idx of reposes) st.occupied.add(idx);
    const placed = reposes.length;
    ctx.layoutSel = null;
    setSelection([]);
    history.clear(); // une hydratation est un POINT DE DÉPART, pas une action annulable
    workshopHistory.clear(); // CAL100 — idem pour l'historique généralisé
    hydrated = true; // PV27 — entrer en mode disposition ne doit plus l'écraser
    renderCustomLayout();
    renderLayoutPanel();
    if (layoutNoteEl && placed) {
      layoutNoteEl.textContent = `Disposition du dossier rechargée — ${fmt(placed)} panneaux reposés à l'identique.`;
    }
    return placed > 0;
  }

  // ── PV28 — garde-fou « ne perds pas le travail manuel » ─────────────────────
  /** La disposition posée diverge-t-elle de l'optimum ? (ajout, retrait ou déplacement). */
  function hasManualEdits(): boolean {
    // PV30 — un placement LIBRE est par définition un travail manuel : il n'existe aucun
    // « optimum » auquel le comparer, donc tout ré-agencement automatique le détruirait.
    if (freeActive() && ctx.freeState!.panels.length) return true;
    return hasManualEditsPure(ctx.layoutState, ctx.layoutOptimalCount);
  }
  /**
   * PV28 — À appeler AVANT un ré-agencement automatique (changement d'axe, optimum,
   * réinitialisation des verrous…). Sans édition manuelle : rien ne se passe, on continue.
   * Avec édition manuelle : on DEMANDE, en français, et un refus laisse l'état INTACT
   * (l'appelant abandonne son action). On ne verrouille aucun panneau : on prévient.
   */
  function confirmDiscardEdits(): boolean {
    if (!hasManualEdits()) return true;
    const count = ctx.layoutState ? ctx.layoutState.occupied.size : 0;
    const ask =
      deps.confirmDiscard ??
      ((msg: string) => (typeof window !== 'undefined' && typeof window.confirm === 'function' ? window.confirm(msg) : true));
    const ok = ask(
      `Vous avez placé ${count} panneaux à la main. Cette action recalcule la disposition et remplacera votre placement. Continuer ?`,
    );
    if (!ok && layoutNoteEl) layoutNoteEl.textContent = 'Modification annulée — votre disposition est conservée.';
    return ok;
  }

  /** Entrée/sortie du mode personnalisation. */
  function setLayoutMode(on: boolean) {
    ctx.layoutMode = on;
    if (layoutToggleEl) layoutToggleEl.setAttribute('aria-pressed', String(on));
    if (layoutPanelEl) layoutPanelEl.hidden = !on;
    // Vue de DESSUS pendant le déplacement : à plat (pitch 0), la déprojection écran→toit est
    // exacte (aucune parallaxe de hauteur), donc glisser un panneau sur la 3D « accroche »
    // vraiment au bon panneau. On restaure la vue inclinée en sortant.
    const view = on ? { pitch: 0 } : { pitch: PITCH_VIEW };
    if (opts.reducedMotion) map.jumpTo(view);
    else map.easeTo({ ...view, duration: 500, essential: true });
    if (on) {
      // PV27 — on PRÉSERVE une disposition déjà posée (hydratée depuis un dossier, ou
      // éditée à la main juste avant) : la remettre à l'optimum ici effaçait le travail
      // manuel dès qu'on rouvrait le panneau. Repartir de l'optimum reste possible — c'est
      // le bouton « Réinitialiser la disposition optimale », explicite.
      if (!ctx.layoutState) ensureLayoutState();
      if (!hydrated) {
        history.clear(); // PV26 — historique propre pour une nouvelle session
        workshopHistory.clear(); // CAL100 — idem pour l'historique généralisé
      }
      setSelection([]);
      renderCustomLayout();
    } else {
      // En sortant, on re-rend la disposition de l'optimiseur (recalc rebranche tout).
      ctx.layoutSel = null;
      setSelection([]); // PV29 — une sélection ne survit pas à la sortie du mode
      setPanelHighlight(null); // W88 — efface tout surlignage de panneau en quittant le mode
      hideMarquee(); // PV31 — jamais un cadre orphelin après la sortie du mode disposition
      marquee = null;
      hideLasso(); // CALX116 — idem pour un lasso orphelin
      lasso = null;
      emptyPress = null;
      if (ctx.closed) renderActive();
    }
    renderLayoutPanel();
  }

  // ═══════════ W69 — câblage « Personnaliser la disposition » ═══════════
  layoutToggleEl?.addEventListener('click', () => setLayoutMode(!ctx.layoutMode));

  // + / − : ajoute/retire un panneau (touch + mouvement réduit, sans glissé fin).
  layoutPlusEl?.addEventListener('click', () => {
    if (!ctx.layoutMode || !ctx.layoutState) return;
    // PV30 — en libre, « + » pose un panneau au PREMIER endroit qui satisfait réellement
    // toutes les contraintes (jamais une position devinée) ; s'il n'y en a aucun aux marges
    // courantes, on le dit et on rappelle que les marges sont réglables.
    if (freeActive()) {
      const st = ctx.freeState!;
      const g = freeGeom();
      const spot = g ? findFreeSpot(st, g, margins()) : null;
      if (!spot) {
        if (layoutNoteEl) {
          layoutNoteEl.textContent =
            'Aucune place pour un panneau de plus avec ces marges. Réduisez le retrait de rive ou l’écart entre panneaux, ou posez-le à la main avec « Ajouter un panneau ».';
        }
        renderLayoutPanel();
        return;
      }
      freeAddAt(spot.cx, spot.cy);
      return;
    }
    recordHistory(); // PV26
    const r = addFirstEmpty(ctx.layoutState, layoutCap());
    if (r.ok) {
      if (layoutNoteEl) layoutNoteEl.textContent = `Panneau ajouté — ${r.count} posés.`;
      renderCustomLayout();
      renderLayoutPanel();
    } else if (layoutNoteEl) {
      layoutNoteEl.textContent = 'Plus d’emplacement valide disponible sur ce toit.';
    }
  });
  layoutMinusEl?.addEventListener('click', () => {
    if (!ctx.layoutMode || !ctx.layoutState) return;
    // PV30 — en libre, « − » retire le panneau SÉLECTIONNÉ, sinon le dernier posé.
    if (freeActive()) {
      const st = ctx.freeState!;
      if (!st.panels.length) return;
      freeRemoveAt(selection.length ? selection[selection.length - 1] : st.panels.length - 1);
      return;
    }
    recordHistory(); // PV26
    const r = removeLast(ctx.layoutState);
    if (r.ok) {
      ctx.layoutSel = null;
      if (layoutNoteEl) {
        layoutNoteEl.textContent = ctx.neededPanels > 0 && r.count < ctx.neededPanels
          ? `Panneau retiré — ${r.count} posés. La disposition ne couvre plus tout le besoin (${fmt(ctx.neededPanels)}).`
          : `Panneau retiré — ${r.count} posés.`;
      }
      renderCustomLayout();
      renderLayoutPanel();
    }
  });
  // WJ20 — « Remplir automatiquement » : un seul geste pose un panneau sur CHAQUE
  // emplacement valide de la lattice (toit entier, retraits + obstacles déjà exclus).
  // Remplace le placement manuel panneau-par-panneau. La couverture peut dépasser le
  // besoin : la note l'indique honnêtement (surproduction non rémunérée).
  layoutFillEl?.addEventListener('click', () => {
    if (!ctx.layoutMode || !ctx.layoutState) return;
    recordHistory(); // PV26
    const r = fillAll(ctx.layoutState);
    ctx.layoutSel = null;
    if (layoutNoteEl) {
      const overNeed = ctx.neededPanels > 0 && r.count > ctx.neededPanels;
      layoutNoteEl.textContent = overNeed
        ? `Toit rempli automatiquement — ${fmt(r.count)} panneaux (le maximum qui tient). C’est plus que votre besoin (${fmt(ctx.neededPanels)}) : le surplus produit n’est pas rémunéré. Retirez-en avec « − » pour coller au besoin.`
        : `Toit rempli automatiquement — ${fmt(r.count)} panneaux (le maximum qui tient sur ce toit).`;
    }
    renderCustomLayout();
    renderLayoutPanel();
  });
  // Réinitialiser la disposition optimale.
  layoutResetEl?.addEventListener('click', () => {
    if (!ctx.layoutState) return;
    recordHistory(); // PV26 — « réinitialiser » s'annule comme n'importe quelle action
    hydrated = false; // PV27 — retour explicite à l'optimum : plus rien à préserver
    resetToOptimal(ctx.layoutState, ctx.layoutOptimalCount);
    ctx.layoutSel = null;
    if (layoutNoteEl) layoutNoteEl.textContent = `Disposition optimale restaurée — ${occupiedCount(ctx.layoutState)} panneaux.`;
    renderCustomLayout();
    renderLayoutPanel();
  });

  // PV25 — bascule « sélection multiple » (repli TACTILE du Maj + glissé) : au doigt, le
  // glissé trace le rectangle de sélection tant que le mode est actif.
  layoutSelectBtn?.addEventListener('click', () => {
    selectMode = !selectMode;
    if (selectMode) rowMode = false; // les deux modes de glissé s'excluent
    if (layoutNoteEl) {
      layoutNoteEl.textContent = selectMode
        ? 'Mode sélection : glissez sur le toit pour encadrer des panneaux.'
        : 'Mode sélection désactivé.';
    }
    renderLayoutPanel();
  });
  // PV25 — bascule « déplacer la rangée » : un glissé emmène toute la rangée du panneau
  // saisi, contrainte à son axe (elle reste une rangée).
  layoutRowBtn?.addEventListener('click', () => {
    rowMode = !rowMode;
    if (rowMode) selectMode = false;
    if (layoutNoteEl) {
      layoutNoteEl.textContent = rowMode
        ? 'Mode rangée : glissez un panneau, toute sa rangée suit (le long de la rangée).'
        : 'Mode rangée désactivé.';
    }
    renderLayoutPanel();
  });
  layoutClearSelBtn?.addEventListener('click', () => {
    setSelection([]);
    if (layoutNoteEl) layoutNoteEl.textContent = 'Sélection effacée.';
    renderLayoutPanel();
  });
  // CALX116 — bascule CADRE/LASSO : ne change QUE la forme du prochain tracé, par défaut
  // sur cadre (comportement d'aujourd'hui inchangé).
  layoutLassoBtn?.addEventListener('click', () => {
    lassoMode = !lassoMode;
    layoutLassoBtn.setAttribute('aria-pressed', String(lassoMode));
    if (layoutNoteEl) {
      layoutNoteEl.textContent = lassoMode
        ? 'Lasso : tracez librement autour des panneaux à sélectionner.'
        : 'Cadre : glissez pour encadrer les panneaux à sélectionner.';
    }
  });

  // PV25 — NUDGE d'azimut (toit en pente) : ±1° sur la face du pan, puis RECALCUL complet
  // (re-pavage) qui re-entre la disposition personnalisée en re-snappant les panneaux
  // posés — exactement le chemin d'une édition d'obstacle, jamais un effacement.
  function nudgeAzimuth(deltaDeg: number) {
    if (ctx.roofType !== 'pitched') return;
    ctx.facingAzimuthDeg = nudgeAzimuthDeg(ctx.facingAzimuthDeg, deltaDeg);
    ctx.facingManual = true; // un réglage MANUEL ne doit plus être écrasé par l'auto-inférence
    if (layoutAzValueEl) layoutAzValueEl.textContent = `${Math.round(ctx.facingAzimuthDeg)}°`;
    if (layoutNoteEl) layoutNoteEl.textContent = `Azimut du pan : ${Math.round(ctx.facingAzimuthDeg)}°.`;
    recalcAfterAxisChange();
    renderLayoutPanel();
  }
  layoutAzMinusEl?.addEventListener('click', () => nudgeAzimuth(-AZIMUTH_NUDGE_DEG));
  layoutAzPlusEl?.addEventListener('click', () => nudgeAzimuth(AZIMUTH_NUDGE_DEG));

  // PV26 — boutons « annuler » / « rétablir ».
  layoutUndoBtn?.addEventListener('click', () => undo());
  layoutRedoBtn?.addEventListener('click', () => redo());

  // ── PV30 — bascule de MODE + réglages du placement libre ─────────────────────
  modeLatticeBtn?.addEventListener('click', () => {
    if (!ctx.freeMode) return;
    exitFreeMode();
  });
  modeFreeBtn?.addEventListener('click', () => {
    if (ctx.freeMode) return;
    enterFreeMode();
  });
  // Les deux champs de marge : on applique à la saisie ET à la sortie du champ. Aucune
  // validation HTML (pas de min/max/step imposé) — règle fondateur : on n'arrondit ni ne
  // rejette jamais ce que l'utilisateur tape.
  freeSetbackEl?.addEventListener('change', applyMargins);
  freeGapEl?.addEventListener('change', applyMargins);
  freeSetbackEl?.addEventListener('blur', applyMargins);
  freeGapEl?.addEventListener('blur', applyMargins);
  // « Ajouter un panneau » : ARME la pose ; le prochain clic sur le toit la commet.
  freeAddBtn?.addEventListener('click', () => {
    if (!freeActive()) return;
    freeAddArmed = !freeAddArmed;
    if (layoutNoteEl) {
      layoutNoteEl.textContent = freeAddArmed
        ? 'Touchez l’endroit du toit où poser le nouveau panneau (Échap pour annuler).'
        : 'Ajout annulé.';
    }
    syncFreeInputs();
    renderLayoutPanel();
  });

  // CALX112 — lit le décalage SAISI (cm → m, même unité que les marges) et duplique la
  // sélection courante. Le bouton reste inactif tant qu'aucun pas > 0 n'est saisi (voir
  // `syncFreeInputs`) — un clic sans pas valide ne fait donc jamais rien de deviné.
  freeDupStepEl?.addEventListener('input', syncFreeInputs);
  freeDupBtn?.addEventListener('click', () => {
    if (!freeActive() || !freeDupStepEl) return;
    const raw = (freeDupStepEl.value ?? '').toString().trim().replace(',', '.');
    const stepM = raw ? Number(raw) / 100 : NaN;
    if (!Number.isFinite(stepM) || stepM <= 0) return;
    const members = selection.length ? selection : [];
    if (!members.length) {
      if (layoutNoteEl) layoutNoteEl.textContent = 'Sélectionnez d’abord les panneaux à dupliquer.';
      return;
    }
    dupliquerSelection(members, stepM);
  });

  // CALX113 — arme la désignation de l'axe : les DEUX prochains clics sur le toit
  // (`beginLayoutDrag`) fixent les deux points qui définissent la droite.
  freeMirrorBtn?.addEventListener('click', () => {
    if (!freeActive()) return;
    mirrorArmed = !mirrorArmed;
    mirrorFirstPoint = null;
    freeMirrorBtn.setAttribute('aria-pressed', String(mirrorArmed));
    if (layoutNoteEl) {
      layoutNoteEl.textContent = mirrorArmed
        ? 'Touchez un premier point de l’axe de symétrie (Échap pour annuler).'
        : 'Symétrie annulée.';
    }
  });

  // PV26 — RACCOURCIS clavier, actifs SEULEMENT en mode disposition (sinon on volerait
  // Ctrl+Z à la page hôte) : Ctrl/⌘+Z annule, Ctrl/⌘+Y (ou Ctrl/⌘+Maj+Z) rétablit. Les
  // FLÈCHES nudgent le panneau sélectionné — ou tout le groupe — d'un pas de calepinage.
  function nudgeSelection(dx: number, dy: number): boolean {
    // PV30 — en placement libre, les flèches avancent du PAS DE STABILITÉ (1 cm) : c'est
    // l'ajustement fin que la lattice ne pouvait pas offrir (elle sautait d'un emplacement).
    if (freeActive()) {
      const members = selection.length ? selection : [];
      if (!members.length) return false;
      const ux = Math.sign(dx) * (dx === 0 ? 0 : 1);
      const uy = Math.sign(dy) * (dy === 0 ? 0 : 1);
      return freeMoveSelection(ux * FREE_STEP_M, uy * FREE_STEP_M, members);
    }
    const st = ctx.layoutState;
    if (!st) return false;
    const members = selection.length ? selection : ctx.layoutSel != null ? [ctx.layoutSel] : [];
    if (!members.length) return false;
    recordHistory();
    const res = moveGroup(st, members, dx, dy, { maxSnapM: GROUP_SNAP_M });
    // Refusé, OU chaque membre est retombé sur sa propre cellule (rien de libre dans cette
    // direction) : dans les deux cas RIEN n'a bougé — on retire la photo pour ne pas
    // empiler une « action » vide dans l'historique.
    const sameAsBefore =
      res.ok && res.targets.length === members.length && [...res.targets].sort((a, b) => a - b).join() === [...members].sort((a, b) => a - b).join();
    if (!res.ok || sameAsBefore) {
      history.drop(); // PV29 — jeter la photo, sans allumer « rétablir » pour rien
      workshopHistory.drop(); // CAL100 — idem pour l'historique généralisé
      if (layoutNoteEl) layoutNoteEl.textContent = 'Pas de place dans cette direction — rien n’a bougé.';
      renderLayoutPanel();
      return false;
    }
    setSelection(res.targets);
    if (ctx.layoutSel != null) ctx.layoutSel = res.targets[0] ?? null;
    if (layoutNoteEl) layoutNoteEl.textContent = `Déplacé — ${fmt(res.targets.length)} panneaux.`;
    renderCustomLayout();
    renderLayoutPanel();
    return true;
  }
  document.addEventListener('keydown', (e) => {
    if (!ctx.layoutMode || !ctx.layoutState) return;
    const mod = e.ctrlKey || e.metaKey;
    const key = e.key.toLowerCase();
    if (mod && key === 'z' && !e.shiftKey) {
      if (undo()) e.preventDefault();
      return;
    }
    if (mod && (key === 'y' || (key === 'z' && e.shiftKey))) {
      if (redo()) e.preventDefault();
      return;
    }
    if (mod) return;
    // PV29 — Échap : abandonne la sélection (le geste « je me suis trompé » universel).
    if (key === 'escape') {
      // PV30 — Échap désarme d'abord la pose d'un nouveau panneau.
      if (freeAddArmed) {
        freeAddArmed = false;
        syncFreeInputs();
        if (layoutNoteEl) layoutNoteEl.textContent = 'Ajout annulé.';
        renderLayoutPanel();
        e.preventDefault();
        return;
      }
      // CALX113 — Échap désarme aussi la désignation de l'axe de symétrie.
      if (mirrorArmed) {
        mirrorArmed = false;
        mirrorFirstPoint = null;
        if (freeMirrorBtn) freeMirrorBtn.setAttribute('aria-pressed', 'false');
        if (layoutNoteEl) layoutNoteEl.textContent = 'Symétrie annulée.';
        renderLayoutPanel();
        e.preventDefault();
        return;
      }
      if (!selection.length && ctx.layoutSel == null) return;
      setSelection([]);
      ctx.layoutSel = null;
      if (layoutNoteEl) layoutNoteEl.textContent = 'Sélection effacée.';
      renderLayoutPanel();
      e.preventDefault();
      return;
    }
    // Pas de nudge : la largeur de rangée (axe u) et le pas de rangée (axe d'empilement)
    // du pavage courant — on avance exactement d'un emplacement, jamais d'un pas inventé.
    const grid = ctx.layoutPlan?.grid;
    if (!grid) return;
    const stepU = grid.rowWidthM;
    const stepV = grid.rowPitchM;
    const moves: Record<string, [number, number]> = {
      arrowleft: [-stepU, 0],
      arrowright: [stepU, 0],
      arrowup: [0, stepV],
      arrowdown: [0, -stepV],
    };
    const delta = moves[key];
    if (!delta) return;
    if (nudgeSelection(delta[0], delta[1])) e.preventDefault();
  });

  // Plan tactile : tap-sélection d'un panneau → tap-cible d'un emplacement libre.
  layoutGridEl?.addEventListener('click', (e) => {
    if (!ctx.layoutMode || !ctx.layoutState) return;
    const btn = (e.target as HTMLElement).closest<HTMLElement>('[data-cell]');
    if (!btn) return;
    const idx = parseInt(btn.dataset.cell ?? '', 10);
    if (!Number.isFinite(idx)) return;
    const occupied = ctx.layoutState.occupied.has(idx);
    if (ctx.layoutSel == null) {
      // 1er tap : sélectionne un panneau OCCUPÉ.
      if (occupied) {
        ctx.layoutSel = idx;
        if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau sélectionné — touchez un emplacement libre (vert) pour l’y déplacer.';
        renderLayoutPanel();
      } else if (layoutNoteEl) {
        layoutNoteEl.textContent = 'Touchez d’abord un panneau (bleu).';
      }
      return;
    }
    // 2e tap : déplace vers la cible si elle est VIDE valide ; sinon rejet (rouge).
    recordHistory(); // PV26
    const res = movePanelToCell(ctx.layoutState, ctx.layoutSel, idx);
    if (res.ok) {
      if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
      ctx.layoutSel = null;
      renderCustomLayout();
    } else {
      if (layoutNoteEl) layoutNoteEl.textContent = occupied ? 'Emplacement déjà occupé — choisissez un emplacement libre.' : 'Cible invalide.';
      // re-sélection si on a touché un autre panneau occupé
      if (occupied) ctx.layoutSel = idx;
      else ctx.layoutSel = null;
    }
    renderLayoutPanel();
  });

  // Glissé sur la 3D : raycast (déprojection) → snap à la cellule VIDE valide la plus
  // proche, commit au relâchement. Désactive le pan de la carte pendant le glissé.
  // PV29 — `altKey` mémorise le modificateur DE SUPPRESSION appuyé au moment de la saisie :
  // un clic simple SÉLECTIONNE désormais, seul Alt + clic supprime (voir endLayoutDrag).
  // PV31 — en placement LIBRE, le glissé porte en plus de quoi rejouer le geste à chaque
  // image : les positions d'ORIGINE de tous les membres (on repart TOUJOURS de là, jamais de
  // l'aperçu précédent → aucune dérive) et le décalage de SAISIE (le panneau garde le point
  // où on l'a attrapé sous le curseur, au lieu de sauter par son centre).
  let layoutDrag:
    | {
        from: number;
        startPoint: maplibregl.Point;
        moved: boolean;
        altKey: boolean;
        /** PV34 — Ctrl/⌘ maintenu à la saisie : un clic sans glissé BASCULE le panneau
         *  dans la sélection (le geste standard « ajouter/retirer » d'un éditeur). */
        ctrlKey?: boolean;
        /** PV34 — l'aperçu vivant a-t-il déjà repeint la 3D en mode LATTICE ? (si oui, un
         *  refus au relâcher doit restaurer le rendu réel, sinon l'écran mentirait). */
        latticePreviewed?: boolean;
        freeOrigin?: { index: number; cx: number; cy: number }[];
        grabDx?: number;
        grabDy?: number;
        freePreviewed?: boolean;
        /** Dernier verdict de REFUS rencontré pendant l'aperçu — sert à NOMMER la raison au
         *  relâchement (« sortirait du toit », « chevaucherait un autre panneau »…) plutôt
         *  que de se contenter d'un « refusé » muet. */
        freeBlocked?: FreeCheck;
      }
    | null = null;
  /** PV31 — point du dernier appui « dans le vide » (aucun panneau saisi), pour distinguer un
   *  CLIC (qui efface la sélection) d'un déplacement de carte (qui ne l'efface pas). */
  let emptyPress: maplibregl.Point | null = null;
  function layoutPanelAt(point: maplibregl.Point): number | null {
    if (freeActive()) return freePanelAt(point); // PV30 — même geste, autre liste
    const layoutState = ctx.layoutState;
    if (!layoutState) return null;
    const enu = screenToENU(point);
    if (!enu) return null;
    // Cellule OCCUPÉE la plus proche du point (le panneau qu'on saisit).
    let best = -1;
    let bestD = Infinity;
    for (const c of layoutState.cells) {
      if (!layoutState.occupied.has(c.index)) continue;
      const d = (c.cx - enu.x) ** 2 + (c.cy - enu.y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = c.index;
      }
    }
    // Seuil de saisie : ~1 panneau de rayon (sinon on considère qu'on n'a rien saisi).
    const grabR2 = (PANEL2_LONG_M * 0.7) ** 2;
    return best >= 0 && bestD <= grabR2 ? best : null;
  }
  /** Début d'un glissé-déplacer (souris OU doigt) : saisit le panneau sous le point, fige le
   *  pan de la carte. Renvoie true si un panneau a été saisi (le geste devient un glissé). */
  function beginLayoutDrag(
    point: maplibregl.Point,
    shiftKey = false,
    altKey = false,
    ctrlKey = false,
    fromMouse = false,
  ): boolean {
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return false;
    // PV30 — « Ajouter un panneau » armé : le prochain clic POSE, il ne saisit rien.
    if (freeActive() && freeAddArmed) {
      const enu = screenToENU(point);
      if (!enu) return false;
      freeAddArmed = false;
      freeAddAt(enu.x, enu.y);
      syncFreeInputs();
      return true;
    }
    // CALX113 — « Symétrie » armée : les DEUX prochains clics désignent l'axe (une droite
    // définie par deux points cliqués) ; le second clic COMMIT la symétrie de la sélection.
    if (freeActive() && mirrorArmed) {
      const enu = screenToENU(point);
      if (!enu) return false;
      if (!mirrorFirstPoint) {
        mirrorFirstPoint = { x: enu.x, y: enu.y };
        if (layoutNoteEl) layoutNoteEl.textContent = 'Touchez un second point pour définir l’axe (Échap pour annuler).';
        return true;
      }
      const axis = { a: [mirrorFirstPoint.x, mirrorFirstPoint.y] as [number, number], b: [enu.x, enu.y] as [number, number] };
      mirrorArmed = false;
      mirrorFirstPoint = null;
      if (freeMirrorBtn) freeMirrorBtn.setAttribute('aria-pressed', 'false');
      const members = selection.length ? selection : [];
      if (!members.length) {
        if (layoutNoteEl) layoutNoteEl.textContent = 'Sélectionnez d’abord les panneaux à symétriser.';
        return true;
      }
      symetriserSelection(members, axis);
      return true;
    }
    /** PV34 — arme le cadre. `additive` : le lot encadré s'AJOUTE au groupe courant
     *  (Maj) au lieu de le remplacer (glissé nu / mode ▭ Sélection). */
    const startMarquee = (additive: boolean): boolean => {
      const enu = screenToENU(point);
      if (!enu) return false;
      // PV29 — `moved` distingue un GLISSÉ (rectangle) d'un CLIC (bascule d'un seul
      // panneau). Avant, un Maj + clic terminait sur un rectangle de surface nulle et
      // VIDAIT donc la sélection — l'inverse de ce que le geste veut dire.
      marquee = { x0: enu.x, y0: enu.y, x1: enu.x, y1: enu.y, moved: false, startPoint: point, additive };
      emptyPress = null;
      showMarquee(point, point); // PV31 — le cadre est VISIBLE dès le premier pixel
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
      return true;
    };
    // CALX116 — arme le LASSO (même déclenchement que le cadre, forme différente). Le
    // box-zoom MapLibre reste désactivé pour tout l'éditeur (map.boxZoom?.disable?.() à la
    // construction, jamais réactivé) — le piège documenté du cadre (PV34 ci-dessus) ne
    // revient donc pas non plus pour le lasso.
    const startLasso = (additive: boolean): boolean => {
      const enu = screenToENU(point);
      if (!enu) return false;
      lasso = { ring: [[enu.x, enu.y]], screenPts: [point], startPoint: point, moved: false, additive };
      emptyPress = null;
      showLasso(lasso.screenPts);
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
      return true;
    };
    const startSelectGesture = (additive: boolean): boolean => (lassoMode ? startLasso(additive) : startMarquee(additive));
    // PV25 — MARQUEE/LASSO : Maj + glissé (souris) ou mode « sélection multiple » (doigt)
    // trace un cadre (ou un lasso) au lieu de déplacer un panneau. En ENU (mètres), via la
    // MÊME déprojection écran→toit que le reste de l'éditeur — aucun second système.
    if (shiftKey || selectMode) return startSelectGesture(shiftKey);
    const from = layoutPanelAt(point);
    if (from == null) {
      // PV34 — SÉLECTION SANS MODIFICATEUR (ordre du fondateur : « the selection should be
      // made easy »). À la SOURIS, un glissé qui part de la zone de calepinage mais d'aucun
      // panneau trace le cadre — la convention de tout éditeur : on glisse sur le vide du
      // plan de travail, on encadre. Hors de cette zone, le glissé reste un déplacement de
      // carte (inchangé), donc la carte ne devient jamais immobile. Au DOIGT, rien ne
      // change : un doigt continue de faire glisser la carte, le cadre reste sur le bouton
      // « ▭ Sélection » (un pan tactile perdu serait une régression bien pire).
      const enu = fromMouse ? screenToENU(point) : null;
      if (enu && pointOnLayoutArea(enu.x, enu.y)) return startSelectGesture(false);
      // PV31 — appui dans le VIDE : on le mémorise, un simple clic effacera la sélection
      // (un glissé, lui, reste un déplacement de carte et n'y touche pas).
      emptyPress = point;
      return false;
    }
    emptyPress = null;
    const drag: NonNullable<typeof layoutDrag> = { from, startPoint: point, moved: false, altKey, ctrlKey };
    layoutDrag = drag;
    // PV31 — placement libre : on fige l'ORIGINE du geste (positions de départ des membres
    // + décalage de saisie) et on photographie l'état UNE fois pour tout le glissé.
    if (freeActive()) {
      const st = ctx.freeState!;
      const grabbed = st.panels[from];
      const enu = screenToENU(point);
      if (grabbed && enu) {
        const members = selection.length > 1 && selection.includes(from) ? [...selection] : [from];
        drag.freeOrigin = members.map((i) => ({ index: i, cx: st.panels[i].cx, cy: st.panels[i].cy }));
        drag.grabDx = grabbed.cx - enu.x;
        drag.grabDy = grabbed.cy - enu.y;
        recordFreeHistory(); // une seule photo pour tout le geste (retirée s'il ne pose rien)
      }
    }
    ctx.layoutSel = from;
    map.dragPan.disable();
    map.getCanvas().style.cursor = 'grabbing';
    renderLayoutPanel();
    return true;
  }

  /**
   * PV31 — APERÇU VIVANT d'un glissé LIBRE : les panneaux SUIVENT le curseur, au lieu de ne
   * bouger qu'au relâchement (le fondateur ne voyait donc rien se passer et concluait que
   * « le déplacement ne marche pas »).
   *
   * On rejoue le geste depuis les positions d'ORIGINE à chaque image — jamais en cumulant
   * l'aperçu précédent — donc le glissé ne dérive pas et reste annulable d'un seul coup. Le
   * lot entier est TOUT OU RIEN : si la position visée viole une contrainte, on GARDE le
   * dernier aperçu valide à l'écran et on NOMME ce qui bloque (rive, voisin, obstacle…).
   */
  function previewFreeDrag(point: maplibregl.Point): void {
    const d = layoutDrag;
    const st = freeState();
    const g = freeGeom();
    if (!d || !d.freeOrigin || !d.freeOrigin.length || !st || !g) return;
    const enu = screenToENU(point);
    if (!enu) return;
    const anchor = d.freeOrigin.find((o) => o.index === d.from) ?? d.freeOrigin[0];
    // Le panneau saisi garde le point d'accroche sous le curseur (décalage de saisie).
    const dx = quantizeFree(enu.x + (d.grabDx ?? 0)) - anchor.cx;
    const dy = quantizeFree(enu.y + (d.grabDy ?? 0)) - anchor.cy;
    const res = placeFreePanels(
      st,
      g,
      d.freeOrigin.map((o) => ({ index: o.index, cx: o.cx + dx, cy: o.cy + dy })),
      margins(),
    );
    if (!res.ok) {
      d.freeBlocked = res.blocked;
      if (res.blocked) showMeasure(res.blocked);
      if (layoutNoteEl) {
        const why = res.blocked ? res.blocked.violations.map(violationLabel).join(', ') : 'placement invalide';
        layoutNoteEl.textContent = `Ici : ${why}.`;
      }
      return; // le dernier aperçu VALIDE reste affiché — rien ne clignote, rien ne saute
    }
    d.freeBlocked = undefined;
    d.freePreviewed = true;
    // Mesures affichées pour le panneau SAISI, à sa position d'aperçu (rive / voisin) : la
    // marge réduite reste un acte VU et CHOISI, jamais un glissement silencieux.
    const posed = st.panels[d.from];
    if (posed) {
      const chk = checkPanelAt(st, g, d.from, posed.cx, posed.cy, margins());
      showMeasure(chk);
      if (layoutNoteEl) {
        layoutNoteEl.textContent = `Relâchez pour poser — rive ${cm(chk.edgeM)}, voisin ${chk.panelM === null ? '—' : cm(chk.panelM)}.`;
      }
    }
    scheduleFreePreviewPaint();
  }

  /** PV31 — au plus UN re-rendu 3D par image pendant un glissé (les événements pointeur
   *  arrivent bien plus vite que l'écran ne rafraîchit). */
  let freePreviewPending = false;
  function scheduleFreePreviewPaint() {
    if (freePreviewPending) return;
    freePreviewPending = true;
    const run = () => {
      freePreviewPending = false;
      renderFreeScene();
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run);
    else run();
  }

  /**
   * PV34 — APERÇU VIVANT d'un glissé en mode LATTICE (« Emplacements validés »).
   *
   * PV31 n'avait donné l'aperçu vivant qu'au placement LIBRE : en lattice — le mode par
   * DÉFAUT — on glissait un groupe et RIEN ne bougeait jusqu'au relâchement. D'où le
   * reproche du fondateur (« it should be easier and more natural to drag them ») : le
   * geste n'avait aucun retour. On re-rend donc la 3D avec l'occupation qu'aurait le
   * relâchement, sans jamais toucher à l'état : `planGroupMove` CALCULE ce que
   * `moveGroup` committera, les deux ne peuvent pas diverger.
   */
  let latticePreviewPending: { occ: Set<number>; targets: number[] } | null = null;
  let latticePreviewFrame = false;
  function scheduleLatticePreviewPaint(occ: Set<number>, targets: number[]) {
    latticePreviewPending = { occ, targets };
    if (latticePreviewFrame) return;
    latticePreviewFrame = true;
    const run = () => {
      latticePreviewFrame = false;
      const pending = latticePreviewPending;
      latticePreviewPending = null;
      if (!pending || !ctx.layoutPlan) return;
      renderScene(
        ctx.layoutPlan.pack,
        ctx.layoutPlan.grid,
        ctx.layoutPlan.tiltDeg,
        ctx.layoutPlan.family,
        pending.occ.size,
        ctx.layoutPlan.flush,
        pending.occ,
      );
      // Re-rendre reconstruit les instances (teintes remises à blanc) : on rallume les
      // panneaux à leur position d'APERÇU, pas à celle d'origine.
      paintPreviewSelection(pending.targets);
    };
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(run);
    else run();
  }

  /** PV34 — calcule et peint l'aperçu du glissé LATTICE en cours. Renvoie la note à
   *  afficher (le verdict honnête : où ça atterrit, ou pourquoi ça ne tient pas). */
  function previewLatticeDrag(enu: { x: number; y: number }): string {
    const d = layoutDrag;
    const st = ctx.layoutState;
    if (!d || !st) return '';
    const cell = st.cells[d.from];
    if (!cell) return '';
    const members = rowMode
      ? rowMembers(st, d.from)
      : selection.length > 1 && selection.includes(d.from)
        ? [...selection]
        : [];
    if (!members.length) {
      // Panneau SEUL : la cible est la cellule vide la plus proche — exactement ce que
      // `movePanelToPoint` choisira au relâchement (il appelle `nearestEmptyCell`).
      const target = nearestEmptyCell(st, enu.x, enu.y);
      if (target < 0) return 'Aucun emplacement libre — il reviendra à sa place.';
      const occ = new Set(st.occupied);
      occ.delete(d.from);
      occ.add(target);
      d.latticePreviewed = true;
      scheduleLatticePreviewPaint(occ, [target]);
      return 'Relâchez pour poser ici.';
    }
    const { dx, dy } = snapDeltaToGrid(enu.x - cell.cx, enu.y - cell.cy);
    // Mode RANGÉE : déplacement CONTRAINT à l'axe de la rangée (aucune composante en y) —
    // la même règle que `moveRowBy`, qui committera au relâchement.
    const plan = planGroupMove(st, members, dx, rowMode ? 0 : dy, { maxSnapM: GROUP_SNAP_M });
    if (!plan.ok) {
      return rowMode
        ? 'La rangée ne tient pas à cet endroit — rien ne bougera.'
        : 'Le groupe entier ne tient pas à cet endroit — rien ne bougera.';
    }
    const occ = new Set(st.occupied);
    for (const i of plan.members) occ.delete(i);
    for (const t of plan.targets) occ.add(t);
    d.latticePreviewed = true;
    scheduleLatticePreviewPaint(occ, plan.targets);
    return `Relâchez pour poser — ${fmt(plan.targets.length)} panneaux.`;
  }
  /** Glissé en cours (souris OU doigt) : au-delà du seuil LAYOUT_GRAB_PX, retour visuel
   *  « relâchez sur un emplacement valide / aucun libre ». Le seuil évite qu'un simple
   *  tap/clic ne fasse sauter le panneau vers la cellule vide la plus proche. */
  function moveLayoutDrag(point: maplibregl.Point) {
    // CALX116 — lasso en cours : on échantillonne le point (au pas mini `LASSO_SAMPLE_PX`,
    // plafonné à `LASSO_MAX_POINTS`) et on annonce le compte, comme le cadre.
    if (lasso && ctx.layoutState) {
      const enu = screenToENU(point);
      if (!enu) return;
      const last = lasso.screenPts[lasso.screenPts.length - 1];
      const farEnough = Math.hypot(point.x - last.x, point.y - last.y) >= LASSO_SAMPLE_PX;
      if (farEnough && lasso.ring.length < LASSO_MAX_POINTS) {
        lasso.ring.push([enu.x, enu.y]);
        lasso.screenPts.push(point);
      }
      showLasso(lasso.screenPts); // le tracé suit le geste, à l'écran
      if (Math.abs(point.x - lasso.startPoint.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - lasso.startPoint.y) >= LAYOUT_GRAB_PX) {
        lasso.moved = true;
      }
      const hits = panelsInLasso(lasso.ring);
      paintPreviewSelection(lasso.additive ? applySelectionGesture(selection, hits, 'add') : hits);
      if (layoutNoteEl) {
        const total = lasso.additive ? applySelectionGesture(selection, hits, 'add').length : hits.length;
        layoutNoteEl.textContent = hits.length
          ? `${fmt(total)} panneaux dans la sélection — relâchez pour les sélectionner.`
          : lasso.additive
            ? 'Aucun panneau de plus dans le lasso.'
            : 'Aucun panneau dans le lasso.';
      }
      return;
    }
    // PV25 — marquee en cours : on met à jour le coin opposé et on annonce le compte.
    if (marquee && ctx.layoutState) {
      const enu = screenToENU(point);
      if (!enu) return;
      marquee.x1 = enu.x;
      marquee.y1 = enu.y;
      showMarquee(marquee.startPoint, point); // PV31 — le cadre suit le geste, à l'écran
      // PV29 — au-delà du seuil, c'est un vrai cadre (et plus un Maj + clic).
      if (Math.abs(point.x - marquee.startPoint.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - marquee.startPoint.y) >= LAYOUT_GRAB_PX) {
        marquee.moved = true;
      }
      // PV34 — les panneaux TRAVERSÉS par le cadre (et plus « centre dedans »).
      const hits = panelsInMarquee(marquee);
      // PV31 — les panneaux encadrés s'allument DÉJÀ pendant le geste : on voit ce qu'on
      // attrape avant même de relâcher. PV34 — en mode additif (Maj), on allume aussi ce
      // qui est DÉJÀ sélectionné : l'aperçu montre le groupe FINAL, pas seulement le lot.
      paintPreviewSelection(marquee.additive ? applySelectionGesture(selection, hits, 'add') : hits);
      if (layoutNoteEl) {
        const total = marquee.additive ? applySelectionGesture(selection, hits, 'add').length : hits.length;
        layoutNoteEl.textContent = hits.length
          ? `${fmt(total)} panneaux dans la sélection — relâchez pour les sélectionner.`
          : marquee.additive
            ? 'Aucun panneau de plus dans le rectangle.'
            : 'Aucun panneau dans le rectangle.';
      }
      return;
    }
    if (!layoutDrag || !ctx.layoutState) return;
    if (!layoutDrag.moved && (Math.abs(point.x - layoutDrag.startPoint.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - layoutDrag.startPoint.y) >= LAYOUT_GRAB_PX)) {
      layoutDrag.moved = true;
    }
    if (!layoutDrag.moved) return;
    const enu = screenToENU(point);
    if (!enu) return;
    // PV30 — placement libre : on MESURE en direct où le panneau atterrirait (distance à
    // la rive et au voisin le plus proche, en cm) et on annonce le verdict. Réduire une
    // marge devient un acte VU et CHOISI — jamais un glissement silencieux.
    if (freeActive()) {
      // PV31 — les panneaux suivent RÉELLEMENT le curseur (aperçu vivant), au lieu de se
      // contenter d'une mesure en texte qui ne bougeait rien à l'écran.
      previewFreeDrag(point);
      return;
    }
    // PV34 — en LATTICE aussi, les panneaux suivent maintenant le curseur pendant le
    // geste (aperçu vivant, une image au plus par rafraîchissement). Avant, rien ne
    // bougeait jusqu'au relâchement : c'est ce qui rendait le glissé de groupe illisible.
    const note = previewLatticeDrag(enu);
    if (layoutNoteEl && note) layoutNoteEl.textContent = note;
  }
  /** W88 — SUPPRIME le panneau de la cellule `cellIndex` directement depuis la 3D (clic
   *  desktop / appui long tactile), puis recompute les chiffres (renderCustomLayout). Efface
   *  tout surlignage. No-op si la cellule n'est pas occupée. */
  function removePanelInScene(cellIndex: number) {
    if (!ctx.layoutState) return;
    recordHistory(); // PV26
    const r = removePanel(ctx.layoutState, cellIndex);
    if (!r.ok) return;
    ctx.layoutSel = null;
    setPanelHighlight(null);
    if (layoutNoteEl) {
      layoutNoteEl.textContent = ctx.neededPanels > 0 && r.count < ctx.neededPanels
        ? `Panneau supprimé — ${r.count} posés. La disposition ne couvre plus tout le besoin (${fmt(ctx.neededPanels)}).`
        : `Panneau supprimé — ${r.count} posés.`;
    }
    renderCustomLayout(); // recompute production/économies/couverture
    renderLayoutPanel();
  }

  /** Fin d'un glissé-déplacer (souris OU doigt) : commit du déplacement sur la cellule vide
   *  valide la plus proche (movePanelToPoint), sinon snap-back ; ré-active le pan. W88 — un
   *  simple CLIC (souris, `removeOnTap`) sans glissé SUPPRIME le panneau saisi ; un tap tactile
   *  bref ne supprime pas (la suppression tactile passe par l'appui long, géré séparément). */
  function endLayoutDrag(point: maplibregl.Point, removeOnTap = false) {
    // CALX116 — fin d'un LASSO : la sélection devient les panneaux dont le CENTRE tombe
    // dans l'anneau tracé (même logique que le cadre : un simple clic, sans glissé, bascule
    // le panneau visé au lieu de fermer un anneau de surface nulle).
    if (lasso && ctx.layoutState) {
      const enu = screenToENU(point);
      if (enu) lasso.ring.push([enu.x, enu.y]);
      const dragged = lasso.moved;
      const additive = lasso.additive;
      const hits = panelsInLasso(lasso.ring);
      lasso = null;
      hideLasso();
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      if (!dragged) {
        const hit = layoutPanelAt(point);
        if (hit != null) {
          selectSinglePanel(hit, true);
          return;
        }
        renderLayoutPanel();
        return;
      }
      setSelection(applySelectionGesture(selection, hits, additive ? 'add' : 'replace'));
      if (layoutNoteEl) {
        layoutNoteEl.textContent = selection.length
          ? `${fmt(selection.length)} panneaux sélectionnés — glissez-en un pour déplacer tout le groupe.`
          : 'Sélection vide.';
      }
      renderLayoutPanel();
      return;
    }
    // PV25 — fin d'un MARQUEE : la sélection devient les panneaux du rectangle.
    if (marquee && ctx.layoutState) {
      const enu = screenToENU(point);
      if (enu) {
        marquee.x1 = enu.x;
        marquee.y1 = enu.y;
      }
      const dragged = marquee.moved;
      const additive = marquee.additive;
      const hits = panelsInMarquee(marquee); // PV34 — panneaux TRAVERSÉS par le cadre
      marquee = null;
      hideMarquee(); // PV31 — le cadre disparaît, la sélection qu'il a produite reste allumée
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      if (!dragged) {
        // PV29 — Maj + CLIC (aucun glissé) : BASCULE le panneau visé dans la sélection.
        const hit = layoutPanelAt(point);
        if (hit != null) {
          selectSinglePanel(hit, true);
          return;
        }
        // Maj + clic dans le vide : on ne touche à rien (on ne vide plus la sélection par
        // accident — c'était le piège du rectangle de surface nulle).
        renderLayoutPanel();
        return;
      }
      // PV34 — un cadre tracé en gardant Maj AJOUTE au groupe (on encadre une rangée,
      // puis une autre) ; un cadre nu repart de zéro, comme dans tout éditeur.
      setSelection(applySelectionGesture(selection, hits, additive ? 'add' : 'replace'));
      if (layoutNoteEl) {
        layoutNoteEl.textContent = selection.length
          ? `${fmt(selection.length)} panneaux sélectionnés — glissez-en un pour déplacer tout le groupe.`
          : 'Sélection vide.';
      }
      renderLayoutPanel();
      return;
    }
    if (!layoutDrag || !ctx.layoutState) return;
    const from = layoutDrag.from;
    const moved = layoutDrag.moved;
    const altTap = layoutDrag.altKey; // PV29 — modificateur de SUPPRESSION saisi au mousedown
    const ctrlTap = !!layoutDrag.ctrlKey; // PV34 — modificateur de BASCULE de sélection
    const hadLatticePreview = !!layoutDrag.latticePreviewed;
    // PV31 — un geste LIBRE qui n'a pas bougé (simple clic, Alt + clic) n'est pas un
    // déplacement : on retire la photo prise à la saisie, sinon « annuler » consommerait un
    // pas pour ne rien changer. Les actions qui suivent reprennent leur propre photo.
    if (!moved && layoutDrag.freeOrigin) dropFreeHistory();
    if (moved && freeActive()) {
      // PV31 — commit d'un glissé LIBRE. L'APERÇU VIVANT a déjà posé les panneaux à leur
      // dernière position VALIDE : il n'y a plus rien à recalculer ici, seulement à
      // confirmer. La photo d'historique a été prise UNE fois au début du geste ; si aucun
      // aperçu n'a jamais été validé (le curseur n'a jamais visé un endroit possible), on
      // la retire — un geste qui n'a rien bougé n'est pas une action à annuler.
      const d = layoutDrag;
      const members = d?.freeOrigin?.map((o) => o.index) ?? [from];
      if (d?.freePreviewed) {
        if (layoutNoteEl) {
          layoutNoteEl.textContent = `Déplacé — ${fmt(members.length)} panneau${members.length > 1 ? 'x' : ''} (placement libre).`;
        }
        renderCustomLayout(); // recompute des chiffres + repeint la sélection
      } else {
        dropFreeHistory();
        flashRefusal(members); // refus VISIBLE (rouge), rien n'a bougé
        if (d?.freeBlocked) showMeasure(d.freeBlocked);
        if (layoutNoteEl) {
          // On NOMME ce qui a bloqué (relevé pendant l'aperçu), jamais un « refusé » muet.
          const why = d?.freeBlocked
            ? d.freeBlocked.violations.map(violationLabel).join(', ')
            : 'aucune position valide sous le curseur';
          layoutNoteEl.textContent = `Déplacement refusé : ${why} — rien n’a bougé.`;
        }
      }
      renderLayoutPanel();
      layoutDrag = null;
      ctx.layoutSel = null;
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      return;
    }
    if (moved) {
      // PV34 — l'aperçu vivant a repeint la 3D avec l'occupation VISÉE. Si le geste est
      // finalement refusé (ou impossible à déprojeter), il faut restaurer le rendu RÉEL —
      // sinon l'écran montrerait des panneaux à un endroit où ils ne sont pas.
      let committed = false;
      const enu = screenToENU(point);
      if (enu) {
        const cell = ctx.layoutState.cells[from];
        const rawDx = enu.x - cell.cx;
        const rawDy = enu.y - cell.cy;
        // PV29 — un déplacement de GROUPE/RANGÉE est quantifié sur le pas du calepinage :
        // le bloc garde sa forme (une rangée reste une rangée) au lieu de se replier au plus
        // près du curseur. Un panneau SEUL garde le placement libre (cellule la plus proche).
        const { dx, dy } = snapDeltaToGrid(rawDx, rawDy);
        recordHistory(); // PV26 — une photo AVANT le geste (simple, groupe ou rangée)
        // PV25 — trois gestes possibles, du plus large au plus fin :
        //  1. mode RANGÉE : toute la rangée suit, déplacement contraint à son axe ;
        //  2. panneau saisi MEMBRE d'une sélection : tout le groupe suit ;
        //  3. sinon : le panneau seul (comportement historique).
        // 1 et 2 sont TOUT OU RIEN : un membre sans emplacement valide annule le geste.
        if (rowMode) {
          const members = rowMembers(ctx.layoutState, from);
          const res = moveRowBy(ctx.layoutState, from, dx, { maxSnapM: GROUP_SNAP_M });
          if (res.ok) {
            setSelection(res.targets);
            if (layoutNoteEl) layoutNoteEl.textContent = `Rangée déplacée — ${fmt(members.length)} panneaux.`;
            renderCustomLayout();
            committed = true;
          } else {
            dropHistoryPhoto(); // PV29 — un geste refusé n'est pas une action à annuler
            if (hadLatticePreview) renderCustomLayout(); // PV34 — l'aperçu est effacé AVANT le rouge
            flashRefusal(members); // PV29 — refus VISIBLE (rouge), rien n'a bougé
            if (layoutNoteEl) layoutNoteEl.textContent = 'La rangée ne tient pas à cet endroit — rien n’a bougé.';
          }
        } else if (selection.length > 1 && selection.includes(from)) {
          const res = moveGroup(ctx.layoutState, selection, dx, dy, { maxSnapM: GROUP_SNAP_M });
          if (res.ok) {
            setSelection(res.targets);
            if (layoutNoteEl) layoutNoteEl.textContent = `Groupe déplacé — ${fmt(res.targets.length)} panneaux.`;
            renderCustomLayout();
            committed = true;
          } else {
            dropHistoryPhoto(); // PV29
            if (hadLatticePreview) renderCustomLayout(); // PV34
            flashRefusal(selection); // PV29
            if (layoutNoteEl) layoutNoteEl.textContent = 'Le groupe entier ne tient pas à cet endroit — rien n’a bougé.';
          }
        } else {
          const res = movePanelToPoint(ctx.layoutState, from, enu.x, enu.y);
          if (res.ok && res.toIndex !== from) {
            setSelection([res.toIndex]); // PV29 — le panneau déplacé reste sélectionné
            if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
            renderCustomLayout();
            committed = true;
          } else {
            dropHistoryPhoto(); // PV29
            if (hadLatticePreview) renderCustomLayout(); // PV34
            flashRefusal([from]); // PV29
            if (layoutNoteEl) {
              layoutNoteEl.textContent = 'Aucun emplacement libre à cet endroit — le panneau est resté en place.';
            }
          }
        }
      }
      // Déprojection impossible (curseur hors du plan) : l'aperçu doit disparaître.
      if (!committed && hadLatticePreview && !enu) renderCustomLayout();
    }
    layoutDrag = null;
    ctx.layoutSel = null;
    map.dragPan.enable();
    map.getCanvas().style.cursor = '';
    // W88/PV29 — clic desktop SANS glissé. La suppression ciblée demande désormais Alt :
    // un clic simple SÉLECTIONNE (le geste attendu par un opérateur), et un clic maladroit
    // ne fait plus disparaître un panneau vendu. Au doigt, la suppression reste l'appui long.
    if (!moved && removeOnTap) {
      if (altTap) {
        if (freeActive()) {
          freeRemoveAt(from); // PV30 — retrait EXPLICITE d'un panneau posé librement
          return;
        }
        removePanelInScene(from);
        return;
      }
    }
    if (!moved) {
      // PV34 — Ctrl/⌘ + clic AJOUTE ou RETIRE ce panneau du groupe (le geste standard de
      // sélection multiple) ; un clic nu repart d'une sélection à un panneau.
      selectSinglePanel(from, ctrlTap);
      return;
    }
    renderLayoutPanel();
  }

  // — Souris —
  map.on('mousedown', (e) => {
    // PV25 — Maj + glissé = rectangle de sélection (marquee) au lieu d'un déplacement.
    // PV29 — Alt = modificateur de SUPPRESSION (un clic nu sélectionne désormais).
    // PV34 — Ctrl/⌘ = modificateur de BASCULE (ajouter/retirer un panneau du groupe). On
    // ne s'en sert QUE pour le clic : Ctrl + GLISSÉ appartient à MapLibre (rotation/pitch
    // de la caméra), le lui voler casserait la vue.
    const ev = e.originalEvent as MouseEvent | undefined;
    const shift = !!ev?.shiftKey;
    const alt = !!ev?.altKey;
    const ctrl = !!(ev?.ctrlKey || ev?.metaKey);
    if (beginLayoutDrag(e.point, shift, alt, ctrl, true)) e.preventDefault();
  });
  // PV29 — DOUBLE-CLIC sur un panneau = sélectionner TOUTE SA RANGÉE, en un seul geste et
  // sans mode à activer (le zoom au double-clic est déjà désactivé par l'entrée). C'est le
  // geste « prendre la rangée » : ensuite un glissé (ou les flèches) l'emmène en bloc.
  map.on('dblclick', (e) => {
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return;
    const hit = layoutPanelAt(e.point);
    if (hit == null) return;
    if (selectRow(hit).length) e.preventDefault();
  });
  map.on('mousemove', (e) => {
    if (layoutDrag || marquee || lasso) {
      moveLayoutDrag(e.point);
      return;
    }
    // W88 — survol : surligne (or) le panneau sous le curseur en mode disposition, sinon rien.
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return;
    setPanelHighlight(layoutPanelAt(e.point));
  });
  map.on('mouseup', (e) => {
    const hadGesture = !!layoutDrag || !!marquee || !!lasso;
    endLayoutDrag(e.point, true); // clic sans glissé = supprimer (W88)
                                  // PV25 — un marquee/lasso en cours est committé par le même chemin.
    if (!hadGesture) clearSelectionOnEmptyClick(e.point);
  });

  /**
   * PV34 — FILET DE SÉCURITÉ : `map.on('mouseup')` ne se déclenche que si le bouton est
   * relâché AU-DESSUS de la carte. Un cadre tracé jusqu'au bord de l'écran — ou un
   * groupe glissé hors du conteneur — laissait donc le geste COLLÉ au curseur (cadre
   * orphelin, pan de carte encore désactivé) jusqu'au prochain clic. On termine le geste
   * au relâchement, où qu'il ait lieu, avec le point ramené dans le repère de la carte.
   */
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('mouseup', (ev: MouseEvent) => {
      if (!layoutDrag && !marquee && !lasso) return;
      const canvas = typeof map.getCanvas === 'function' ? map.getCanvas() : null;
      // Relâché SUR la carte : le chemin `map.on('mouseup')` s'en charge déjà.
      if (canvas && ev.target instanceof Node && canvas.contains(ev.target)) return;
      const rect = canvas?.getBoundingClientRect?.();
      const point = new maplibregl.Point(
        ev.clientX - (rect?.left ?? 0),
        ev.clientY - (rect?.top ?? 0),
      );
      endLayoutDrag(point, false); // hors carte : jamais une suppression sur « tap »
    });
  }

  /**
   * PV31 — un CLIC sur le vide (aucun panneau saisi, aucun cadre en cours) EFFACE la
   * sélection : le geste standard de tout éditeur, et le seul moyen évident de « lâcher »
   * un groupe. Un GLISSÉ parti du vide reste un déplacement de carte et ne touche à rien.
   */
  function clearSelectionOnEmptyClick(point: maplibregl.Point) {
    const press = emptyPress;
    emptyPress = null;
    if (!press) return;
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return;
    const dragged =
      Math.abs(point.x - press.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - press.y) >= LAYOUT_GRAB_PX;
    if (dragged) return; // la carte a été déplacée : ce n'était pas un clic
    if (!selection.length) return;
    setSelection([]);
    if (layoutNoteEl) layoutNoteEl.textContent = 'Sélection effacée.';
    renderLayoutPanel();
  }

  // W80 — TOUCH : glissé-déplacer au DOIGT, miroir du chemin souris, gardé par layoutMode
  // (via beginLayoutDrag). On ne saisit qu'à UN seul doigt (un pinch/zoom à deux doigts ne
  // doit pas déplacer un panneau). preventDefault en touchmove neutralise le pan de la carte
  // pendant qu'on glisse le panneau (parité avec dragPan.disable du chemin souris).
  // W88 — un APPUI LONG (sans glissé) au doigt SUPPRIME le panneau saisi : un minuteur démarré
  // à touchstart, annulé si le doigt bouge (glissé) ou se relève avant l'échéance (tap bref).
  const LONG_PRESS_MS = 500;
  let longPressTimer: ReturnType<typeof setTimeout> | null = null;
  function cancelLongPress() {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
  }
  map.on('touchstart', (e) => {
    if (e.points && e.points.length > 1) return; // multi-touch (pinch) → pas un glissé panneau
    if (beginLayoutDrag(e.point)) {
      e.preventDefault();
      // W88 — appui long → suppression du panneau saisi (s'il n'a pas bougé entre-temps).
      cancelLongPress();
      const cell = layoutDrag ? layoutDrag.from : -1;
      longPressTimer = setTimeout(() => {
        longPressTimer = null;
        if (layoutDrag && !layoutDrag.moved && cell >= 0) {
          const wasFreeGrab = !!layoutDrag.freeOrigin;
          layoutDrag = null;
          map.dragPan.enable();
          map.getCanvas().style.cursor = '';
          // PV31 — la photo prise à la saisie n'a servi à rien (le doigt n'a pas bougé) :
          // on la retire, la suppression reprend la sienne.
          if (wasFreeGrab) dropFreeHistory();
          // PV31 — en placement LIBRE, l'index saisi indexe la LISTE des panneaux libres,
          // pas une cellule de lattice : l'appui long doit retirer le panneau LIBRE (le
          // chemin lattice mutait silencieusement une occupation qui ne gouverne plus rien).
          if (freeActive()) freeRemoveAt(cell);
          else removePanelInScene(cell);
        }
      }, LONG_PRESS_MS);
    }
  });
  map.on('touchmove', (e) => {
    if (!layoutDrag && !marquee && !lasso) return;
    e.preventDefault();
    moveLayoutDrag(e.point);
    if (layoutDrag?.moved) cancelLongPress(); // un glissé annule l'appui long (c'est un déplacement)
  });
  map.on('touchend', (e) => {
    cancelLongPress(); // tap bref / fin de glissé : pas de suppression par appui long
    if (!layoutDrag && !marquee && !lasso) {
      clearSelectionOnEmptyClick(e.point); // PV31 — un tap dans le vide lâche la sélection
      return;
    }
    endLayoutDrag(e.point); // tactile : pas de suppression sur tap bref (removeOnTap=false)
  });

  return {
    layoutCap,
    ensureLayoutState,
    renderCustomLayout,
    screenToENU,
    renderLayoutPanel,
    setLayoutMode,
    occupiedCenters,
    reenterCustomLayout,
    selection: () => [...selection],
    setSelection,
    removeCells,
    undo,
    redo,
    hydrateLayout,
    hasManualEdits,
    confirmDiscardEdits,
    selectRow,
    // PV30 - placement libre.
    isFreeMode: () => !!ctx.freeMode,
    setFreeMode: (on: boolean) => (on ? enterFreeMode() : exitFreeMode(false)),
    freePanels: () => (ctx.freeState ? ctx.freeState.panels.map((p) => ({ ...p })) : []),
    freeMargins: () => margins(),
    setFreeMargins: (m: { setbackM?: number; gapM?: number }) => {
      ctx.freeMargins = {
        setbackM: Number.isFinite(m.setbackM as number) ? (m.setbackM as number) : margins().setbackM,
        gapM: Number.isFinite(m.gapM as number) ? (m.gapM as number) : margins().gapM,
      };
      syncFreeInputs();
    },
    freeRotateSelection,
    freeSnapCandidate,
    freeAlignSelection,
    freeDistributeSelection,
    dupliquerSelection,
    symetriserSelection,
    panelsInLasso,
    isLassoMode: () => lassoMode,
  };
}

/* ════════════════════════════════════════════════════════════════════════════
   CAL106 — TENIR LA CHARGE DES GRANDS CHAMPS : LE RE-SNAP EN MASSE.
   ----------------------------------------------------------------------------
   Constat mesuré : le coût qui explose sur un grand champ n'est pas le rendu,
   c'est le RE-SNAP EN MASSE. `nearestEmptyCell` balaie TOUTES les cellules de
   la lattice pour UN centre ; les trois chemins de masse (retour depuis le
   placement libre, `reenterCustomLayout` après un re-pavage, `hydrateLayout` au
   rechargement d'un dossier) l'appellent une fois PAR panneau. C'est du
   N × M : 2 000 panneaux sur une lattice de 2 000 cellules = 4 000 000 de
   distances par geste, sur le fil d'exécution de l'interface. Dimensionné pour
   la villa (quelques dizaines), jamais mesuré sur un champ.

   `resnapEnMasse` fait le MÊME travail avec un index par cases : les cellules
   vides sont rangées dans une grille de cases, et la recherche part de la case
   du centre puis s'élargit en anneaux jusqu'à ce que l'anneau suivant ne puisse
   plus contenir mieux. Le coût redevient proportionnel au voisinage, pas à la
   lattice entière.

   ÉQUIVALENCE STRICTE, PAS « À PEU PRÈS PAREIL » — c'est la condition posée par
   la tâche (« aucun chiffre de calepinage ne change ») :
     * même critère : la cellule VIDE la plus proche au carré de la distance ;
     * même départage : à distance ÉGALE, la cellule qui vient en PREMIER dans
       l'ordre de la lattice — exactement ce que produit le balayage linéaire,
       qui n'améliore que sur un `<` strict ;
     * même effet de bord : chaque centre occupe sa cellule AVANT que le centre
       suivant ne cherche la sienne (l'ordre des centres compte, et il est
       préservé).
   Le test jumeau confronte les deux implémentations sur des cas aléatoires et
   exige des ensembles d'index IDENTIQUES.
   ══════════════════════════════════════════════════════════════════════════ */

/** Un centre à re-snapper (repère ENU, mètres). */
export interface CentreASnapper {
  cx: number;
  cy: number;
}

/**
 * CAL106 — RÉFÉRENCE : le balayage linéaire historique, extrait tel quel pour
 * que le test puisse confronter la version rapide à la sémantique d'origine.
 * Ce n'est pas du code mort : c'est l'étalon de l'équivalence.
 */
export function resnapNaif(
  cells: readonly { index: number; cx: number; cy: number }[],
  centres: readonly CentreASnapper[],
): number[] {
  const occupees = new Set<number>();
  const retenus: number[] = [];
  for (const p of centres) {
    let best = -1;
    let bestD = Infinity;
    for (const c of cells) {
      if (occupees.has(c.index)) continue;
      const dx = c.cx - p.cx;
      const dy = c.cy - p.cy;
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = c.index;
      }
    }
    if (best >= 0) {
      occupees.add(best);
      retenus.push(best);
    }
  }
  return retenus;
}

/** Taille de case de l'index (m). Une case ≈ une travée : assez grande pour que
 *  le voisinage utile tienne en un ou deux anneaux, assez petite pour élaguer. */
const CASE_RESNAP_M = 4;

/**
 * CAL106 — re-snap en masse INDEXÉ. Rend les index de cellules occupées, dans
 * l'ordre des centres — strictement les mêmes que `resnapNaif`.
 */
export function resnapEnMasse(
  cells: readonly { index: number; cx: number; cy: number }[],
  centres: readonly CentreASnapper[],
): number[] {
  if (!cells.length || !centres.length) return [];

  // Rang de chaque cellule dans l'ORDRE DE LA LATTICE : c'est lui qui départage
  // à distance égale, comme le fait le balayage linéaire.
  const rang = new Map<number, number>();
  for (let i = 0; i < cells.length; i++) rang.set(cells[i].index, i);

  /* Clé de case NUMÉRIQUE : une `Map<number, …>` évite de fabriquer une chaîne
     à chaque sondage d'anneau — mesurable sur un grand champ. */
  const DECALAGE = 1_000_000;
  const cle = (ix: number, iy: number) => (ix + DECALAGE) * 4_000_000 + (iy + DECALAGE);
  const cases = new Map<number, number[]>(); // case → positions dans `cells`
  const cleDe = new Float64Array(cells.length);
  for (let i = 0; i < cells.length; i++) {
    const k = cle(Math.floor(cells[i].cx / CASE_RESNAP_M), Math.floor(cells[i].cy / CASE_RESNAP_M));
    cleDe[i] = k;
    const seau = cases.get(k);
    if (seau) seau.push(i);
    else cases.set(k, [i]);
  }

  // Portée maximale utile : les cases EXTRÊMES de la lattice. Elle est calculée
  // PAR CENTRE, parce qu'un centre peut tomber très loin de la lattice (un
  // dossier rechargé dans un autre repère) : une portée mesurée sur la seule
  // emprise de la lattice s'arrêterait avant de l'avoir atteinte, et rendrait
  // « aucune cellule » là où le balayage linéaire en trouvait une.
  let ixMin = Infinity; let ixMax = -Infinity; let iyMin = Infinity; let iyMax = -Infinity;
  for (const c of cells) {
    const ix = Math.floor(c.cx / CASE_RESNAP_M);
    const iy = Math.floor(c.cy / CASE_RESNAP_M);
    if (ix < ixMin) ixMin = ix;
    if (ix > ixMax) ixMax = ix;
    if (iy < iyMin) iyMin = iy;
    if (iy > iyMax) iyMax = iy;
  }

  const retenus: number[] = [];

  for (const p of centres) {
    const cx0 = Math.floor(p.cx / CASE_RESNAP_M);
    const cy0 = Math.floor(p.cy / CASE_RESNAP_M);
    let best = -1;
    let bestRang = Infinity;
    let bestD = Infinity;
    // Assez d'anneaux pour couvrir TOUTE la lattice depuis CE centre.
    const anneauMax = Math.max(
      Math.abs(cx0 - ixMin), Math.abs(cx0 - ixMax),
      Math.abs(cy0 - iyMin), Math.abs(cy0 - iyMax),
    ) + 1;

    const examiner = (ix: number, iy: number) => {
      const seau = cases.get(cle(ix, iy));
      if (!seau) return;
      // Un seau ne contient QUE des cellules encore libres (voir le retrait
      // plus bas) : plus aucun test d'occupation n'est nécessaire ici.
      for (let j = 0; j < seau.length; j++) {
        const pos = seau[j];
        const c = cells[pos];
        const dx = c.cx - p.cx;
        const dy = c.cy - p.cy;
        const d = dx * dx + dy * dy;
        // `<` strict pour la distance ; à ÉGALITÉ, le rang le plus petit gagne
        // — le même départage que le balayage linéaire d'origine.
        if (d < bestD || (d === bestD && pos < bestRang)) {
          bestD = d;
          best = c.index;
          bestRang = pos;
        }
      }
    };

    for (let r = 0; r <= anneauMax; r++) {
      if (r === 0) examiner(cx0, cy0);
      else {
        for (let ix = cx0 - r; ix <= cx0 + r; ix++) {
          examiner(ix, cy0 - r);
          examiner(ix, cy0 + r);
        }
        for (let iy = cy0 - r + 1; iy <= cy0 + r - 1; iy++) {
          examiner(cx0 - r, iy);
          examiner(cx0 + r, iy);
        }
      }
      // Distance minimale garantie de l'anneau SUIVANT : si le meilleur trouvé
      // est déjà plus proche, aucun anneau plus loin ne peut faire mieux.
      if (best >= 0) {
        const plancher = r * CASE_RESNAP_M;
        if (bestD <= plancher * plancher) break;
      }
    }

    if (best >= 0) {
      /* La cellule prise SORT de son seau : les centres suivants ne la
         reverront jamais. Sans ce retrait, les derniers centres re-balaient
         les cellules déjà occupées et le coût remonte au N² qu'on supprime —
         mesuré sur 2 000 centres / 2 000 cellules (le pire cas : la lattice
         finit saturée) : 154 ms AVEC re-balayage — donc PLUS LENT que les
         ~120 ms du balayage linéaire, l'index était devenu un ralentisseur —
         contre 20-48 ms une fois les cellules prises retirées de l'index. */
      const seau = cases.get(cleDe[bestRang]);
      if (seau) {
        const j = seau.indexOf(bestRang);
        if (j >= 0) {
          seau[j] = seau[seau.length - 1];
          seau.pop();
          if (!seau.length) cases.delete(cleDe[bestRang]);
        }
      }
      retenus.push(best);
    }
  }
  return retenus;
}

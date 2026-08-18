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
  rowMembers,
  moveRowBy,
  nudgeAzimuthDeg,
} from '../../lib/layoutVariability';
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
import { type ProdConfig } from './types';
import { createLayoutHistory, createValueHistory } from './layoutHistory';
// PV30 — placement libre : géométrie PURE + pont vers le pavage gagnant.
import {
  moveFreePanels,
  addFreePanel,
  removeFreePanel,
  checkPanelAt,
  findFreeSpot,
  copyFreeState,
  toUV,
  type FreeGeom,
  type FreeCheck,
  type FreeLayoutState,
  type FreeViolation,
  type FreeMargins,
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

  // PV25 — ÉTAT de la sélection multiple. Il vit dans ce module (rien à ajouter au ctx
  // partagé) : c'est une intention d'édition, pas un état de design.
  let selection: number[] = [];
  /** Mode « sélection » (tactile) : le glissé trace un rectangle au lieu de déplacer. */
  let selectMode = false;
  /** Mode « rangée » : le glissé sur un panneau emmène TOUTE sa rangée (axe contraint). */
  let rowMode = false;
  /** Marquee en cours (coin de départ en ENU) ou null. `moved` : le doigt/la souris a-t-il
   *  franchi le seuil de glissé ? (PV29 — sinon le geste est un Maj + CLIC, pas un cadre.) */
  let marquee: { x0: number; y0: number; x1: number; y1: number; moved: boolean; startPoint: maplibregl.Point } | null = null;
  /** Tolérance de « snap » d'un déplacement de groupe/rangée : chaque membre doit
   *  atterrir à moins d'un DEMI-panneau de l'endroit visé. Au-delà, le geste sort du toit
   *  (ou le groupe se replierait n'importe où) → refus, et rien ne bouge. */
  const GROUP_SNAP_M = PANEL2_LONG_M / 2;
  /** Pas du nudge d'azimut (°) — jamais un arrondi imposé, juste l'incrément du bouton. */
  const AZIMUTH_NUDGE_DEG = 1;
  /** PV29 — durée du clignotement ROUGE d'un déplacement REFUSÉ (ms). */
  const REFUSAL_FLASH_MS = 900;

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

  /** Panneaux libres dont le centre tombe dans le rectangle ENU (marquee). */
  function freeInRect(rect: { x0: number; y0: number; x1: number; y1: number }): number[] {
    const st = freeState();
    if (!st) return [];
    const xMin = Math.min(rect.x0, rect.x1);
    const xMax = Math.max(rect.x0, rect.x1);
    const yMin = Math.min(rect.y0, rect.y1);
    const yMax = Math.max(rect.y0, rect.y1);
    const out: number[] = [];
    for (let i = 0; i < st.panels.length; i++) {
      const p = st.panels[i];
      if (p.cx < xMin || p.cx > xMax || p.cy < yMin || p.cy > yMax) continue;
      out.push(i);
    }
    return out;
  }

  /** Membres de la RANGÉE d'un panneau libre : ceux qui partagent sa coordonnée
   *  d'empilement `v` (dans le repère du pavage) à une demi-profondeur près. La rangée
   *  reste une notion géométrique réelle, même sans lattice. */
  function freeRowMembers(idx: number): number[] {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || idx < 0 || idx >= st.panels.length) return [];
    const refV = toUV(g, st.panels[idx].cx, st.panels[idx].cy)[1];
    const tol = g.depthM / 2;
    const out: number[] = [];
    for (let i = 0; i < st.panels.length; i++) {
      const v = toUV(g, st.panels[i].cx, st.panels[i].cy)[1];
      if (Math.abs(v - refV) <= tol) out.push(i);
    }
    return out;
  }

  /** Déplace la sélection libre de (dx, dy) mètres — rigide, tout ou rien. */
  function freeMoveSelection(dx: number, dy: number, members: readonly number[]): boolean {
    const st = freeState();
    const g = freeGeom();
    if (!st || !g || !members.length) return false;
    recordFreeHistory();
    const res = moveFreePanels(st, g, members, quantizeFree(dx), quantizeFree(dy), margins());
    if (!res.ok) {
      freeHistory.drop();
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
      freeHistory.drop();
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
      freeHistory.drop();
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
  }
  /** Ré-applique une occupation photographiée + re-rend (3D, chiffres, plan). */
  function applySnapshot(snapshot: number[]) {
    const st = ctx.layoutState;
    if (!st) return;
    st.occupied.clear();
    for (const i of snapshot) if (i >= 0 && i < st.cells.length) st.occupied.add(i);
    ctx.layoutSel = null;
    pruneSelection();
    renderCustomLayout();
    renderLayoutPanel();
  }
  /** PV30 — ré-applique une photo de PLACEMENT LIBRE (positions continues). */
  function applyFreeSnapshot(snap: FreeLayoutState) {
    ctx.freeState = snap;
    ctx.layoutSel = null;
    pruneSelection();
    renderCustomLayout();
    renderLayoutPanel();
  }
  function undo(): boolean {
    // PV30 — chaque mode a sa pile ; on annule TOUJOURS dans le mode où l'on se trouve.
    if (freeActive()) {
      const prev = freeHistory.undo(ctx.freeState!);
      if (!prev) return false;
      applyFreeSnapshot(prev);
      if (layoutNoteEl) layoutNoteEl.textContent = `Action annulée — ${fmt(ctx.freeState!.panels.length)} panneaux posés.`;
      return true;
    }
    const st = ctx.layoutState;
    if (!st) return false;
    const prev = history.undo(st.occupied);
    if (!prev) return false;
    applySnapshot(prev);
    if (layoutNoteEl) layoutNoteEl.textContent = `Action annulée — ${fmt(st.occupied.size)} panneaux posés.`;
    return true;
  }
  function redo(): boolean {
    if (freeActive()) {
      const next = freeHistory.redo(ctx.freeState!);
      if (!next) return false;
      applyFreeSnapshot(next);
      if (layoutNoteEl) layoutNoteEl.textContent = `Action rétablie — ${fmt(ctx.freeState!.panels.length)} panneaux posés.`;
      return true;
    }
    const st = ctx.layoutState;
    if (!st) return false;
    const next = history.redo(st.occupied);
    if (!next) return false;
    applySnapshot(next);
    if (layoutNoteEl) layoutNoteEl.textContent = `Action rétablie — ${fmt(st.occupied.size)} panneaux posés.`;
    return true;
  }

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
      const grid = { ...ctx.layoutPlan.grid, panels: st.panels.map((p) => ({ ...p })), count: st.panels.length };
      const all = new Set(st.panels.map((_, i) => i));
      renderScene(ctx.layoutPlan.pack, grid, ctx.layoutPlan.tiltDeg, ctx.layoutPlan.family, st.panels.length, ctx.layoutPlan.flush, all);
      const cfgFree = prodConfigFromState();
      if (cfgFree) updateProductionWindow({ ...cfgFree, panels: st.panels.length });
      snapshotActiveAreaResult();
      renderAreasPanel();
      paintScene();
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
      layoutNoteEl.textContent = freeOn
        ? 'Placement libre : clic = sélectionner, Maj + clic = ajouter au groupe, double-clic = toute la rangée. Glissez pour déplacer au millimètre, flèches pour ajuster, Alt + clic pour retirer. « Ajouter un panneau » puis un clic pose un panneau de plus.'
        : 'Sur la 3D : clic = sélectionner, Maj + clic = ajouter au groupe, Maj + glissé = encadrer, double-clic = toute la rangée. Glissez pour déplacer, flèches pour ajuster, Alt + clic pour retirer un panneau. Ou touchez un panneau (bleu) puis un emplacement libre (vert) dans le plan ci-dessous.';
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
      const next = selection.includes(cellIndex) ? selection.filter((i) => i !== cellIndex) : [...selection, cellIndex];
      setSelection(next);
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
    // PV26/PV30 — l'historique reflété est celui du MODE courant.
    const hist = freeActive() ? freeHistory : history;
    if (layoutUndoBtn) layoutUndoBtn.disabled = !hist.canUndo();
    if (layoutRedoBtn) layoutRedoBtn.disabled = !hist.canRedo();
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
      for (const p of st.panels) {
        const idx = nearestEmptyCell(lat, p.cx, p.cy);
        if (idx >= 0) lat.occupied.add(idx);
      }
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
    for (const c of prevCenters) {
      const idx = nearestEmptyCell(st, c.cx, c.cy);
      if (idx >= 0) st.occupied.add(idx);
    }
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
    let placed = 0;
    for (const c of centers) {
      const idx = nearestEmptyCell(st, c.cx + dx, c.cy + dy);
      if (idx >= 0) {
        st.occupied.add(idx);
        placed++;
      }
    }
    ctx.layoutSel = null;
    setSelection([]);
    history.clear(); // une hydratation est un POINT DE DÉPART, pas une action annulable
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
      if (!hydrated) history.clear(); // PV26 — historique propre pour une nouvelle session
      setSelection([]);
      renderCustomLayout();
    } else {
      // En sortant, on re-rend la disposition de l'optimiseur (recalc rebranche tout).
      ctx.layoutSel = null;
      setSelection([]); // PV29 — une sélection ne survit pas à la sortie du mode
      setPanelHighlight(null); // W88 — efface tout surlignage de panneau en quittant le mode
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
  let layoutDrag: { from: number; startPoint: maplibregl.Point; moved: boolean; altKey: boolean } | null = null;
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
  function beginLayoutDrag(point: maplibregl.Point, shiftKey = false, altKey = false): boolean {
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
    // PV25 — MARQUEE : Maj + glissé (souris) ou mode « sélection multiple » (doigt) trace
    // un rectangle au lieu de déplacer un panneau. Le rectangle est en ENU (mètres), via
    // la MÊME déprojection écran→toit que le reste de l'éditeur — aucun second système.
    if (shiftKey || selectMode) {
      const enu = screenToENU(point);
      if (!enu) return false;
      // PV29 — `moved` distingue un Maj + GLISSÉ (rectangle) d'un Maj + CLIC (bascule d'un
      // seul panneau dans la sélection). Avant, un Maj + clic terminait sur un rectangle de
      // surface nulle et VIDAIT donc la sélection — l'inverse de ce que le geste veut dire.
      marquee = { x0: enu.x, y0: enu.y, x1: enu.x, y1: enu.y, moved: false, startPoint: point };
      map.dragPan.disable();
      map.getCanvas().style.cursor = 'crosshair';
      return true;
    }
    const from = layoutPanelAt(point);
    if (from == null) return false;
    layoutDrag = { from, startPoint: point, moved: false, altKey };
    ctx.layoutSel = from;
    map.dragPan.disable();
    map.getCanvas().style.cursor = 'grabbing';
    renderLayoutPanel();
    return true;
  }
  /** Glissé en cours (souris OU doigt) : au-delà du seuil LAYOUT_GRAB_PX, retour visuel
   *  « relâchez sur un emplacement valide / aucun libre ». Le seuil évite qu'un simple
   *  tap/clic ne fasse sauter le panneau vers la cellule vide la plus proche. */
  function moveLayoutDrag(point: maplibregl.Point) {
    // PV25 — marquee en cours : on met à jour le coin opposé et on annonce le compte.
    if (marquee && ctx.layoutState) {
      const enu = screenToENU(point);
      if (!enu) return;
      marquee.x1 = enu.x;
      marquee.y1 = enu.y;
      // PV29 — au-delà du seuil, c'est un vrai cadre (et plus un Maj + clic).
      if (Math.abs(point.x - marquee.startPoint.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - marquee.startPoint.y) >= LAYOUT_GRAB_PX) {
        marquee.moved = true;
      }
      const hits = freeActive() ? freeInRect(marquee) : cellsInRect(ctx.layoutState, marquee);
      if (layoutNoteEl) {
        layoutNoteEl.textContent = hits.length
          ? `${fmt(hits.length)} panneaux dans la sélection — relâchez pour les sélectionner.`
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
      const st = ctx.freeState!;
      const g = freeGeom();
      const from = layoutDrag.from;
      if (g && st.panels[from]) {
        const chk = checkPanelAt(st, g, from, quantizeFree(enu.x), quantizeFree(enu.y), margins());
        showMeasure(chk);
        if (layoutNoteEl) {
          layoutNoteEl.textContent = chk.ok
            ? `Relâchez pour poser — rive ${cm(chk.edgeM)}, voisin ${chk.panelM === null ? '—' : cm(chk.panelM)}.`
            : `Ici : ${chk.violations.map(violationLabel).join(', ')}.`;
        }
      }
      return;
    }
    const target = nearestEmptyCell(ctx.layoutState, enu.x, enu.y);
    if (layoutNoteEl) layoutNoteEl.textContent = target >= 0 ? 'Relâchez sur un emplacement valide (vert).' : 'Aucun emplacement libre — il reviendra à sa place.';
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
    // PV25 — fin d'un MARQUEE : la sélection devient les panneaux du rectangle.
    if (marquee && ctx.layoutState) {
      const enu = screenToENU(point);
      if (enu) {
        marquee.x1 = enu.x;
        marquee.y1 = enu.y;
      }
      const dragged = marquee.moved;
      const hits = freeActive() ? freeInRect(marquee) : cellsInRect(ctx.layoutState, marquee); // PV30
      marquee = null;
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
      setSelection(hits);
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
    if (moved && freeActive()) {
      // PV30 — commit d'un glissé LIBRE : translation rigide de toute la sélection (ou du
      // seul panneau saisi), quantifiée au centimètre. Tout ou rien, refus visible.
      const enu = screenToENU(point);
      const st = ctx.freeState!;
      const grabbed = st.panels[from];
      if (enu && grabbed) {
        const members = selection.length > 1 && selection.includes(from) ? selection : [from];
        freeMoveSelection(enu.x - grabbed.cx, enu.y - grabbed.cy, members);
      }
      layoutDrag = null;
      ctx.layoutSel = null;
      map.dragPan.enable();
      map.getCanvas().style.cursor = '';
      return;
    }
    if (moved) {
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
          } else {
            dropHistoryPhoto(); // PV29 — un geste refusé n'est pas une action à annuler
            flashRefusal(members); // PV29 — refus VISIBLE (rouge), rien n'a bougé
            if (layoutNoteEl) layoutNoteEl.textContent = 'La rangée ne tient pas à cet endroit — rien n’a bougé.';
          }
        } else if (selection.length > 1 && selection.includes(from)) {
          const res = moveGroup(ctx.layoutState, selection, dx, dy, { maxSnapM: GROUP_SNAP_M });
          if (res.ok) {
            setSelection(res.targets);
            if (layoutNoteEl) layoutNoteEl.textContent = `Groupe déplacé — ${fmt(res.targets.length)} panneaux.`;
            renderCustomLayout();
          } else {
            dropHistoryPhoto(); // PV29
            flashRefusal(selection); // PV29
            if (layoutNoteEl) layoutNoteEl.textContent = 'Le groupe entier ne tient pas à cet endroit — rien n’a bougé.';
          }
        } else {
          const res = movePanelToPoint(ctx.layoutState, from, enu.x, enu.y);
          if (res.ok && res.toIndex !== from) {
            setSelection([res.toIndex]); // PV29 — le panneau déplacé reste sélectionné
            if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
            renderCustomLayout();
          } else {
            dropHistoryPhoto(); // PV29
            flashRefusal([from]); // PV29
            if (layoutNoteEl) {
              layoutNoteEl.textContent = 'Aucun emplacement libre à cet endroit — le panneau est resté en place.';
            }
          }
        }
      }
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
      selectSinglePanel(from);
      return;
    }
    renderLayoutPanel();
  }

  // — Souris —
  map.on('mousedown', (e) => {
    // PV25 — Maj + glissé = rectangle de sélection (marquee) au lieu d'un déplacement.
    // PV29 — Alt = modificateur de SUPPRESSION (un clic nu sélectionne désormais).
    const shift = !!(e.originalEvent as MouseEvent | undefined)?.shiftKey;
    const alt = !!(e.originalEvent as MouseEvent | undefined)?.altKey;
    if (beginLayoutDrag(e.point, shift, alt)) e.preventDefault();
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
    if (layoutDrag || marquee) {
      moveLayoutDrag(e.point);
      return;
    }
    // W88 — survol : surligne (or) le panneau sous le curseur en mode disposition, sinon rien.
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return;
    setPanelHighlight(layoutPanelAt(e.point));
  });
  map.on('mouseup', (e) => endLayoutDrag(e.point, true)); // clic sans glissé = supprimer (W88)
                                                          // PV25 — un marquee en cours est committé par le même chemin.

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
          layoutDrag = null;
          map.dragPan.enable();
          map.getCanvas().style.cursor = '';
          removePanelInScene(cell);
        }
      }, LONG_PRESS_MS);
    }
  });
  map.on('touchmove', (e) => {
    if (!layoutDrag && !marquee) return;
    e.preventDefault();
    moveLayoutDrag(e.point);
    if (layoutDrag?.moved) cancelLongPress(); // un glissé annule l'appui long (c'est un déplacement)
  });
  map.on('touchend', (e) => {
    cancelLongPress(); // tap bref / fin de glissé : pas de suppression par appui long
    if (!layoutDrag && !marquee) return;
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
  };
}

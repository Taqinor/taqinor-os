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
    setPanelHighlight,
  } = deps;
  const opts = ctx.opts;

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
    if (!ctx.layoutPlan || !ctx.layoutState) return;
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

    const count = occupiedCount(layoutState);
    const free = emptyIndices(layoutState).length;
    const kwc = count * PANEL_KWC;
    if (layoutCountEl) layoutCountEl.textContent = fmt(count);
    if (layoutKwcEl) layoutKwcEl.textContent = `${fmt1(kwc)} kWc`;
    if (layoutFreeEl) layoutFreeEl.textContent = fmt(free);
    const cover = ctx.neededPanels > 0 ? Math.round((count / ctx.neededPanels) * 100) : 0;
    if (layoutCoverEl) layoutCoverEl.textContent = ctx.neededPanels > 0 ? `${cover} %` : '—';
    if (layoutMinusEl) layoutMinusEl.disabled = count <= 0;
    if (layoutPlusEl) layoutPlusEl.disabled = free <= 0 || count >= layoutCap();
    // WJ20 — « Remplir » n'a de sens que s'il reste des cellules libres.
    if (layoutFillEl) layoutFillEl.disabled = free <= 0;

    // Mini-plan des cellules : occupées (bleu) / libres (gris→vert au survol).
    if (layoutGridEl) {
      layoutGridEl.innerHTML = layoutState.cells
        .map((c) => {
          const occupied = layoutState.occupied.has(c.index);
          const selected = ctx.layoutSel === c.index;
          return `<button type="button" class="rp9-layout-cell" data-cell="${c.index}" data-occupied="${occupied}" aria-pressed="${selected}" aria-label="${occupied ? 'Panneau' : 'Emplacement libre'} ${c.index + 1}"></button>`;
        })
        .join('');
    }
    if (layoutNoteEl && !layoutNoteEl.textContent) {
      layoutNoteEl.textContent = 'Touchez un panneau (bleu) pour le sélectionner, puis un emplacement libre (vert) pour l’y déplacer. Ou utilisez + / −.';
    }
  }

  /** W79 — centres ENU des cellules POSÉES de la disposition courante. Capturé AVANT un
   *  recalc (qui va remplacer la lattice et nuller layoutState) pour pouvoir re-snapper la
   *  même intention de placement sur la nouvelle lattice. [] si pas de disposition. */
  function occupiedCenters(): { cx: number; cy: number }[] {
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
      ctx.layoutState = null; // repart de l'optimum courant
      ensureLayoutState();
      renderCustomLayout();
    } else {
      // En sortant, on re-rend la disposition de l'optimiseur (recalc rebranche tout).
      ctx.layoutSel = null;
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
    resetToOptimal(ctx.layoutState, ctx.layoutOptimalCount);
    ctx.layoutSel = null;
    if (layoutNoteEl) layoutNoteEl.textContent = `Disposition optimale restaurée — ${occupiedCount(ctx.layoutState)} panneaux.`;
    renderCustomLayout();
    renderLayoutPanel();
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
  let layoutDrag: { from: number; startPoint: maplibregl.Point; moved: boolean } | null = null;
  function layoutPanelAt(point: maplibregl.Point): number | null {
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
  function beginLayoutDrag(point: maplibregl.Point): boolean {
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return false;
    const from = layoutPanelAt(point);
    if (from == null) return false;
    layoutDrag = { from, startPoint: point, moved: false };
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
    if (!layoutDrag || !ctx.layoutState) return;
    if (!layoutDrag.moved && (Math.abs(point.x - layoutDrag.startPoint.x) >= LAYOUT_GRAB_PX || Math.abs(point.y - layoutDrag.startPoint.y) >= LAYOUT_GRAB_PX)) {
      layoutDrag.moved = true;
    }
    if (!layoutDrag.moved) return;
    const enu = screenToENU(point);
    if (!enu) return;
    const target = nearestEmptyCell(ctx.layoutState, enu.x, enu.y);
    if (layoutNoteEl) layoutNoteEl.textContent = target >= 0 ? 'Relâchez sur un emplacement valide (vert).' : 'Aucun emplacement libre — il reviendra à sa place.';
  }
  /** W88 — SUPPRIME le panneau de la cellule `cellIndex` directement depuis la 3D (clic
   *  desktop / appui long tactile), puis recompute les chiffres (renderCustomLayout). Efface
   *  tout surlignage. No-op si la cellule n'est pas occupée. */
  function removePanelInScene(cellIndex: number) {
    if (!ctx.layoutState) return;
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
    if (!layoutDrag || !ctx.layoutState) return;
    const from = layoutDrag.from;
    const moved = layoutDrag.moved;
    if (moved) {
      const enu = screenToENU(point);
      if (enu) {
        const res = movePanelToPoint(ctx.layoutState, from, enu.x, enu.y);
        if (res.ok && res.toIndex !== from) {
          if (layoutNoteEl) layoutNoteEl.textContent = 'Panneau déplacé.';
          renderCustomLayout();
        } else if (layoutNoteEl) {
          layoutNoteEl.textContent = 'Aucun emplacement libre à cet endroit — le panneau est resté en place.';
        }
      }
    }
    layoutDrag = null;
    ctx.layoutSel = null;
    map.dragPan.enable();
    map.getCanvas().style.cursor = '';
    // W88 — clic desktop sans glissé sur un panneau = suppression ciblée de CE panneau.
    if (!moved && removeOnTap) {
      removePanelInScene(from);
      return;
    }
    renderLayoutPanel();
  }

  // — Souris —
  map.on('mousedown', (e) => {
    if (beginLayoutDrag(e.point)) e.preventDefault();
  });
  map.on('mousemove', (e) => {
    if (layoutDrag) {
      moveLayoutDrag(e.point);
      return;
    }
    // W88 — survol : surligne (or) le panneau sous le curseur en mode disposition, sinon rien.
    if (!ctx.layoutMode || isObstacleMode() || !ctx.layoutState) return;
    setPanelHighlight(layoutPanelAt(e.point));
  });
  map.on('mouseup', (e) => endLayoutDrag(e.point, true)); // clic sans glissé = supprimer (W88)

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
    if (!layoutDrag) return;
    e.preventDefault();
    moveLayoutDrag(e.point);
    if (layoutDrag.moved) cancelLongPress(); // un glissé annule l'appui long (c'est un déplacement)
  });
  map.on('touchend', (e) => {
    cancelLongPress(); // tap bref / fin de glissé : pas de suppression par appui long
    if (!layoutDrag) return;
    endLayoutDrag(e.point); // tactile : pas de suppression sur tap bref (removeOnTap=false)
  });

  return { layoutCap, ensureLayoutState, renderCustomLayout, screenToENU, renderLayoutPanel, setLayoutMode, occupiedCenters, reenterCustomLayout };
}

// @vitest-environment jsdom
//
// PV29 — ÉDITION MANUELLE du calepinage 3D par un opérateur ERP (ordre fondateur du
// 18/08 : « le PV doit pouvoir être déplacé à la main, par rangée ou par paquet »).
//
// Ce fichier teste les GESTES au travers du vrai câblage (`createLayoutEditor`), pas de la
// lib pure : sélection d'un panneau au clic, bascule au Maj + clic, rangée entière au
// double-clic, déplacement rigide d'un groupe/rangée quantifié sur le pas du calepinage,
// refus VISIBLE quand ça ne tient pas, invariant de COMPTAGE, et l'échafaudage de secours
// qui rend la fenêtre joignable sur un hôte qui ne la fournit pas (l'écran ERP).
//
// Harnais : celui de tests/layoutEditorSelectionPV25.test.ts (ctx minimal + carte stub qui
// déprojette 10 px → 1 m), avec une lattice au pas de 3 m — plus large que la tolérance de
// snap d'un groupe (GROUP_SNAP_M = PANEL2_LONG_M / 2 ≈ 1,19 m), donc un membre ne peut
// atterrir QUE sur sa cellule translatée exacte : la rigidité est réellement mise à
// l'épreuve, elle n'est pas un artefact d'une grille trop serrée.
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';
import { parseRoofLayout } from '../src/lib/proposition';
import { buildViewerFullPlan, zoneRenderPlan } from '../src/scripts/roofPro11/viewerFullModel';
import { PANEL2_SHORT_M } from '../src/lib/roofPro2';
import { DEG2M as DEG2M_CONST } from '../src/scripts/roofPro11/constants';

const DEG2M = (Math.PI / 180) * 6378137;
const ORIGIN: [number, number] = [-7.62, 33.59];
const PX_PER_M = 10;
/** Pas de la lattice de test (m) : 4 colonnes × 3 rangées. */
const STEP_M = 3;
const COLS = 4;
const ROWS = 3;

const IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid',
  'rp9-layout-note', 'rp9-layout-azimuth', 'rp9-layout-az-value',
];
const BTN_IDS = [
  'rp9-layout-minus', 'rp9-layout-plus', 'rp9-layout-reset', 'rp9-layout-fill',
  'rp9-layout-select', 'rp9-layout-row', 'rp9-layout-clear-sel',
  'rp9-layout-az-minus', 'rp9-layout-az-plus', 'rp9-layout-undo', 'rp9-layout-redo',
];

function setupDom() {
  document.body.innerHTML = '';
  document.getElementById('rp9-layout-fallback-style')?.remove();
  for (const id of IDS) {
    const e = document.createElement('div');
    e.id = id;
    document.body.appendChild(e);
  }
  for (const id of BTN_IDS) {
    const b = document.createElement('button');
    b.id = id;
    document.body.appendChild(b);
  }
}

/** Carte stub : mémorise les handlers pour rejouer des gestes, et déprojette 10 px → 1 m. */
function makeMap(container?: HTMLElement) {
  const handlers: Record<string, ((e: unknown) => void)[]> = {};
  return {
    handlers,
    on(ev: string, fn: (e: unknown) => void) {
      (handlers[ev] ??= []).push(fn);
    },
    emit(ev: string, e: unknown) {
      for (const fn of handlers[ev] ?? []) fn(e);
    },
    jumpTo() {},
    easeTo() {},
    once() {},
    dragPan: { enable() {}, disable() {} },
    getCanvas: () => ({ style: {} as Record<string, string> }),
    ...(container ? { getContainer: () => container } : {}),
    unproject: (p: { x: number; y: number }) => ({
      lng: ORIGIN[0] + p.x / PX_PER_M / (DEG2M * Math.cos(ORIGIN[1] * (Math.PI / 180))),
      lat: ORIGIN[1] + p.y / PX_PER_M / DEG2M,
    }),
  };
}

/** Lattice COLS × ROWS au pas de STEP_M, toutes cellules posées (index = r * COLS + c). */
function seedPlan(): LayoutPlan {
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) panels.push({ cx: c * STEP_M, cy: r * STEP_M });
  return {
    pack: { origin: ORIGIN } as never,
    grid: {
      count: panels.length,
      kwc: panels.length * PANEL_KWC,
      panels,
      // Les pas RÉELS du pavage : c'est sur eux que l'éditeur quantifie un déplacement de
      // groupe (et sur eux que les flèches nudgent) — jamais un pas inventé.
      rowWidthM: STEP_M,
      rowPitchM: STEP_M,
    } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

const TOTAL = COLS * ROWS;

function makeCtx(over: Partial<Ctx> = {}): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: true,
    layoutState: null,
    layoutPlan: seedPlan(),
    layoutOptimalCount: TOTAL,
    layoutSel: null,
    neededPanels: TOTAL,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
    ...over,
  } as unknown as Ctx;
}

/** Trace des appels de peinture 3D (sélection / survol / refus). */
type PaintCall = { selected: number[]; hover: number | null; refused: boolean };

function makeEditor(ctx: Ctx, map: ReturnType<typeof makeMap>, paints: PaintCall[]) {
  return createLayoutEditor(ctx, {
    map: map as never,
    renderScene: () => {},
    prodConfigFromState: () => null,
    updateProductionWindow: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
    setPanelSelection: (selected, hover, refused) => {
      paints.push({ selected: [...(selected ?? [])], hover, refused });
    },
    recalcWithReenter: () => {},
  });
}

const pt = (xM: number, yM: number) => ({ x: xM * PX_PER_M, y: yM * PX_PER_M });
/** Centre écran de la cellule d'index `i`. */
const cellPt = (i: number) => pt((i % COLS) * STEP_M, Math.floor(i / COLS) * STEP_M);
const occ = (ctx: Ctx) => [...ctx.layoutState!.occupied].sort((a, b) => a - b);
const note = () => document.getElementById('rp9-layout-note')?.textContent ?? '';

let map: ReturnType<typeof makeMap>;
let ctx: Ctx;
let paints: PaintCall[];
let editor: ReturnType<typeof createLayoutEditor>;

beforeEach(() => {
  setupDom();
  map = makeMap();
  ctx = makeCtx();
  paints = [];
  editor = makeEditor(ctx, map, paints);
  editor.ensureLayoutState();
  editor.renderLayoutPanel();
});

/** Rejoue un clic (mousedown + mouseup au MÊME point : aucun glissé). */
function click(point: { x: number; y: number }, mods: { shiftKey?: boolean; altKey?: boolean } = {}) {
  map.emit('mousedown', { point, originalEvent: mods, preventDefault() {} });
  map.emit('mouseup', { point });
}
/** Rejoue un glissé (mousedown → mousemove → mouseup). */
function drag(from: { x: number; y: number }, to: { x: number; y: number }, mods: { shiftKey?: boolean } = {}) {
  map.emit('mousedown', { point: from, originalEvent: mods, preventDefault() {} });
  map.emit('mousemove', { point: to });
  map.emit('mouseup', { point: to });
}

describe('PV29 — sélectionner UN panneau au clic (et ne plus le supprimer par accident)', () => {
  it('un clic simple SÉLECTIONNE le panneau et ne change PAS le comptage', () => {
    click(cellPt(5));
    expect(editor.selection()).toEqual([5]);
    expect(ctx.layoutState!.occupied.size).toBe(TOTAL); // invariant : le clic ne retire rien
    expect(note()).toContain('Panneau sélectionné');
  });

  it('la SUPPRESSION ciblée demande Alt + clic (le geste destructeur est explicite)', () => {
    click(cellPt(5), { altKey: true });
    expect(ctx.layoutState!.occupied.has(5)).toBe(false);
    expect(ctx.layoutState!.occupied.size).toBe(TOTAL - 1);
    expect(note()).toContain('supprimé');
  });

  it('Maj + clic BASCULE le panneau dans la sélection (ajout puis retrait)', () => {
    click(cellPt(0));
    click(cellPt(1), { shiftKey: true });
    expect(editor.selection()).toEqual([0, 1]);
    click(cellPt(1), { shiftKey: true });
    expect(editor.selection()).toEqual([0]);
    expect(ctx.layoutState!.occupied.size).toBe(TOTAL);
  });

  it('Maj + GLISSÉ reste le rectangle de sélection (aucune régression PV25)', () => {
    drag(pt(-1, -1), pt(STEP_M + 1, 1), { shiftKey: true });
    expect(editor.selection()).toEqual([0, 1]);
  });

  it('Échap efface la sélection', () => {
    editor.setSelection([0, 1, 2]);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(editor.selection()).toEqual([]);
    expect(note()).toContain('Sélection effacée');
  });
});

describe('PV29 — prendre TOUTE UNE RANGÉE en un seul geste (double-clic)', () => {
  it('le double-clic sur un panneau sélectionne les 4 panneaux de sa rangée', () => {
    map.emit('dblclick', { point: cellPt(1), preventDefault() {} });
    expect(editor.selection()).toEqual([0, 1, 2, 3]);
    expect(note()).toContain('Rangée sélectionnée');
  });

  it('sur une rangée déjà trouée, seuls les panneaux POSÉS sont pris', () => {
    ctx.layoutState!.occupied.delete(2);
    map.emit('dblclick', { point: cellPt(1), preventDefault() {} });
    expect(editor.selection()).toEqual([0, 1, 3]);
  });

  it('un double-clic dans le vide ne sélectionne rien', () => {
    map.emit('dblclick', { point: pt(50, 50), preventDefault() {} });
    expect(editor.selection()).toEqual([]);
  });
});

describe('PV29 — déplacer la rangée / le groupe : RIGIDE et à comptage constant', () => {
  it('la rangée entière monte d’un pas et garde sa forme', () => {
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i); // rangée du haut libre
    map.emit('dblclick', { point: cellPt(0), preventDefault() {} });
    drag(cellPt(0), pt(0, 2 * STEP_M));
    expect(occ(ctx)).toEqual([4, 5, 6, 7, 8, 9, 10, 11]);
    expect(ctx.layoutState!.occupied.size).toBe(8); // AUCUN panneau créé ni perdu
    expect(note()).toContain('Groupe déplacé');
  });

  it('un glissé IMPRÉCIS est ramené sur le pas du calepinage (la rangée reste alignée)', () => {
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    map.emit('dblclick', { point: cellPt(0), preventDefault() {} });
    // 7,4 m visés alors que le pas est de 3 m : sans quantification chaque membre viserait
    // 7,4 m et se retrouverait à 1,4 m de la cellule 6 m — au-delà de la tolérance de snap,
    // donc REFUSÉ. Quantifié, le geste vaut 6 m : la rangée se pose proprement.
    drag(cellPt(0), pt(0, 7.4));
    expect(occ(ctx)).toEqual([4, 5, 6, 7, 8, 9, 10, 11]);
  });

  it('un SOUS-ENSEMBLE se détache proprement de sa rangée', () => {
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    editor.setSelection([0, 1]); // deux panneaux de la rangée du bas seulement
    drag(cellPt(0), pt(0, 2 * STEP_M));
    // 0 et 1 sont montés en 8 et 9 ; 2 et 3 sont restés sur leur rangée.
    expect(ctx.layoutState!.occupied.has(8)).toBe(true);
    expect(ctx.layoutState!.occupied.has(9)).toBe(true);
    expect(ctx.layoutState!.occupied.has(2)).toBe(true);
    expect(ctx.layoutState!.occupied.has(3)).toBe(true);
    expect(ctx.layoutState!.occupied.size).toBe(8);
  });

  it('un panneau SEUL se pose librement sur l’emplacement le plus proche', () => {
    ctx.layoutState!.occupied.delete(8);
    const countBefore = ctx.layoutState!.occupied.size;
    click(cellPt(0));
    drag(cellPt(0), pt(0, 2 * STEP_M));
    expect(ctx.layoutState!.occupied.has(8)).toBe(true);
    expect(ctx.layoutState!.occupied.has(0)).toBe(false);
    expect(ctx.layoutState!.occupied.size).toBe(countBefore); // comptage inchangé
  });
});

describe('PV29 — un déplacement impossible est REFUSÉ, visiblement, sans rien casser', () => {
  it('rangée bloquée : rien ne bouge, la note le dit, et la 3D vire au ROUGE', () => {
    const before = occ(ctx); // toit plein : aucune place ailleurs
    map.emit('dblclick', { point: cellPt(0), preventDefault() {} });
    paints.length = 0;
    drag(cellPt(0), pt(0, 2 * STEP_M));
    expect(occ(ctx)).toEqual(before);
    expect(note()).toContain('rien n’a bougé');
    const refused = paints.filter((p) => p.refused);
    expect(refused.length).toBeGreaterThan(0);
    expect(refused[0].selected).toEqual([0, 1, 2, 3]);
  });

  it('un refus n’empile PAS d’action vide dans l’historique (rien à annuler)', () => {
    editor.setSelection([0, 1]);
    const before = occ(ctx);
    drag(cellPt(0), pt(0, 2 * STEP_M)); // toit plein → refus
    // La photo prise juste AVANT le geste est jetée : un geste refusé n'a rien changé, donc
    // il n'y a rien à annuler — et « rétablir » ne s'allume pas pour une action fantôme.
    expect(editor.undo()).toBe(false);
    expect(editor.redo()).toBe(false);
    expect(occ(ctx)).toEqual(before);
    expect(document.getElementById('rp9-layout-undo')!.hasAttribute('disabled')).toBe(true);
  });

  it('un nudge clavier bloqué ne laisse pas non plus d’action fantôme', () => {
    editor.setSelection([0, 1]); // toit plein : aucune direction libre
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
    expect(note()).toContain('Pas de place dans cette direction');
    expect(editor.undo()).toBe(false);
    expect(editor.redo()).toBe(false);
  });
});

describe('PV29 — la sélection est VISIBLE sur la 3D', () => {
  it('sélectionner une rangée la peint sur la scène (pas seulement dans le mini-plan)', () => {
    paints.length = 0;
    map.emit('dblclick', { point: cellPt(0), preventDefault() {} });
    const last = paints[paints.length - 1];
    expect(last.selected).toEqual([0, 1, 2, 3]);
    expect(last.refused).toBe(false);
  });

  it('le survol n’efface plus la sélection (les deux cohabitent)', () => {
    editor.setSelection([0, 1]);
    paints.length = 0;
    map.emit('mousemove', { point: cellPt(6) });
    const last = paints[paints.length - 1];
    expect(last.selected).toEqual([0, 1]);
    expect(last.hover).toBe(6);
  });

  it('la sélection survit au re-rendu qui suit un déplacement', () => {
    ctx.layoutState!.occupied.delete(8);
    click(cellPt(0));
    drag(cellPt(0), pt(0, 2 * STEP_M));
    expect(editor.selection()).toEqual([8]);
    expect(paints[paints.length - 1].selected).toEqual([8]);
  });
});

describe('PV29 — annuler / rétablir couvre les gestes manuels', () => {
  it('un déplacement de rangée s’annule puis se rétablit', () => {
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    const before = occ(ctx);
    map.emit('dblclick', { point: cellPt(0), preventDefault() {} });
    drag(cellPt(0), pt(0, 2 * STEP_M));
    const after = occ(ctx);
    expect(after).not.toEqual(before);
    expect(editor.undo()).toBe(true);
    expect(occ(ctx)).toEqual(before);
    expect(editor.redo()).toBe(true);
    expect(occ(ctx)).toEqual(after);
  });

  it('Ctrl+Z annule aussi le déplacement fait au clic', () => {
    ctx.layoutState!.occupied.delete(8);
    const before = occ(ctx);
    click(cellPt(0));
    drag(cellPt(0), pt(0, 2 * STEP_M));
    expect(occ(ctx)).not.toEqual(before);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true }));
    expect(occ(ctx)).toEqual(before);
  });
});

describe('PV29 — la pose manuelle est PERSISTABLE et protégée du ré-agencement', () => {
  it('les centres exportés après un déplacement reposent la MÊME disposition', () => {
    ctx.layoutState!.occupied.delete(8);
    click(cellPt(0));
    drag(cellPt(0), pt(0, 2 * STEP_M));
    const moved = occ(ctx);
    const centers = editor.occupiedCenters();
    // On repart d'une lattice neuve (comme au rechargement du dossier) puis on hydrate.
    ctx.layoutState = null;
    editor.ensureLayoutState();
    expect(editor.hydrateLayout(centers, ORIGIN)).toBe(true);
    expect(occ(ctx)).toEqual(moved);
  });

  it('un déplacement manuel déclenche la demande de confirmation AVANT un ré-agencement', () => {
    const confirmSpy = vi.fn(() => false);
    const ctx2 = makeCtx();
    const map2 = makeMap();
    const editor2 = createLayoutEditor(ctx2, {
      map: map2 as never,
      renderScene: () => {},
      prodConfigFromState: () => null,
      updateProductionWindow: () => {},
      snapshotActiveAreaResult: () => {},
      renderAreasPanel: () => {},
      renderActive: () => {},
      isObstacleMode: () => false,
      setPanelHighlight: () => {},
      confirmDiscard: confirmSpy,
    });
    editor2.ensureLayoutState();
    // Un simple DÉPLACEMENT (comptage constant) suffit à rendre la pose « manuelle ».
    ctx2.layoutState!.occupied.delete(0);
    ctx2.layoutState!.occupied.add(0); // no-op de contrôle : encore l'optimum
    expect(editor2.hasManualEdits()).toBe(false);
    ctx2.layoutState!.occupied.delete(0);
    ctx2.layoutState!.occupied.add(TOTAL - 1);
    expect(editor2.hasManualEdits()).toBe(true);
    expect(editor2.confirmDiscardEdits()).toBe(false); // refus → l'appelant abandonne
    expect(confirmSpy).toHaveBeenCalledTimes(1);
  });
});

describe('PV29 — échafaudage de SECOURS : la fenêtre existe même si l’hôte ne la fournit pas', () => {
  it('sans balisage hôte, l’éditeur construit la fenêtre dans le conteneur de la carte', () => {
    document.body.innerHTML = '';
    document.getElementById('rp9-layout-fallback-style')?.remove();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const m = makeMap(container);
    makeEditor(makeCtx(), m, []);
    const win = document.getElementById('rp9-layout-window');
    expect(win).not.toBeNull();
    expect(container.contains(win!)).toBe(true);
    expect(win!.classList.contains('rp9-layout-fallback')).toBe(true);
    // Les commandes essentielles portent les MÊMES identifiants que la page publique :
    // tout le câblage existant fonctionne sans un seul « if » supplémentaire.
    for (const id of ['rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-grid', 'rp9-layout-note', 'rp9-layout-undo', 'rp9-layout-reset']) {
      expect(document.getElementById(id), id).not.toBeNull();
    }
  });

  it('le bouton de secours ouvre bien le mode disposition', () => {
    document.body.innerHTML = '';
    document.getElementById('rp9-layout-fallback-style')?.remove();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const c = makeCtx({ layoutMode: false } as Partial<Ctx>);
    const m = makeMap(container);
    makeEditor(c, m, []);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new Event('click'));
    expect(c.layoutMode).toBe(true);
  });

  it('quand la page hôte FOURNIT son balisage, rien n’est injecté', () => {
    setupDom();
    const container = document.createElement('div');
    document.body.appendChild(container);
    makeEditor(makeCtx(), makeMap(container), []);
    expect(document.querySelectorAll('#rp9-layout-window').length).toBe(1);
    expect(document.querySelector('.rp9-layout-fallback')).toBeNull();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// PV29 §visionneuses — un calepinage DÉPLACÉ À LA MAIN se rejoue à l'identique.
// Les visionneuses (viewerOnly / viewerFull) ne ré-optimisent rien : elles
// REJOUENT `zone.geometry.panels`. Une pose manuelle (trous, rangée décalée)
// doit donc s'y afficher exactement telle qu'elle a été enregistrée — c'est le
// seul point où une régression rendrait au client un toit qu'il n'a pas acheté.
// Modules PURS : aucun DOM, aucun Three.js.
const V_LAT0 = 33.5;
const V_LNG0 = -7.6;
const V_COS = Math.cos((V_LAT0 * Math.PI) / 180);
const vAt = (x: number, y: number): [number, number] => [
  V_LNG0 + x / (DEG2M_CONST * V_COS),
  V_LAT0 + y / DEG2M_CONST,
];
const V_PITCH = PANEL2_SHORT_M + 0.02;

/** Pose MANUELLE : 4 colonnes dont la 3ᵉ a été retirée et une 5ᵉ décalée d'une rangée. */
const MANUAL_PANELS = [
  { cx: -1.5 * V_PITCH, cy: 0 },
  { cx: -0.5 * V_PITCH, cy: 0 },
  { cx: 1.5 * V_PITCH, cy: 0 }, // trou volontaire à +0,5 (panneau déplacé)
  { cx: 0.5 * V_PITCH, cy: 3 }, // ce panneau-là a été monté d'une rangée à la main
];

function manualLayout() {
  const parsed = parseRoofLayout({
    version: 2,
    zones: [
      {
        id: 'zone-1',
        label: 'Pan principal',
        vertices: [vAt(-12, -12), vAt(12, -12), vAt(12, 12), vAt(-12, 12)],
        obstacles: [],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        neededPanels: 0,
        geometry: {
          azimuthDeg: 180,
          tiltDeg: 13,
          family: 'south',
          flush: false,
          count: MANUAL_PANELS.length,
          origin: [V_LNG0, V_LAT0],
          panels: MANUAL_PANELS,
        },
      },
    ],
  });
  if (!parsed) throw new Error('fixture invalide');
  return parsed;
}

describe('PV29 — les visionneuses rejouent la pose MANUELLE, verbatim', () => {
  it('les centres rendus sont EXACTEMENT ceux enregistrés (trou compris)', () => {
    const plan = zoneRenderPlan(manualLayout().zones[0]);
    expect(plan).not.toBeNull();
    expect(plan!.grid.panels.map((p) => [p.cx, p.cy])).toEqual(MANUAL_PANELS.map((p) => [p.cx, p.cy]));
  });

  it('le comptage dessiné est celui de la pose manuelle — jamais un optimum recalculé', () => {
    const plan = zoneRenderPlan(manualLayout().zones[0]);
    expect(plan!.count).toBe(MANUAL_PANELS.length);
    expect(plan!.grid.count).toBe(MANUAL_PANELS.length);
  });

  it('la visionneuse pleine accepte ce layout et en fait un plan de pan', () => {
    const full = buildViewerFullPlan(manualLayout());
    expect(full).not.toBeNull();
    expect(full!.zones[0].plan!.grid.panels.length).toBe(MANUAL_PANELS.length);
  });
});

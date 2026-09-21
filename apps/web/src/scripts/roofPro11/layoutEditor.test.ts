// @vitest-environment jsdom
//
// CALX112/113/116 — lane LAYOUT (rp11/layoutEditor.ts, rp11/freeMode.ts).
//
// Ces trois tâches ajoutent des GESTES au placement libre (dupliquer, symétriser) et à la
// sélection (lasso) — elles vivent DANS `createLayoutEditor`, qui a besoin d'une carte
// MapLibre + d'un `Ctx` pour se construire. Ce fichier fournit le harnais minimal (mêmes
// conventions que les autres tests roofPro11 : `ctx` partiel typé `as unknown as Ctx`, seuls
// les champs lus sont fournis — cf. `prefill.test.ts`).
//
// CONVENTION DE REPÈRE DES FIXTURES : `pack.azimuthDeg = 0` donne, par `geomAxes(0)`,
// u = [-1, 0] et s = [0, 1] EXACTEMENT (sin/cos de 0, aucun bruit flottant) — donc dans ce
// fichier, et SEULEMENT ici : coordonnée u ≡ −(x ENU), coordonnée v ≡ y ENU. Un panneau
// « posé à l'abscisse u » a donc son centre ENU en `cx = -u, cy = v`.
import { describe, expect, it, vi } from 'vitest';
import { createLayoutEditor, type LayoutEditorDeps } from './layoutEditor';
import { type Ctx } from './context';
import { type LayoutPlan } from './types';
import { createLayoutState } from '../../lib/layoutVariability';
import { type FreePanel } from '../../lib/freeLayout';

/** Un contour CARRÉ centré sur l'origine ENU, de demi-côté `halfWidthM`. */
function squareRingENU(halfWidthM: number): [number, number][] {
  return [
    [-halfWidthM, -halfWidthM],
    [halfWidthM, -halfWidthM],
    [halfWidthM, halfWidthM],
    [-halfWidthM, halfWidthM],
  ];
}

/** Plan de pavage minimal : azimut 0 (repère exact, voir en-tête), panneau widthM × depthM. */
function makePlan(halfWidthM: number, widthM = 2, depthM = 1): LayoutPlan {
  return {
    pack: {
      origin: [-7.6, 33.5],
      ringENU: squareRingENU(halfWidthM),
      azimuthDeg: 0,
    },
    grid: {
      rowWidthM: widthM,
      footprintPerPanelM2: widthM * depthM,
      slopeLenM: depthM,
      panels: [], // vide : `renderLayoutPanel` sort tôt, aucun rendu de table requis ici
    },
    tiltDeg: 0,
    family: 'S',
    flush: false,
  } as unknown as LayoutPlan;
}

/** Carte MapLibre FACTICE : juste assez pour que `createLayoutEditor` se construise et que
 *  ses gestes de base (dragPan/curseur) ne lèvent rien. Le conteneur est attaché au DOM —
 *  sans quoi `document.getElementById` ne retrouverait JAMAIS l'échafaudage de secours que
 *  `buildFallbackLayoutDom` y insère (un nœud détaché n'est pas dans le document). */
function makeMap() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const boxZoomDisable = vi.fn();
  const boxZoomEnable = vi.fn();
  const map = {
    getContainer: () => container,
    boxZoom: { disable: boxZoomDisable, enable: boxZoomEnable },
    dragPan: { enable: vi.fn(), disable: vi.fn() },
    getCanvas: () => ({ style: {} }) as unknown as HTMLCanvasElement,
    on: vi.fn(),
    unproject: () => ({ lng: 0, lat: 0 }),
    easeTo: vi.fn(),
    jumpTo: vi.fn(),
  };
  return { map: map as unknown as Parameters<typeof createLayoutEditor>[1]['map'], boxZoomDisable, boxZoomEnable };
}

function makeDeps(map: LayoutEditorDeps['map']): LayoutEditorDeps {
  return {
    map,
    renderScene: vi.fn(),
    prodConfigFromState: () => null,
    updateProductionWindow: vi.fn(),
    snapshotActiveAreaResult: vi.fn(),
    renderAreasPanel: vi.fn(),
    renderActive: vi.fn(),
    isObstacleMode: () => false,
    setPanelHighlight: vi.fn(),
  };
}

/** `ctx` PLACEMENT LIBRE minimal : mode libre actif d'entrée, un plan de pavage et les
 *  panneaux fournis déjà posés. Les tableaux (vertices/obstacles/areas) sont des refs
 *  STABLES réelles — `applyWorkshopSnapshot` (Ctrl+Z) les vide/repeuple en place. */
function makeFreeCtx(plan: LayoutPlan | null, panels: FreePanel[]): Ctx {
  return {
    layoutMode: true,
    closed: true,
    vertices: [],
    obstacles: [],
    areas: [],
    roofType: 'flat',
    pitchDeg: 0,
    facingAzimuthDeg: 0,
    facingManual: false,
    neededPanels: 0,
    layoutPlan: plan,
    layoutState: null,
    layoutSel: null,
    layoutOptimalCount: 0,
    freeMode: true,
    freeState: { panels },
  } as unknown as Ctx;
}

function buildFreeEditor(halfWidthM: number, panels: FreePanel[], widthM = 2, depthM = 1) {
  const { map, boxZoomDisable, boxZoomEnable } = makeMap();
  const ctx = makeFreeCtx(makePlan(halfWidthM, widthM, depthM), panels);
  const editor = createLayoutEditor(ctx, makeDeps(map));
  return { editor, ctx, boxZoomDisable, boxZoomEnable };
}

describe('CALX112 — dupliquerSelection', () => {
  it('4 modules dupliqués à 3 m donnent 8 modules, en UN SEUL pas d’historique (Ctrl+Z exact)', () => {
    // u = 0, 6, 12, 18 (rangée simple, v = 0) → cx = -u, cy = 0. Demi-côté du toit très
    // généreux : les copies décalées de +3 (u = 3, 9, 15, 21) tiennent largement dedans.
    const panels: FreePanel[] = [0, 6, 12, 18].map((u) => ({ cx: -u, cy: 0 }));
    const before = panels.map((p) => ({ ...p }));
    const { editor } = buildFreeEditor(40, panels);

    const ok = editor.dupliquerSelection([0, 1, 2, 3], 3);
    expect(ok).toBe(true);
    expect(editor.freePanels()).toHaveLength(8);

    // Les 4 copies sont bien décalées de 3 m le long de l'axe des rangées (u), donc de
    // -3 m en x ENU sous cette convention — et rien d'autre n'a bougé.
    const after = editor.freePanels();
    for (let i = 0; i < 4; i++) {
      expect(after[i]).toEqual(before[i]);
      expect(after[4 + i].cx).toBeCloseTo(before[i].cx - 3, 9);
      expect(after[4 + i].cy).toBeCloseTo(before[i].cy, 9);
    }

    // Ctrl+Z : UN SEUL pas d'historique annule TOUT le geste, à l'état EXACT d'avant.
    expect(editor.undo()).toBe(true);
    expect(editor.freePanels()).toEqual(before);
    expect(editor.undo()).toBe(false); // rien de plus à annuler : c'était un seul pas
  });

  it('une copie qui sortirait du toit est refusée EN BLOC, en nommant le motif — rien n’est copié', () => {
    const panels: FreePanel[] = [{ cx: -8.5, cy: 0 }]; // u = 8.5
    const { editor, ctx } = buildFreeEditor(10, panels);

    const ok = editor.dupliquerSelection([0], 5); // u → 13.5, hors du toit (demi-côté 10)
    expect(ok).toBe(false);
    expect(editor.freePanels()).toEqual(panels); // rien n'a bougé, rien n'a été copié

    const note = document.getElementById('rp9-layout-note');
    expect(note?.textContent).toContain('sortirait du toit');
    expect(ctx.freeState?.panels).toHaveLength(1);
  });

  it('un chevauchement avec un module existant est refusé, sans rien copier', () => {
    // Deux panneaux voisins ; dupliquer le premier à 6 m atterrirait EXACTEMENT sur le
    // second (u : 0→6, second déjà à u=6) → chevauchement.
    const panels: FreePanel[] = [
      { cx: 0, cy: 0 }, // u = 0
      { cx: -6, cy: 0 }, // u = 6
    ];
    const { editor } = buildFreeEditor(30, panels);

    const ok = editor.dupliquerSelection([0], 6);
    expect(ok).toBe(false);
    expect(editor.freePanels()).toEqual(panels);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('chevaucherait');
  });

  it('le bouton « Dupliquer » reste inactif tant qu’aucun pas > 0 n’est saisi', () => {
    const panels: FreePanel[] = [{ cx: 0, cy: 0 }];
    buildFreeEditor(20, panels);
    const btn = document.getElementById('rp9-free-dup-btn') as HTMLButtonElement | null;
    const input = document.getElementById('rp9-free-dup-step') as HTMLInputElement | null;
    expect(btn).not.toBeNull();
    expect(btn!.disabled).toBe(true);
    input!.value = '300';
    input!.dispatchEvent(new Event('input'));
    expect(btn!.disabled).toBe(false);
    input!.value = '';
    input!.dispatchEvent(new Event('input'));
    expect(btn!.disabled).toBe(true);
  });
});

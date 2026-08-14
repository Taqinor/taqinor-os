// @vitest-environment jsdom
//
// PV27 §câblage — les deux chemins de perte restants :
//  2. la pose exportée doit être REPOSÉE au boot (hydrateLayout) ;
//  3. entrer en mode « Personnaliser » doit PRÉSERVER cette pose (avant : retour à
//     l'optimum, donc travail manuel effacé) — le retour à l'optimum reste possible, mais
//     seulement par le bouton explicite « Réinitialiser ».
import { describe, expect, it, beforeEach } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import { occupiedIndices } from '../src/lib/layoutVariability';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

const ORIGIN: [number, number] = [-7.62, 33.59];
const IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid', 'rp9-layout-note',
];
const BTN_IDS = ['rp9-layout-minus', 'rp9-layout-plus', 'rp9-layout-reset', 'rp9-layout-fill'];

function setupDom() {
  document.body.innerHTML = '';
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

function makeMap() {
  return {
    on() {},
    jumpTo() {},
    easeTo() {},
    once() {},
    dragPan: { enable() {}, disable() {} },
    getCanvas: () => ({ style: {} as Record<string, string> }),
    unproject: () => ({ lng: 0, lat: 0 }),
  } as never;
}

/** Lattice 4 × 3 au pas de 1 m. */
const CELLS = Array.from({ length: 12 }, (_, i) => ({ cx: i % 4, cy: Math.floor(i / 4) }));
function seedPlan(): LayoutPlan {
  return {
    pack: { origin: ORIGIN } as never,
    grid: { count: CELLS.length, kwc: CELLS.length * PANEL_KWC, panels: CELLS, rowWidthM: 1, rowPitchM: 1 } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

function makeCtx(): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: false,
    layoutState: null,
    layoutPlan: seedPlan(),
    layoutOptimalCount: 6,
    layoutSel: null,
    neededPanels: 6,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
  } as unknown as Ctx;
}

let ctx: Ctx;
let editor: ReturnType<typeof createLayoutEditor>;
let scenes: (Set<number> | undefined)[];

beforeEach(() => {
  setupDom();
  ctx = makeCtx();
  scenes = [];
  editor = createLayoutEditor(ctx, {
    map: makeMap(),
    renderScene: (_p, _g, _t, _f, _c, _flush, occupiedSet) => {
      scenes.push(occupiedSet);
    },
    prodConfigFromState: () => null,
    updateProductionWindow: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
  });
});

/** Pose NON contiguë exportée : cellules 0,1,2 et 9 (le trou en 3..8 est volontaire). */
const POSED = [CELLS[0], CELLS[1], CELLS[2], CELLS[9]];

describe('PV27 — la pose exportée est REPOSÉE (hydratation)', () => {
  it('re-snappe chaque panneau exporté sur la lattice courante', () => {
    expect(editor.hydrateLayout(POSED)).toBe(true);
    expect(occupiedIndices(ctx.layoutState!)).toEqual([0, 1, 2, 9]);
    // La 3D a bien été rendue avec CETTE occupation (et pas l'optimum).
    const last = scenes[scenes.length - 1];
    expect(last).toBeInstanceOf(Set);
    expect([...(last as Set<number>)].sort((a, b) => a - b)).toEqual([0, 1, 2, 9]);
  });

  it('translate les centres quand le repère d’origine a bougé', () => {
    const DEG2M = (Math.PI / 180) * 6378137;
    // Repère enregistré décalé d'un mètre vers l'est : les centres doivent revenir en place.
    const shifted: [number, number] = [ORIGIN[0] + 1 / (DEG2M * Math.cos(ORIGIN[1] * (Math.PI / 180))), ORIGIN[1]];
    const centers = POSED.map((p) => ({ cx: p.cx - 1, cy: p.cy }));
    expect(editor.hydrateLayout(centers, shifted)).toBe(true);
    expect(occupiedIndices(ctx.layoutState!)).toEqual([0, 1, 2, 9]);
  });

  it('liste vide ou plan absent → aucune hydratation, aucun crash', () => {
    expect(editor.hydrateLayout([])).toBe(false);
    ctx.layoutPlan = null;
    expect(editor.hydrateLayout(POSED)).toBe(false);
  });
});

describe('PV27 — entrer en mode « Personnaliser » PRÉSERVE la pose', () => {
  it('la disposition hydratée survit à l’ouverture du panneau', () => {
    editor.hydrateLayout(POSED);
    editor.setLayoutMode(true);
    expect(occupiedIndices(ctx.layoutState!)).toEqual([0, 1, 2, 9]);
  });

  it('« Réinitialiser » reste le chemin EXPLICITE vers l’optimum', () => {
    editor.hydrateLayout(POSED);
    editor.setLayoutMode(true);
    document.getElementById('rp9-layout-reset')!.dispatchEvent(new Event('click'));
    expect(occupiedIndices(ctx.layoutState!)).toEqual([0, 1, 2, 3, 4, 5]); // les 6 premiers
  });

  it('sans pose préalable, l’ouverture part bien de l’optimum (comportement historique)', () => {
    editor.setLayoutMode(true);
    expect(occupiedIndices(ctx.layoutState!)).toEqual([0, 1, 2, 3, 4, 5]);
  });
});

// @vitest-environment jsdom
//
// PV26 §câblage — annuler / rétablir branchés sur les VRAIES actions de l'éditeur
// (boutons + / − / remplir / réinitialiser, déplacements) + les raccourcis Ctrl+Z /
// Ctrl+Y et le nudge aux flèches. Même montage que layoutEditorRecomputeW97 : ctx minimal
// avec layoutPlan seedé, renderScene stub, carte stub.
import { describe, expect, it, beforeEach } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

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

/** Lattice 4 × 3 au pas de 1 m (rowWidth/rowPitch = 1 m → une flèche = un emplacement). */
function seedPlan(): LayoutPlan {
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) panels.push({ cx: c, cy: r });
  return {
    pack: { origin: [-7.62, 33.59] } as never,
    grid: { count: panels.length, kwc: panels.length * PANEL_KWC, panels, rowWidthM: 1, rowPitchM: 1 } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

function makeCtx(optimalCount = 4): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: true,
    layoutState: null,
    layoutPlan: seedPlan(),
    layoutOptimalCount: optimalCount,
    layoutSel: null,
    neededPanels: 4,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
  } as unknown as Ctx;
}

function makeEditor(ctx: Ctx) {
  return createLayoutEditor(ctx, {
    map: makeMap(),
    renderScene: () => {},
    prodConfigFromState: () => null,
    updateProductionWindow: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
  });
}

const click = (id: string) => document.getElementById(id)!.dispatchEvent(new Event('click'));
const key = (k: string, init: KeyboardEventInit = {}) =>
  document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init }));
const count = (ctx: Ctx) => ctx.layoutState!.occupied.size;

let ctx: Ctx;
let editor: ReturnType<typeof createLayoutEditor>;

beforeEach(() => {
  setupDom();
  ctx = makeCtx();
  editor = makeEditor(ctx);
  editor.ensureLayoutState();
  editor.renderLayoutPanel();
});

describe('PV26 — annuler / rétablir les actions de disposition', () => {
  it('« + » puis annuler revient au compte précédent, rétablir le remet', () => {
    expect(count(ctx)).toBe(4);
    click('rp9-layout-plus');
    expect(count(ctx)).toBe(5);
    expect(editor.undo()).toBe(true);
    expect(count(ctx)).toBe(4);
    expect(editor.redo()).toBe(true);
    expect(count(ctx)).toBe(5);
  });

  it('« remplir » et « réinitialiser » s’annulent comme le reste', () => {
    click('rp9-layout-fill');
    expect(count(ctx)).toBe(12);
    click('rp9-layout-reset');
    expect(count(ctx)).toBe(4);
    editor.undo(); // annule le reset
    expect(count(ctx)).toBe(12);
    editor.undo(); // annule le remplissage
    expect(count(ctx)).toBe(4);
  });

  it('une nouvelle action après une annulation vide le « rétablir »', () => {
    click('rp9-layout-plus');
    editor.undo();
    click('rp9-layout-minus'); // nouvelle branche
    expect(editor.redo()).toBe(false);
  });

  it('les boutons reflètent ce qui est possible', () => {
    const undoBtn = document.getElementById('rp9-layout-undo') as HTMLButtonElement;
    const redoBtn = document.getElementById('rp9-layout-redo') as HTMLButtonElement;
    expect(undoBtn.disabled).toBe(true);
    expect(redoBtn.disabled).toBe(true);
    click('rp9-layout-plus');
    expect(undoBtn.disabled).toBe(false);
    click('rp9-layout-undo');
    expect(redoBtn.disabled).toBe(false);
    expect(count(ctx)).toBe(4);
  });

  it('Ctrl+Z annule, Ctrl+Y et Ctrl+Maj+Z rétablissent', () => {
    click('rp9-layout-plus');
    key('z', { ctrlKey: true });
    expect(count(ctx)).toBe(4);
    key('y', { ctrlKey: true });
    expect(count(ctx)).toBe(5);
    key('z', { ctrlKey: true });
    expect(count(ctx)).toBe(4);
    key('Z', { ctrlKey: true, shiftKey: true });
    expect(count(ctx)).toBe(5);
  });

  it('hors mode disposition, les raccourcis ne volent RIEN à la page', () => {
    click('rp9-layout-plus');
    ctx.layoutMode = false;
    key('z', { ctrlKey: true });
    expect(count(ctx)).toBe(5); // inchangé
  });
});

describe('PV26 — nudge au clavier', () => {
  it('une flèche déplace la sélection d’un emplacement, et c’est annulable', () => {
    // Occupation initiale = cellules 0..3 (rangée du bas) ; la rangée du dessus est libre.
    editor.setSelection([0]);
    key('ArrowUp');
    expect(ctx.layoutState!.occupied.has(0)).toBe(false);
    expect(ctx.layoutState!.occupied.has(4)).toBe(true);
    expect(count(ctx)).toBe(4);
    editor.undo();
    expect(ctx.layoutState!.occupied.has(0)).toBe(true);
    expect(ctx.layoutState!.occupied.has(4)).toBe(false);
  });

  it('sans sélection, les flèches ne font rien', () => {
    const before = [...ctx.layoutState!.occupied].sort((a, b) => a - b);
    key('ArrowRight');
    expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual(before);
    expect(editor.undo()).toBe(false); // aucune photo inutile n'a été empilée
  });

  it('un nudge sans place ne bouge rien et ne pollue pas l’historique', () => {
    editor.setSelection([0]);
    key('ArrowDown'); // sous la première rangée : rien
    expect(ctx.layoutState!.occupied.has(0)).toBe(true);
    expect(editor.undo()).toBe(false);
  });
});

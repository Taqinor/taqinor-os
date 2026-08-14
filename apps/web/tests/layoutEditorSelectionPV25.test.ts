// @vitest-environment jsdom
//
// PV25 §câblage — la sélection multiple, le déplacement de GROUPE et de RANGÉE, et le
// nudge d'azimut passent par le VRAI câblage de l'éditeur (createLayoutEditor), pas
// seulement par la lib pure. Comme le harness jsdom ne peut pas monter la 3D, on
// reproduit le montage de tests/layoutEditorRecomputeW97.ts : ctx minimal avec un
// layoutPlan SEEDÉ, renderScene stub, et une carte stub dont `unproject` fait
// correspondre 10 px écran à 1 m ENU (le seuil de glissé LAYOUT_GRAB_PX = 12 px est
// donc franchi dès ~1,2 m).
import { describe, expect, it, beforeEach } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

const DEG2M = (Math.PI / 180) * 6378137;
const ORIGIN: [number, number] = [-7.62, 33.59];
const PX_PER_M = 10;

const IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid',
  'rp9-layout-note', 'rp9-layout-azimuth', 'rp9-layout-az-value',
];
const BTN_IDS = [
  'rp9-layout-minus', 'rp9-layout-plus', 'rp9-layout-reset', 'rp9-layout-fill',
  'rp9-layout-select', 'rp9-layout-row', 'rp9-layout-clear-sel',
  'rp9-layout-az-minus', 'rp9-layout-az-plus',
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

/** Carte stub : mémorise les handlers pour rejouer des gestes, et déprojette 10 px → 1 m. */
function makeMap() {
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
    unproject: (p: { x: number; y: number }) => ({
      lng: ORIGIN[0] + p.x / PX_PER_M / (DEG2M * Math.cos(ORIGIN[1] * (Math.PI / 180))),
      lat: ORIGIN[1] + p.y / PX_PER_M / DEG2M,
    }),
  };
}

/** Lattice 4 × 3 au pas de 1 m, toutes cellules posées. */
function seedPlan(): LayoutPlan {
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) panels.push({ cx: c, cy: r });
  return {
    pack: { origin: ORIGIN } as never,
    grid: { count: panels.length, kwc: panels.length * PANEL_KWC, panels } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

function makeCtx(over: Partial<Ctx> = {}): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: true,
    layoutState: null,
    layoutPlan: seedPlan(),
    layoutOptimalCount: 12,
    layoutSel: null,
    neededPanels: 12,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
    ...over,
  } as unknown as Ctx;
}

function makeEditor(ctx: Ctx, map: ReturnType<typeof makeMap>, sink: { recalcs: number }) {
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
    recalcWithReenter: () => {
      sink.recalcs++;
    },
  });
}

const pt = (xM: number, yM: number) => ({ x: xM * PX_PER_M, y: yM * PX_PER_M });

let map: ReturnType<typeof makeMap>;
let ctx: Ctx;
let sink: { recalcs: number };
let editor: ReturnType<typeof createLayoutEditor>;

beforeEach(() => {
  setupDom();
  map = makeMap();
  ctx = makeCtx();
  sink = { recalcs: 0 };
  editor = makeEditor(ctx, map, sink);
  editor.ensureLayoutState();
  editor.renderLayoutPanel();
});

describe('PV25 — marquee (Maj + glissé) via le câblage réel', () => {
  it('sélectionne les panneaux encadrés et l’annonce', () => {
    map.emit('mousedown', { point: pt(-0.5, -0.5), originalEvent: { shiftKey: true }, preventDefault() {} });
    map.emit('mousemove', { point: pt(2.5, 0.5) });
    map.emit('mouseup', { point: pt(2.5, 0.5) });
    expect(editor.selection()).toEqual([0, 1, 2]);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('sélectionnés');
  });

  it('le mode « sélection multiple » (tactile) fait la même chose SANS Maj', () => {
    document.getElementById('rp9-layout-select')!.dispatchEvent(new Event('click'));
    map.emit('mousedown', { point: pt(-0.5, -0.5), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(1.5, 0.5) });
    map.emit('mouseup', { point: pt(1.5, 0.5) });
    expect(editor.selection()).toEqual([0, 1]);
    expect(document.getElementById('rp9-layout-select')?.getAttribute('aria-pressed')).toBe('true');
  });

  it('« Effacer la sélection » vide la sélection', () => {
    editor.setSelection([0, 1, 2]);
    document.getElementById('rp9-layout-clear-sel')!.dispatchEvent(new Event('click'));
    expect(editor.selection()).toEqual([]);
  });

  it('la sélection ne garde jamais un emplacement VIDE', () => {
    ctx.layoutState!.occupied.delete(2);
    editor.setSelection([0, 1, 2]);
    expect(editor.selection()).toEqual([0, 1]);
  });
});

describe('PV25 — déplacement de GROUPE tout ou rien', () => {
  it('glisser un membre déplace tout le groupe quand la place existe', () => {
    // Libère la rangée du haut pour laisser monter le groupe.
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    editor.setSelection([0, 1]);
    map.emit('mousedown', { point: pt(0, 0), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(0, 2) });
    map.emit('mouseup', { point: pt(0, 2) });
    // 0 et 1 sont montés de 2 rangées (8 et 9), les autres n'ont pas bougé.
    expect(ctx.layoutState!.occupied.has(8)).toBe(true);
    expect(ctx.layoutState!.occupied.has(9)).toBe(true);
    expect(ctx.layoutState!.occupied.has(0)).toBe(false);
    expect(ctx.layoutState!.occupied.size).toBe(8);
  });

  it('groupe bloqué : RIEN ne bouge et la note le dit', () => {
    editor.setSelection([0, 1]); // toit plein : aucune place ailleurs
    const before = [...ctx.layoutState!.occupied].sort((a, b) => a - b);
    map.emit('mousedown', { point: pt(0, 0), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(0, 2) });
    map.emit('mouseup', { point: pt(0, 2) });
    expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual(before);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('rien n’a bougé');
  });
});

describe('PV25 — mode RANGÉE', () => {
  it('glisser un panneau emmène toute sa rangée', () => {
    ctx.layoutState!.occupied.delete(3); // place à droite sur la rangée du bas
    document.getElementById('rp9-layout-row')!.dispatchEvent(new Event('click'));
    map.emit('mousedown', { point: pt(0, 0), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(1.4, 0) });
    map.emit('mouseup', { point: pt(1, 0) });
    expect([...ctx.layoutState!.occupied].filter((i) => i < 4).sort((a, b) => a - b)).toEqual([1, 2, 3]);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('Rangée déplacée');
  });

  it('les deux modes de glissé s’excluent', () => {
    document.getElementById('rp9-layout-row')!.dispatchEvent(new Event('click'));
    document.getElementById('rp9-layout-select')!.dispatchEvent(new Event('click'));
    expect(document.getElementById('rp9-layout-row')?.getAttribute('aria-pressed')).toBe('false');
    expect(document.getElementById('rp9-layout-select')?.getAttribute('aria-pressed')).toBe('true');
  });
});

describe('PV25 — nudge d’azimut', () => {
  it('sur toit en PENTE : ±1° puis RECALCUL complet (re-pavage + re-snap)', () => {
    ctx.roofType = 'pitched';
    editor.renderLayoutPanel();
    document.getElementById('rp9-layout-az-plus')!.dispatchEvent(new Event('click'));
    expect(ctx.facingAzimuthDeg).toBe(181);
    expect(ctx.facingManual).toBe(true);
    expect(sink.recalcs).toBe(1);
    document.getElementById('rp9-layout-az-minus')!.dispatchEvent(new Event('click'));
    document.getElementById('rp9-layout-az-minus')!.dispatchEvent(new Event('click'));
    expect(ctx.facingAzimuthDeg).toBe(179);
    expect(sink.recalcs).toBe(3);
    expect(document.getElementById('rp9-layout-az-value')?.textContent).toBe('179°');
  });

  it('sur toit PLAT : contrôle masqué et sans effet (l’azimut est un axe de l’optimiseur)', () => {
    editor.renderLayoutPanel();
    expect((document.getElementById('rp9-layout-azimuth') as HTMLElement).hidden).toBe(true);
    document.getElementById('rp9-layout-az-plus')!.dispatchEvent(new Event('click'));
    expect(ctx.facingAzimuthDeg).toBe(180);
    expect(sink.recalcs).toBe(0);
  });
});

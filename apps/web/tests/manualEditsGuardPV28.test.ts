// @vitest-environment jsdom
//
// PV28 — NE PERDS PAS LE TRAVAIL MANUEL. `hasManualEdits` compare l'occupation à celle
// que produirait « réinitialiser à l'optimum » ; dès qu'elles divergent, tout
// ré-agencement automatique (changement d'axe, optimum, réinitialisation) DEMANDE
// confirmation en français AVANT de commettre quoi que ce soit. Un refus laisse l'état
// strictement intact. Aucun panneau n'est verrouillé : on prévient, on ne fige pas.
import { describe, expect, it, beforeEach } from 'vitest';
import { createLayoutState, hasManualEdits, occupiedIndices } from '../src/lib/layoutVariability';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

const CELLS = Array.from({ length: 12 }, (_, i) => ({ cx: i % 4, cy: Math.floor(i / 4) }));

describe('PV28 — détection d’une disposition éditée à la main', () => {
  it('l’optimum intact n’est PAS une édition manuelle', () => {
    expect(hasManualEdits(createLayoutState(CELLS, 6), 6)).toBe(false);
    expect(hasManualEdits(createLayoutState(CELLS, 0), 0)).toBe(false);
    expect(hasManualEdits(createLayoutState(CELLS, 12), 12)).toBe(false);
  });

  it('un panneau ajouté, retiré ou DÉPLACÉ compte comme édition manuelle', () => {
    const added = createLayoutState(CELLS, 6);
    added.occupied.add(7);
    expect(hasManualEdits(added, 6)).toBe(true);

    const removed = createLayoutState(CELLS, 6);
    removed.occupied.delete(0);
    expect(hasManualEdits(removed, 6)).toBe(true);

    // Même NOMBRE de panneaux, mais l'un a été déplacé ailleurs → édition manuelle.
    const moved = createLayoutState(CELLS, 6);
    moved.occupied.delete(2);
    moved.occupied.add(9);
    expect(moved.occupied.size).toBe(6);
    expect(hasManualEdits(moved, 6)).toBe(true);
  });

  it('état absent ou comptage aberrant → pas de faux positif', () => {
    expect(hasManualEdits(null, 6)).toBe(false);
    expect(hasManualEdits(undefined, 6)).toBe(false);
    // Un optimum plus grand que la lattice est borné à la lattice.
    expect(hasManualEdits(createLayoutState(CELLS, 12), 99)).toBe(false);
    expect(hasManualEdits(createLayoutState(CELLS, 6), Number.NaN)).toBe(true); // 6 ≠ 0
  });
});

// ── Câblage : la confirmation passe par l'éditeur (confirm injectable) ────────
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

function seedPlan(): LayoutPlan {
  return {
    pack: { origin: [-7.62, 33.59] } as never,
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
    layoutMode: true,
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
let asked: string[];
let answer: boolean;
let editor: ReturnType<typeof createLayoutEditor>;

beforeEach(() => {
  setupDom();
  ctx = makeCtx();
  asked = [];
  answer = true;
  editor = createLayoutEditor(ctx, {
    map: {
      on() {},
      jumpTo() {},
      easeTo() {},
      once() {},
      dragPan: { enable() {}, disable() {} },
      getCanvas: () => ({ style: {} as Record<string, string> }),
      unproject: () => ({ lng: 0, lat: 0 }),
    } as never,
    renderScene: () => {},
    prodConfigFromState: () => null,
    updateProductionWindow: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
    confirmDiscard: (msg: string) => {
      asked.push(msg);
      return answer;
    },
  });
  editor.ensureLayoutState();
  editor.renderLayoutPanel();
});

describe('PV28 — la confirmation ne s’ouvre QUE si un travail manuel existe', () => {
  it('sans édition manuelle : on continue SANS rien demander', () => {
    expect(editor.hasManualEdits()).toBe(false);
    expect(editor.confirmDiscardEdits()).toBe(true);
    expect(asked).toEqual([]);
  });

  it('avec édition manuelle : question en FRANÇAIS, et « oui » laisse passer', () => {
    document.getElementById('rp9-layout-plus')!.dispatchEvent(new Event('click'));
    expect(editor.hasManualEdits()).toBe(true);
    answer = true;
    expect(editor.confirmDiscardEdits()).toBe(true);
    expect(asked.length).toBe(1);
    expect(asked[0]).toContain('panneaux');
    expect(asked[0]).toContain('Continuer ?');
  });

  it('« non » REFUSE l’action et la disposition reste intacte', () => {
    document.getElementById('rp9-layout-plus')!.dispatchEvent(new Event('click'));
    const before = occupiedIndices(ctx.layoutState!);
    answer = false;
    expect(editor.confirmDiscardEdits()).toBe(false);
    expect(occupiedIndices(ctx.layoutState!)).toEqual(before); // rien n'a bougé
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('conservée');
  });

  it('après un retour explicite à l’optimum, plus rien à protéger', () => {
    document.getElementById('rp9-layout-plus')!.dispatchEvent(new Event('click'));
    expect(editor.hasManualEdits()).toBe(true);
    document.getElementById('rp9-layout-reset')!.dispatchEvent(new Event('click'));
    expect(editor.hasManualEdits()).toBe(false);
    asked = [];
    expect(editor.confirmDiscardEdits()).toBe(true);
    expect(asked).toEqual([]);
  });
});

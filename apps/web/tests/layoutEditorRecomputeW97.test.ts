// @vitest-environment jsdom
//
// W97 §5 — RECOMPUTE D'ÉDITION DE DISPOSITION à travers le CÂBLAGE de l'éditeur (W69),
// pas seulement la lib pure layoutVariability (déjà couverte par layoutVariability.test.ts).
//
// Le harness jsdom ne peut PAS faire tourner la vraie scène 3D (renderScene s'auto-annule
// avec un sceneRoot null), donc ctx.layoutPlan n'est jamais posé par un montage complet.
// On reproduit fidèlement le câblage en construisant createLayoutEditor avec un ctx minimal
// dont layoutPlan/layoutOptimalCount sont SEEDÉS (comme le ferait renderScene en prod) et un
// renderScene STUB. On entre en mode disposition, on ajoute/retire/réinitialise via les
// lattice helpers (boutons rp9-layout-plus/-minus/-reset + plan tactile), et on vérifie que
// #rp9-layout-count / #rp9-layout-kwc / la couverture RECOMPUTENT et que le recompute par
// COMPTAGE (updateProductionWindow) suit le nombre posé.
import { describe, expect, it, beforeEach, vi } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

const LAYOUT_IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid', 'rp9-layout-note',
];
const LAYOUT_BTN_IDS = ['rp9-layout-minus', 'rp9-layout-plus', 'rp9-layout-reset'];

function setupDom() {
  document.body.innerHTML = '';
  for (const id of LAYOUT_IDS) {
    const e = document.createElement('div');
    e.id = id;
    document.body.appendChild(e);
  }
  for (const id of LAYOUT_BTN_IDS) {
    const b = document.createElement('button');
    b.id = id;
    document.body.appendChild(b);
  }
}

// Carte stub : l'éditeur s'abonne à des événements carte (on) pour le glissé 3D ; setLayoutMode
// appelle jumpTo (reducedMotion). renderScene est injecté en stub. On ne déclenche aucun
// glissé carte ici (les tests passent par les boutons + le plan tactile DOM).
function makeMap() {
  return {
    on() {},
    jumpTo() {},
    easeTo() {},
    dragPan: { enable() {}, disable() {} },
    getCanvas: () => ({ style: {} as Record<string, string> }),
    unproject: () => ({ lng: 0, lat: 0 }),
  } as never;
}

// Un plan gagnant SEEDÉ : grille de 12 cellules régulières (1 m de pas), comme le poserait
// renderScene (ctx.layoutPlan) en production après un tracé.
function seedPlan(): LayoutPlan {
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) panels.push({ cx: c, cy: r });
  return {
    pack: { origin: [-7.62, 33.59] } as never,
    grid: { count: panels.length, kwc: panels.length * PANEL_KWC, panels } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

// ctx minimal : seuls les champs lus/écrits par l'éditeur de disposition sont fournis.
function makeCtx(optimalCount = 8): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: false,
    layoutState: null,
    layoutPlan: seedPlan(),
    layoutOptimalCount: optimalCount,
    layoutSel: null,
    neededPanels: 8, // pour la couverture (count / neededPanels)
  } as unknown as Ctx;
}

const txt = (id: string) => document.getElementById(id)?.textContent ?? '';
const num = (id: string) => Number((txt(id).match(/[\d   ]+/)?.[0] ?? '0').replace(/[^\d]/g, ''));

function makeEditor(ctx: Ctx, sink: { prodCalls: number[]; sceneCalls: number }) {
  return createLayoutEditor(ctx, {
    map: makeMap(),
    renderScene: () => {
      sink.sceneCalls++;
    },
    prodConfigFromState: () => ({ panels: 0 }) as never,
    updateProductionWindow: (cfg) => {
      sink.prodCalls.push((cfg as { panels: number }).panels);
    },
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
  });
}

describe('W97 §5 — l\'éditeur de disposition recompute count/kWc/couverture via le câblage', () => {
  beforeEach(setupDom);

  it('entrer en mode disposition remplit #rp9-layout-count à l\'optimum (8) + kWc/couverture', () => {
    const ctx = makeCtx(8);
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    const editor = makeEditor(ctx, sink);
    editor.setLayoutMode(true);
    expect(num('rp9-layout-count')).toBe(8); // les 8 premières cellules occupées
    // kWc = 8 × 0,72 = 5,76 → « 5,8 kWc »
    expect(txt('rp9-layout-kwc')).toMatch(/5[.,]8\s*kWc/);
    expect(txt('rp9-layout-cover')).toBe('100 %'); // 8 / besoin 8
    // le plan tactile a 12 cellules (la lattice complète)
    expect(document.querySelectorAll('#rp9-layout-grid [data-cell]').length).toBe(12);
    // updateProductionWindow a été appelé avec le comptage posé (recompute par COMPTAGE)
    expect(sink.prodCalls[sink.prodCalls.length - 1]).toBe(8);
  });

  it('le bouton + ajoute un panneau → count 8→9, kWc monte, production recompute', () => {
    const ctx = makeCtx(8);
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    makeEditor(ctx, sink);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new window.Event('click', { bubbles: true }));
    expect(num('rp9-layout-count')).toBe(8);
    const kwcBefore = txt('rp9-layout-kwc');
    (document.getElementById('rp9-layout-plus') as HTMLButtonElement).click();
    expect(num('rp9-layout-count')).toBe(9);
    expect(txt('rp9-layout-kwc')).not.toBe(kwcBefore); // 9 × 0,72 = 6,5 kWc
    expect(sink.prodCalls[sink.prodCalls.length - 1]).toBe(9); // recompte par comptage
  });

  it('le bouton − retire un panneau → count 8→7, et la couverture chute sous 100 %', () => {
    const ctx = makeCtx(8);
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    makeEditor(ctx, sink);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new window.Event('click', { bubbles: true }));
    (document.getElementById('rp9-layout-minus') as HTMLButtonElement).click();
    expect(num('rp9-layout-count')).toBe(7);
    // 7 / 8 ≈ 88 %
    expect(num('rp9-layout-cover')).toBeLessThan(100);
    expect(sink.prodCalls[sink.prodCalls.length - 1]).toBe(7);
  });

  it('réinitialiser restaure le comptage optimal après des éditions', () => {
    const ctx = makeCtx(8);
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    makeEditor(ctx, sink);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new window.Event('click', { bubbles: true }));
    (document.getElementById('rp9-layout-plus') as HTMLButtonElement).click();
    (document.getElementById('rp9-layout-plus') as HTMLButtonElement).click();
    expect(num('rp9-layout-count')).toBe(10);
    (document.getElementById('rp9-layout-reset') as HTMLButtonElement).click();
    expect(num('rp9-layout-count')).toBe(8); // optimum restauré
    expect(sink.prodCalls[sink.prodCalls.length - 1]).toBe(8);
  });

  it('le plan tactile : sélectionner un panneau puis une cellule libre le DÉPLACE (count inchangé)', () => {
    const ctx = makeCtx(8); // cellules 0..7 occupées, 8..11 libres
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    makeEditor(ctx, sink);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new window.Event('click', { bubbles: true }));
    const grid = document.getElementById('rp9-layout-grid')!;
    const cell = (i: number) => grid.querySelector<HTMLButtonElement>(`[data-cell="${i}"]`)!;
    // 1er tap : sélectionne le panneau occupé 0 ; 2e tap : cellule libre 11 → déplacement
    cell(0).click();
    cell(11).click();
    expect(num('rp9-layout-count')).toBe(8); // déplacement, pas ajout/retrait
    // la cellule 0 est désormais libre, la 11 occupée
    expect(cell(0).getAttribute('data-occupied')).toBe('false');
    expect(cell(11).getAttribute('data-occupied')).toBe('true');
  });

  it('plein toit : + est désactivé une fois les 12 cellules occupées (plafond lattice)', () => {
    const ctx = makeCtx(12); // toutes occupées d'emblée
    const sink = { prodCalls: [] as number[], sceneCalls: 0 };
    makeEditor(ctx, sink);
    document.getElementById('rp9-layout-toggle')!.dispatchEvent(new window.Event('click', { bubbles: true }));
    expect(num('rp9-layout-count')).toBe(12);
    expect((document.getElementById('rp9-layout-plus') as HTMLButtonElement).disabled).toBe(true);
  });
});

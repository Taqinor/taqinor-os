// @vitest-environment jsdom
//
// PV34 — SÉLECTION FACILE + GLISSÉ DE GROUPE NATUREL, testés au travers du VRAI câblage
// (`createLayoutEditor`), pas de la lib pure. Ordre du fondateur, 25/08 : « moving manually
// the pv in calepinage does not look good, it is working now yes, but i cannot select a
// group of pannels or a raw ; the selection should be made easy and also once we select the
// pannels it should be easier and more natural to drag them ».
//
// Ce que ce fichier épingle :
//   1. le BOX-ZOOM natif de MapLibre est ÉTEINT — c'était la cause réelle : son geste par
//      défaut EST Maj + glissé, il ne consulte jamais `preventDefault()`, et il zoomait la
//      caméra sur le rectangle au relâchement. Le cadre de PV31 était donc mécaniquement
//      impossible à réussir à la souris ;
//   2. un glissé SANS modificateur, parti du toit mais d'aucun panneau, encadre (et hors de
//      la zone de calepinage, il reste un déplacement de carte : la carte ne se fige pas) ;
//   3. Ctrl/⌘ + clic ajoute ou retire un panneau du groupe ;
//   4. Maj + glissé AJOUTE le lot encadré au groupe au lieu de le remplacer ;
//   5. le compteur « N panneaux sélectionnés » suit la sélection ;
//   6. l'APERÇU VIVANT du glissé de groupe en mode lattice (les panneaux suivent le curseur)
//      et la restauration du rendu réel quand le geste est refusé ;
//   7. le tactile est INCHANGÉ (un doigt fait toujours glisser la carte) ;
//   8. un relâchement HORS de la carte termine quand même le geste.
//
// Harnais : celui de tests/layoutManualEditPV29.test.ts (ctx minimal + carte stub qui
// déprojette 10 px → 1 m, lattice 4×3 au pas de 3 m).
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan } from '../src/scripts/roofPro11/types';
import { PANEL_KWC } from '../src/lib/productionEngine';

const DEG2M = (Math.PI / 180) * 6378137;
const ORIGIN: [number, number] = [-7.62, 33.59];
const PX_PER_M = 10;
const STEP_M = 3;
const COLS = 4;
const ROWS = 3;
const TOTAL = COLS * ROWS;

const IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid',
  'rp9-layout-note', 'rp9-layout-azimuth', 'rp9-layout-az-value', 'rp9-layout-selcount',
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

/** Carte stub : mémorise les handlers, déprojette 10 px → 1 m, et TRACE boxZoom.disable. */
function makeMap() {
  const handlers: Record<string, ((e: unknown) => void)[]> = {};
  const boxZoomDisabled = { count: 0 };
  return {
    handlers,
    boxZoomDisabled,
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
    boxZoom: {
      disable() {
        boxZoomDisabled.count += 1;
      },
    },
    getCanvas: () => ({ style: {} as Record<string, string> }),
    unproject: (p: { x: number; y: number }) => ({
      lng: ORIGIN[0] + p.x / PX_PER_M / (DEG2M * Math.cos(ORIGIN[1] * (Math.PI / 180))),
      lat: ORIGIN[1] + p.y / PX_PER_M / DEG2M,
    }),
  };
}

/** Lattice COLS × ROWS au pas de STEP_M, toutes cellules posées (index = r * COLS + c).
 *  `withGeometry` ajoute de quoi décrire l'EMPRISE d'un panneau (azimut + empreinte au
 *  sol) : c'est ce qui active le cadre « traversant ». Sans elle, l'éditeur retombe sur
 *  le critère historique « centre dedans » — la non-régression est testée aussi. */
function seedPlan(withGeometry = false): LayoutPlan {
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) panels.push({ cx: c * STEP_M, cy: r * STEP_M });
  return {
    pack: withGeometry
      ? ({ origin: ORIGIN, azimuthDeg: 180, ringENU: [[-5, -5], [15, -5], [15, 15], [-5, 15]] } as never)
      : ({ origin: ORIGIN } as never),
    grid: {
      count: panels.length,
      kwc: panels.length * PANEL_KWC,
      panels,
      rowWidthM: STEP_M,
      rowPitchM: STEP_M,
      // Empreinte au sol par panneau : largeur 3 m × profondeur 1 m → depthM = 1 m.
      ...(withGeometry ? { footprintPerPanelM2: STEP_M * 1 } : {}),
    } as never,
    tiltDeg: 15,
    family: 'south',
    flush: false,
  };
}

function makeCtx(withGeometry = false): Ctx {
  return {
    opts: { reducedMotion: true },
    closed: true,
    layoutMode: true,
    layoutState: null,
    layoutPlan: seedPlan(withGeometry),
    layoutOptimalCount: TOTAL,
    layoutSel: null,
    neededPanels: TOTAL,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
  } as unknown as Ctx;
}

type PaintCall = { selected: number[]; hover: number | null; refused: boolean };

let map: ReturnType<typeof makeMap>;
let ctx: Ctx;
let paints: PaintCall[];
let renders: Set<number>[];
let editor: ReturnType<typeof createLayoutEditor>;

function boot(withGeometry = false) {
  setupDom();
  map = makeMap();
  ctx = makeCtx(withGeometry);
  paints = [];
  renders = [];
  editor = createLayoutEditor(ctx, {
    map: map as never,
    renderScene: (_pack, _grid, _tilt, _family, _max, _flush, occSet) => {
      renders.push(new Set(occSet as Set<number>));
    },
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
  } as never);
  editor.ensureLayoutState();
  editor.renderLayoutPanel();
}

beforeEach(() => {
  // L'aperçu vivant passe par requestAnimationFrame : on le rend SYNCHRONE pour que le
  // test observe le rendu au moment du geste, sans minuterie.
  vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => {
    fn(0);
    return 0;
  });
  boot();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const pt = (xM: number, yM: number) => ({ x: xM * PX_PER_M, y: yM * PX_PER_M });
const cellPt = (i: number) => pt((i % COLS) * STEP_M, Math.floor(i / COLS) * STEP_M);
const note = () => document.getElementById('rp9-layout-note')?.textContent ?? '';
const selCount = () => document.getElementById('rp9-layout-selcount');

type Mods = { shiftKey?: boolean; altKey?: boolean; ctrlKey?: boolean; metaKey?: boolean };
function click(point: { x: number; y: number }, mods: Mods = {}) {
  map.emit('mousedown', { point, originalEvent: mods, preventDefault() {} });
  map.emit('mouseup', { point });
}
function drag(from: { x: number; y: number }, to: { x: number; y: number }, mods: Mods = {}) {
  map.emit('mousedown', { point: from, originalEvent: mods, preventDefault() {} });
  map.emit('mousemove', { point: to });
  map.emit('mouseup', { point: to });
}

describe('PV34 — la CAUSE réelle : le box-zoom natif de MapLibre', () => {
  it('l’éditeur éteint `map.boxZoom` (son geste par défaut EST le Maj + glissé du cadre)', () => {
    expect(map.boxZoomDisabled.count).toBe(1);
  });

  it('une carte sans `boxZoom` (hôte ancien / stub) ne fait pas planter la construction', () => {
    setupDom();
    const bare = makeMap() as unknown as Record<string, unknown>;
    delete bare.boxZoom;
    expect(() =>
      createLayoutEditor(makeCtx(), {
        map: bare as never,
        renderScene: () => {},
        prodConfigFromState: () => null,
        updateProductionWindow: () => {},
        snapshotActiveAreaResult: () => {},
        renderAreasPanel: () => {},
        renderActive: () => {},
        isObstacleMode: () => false,
      } as never),
    ).not.toThrow();
  });
});

describe('PV34 — encadrer SANS modificateur', () => {
  it('un glissé parti du toit, à côté des panneaux, ENCADRE (aucune touche à connaître)', () => {
    // (1,5 m ; 1,5 m) est à 2,12 m de la cellule la plus proche : hors du rayon de saisie
    // (~1,67 m), donc « sur le toit mais sur aucun panneau ».
    drag(pt(1.5, 1.5), pt(4.5, 4.5));
    expect(editor.selection()).toEqual([5]); // seule la cellule (3 m ; 3 m)
    expect(note()).toContain('sélectionnés');
  });

  it('un glissé parti HORS de la zone de calepinage reste un déplacement de carte', () => {
    click(cellPt(5)); // une sélection existante…
    expect(editor.selection()).toEqual([5]);
    drag(pt(40, 40), pt(50, 50)); // …que le pan ne doit pas toucher
    expect(editor.selection()).toEqual([5]);
    expect(note()).not.toContain('Aucun panneau dans le rectangle');
  });

  it('un glissé qui part D’UN panneau le déplace toujours (non-régression du geste PV29)', () => {
    editor.setSelection([]);
    map.emit('mousedown', { point: cellPt(0), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: cellPt(1) });
    map.emit('mouseup', { point: cellPt(1) });
    // La cellule 0 s'est libérée au profit d'une autre : le comptage est conservé.
    expect(ctx.layoutState!.occupied.size).toBe(TOTAL);
  });
});

describe('PV34 — Ctrl/⌘ + clic ajoute ou retire du groupe', () => {
  it('Ctrl + clic empile les panneaux un à un, puis les retire', () => {
    click(cellPt(1));
    click(cellPt(2), { ctrlKey: true });
    click(cellPt(3), { ctrlKey: true });
    expect(editor.selection()).toEqual([1, 2, 3]);
    click(cellPt(2), { ctrlKey: true });
    expect(editor.selection()).toEqual([1, 3]);
  });

  it('⌘ (metaKey) fait la même chose — le Mac n’est pas un cas particulier', () => {
    click(cellPt(1));
    click(cellPt(2), { metaKey: true });
    expect(editor.selection()).toEqual([1, 2]);
  });

  it('un clic NU repart d’une sélection à un seul panneau', () => {
    click(cellPt(1));
    click(cellPt(2), { ctrlKey: true });
    click(cellPt(7));
    expect(editor.selection()).toEqual([7]);
  });
});

describe('PV34 — Maj + glissé AJOUTE le cadre au groupe', () => {
  it('le second cadre s’ajoute au premier au lieu de le remplacer', () => {
    drag(pt(1.5, 1.5), pt(4.5, 4.5)); // cadre nu → {5}
    expect(editor.selection()).toEqual([5]);
    drag(pt(4.5, 1.5), pt(7.5, 4.5), { shiftKey: true }); // + la cellule (6 m ; 3 m) = 6
    expect(editor.selection()).toEqual([5, 6]);
  });

  it('un cadre NU, lui, repart de zéro', () => {
    editor.setSelection([0, 1, 2]);
    drag(pt(1.5, 1.5), pt(4.5, 4.5));
    expect(editor.selection()).toEqual([5]);
  });
});

describe('PV34 — le compteur permanent', () => {
  it('dit combien de panneaux sont tenus, au singulier comme au pluriel', () => {
    expect(selCount()?.textContent).toContain('Aucun panneau');
    expect(selCount()?.getAttribute('data-rp9-selcount')).toBe('0');
    click(cellPt(4));
    expect(selCount()?.textContent).toBe('1 panneau sélectionné');
    expect(selCount()?.getAttribute('data-rp9-selcount')).toBe('1');
    click(cellPt(5), { ctrlKey: true });
    expect(selCount()?.textContent).toContain('2 panneaux sélectionnés');
    expect(selCount()?.getAttribute('data-rp9-selcount')).toBe('2');
  });

  it('Échap remet le compteur à zéro', () => {
    click(cellPt(4));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(editor.selection()).toEqual([]);
    expect(selCount()?.getAttribute('data-rp9-selcount')).toBe('0');
  });
});

describe('PV34 — la rangée en un geste (double-clic), inchangée mais vérifiée', () => {
  it('un double-clic prend TOUTE la rangée du panneau visé', () => {
    map.emit('dblclick', { point: cellPt(5), preventDefault() {} });
    expect(editor.selection()).toEqual([4, 5, 6, 7]); // la rangée r = 1
    expect(selCount()?.getAttribute('data-rp9-selcount')).toBe('4');
  });
});

describe('PV34 — APERÇU VIVANT du glissé de groupe (mode lattice)', () => {
  it('les panneaux suivent le curseur PENDANT le geste, sans toucher à l’occupation', () => {
    // Groupe = la rangée du haut, décalé d'une rangée vers le bas… mais la lattice est
    // pleine : on libère d'abord la rangée du bas pour laisser une cible.
    editor.setSelection([]);
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    editor.setSelection([4, 5, 6, 7]);
    const before = renders.length;
    const occBefore = [...ctx.layoutState!.occupied].sort((a, b) => a - b);
    map.emit('mousedown', { point: cellPt(5), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: cellPt(9) }); // une rangée plus bas
    // Un rendu d'APERÇU a bien eu lieu…
    expect(renders.length).toBeGreaterThan(before);
    const preview = renders[renders.length - 1];
    expect([...preview].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 8, 9, 10, 11]);
    // …et l'état RÉEL n'a pas bougé tant que le doigt n'est pas relâché.
    expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual(occBefore);
    map.emit('mouseup', { point: cellPt(9) });
    expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 8, 9, 10, 11]);
  });

  it('un geste REFUSÉ restaure le rendu réel (l’écran ne ment pas) et ne bouge rien', () => {
    // On passe D'ABORD par une position VALIDE (l'aperçu peint la rangée déplacée), PUIS
    // on relâche sur une position impossible : le rendu d'aperçu doit être effacé.
    editor.setSelection([]);
    for (const i of [8, 9, 10, 11]) ctx.layoutState!.occupied.delete(i);
    editor.setSelection([4, 5, 6, 7]);
    const occBefore = [...ctx.layoutState!.occupied].sort((a, b) => a - b);
    map.emit('mousedown', { point: cellPt(5), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: cellPt(9) }); // valide → aperçu peint
    const previewed = renders[renders.length - 1];
    expect([...previewed].sort((a, b) => a - b)).not.toEqual(occBefore);
    map.emit('mousemove', { point: pt(60, 60) }); // très loin : hors tolérance de snap
    map.emit('mouseup', { point: pt(60, 60) });
    expect([...ctx.layoutState!.occupied].sort((a, b) => a - b)).toEqual(occBefore);
    const last = renders[renders.length - 1];
    expect([...last].sort((a, b) => a - b)).toEqual(occBefore); // le rendu montre le RÉEL
    expect(note()).toContain('rien n’a bougé');
  });
});

describe('PV34 — le TACTILE est inchangé (aucune régression du pan à un doigt)', () => {
  it('un doigt posé sur le toit mais sur aucun panneau ne trace PAS de cadre', () => {
    map.emit('touchstart', { point: pt(1.5, 1.5), points: [pt(1.5, 1.5)], preventDefault() {} });
    map.emit('touchmove', { point: pt(4.5, 4.5), preventDefault() {} });
    map.emit('touchend', { point: pt(4.5, 4.5) });
    expect(editor.selection()).toEqual([]);
  });

  it('le bouton « ▭ Sélection » reste le chemin tactile du cadre', () => {
    (document.getElementById('rp9-layout-select') as HTMLButtonElement).click();
    map.emit('touchstart', { point: pt(1.5, 1.5), points: [pt(1.5, 1.5)], preventDefault() {} });
    map.emit('touchmove', { point: pt(4.5, 4.5), preventDefault() {} });
    map.emit('touchend', { point: pt(4.5, 4.5) });
    expect(editor.selection()).toEqual([5]);
  });
});

describe('PV34 — un relâchement HORS de la carte termine quand même le geste', () => {
  it('le cadre commence sur la carte et se termine sur le document : la sélection est prise', () => {
    map.emit('mousedown', { point: pt(1.5, 1.5), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(4.5, 4.5) });
    window.dispatchEvent(
      new MouseEvent('mouseup', { clientX: 4.5 * PX_PER_M, clientY: 4.5 * PX_PER_M, bubbles: true }),
    );
    expect(editor.selection()).toEqual([5]);
  });
});

describe('PV34 — le cadre TRAVERSANT au travers du vrai câblage', () => {
  // Le cadre est ouvert par Maj + glissé : le point de départ de la bande fine tombe dans
  // le rayon de SAISIE d'un panneau, un glissé nu y déplacerait donc un panneau. C'est bien
  // la géométrie du cadre qu'on teste ici, pas l'arbitrage du geste (testé plus haut).
  it('un cadre qui effleure une rangée sans avaler ses centres la prend quand même', () => {
    boot(true); // plan AVEC empreinte de panneau (3 m × 1 m, azimut 180°)
    // Bande fine 20-40 cm au-dessus de la ligne des centres de la rangée r = 0 : aucun
    // centre dedans, mais elle mord les panneaux (demi-profondeur 50 cm).
    drag(pt(-1, 0.2), pt(10, 0.4), { shiftKey: true });
    expect(editor.selection()).toEqual([0, 1, 2, 3]);
  });

  it('sans empreinte décrite par le plan, on retombe sur le critère historique', () => {
    boot(false);
    map.emit('mousedown', { point: pt(-1, 0.2), originalEvent: { shiftKey: true }, preventDefault() {} });
    map.emit('mousemove', { point: pt(10, 0.4) }); // aucun centre dedans → rien
    expect(note()).toContain('Aucun panneau');
    map.emit('mouseup', { point: pt(10, 0.4) });
    expect(editor.selection()).toEqual([]);
  });
});

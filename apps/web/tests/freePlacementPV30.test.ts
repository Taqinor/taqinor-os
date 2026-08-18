// @vitest-environment jsdom
//
// PV30 — PLACEMENT LIBRE (ordre fondateur du 18/08 : « et si je veux réduire l'espace
// entre les panneaux et le bord du toit, ou entre les panneaux, pour en faire tenir
// plus ? »). Second mode d'édition, EN PARALLÈLE du mode lattice — les deux restent.
//
// Ce que ce fichier verrouille :
//   1. la géométrie PURE (lib/freeLayout) : trois contraintes DURES qui ne cèdent jamais
//      (contour, chevauchement, obstacle) et deux RELÂCHABLES qui, elles, cèdent quand
//      l'utilisateur le demande (retrait de rive, écart entre panneaux) ;
//   2. le câblage réel : bascule de mode, glissé continu, rangée rigide, ajout/retrait,
//      refus visible, annuler/rétablir, mesures affichées ;
//   3. la PERSISTANCE : le mode libre s'enregistre (mode + positions), le mode lattice
//      reste sérialisé EXACTEMENT comme avant, et le nombre de panneaux qui part au devis
//      suit les ajouts/retraits explicites.
import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  checkRect,
  checkPanelAt,
  moveFreePanels,
  addFreePanel,
  removeFreePanel,
  findFreeSpot,
  rectAt,
  toUV,
  freeStateFrom,
  type FreeGeom,
  type FreeLayoutState,
} from '../src/lib/freeLayout';
import { geomAxes } from '../src/lib/freeLayout';
import { createLayoutEditor } from '../src/scripts/roofPro11/layoutEditor';
import { serializeLayout } from '../src/scripts/roofPro11/prefill';
import { zoneRenderPlan } from '../src/scripts/roofPro11/viewerFullModel';
import { parseRoofLayout } from '../src/lib/proposition';
import { PANEL2_WATT } from '../src/lib/estimatorBrainV2';
import type { Ctx } from '../src/scripts/roofPro11/context';
import type { LayoutPlan, AreaRecord } from '../src/scripts/roofPro11/types';

// ═══════════════════════ 1. GÉOMÉTRIE PURE ═══════════════════════
// Toit carré de 20 m de côté, azimut 180° (plein sud) → u = axe est-ouest, s = axe nord-sud.
// Panneau 2 m (largeur) × 1 m (profondeur au sol) : des chiffres ronds pour que chaque
// distance attendue soit lisible à l'œil dans le test.
const SQUARE: [number, number][] = [
  [-10, -10],
  [10, -10],
  [10, 10],
  [-10, 10],
];

function geom(over: Partial<FreeGeom> = {}): FreeGeom {
  const { u, s } = geomAxes(180);
  return { u, s, widthM: 2, depthM: 1, ringENU: SQUARE, obstacles: [], ...over };
}
const NO_MARGIN = { setbackM: 0, gapM: 0 };
const STUDY_MARGIN = { setbackM: 0.5, gapM: 0.02 };
const empty = (): FreeLayoutState => freeStateFrom([]);
const withPanels = (...p: { cx: number; cy: number }[]): FreeLayoutState => freeStateFrom(p);

/** Contrôle d'un panneau POSABLE au point donné (aucun panneau à ignorer). */
function checkAt(state: FreeLayoutState, g: FreeGeom, cx: number, cy: number, margins = STUDY_MARGIN) {
  const [cu, cv] = toUV(g, cx, cy);
  return checkRect(state, g, rectAt(g, cu, cv), margins);
}

describe('PV30 §pur — les trois contraintes DURES ne cèdent jamais', () => {
  it('un panneau bien au centre passe', () => {
    expect(checkAt(empty(), geom(), 0, 0).ok).toBe(true);
  });

  it('DURE — un panneau qui déborde du toit est refusé, et le refus est « dur »', () => {
    const chk = checkAt(empty(), geom(), 9.5, 0, NO_MARGIN); // demi-largeur 1 m → dépasse à 10,5
    expect(chk.violations).toContain('outline');
    expect(chk.hard).toBe(true);
    expect(chk.ok).toBe(false);
  });

  it('DURE — même avec TOUTES les marges à zéro, le débord reste refusé', () => {
    expect(checkAt(empty(), geom(), 9.9, 0, NO_MARGIN).violations).toContain('outline');
  });

  it('DURE — un toit CONCAVE : 4 coins dedans mais une encoche qui traverse → refusé', () => {
    // Un « U » : l'encoche centrale remonte entre les deux branches.
    const u: [number, number][] = [
      [-10, -10],
      [10, -10],
      [10, 10],
      [4, 10],
      [4, -2],
      [-4, -2],
      [-4, 10],
      [-10, 10],
    ];
    const g = geom({ ringENU: u });
    // Centré sur l'encoche, à cheval : les coins bas sont dans la barre du U, les coins
    // hauts dans le vide — la détection de traversée d'arête est ce qui l'attrape.
    const chk = checkAt(empty(), g, 0, -2, NO_MARGIN);
    expect(chk.violations).toContain('outline');
    expect(chk.hard).toBe(true);
  });

  it('DURE — deux panneaux qui se chevauchent : refusé même à écart nul', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const chk = checkAt(st, geom(), 1, 0, NO_MARGIN); // panneaux de 2 m : décalage de 1 m = moitié dedans
    expect(chk.violations).toContain('overlap');
    expect(chk.hard).toBe(true);
  });

  it('deux panneaux JOINTIFS (écart 0) sont acceptés — ils ne se recouvrent pas', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const chk = checkAt(st, geom(), 2, 0, NO_MARGIN);
    expect(chk.ok).toBe(true);
    expect(chk.panelM).toBeCloseTo(0, 6);
  });

  it('DURE — l’empreinte d’un obstacle (et son dégagement) reste interdite', () => {
    const obstacle = {
      ring: [
        [-1, -1],
        [1, -1],
        [1, 1],
        [-1, 1],
      ] as [number, number][],
      clearanceM: 0.3,
    };
    const g = geom({ obstacles: [obstacle] });
    expect(checkAt(empty(), g, 0, 0, NO_MARGIN).violations).toContain('obstacle');
    // Juste à l'extérieur du dégagement : accepté (on n'interdit pas tout le toit).
    expect(checkAt(empty(), g, 0, 2.5, NO_MARGIN).ok).toBe(true);
  });
});

describe('PV30 §pur — les deux contraintes RELÂCHABLES cèdent quand on le demande', () => {
  it('RETRAIT DE RIVE : refusé à 50 cm, ACCEPTÉ une fois la marge ramenée à 5 cm', () => {
    const g = geom();
    // Centre à 8,6 m : le bord du panneau est à 9,1 m → 90 cm de rive… non : 0,9 m.
    // On vise 9,2 : bord à 9,7 → 30 cm de rive, sous le retrait de 50 cm.
    const tight = checkAt(empty(), g, 0, 9.2, STUDY_MARGIN);
    expect(tight.violations).toEqual(['setback']);
    expect(tight.hard).toBe(false); // relâchable : ce n'est PAS une impossibilité physique
    expect(tight.edgeM).toBeCloseTo(0.3, 6);
    // C'est tout l'objet du mode : je baisse la marge, ça passe.
    expect(checkAt(empty(), g, 0, 9.2, { setbackM: 0.05, gapM: 0.02 }).ok).toBe(true);
  });

  it('ÉCART ENTRE PANNEAUX : refusé à 2 cm, ACCEPTÉ à 0 — et la distance est MESURÉE', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const g = geom();
    const tight = checkAt(st, g, 2.01, 0, STUDY_MARGIN); // 1 cm d'écart, la marge en demande 2
    expect(tight.violations).toEqual(['gap']);
    expect(tight.hard).toBe(false);
    expect(tight.panelM).toBeCloseTo(0.01, 6);
    expect(checkAt(st, g, 2.01, 0, NO_MARGIN).ok).toBe(true);
  });

  it('les distances mesurées sont renvoyées MÊME quand le placement passe', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const chk = checkAt(st, geom(), 3, 0, NO_MARGIN);
    expect(chk.ok).toBe(true);
    expect(chk.panelM).toBeCloseTo(1, 6);
    // Panneau centré en 3 m, large de 2 m → son bord droit est à 4 m ; la rive est à 10 m.
    expect(chk.edgeM).toBeCloseTo(6, 6);
  });
});

describe('PV30 §pur — déplacer : rigide et tout ou rien', () => {
  it('un groupe subit EXACTEMENT la même translation (la forme est préservée)', () => {
    const st = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 0 }, { cx: 4, cy: 0 });
    const res = moveFreePanels(st, geom(), [0, 1, 2], 0, 3, NO_MARGIN);
    expect(res.ok).toBe(true);
    expect(st.panels.map((p) => [p.cx, p.cy])).toEqual([
      [-4, 3],
      [0, 3],
      [4, 3],
    ]);
  });

  it('si UN SEUL membre sortirait du toit, RIEN ne bouge', () => {
    const st = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 9 });
    const before = st.panels.map((p) => ({ ...p }));
    const res = moveFreePanels(st, geom(), [0, 1], 0, 1, NO_MARGIN);
    expect(res.ok).toBe(false);
    expect(res.blocked?.violations).toContain('outline');
    expect(st.panels).toEqual(before);
  });

  it('les membres du groupe ne se bloquent pas entre eux (ils libèrent leur place)', () => {
    // Deux panneaux jointifs qui glissent ensemble d'une largeur : sans la règle « le
    // groupe s'ignore au départ et se voit à l'arrivée », le 2ᵉ se croirait chevauché.
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 2, cy: 0 });
    const res = moveFreePanels(st, geom(), [0, 1], 2, 0, NO_MARGIN);
    expect(res.ok).toBe(true);
    expect(st.panels.map((p) => p.cx)).toEqual([2, 4]);
  });

  it('un SOUS-ENSEMBLE se détache en gardant sa forme', () => {
    const st = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 0 }, { cx: 4, cy: 0 });
    const res = moveFreePanels(st, geom(), [0, 1], 0, 4, NO_MARGIN);
    expect(res.ok).toBe(true);
    expect(st.panels.map((p) => [p.cx, p.cy])).toEqual([
      [-4, 4],
      [0, 4],
      [4, 0], // resté sur sa rangée
    ]);
  });
});

describe('PV30 §pur — ajouter et retirer', () => {
  it('ajoute au point visé quand c’est valide, refuse sinon (sans rien modifier)', () => {
    const st = empty();
    expect(addFreePanel(st, geom(), 0, 0, NO_MARGIN).ok).toBe(true);
    expect(st.panels.length).toBe(1);
    const refused = addFreePanel(st, geom(), 0.5, 0, NO_MARGIN); // chevauche
    expect(refused.ok).toBe(false);
    expect(refused.check.violations).toContain('overlap');
    expect(st.panels.length).toBe(1); // rien n'a été ajouté
  });

  it('retire un panneau par son index', () => {
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 4, cy: 0 });
    expect(removeFreePanel(st, 0)).toBe(true);
    expect(st.panels.map((p) => p.cx)).toEqual([4]);
    expect(removeFreePanel(st, 9)).toBe(false);
  });

  it('findFreeSpot trouve une place réelle, et rend null quand il n’y en a plus', () => {
    const g = geom();
    const spot = findFreeSpot(empty(), g, STUDY_MARGIN);
    expect(spot).not.toBeNull();
    expect(checkAt(empty(), g, spot!.cx, spot!.cy, STUDY_MARGIN).ok).toBe(true);
    // Un toit minuscule au regard du panneau : aucune place.
    const tiny = geom({ ringENU: [[-0.4, -0.2], [0.4, -0.2], [0.4, 0.2], [-0.4, 0.2]] });
    expect(findFreeSpot(empty(), tiny, NO_MARGIN)).toBeNull();
  });
});

// ═══════════════════════ 2. CÂBLAGE RÉEL ═══════════════════════
const DEG2M = (Math.PI / 180) * 6378137;
const ORIGIN: [number, number] = [-7.62, 33.59];
const PX_PER_M = 10;

const IDS = [
  'rp9-layout-window', 'rp9-layout-toggle', 'rp9-layout-panel', 'rp9-layout-count',
  'rp9-layout-kwc', 'rp9-layout-free', 'rp9-layout-cover', 'rp9-layout-grid',
  'rp9-layout-note', 'rp9-layout-azimuth', 'rp9-layout-az-value', 'rp9-free-controls',
  'rp9-free-measure',
];
const BTN_IDS = [
  'rp9-layout-minus', 'rp9-layout-plus', 'rp9-layout-reset', 'rp9-layout-fill',
  'rp9-layout-select', 'rp9-layout-row', 'rp9-layout-clear-sel', 'rp9-layout-undo',
  'rp9-layout-redo', 'rp9-layout-az-minus', 'rp9-layout-az-plus',
  'rp9-layout-mode-lattice', 'rp9-layout-mode-free', 'rp9-free-add',
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
  for (const id of ['rp9-free-setback', 'rp9-free-gap']) {
    const i = document.createElement('input');
    i.id = id;
    document.body.appendChild(i);
  }
}

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

/** Toit carré 20 m ; lattice 3 × 3 au pas de 4 m ; panneau 2 m × 1 m au sol. */
const LAT_CELLS = [-4, 0, 4].flatMap((cy) => [-4, 0, 4].map((cx) => ({ cx, cy })));
function seedPlan(): LayoutPlan {
  return {
    pack: { origin: ORIGIN, azimuthDeg: 180, ringENU: SQUARE } as never,
    grid: {
      count: LAT_CELLS.length,
      kwc: (LAT_CELLS.length * PANEL2_WATT) / 1000,
      panels: LAT_CELLS,
      rowWidthM: 2,
      rowPitchM: 4,
      slopeLenM: 1,
      footprintPerPanelM2: 2, // 2 m de large × 1 m de profondeur au sol
    } as never,
    tiltDeg: 13,
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
    layoutOptimalCount: LAT_CELLS.length,
    layoutSel: null,
    neededPanels: LAT_CELLS.length,
    roofType: 'flat',
    facingAzimuthDeg: 180,
    facingManual: false,
    obstacles: [],
    freeMode: false,
    freeState: null,
    freeMargins: { setbackM: 0.5, gapM: 0.02 },
    ...over,
  } as unknown as Ctx;
}

type PaintCall = { selected: number[]; hover: number | null; refused: boolean };
function makeEditor(ctx: Ctx, map: ReturnType<typeof makeMap>, paints: PaintCall[], confirmDiscard?: (m: string) => boolean) {
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
    ...(confirmDiscard ? { confirmDiscard } : {}),
  });
}

const pt = (xM: number, yM: number) => ({ x: xM * PX_PER_M, y: yM * PX_PER_M });
const note = () => document.getElementById('rp9-layout-note')?.textContent ?? '';
const measure = () => document.getElementById('rp9-free-measure')?.textContent ?? '';
const click2 = (map: ReturnType<typeof makeMap>, p: { x: number; y: number }, mods: Record<string, boolean> = {}) => {
  map.emit('mousedown', { point: p, originalEvent: mods, preventDefault() {} });
  map.emit('mouseup', { point: p });
};
const drag2 = (map: ReturnType<typeof makeMap>, a: { x: number; y: number }, b: { x: number; y: number }) => {
  map.emit('mousedown', { point: a, originalEvent: {}, preventDefault() {} });
  map.emit('mousemove', { point: b });
  map.emit('mouseup', { point: b });
};

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

describe('PV30 §câblage — les deux modes cohabitent, la lattice reste le défaut', () => {
  it('on démarre en mode lattice ; le bouton « Placement libre » bascule', () => {
    expect(editor.isFreeMode()).toBe(false);
    expect(document.getElementById('rp9-layout-mode-lattice')?.getAttribute('aria-pressed')).toBe('true');
    document.getElementById('rp9-layout-mode-free')!.dispatchEvent(new Event('click'));
    expect(editor.isFreeMode()).toBe(true);
    expect(document.getElementById('rp9-layout-mode-free')?.getAttribute('aria-pressed')).toBe('true');
    expect(document.getElementById('rp9-free-controls')?.hasAttribute('hidden')).toBe(false);
  });

  it('la bascule PRÉSERVE les positions au millimètre (aucun re-calcul)', () => {
    editor.setFreeMode(true);
    expect(editor.freePanels().map((p) => [p.cx, p.cy])).toEqual(LAT_CELLS.map((c) => [c.cx, c.cy]));
  });

  it('revenir à la lattice DEMANDE confirmation, et un refus garde le placement libre', () => {
    const ctx2 = makeCtx();
    const refuse = vi.fn(() => false);
    const ed2 = makeEditor(ctx2, makeMap(), [], refuse);
    ed2.ensureLayoutState();
    ed2.setFreeMode(true);
    document.getElementById('rp9-layout-mode-lattice')!.dispatchEvent(new Event('click'));
    expect(refuse).toHaveBeenCalledTimes(1);
    expect(ed2.isFreeMode()).toBe(true);
    expect(note()).toContain('conservé');
  });

  it('les marges par défaut sont celles de l’étude, affichées en centimètres', () => {
    editor.setFreeMode(true);
    expect(editor.freeMargins()).toEqual({ setbackM: 0.5, gapM: 0.02 });
    expect((document.getElementById('rp9-free-setback') as HTMLInputElement).value).toBe('50');
    expect((document.getElementById('rp9-free-gap') as HTMLInputElement).value).toBe('2');
  });
});

describe('PV30 §câblage — déplacement CONTINU (ce que la lattice ne pouvait pas faire)', () => {
  beforeEach(() => {
    editor.setFreeMode(true);
  });

  it('un panneau se pose à une position quelconque, pas sur une cellule', () => {
    click2(map, pt(0, 0)); // saisit le panneau du centre (cellule 4 → index 4)
    drag2(map, pt(0, 0), pt(1.37, 0)); // 13,7 px : au-delà du seuil de glissé (12 px)
    const moved = editor.freePanels()[4];
    expect(moved.cx).toBeCloseTo(1.37, 6); // 1,37 m : aucune cellule ici (elles sont à 0 et 4)
    expect(moved.cy).toBeCloseTo(0, 6);
  });

  it('les flèches ajustent au CENTIMÈTRE', () => {
    editor.setSelection([4]);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    expect(editor.freePanels()[4].cx).toBeCloseTo(0.01, 6);
  });

  it('une RANGÉE entière se prend au double-clic et se déplace rigidement', () => {
    map.emit('dblclick', { point: pt(0, 0), preventDefault() {} });
    expect(editor.selection()).toEqual([3, 4, 5]); // la rangée cy = 0
    drag2(map, pt(0, 0), pt(0, 1.5));
    const ys = [3, 4, 5].map((i) => editor.freePanels()[i].cy);
    expect(ys).toEqual([1.5, 1.5, 1.5]); // rigide : même translation pour les trois
  });

  it('les distances MESURÉES s’affichent pendant le glissé (rive + voisin, en cm)', () => {
    map.emit('mousedown', { point: pt(0, 0), originalEvent: {}, preventDefault() {} });
    map.emit('mousemove', { point: pt(0, 2) });
    expect(measure()).toMatch(/Rive : .*cm/);
    expect(measure()).toMatch(/Voisin : .*cm/);
  });
});

describe('PV30 §câblage — un refus reste un refus, et il se voit', () => {
  beforeEach(() => {
    editor.setFreeMode(true);
  });

  it('sortir du toit : rien ne bouge, la note NOMME la raison, la 3D vire au rouge', () => {
    const before = editor.freePanels();
    click2(map, pt(4, 0));
    paints.length = 0;
    drag2(map, pt(4, 0), pt(40, 0)); // très au-delà de la rive
    expect(editor.freePanels()).toEqual(before);
    expect(note()).toContain('sortirait du toit');
    expect(paints.some((p) => p.refused)).toBe(true);
  });

  it('chevaucher un voisin : refusé, et la note le dit', () => {
    click2(map, pt(0, 0));
    drag2(map, pt(0, 0), pt(3.5, 0)); // le voisin est en cx = 4, largeur 2 m
    expect(note()).toContain('chevaucherait');
  });

  it('un refus ne laisse PAS d’action fantôme dans l’historique', () => {
    click2(map, pt(4, 0));
    drag2(map, pt(4, 0), pt(40, 0));
    expect(editor.undo()).toBe(false);
    expect(editor.redo()).toBe(false);
  });
});

describe('PV30 §câblage — RÉDUIRE une marge fait tenir plus de panneaux', () => {
  it('baisser le retrait de rive autorise une position que l’étude refusait', () => {
    editor.setFreeMode(true);
    // Un panneau seul, poussé tout près de la rive nord (rive à 10 m, demi-profondeur 0,5).
    const st: FreeLayoutState = freeStateFrom([{ cx: 0, cy: 0 }]);
    const g: FreeGeom = { ...geom(), ringENU: SQUARE };
    expect(checkPanelAt(st, g, 0, 0, 9.2, { setbackM: 0.5, gapM: 0.02 }).ok).toBe(false);
    editor.setFreeMargins({ setbackM: 0.05 });
    expect(editor.freeMargins().setbackM).toBeCloseTo(0.05, 6);
    expect(checkPanelAt(st, g, 0, 0, 9.2, editor.freeMargins()).ok).toBe(true);
  });

  it('le champ « retrait de rive » lit des CENTIMÈTRES et n’est jamais rejeté', () => {
    editor.setFreeMode(true);
    const el = document.getElementById('rp9-free-setback') as HTMLInputElement;
    el.value = '7,5'; // virgule décimale française : acceptée telle quelle
    el.dispatchEvent(new Event('change'));
    expect(editor.freeMargins().setbackM).toBeCloseTo(0.075, 6);
    // Saisie illisible : la marge précédente est CONSERVÉE (jamais un rejet bruyant).
    el.value = 'abc';
    el.dispatchEvent(new Event('change'));
    expect(editor.freeMargins().setbackM).toBeCloseTo(0.075, 6);
  });

  it('un changement de marge est ANNULABLE comme le reste', () => {
    editor.setFreeMode(true);
    const el = document.getElementById('rp9-free-gap') as HTMLInputElement;
    el.value = '0';
    el.dispatchEvent(new Event('change'));
    expect(editor.freeMargins().gapM).toBeCloseTo(0, 6);
    expect(editor.undo()).toBe(true);
  });
});

describe('PV30 §câblage — AJOUTER et RETIRER des panneaux (acte explicite du fondateur)', () => {
  beforeEach(() => {
    editor.setFreeMode(true);
  });

  it('« Ajouter un panneau » puis un clic pose un panneau de plus', () => {
    const before = editor.freePanels().length;
    document.getElementById('rp9-free-add')!.dispatchEvent(new Event('click'));
    expect(note()).toContain('Touchez l’endroit');
    click2(map, pt(-8, 8));
    expect(editor.freePanels().length).toBe(before + 1);
    expect(note()).toContain('Panneau ajouté');
  });

  it('poser sur une place invalide refuse SANS rien ajouter, en nommant la raison', () => {
    const before = editor.freePanels().length;
    document.getElementById('rp9-free-add')!.dispatchEvent(new Event('click'));
    click2(map, pt(0, 0)); // pile sur un panneau existant
    expect(editor.freePanels().length).toBe(before);
    expect(note()).toContain('chevaucherait');
  });

  it('Alt + clic retire le panneau visé', () => {
    const before = editor.freePanels().length;
    click2(map, pt(0, 0), { altKey: true });
    expect(editor.freePanels().length).toBe(before - 1);
    expect(note()).toContain('Panneau retiré');
  });

  it('ajout et retrait s’annulent / se rétablissent', () => {
    const before = editor.freePanels().length;
    document.getElementById('rp9-free-add')!.dispatchEvent(new Event('click'));
    click2(map, pt(-8, 8));
    expect(editor.freePanels().length).toBe(before + 1);
    expect(editor.undo()).toBe(true);
    expect(editor.freePanels().length).toBe(before);
    expect(editor.redo()).toBe(true);
    expect(editor.freePanels().length).toBe(before + 1);
  });

  it('« Échap » désarme l’ajout au lieu de poser n’importe où', () => {
    document.getElementById('rp9-free-add')!.dispatchEvent(new Event('click'));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    const before = editor.freePanels().length;
    click2(map, pt(-8, 8));
    expect(editor.freePanels().length).toBe(before);
  });
});

describe('PV30 §garde-fou — un placement libre est toujours un travail manuel', () => {
  it('confirmDiscardEdits DEMANDE avant tout ré-agencement automatique', () => {
    const ask = vi.fn(() => false);
    const ctx2 = makeCtx();
    const ed2 = makeEditor(ctx2, makeMap(), [], ask);
    ed2.ensureLayoutState();
    ed2.setFreeMode(true);
    expect(ed2.hasManualEdits()).toBe(true);
    expect(ed2.confirmDiscardEdits()).toBe(false);
    expect(ask).toHaveBeenCalledTimes(1);
  });
});

// ═══════════════════════ 3. PERSISTANCE ═══════════════════════
const SER_VERTS: [number, number][] = [
  [-7.62, 33.59],
  [-7.619, 33.59],
  [-7.619, 33.591],
  [-7.62, 33.591],
];

function serZone(): AreaRecord {
  return {
    id: 'area-1',
    label: 'Zone 1',
    vertices: SER_VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 13,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 9,
    neededAuto: false,
    result: null,
    renderPlan: null,
  };
}

function serCtx(free: { cx: number; cy: number }[] | null): Ctx {
  const base = makeCtx({
    areas: [serZone()],
    activeAreaId: 'area-1',
    vertices: SER_VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    neededPanels: 9,
  } as unknown as Partial<Ctx>);
  const map2 = makeMap();
  const ed = createLayoutEditor(base, {
    map: map2 as never,
    renderScene: () => {},
    prodConfigFromState: () => null,
    updateProductionWindow: () => {},
    snapshotActiveAreaResult: () => {},
    renderAreasPanel: () => {},
    renderActive: () => {},
    isObstacleMode: () => false,
    setPanelHighlight: () => {},
  });
  ed.ensureLayoutState();
  if (free) {
    ed.setFreeMode(true);
    base.freeState = freeStateFrom(free);
  }
  return base;
}

describe('PV30 §persistance — le placement libre s’enregistre, la lattice ne bouge pas', () => {
  it('mode LATTICE : le JSON est identique à avant (aucune clé `mode` ajoutée)', () => {
    setupDom();
    const json = serializeLayout(serCtx(null));
    const geo = json.zones[0].geometry!;
    expect(geo.mode).toBeUndefined();
    expect(geo.panels.length).toBe(LAT_CELLS.length);
  });

  it('mode LIBRE : positions verbatim + drapeau `mode: "free"`', () => {
    setupDom();
    const free = [
      { cx: 0.37, cy: 1.5 },
      { cx: 2.4, cy: 1.5 },
    ];
    const json = serializeLayout(serCtx(free));
    const geo = json.zones[0].geometry!;
    expect(geo.mode).toBe('free');
    expect(geo.panels.map((p) => [p.cx, p.cy])).toEqual(free.map((p) => [p.cx, p.cy]));
  });

  it('le NOMBRE qui part au devis suit les ajouts/retraits explicites', () => {
    setupDom();
    // `sync_devis_from_layout` (PV18) lit `result.panels` — pas la longueur du tableau.
    // C'est donc CE chiffre qui doit refléter le placement libre, sinon le devis resterait
    // sur l'ancien comptage.
    const json = serializeLayout(serCtx([{ cx: 0, cy: 0 }, { cx: 2.4, cy: 0 }, { cx: 4.8, cy: 0 }]));
    expect(json.zones[0].geometry!.count).toBe(3);
    expect(json.result.panels).toBe(3);
  });

  it('hydrater un dossier « free » repose les positions VERBATIM (aucun re-snap)', () => {
    setupDom();
    const c = makeCtx();
    const m = makeMap();
    const ed = makeEditor(c, m, []);
    ed.ensureLayoutState();
    const centers = [
      { cx: 0.37, cy: 1.5 },
      { cx: 2.4, cy: 1.5 },
    ];
    expect(ed.hydrateLayout(centers, ORIGIN, 'free')).toBe(true);
    expect(ed.isFreeMode()).toBe(true);
    expect(ed.freePanels().map((p) => [p.cx, p.cy])).toEqual(centers.map((p) => [p.cx, p.cy]));
  });

  it('hydrater un dossier « lattice » garde le re-snap historique', () => {
    setupDom();
    const c = makeCtx();
    const ed = makeEditor(c, makeMap(), []);
    ed.ensureLayoutState();
    expect(ed.hydrateLayout([{ cx: 0.2, cy: 0.2 }], ORIGIN, 'lattice')).toBe(true);
    expect(ed.isFreeMode()).toBe(false);
    expect([...c.layoutState!.occupied]).toEqual([4]); // re-snappé sur la cellule (0,0)
  });
});

describe('PV30 §visionneuses — un placement libre se rejoue tel quel', () => {
  const V_LAT0 = 33.5;
  const V_LNG0 = -7.6;
  const V_DEG2M = (Math.PI / 180) * 6378137;
  const V_COS = Math.cos((V_LAT0 * Math.PI) / 180);
  const vAt = (x: number, y: number): [number, number] => [V_LNG0 + x / (V_DEG2M * V_COS), V_LAT0 + y / V_DEG2M];
  // Des positions volontairement « non rondes » : elles ne tomberaient sur AUCUNE lattice.
  const FREE_PANELS = [
    { cx: -3.17, cy: 0 },
    { cx: -0.81, cy: 0 },
    { cx: 1.55, cy: 0.4 },
  ];

  function freeLayoutJson() {
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
            count: FREE_PANELS.length,
            origin: [V_LNG0, V_LAT0],
            panels: FREE_PANELS,
            mode: 'free',
          },
        },
      ],
    });
    if (!parsed) throw new Error('fixture invalide');
    return parsed;
  }

  it('la visionneuse rejoue les centres LIBRES au millimètre', () => {
    const plan = zoneRenderPlan(freeLayoutJson().zones[0]);
    expect(plan).not.toBeNull();
    expect(plan!.grid.panels.map((p) => [p.cx, p.cy])).toEqual(FREE_PANELS.map((p) => [p.cx, p.cy]));
    expect(plan!.count).toBe(FREE_PANELS.length);
  });
});

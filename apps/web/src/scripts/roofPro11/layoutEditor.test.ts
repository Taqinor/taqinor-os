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
import { occupiedCount } from '../../lib/layoutVariability'; // ACAL891
import { createLayoutEditor } from './layoutEditor';
import { creerBarreSelection } from './barreSelection';
import { creerAnnulerAtelier } from './annulerAtelier';
import { glisserAimante } from './reperesAlignement';
import { DEFAULT_FREE_MARGINS, freeGeomFrom } from './freeMode';
import { type Ctx } from './context';
import { type LayoutPlan } from './types';
import { createLayoutState } from '../../lib/layoutVariability';
import { placeFreePanels, type FreePanel } from '../../lib/freeLayout';
import { carteEditeurFactice, depsEditeur } from './harnaisAtelier';
import { viderCollage } from './collage'; // ACAL553
import { natureSilhouette, silhouetteDuLot, silhouetteGeoJSON, peindreSilhouette, texteDeMesure } from './silhouetteGlisse'; // ACAL551
import type { FreeCheck, FreeGeom } from '../../lib/freeLayout'; // ACAL551

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
  const map = carteEditeurFactice(container, { disable: boxZoomDisable, enable: boxZoomEnable });
  return { map, boxZoomDisable, boxZoomEnable };
}

const makeDeps = depsEditeur;

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

describe('CALX113 — symetriserSelection', () => {
  it('symétrie appliquée deux fois de suite rend l’état initial à 10⁻⁹ près', () => {
    const panels: FreePanel[] = [{ cx: -5, cy: 0 }]; // u = 5, v = 0
    const before = panels.map((p) => ({ ...p }));
    const { editor } = buildFreeEditor(20, panels);

    // Axe = la droite u = 0 (deux points ENU distincts sur x = 0, cf. l'en-tête du fichier).
    const axis = { a: [0, -5] as [number, number], b: [0, 5] as [number, number] };

    expect(editor.symetriserSelection([0], axis)).toBe(true);
    const mirrored = editor.freePanels()[0];
    expect(mirrored.cx).toBeCloseTo(5, 9); // u = -5 → cx = 5
    expect(mirrored.angleDeg).toBeCloseTo(180, 9); // orientation réfléchie AVEC le centre

    expect(editor.symetriserSelection([0], axis)).toBe(true);
    const back = editor.freePanels()[0];
    expect(back.cx).toBeCloseTo(before[0].cx, 9);
    expect(back.cy).toBeCloseTo(before[0].cy, 9);
    expect(((back.angleDeg ?? 0) % 360 + 360) % 360).toBeCloseTo(0, 9);
  });

  it('un module dont l’image sortirait du posable fait refuser le geste ENTIER, en nommant le motif', () => {
    const panels: FreePanel[] = [{ cx: -8.5, cy: 0 }]; // u = 8.5
    const before = panels.map((p) => ({ ...p }));
    const { editor } = buildFreeEditor(10, panels);

    // Axe vertical à u = 10 (bord du toit) : l'image part à u = 11.5, hors du posable.
    const axis = { a: [-10, -5] as [number, number], b: [-10, 5] as [number, number] };
    const ok = editor.symetriserSelection([0], axis);
    expect(ok).toBe(false);
    expect(editor.freePanels()).toEqual(before); // tout ou rien : rien n'a bougé

    const note = document.getElementById('rp9-layout-note');
    expect(note?.textContent).toContain('sortirait du toit');
  });

  it('deux points confondus ne définissent aucun axe : le geste est refusé sans rien muter', () => {
    const panels: FreePanel[] = [{ cx: -5, cy: 0 }];
    const { editor } = buildFreeEditor(20, panels);
    const same = [1, 1] as [number, number];
    expect(editor.symetriserSelection([0], { a: same, b: same })).toBe(false);
    expect(editor.freePanels()).toEqual(panels);
  });
});

describe('CALX116 — panelsInLasso', () => {
  // Anneau en « L » (concave) : bande basse [0,10]×[0,4] + colonne droite [4,10]×[4,10].
  // Sa boîte ENGLOBANTE est le carré [0,10]×[0,10] tout entier — un panneau posé dans le
  // coin NON couvert (l'encoche haut-gauche) doit donc être retenu par la boîte mais PAS
  // par l'anneau réel : c'est exactement la garantie que le lasso doit apporter.
  const LASSO_RING: [number, number][] = [
    [0, 0],
    [10, 0],
    [10, 10],
    [4, 10],
    [4, 4],
    [0, 4],
  ];

  it('retient les modules de la poche, PAS ceux de la boîte englobante (placement libre)', () => {
    const panels: FreePanel[] = [
      { cx: 2, cy: 7 }, // dans l'ENCOCHE (boîte englobante seulement) — à exclure
      { cx: 7, cy: 7 }, // dans la colonne droite — à retenir
      { cx: 2, cy: 2 }, // dans la bande basse — à retenir
    ];
    const { editor } = buildFreeEditor(20, panels);
    expect(editor.panelsInLasso(LASSO_RING)).toEqual([1, 2]);
  });

  it('même garantie en mode lattice (emplacements validés)', () => {
    const { map } = makeMap();
    const ctx = makeFreeCtx(makePlan(20), []);
    ctx.freeMode = false;
    ctx.layoutState = createLayoutState([{ cx: 2, cy: 7 }, { cx: 7, cy: 7 }, { cx: 2, cy: 2 }], 3);
    const editor = createLayoutEditor(ctx, makeDeps(map));
    expect(editor.panelsInLasso(LASSO_RING)).toEqual([1, 2]);
  });

  it('anneau dégénéré (< 3 points) ⇒ aucune sélection, jamais une exception', () => {
    const { editor } = buildFreeEditor(20, [{ cx: 1, cy: 1 }]);
    expect(editor.panelsInLasso([[0, 0], [1, 1]])).toEqual([]);
  });

  it('la bascule cadre/lasso est une puce du module, par défaut sur CADRE', () => {
    const { editor } = buildFreeEditor(20, []);
    expect(editor.isLassoMode()).toBe(false);
    const btn = document.getElementById('rp9-layout-lasso') as HTMLButtonElement | null;
    expect(btn).not.toBeNull();
    expect(btn!.getAttribute('aria-pressed')).toBe('false');
    btn!.click();
    expect(editor.isLassoMode()).toBe(true);
    expect(btn!.getAttribute('aria-pressed')).toBe('true');
  });

  it('le box-zoom MapLibre reste désactivé (piège documenté layoutEditor.ts:309-318) — jamais réactivé par ce module', () => {
    const { boxZoomDisable, boxZoomEnable } = buildFreeEditor(20, []);
    expect(boxZoomDisable).toHaveBeenCalledTimes(1);
    expect(boxZoomEnable).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL28 — `hydrateLayout` en mode LIBRE repose la face E/O enregistrée (chevrons dos à
// dos conservés), comme l'entrée en mode libre (`enterFreeMode`).
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL28 — hydrateLayout free conserve face E/W', () => {
  it('hydrateLayout free conserve face E/W', () => {
    const { map } = makeMap();
    const plan = makePlan(40);
    (plan.grid as unknown as { panels: unknown[] }).panels = [
      { cx: 0, cy: 0 },
      { cx: -3, cy: 0 },
    ];
    const ctx = makeFreeCtx(plan, []);
    (ctx as unknown as { freeMode: boolean; freeState: unknown }).freeMode = false;
    (ctx as unknown as { freeMode: boolean; freeState: unknown }).freeState = null;
    const editor = createLayoutEditor(ctx, makeDeps(map));
    const enregistres = [
      { cx: 0, cy: 0, face: 'E' as const },
      { cx: -3, cy: 0, face: 'W' as const },
      { cx: -6, cy: 0 },
    ];
    expect(editor.hydrateLayout(enregistres, [-7.6, 33.5], 'free')).toBe(true);
    const reposes = editor.freePanels();
    expect(reposes.map((p) => p.face)).toEqual(['E', 'W', undefined]);
  });
});

// ACAL411 — la barre Pivoter / Aligner / Répartir pilote les fonctions de sélection libre.
describe('ACAL411 — barre de sélection : aligner, répartir, pivoter', () => {
  function monterBarre(panels: FreePanel[]) {
    const { map } = makeMap();
    const ctx = makeFreeCtx(makePlan(40), panels);
    let barre: { rafraichir: () => void } | undefined;
    const editor = createLayoutEditor(ctx, { ...makeDeps(map), onSelectionChange: () => barre?.rafraichir() });
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const statuts: string[] = [];
    barre = creerBarreSelection({ hote: () => hote, editeur: editor, setStatus: (m) => void statuts.push(m) });
    const clic = (txt: string) =>
      [...hote.querySelectorAll('button')].find((b) => b.textContent === txt)!.click();
    return { editor, hote, statuts, clic };
  }

  it('« Aligner en rangée » met 3 centres sur la même coordonnée v, « Répartir » refuse à 2 panneaux', () => {
    const { editor, hote, statuts, clic } = monterBarre([
      { cx: 0, cy: 0 },
      { cx: -4, cy: 1.5 },
      { cx: -8, cy: -1 },
    ]);
    const barre = hote.querySelector('#rp9-barre-selection') as HTMLElement;
    expect(barre.style.display).toBe('none');
    editor.setSelection([0, 1, 2]);
    expect(barre.style.display).toBe('flex');
    clic('Aligner en rangée');
    const cys = editor.freePanels().map((p) => p.cy);
    expect(cys[1]).toBeCloseTo(cys[0], 9);
    expect(cys[2]).toBeCloseTo(cys[0], 9);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('Aligné — 3 panneaux');
    editor.setSelection([0, 1]);
    clic('Répartir');
    expect(statuts.at(-1)).toContain('au moins 3 panneaux');
  });

  it('« Pivoter » lit un angle libre ; un angle illisible est refusé en nommant le champ', () => {
    const { editor, hote, statuts, clic } = monterBarre([{ cx: 0, cy: 0 }]);
    editor.setSelection([0]);
    (hote.querySelector('input') as HTMLInputElement).value = 'abc';
    clic('Pivoter');
    expect(statuts.at(-1)).toContain('angle');
    (hote.querySelector('input') as HTMLInputElement).value = '12,5';
    clic('Pivoter');
    expect(editor.freePanels()[0].angleDeg).toBeCloseTo(12.5, 9);
  });
});

// ACAL425 — aimantation et repères pendant le glissé libre.
describe('ACAL425 — glissé libre : colle au voisin à moins du seuil et publie un repère ; coupé par A', () => {
  const panels: FreePanel[] = [{ cx: 0, cy: 0 }, { cx: -2.05, cy: 0.03 }]; // u = 0 et 2,05 : 5 cm du collage
  function essai(actif: boolean, poserOk = true) {
    const { map } = makeMap();
    const plan = makePlan(40);
    const editor = createLayoutEditor(makeFreeCtx(plan, panels.map((p) => ({ ...p }))), makeDeps(map));
    const g = freeGeomFrom(plan, [])!;
    const poses: Array<[number, number]> = [];
    const segs: unknown[][] = [];
    const res = glisserAimante({
      actif, idx: 1, g, panels, anchor: { cx: -6, cy: 0 }, dx: 3.95, dy: 0.03,
      snap: editor.freeSnapCandidate,
      poser: (dx, dy) => {
        poses.push([dx, dy]);
        return { ok: poserOk || poses.length > 1 };
      },
      reperes: { afficher: (s) => void segs.push([...s]) },
    });
    return { res, poses, segs, g };
  }

  it('collé : la position vise u = 2 (bord à bord), un repère longe le bord commun', () => {
    const { poses, segs } = essai(true);
    expect(poses).toHaveLength(1);
    expect(poses[0][0]).toBeCloseTo(4, 9); // cx cible -2 depuis -6
    expect(segs.at(-1)).toHaveLength(1);
  });

  it('aimantation coupée : ni collage ni repère ; collage refusé par une contrainte dure : ignoré', () => {
    const coupe = essai(false);
    expect(coupe.poses).toEqual([[3.95, 0.03]]);
    expect(coupe.segs.at(-1)).toEqual([]);
    const dur = essai(true, false);
    expect(dur.poses).toHaveLength(2);
    expect(dur.poses[1]).toEqual([3.95, 0.03]);
    expect(dur.segs.at(-1)).toEqual([]);
  });

  it('marges par défaut (écart 2 cm, relâchable) : le collage garde l’écart, il est posé et publie un repère', () => {
    const { map } = makeMap();
    const plan = makePlan(40);
    const ctx = makeFreeCtx(plan, [{ cx: 0, cy: 0 }, { cx: -6, cy: 0 }]);
    const editor = createLayoutEditor(ctx, makeDeps(map));
    const g = freeGeomFrom(plan, [])!;
    const st = (ctx as unknown as { freeState: { panels: FreePanel[] } }).freeState;
    const segs: unknown[][] = [];
    const res = glisserAimante({
      actif: true, idx: 1, g, panels: st.panels, anchor: { cx: -6, cy: 0 }, dx: 3.95, dy: 0,
      snap: editor.freeSnapCandidate, marges: DEFAULT_FREE_MARGINS,
      poser: (dx, dy) => placeFreePanels(st, g, [{ index: 1, cx: -6 + dx, cy: dy }], DEFAULT_FREE_MARGINS),
      reperes: { afficher: (s) => void segs.push([...s]) },
    });
    expect(res.ok).toBe(true);
    expect(st.panels[1].cx).toBeCloseTo(-2.02, 9); // u = 2 + 0,02 : bord à bord + l'écart
    expect(segs.at(-1)).toHaveLength(1);
  });
});

// ACAL412 — Annuler / Rétablir joignables hors du panneau de disposition.
describe('ACAL412 — Ctrl+Z hors mode disposition restaure le sommet et redessine', () => {
  function monter() {
    const { map } = makeMap();
    const ctx = makeFreeCtx(makePlan(40), []);
    (ctx as unknown as { layoutMode: boolean }).layoutMode = false;
    (ctx as unknown as { vertices: [number, number][] }).vertices = [[0, 0], [1, 0], [1, 1]];
    const editor = createLayoutEditor(ctx, makeDeps(map));
    const redessins = vi.fn();
    const statuts: string[] = [];
    const a = creerAnnulerAtelier({
      ancre: null,
      editeur: editor,
      modeDisposition: () => Boolean(ctx.layoutMode && ctx.layoutState),
      apres: redessins,
      setStatus: (m) => void statuts.push(m),
      ctx, // ACAL1901 — le bouton de la barre passe par le même geste
    });
    return { ctx, a, redessins, statuts };
  }

  it('un sommet déplacé s’annule par Ctrl+Z puis se rétablit, avec redessin', () => {
    const { ctx, a, redessins } = monter();
    ctx.pushWorkshopHistory?.(); // photo AVANT le déplacement, comme obstaclesUi
    (ctx as unknown as { vertices: [number, number][] }).vertices = [[0, 0], [1, 0], [5, 5]];
    const evt = { key: 'z', ctrlKey: true, target: document.body, preventDefault: vi.fn() };
    expect(a.surFrappe(evt)).toBe(true);
    expect(evt.preventDefault).toHaveBeenCalled();
    expect(ctx.vertices[2]).toEqual([1, 1]);
    expect(redessins).toHaveBeenCalledTimes(1);
    expect(a.surFrappe({ key: 'y', ctrlKey: true, target: document.body })).toBe(true);
    expect(ctx.vertices[2]).toEqual([5, 5]);
  });

  it('rien à annuler : la touche reste au navigateur ; champ de saisie et mode disposition : intacts', () => {
    const { ctx, a, statuts } = monter();
    const evt = { key: 'z', ctrlKey: true, target: document.body, preventDefault: vi.fn() };
    expect(a.surFrappe(evt)).toBe(false);
    expect(evt.preventDefault).not.toHaveBeenCalled();
    expect(statuts.at(-1)).toBe('Rien à annuler.');
    ctx.pushWorkshopHistory?.();
    const champ = document.createElement('input');
    expect(a.surFrappe({ key: 'z', ctrlKey: true, target: champ })).toBe(false); // Ctrl+Z dans un champ
    expect(a.annuler()).toBe(true); // la photo est restée intacte
  });

  // ACAL1901 (T3-POSE-001) — le bouton Annuler de la barre (#rp9-layout-undo, cliqué par la coque) défait COMME Ctrl+Z.
  it('clic sur Annuler hors mode disposition : sommet restauré ET redessiné ; Rétablir de même', () => {
    document.body.innerHTML = ''; // ids uniques : les boutons sont ceux de CET éditeur
    const { ctx, redessins } = monter();
    ctx.pushWorkshopHistory?.(); // photo AVANT le coin glissé (70 → 91 m²)
    (ctx as unknown as { vertices: [number, number][] }).vertices = [[0, 0], [1, 0], [5, 5]];
    (document.getElementById('rp9-layout-undo') as HTMLButtonElement).click();
    expect(ctx.vertices[2]).toEqual([1, 1]);
    expect(redessins).toHaveBeenCalledTimes(1); // le toit et sa surface sont redessinés, comme Ctrl+Z
    (document.getElementById('rp9-layout-redo') as HTMLButtonElement).click();
    expect(ctx.vertices[2]).toEqual([5, 5]);
    expect(redessins).toHaveBeenCalledTimes(2);
    ctx.pushWorkshopHistory?.(); // un obstacle posé : même chemin
    (ctx as unknown as { obstacles: unknown[] }).obstacles = [{ id: 'o1' }];
    (document.getElementById('rp9-layout-undo') as HTMLButtonElement).click();
    expect(ctx.obstacles).toEqual([]);
    expect(redessins).toHaveBeenCalledTimes(3);
  });

  // ACAL2031 — figé SANS `opts.chiffrage` (site public, aperçu interne `/preview/toiture-3d-pro-11`, retiré du build par
  // ACAL332) : l'Annuler de la barre, hors disposition, n'est pas réservé à l'ERP.
  it('sans chiffrage, Annuler hors disposition passe par annulerGeste puis par undo', () => {
    document.body.innerHTML = '';
    const { ctx } = monter();
    expect((ctx as unknown as { opts?: { chiffrage?: unknown } }).opts?.chiffrage).toBeUndefined();
    const geste = { annuler: vi.fn(() => true), retablir: vi.fn(() => true) };
    ctx.annulerGeste = geste; // posé par creerAnnulerAtelier (roof-tool-pro11, ERP comme site public)
    ctx.pushWorkshopHistory?.();
    (ctx as unknown as { vertices: [number, number][] }).vertices = [[0, 0], [1, 0], [5, 5]];
    (document.getElementById('rp9-layout-undo') as HTMLButtonElement).click();
    expect(geste.annuler).toHaveBeenCalledTimes(1); // le geste unique, pas l'undo de l'éditeur
    expect(ctx.vertices[2]).toEqual([5, 5]);
    // Sans annulerGeste posé : le repli est l'undo de l'éditeur, comme avant ACAL1901.
    document.body.innerHTML = '';
    const sans = makeFreeCtx(makePlan(40), []);
    Object.assign(sans, { layoutMode: false, vertices: [[0, 0], [1, 0], [1, 1]] });
    createLayoutEditor(sans, makeDeps(makeMap().map));
    sans.pushWorkshopHistory?.();
    (sans as unknown as { vertices: [number, number][] }).vertices = [[0, 0], [1, 0], [5, 5]];
    (document.getElementById('rp9-layout-undo') as HTMLButtonElement).click();
    expect(sans.vertices[2]).toEqual([1, 1]);
    (document.getElementById('rp9-layout-redo') as HTMLButtonElement).click();
    expect(sans.vertices[2]).toEqual([5, 5]);
  });
});

// ACAL1403 — les boutons Annuler / Rétablir de la barre suivent la pile dès qu'un geste est photographié.
describe('ACAL1403 — Annuler / Rétablir actifs dès qu’un geste est à défaire', () => {
  it('un pushWorkshopHistory active Annuler ; undo active Rétablir et grise Annuler ; redo l’inverse', () => {
    document.body.innerHTML = ''; // les autres cas laissent leur échafaudage : ids uniques
    const { editor, ctx } = buildFreeEditor(40, []);
    const annuler =document.getElementById('rp9-layout-undo') as HTMLButtonElement;
    const retablir = document.getElementById('rp9-layout-redo') as HTMLButtonElement;
    expect(annuler.disabled).toBe(true);
    expect(retablir.disabled).toBe(true);
    ctx.pushWorkshopHistory?.();
    expect(annuler.disabled).toBe(false);
    expect(retablir.disabled).toBe(true);
    expect(editor.undo()).toBe(true);
    expect(annuler.disabled).toBe(true);
    expect(retablir.disabled).toBe(false);
    expect(editor.redo()).toBe(true);
    expect(annuler.disabled).toBe(false);
    expect(retablir.disabled).toBe(true);
  });
});

// ACAL418 — « Retirer la sélection » : le geste caché Alt + clic reçoit un bouton visible.
describe('ACAL418 — barre de sélection : Retirer la sélection', () => {
  function monterRetrait(mode: 'free' | 'lattice', n: number) {
    const { map } = makeMap();
    const centres = Array.from({ length: n }, (_, i) => ({ cx: -4 * i, cy: 0 }));
    const ctx = makeFreeCtx(makePlan(40), mode === 'free' ? centres : []);
    ctx.layoutState = createLayoutState(centres, n); // le pavage existe aussi avant le placement libre
    if (mode === 'lattice') {
      ctx.freeMode = false;
      ctx.layoutState = createLayoutState(centres, n);
    }
    let barre: { rafraichir: () => void } | undefined;
    const editor = createLayoutEditor(ctx, { ...makeDeps(map), onSelectionChange: () => barre?.rafraichir() });
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    const statuts: string[] = [];
    barre = creerBarreSelection({
      hote: () => hote, editeur: editor, setStatus: (m) => void statuts.push(m),
      photographier: () => ctx.pushWorkshopHistory?.(),
    });
    const clic = (txt: string) =>
      [...hote.querySelectorAll('button')].find((b) => b.textContent === txt)!.click();
    const nombre = () => (mode === 'free' ? editor.freePanels().length : ctx.layoutState!.occupied.size);
    return { editor, hote, statuts, clic, nombre };
  }

  it('placement libre : 3 panneaux se retirent en UN pas, Ctrl + Z les rend', () => {
    const { editor, statuts, clic, nombre } = monterRetrait('free', 5);
    editor.setSelection([0, 2, 4]);
    clic('Retirer la sélection');
    expect(nombre()).toBe(2);
    expect(statuts.at(-1)).toContain('3 panneau(x) retiré(s)');
    expect(editor.undo()).toBe(true);
    expect(nombre()).toBe(5);
  });

  it('emplacements validés : retrait annulable ; le pan entier est refusé', () => {
    const { editor, hote, statuts, clic, nombre } = monterRetrait('lattice', 4);
    editor.setSelection([0, 1, 2]);
    const barre = hote.firstElementChild as HTMLElement; // (ids dupliqués entre tests : pas de `#id`)
    expect(barre.style.display).toBe('flex');
    const aligner = [...hote.querySelectorAll('button')].find((b) => b.textContent === 'Aligner en rangée')!;
    expect(aligner.style.display).toBe('none'); // geste libre : masqué ici
    clic('Retirer la sélection');
    expect(nombre()).toBe(1);
    expect(editor.undo()).toBe(true);
    expect(nombre()).toBe(4);
    editor.setSelection([0, 1, 2, 3]);
    clic('Retirer la sélection');
    expect(nombre()).toBe(4);
    expect(statuts.at(-1)).toContain('gardez au moins un panneau');
  });

  it('placement libre : tout retirer est refusé aussi, sans rien toucher', () => {
    const { editor, statuts, clic, nombre } = monterRetrait('free', 2);
    editor.setSelection([0, 1]);
    clic('Retirer la sélection');
    expect(nombre()).toBe(2);
    expect(statuts.at(-1)).toContain('gardez au moins un panneau');
  });

  it('mutant : sans photo d’historique, Ctrl + Z ne rend rien (le test le sait)', () => {
    const { map } = makeMap();
    const ctx = makeFreeCtx(makePlan(40), [{ cx: 0, cy: 0 }, { cx: -4, cy: 0 }, { cx: -8, cy: 0 }]);
    ctx.layoutState = createLayoutState([{ cx: 0, cy: 0 }, { cx: -4, cy: 0 }, { cx: -8, cy: 0 }], 3);
    const editor = createLayoutEditor(ctx, makeDeps(map));
    const hote = document.createElement('div');
    document.body.appendChild(hote);
    creerBarreSelection({ hote: () => hote, editeur: editor, setStatus: () => {} }); // pas de `photographier`
    editor.setSelection([0]);
    [...hote.querySelectorAll('button')].find((b) => b.textContent === 'Retirer la sélection')!.click();
    expect(editor.freePanels()).toHaveLength(2);
    expect(editor.undo()).toBe(false);
    expect(editor.freePanels()).toHaveLength(2);
  });
});


// ═══════════════════════════════════════════════════════════════════════════════
// ACAL551 — silhouette du panneau glissé : rouge (dur), ambre (marge réglable), rien (valide).
// ═══════════════════════════════════════════════════════════════════════════════
describe('ACAL551 — silhouette du glissé', () => {
  const verdict = (violations: FreeCheck['violations'], hard: boolean): FreeCheck =>
    ({ ok: violations.length === 0, violations, hard, edgeM: 0.2, panelM: null });
  const g = { u: [1, 0], s: [0, 1], widthM: 2, depthM: 1 } as unknown as FreeGeom;

  it('natureSilhouette : obstacle ⇒ dur, retrait ou écart seul ⇒ relâchable, valide ⇒ rien', () => {
    expect(natureSilhouette(verdict(['obstacle'], true))).toBe('dur');
    expect(natureSilhouette(verdict(['overlap'], true))).toBe('dur');
    expect(natureSilhouette(verdict(['setback'], false))).toBe('relachable');
    expect(natureSilhouette(verdict(['gap'], false))).toBe('relachable');
    expect(natureSilhouette(verdict([], false))).toBeNull();
    expect(natureSilhouette(null)).toBeNull();
  });

  it('silhouetteGeoJSON rend un anneau de 4 coins (fermé) par membre du lot', () => {
    const coins: [number, number][][] = [
      [[0, 0], [2, 0], [2, 1], [0, 1]],
      [[3, 0], [5, 0], [5, 1], [3, 1]],
    ];
    const f = silhouetteGeoJSON(coins, [-7.6, 33.5], 'dur');
    expect(f).toHaveLength(2);
    for (const e of f) {
      expect(e.properties.nature).toBe('dur');
      const anneau = e.geometry.coordinates[0];
      expect(anneau).toHaveLength(5);
      expect(anneau[0]).toEqual(anneau[4]);
      expect(new Set(anneau.slice(0, 4).map((p) => p.join())).size).toBe(4);
    }
  });

  it('silhouetteDuLot : position valide ⇒ null ; refusée ⇒ une silhouette par membre, à la position visée', () => {
    const membres = [{ index: 0, cx: 0, cy: 0 }, { index: 1, cx: 3, cy: 0 }];
    const panels = [{ cx: 0, cy: 0 }, { cx: 3, cy: 0 }];
    expect(silhouetteDuLot(g, panels, membres, 1, 1, verdict([], false), [-7.6, 33.5])).toBeNull();
    const f = silhouetteDuLot(g, panels, membres, 1, 1, verdict(['obstacle'], true), [-7.6, 33.5])!;
    expect(f).toHaveLength(2);
    // le premier membre visé à (1, 1) : centre est/nord décalé d'un mètre de l'origine
    const lngs = f[0].geometry.coordinates[0].map((p) => p[0]);
    const lats = f[0].geometry.coordinates[0].map((p) => p[1]);
    expect(Math.min(...lngs)).toBeGreaterThanOrEqual(-7.6 - 1e-12);
    expect(Math.max(...lngs)).toBeGreaterThan(-7.6 + 1.5 / (111320 * Math.cos(33.5 * Math.PI / 180)));
    expect(Math.min(...lats)).toBeGreaterThan(33.5 + 0.4 / 111320);
  });

  it('peindreSilhouette crée la source et la couche à la demande, efface sur null, ignore une carte inerte', () => {
    const sources = new Map<string, { setData: (d: unknown) => void; data: unknown }>();
    const couches: unknown[] = [];
    const carte = {
      getSource: (id: string) => sources.get(id),
      addSource: (id: string, spec: { data: unknown }) => sources.set(id, { data: spec.data, setData(d) { this.data = d; } }),
      addLayer: (spec: unknown) => couches.push(spec),
    };
    const f = silhouetteGeoJSON([[[0, 0], [2, 0], [2, 1], [0, 1]]], [-7.6, 33.5], 'relachable');
    peindreSilhouette(carte, f);
    expect(couches).toHaveLength(1);
    expect((sources.get('rp9-glisse-silhouette')!.data as { features: unknown[] }).features).toHaveLength(1);
    peindreSilhouette(carte, null);
    expect((sources.get('rp9-glisse-silhouette')!.data as { features: unknown[] }).features).toHaveLength(0);
    expect(couches).toHaveLength(1); // pas de couche en double
    expect(() => peindreSilhouette({}, f)).not.toThrow();
    expect(() => peindreSilhouette(null, null)).not.toThrow();
  });

  it('texteDeMesure garde la cause en toutes lettres', () => {
    expect(texteDeMesure(verdict(['obstacle'], true))).toBe('Rive : 20 cm · Voisin : — — il tomberait sur un obstacle (ou son dégagement)');
  });
});

describe('ACAL553 — copier / coller la sélection libre', () => {
  it('3 panneaux copiés d’un pan se collent dans un autre, au même écartement relatif', () => {
    viderCollage();
    const src = buildFreeEditor(40, [0, 6, 12].map((u) => ({ cx: -u, cy: 0 })));
    src.editor.setSelection([0, 1, 2]);
    expect(src.editor.copierSelection()).toBe(true);
    const dest = buildFreeEditor(40, []);
    expect(dest.editor.collerSelection()).toBe(true);
    const posés = dest.editor.freePanels();
    expect(posés).toHaveLength(3);
    expect(posés[1].cx - posés[0].cx).toBeCloseTo(-6, 9);
    expect(posés[2].cx - posés[1].cx).toBeCloseTo(-6, 9);
    expect(dest.editor.selection()).toEqual([0, 1, 2]); // les collés restent sélectionnés
  });

  it('un collage dont un membre sort du pan : rien de collé, refus nommé', () => {
    viderCollage();
    const src = buildFreeEditor(40, [0, 6, 12].map((u) => ({ cx: -u, cy: 0 })));
    src.editor.setSelection([0, 1, 2]);
    src.editor.copierSelection();
    const petit = buildFreeEditor(5, []); // lot de 12 m de large : tient pas dans 10 m
    expect(petit.editor.collerSelection()).toBe(false);
    expect(petit.editor.freePanels()).toEqual([]);
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('Collage refusé');
    expect(document.getElementById('rp9-layout-note')?.textContent).toContain('rien n’a été collé');
  });

  it('Ctrl+C sans sélection libre : aucun effet ; rien en mémoire : Ctrl+V sans effet', () => {
    viderCollage();
    const { editor } = buildFreeEditor(40, [{ cx: 0, cy: 0 }]);
    editor.setSelection([]);
    expect(editor.copierSelection()).toBe(false);
    expect(editor.collerSelection()).toBe(false);
    expect(editor.freePanels()).toHaveLength(1);
  });
});

describe('ACAL1528 — Ctrl+V : un seul collage, une seule note vraie', () => {
  it("l'écran qui rappelle le geste sur la même frappe ne recolle pas : 2 → 4 panneaux, note « Collé », jamais « refusé »", () => {
    viderCollage();
    const { editor, ctx } = buildFreeEditor(40, [0, 6].map((u) => ({ cx: -u, cy: 0 })));
    ctx.layoutState = { cells: [], occupied: new Set<number>() } as unknown as Ctx['layoutState']; // la frappe n'est lue qu'avec une disposition
    editor.setSelection([0, 1]);
    expect(editor.copierSelection()).toBe(true);
    // Le gestionnaire de l'écran (fenêtre) appelle `raccourcis.coller` → `collerSelection` : un second chemin.
    const ecran = vi.fn(() => { editor.collerSelection(); });
    window.addEventListener('keydown', ecran);
    try {
      document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'v', ctrlKey: true, bubbles: true, cancelable: true }));
    } finally { window.removeEventListener('keydown', ecran); }
    expect(editor.freePanels()).toHaveLength(4);
    const note = document.getElementById('rp9-layout-note')?.textContent ?? '';
    expect(note).toContain('Collé — 2 panneaux');
    expect(note).not.toContain('refusé');
    expect(ecran).not.toHaveBeenCalled(); // la frappe traitée par l'atelier ne remonte pas à l'écran
  });
});

describe('ACAL1529 — le glissé et son relâchement disent la même chose', () => {
  /** Glisse le panneau (0, 0) vers `cibles` (ENU, mètres ; 10 pixels = 1 m dans cette carte factice), puis relâche. */
  function glisser(cibles: [number, number][], retraitM: number) {
    document.body.innerHTML = '';
    const container = document.createElement('div');
    document.body.appendChild(container);
    const peint: { nature?: string }[][] = [];
    const source = { setData: (d: { features: { properties: { nature: string } }[] }) => { peint.push(d.features.map((f) => f.properties)); } };
    const origine: [number, number] = [-7.6, 33.5];
    const cos = Math.cos(origine[1] * Math.PI / 180);
    const M = 111320;
    const map = {
      ...carteEditeurFactice(container),
      unproject: (p: { x: number; y: number }) => ({ lng: origine[0] + (p.x / 10) / (M * cos), lat: origine[1] + (p.y / 10) / M }), // 10 pixels = 1 m
      getSource: () => source, addSource: vi.fn(), addLayer: vi.fn(),
    } as unknown as ReturnType<typeof carteEditeurFactice>;
    const ctx = makeFreeCtx(makePlan(10), [{ cx: 0, cy: 0 }]) as unknown as Record<string, unknown>;
    Object.assign(ctx, { layoutState: { cells: [], occupied: new Set<number>() } });
    const editor = createLayoutEditor(ctx as unknown as Ctx, makeDeps(map));
    editor.setFreeMargins({ setbackM: retraitM, gapM: 0 });
    const appels = (map.on as unknown as { mock: { calls: [string, (e: unknown) => void][] } }).mock.calls;
    const sur = (ev: string, mx: number, my: number, x = mx * 10, y = my * 10) => appels.filter(([n]) => n === ev).forEach(([, f]) => f({ point: { x, y }, originalEvent: {}, preventDefault: () => undefined }));
    const note = () => document.getElementById('rp9-layout-note')?.textContent ?? '';
    sur('mousedown', 0, 0);
    const notes: string[] = [];
    for (const [x, y] of cibles) { sur('mousemove', x, y); notes.push(note()); }
    sur('mouseup', cibles[cibles.length - 1][0], cibles[cibles.length - 1][1]);
    return { notes, final: note(), peint, panneaux: editor.freePanels() };
  }
  it("marge réglable seule franchie : silhouette ambre, note du retrait, et le relâchement refuse comme la note l'a dit", () => {
    const r = glisser([[-4, 0], [-8.6, 0]], 1);
    expect(r.notes[1]).toBe('Ici : il passerait sous le retrait de rive que vous avez fixé.');
    expect(r.peint.some((f) => f.some((p) => p.nature === 'relachable'))).toBe(true); // silhouette ambre
    expect(r.final).toContain('Déplacement refusé');
    expect(r.final).toContain('retrait de rive');
    expect(r.final).not.toContain('Déplacé');
    expect(r.panneaux).toEqual([{ cx: 0, cy: 0 }]); // refusé : le panneau est revenu à son départ
  });
  it('un glissé qui finit sur une position valide : « Déplacé », panneau à la position visée', () => {
    const r = glisser([[-3, 0], [-4, 0]], 1);
    expect(r.final).toContain('Déplacé — 1 panneau');
    expect(r.panneaux[0].cx).toBeCloseTo(-4, 6);
  });
});

describe('ACAL510 — pan existant : ses modules ne se glissent pas', () => {
  function presser(existant: boolean) {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const map = { ...carteEditeurFactice(container), unproject: () => ({ lng: -7.6, lat: 33.5 }) } as unknown as ReturnType<typeof carteEditeurFactice>;
    const ctx = makeFreeCtx(makePlan(40), [{ cx: 0, cy: 0 }]) as unknown as Record<string, unknown>;
    Object.assign(ctx, { layoutState: { cells: [], occupied: new Set<number>() }, activeAreaId: 'z1', areas: [{ id: 'z1', label: 'Pan A', vertices: [], obstacles: [], ...(existant ? { existant: true } : {}) }] });
    createLayoutEditor(ctx as unknown as Ctx, makeDeps(map));
    const appels = (map.on as unknown as { mock: { calls: [string, (e: unknown) => void][] } }).mock.calls;
    const preventDefault = vi.fn();
    appels.find(([ev]) => ev === 'mousedown')![1]({ point: { x: 0, y: 0 }, originalEvent: {}, preventDefault });
    return { ctx, map, preventDefault };
  }
  it('un module d’un pan `existant` : refus nommant le pan, rien n’est saisi', () => {
    const { ctx, map } = presser(true);
    expect(ctx.layoutSel ?? null).toBeNull();
    expect(map.dragPan.disable).not.toHaveBeenCalled();
    const notes = [...document.querySelectorAll('#rp9-layout-note')].map((n) => n.textContent);
    expect(notes).toContain('Zone 1 : pan existant (déjà posé) — ses modules ne se modifient pas ; décochez « Pan existant » pour le modifier');
  });
  it('sans le drapeau : le module est saisi comme avant', () => {
    const { ctx, map } = presser(false);
    expect(ctx.layoutSel).toBe(0);
    expect(map.dragPan.disable).toHaveBeenCalled();
  });
});

// ACAL891 — « Remplir » au-delà de la limite mesurée : le refus nommé, rien n'est posé.
const limiteInjectee = vi.hoisted(() => ({ valeur: null as number | null }));
vi.mock('./limiteModules', async (orig) => ({ ...(await orig<typeof import('./limiteModules')>()), limiteModules: () => limiteInjectee.valeur }));

describe('ACAL891 — Remplir et la limite de modules', () => {
  const remplir = (limite: number | null) => {
    document.body.innerHTML = ''; // le gabarit de secours (ids uniques) est reposé pour CE cas
    limiteInjectee.valeur = limite;
    const { map } = makeMap();
    const panneaux = [{ cx: 0, cy: 0 }, { cx: -4, cy: 0 }, { cx: -8, cy: 0 }];
    const ctx = makeFreeCtx(makePlan(40), panneaux);
    (ctx as unknown as { freeMode: boolean }).freeMode = false;
    ctx.layoutState = createLayoutState(panneaux, 1); // 1 posé + 2 libres = 3 au total
    createLayoutEditor(ctx, makeDeps(map));
    (document.getElementById('rp9-layout-fill') as HTMLButtonElement).click();
    return { posés: occupiedCount(ctx.layoutState!), note: document.getElementById('rp9-layout-note')?.textContent ?? '' };
  };
  it('limite 2 < 3 modules visés ⇒ message et zéro pose', () => {
    const r = remplir(2);
    expect(r.note).toBe('Au-delà de 2 modules, l’atelier n’est plus fluide : réduisez le toit ou posez par parties.');
    expect(r.posés).toBe(1);
  });
  it('sous la limite, ou limite absente ⇒ inchangé (rempli)', () => {
    expect(remplir(5).posés).toBe(3);
    expect(remplir(null).posés).toBe(3);
  });
});

describe('ACAL1530 — « Personnaliser la disposition » reste présent quand le seuil écarte tout', () => {
  const monter = (cellules: number) => {
    document.body.innerHTML = '';
    const { map } = makeMap();
    const plan = makePlan(40);
    (plan.grid as unknown as { panels: unknown[] }).panels = Array.from({ length: cellules }, (_, i) => ({ cx: -4 * i, cy: 0 }));
    const editor = createLayoutEditor(makeFreeCtx(plan, []), makeDeps(map));
    editor.renderLayoutPanel();
    return { fenetre: document.getElementById('rp9-layout-window') as HTMLElement, bouton: document.getElementById('rp9-layout-toggle') as HTMLButtonElement };
  };
  it('le bloc reste présent quand un seuil écarte des emplacements : il dit pourquoi, le bouton ne se touche pas dans le vide', () => {
    const { fenetre, bouton } = monter(0);
    expect(fenetre.hidden).toBe(false);
    expect(document.getElementById('rp9-layout-indispo')?.textContent).toContain('seuil d’accès solaire');
    expect(bouton.disabled).toBe(true);
  });
  it('avec des emplacements : aucune phrase d’indisponibilité, bouton actif', () => {
    const { fenetre, bouton } = monter(3);
    expect(fenetre.hidden).toBe(false);
    expect(document.getElementById('rp9-layout-indispo')?.hidden ?? true).toBe(true);
    expect(bouton.disabled).toBe(false);
  });
});

describe('Demande croisée — l\'historique de l\'atelier rend le pan actif et les surfaces de pose', () => {
  it('Annuler après « pan de tracé remplacé par un champ au sol » rend le pan, le pan actif et l\'absence de surface', () => {
    const { map } = makeMap();
    const pan = (id: string) => ({ id, label: id, vertices: [], obstacles: [], roofType: 'flat', pitchDeg: 0, facingAzimuthDeg: 180, neededPanels: 0, neededAuto: true, result: null, renderPlan: null });
    const areas = [pan('area-1'), pan('area-2')];
    const ctx = makeFreeCtx(makePlan(40), []) as unknown as Record<string, unknown>;
    Object.assign(ctx, { areas, activeAreaId: 'area-2', surfacesPose: [{ id: 'sol-0', genre: 'sol' }] });
    const editor = createLayoutEditor(ctx as unknown as Ctx, makeDeps(map));
    (ctx.pushWorkshopHistory as () => void)(); // ce que fait deleteArea avant de retirer le pan
    areas.splice(1, 1);
    ctx.activeAreaId = 'area-1';
    (ctx.surfacesPose as unknown[]).push({ id: 'sol-1', genre: 'sol' });
    expect(editor.undo()).toBe(true);
    expect((ctx.areas as { id: string }[]).map((a) => a.id)).toEqual(['area-1', 'area-2']);
    expect(ctx.activeAreaId).toBe('area-2');
    expect((ctx.surfacesPose as { id: string }[]).map((x) => x.id)).toEqual(['sol-0']);
    expect(editor.redo()).toBe(true);
    expect((ctx.areas as { id: string }[]).map((a) => a.id)).toEqual(['area-1']);
    expect(ctx.activeAreaId).toBe('area-1');
    expect((ctx.surfacesPose as { id: string }[]).map((x) => x.id)).toEqual(['sol-0', 'sol-1']);
  });
});

// R2-09 / R2-05 — LE formateur de puissance (virgule, 2 décimales) et le libellé « Posés ÷ cible » (atelier ERP seulement).
describe('R2-09 / R2-05 — fenêtre de pose : kWc au format français, « Posés ÷ cible » en ERP seulement', () => {
  const rendre = (opts: Record<string, unknown>) => {
    document.body.innerHTML = '<div id="hote"><dd id="rp9-layout-cover">—</dd><dt id="dt-cover">Couverture besoin</dt></div>';
    const { map } = makeMap();
    const plan = makePlan(40);
    (plan.grid as unknown as { panels: unknown[] }).panels = [{ cx: 0, cy: 0 }];
    const ctx = makeFreeCtx(plan, [{ cx: 0, cy: 0 }, { cx: -4, cy: 0 }, { cx: -8, cy: 0 }]);
    (ctx as unknown as { opts: unknown }).opts = opts;
    (ctx as unknown as { neededPanels: number }).neededPanels = 6;
    const editor = createLayoutEditor(ctx, makeDeps(map));
    editor.renderLayoutPanel();
    return { kwc: document.getElementById('rp9-layout-kwc')?.textContent, cover: document.getElementById('rp9-layout-cover')?.textContent,
      dt: document.getElementById('dt-cover')?.textContent };
  };
  it('ERP : « Posés ÷ cible » et puissance « x,xx kWc » ; site public : « Couverture besoin » d’avant', () => {
    const erp = rendre({ chiffrage: null });
    expect(erp.dt).toBe('Posés ÷ cible');
    expect(erp.cover).toBe('50 %');
    expect(erp.kwc).toMatch(/^\d+,\d{2} kWc$/);
    const pub = rendre({});
    expect(pub.dt).toBe('Couverture besoin');
    expect(pub.kwc).toMatch(/^\d+,\d{2} kWc$/);
  });

  // T4-X8-012 (une cible) — « Posés ÷ cible » se divise par LA cible servie (le nombre à poser, 6, est un autre champ) ; sans cible servie : d'avant.
  it('T4-X8-012 (une cible) : « Posés ÷ cible » compte contre la cible servie dans le module posé ; sans cible servie, contre le nombre à poser ; public inchangé', () => {
    const servie = (n: number, watt = 720) => ({ chiffrage: null, hydrate: { devis: { origineCible: 'factures', libelleOrigineCible: 'Factures du lead', cible: { panneaux: n, panel_watt: watt } } } });
    expect(rendre(servie(4)).cover).toBe('75 %'); // 3 posés / 4 servis (le nombre à poser, 6, donnerait 50 %)
    expect(rendre({ chiffrage: null }).cover).toBe('50 %');
    expect(rendre(servie(4, 550)).cover).toBe('50 %'); // aucun compte servi pour ce module : le nombre à poser, comme avant
    expect(rendre({ hydrate: servie(4).hydrate }).cover).toBe('50 %'); // site public : jamais lu
  });

  // ACAL1520 — la puissance du bandeau suit le module DÉSIGNÉ du pan (comme la pastille), pas le 720 Wc par défaut.
  it('ACAL1520 — 5 panneaux de 710 Wc lisent « 3,55 kWc » ; sans module désigné : 3,60 (défaut 720 Wc)', () => {
    const module710 = { id: 'm710', libelle: 'Module 710', source: 'catalogue', longueurMm: 2384, largeurMm: 1303, pmaxWc: 710 };
    const rendreAvec = (moduleId: string | undefined) => {
      document.body.innerHTML = '';
      const { map } = makeMap();
      const plan = makePlan(40);
      (plan.grid as unknown as { panels: unknown[] }).panels = [{ cx: 0, cy: 0 }];
      const ctx = makeFreeCtx(plan, [0, 1, 2, 3, 4].map((i) => ({ cx: -4 * i, cy: 0 })));
      (ctx as unknown as { opts: unknown }).opts = { modulesDisponibles: { modules: [{ module: module710, selectionnable: true }] } };
      (ctx as unknown as { activeArea: () => unknown }).activeArea = () => ({ id: 'a1', ...(moduleId ? { moduleId } : {}) });
      createLayoutEditor(ctx, makeDeps(map)).renderLayoutPanel();
      return document.getElementById('rp9-layout-kwc')?.textContent;
    };
    expect(rendreAvec('m710')).toBe('3,55 kWc');
    expect(rendreAvec(undefined)).toBe('3,60 kWc');
  });
});

describe('ACAL1945 — à l’étape Toit en Guidé, la carte ne montre aucun panneau posé ; ils reviennent à l’étape Panneaux', () => {
  const monter = () => {
    document.body.innerHTML = '<div class="rp9-host cal-coque" data-etape="toit" data-expert="0"></div>';
    const { map } = makeMap();
    const ctx = makeFreeCtx(makePlan(40), [0, 1, 2, 3, 4].map((i) => ({ cx: -4 * i, cy: 0 })));
    const deps = makeDeps(map);
    const editor = createLayoutEditor(ctx, deps);
    const coque = document.querySelector('.cal-coque') as HTMLElement;
    const dernierRendu = () => {
      const appels = (deps.renderScene as unknown as { mock: { calls: unknown[][] } }).mock.calls;
      const a = appels[appels.length - 1];
      return { maxCount: a[4] as number, occupes: (a[6] as Set<number>).size };
    };
    return { editor, ctx, coque, dernierRendu };
  };
  it('drapeau posé par l’étape Toit (Guidé) : la scène est rendue SANS panneau, la pose n’est pas modifiée', () => {
    const { editor, ctx, coque, dernierRendu } = monter();
    coque.dataset.poseMasquee = '1';
    editor.renderCustomLayout();
    expect(dernierRendu()).toEqual({ maxCount: 0, occupes: 0 });
    expect((ctx.freeState as { panels: unknown[] }).panels).toHaveLength(5);
  });
  it('drapeau retiré (étape Panneaux) puis signal d’étape : les 5 panneaux reviennent sans geste de l’utilisateur', () => {
    const { editor, coque, dernierRendu } = monter();
    coque.dataset.poseMasquee = '1';
    editor.renderCustomLayout();
    delete coque.dataset.poseMasquee;
    document.dispatchEvent(new CustomEvent('cal:pose-etape'));
    expect(dernierRendu()).toEqual({ maxCount: 5, occupes: 5 });
  });
  it('sans drapeau (Expert, étape Panneaux, site public) : rendu d’avant, 5 panneaux', () => {
    const { editor, dernierRendu } = monter();
    editor.renderCustomLayout();
    expect(dernierRendu()).toEqual({ maxCount: 5, occupes: 5 });
  });
});

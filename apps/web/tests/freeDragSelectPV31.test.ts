// PV31 — GLISSÉ LIBRE + CADRE DE SÉLECTION (demande du fondateur, 21/08 : « je veux
// prendre un panneau et le poser où je veux ; encadrer une rangée et la déplacer »).
//
// Ce fichier verrouille la GÉOMÉTRIE PURE des deux gestes — la seule partie testable
// hors navigateur :
//   1. le cadre : quels panneaux un rectangle attrape (règle « centre dedans »), quel que
//      soit le coin d'où part le geste ;
//   2. la pose à positions ABSOLUES (`placeFreePanels`), primitive commune de l'aperçu
//      vivant et du déplacement rigide : TOUT OU RIEN, les membres libèrent leur position
//      de départ et se voient à l'arrivée ;
//   3. la non-régression de `moveFreePanels`, qui délègue désormais à cette primitive.
//
// Le glissé lui-même (pointerdown/move/up sur la carte, cadre peint en surcouche DOM,
// re-rendu 3D à chaque image) n'est PAS testable ici : il demande une vraie carte MapLibre
// et un contexte WebGL. Il relève de l'e2e.
import { describe, expect, it } from 'vitest';
import {
  geomAxes,
  freeStateFrom,
  moveFreePanels,
  placeFreePanels,
  normalizeRectENU,
  panelsInRectENU,
  type FreeGeom,
  type FreeLayoutState,
} from '../src/lib/freeLayout';

// Toit carré de 20 m de côté, azimut 180° (plein sud) — mêmes conventions que PV30.
// Panneau 2 m de large (axe u = est-ouest) × 1 m d'empreinte au sol (axe s).
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
const withPanels = (...p: { cx: number; cy: number }[]): FreeLayoutState => freeStateFrom(p);
/** Positions courantes, pour prouver qu'un refus n'a RIEN muté. */
const snap = (st: FreeLayoutState) => st.panels.map((p) => [p.cx, p.cy]);

// ═══════════════════ 1. LE CADRE DE SÉLECTION ═══════════════════

describe('PV31 §cadre — ce que le rectangle attrape', () => {
  it('normalise les deux coins quel que soit le sens du geste', () => {
    const fromTopRight = normalizeRectENU(5, 5, -5, -5);
    const fromBottomLeft = normalizeRectENU(-5, -5, 5, 5);
    expect(fromTopRight).toEqual({ xMin: -5, xMax: 5, yMin: -5, yMax: 5 });
    expect(fromTopRight).toEqual(fromBottomLeft);
  });

  it('attrape les panneaux dont le CENTRE tombe dans le cadre', () => {
    const panels = [
      { cx: -6, cy: 0 },
      { cx: -2, cy: 0 },
      { cx: 2, cy: 0 },
      { cx: 6, cy: 0 },
    ];
    // Un cadre grossier autour des deux du milieu.
    const hits = panelsInRectENU(panels, normalizeRectENU(-3.5, -1.5, 3.5, 1.5));
    expect(hits).toEqual([1, 2]);
  });

  it('un cadre tracé À L’ENVERS (bas-droite → haut-gauche) attrape exactement les mêmes', () => {
    const panels = [
      { cx: -6, cy: 0 },
      { cx: -2, cy: 0 },
      { cx: 2, cy: 0 },
      { cx: 6, cy: 0 },
    ];
    const straight = panelsInRectENU(panels, normalizeRectENU(-3.5, -1.5, 3.5, 1.5));
    const reversed = panelsInRectENU(panels, normalizeRectENU(3.5, 1.5, -3.5, -1.5));
    expect(reversed).toEqual(straight);
  });

  it('un panneau seulement EFFLEURÉ par le cadre (centre dehors) n’est pas pris', () => {
    // Panneau centré en 2 (il s'étend de 1 à 3) : le cadre s'arrête à 1,5 — il le touche,
    // mais son centre est dehors. La règle « centre dedans » est celle qu'attend l'opérateur.
    const hits = panelsInRectENU([{ cx: 2, cy: 0 }], normalizeRectENU(-3, -1, 1.5, 1));
    expect(hits).toEqual([]);
  });

  it('un cadre vide ne prend rien, sans planter', () => {
    expect(panelsInRectENU([], normalizeRectENU(0, 0, 5, 5))).toEqual([]);
    expect(panelsInRectENU([{ cx: 9, cy: 9 }], normalizeRectENU(-1, -1, 1, 1))).toEqual([]);
  });

  it('attrape TOUTE une rangée d’un seul cadre (le geste que le fondateur décrit)', () => {
    // Deux rangées de 3 panneaux ; on encadre largement la rangée du haut seulement.
    const panels = [
      { cx: -4, cy: 3 },
      { cx: 0, cy: 3 },
      { cx: 4, cy: 3 },
      { cx: -4, cy: -3 },
      { cx: 0, cy: -3 },
      { cx: 4, cy: -3 },
    ];
    expect(panelsInRectENU(panels, normalizeRectENU(-9, 1, 9, 9))).toEqual([0, 1, 2]);
  });
});

// ═══════════════════ 2. LA POSE À POSITIONS ABSOLUES ═══════════════════

describe('PV31 §pose — `placeFreePanels`, primitive de l’aperçu vivant', () => {
  it('pose un panneau seul à la position visée et mute l’état', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const res = placeFreePanels(st, geom(), [{ index: 0, cx: 5, cy: 0 }], STUDY_MARGIN);
    expect(res.ok).toBe(true);
    expect(res.positions).toEqual([{ cx: 5, cy: 0 }]);
    expect(snap(st)).toEqual([[5, 0]]);
  });

  it('TOUT OU RIEN — un seul membre hors du toit annule le lot ENTIER', () => {
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 3, cy: 0 });
    const before = snap(st);
    // Le premier membre atterrirait bien (8 → 7..9) ; le second déborde (11 → 10..12).
    const res = placeFreePanels(
      st,
      geom(),
      [
        { index: 0, cx: 8, cy: 0 },
        { index: 1, cx: 11, cy: 0 },
      ],
      NO_MARGIN,
    );
    expect(res.ok).toBe(false);
    expect(res.blockedIndex).toBe(1);
    expect(res.blocked?.violations).toContain('outline');
    // Le membre VALIDE ne doit pas non plus avoir bougé : le commit est atomique.
    expect(snap(st)).toEqual(before);
  });

  it('les membres LIBÈRENT leur position de départ (une rangée peut glisser sur elle-même)', () => {
    // Deux panneaux jointifs (-1..1 et 1..3). On translate le lot de +2 : la cible du
    // premier tombe exactement sur la position de DÉPART du second — ce qui doit passer,
    // puisque le second s'en va aussi.
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 2, cy: 0 });
    const res = placeFreePanels(
      st,
      geom(),
      [
        { index: 0, cx: 2, cy: 0 },
        { index: 1, cx: 4, cy: 0 },
      ],
      NO_MARGIN,
    );
    expect(res.ok).toBe(true);
    expect(snap(st)).toEqual([
      [2, 0],
      [4, 0],
    ]);
  });

  it('les membres SE VOIENT à l’arrivée (un lot ne se replie pas sur lui-même)', () => {
    const st = withPanels({ cx: -4, cy: 0 }, { cx: 4, cy: 0 });
    const before = snap(st);
    const res = placeFreePanels(
      st,
      geom(),
      [
        { index: 0, cx: 0, cy: 0 },
        { index: 1, cx: 0, cy: 0 }, // même point que le membre déjà posé → chevauchement
      ],
      NO_MARGIN,
    );
    expect(res.ok).toBe(false);
    expect(res.blocked?.violations).toContain('overlap');
    expect(snap(st)).toEqual(before);
  });

  it('un panneau NON membre bloque toujours (il n’est pas ignoré)', () => {
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 5, cy: 0 });
    const before = snap(st);
    const res = placeFreePanels(st, geom(), [{ index: 0, cx: 5, cy: 0 }], NO_MARGIN);
    expect(res.ok).toBe(false);
    expect(res.blockedIndex).toBe(0);
    expect(res.blocked?.violations).toContain('overlap');
    expect(snap(st)).toEqual(before);
  });

  it('ignore les index hors liste et les doublons, sans rien casser', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const res = placeFreePanels(
      st,
      geom(),
      [
        { index: 0, cx: 4, cy: 0 },
        { index: 0, cx: -4, cy: 0 }, // doublon : le PREMIER gagne
        { index: 99, cx: 0, cy: 0 }, // hors liste : ignoré
      ],
      STUDY_MARGIN,
    );
    expect(res.ok).toBe(true);
    expect(snap(st)).toEqual([[4, 0]]);
  });

  it('refuse une position non finie sans muter l’état', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    const res = placeFreePanels(st, geom(), [{ index: 0, cx: Number.NaN, cy: 0 }], NO_MARGIN);
    expect(res.ok).toBe(false);
    expect(snap(st)).toEqual([[0, 0]]);
  });

  it('un lot vide est refusé proprement', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    expect(placeFreePanels(st, geom(), [], NO_MARGIN).ok).toBe(false);
    expect(snap(st)).toEqual([[0, 0]]);
  });
});

// ═══════════════════ 3. NON-RÉGRESSION DE LA TRANSLATION RIGIDE ═══════════════════

describe('PV31 §rigide — `moveFreePanels` délègue sans changer de comportement', () => {
  it('translate le groupe RIGIDEMENT (les écarts internes sont préservés)', () => {
    const st = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 0 }, { cx: 4, cy: 0 });
    const res = moveFreePanels(st, geom(), [0, 1, 2], 0, 2, STUDY_MARGIN);
    expect(res.ok).toBe(true);
    expect(snap(st)).toEqual([
      [-4, 2],
      [0, 2],
      [4, 2],
    ]);
  });

  it('reste TOUT OU RIEN quand un membre sortirait du toit', () => {
    const st = withPanels({ cx: 0, cy: 0 }, { cx: 8, cy: 0 });
    const before = snap(st);
    const res = moveFreePanels(st, geom(), [0, 1], 3, 0, NO_MARGIN); // 8 → 11 : dehors
    expect(res.ok).toBe(false);
    expect(snap(st)).toEqual(before);
  });

  it('donne EXACTEMENT le même résultat que la pose absolue équivalente', () => {
    const viaMove = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 0 });
    const viaPlace = withPanels({ cx: -4, cy: 0 }, { cx: 0, cy: 0 });
    moveFreePanels(viaMove, geom(), [0, 1], 1.5, -2, STUDY_MARGIN);
    placeFreePanels(
      viaPlace,
      geom(),
      [
        { index: 0, cx: -2.5, cy: -2 },
        { index: 1, cx: 1.5, cy: -2 },
      ],
      STUDY_MARGIN,
    );
    expect(snap(viaMove)).toEqual(snap(viaPlace));
  });

  it('un déplacement non fini est refusé (garde historique de PV30)', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    expect(moveFreePanels(st, geom(), [0], Number.NaN, 0, NO_MARGIN).ok).toBe(false);
    expect(snap(st)).toEqual([[0, 0]]);
  });

  it('une liste de membres vide est refusée', () => {
    const st = withPanels({ cx: 0, cy: 0 });
    expect(moveFreePanels(st, geom(), [], 1, 0, NO_MARGIN).ok).toBe(false);
  });
});

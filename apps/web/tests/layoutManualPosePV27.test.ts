// PV27 — LA POSE MANUELLE NE DOIT PLUS DISPARAÎTRE. Trois chemins prouvés :
//  1. l'export prenait « les `count` premiers panneaux du pavage » (slice) au lieu des
//     cellules RÉELLEMENT occupées → une pose non contiguë était réécrite en pose contiguë ;
//  2. personne ne REPOSAIT les panneaux exportés au ré-import (l'optimum s'affichait) ;
//  3. entrer en mode « Personnaliser » remettait la disposition à l'optimum.
// Ce test couvre 1 (export fidèle + round-trip sur un motif NON contigu) ; le câblage 2 et
// 3 est couvert par layoutEditorHydratePV27 (jsdom).
import { describe, expect, it } from 'vitest';
import { serializeLayout } from '../src/scripts/roofPro11/prefill';
import { createLayoutState, nearestEmptyCell, occupiedIndices } from '../src/lib/layoutVariability';
import { PANEL2_WATT } from '../src/lib/estimatorBrainV2';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];
/** Pavage de 60 cellules (10 colonnes × 6 rangées, pas de 1 m) — assez pour un nº47. */
const CELLS = Array.from({ length: 60 }, (_, i) => ({ cx: i % 10, cy: Math.floor(i / 10) }));

function zone(): AreaRecord {
  return {
    id: 'area-1',
    label: 'Zone 1',
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 48,
    neededAuto: false,
    result: null,
    renderPlan: null,
  };
}

/** ctx minimal avec un plan gagnant VIVANT + une disposition personnalisée. */
function makeCtx(occupied: number[], optimalCount = 48): Ctx {
  const state = createLayoutState(CELLS, 0);
  for (const i of occupied) state.occupied.add(i);
  return {
    areas: [zone()],
    activeAreaId: 'area-1',
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 48,
    neededAuto: false,
    layoutPlan: {
      pack: { origin: [-7.6, 33.59], azimuthDeg: 180 },
      grid: { panels: CELLS, kwc: (CELLS.length * PANEL2_WATT) / 1000, count: CELLS.length },
      tiltDeg: 13,
      family: 'south',
      flush: false,
    },
    layoutOptimalCount: optimalCount,
    layoutState: state,
  } as unknown as Ctx;
}

/** Pose NON contiguë : les 48 premiers emplacements, MOINS le nº12, PLUS le nº47… et le 55. */
const MANUAL_POSE = [...Array.from({ length: 48 }, (_, i) => i).filter((i) => i !== 12), 55];

describe('PV27 — l’export porte les cellules RÉELLEMENT occupées', () => {
  it('un motif non contigu (nº12 retiré, nº47 gardé) est exporté TEL QUEL', () => {
    const layout = serializeLayout(makeCtx(MANUAL_POSE), 9000);
    const geo = layout.zones[0].geometry!;
    expect(geo.count).toBe(MANUAL_POSE.length); // 48 panneaux posés
    // Le trou est bien un trou : aucun panneau au centre de la cellule nº12.
    const has = (i: number) => geo.panels.some((p) => p.cx === CELLS[i].cx && p.cy === CELLS[i].cy);
    expect(has(12)).toBe(false);
    expect(has(47)).toBe(true);
    expect(has(55)).toBe(true); // au-delà du « count » : l'ancien slice l'aurait perdu
    // kWc suit le nombre RÉELLEMENT posé.
    expect(geo.kwc).toBeCloseTo((MANUAL_POSE.length * PANEL2_WATT) / 1000, 9);
  });

  it('ROUND-TRIP : reposer les panneaux exportés redonne EXACTEMENT la même pose', () => {
    const layout = serializeLayout(makeCtx(MANUAL_POSE), 9000);
    const geo = layout.zones[0].geometry!;
    // Re-hydratation : lattice fraîche + re-snap de chaque centre exporté (le mécanisme
    // de `hydrateLayout` / `reenterCustomLayout`).
    const fresh = createLayoutState(CELLS, 0);
    for (const p of geo.panels) {
      const idx = nearestEmptyCell(fresh, p.cx, p.cy);
      expect(idx).toBeGreaterThanOrEqual(0);
      fresh.occupied.add(idx);
    }
    expect(occupiedIndices(fresh)).toEqual([...MANUAL_POSE].sort((a, b) => a - b));
  });

  it('sans disposition personnalisée, l’export reste le comportement historique', () => {
    const ctx = makeCtx([], 10);
    (ctx as unknown as { layoutState: null }).layoutState = null;
    const geo = serializeLayout(ctx, 9000).zones[0].geometry!;
    expect(geo.count).toBe(10);
    expect(geo.panels.map((p) => `${p.cx}/${p.cy}`)).toEqual(CELLS.slice(0, 10).map((c) => `${c.cx}/${c.cy}`));
  });

  it('une disposition VIDE (tous les panneaux retirés) s’exporte comme telle', () => {
    const geo = serializeLayout(makeCtx([]), 9000).zones[0].geometry!;
    expect(geo.count).toBe(0);
    expect(geo.panels).toEqual([]);
    expect(geo.kwc).toBe(0);
  });
});

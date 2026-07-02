// WJ24 — export fidelity : serializeLayout est ÉLARGI de façon ADDITIVE pour porter la
// géométrie PLEINE par pan (azimut/tilt/family + centres de chaque panneau posé), afin que
// le devis/PDF ERP reflète le VRAI design multi-plan. On vérifie que TOUS les champs
// antérieurs sont toujours émis (le backend les consomme) ET que la nouvelle géométrie
// apparaît quand un plan de rendu existe, sans casser le round-trip d'identité.
import { describe, expect, it } from 'vitest';
import { serializeLayout, deserializeLayout } from '../src/scripts/roofPro11/prefill';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord, type ZoneRenderPlan } from '../src/scripts/roofPro11/types';
import { packConfig, type PackResult, type PanelGrid } from '../src/lib/estimatorBrainV2';

function renderPlanFor(): ZoneRenderPlan {
  const ring = [
    [-7.6, 33.59],
    [-7.5988, 33.59],
    [-7.5988, 33.5906],
    [-7.6, 33.5906],
  ] as [number, number][];
  const pack: PackResult = packConfig(ring, 33.59, { family: 'south', tiltDeg: 15 });
  const grid: PanelGrid = pack.best;
  return { pack, grid, tiltDeg: 15, family: 'south', flush: false, count: Math.min(4, grid.panels.length), obstacles: [] };
}

function zone(id: string, rp: ZoneRenderPlan | null): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: [
      [-7.6, 33.59],
      [-7.5988, 33.59],
      [-7.5988, 33.5906],
      [-7.6, 33.5906],
    ],
    obstacles: [{ id: `obs-${id}`, centerLng: -7.5994, centerLat: 33.5903, lengthM: 2, widthM: 1.5 }],
    roofType: 'flat',
    pitchDeg: 15,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 10,
    neededAuto: true,
    result: null,
    renderPlan: rp,
  };
}

function makeCtx(areas: AreaRecord[], activeId: string): Ctx {
  const active = areas.find((a) => a.id === activeId)!;
  return {
    areas,
    activeAreaId: activeId,
    vertices: active.vertices,
    obstacles: active.obstacles,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: active.facingManual ?? false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
  } as unknown as Ctx;
}

describe('WJ24 — serializeLayout élargi (géométrie par pan, additif)', () => {
  it('émet TOUJOURS tous les champs antérieurs (backward-compat backend)', () => {
    const ctx = makeCtx([zone('area-1', renderPlanFor())], 'area-1');
    const layout = serializeLayout(ctx, 8000);
    const z = layout.zones[0];
    // champs historiques présents et inchangés
    for (const k of ['id', 'label', 'vertices', 'obstacles', 'roofType', 'pitchDeg', 'facingAzimuthDeg', 'facingManual', 'neededPanels', 'neededAuto']) {
      expect(z).toHaveProperty(k);
    }
    expect(z.neededPanels).toBe(10);
    expect(layout.version).toBe(1);
    expect(layout.billKwh).toBe(8000);
  });

  it('ajoute la géométrie pleine par pan quand un plan de rendu existe', () => {
    const rp = renderPlanFor();
    const ctx = makeCtx([zone('area-1', rp)], 'area-1');
    const z = serializeLayout(ctx).zones[0];
    expect(z.geometry).toBeTruthy();
    expect(z.geometry!.azimuthDeg).toBe(rp.pack.azimuthDeg);
    expect(z.geometry!.tiltDeg).toBe(15);
    expect(z.geometry!.family).toBe('south');
    expect(z.geometry!.count).toBe(rp.count);
    // un centre par panneau posé, dans le repère `origin`
    expect(z.geometry!.panels.length).toBe(rp.count);
    expect(z.geometry!.origin).toEqual([rp.pack.origin[0], rp.pack.origin[1]]);
    for (const p of z.geometry!.panels) {
      expect(typeof p.cx).toBe('number');
      expect(typeof p.cy).toBe('number');
    }
    // kWc posé cohérent (proportionnel au nombre posé)
    expect(z.geometry!.kwc).toBeGreaterThan(0);
  });

  it('pas de géométrie si la zone n’a pas de plan de rendu (rétro-compatible)', () => {
    const ctx = makeCtx([zone('area-1', null)], 'area-1');
    const z = serializeLayout(ctx).zones[0];
    expect(z.geometry).toBeUndefined();
  });

  it('reste JSON pur et le round-trip d’identité tient (géométrie ignorée à l’hydratation)', () => {
    const ctx = makeCtx([zone('area-1', renderPlanFor())], 'area-1');
    const layout = serializeLayout(ctx, 8000);
    const flat = JSON.stringify(layout);
    expect(flat).not.toContain('renderPlan');
    expect(flat).not.toContain('"result"');
    const back = deserializeLayout(layout);
    expect(back.length).toBe(1);
    expect(back[0].vertices).toEqual(ctx.areas[0].vertices);
    expect(back[0].neededPanels).toBe(10);
    expect(back[0].renderPlan).toBeNull(); // dérivé, recalculé au boot
  });
});

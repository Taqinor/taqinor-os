// W113 — sérialisation / hydratation du layout (linchpin). Fonctions PURES :
// serializeLayout(ctx) → JSON ; deserializeLayout(json) → AreaRecord[] ; round-trip
// = identité sur la géométrie + le dimensionnement multi-zones. hydrateFromLead(lead)
// convertit un payload lead [lat,lng] en contour/pin [lng,lat] + contact.
import { describe, expect, it } from 'vitest';
import {
  serializeLayout,
  deserializeLayout,
  hydrateFromLead,
} from '../src/scripts/roofPro11/prefill';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

/** Construit une zone d'exemple. */
function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: [
      [-7.6, 33.59],
      [-7.599, 33.59],
      [-7.599, 33.591],
      [-7.6, 33.591],
    ],
    obstacles: [{ id: `obs-${id}`, centerLng: -7.5995, centerLat: 33.5905, lengthM: 2, widthM: 1.5 }],
    roofType: 'flat',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...opts,
  };
}

/** Ctx minimal : multi-zones, la zone ACTIVE reflétée par l'état d'édition vivant. */
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
  } as unknown as Ctx;
}

describe('W113 — serializeLayout / deserializeLayout (round-trip identité)', () => {
  it('round-trip multi-zones préserve géométrie + dimensionnement', () => {
    const z1 = zone('area-1');
    const z2 = zone('area-2', {
      roofType: 'pitched',
      pitchDeg: 30,
      facingAzimuthDeg: 135,
      facingManual: true,
      neededPanels: 8,
      neededAuto: false,
      vertices: [
        [-7.7, 33.6],
        [-7.699, 33.6],
        [-7.699, 33.601],
      ],
    });
    const ctx = makeCtx([z1, z2], 'area-1');
    const layout = serializeLayout(ctx, 9000);

    expect(layout.version).toBe(1);
    expect(layout.billKwh).toBe(9000);
    expect(layout.zones.length).toBe(2);
    expect(layout.activeAreaId).toBe('area-1');

    // JSON pur : pas de result/renderPlan/THREE qui fuient.
    const flat = JSON.stringify(layout);
    expect(flat).not.toContain('renderPlan');
    expect(flat).not.toContain('"result"');

    const back = deserializeLayout(layout);
    expect(back.length).toBe(2);
    // Zone 1 (active) — géométrie et dimensionnement identiques.
    expect(back[0].id).toBe('area-1');
    expect(back[0].vertices).toEqual(z1.vertices);
    expect(back[0].obstacles).toEqual(z1.obstacles);
    expect(back[0].neededPanels).toBe(12);
    expect(back[0].neededAuto).toBe(true);
    // Zone 2 (figée) — pente/face/manual/needed conservés.
    expect(back[1].id).toBe('area-2');
    expect(back[1].roofType).toBe('pitched');
    expect(back[1].pitchDeg).toBe(30);
    expect(back[1].facingAzimuthDeg).toBe(135);
    expect(back[1].facingManual).toBe(true);
    expect(back[1].neededPanels).toBe(8);
    expect(back[1].neededAuto).toBe(false);
    expect(back[1].vertices).toEqual(z2.vertices);
    // les champs dérivés repartent à null (recalculés au boot).
    expect(back[0].result).toBeNull();
    expect(back[0].renderPlan).toBeNull();
  });

  it('le pin = centroïde de la zone active + outline en [lat,lng]', () => {
    const ctx = makeCtx([zone('area-1')], 'area-1');
    const layout = serializeLayout(ctx);
    expect(layout.pin).not.toBeNull();
    // centroïde du carré ≈ (-7.5995, 33.5905)
    expect(layout.pin!.lng).toBeCloseTo(-7.5995, 4);
    expect(layout.pin!.lat).toBeCloseTo(33.5905, 4);
    // outline en [lat,lng] (convention CRM), 4 sommets.
    expect(layout.outline.length).toBe(4);
    expect(layout.outline[0]).toEqual([33.59, -7.6]);
  });

  it('deserializeLayout tolère un JSON vide/malformé', () => {
    expect(deserializeLayout({ zones: [] } as never)).toEqual([]);
    expect(deserializeLayout({} as never)).toEqual([]);
  });
});

describe('W113 — hydrateFromLead', () => {
  it('convertit roof_outline [lat,lng] → vertices [lng,lat] + contact', () => {
    const h = hydrateFromLead({
      roof_outline: [
        [33.59, -7.6],
        [33.591, -7.6],
        [33.591, -7.599],
      ],
      roof_point: { lat: 33.5905, lng: -7.5997 },
      fullName: 'Reda K.',
      phone: '0612345678',
      city: 'Casablanca',
    });
    expect(h.vertices.length).toBe(3);
    expect(h.vertices[0]).toEqual([-7.6, 33.59]); // [lng,lat]
    expect(h.center).toEqual([-7.5997, 33.5905]); // roof_point prioritaire
    expect(h.contact).toEqual({ name: 'Reda K.', phone: '0612345678', city: 'Casablanca' });
  });

  it('un pin seul (sans contour) donne un center mais aucun vertex', () => {
    const h = hydrateFromLead({ roof_point: { lat: 33.5, lng: -7.6 } });
    expect(h.vertices).toEqual([]);
    expect(h.center).toEqual([-7.6, 33.5]);
  });

  it('un contour seul (sans roof_point) centre sur le centroïde', () => {
    const h = hydrateFromLead({
      roof_outline: [
        [33.0, -7.0],
        [33.0, -7.2],
        [33.2, -7.1],
      ],
    });
    expect(h.center).not.toBeNull();
    expect(h.center![0]).toBeCloseTo(-7.1, 5);
  });

  it('un lead vide/null ne sème rien (pas de crash)', () => {
    expect(hydrateFromLead(null)).toEqual({ vertices: [], center: null, contact: {} });
    expect(hydrateFromLead({})).toEqual({ vertices: [], center: null, contact: {} });
  });
});

// PV19 — HYDRATATION DEPUIS UN DEVIS. Un devis porte son design (layout sérialisé) et sa
// CIBLE vendue : c'est le nombre de panneaux du devis qui pilote l'optimiseur, pas la
// facture. Fonction PURE, jumelle de hydrateFromLead — dont le comportement doit rester
// strictement inchangé (golden ci-dessous).
import { describe, expect, it } from 'vitest';
import { hydrateFromDevis, hydrateFromLead, serializeLayout } from '../src/scripts/roofPro11/prefill';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
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

/** Un layout sérialisé RÉEL (celui que l'outil produit), pour hydrater un devis. */
function layoutOf(areas: AreaRecord[], activeId = areas[0].id) {
  const active = areas.find((a) => a.id === activeId)!;
  const ctx = {
    areas,
    activeAreaId: activeId,
    vertices: active.vertices,
    obstacles: active.obstacles,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
  } as unknown as Ctx;
  return serializeLayout(ctx, 9000);
}

describe('PV19 — hydratation depuis le DESIGN du devis', () => {
  const layout = layoutOf([zone('area-1'), zone('area-2', { neededPanels: 8, neededAuto: false })], 'area-2');
  const devis = {
    id: 'DV-2026-014',
    geometrie: { roof_layout: layout },
    cible: { panneaux: 26, panel_watt: 615, scenario: 'avec_batterie' as const },
    fullName: 'Reda K.',
    phone: '0612345678',
    city: 'Casablanca',
  };

  it('reconstruit LES ZONES du devis et retient la zone active du layout', () => {
    const h = hydrateFromDevis(devis);
    expect(h.zones).not.toBeNull();
    expect(h.zones!.length).toBe(2);
    expect(h.zones!.map((z) => z.id)).toEqual(['area-1', 'area-2']);
    expect(h.activeAreaId).toBe('area-2');
    expect(h.vertices).toEqual(VERTS.map(([lng, lat]) => [lng, lat]));
    expect(h.center).not.toBeNull();
    // Les champs dérivés repartent à null (l'optimiseur les recalcule au boot).
    expect(h.zones![0].result).toBeNull();
    expect(h.zones![0].renderPlan).toBeNull();
  });

  it('la CIBLE vendue impose le besoin (la facture ne décide plus)', () => {
    const h = hydrateFromDevis(devis);
    expect(h.neededPanels).toBe(26);
    expect(h.neededAuto).toBe(false);
    expect(h.panelWatt).toBe(615);
    expect(h.scenario).toBe('avec_batterie');
    expect(h.devisId).toBe('DV-2026-014');
  });

  it('reporte les coordonnées client comme l’hydratation lead', () => {
    expect(hydrateFromDevis(devis).contact).toEqual({ name: 'Reda K.', phone: '0612345678', city: 'Casablanca' });
  });
});

describe('PV19 — devis SANS design : repli lead-like', () => {
  it('un contour seul sème les sommets et le centre', () => {
    const h = hydrateFromDevis({
      geometrie: {
        roof_outline: [
          [33.59, -7.6],
          [33.591, -7.6],
          [33.591, -7.599],
        ],
      },
      cible: { panneaux: 14 },
    });
    expect(h.zones).toBeNull();
    expect(h.vertices.length).toBe(3);
    expect(h.vertices[0]).toEqual([-7.6, 33.59]); // [lat,lng] → [lng,lat]
    expect(h.center).not.toBeNull();
    expect(h.neededPanels).toBe(14);
    expect(h.neededAuto).toBe(false);
  });

  it('un pin seul donne un centre sans sommet', () => {
    const h = hydrateFromDevis({ geometrie: { roof_point: { lat: 33.5, lng: -7.6 } } });
    expect(h.vertices).toEqual([]);
    expect(h.center).toEqual([-7.6, 33.5]);
  });
});

describe('PV19 — garde-fous', () => {
  it('sans cible exploitable, le besoin reste piloté par la facture', () => {
    for (const panneaux of [undefined, null, 0, -3, Number.NaN]) {
      const h = hydrateFromDevis({ cible: { panneaux: panneaux as number } });
      expect(h.neededPanels).toBeNull();
      expect(h.neededAuto).toBe(true);
    }
  });

  it('devis nul/vide → rien n’est semé (pas de crash)', () => {
    expect(hydrateFromDevis(null)).toEqual({
      vertices: [],
      center: null,
      contact: {},
      zones: null,
      activeAreaId: null,
      neededPanels: null,
      neededAuto: true,
      panelWatt: null,
      scenario: null,
      devisId: null,
    });
    const empty = hydrateFromDevis({});
    expect(empty.zones).toBeNull();
    expect(empty.vertices).toEqual([]);
    expect(empty.neededAuto).toBe(true);
  });

  it('un layout vide (0 zone) retombe sur le repli lead-like', () => {
    const h = hydrateFromDevis({
      geometrie: { roof_layout: { version: 2, pin: null, outline: [], billKwh: null, zones: [], activeAreaId: '' }, roof_point: { lat: 33.4, lng: -7.5 } },
    });
    expect(h.zones).toBeNull();
    expect(h.center).toEqual([-7.5, 33.4]);
  });
});

describe('PV19 — le boot LEAD reste strictement inchangé (golden)', () => {
  it('hydrateFromLead donne exactement le même résultat qu’avant', () => {
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
    expect(h.vertices[0]).toEqual([-7.6, 33.59]);
    expect(h.center).toEqual([-7.5997, 33.5905]);
    expect(h.contact).toEqual({ name: 'Reda K.', phone: '0612345678', city: 'Casablanca' });
    // Aucun champ devis ne s'invite dans l'hydratation lead.
    expect(Object.keys(h).sort()).toEqual(['center', 'contact', 'vertices']);
    expect(hydrateFromLead(null)).toEqual({ vertices: [], center: null, contact: {} });
  });
});

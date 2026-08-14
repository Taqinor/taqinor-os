// PV13 — SÉRIALISATION v2 du layout : le JSON porte désormais le résultat global, le
// scénario, la puissance panneau, la batterie et l'origine (devis/lead). Contrainte dure :
// TOUS les champs v1 restent identiques (un lecteur v1 ne casse pas) et
// `deserializeLayout` ignore purement et simplement les ajouts.
import { describe, expect, it } from 'vitest';
import { serializeLayout, deserializeLayout } from '../src/scripts/roofPro11/prefill';
import { PANEL2_WATT } from '../src/lib/estimatorBrainV2';
import { type Ctx } from '../src/scripts/roofPro11/context';
import { type AreaRecord } from '../src/scripts/roofPro11/types';

const VERTS = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
] as [number, number][];

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

/** Plan de rendu minimal : 5 cellules, 3 posées → géométrie exportée de 3 panneaux. */
function renderPlan(count: number, cells = 5) {
  const panels = Array.from({ length: cells }, (_, i) => ({ cx: i, cy: 0 }));
  return {
    pack: { origin: [-7.6, 33.59], azimuthDeg: 180 },
    grid: { panels, kwc: (cells * PANEL2_WATT) / 1000 },
    tiltDeg: 13,
    family: 'south',
    flush: false,
    count,
    obstacles: [],
  } as unknown as AreaRecord['renderPlan'];
}

function makeCtx(areas: AreaRecord[], activeId = areas[0].id): Ctx {
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

/** Les champs v1, extraits d'un layout (pour prouver qu'ils n'ont pas bougé). */
const v1Fields = (l: Record<string, unknown>) => ({
  pin: l.pin,
  outline: l.outline,
  billKwh: l.billKwh,
  zones: l.zones,
  activeAreaId: l.activeAreaId,
});

describe('PV13 — la v2 AJOUTE sans rien retirer', () => {
  const ctx = makeCtx([
    zone('area-1', { renderPlan: renderPlan(3), result: { panels: 3, kwc: 2.16, annualKwh: 3400, savingsLow: 1, savingsHigh: 2 } }),
    zone('area-2', { renderPlan: renderPlan(2), result: { panels: 2, kwc: 1.44, annualKwh: 2100, savingsLow: 1, savingsHigh: 2 } }),
  ]);

  it('annonce version 2 et expose les nouveaux champs', () => {
    const l = serializeLayout(ctx, 9000);
    expect(l.version).toBe(2);
    expect(l.result).toBeDefined();
    expect(l.scenario).toBe('reseau'); // défaut
    expect(l.panelWatt).toBe(PANEL2_WATT);
    expect(l.battery).toBeNull();
    expect(l.source).toBe('lead');
    expect(l.devisId).toBeNull();
  });

  it('AUCUN champ v1 perdu ni modifié par l’ajout du meta', () => {
    const bare = serializeLayout(ctx, 9000);
    const rich = serializeLayout(ctx, 9000, {
      scenario: 'hybride',
      panelWatt: 615,
      battery: { kwh: 10, count: 2, model: 'Deye' },
      source: 'devis',
      devisId: 'DV-2026-014',
      savingsMad: 12345,
    });
    expect(v1Fields(rich as never)).toEqual(v1Fields(bare as never));
    // Les champs v1 sont TOUS présents, au même endroit.
    for (const k of ['pin', 'outline', 'billKwh', 'zones', 'activeAreaId']) {
      expect(Object.prototype.hasOwnProperty.call(rich, k)).toBe(true);
    }
    expect(rich.billKwh).toBe(9000);
    expect(rich.activeAreaId).toBe('area-1');
    expect(rich.zones.length).toBe(2);
  });

  it('le résultat global SOMME les géométries réellement exportées', () => {
    const l = serializeLayout(ctx, 9000);
    const geoPanels = l.zones.reduce((s, z) => s + (z.geometry?.count ?? 0), 0);
    const geoKwc = l.zones.reduce((s, z) => s + (z.geometry?.kwc ?? 0), 0);
    expect(l.result!.panels).toBe(geoPanels);
    expect(l.result!.panels).toBe(5); // 3 + 2 posés
    expect(l.result!.kwc).toBeCloseTo(geoKwc, 9);
    // Production = somme des résultats de zone DÉJÀ calculés (même source que l'écran).
    expect(l.result!.annualKwh).toBe(3400 + 2100);
  });

  it('les économies ne sont jamais inventées : null sans meta, la valeur fournie sinon', () => {
    expect(serializeLayout(ctx, 9000).result!.savings).toBeNull();
    expect(serializeLayout(ctx, 9000, { savingsMad: 8700 }).result!.savings).toBe(8700);
    expect(serializeLayout(ctx, 9000, { savingsMad: Number.NaN }).result!.savings).toBeNull();
  });

  it('le meta est repris TEL QUEL (scénario, panneau, batterie, origine, devis)', () => {
    const l = serializeLayout(ctx, 9000, {
      scenario: 'avec_batterie',
      panelWatt: 550,
      battery: { kwh: 5.12, count: 1 },
      source: 'devis',
      devisId: 42,
    });
    expect(l.scenario).toBe('avec_batterie');
    expect(l.panelWatt).toBe(550);
    expect(l.battery).toEqual({ kwh: 5.12, count: 1 });
    expect(l.source).toBe('devis');
    expect(l.devisId).toBe(42);
  });

  it('reste un JSON PUR (aucun objet moteur ne fuit)', () => {
    const flat = JSON.stringify(serializeLayout(ctx, 9000, { source: 'devis', devisId: 7 }));
    expect(flat).not.toContain('renderPlan');
    expect(flat).not.toContain('ringENU');
    expect(JSON.parse(flat).version).toBe(2);
  });
});

describe('PV13 — deserializeLayout ignore les ajouts v2', () => {
  it('round-trip identité sur la géométrie et le dimensionnement', () => {
    const z1 = zone('area-1');
    const z2 = zone('area-2', { neededPanels: 8, neededAuto: false, roofType: 'pitched', pitchDeg: 30 });
    const l = serializeLayout(makeCtx([z1, z2]), 9000, { source: 'devis', devisId: 'DV-1', scenario: 'hybride' });
    const back = deserializeLayout(l);
    expect(back.length).toBe(2);
    expect(back[0].vertices).toEqual(z1.vertices);
    expect(back[0].obstacles).toEqual(z1.obstacles);
    expect(back[0].neededPanels).toBe(12);
    expect(back[1].neededPanels).toBe(8);
    expect(back[1].neededAuto).toBe(false);
    expect(back[1].roofType).toBe('pitched');
    // Les champs dérivés repartent à null — l'optimiseur les recalcule au boot.
    expect(back[0].result).toBeNull();
    expect(back[0].renderPlan).toBeNull();
    // Aucun champ v2 ne s'invite dans les AreaRecord reconstruits.
    expect(Object.prototype.hasOwnProperty.call(back[0], 'scenario')).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(back[0], 'devisId')).toBe(false);
  });

  it('un JSON v1 (sans les ajouts) se relit exactement pareil', () => {
    const l = serializeLayout(makeCtx([zone('area-1')]), 9000);
    const asV1 = JSON.parse(JSON.stringify(l));
    delete asV1.result;
    delete asV1.scenario;
    delete asV1.panelWatt;
    delete asV1.battery;
    delete asV1.source;
    delete asV1.devisId;
    asV1.version = 1;
    expect(deserializeLayout(asV1)).toEqual(deserializeLayout(l));
  });
});

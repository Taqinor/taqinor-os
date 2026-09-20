// Tests ciblés de prefill.ts — la sérialisation CAL102 (mesures) + CAL57/CAL59 (arêtes
// typées, bâtiment). D'autres extensions v2 (CAL66/CAL67/CAL72…) ajouteront leurs propres
// describe() ici au lieu d'un fichier par tâche (même contrat v2, même fichier source).
import { describe, expect, it } from 'vitest';
import { serializeMeasurements, deserializeMeasurements, serializeLayout, deserializeLayout } from './prefill';
import { type Measurement } from './mesureUi';
import { type Ctx } from './context';
import { type AreaRecord } from './types';

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
    obstacles: [],
    roofType: 'pitched',
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

describe('CAL102 — serializeMeasurements', () => {
  it('conserve les mesures géométriquement valides, intactes', () => {
    const list: Measurement[] = [
      { id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]], label: 'côté sud' },
      { id: 'm2', kind: 'area', points: [[0, 0], [1, 0], [1, 1]] },
    ];
    expect(serializeMeasurements(list)).toEqual(list);
  });

  it('écarte une mesure géométriquement invalide pour son genre, sans toucher aux autres', () => {
    const list: Measurement[] = [
      { id: 'm1', kind: 'distance', points: [[0, 0]] }, // < 2 points : invalide
      { id: 'm2', kind: 'distance', points: [[0, 0], [0, 1]] }, // valide
    ];
    const out = serializeMeasurements(list);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('m2');
  });

  it('écarte une mesure sans id ou d’un genre inconnu', () => {
    const list = [
      { id: '', kind: 'distance', points: [[0, 0], [0, 1]] },
      { id: 'm2', kind: 'diagonale', points: [[0, 0], [0, 1]] },
    ] as unknown as Measurement[];
    expect(serializeMeasurements(list)).toEqual([]);
  });

  it('null/undefined/non-tableau → tableau vide (jamais une exception)', () => {
    expect(serializeMeasurements(null)).toEqual([]);
    expect(serializeMeasurements(undefined)).toEqual([]);
    expect(serializeMeasurements([] as Measurement[])).toEqual([]);
  });

  it('omet `label` quand absent (jamais `label: undefined` dans le JSON)', () => {
    const out = serializeMeasurements([{ id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]] }]);
    expect('label' in out[0]).toBe(false);
  });
});

describe('CAL102 — deserializeMeasurements', () => {
  it('relit measurements depuis un layout complet', () => {
    const layout = { measurements: [{ id: 'm1', kind: 'distance', points: [[0, 0], [0, 1]] }] };
    expect(deserializeMeasurements(layout)).toEqual(layout.measurements);
  });

  it('accepte aussi un tableau brut directement', () => {
    const raw = [{ id: 'm1', kind: 'angle', points: [[0, 0], [1, 1], [1, 0]] }];
    expect(deserializeMeasurements(raw)).toEqual(raw);
  });

  it('round-trip : serializeMeasurements → deserializeMeasurements = identité (mesures valides)', () => {
    const list: Measurement[] = [{ id: 'm1', kind: 'distance', points: [[-7.6, 33.5], [-7.601, 33.5]], label: 'test' }];
    const written = { measurements: serializeMeasurements(list) };
    expect(deserializeMeasurements(written)).toEqual(list);
  });

  it('un JSON douteux (measurements absent/mal formé) → tableau vide, jamais une exception', () => {
    expect(deserializeMeasurements(null)).toEqual([]);
    expect(deserializeMeasurements({})).toEqual([]);
    expect(deserializeMeasurements({ measurements: 'nope' })).toEqual([]);
  });
});

describe('CAL57 — arêtes typées, sérialisées', () => {
  it('une zone seule (pas d’adjacence) porte un égout + des arêtes inconnues, jamais de faîtière', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    const z = layout.zones[0];
    expect(z.edges).toBeTruthy();
    expect(z.edges!.length).toBe(4);
    expect(z.edges!.some((e) => e.type === 'egout')).toBe(true);
    expect(z.edges!.some((e) => e.type === 'faitage')).toBe(false);
  });

  it('un document ancien SANS edges se relit sans en gagner (round-trip verbatim, pas de déduction à la lecture)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    delete (layout.zones[0] as { edges?: unknown }).edges;
    const back = deserializeLayout(layout);
    expect(back[0].edges).toBeUndefined();
  });

  it('les arêtes survivent à un aller-retour de sérialisation (round-trip)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    const back = deserializeLayout(layout);
    expect(back[0].edges).toEqual(layout.zones[0].edges);
  });
});

describe('CAL59 — buildingId (multi-bâtiments)', () => {
  it('absent par défaut (bâtiment unique, comportement historique)', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('buildingId' in layout.zones[0]).toBe(false);
  });

  it('porté par zone quand renseigné, et survit au round-trip', () => {
    const areas = [zone('z1', { buildingId: 'bat-1' }), zone('z2', { buildingId: 'bat-2' })];
    const layout = serializeLayout(makeCtx(areas, 'z2'));
    expect(layout.zones.find((z) => z.id === 'z1')!.buildingId).toBe('bat-1');
    expect(layout.zones.find((z) => z.id === 'z2')!.buildingId).toBe('bat-2');
    const back = deserializeLayout(layout);
    expect(back.find((a) => a.id === 'z1')!.buildingId).toBe('bat-1');
    expect(back.find((a) => a.id === 'z2')!.buildingId).toBe('bat-2');
  });
});

// Tests ciblés de prefill.ts — la sérialisation CAL102 (mesures) + CAL57/CAL59 (arêtes
// typées, bâtiment). D'autres extensions v2 (CAL66/CAL67/CAL72…) ajouteront leurs propres
// describe() ici au lieu d'un fichier par tâche (même contrat v2, même fichier source).
import { describe, expect, it } from 'vitest';
import {
  serializeMeasurements,
  deserializeMeasurements,
  serializeEnvironment,
  deserializeEnvironment,
  serializeLayout,
  deserializeLayout,
} from './prefill';
import { type Measurement } from './mesureUi';
import { type EnvironmentObject } from './environment';
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

describe('CAL67 — serializeEnvironment / deserializeEnvironment', () => {
  it('conserve un objet valide, intact', () => {
    const list: EnvironmentObject[] = [
      { id: 'e1', kind: 'arbre', centerLng: -7.6, centerLat: 33.5, heightM: 6, crownDiameterM: 4, evergreen: true },
    ];
    expect(serializeEnvironment(list)).toEqual(list);
  });

  it('écarte un objet sans id, de genre inconnu, ou aux coordonnées non finies', () => {
    const list = [
      { id: '', kind: 'arbre', centerLng: -7.6, centerLat: 33.5 },
      { id: 'e2', kind: 'ovni', centerLng: -7.6, centerLat: 33.5 },
      { id: 'e3', kind: 'arbre', centerLng: NaN, centerLat: 33.5 },
      { id: 'e4', kind: 'batiment', centerLng: -7.6, centerLat: 33.5 },
    ] as unknown as EnvironmentObject[];
    const out = serializeEnvironment(list);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('e4');
  });

  it('n’écrit heightM/crownDiameterM que s’ils sont finis et positifs (jamais 0 ou négatif)', () => {
    const out = serializeEnvironment([
      { id: 'e1', kind: 'arbre', centerLng: -7.6, centerLat: 33.5, heightM: 0, crownDiameterM: -2 } as EnvironmentObject,
    ]);
    expect('heightM' in out[0]).toBe(false);
    expect('crownDiameterM' in out[0]).toBe(false);
  });

  it('round-trip : serialize → deserialize = identité pour un objet valide', () => {
    const list: EnvironmentObject[] = [{ id: 'e1', kind: 'batiment', centerLng: -7.6, centerLat: 33.5, heightM: 5, lengthM: 8, widthM: 6 }];
    const written = { environment: serializeEnvironment(list) };
    expect(deserializeEnvironment(written)).toEqual(list);
  });

  it('null/undefined/mal formé → tableau vide, jamais une exception', () => {
    expect(deserializeEnvironment(null)).toEqual([]);
    expect(deserializeEnvironment({})).toEqual([]);
    expect(deserializeEnvironment({ environment: 'nope' })).toEqual([]);
  });
});

describe('CAL67 — serializeLayout porte l’environnement (additif)', () => {
  it('absent du layout quand ctx.environment est vide/undefined', () => {
    const areas = [zone('z1')];
    const layout = serializeLayout(makeCtx(areas));
    expect('environment' in layout).toBe(false);
  });

  it('présent et round-trippable quand renseigné', () => {
    const areas = [zone('z1')];
    const ctx = makeCtx(areas);
    (ctx as unknown as { environment: EnvironmentObject[] }).environment = [
      { id: 'e1', kind: 'arbre', centerLng: -7.6002, centerLat: 33.4998, heightM: 6, crownDiameterM: 4 },
    ];
    const layout = serializeLayout(ctx);
    expect(layout.environment).toHaveLength(1);
    expect(deserializeEnvironment(layout)).toEqual(ctx.environment);
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

describe('CAL66/CAL72 — hauteur d’obstacle + provenance, sérialisées', () => {
  it('heightM et provenance survivent au round-trip quand renseignés', () => {
    const areas = [
      zone('z1', {
        obstacles: [{ id: 'o1', centerLng: -7.5995, centerLat: 33.5905, lengthM: 1, widthM: 1, heightM: 1.2, provenance: 'MESURE' }],
      }),
    ];
    const layout = serializeLayout(makeCtx(areas));
    expect(layout.zones[0].obstacles[0].heightM).toBe(1.2);
    expect(layout.zones[0].obstacles[0].provenance).toBe('MESURE');
    const back = deserializeLayout(layout);
    expect(back[0].obstacles[0].heightM).toBe(1.2);
    expect(back[0].obstacles[0].provenance).toBe('MESURE');
  });

  it('absents par défaut (comportement historique)', () => {
    const areas = [zone('z1', { obstacles: [{ id: 'o1', centerLng: -7.5995, centerLat: 33.5905, lengthM: 1, widthM: 1 }] })];
    const layout = serializeLayout(makeCtx(areas));
    expect('heightM' in layout.zones[0].obstacles[0]).toBe(false);
    expect('provenance' in layout.zones[0].obstacles[0]).toBe(false);
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

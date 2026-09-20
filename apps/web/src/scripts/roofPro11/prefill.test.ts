// Tests ciblés de prefill.ts — pour l'instant, la sérialisation CAL102 (mesures). D'autres
// extensions v2 (CAL57/CAL59/CAL66/CAL67/CAL72…) ajouteront leurs propres describe() ici au
// lieu d'un fichier par tâche (même contrat v2, même fichier source).
import { describe, expect, it } from 'vitest';
import { serializeMeasurements, deserializeMeasurements } from './prefill';
import { type Measurement } from './mesureUi';

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

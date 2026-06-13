import { describe, expect, it } from 'vitest';
import {
  SUPPLY_TYPES,
  ORIENTATIONS,
  cleanEnrichment,
  hasEnrichment,
} from '../src/lib/enrichment';

describe('cleanEnrichment — champs facultatifs, jamais bloquants', () => {
  it('entrée vide → objet vide (comportement identique au formulaire actuel)', () => {
    expect(cleanEnrichment({})).toEqual({});
    expect(cleanEnrichment(undefined)).toEqual({});
    expect(cleanEnrichment(null)).toEqual({});
    expect(hasEnrichment(cleanEnrichment({}))).toBe(false);
  });

  it('champs vides ou absents → ignorés (rien ne ride along)', () => {
    expect(cleanEnrichment({ supplyType: '', roofArea: '', orientation: '' })).toEqual({});
    // Une valeur hors liste n'est jamais retenue (anti-injection)
    expect(cleanEnrichment({ supplyType: 'bidon', orientation: 'haut' })).toEqual({});
  });

  it('type d’alimentation : seules les valeurs canoniques passent', () => {
    expect(cleanEnrichment({ supplyType: 'mono' })).toEqual({ supplyType: 'mono' });
    expect(cleanEnrichment({ supplyType: 'tri' })).toEqual({ supplyType: 'tri' });
    expect(cleanEnrichment({ supplyType: 'inconnu' })).toEqual({ supplyType: 'inconnu' });
    expect(SUPPLY_TYPES.map((s) => s.id)).toEqual(['mono', 'tri', 'inconnu']);
  });

  it('orientation : seules les valeurs canoniques passent', () => {
    for (const o of ORIENTATIONS) {
      expect(cleanEnrichment({ orientation: o.id })).toEqual({ orientation: o.id });
    }
    expect(ORIENTATIONS.map((o) => o.id)).toEqual([
      'sud', 'sud-est', 'sud-ouest', 'est', 'ouest', 'nord', 'inconnu',
    ]);
  });

  it('surface de toiture : nombre positif accepté, borné, jamais négatif', () => {
    expect(cleanEnrichment({ roofArea: '80' })).toEqual({ roofAreaM2: 80 });
    expect(cleanEnrichment({ roofArea: 120.5 })).toEqual({ roofAreaM2: 120.5 });
    // Valeurs absurdes rejetées sans bloquer le reste
    expect(cleanEnrichment({ roofArea: '-5' })).toEqual({});
    expect(cleanEnrichment({ roofArea: '0' })).toEqual({});
    expect(cleanEnrichment({ roofArea: 'abc' })).toEqual({});
    // Plafond raisonnable (anti-saisie folle), n'affecte jamais la capture
    expect(cleanEnrichment({ roofArea: 99999999 })).toEqual({});
  });

  it('tous les champs remplis → tous présents', () => {
    const e = cleanEnrichment({ supplyType: 'tri', roofArea: '150', orientation: 'sud-ouest' });
    expect(e).toEqual({ supplyType: 'tri', roofAreaM2: 150, orientation: 'sud-ouest' });
    expect(hasEnrichment(e)).toBe(true);
  });
});

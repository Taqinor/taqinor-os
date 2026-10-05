// ACAL99 — la cible VENDUE à la réouverture : jamais au-dessus de la conception enregistrée,
// jamais le total du site au seul pan actif. PURE (aucun DOM, aucune carte).
import { describe, expect, it } from 'vitest';
import { repartirCibleVendue, type PanCible } from './cible';
import { hydrateFromDevis } from './prefill';

const pan = (id: string, neededPanels: number, neededAuto: boolean, count?: number): PanCible => ({
  id,
  neededPanels,
  neededAuto,
  ...(count != null ? { geometrieEnregistree: { count } } : {}),
});

describe('ACAL99 — repartirCibleVendue', () => {
  it('document posé à 8 + cible devis 12 → objectif 8', () => {
    // Le chemin réel : la cible vient de `hydrateFromDevis` (prefill.ts, cible.panneaux).
    const h = hydrateFromDevis({ id: 5, cible: { panneaux: 12 } });
    const r = repartirCibleVendue({ cibleVendue: h.neededPanels!, zones: [pan('area-1', 8, false, 8)], activeAreaId: 'area-1' });
    expect(r).toEqual({ mode: 'conserver', objectifs: { 'area-1': 8 } });
  });

  it('deux zones 20/20 + cible 40 → 20/20', () => {
    const r = repartirCibleVendue({
      cibleVendue: 40,
      zones: [pan('area-1', 20, false), pan('area-2', 20, false)],
      activeAreaId: 'area-1',
    });
    expect(r).toEqual({ mode: 'conserver', objectifs: { 'area-1': 20, 'area-2': 20 } });
  });

  it('zone unique sans compte → cible imposée', () => {
    expect(repartirCibleVendue({ cibleVendue: 12, zones: [pan('area-1', 0, true)], activeAreaId: 'area-1' }))
      .toEqual({ mode: 'imposer', cible: 12 });
  });

  it('plusieurs pans sans aucun compte : le total n’est jamais imposé au pan actif', () => {
    expect(repartirCibleVendue({ cibleVendue: 40, zones: [pan('a', 0, true), pan('b', 0, true)], activeAreaId: 'a' }))
      .toEqual({ mode: 'conserver', objectifs: {} });
  });
});

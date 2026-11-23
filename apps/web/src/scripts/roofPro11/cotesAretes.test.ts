// ACAL1328 — cotes d'arêtes du toit tracé (maquette Main : « 12,4 m » posé sur chaque bord). La fonction PURE est
// exécutée sur un rectangle connu ; le calque est monté sur une carte de test (aucun DOM, aucune MapLibre) pour prouver
// qu'il suit un sommet déplacé, se tait en 3D et en présentation, et n'est jamais posé sur le site public.
import { describe, expect, it } from 'vitest';
import { CALQUE_COTES, cotesDesAretes, monterCotesAretes, texteCote } from './cotesAretes';
import { CALQUES_EDITION, poserPresentation } from './presentationCarte';
import { rectRing } from './harnaisAtelier';
import { type LngLat } from '../../lib/roof';

/** Carte de test : sources, calques, pente et événements — juste ce que lit le calque. */
function carteDeTest() {
  const donnees = new Map<string, { features: Array<{ properties: { texte: string }; geometry: { coordinates: LngLat } }> }>();
  const visibilite = new Map<string, string>();
  const ecoute = new Map<string, Array<(e: { sourceId?: string }) => void>>();
  let pente = 0;
  const carte = {
    addSource: (id: string, s: { data: never }) => { donnees.set(id, s.data); },
    getSource: (id: string) => ({ setData: (d: never) => { donnees.set(id, d); } }),
    addLayer: (l: { id: string; layout?: { visibility?: string } }) => { visibilite.set(l.id, l.layout?.visibility ?? 'visible'); },
    getLayer: (id: string) => (visibilite.has(id) ? {} : undefined),
    getLayoutProperty: (id: string) => visibilite.get(id),
    setLayoutProperty: (id: string, _n: string, v: string) => { visibilite.set(id, v); },
    getPitch: () => pente,
    on: (t: string, fn: (e: { sourceId?: string }) => void) => { ecoute.set(t, [...(ecoute.get(t) ?? []), fn]); },
  };
  const emettre = (t: string, e: { sourceId?: string } = {}) => (ecoute.get(t) ?? []).forEach((fn) => fn(e));
  const textes = () => (donnees.get('rp9-cotes')?.features ?? []).map((f) => f.properties.texte);
  return { carte, emettre, textes, visibilite, pencher: (p: number) => { pente = p; emettre('pitch'); } };
}

describe('ACAL1328 — cotesDesAretes', () => {
  it('4 sommets ⇒ 4 cotes arrondies au dixième, virgule', () => {
    const ring = rectRing(12.4, 8.1);
    const cotes = cotesDesAretes(ring, true);
    expect(cotes.map((c) => c.texte)).toEqual(['12,4 m', '8,1 m', '12,4 m', '8,1 m']);
    // Le point de pose est le MILIEU de l'arête (jamais un sommet).
    expect(cotes[0].milieu[0]).toBeCloseTo((ring[0][0] + ring[1][0]) / 2, 12);
    expect(cotes[0].milieu[1]).toBeCloseTo((ring[0][1] + ring[1][1]) / 2, 12);
  });

  it('contour en cours : n − 1 arêtes ; aucun pan sans arête ; arête nulle ignorée', () => {
    const ring = rectRing(12.4, 8.1);
    expect(cotesDesAretes(ring.slice(0, 3), false)).toHaveLength(2);
    expect(cotesDesAretes([ring[0]], true)).toEqual([]);
    expect(cotesDesAretes([], true)).toEqual([]);
    expect(cotesDesAretes([ring[0], ring[0], ring[1]], false).map((c) => c.texte)).toEqual(['12,4 m']);
    expect(texteCote(8.06)).toBe('8,1 m');
  });
});

describe('ACAL1328 — calque rp9-cotes', () => {
  it('suit le sommet déplacé, se tait en 3D et en présentation', () => {
    const t = carteDeTest();
    const pans: Array<{ sommets: LngLat[]; ferme: boolean }> = [{ sommets: rectRing(12.4, 8.1), ferme: true }];
    monterCotesAretes(t.carte, () => pans, true);
    expect(t.textes()).toEqual(['12,4 m', '8,1 m', '12,4 m', '8,1 m']);
    // Sommet déplacé : le tracé re-pose ses points (`rp9-pts`) ⇒ les cotes sont recalculées.
    pans[0] = { sommets: rectRing(14, 8.1), ferme: true };
    t.emettre('sourcedata', { sourceId: 'rp9-pts' });
    expect(t.textes()).toEqual(['14,0 m', '8,1 m', '14,0 m', '8,1 m']);
    t.pencher(60);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('none');
    t.pencher(0);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('visible');
    expect(CALQUES_EDITION).toContain(CALQUE_COTES);
    poserPresentation(t.carte, true);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('none');
    poserPresentation(t.carte, false);
    expect(t.visibilite.get(CALQUE_COTES)).toBe('visible');
  });

  it('site public (option de montage absente) : aucun calque posé', () => {
    const t = carteDeTest();
    monterCotesAretes(t.carte, () => [{ sommets: rectRing(12.4, 8.1), ferme: true }], false);
    expect(t.visibilite.has(CALQUE_COTES)).toBe(false);
  });
});

// AP-F1 (fondateur 26/08/2026) — le vendeur ERP ne voit AUCUN panneau tant qu'il ne
// retrace pas le toit à la main, alors que le tracé client apparaît déjà comme calque
// passif : `hydrateFromLead` (qui SÈME la zone active éditable, appelée par
// roof-tool-pro11.ts `applyHydration`/`applyDevisHydration`) ré-implémentait son PROPRE
// filtre de contour et n'acceptait QUE la forme `[lat, lng]`, alors que
// `referenceContourRing` (le calque de référence L-MAP) accepte déjà les DEUX formes
// RÉELLES de `Lead.roof_outline` — `[lat, lng]` (le webhook) ET `{lat, lng}`
// (import/saisie manuelle). Un contour `{lat, lng}` se dessinait donc « affiché » sur
// la carte (calque de référence) mais ne posait AUCUN panneau (zone éditable vide).
//
// Le correctif fait de `hydrateFromLead` un DÉLÉGUÉ de `referenceContourRing` : UN SEUL
// validateur de contour. Ce fichier prouve (1) que les deux formes sèment désormais des
// sommets, avec une sortie IDENTIQUE à avant pour la forme tuple, (2) que les
// garde-fous (< 3 sommets valides, hors bornes) tiennent toujours, et (3) que
// `hydrateFromDevis`, dont le repli lead-like appelle `hydrateFromLead` en interne
// (prefill.ts), hérite du correctif : un devis SANS design enregistré mais dont le lead
// porte un contour `{lat, lng}` sème désormais >= 3 sommets au lieu de zéro.
import { describe, expect, it } from 'vitest';
import { hydrateFromDevis, hydrateFromLead } from '../src/scripts/roofPro11/prefill';

// Carré ≈ 20 m à Casablanca, MÊME contour que referenceContourLMap.test.ts /
// ToitClientOverlay.test.jsx / TraceToitClient.test.jsx (fixture partagée).
const CONTOUR_TUPLES: Array<[number, number]> = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
];
const CONTOUR_OBJETS = CONTOUR_TUPLES.map(([lat, lng]) => ({ lat, lng }));
const ATTENDU_LNGLAT = [
  [-7.603, 33.589],
  [-7.602784, 33.589],
  [-7.602784, 33.58918],
  [-7.603, 33.58918],
];

describe('AP-F1 — hydrateFromLead accepte les DEUX formes de contour (UN SEUL validateur)', () => {
  it('forme tuple [lat, lng] — sortie IDENTIQUE à avant (golden)', () => {
    const h = hydrateFromLead({ roof_outline: CONTOUR_TUPLES });
    expect(h.vertices.length).toBeGreaterThanOrEqual(3);
    expect(h.vertices).toEqual(ATTENDU_LNGLAT);
  });

  it('forme objet {lat, lng} — sème désormais les mêmes sommets (le bug corrigé)', () => {
    const h = hydrateFromLead({ roof_outline: CONTOUR_OBJETS });
    expect(h.vertices.length).toBeGreaterThanOrEqual(3);
    expect(h.vertices).toEqual(ATTENDU_LNGLAT);
  });

  it('un contour mixte (tuples + objets) sème aussi — MÊME comportement que referenceContourRing', () => {
    const mixte = [
      CONTOUR_TUPLES[0],
      CONTOUR_OBJETS[1],
      CONTOUR_TUPLES[2],
    ];
    const h = hydrateFromLead({ roof_outline: mixte });
    expect(h.vertices).toEqual([ATTENDU_LNGLAT[0], ATTENDU_LNGLAT[1], ATTENDU_LNGLAT[2]]);
  });

  it('moins de 3 points valides (forme objet) → aucun sommet semé', () => {
    const h = hydrateFromLead({ roof_outline: CONTOUR_OBJETS.slice(0, 2) });
    expect(h.vertices).toEqual([]);
  });

  it('un sommet hors bornes (forme objet) fait tomber sous 3 restants → aucun sommet semé', () => {
    const horsBornes = [
      { lat: 999, lng: -7.603 }, // lat hors bornes → rejeté
      CONTOUR_OBJETS[1],
      CONTOUR_OBJETS[2],
    ];
    const h = hydrateFromLead({ roof_outline: horsBornes });
    expect(h.vertices).toEqual([]);
  });

  it('un sommet hors bornes (forme tuple) rejeté, mais 3 restants → sème quand même (MÊME bornage que referenceContourRing)', () => {
    const unRejete: Array<[number, number]> = [
      [999, -7.603], // lat hors bornes → rejeté
      CONTOUR_TUPLES[1],
      CONTOUR_TUPLES[2],
      CONTOUR_TUPLES[3],
    ];
    const h = hydrateFromLead({ roof_outline: unRejete });
    expect(h.vertices).toEqual([ATTENDU_LNGLAT[1], ATTENDU_LNGLAT[2], ATTENDU_LNGLAT[3]]);
  });

  it('lead nul/vide → rien n’est semé (pas de crash)', () => {
    expect(hydrateFromLead(null)).toEqual({ vertices: [], center: null, contact: {} });
    expect(hydrateFromLead({})).toEqual({ vertices: [], center: null, contact: {} });
  });
});

describe('AP-F1 — hydrateFromDevis, roof_layout SANS zones : repli lead-like sur geometrie.roof_outline', () => {
  it('roof_layout ABSENT + roof_outline présent → >= 3 sommets semés (repli lead-like), cible imposée', () => {
    const h = hydrateFromDevis({
      geometrie: { roof_outline: CONTOUR_TUPLES },
      cible: { panneaux: 18 },
    });
    // Repli lead-like : aucune zone reconstruite (pas de layout enregistré), mais un
    // contour semé — la fonction pure `hydrateFromLead` (corrigée par AP-F1) tourne
    // en interne (prefill.ts hydrateFromDevis, chemin « repli »).
    expect(h.zones).toBeNull();
    expect(h.vertices.length).toBeGreaterThanOrEqual(3);
    expect(h.vertices).toEqual(ATTENDU_LNGLAT);
    // La cible vendue impose le besoin — la facture ne décide plus.
    expect(h.neededAuto).toBe(false);
    expect(h.neededPanels).toBe(18);
  });

  it('roof_layout à zones VIDES ([]) + roof_outline présent → même repli, même semis', () => {
    const h = hydrateFromDevis({
      geometrie: {
        roof_layout: { version: 2, zones: [], pin: null, outline: [], billKwh: null, activeAreaId: '' },
        roof_outline: CONTOUR_TUPLES,
      },
      cible: { panneaux: 9 },
    });
    expect(h.zones).toBeNull();
    expect(h.vertices.length).toBeGreaterThanOrEqual(3);
    expect(h.neededAuto).toBe(false);
    expect(h.neededPanels).toBe(9);
  });

  it('sans cible vendue (cible.panneaux absent), le contour sème quand même — la facture reprend la main', () => {
    const h = hydrateFromDevis({ geometrie: { roof_outline: CONTOUR_TUPLES } });
    expect(h.vertices.length).toBeGreaterThanOrEqual(3);
    expect(h.neededAuto).toBe(true);
    expect(h.neededPanels).toBeNull();
  });
});

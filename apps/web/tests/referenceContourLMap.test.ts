// L-MAP (fondateur 26/08/2026 : « i want it visible on the map in the 3D
// layouter ») — `referenceContourRing` (roofPro11/prefill.ts) est la fonction
// PURE que `roof-tool-pro11.ts` appelle pour transformer le contour ORIGINAL
// du client (`opts.referenceContour`) en anneau `[lng, lat]` prêt pour la
// source GeoJSON du calque de référence géo-référencé.
//
// FINDING A (revue adversariale 26/08/2026) — cette fonction DOIT accepter
// EXACTEMENT ce que `normaliserContour` (traceToit.js, ERP) accepte : les
// DEUX formes de points (`[lat, lng]` et `{lat, lng}`) ET le MÊME bornage
// lat ∈ [-90, 90] / lng ∈ [-180, 180]. Avant ce correctif, elle n'acceptait
// QUE la forme tableau (sans bornage) : un lead dont `roof_outline` est en
// forme objet montrait la légende/bascule (ERP) mais AUCUN calque carte —
// « affiché » qui ment. Et un contour hors bornes (webhook malformé, import
// manuel) passait ICI sans jamais passer par `contourExploitable` côté écran
// (`ToitureDesign.jsx` gate désormais `referenceContour` sur ce MÊME
// predicat AVANT de l'envoyer au builder) — deux gardes, UNE seule vérité.
import { describe, expect, it } from 'vitest';
import { referenceContourRing } from '../src/scripts/roofPro11/prefill';

// Carré ≈ 20 m à Casablanca, MÊME contour que TraceToitClient/traceToit.test.mjs
// côté ERP (frontend/src/features/crm/workspace/traceToit.test.mjs) — la fixture
// partagée par les deux couches (fiche lead + calque du calepinage).
const CONTOUR: Array<[number, number]> = [
  [33.589, -7.603],
  [33.589, -7.602784],
  [33.58918, -7.602784],
  [33.58918, -7.603],
];

describe('referenceContourRing', () => {
  it('convertit [lat, lng] × n en [lng, lat] × n, MÊME convention que hydrateFromLead', () => {
    const ring = referenceContourRing(CONTOUR);
    expect(ring).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);
  });

  it('null sans contour exploitable — jamais un anneau dégénéré', () => {
    expect(referenceContourRing(null)).toBeNull();
    expect(referenceContourRing(undefined)).toBeNull();
    expect(referenceContourRing([])).toBeNull();
    expect(referenceContourRing([[33.589, -7.603], [33.589, -7.602784]])).toBeNull();
  });

  it('écarte les points non finis, refuse si moins de 3 restent valides', () => {
    const avecUnPointInvalide: Array<[number, number]> = [
      [33.589, -7.603],
      [Number.NaN, -7.602784],
      [33.58918, -7.602784],
      [33.58918, -7.603],
    ];
    const ring = referenceContourRing(avecUnPointInvalide);
    expect(ring).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);
  });

  // FINDING A (i) — la forme objet `{lat, lng}` (import/saisie manuelle,
  // MÊME forme que `normaliserContour` accepte déjà côté ERP).
  it('accepte AUSSI la forme objet {lat, lng} — MÊME forme que normaliserContour', () => {
    const contourObjet = [
      { lat: 33.589, lng: -7.603 },
      { lat: 33.589, lng: -7.602784 },
      { lat: 33.58918, lng: -7.602784 },
      { lat: 33.58918, lng: -7.603 },
    ];
    expect(referenceContourRing(contourObjet)).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);
  });

  it('mélange [lat, lng] et {lat, lng} dans le même contour, comme normaliserContour', () => {
    const mixte = [
      [33.589, -7.603] as [number, number],
      { lat: 33.589, lng: -7.602784 },
      [33.58918, -7.602784] as [number, number],
    ];
    expect(referenceContourRing(mixte)).toEqual([
      [-7.603, 33.589],
      [-7.602784, 33.589],
      [-7.602784, 33.58918],
    ]);
  });

  // FINDING A (ii) — bornage lat/lng, MÊME predicat que `borne()` de
  // traceToit.js : un point hors bornes ne doit JAMAIS dessiner un polygone
  // à une position aberrante sans bascule pour le masquer.
  it('rejette un sommet hors bornes (lat/lng aberrants) — jamais un anneau mal placé', () => {
    const latHorsBornes: Array<[number, number]> = [
      [999, -7.603],
      [33.589, -7.602784],
      [33.58918, -7.602784],
      [33.58918, -7.603],
    ];
    // 1 point rejeté → 3 restants → toujours un anneau valide (le test
    // suivant couvre le cas où ça retombe sous 3).
    expect(referenceContourRing(latHorsBornes)).toEqual([
      [-7.602784, 33.589],
      [-7.602784, 33.58918],
      [-7.603, 33.58918],
    ]);

    const lngHorsBornes: Array<[number, number]> = [
      [33.589, -7.603],
      [33.589, 250],
      [33.58918, -7.602784],
    ];
    // 1 seul point rejeté, 2 restants < 3 → aucun anneau exploitable.
    expect(referenceContourRing(lngHorsBornes)).toBeNull();
  });
});

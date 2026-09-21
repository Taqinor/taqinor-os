// CALX95 câblage — le retrait PROPRE à une arête passe enfin par le VRAI chemin de pavage.
//
// `rognerParArete` (roofSetbackEdge.ts) et l'option `retraitsParAreteM` de `layoutProRows2`
// existaient déjà, mais `layoutProRows2` n'a aucun appelant de production : l'atelier pave
// par `solveLive` (V7, toit plat) et `solveLivePitched` (V8, toit en pente), qui ne
// recevaient que les retraits de CATÉGORIE. Ce fichier prouve les deux moitiés de la tâche :
//  1. un retrait MANUEL sur une arête change le nombre de modules posés par ce vrai chemin ;
//  2. sans retrait manuel, le résultat est IDENTIQUE — sérialisation octet pour octet.
import { describe, expect, it } from 'vitest';
import { anneauPosableParArete, solveLive } from './estimatorBrainV7';
import { solveLivePitched } from './estimatorBrainV8';
import { supplementsParArete } from './roofSetbackEdge';
import { type LngLat } from './roof';

const LAT = 33.5;
const LNG = -7.6;
/** Facture mensuelle (MAD) assez haute pour que le besoin ne plafonne pas le pavage :
 *  on compare alors ce qui TIENT (`fitCount`), pas ce que la facture demande. */
const FACTURE_MAD = 9000;
/** Retrait de CATÉGORIE de référence (m) — celui déjà appliqué au pourtour entier. */
const RETRAIT_CATEGORIE_M = 0.5;

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;

/** Carré de `coteM` mètres de côté, ancré au sud-ouest sur (LNG, LAT). */
function carre(coteM: number): LngLat[] {
  const dLat = coteM / DEG2M;
  const dLng = coteM / (DEG2M * Math.cos(LAT * DEG2RAD));
  return [
    [LNG, LAT],
    [LNG + dLng, LAT],
    [LNG + dLng, LAT + dLat],
    [LNG, LAT + dLat],
  ];
}

describe('CALX95 câblage — `anneauPosableParArete` : rogner l’anneau, ou ne rien toucher', () => {
  const ring = carre(30);

  it('table absente / vide / sans entrée exploitable : le contour repart TEL QUEL (même référence)', () => {
    expect(anneauPosableParArete(ring)).toBe(ring);
    expect(anneauPosableParArete(ring, {})).toBe(ring);
    expect(anneauPosableParArete(ring, { 0: 0 })).toBe(ring);
    expect(anneauPosableParArete(ring, { 0: -1 })).toBe(ring);
    expect(anneauPosableParArete(ring, { 0: Number.NaN })).toBe(ring);
    expect(anneauPosableParArete(ring, { 9: 1 })).toBe(ring); // segment hors contour
  });

  it('un retrait de 4 m sur UNE arête rogne une bande de 4 m de CE côté seulement', () => {
    const posable = anneauPosableParArete(ring, { 0: 4 });
    expect(posable).not.toBe(ring);
    expect(posable.length).toBeGreaterThanOrEqual(3);
    // L'arête 0 va du sommet sud-ouest au sommet sud-est : c'est le bord SUD qui recule.
    const latMinAvant = Math.min(...ring.map(([, lat]) => lat));
    const latMinApres = Math.min(...posable.map(([, lat]) => lat));
    expect((latMinApres - latMinAvant) * DEG2M).toBeCloseTo(4, 3);
    // Le bord nord, lui, n'a pas bougé.
    expect(Math.max(...posable.map(([, lat]) => lat))).toBeCloseTo(Math.max(...ring.map(([, lat]) => lat)), 12);
  });

  it('des retraits qui mangent tout le pan rendent « aucune surface posable », jamais le contour entier', () => {
    expect(anneauPosableParArete(ring, { 0: 20, 2: 20 })).toEqual([]);
  });
});

describe('CALX95 câblage — `solveLive` (toit plat) : le vrai chemin de pavage', () => {
  const ring = carre(30);
  const reference = solveLive(ring, LAT, FACTURE_MAD, [], {}, {});

  it('AUCUN retrait d’arête : résultat IDENTIQUE octet pour octet à aujourd’hui', () => {
    const sansOption = JSON.stringify(reference);
    expect(JSON.stringify(solveLive(ring, LAT, FACTURE_MAD, [], {}, { retraitsParAreteM: {} }))).toBe(sansOption);
    expect(JSON.stringify(solveLive(ring, LAT, FACTURE_MAD, [], {}, { retraitsParAreteM: undefined }))).toBe(sansOption);
  });

  it('des arêtes SAISIES sans `retraitM` ne produisent aucune table : pavage inchangé', () => {
    const table = supplementsParArete(
      [{ index: 0 }, { index: 1 }, { index: 2 }, { index: 3 }],
      RETRAIT_CATEGORIE_M,
    );
    expect(table).toEqual({});
    expect(JSON.stringify(solveLive(ring, LAT, FACTURE_MAD, [], {}, { retraitsParAreteM: table }))).toBe(
      JSON.stringify(reference),
    );
  });

  it('un retrait MANUEL sur une arête fait baisser ce qui tient (le compte change vraiment)', () => {
    const table = supplementsParArete([{ index: 0, retraitM: 4 }], RETRAIT_CATEGORIE_M);
    expect(table).toEqual({ 0: 4 });
    const avec = solveLive(ring, LAT, FACTURE_MAD, [], {}, { retraitsParAreteM: table });
    expect(reference.winner.fitCount).toBeGreaterThan(0);
    expect(avec.winner.fitCount).toBeLessThan(reference.winner.fitCount);
  });

  it('quand le besoin dépasse ce qui tient, le nombre POSÉ baisse lui aussi', () => {
    const besoin = { need: 400 }; // au-delà de la capacité du pan : le toit est la limite
    const table = supplementsParArete([{ index: 0, retraitM: 4 }], RETRAIT_CATEGORIE_M);
    const sans = solveLive(ring, LAT, FACTURE_MAD, [], besoin, {});
    const avec = solveLive(ring, LAT, FACTURE_MAD, [], besoin, { retraitsParAreteM: table });
    expect(sans.winner.placedCount).toBe(sans.winner.fitCount);
    expect(avec.winner.placedCount).toBeLessThan(sans.winner.placedCount);
  });

  it('plus le retrait d’arête est grand, moins il tient — jamais l’inverse', () => {
    const fit = (retraitM: number): number =>
      solveLive(ring, LAT, FACTURE_MAD, [], {}, {
        retraitsParAreteM: supplementsParArete([{ index: 0, retraitM }], RETRAIT_CATEGORIE_M),
      }).winner.fitCount;
    expect(fit(8)).toBeLessThanOrEqual(fit(4));
    expect(fit(4)).toBeLessThanOrEqual(reference.winner.fitCount);
  });

  it('des retraits qui mangent tout le pan : aucune config viable, jamais un pavage de repli', () => {
    const table = supplementsParArete(
      [
        { index: 0, retraitM: 20 },
        { index: 2, retraitM: 20 },
      ],
      RETRAIT_CATEGORIE_M,
    );
    const res = solveLive(ring, LAT, FACTURE_MAD, [], {}, { retraitsParAreteM: table });
    expect(res.winner.fitCount).toBe(0);
    expect(res.noViableConfig).toBe(true);
  });
});

describe('CALX95 câblage — `solveLivePitched` (toit en pente) : même règle', () => {
  const ring = carre(30);
  const PENTE_DEG = 25;
  const FACE_DEG = 180;
  const reference = solveLivePitched(ring, LAT, FACTURE_MAD, PENTE_DEG, FACE_DEG, [], {}, {});

  it('AUCUN retrait d’arête : résultat IDENTIQUE octet pour octet à aujourd’hui', () => {
    const attendu = JSON.stringify(reference);
    expect(
      JSON.stringify(solveLivePitched(ring, LAT, FACTURE_MAD, PENTE_DEG, FACE_DEG, [], {}, { retraitsParAreteM: {} })),
    ).toBe(attendu);
  });

  it('un retrait MANUEL sur une arête fait baisser ce qui tient', () => {
    const table = supplementsParArete([{ index: 0, retraitM: 4 }], RETRAIT_CATEGORIE_M);
    const avec = solveLivePitched(ring, LAT, FACTURE_MAD, PENTE_DEG, FACE_DEG, [], {}, { retraitsParAreteM: table });
    expect(reference.winner.fitCount).toBeGreaterThan(0);
    expect(avec.winner.fitCount).toBeLessThan(reference.winner.fitCount);
  });
});

// CALX95 — retrait propre à CHAQUE arête physique du contour : géométrie pure
// (`rognerParArete`), règle de repli explicite sur la catégorie (`retraitArete`), et
// non-régression du calepinage quand aucune arête n'est saisie.
import { describe, expect, it } from 'vitest';
import { rognerParArete, retraitArete, supplementsParArete, type PointM } from './roofSetbackEdge';
import { layoutProRows2 } from './roofPro2';
import { type LngLat } from './roof';

/** Carré 10×10 m centré sur l'origine, sens DIRECT : segment 0 = SUD, 1 = EST,
 *  2 = NORD, 3 = OUEST. */
const CARRE: PointM[] = [
  [-5, -5],
  [5, -5],
  [5, 5],
  [-5, 5],
];

/** Le même carré parcouru dans l'autre sens (l'intérieur ne change pas de côté). */
const CARRE_INVERSE: PointM[] = [...CARRE].reverse();

/** Anneau lng/lat carré de `side` mètres (repris de tests/roofPro2.test.ts). */
function squareRing(side: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

describe('CALX95 — rognerParArete', () => {
  it('aucune arête saisie ⇒ anneau posable IDENTIQUE (non-régression)', () => {
    expect(rognerParArete(CARRE)).toEqual(CARRE);
    expect(rognerParArete(CARRE, {})).toEqual(CARRE);
  });

  it('une seule arête à 1 m : la bande est retirée de CE côté seulement', () => {
    const out = rognerParArete(CARRE, { 0: 1 });
    // Le côté sud remonte de 1 m ; les trois autres côtés ne bougent pas.
    expect(out).toEqual([
      [-5, -4],
      [5, -4],
      [5, 5],
      [-5, 5],
    ]);
  });

  it('le sens de parcours du contour ne change pas le côté rogné', () => {
    // Dans ce sens, le côté SUD est le segment 2 — c'est bien lui qui recule.
    const out = rognerParArete(CARRE_INVERSE, { 2: 1 });
    const ys = out.map((p) => p[1]);
    expect(Math.min(...ys)).toBeCloseTo(-4, 9);
    expect(Math.max(...ys)).toBeCloseTo(5, 9);
    const xs = out.map((p) => p[0]);
    expect(Math.min(...xs)).toBeCloseTo(-5, 9);
    expect(Math.max(...xs)).toBeCloseTo(5, 9);
  });

  it('deux arêtes opposées : chacune rogne sa propre bande', () => {
    const out = rognerParArete(CARRE, { 0: 1, 2: 2 });
    const ys = out.map((p) => p[1]);
    expect(Math.min(...ys)).toBeCloseTo(-4, 9);
    expect(Math.max(...ys)).toBeCloseTo(3, 9);
  });

  it('des retraits qui mangent tout le pan ⇒ aucune surface posable (jamais un repli)', () => {
    expect(rognerParArete(CARRE, { 0: 6, 2: 6 })).toEqual([]);
  });

  it('une valeur illisible, nulle, négative ou hors contour ne rogne RIEN', () => {
    const sales = { 0: 0, 1: -1, 2: Number.NaN, 9: 1 } as unknown as Record<number, number>;
    expect(rognerParArete(CARRE, sales)).toEqual(CARRE);
  });

  it('contour de moins de 3 sommets : rendu tel quel', () => {
    const segment: PointM[] = [
      [0, 0],
      [1, 0],
    ];
    expect(rognerParArete(segment, { 0: 1 })).toEqual(segment);
  });

  it('ne mute jamais son entrée', () => {
    const avant = JSON.stringify(CARRE);
    rognerParArete(CARRE, { 0: 1, 1: 2 });
    expect(JSON.stringify(CARRE)).toBe(avant);
  });
});

describe('CALX95 — retraitArete : l’arête d’abord, la catégorie en repli explicite', () => {
  it('un retrait SAISI sur l’arête s’ajoute au retrait de catégorie', () => {
    expect(retraitArete(1, 0.5)).toEqual({ totalM: 1.5, supplementM: 1, origine: 'arête' });
  });

  it('aucun retrait saisi ⇒ la catégorie s’applique seule, sans supplément', () => {
    expect(retraitArete(undefined, 0.5)).toEqual({ totalM: 0.5, supplementM: 0, origine: 'catégorie' });
  });

  it('un retrait d’arête illisible ou négatif n’invente rien : repli sur la catégorie', () => {
    expect(retraitArete(Number.NaN, 0.5).origine).toBe('catégorie');
    expect(retraitArete(-2, 0.5)).toEqual({ totalM: 0.5, supplementM: 0, origine: 'catégorie' });
  });

  it('une catégorie illisible vaut 0 (aucun total douteux fabriqué)', () => {
    expect(retraitArete(1, Number.NaN)).toEqual({ totalM: 1, supplementM: 1, origine: 'arête' });
  });
});

describe('CALX95 — supplementsParArete', () => {
  it('ne retient que les arêtes qui portent un retrait saisi', () => {
    const edges = [{ index: 0, retraitM: 1 }, { index: 1 }, { index: 2, retraitM: 0 }];
    expect(supplementsParArete(edges, 0.5)).toEqual({ 0: 1 });
  });

  it('aucune arête (ou aucune saisie) ⇒ table vide ⇒ calepinage d’aujourd’hui', () => {
    expect(supplementsParArete(undefined, 0.5)).toEqual({});
    expect(supplementsParArete([{ index: 0 }, { index: 1 }], 0.5)).toEqual({});
  });
});

describe('CALX95 — calepinage : le retrait par arête n’agit que là où il est saisi', () => {
  const ring = squareRing(20);

  it('sans retrait d’arête, le pavage est celui d’aujourd’hui, à l’identique', () => {
    const aujourdhui = layoutProRows2(ring, 'sud', 33.5);
    expect(layoutProRows2(ring, 'sud', 33.5, {})).toEqual(aujourdhui);
    expect(layoutProRows2(ring, 'sud', 33.5, { retraitsParAreteM: {} })).toEqual(aujourdhui);
    // Un retrait à 0 n'est PAS une saisie : rien ne change non plus.
    expect(layoutProRows2(ring, 'sud', 33.5, { retraitsParAreteM: { 0: 0 } })).toEqual(aujourdhui);
    expect(aujourdhui.count).toBeGreaterThan(0);
  });

  it('1 m sur la seule arête SUD : la bande sud perd ses panneaux, le reste est intact', () => {
    const aujourdhui = layoutProRows2(ring, 'sud', 33.5);
    const rogne = layoutProRows2(ring, 'sud', 33.5, { retraitsParAreteM: { 0: 1 } });
    expect(rogne.count).toBeLessThan(aujourdhui.count);
    // Le contour exporté reste le TRACÉ (on ne réécrit pas le toit, on pose moins dessus).
    expect(rogne.ringENU).toEqual(aujourdhui.ringENU);
    // Aucun panneau retenu n'est à moins d'un mètre de plus du bord sud qu'avant.
    const yMinAvant = Math.min(...aujourdhui.panels.map((p) => p.cy));
    const yMinApres = Math.min(...rogne.panels.map((p) => p.cy));
    expect(yMinApres).toBeGreaterThan(yMinAvant);
  });

  it('un retrait d’arête qui mange tout le pan ⇒ aucun panneau, pas un pavage de repli', () => {
    const rogne = layoutProRows2(ring, 'sud', 33.5, { retraitsParAreteM: { 0: 40 } });
    expect(rogne.count).toBe(0);
    expect(rogne.panels).toEqual([]);
  });
});

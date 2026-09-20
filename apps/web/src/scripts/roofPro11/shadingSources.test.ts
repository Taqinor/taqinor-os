// CAL66 + CAL67 — BRANCHEMENT de la hauteur d'obstacle et des objets d'environnement dans
// l'ombrage VIVANT. Jusqu'ici seules les ombres tracées (WJ19) dératant la production ; une
// cheminée à hauteur saisie ou un arbre voisin n'ombraient RIEN. Ce fichier prouve, sans DOM
// ni WebGL, que la source unifiée alimente bien le moteur d'ombrage — et que sans obstruction
// renseignée, rien ne change (non-régression stricte).
import { describe, expect, it } from 'vitest';
import { unifiedShadeEntries } from './shadingUi';
import { newEnvironmentObject, withEnvHeight, withCrownDiameter } from './environment';
import { roofObstacleShadeEntries, withHeight, defaultObstacle, resizedObstacle, type Obstacle } from '../../lib/obstacles';
import { hourlyShadeFactors, pointSolarAccess, type ShadeObstruction } from '../../lib/shadingEngine';
import { fallbackPerKwc } from '../../lib/productionEngine';

const ORIGIN: [number, number] = [-7.6, 33.5];
const LAT = 33.5;
/** 10 m au sud de l'origine, en latitude (≈ 9e-5°). */
const SOUTH_10M: [number, number] = [-7.6, 33.5 - 10 / 111320];
/** 4 m au sud : assez près pour que le cône d'occultation couvre la course du soleil. */
const SOUTH_4M: [number, number] = [-7.6, 33.5 - 4 / 111320];

describe('CAL66 — roofObstacleShadeEntries : la hauteur SAISIE fait l’ombre, rien d’autre', () => {
  it('un obstacle SANS hauteur ne produit aucune obstruction (comportement d’avant CAL66)', () => {
    const o = defaultObstacle('o1', SOUTH_10M);
    expect(roofObstacleShadeEntries([o], ORIGIN)).toEqual([]);
  });

  it('un obstacle AVEC hauteur produit une obstruction à cette hauteur exacte, non réduite du toit', () => {
    const o = withHeight(defaultObstacle('o1', SOUTH_10M), 2.5);
    const entries = roofObstacleShadeEntries([o], ORIGIN);
    expect(entries).toHaveLength(1);
    // L'obstacle est SUR le toit : sa hauteur saisie est déjà au-dessus du plan du champ.
    expect(entries[0].effHeightM).toBe(2.5);
    expect(entries[0].y).toBeLessThan(0); // au sud → y ENU négatif
    // Demi-largeur = demi-diagonale du rectangle saisi (2 × 2 m par défaut).
    expect(entries[0].halfWidthM).toBeCloseTo(Math.hypot(2, 2) / 2, 6);
  });

  it('liste vide / absente → aucune obstruction, jamais une erreur', () => {
    expect(roofObstacleShadeEntries([], ORIGIN)).toEqual([]);
    expect(roofObstacleShadeEntries(null, ORIGIN)).toEqual([]);
    expect(roofObstacleShadeEntries(undefined, ORIGIN)).toEqual([]);
  });
});

describe('CAL66 + CAL67 — unifiedShadeEntries : une seule source pour les trois familles', () => {
  const tracee: ShadeObstruction = {
    id: 's1',
    base: SOUTH_10M,
    tip: [SOUTH_10M[0], SOUTH_10M[1] + 5 / 111320],
    heightM: 9, // 9 m au-dessus du SOL
    halfWidthM: 3,
  };

  it('AUCUNE source renseignée → liste vide (non-régression stricte)', () => {
    expect(unifiedShadeEntries([], [], [], ORIGIN, 6)).toEqual([]);
    expect(unifiedShadeEntries(null, null, null, ORIGIN, 6)).toEqual([]);
  });

  it('les obstacles PLANS et les objets sans hauteur restent invisibles pour l’ombrage', () => {
    const plat = defaultObstacle('o1', SOUTH_10M);
    const arbreSansHauteur = withCrownDiameter(newEnvironmentObject('e1', 'arbre', SOUTH_10M), 4);
    expect(unifiedShadeEntries([], [plat], [arbreSansHauteur], ORIGIN, 6)).toEqual([]);
  });

  it('les trois familles se cumulent, chacune dans SON référentiel', () => {
    const cheminee = withHeight(defaultObstacle('o1', SOUTH_10M), 2); // sur le toit
    const arbre = withEnvHeight(withCrownDiameter(newEnvironmentObject('e1', 'arbre', SOUTH_10M), 4), 10); // au sol
    const entries = unifiedShadeEntries([tracee], [cheminee], [arbre], ORIGIN, 6);
    expect(entries).toHaveLength(3);
    // ombre tracée : 9 m au sol − 6 m de toit = 3 m utiles
    expect(entries[0].effHeightM).toBeCloseTo(3, 6);
    // obstacle de toiture : 2 m, tels quels
    expect(entries[1].effHeightM).toBe(2);
    // arbre : 10 m au sol − 6 m de toit = 4 m utiles
    expect(entries[2].effHeightM).toBeCloseTo(4, 6);
  });

  it('un objet d’environnement entièrement SOUS le toit est écarté (aucune ombre inventée)', () => {
    const buisson = withEnvHeight(withCrownDiameter(newEnvironmentObject('e1', 'arbre', SOUTH_10M), 2), 3);
    expect(unifiedShadeEntries([], [], [buisson], ORIGIN, 6)).toEqual([]);
  });
});

describe('CAL66 + CAL67 — la production et l’accès solaire SUIVENT réellement', () => {
  const prod = fallbackPerKwc();

  it('une cheminée HAUTE au sud masque des heures ; sans elle, la matrice est l’identité', () => {
    const sans = hourlyShadeFactors(LAT, unifiedShadeEntries([], [], [], ORIGIN, 6));
    expect(sans.flat().every((f) => f === 1)).toBe(true);

    const cheminee: Obstacle = withHeight(resizedObstacle(defaultObstacle('o1', SOUTH_4M), 3, 3), 8);
    const avec = hourlyShadeFactors(LAT, unifiedShadeEntries([], [cheminee], [], ORIGIN, 6));
    expect(avec.flat().some((f) => f < 1)).toBe(true);
  });

  it('un arbre voisin au sud dégrade l’accès solaire ; le retirer restaure EXACTEMENT 1', () => {
    const arbre = withEnvHeight(withCrownDiameter(newEnvironmentObject('e1', 'arbre', SOUTH_10M), 6), 14);
    const avec = pointSolarAccess(LAT, unifiedShadeEntries([], [], [arbre], ORIGIN, 6), prod, 0, 0);
    const sans = pointSolarAccess(LAT, unifiedShadeEntries([], [], [], ORIGIN, 6), prod, 0, 0);
    expect(avec).toBeLessThan(1);
    expect(sans).toBe(1);
  });

  it('une cheminée n’assombrit QUE ce qui est derrière elle : un point loin au nord reste dégagé', () => {
    const cheminee = withHeight(resizedObstacle(defaultObstacle('o1', SOUTH_4M), 3, 3), 8);
    const enu = unifiedShadeEntries([], [cheminee], [], ORIGIN, 6);
    // Point juste au nord de la cheminée (dans son ombre) vs point très à l'est (hors cône).
    const derriere = pointSolarAccess(LAT, enu, prod, 0, 0);
    const aCote = pointSolarAccess(LAT, enu, prod, 80, 0);
    expect(derriere).toBeLessThan(1);
    expect(aCote).toBeGreaterThan(derriere);
  });
});

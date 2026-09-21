// CAL60 — hauteur de bâtiment saisissable (repli AFFICHÉ comme hypothèse). Le calcul
// d'ombrage (hourlyShadeFactors, etc.) est déjà testé ailleurs (shadingWJ19.test.ts) ;
// ce fichier couvre uniquement la résolution PURE de la hauteur (le reste de
// `createShadingUi` a besoin d'une carte MapLibre + du DOM, hors de portée d'un test pur).
import { describe, expect, it } from 'vitest';
import {
  effectiveBuildingHeightM,
  heatmapAccessValues,
  HEATMAP_MONTH_LABELS,
  moduleShadeReading,
  moduleShadeReadingsForPanels,
  type ModuleShadeReading,
} from './shadingUi';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';
import { fallbackPerKwc } from '../../lib/productionEngine';
import { hourlyShadeFactors, type ShadeObstructionENU } from '../../lib/shadingEngine';

describe('CAL60 — effectiveBuildingHeightM', () => {
  it('sans saisie (null/undefined) : repli historique FLOORS × FLOOR_HEIGHT_M', () => {
    expect(effectiveBuildingHeightM(null)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(undefined)).toBe(FLOORS * FLOOR_HEIGHT_M);
  });

  it('une hauteur saisie finie et positive prime sur le repli', () => {
    expect(effectiveBuildingHeightM(9.5)).toBe(9.5);
    expect(effectiveBuildingHeightM(3)).toBe(3);
  });

  it('une saisie aberrante (0, négative, non finie) retombe sur le repli', () => {
    expect(effectiveBuildingHeightM(0)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(-2)).toBe(FLOORS * FLOOR_HEIGHT_M);
    expect(effectiveBuildingHeightM(NaN)).toBe(FLOORS * FLOOR_HEIGHT_M);
  });

  it('changer la hauteur change visiblement le résultat (valeurs distinctes)', () => {
    const a = effectiveBuildingHeightM(4);
    const b = effectiveBuildingHeightM(12);
    expect(a).not.toBe(b);
  });
});

// CAL95 — carte d'accès solaire : alimentée par la source unifiée (CAL94) et lisible PAR
// MOIS en plus de la lecture annuelle. Calcul PUR, testable sans DOM ni WebGL.
describe('CAL95 — heatmapAccessValues : toutes les obstructions, et par mois', () => {
  const LAT = 33.5;
  const prod = fallbackPerKwc();
  const panels = [
    { cx: 0, cy: 0 }, // juste au nord de la cheminée : dans son ombre
    { cx: 40, cy: 0 }, // 40 m à l'est : hors de son ombre
  ];
  /** Cheminée 3 × 3 m, 5 m de haut, 3 m au sud du premier module. */
  const cheminee: ShadeObstructionENU = {
    x: 0,
    y: -3,
    effHeightM: 5,
    halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [
      [-1.5, -4.5],
      [1.5, -4.5],
      [1.5, -1.5],
      [-1.5, -1.5],
    ],
  };

  it('sans obstruction : tout à 1, en annuel comme au mois (aucun dérate inventé)', () => {
    expect(heatmapAccessValues(LAT, [], prod, panels, null)).toEqual([1, 1]);
    expect(heatmapAccessValues(LAT, [], prod, panels, 11)).toEqual([1, 1]);
  });

  it('poser une cheminée à hauteur fait varier la carte, et seulement derrière elle', () => {
    const access = heatmapAccessValues(LAT, [cheminee], prod, panels, null);
    expect(access[0]).toBeLessThan(1);
    expect(access[1]).toBeGreaterThan(access[0]);
  });

  it('décembre est plus rouge que juin sur le même module (soleil bas, ombres longues)', () => {
    const decembre = heatmapAccessValues(LAT, [cheminee], prod, panels, 11)[0];
    const juin = heatmapAccessValues(LAT, [cheminee], prod, panels, 5)[0];
    expect(decembre).toBeLessThan(juin);
  });

  it('un mois hors bornes retombe sur « aucun dérate » plutôt que sur une valeur inventée', () => {
    expect(heatmapAccessValues(LAT, [cheminee], prod, panels, 12)).toEqual([1, 1]);
    expect(heatmapAccessValues(LAT, [cheminee], prod, panels, -1)).toEqual([1, 1]);
  });

  it('les douze mois sont nommés, dans l’ordre', () => {
    expect(HEATMAP_MONTH_LABELS).toHaveLength(12);
    expect(HEATMAP_MONTH_LABELS[0]).toBe('janvier');
    expect(HEATMAP_MONTH_LABELS[11]).toBe('décembre');
  });
});

// CALX122 — lecture géométrique d'ombrage PAR MODULE : nombre d'heures représentatives
// masquées (sur les 288 = 12 mois × 24 h de la matrice déjà calculée par
// `hourlyShadeFactors`) et le premier mois concerné. Aucun kWh : lecture géométrique pure,
// testable sans DOM ni production (les fonctions ne prennent même pas de profil PVGIS).
describe('CALX122 — lecture géométrique d’ombrage par module (heures + premier mois)', () => {
  const LAT = 33.5;
  /** Même cheminée que CAL95 ci-dessus (3 × 3 m, 5 m de haut, 3 m au sud du module) —
   *  déjà prouvée « obstruction effective » par le test CAL95 (`access[0]` < 1). */
  const cheminee: ShadeObstructionENU = {
    x: 0,
    y: -3,
    effHeightM: 5,
    halfWidthM: Math.hypot(3, 3) / 2,
    footprint: [
      [-1.5, -4.5],
      [1.5, -4.5],
      [1.5, -1.5],
      [-1.5, -1.5],
    ],
  };
  const panels = [
    { cx: 0, cy: 0 }, // juste au nord de la cheminée : dans son ombre
    { cx: 40, cy: 0 }, // 40 m à l'est : hors de son ombre
  ];

  it('sans AUCUNE source d’ombrage saisie (hasSource=false) : la lecture est ABSENTE (null), jamais « 0 heure »', () => {
    expect(moduleShadeReadingsForPanels(LAT, [cheminee], panels, false)).toBeNull();
    expect(moduleShadeReadingsForPanels(LAT, [], panels, false)).toBeNull();
  });

  it('une source saisie mais sans obstruction effective (enu vide) publie un VRAI zéro, jamais une omission', () => {
    const readings = moduleShadeReadingsForPanels(LAT, [], panels, true);
    expect(readings).toEqual([
      { maskedHours: 0, firstMonthIndex: null },
      { maskedHours: 0, firstMonthIndex: null },
    ]);
  });

  it('une obstruction saisie ⇒ le compte d’heures suit EXACTEMENT la matrice 12×24 existante', () => {
    const reading = moduleShadeReading(LAT, [cheminee], 0, 0);
    // Recalcul indépendant depuis la matrice déjà testée ailleurs (shadingWJ19.test.ts) :
    // la lecture géométrique ne doit rien inventer de plus que ce que hourlyShadeFactors dit.
    const matrix = hourlyShadeFactors(LAT, [cheminee], 0, 0);
    let expectedHours = 0;
    let expectedFirstMonth: number | null = null;
    matrix.forEach((row, m) => {
      const maskedInMonth = row.filter((v) => v < 1).length;
      if (maskedInMonth > 0) {
        expectedHours += maskedInMonth;
        if (expectedFirstMonth == null) expectedFirstMonth = m;
      }
    });
    expect(reading.maskedHours).toBe(expectedHours);
    expect(reading.firstMonthIndex).toBe(expectedFirstMonth);
    expect(reading.maskedHours).toBeGreaterThan(0);
  });

  it('le module plus loin (40 m à l’est) est nettement moins masqué — toujours depuis SA PROPRE matrice, jamais un chiffre par défaut', () => {
    const far = moduleShadeReading(LAT, [cheminee], 40, 0);
    const matrixFar = hourlyShadeFactors(LAT, [cheminee], 40, 0);
    let expectedFarHours = 0;
    matrixFar.forEach((row) => {
      for (const v of row) if (v < 1) expectedFarHours++;
    });
    expect(far.maskedHours).toBe(expectedFarHours);
    const near = moduleShadeReading(LAT, [cheminee], 0, 0);
    expect(far.maskedHours).toBeLessThan(near.maskedHours);
  });

  it('moduleShadeReadingsForPanels aligne un résultat par panneau, dans l’ordre (le plus proche masqué au moins autant que le plus loin)', () => {
    const readings = moduleShadeReadingsForPanels(LAT, [cheminee], panels, true) as ModuleShadeReading[];
    expect(readings).toHaveLength(2);
    expect(readings[0].maskedHours).toBeGreaterThan(0);
    expect(readings[0].firstMonthIndex).not.toBeNull();
    expect(readings[1].maskedHours).toBeLessThanOrEqual(readings[0].maskedHours);
    expect(readings[1].firstMonthIndex == null || typeof readings[1].firstMonthIndex === 'number').toBe(true);
  });
});

// CAL60 — hauteur de bâtiment saisissable (repli AFFICHÉ comme hypothèse). Le calcul
// d'ombrage (hourlyShadeFactors, etc.) est déjà testé ailleurs (shadingWJ19.test.ts) ;
// ce fichier couvre uniquement la résolution PURE de la hauteur (le reste de
// `createShadingUi` a besoin d'une carte MapLibre + du DOM, hors de portée d'un test pur).
import { describe, expect, it } from 'vitest';
import { effectiveBuildingHeightM } from './shadingUi';
import { FLOORS, FLOOR_HEIGHT_M } from './constants';

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

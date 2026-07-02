// WJ19 — moteur d'ombrage pur : hauteur déduite d'une ombre tracée (h = L·tan α),
// masquage angulaire du soleil par une obstruction, matrice horaire de dérate et
// application aux profils PVGIS (cohérence jour → mois → an, jamais de production
// gonflée). Le module est PUR : ces tests tournent hors DOM et hors réseau.
import { describe, expect, it } from 'vitest';
import {
  IMAGERY_SUN_DEFAULT,
  DIFFUSE_FRACTION_WHEN_SHADED,
  MID_MONTH_DAY_OF_YEAR,
  shadowVector,
  obstructionHeightFromShadow,
  shadeObstructionsENU,
  isSunBlocked,
  hourlyShadeFactors,
  applyShadeFactors,
  annualShadeFactor,
  type ShadeObstruction,
  type ShadeObstructionENU,
} from '../src/lib/shadingEngine';
import { sunDirection } from '../src/lib/roofPro2';
import { fallbackPerKwc, DAYS_IN_MONTH } from '../src/lib/productionEngine';

const CASA_LAT = 33.57;

describe('WJ19 — géométrie de l’ombre tracée', () => {
  it('shadowVector : longueur et azimut d’un tracé vers le nord', () => {
    // ~11,1 m vers le nord (0,0001° de latitude ≈ 11,13 m).
    const v = shadowVector([-7.6, 33.57], [-7.6, 33.5701]);
    expect(v.lengthM).toBeCloseTo(11.13, 1);
    expect(v.azimuthDeg).toBeCloseTo(0, 5);
  });

  it('obstructionHeightFromShadow : h = L·tan(α) — soleil à 45° → h = L', () => {
    expect(obstructionHeightFromShadow(10, 45)).toBeCloseTo(10, 6);
    expect(obstructionHeightFromShadow(12, 30)).toBeCloseTo(12 * Math.tan((30 * Math.PI) / 180), 6);
  });

  it('refuse de déduire une hauteur sans donnée exploitable (pas de précision inventée)', () => {
    expect(obstructionHeightFromShadow(0, 45)).toBeNull();
    expect(obstructionHeightFromShadow(-3, 45)).toBeNull();
    expect(obstructionHeightFromShadow(10, 0)).toBeNull(); // soleil rasant : tangente explosive
    expect(obstructionHeightFromShadow(10, 2.9)).toBeNull();
  });

  it('l’hypothèse par défaut de prise de vue est documentée (10 h 30 solaire, mi-saison)', () => {
    expect(IMAGERY_SUN_DEFAULT.solarHour).toBe(10.5);
    expect(IMAGERY_SUN_DEFAULT.dayOfYear).toBe(80);
    // Le soleil de l'hypothèse par défaut est haut et exploitable à Casablanca.
    const sun = sunDirection(CASA_LAT, IMAGERY_SUN_DEFAULT.dayOfYear, IMAGERY_SUN_DEFAULT.solarHour);
    expect(sun.elevationDeg).toBeGreaterThan(30);
  });

  it('shadeObstructionsENU retire la hauteur de toit et écarte ce qui reste sous le plan', () => {
    const list: ShadeObstruction[] = [
      { id: 'a', base: [-7.6, 33.57], tip: [-7.6, 33.5701], heightM: 10, halfWidthM: 3 },
      { id: 'b', base: [-7.6, 33.57], tip: [-7.6, 33.5701], heightM: 5, halfWidthM: 3 }, // sous le toit (6 m)
    ];
    const enu = shadeObstructionsENU(list, [-7.6, 33.57], 6);
    expect(enu.length).toBe(1);
    expect(enu[0].effHeightM).toBeCloseTo(4, 6);
    expect(enu[0].x).toBeCloseTo(0, 3);
    expect(enu[0].y).toBeCloseTo(0, 3);
  });
});

describe('WJ19 — masquage angulaire du soleil', () => {
  // Obstruction effective de 10 m à 10 m PLEIN SUD du point (azimut 180°).
  const southObs: ShadeObstructionENU[] = [{ x: 0, y: -10, effHeightM: 10, halfWidthM: 3 }];

  it('masque un soleil bas dans son azimut, laisse passer un soleil plus haut', () => {
    // Sommet vu à atan(10/10) = 45° d'élévation, plein sud.
    expect(isSunBlocked(0, 0, southObs, 30, 180)).toBe(true);
    expect(isSunBlocked(0, 0, southObs, 60, 180)).toBe(false);
  });

  it('ne masque pas hors de son cône azimutal', () => {
    // Demi-largeur angulaire = atan(3/10) ≈ 16,7° : à 90° (est) le soleil passe.
    expect(isSunBlocked(0, 0, southObs, 30, 90)).toBe(false);
    expect(isSunBlocked(0, 0, southObs, 30, 180 + 10)).toBe(true); // dans le cône
    expect(isSunBlocked(0, 0, southObs, 30, 180 + 30)).toBe(false); // hors cône
  });

  it('nuit (élévation ≤ 0) : jamais « masqué »', () => {
    expect(isSunBlocked(0, 0, southObs, -5, 180)).toBe(false);
  });
});

describe('WJ19 — matrice horaire de dérate + application aux profils PVGIS', () => {
  it('sans obstruction : matrice identité (12 × 24 de 1)', () => {
    const f = hourlyShadeFactors(CASA_LAT, []);
    expect(f.length).toBe(12);
    for (const row of f) {
      expect(row.length).toBe(24);
      for (const v of row) expect(v).toBe(1);
    }
  });

  it('un mur au sud masque des heures d’hiver (soleil bas) plus que d’été', () => {
    // Obstruction effective massive plein sud : 12 m de haut à 8 m, large (10 m).
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -8, effHeightM: 12, halfWidthM: 10 }];
    const f = hourlyShadeFactors(CASA_LAT, obs);
    const shadedHours = (m: number) => f[m].filter((v) => v < 1).length;
    // Décembre (index 11) : midi d'hiver ~33° < atan(12/8) ≈ 56° → masqué.
    expect(shadedHours(11)).toBeGreaterThan(0);
    // L'hiver est plus masqué que juin (soleil d'été bien plus haut à midi).
    expect(shadedHours(11)).toBeGreaterThanOrEqual(shadedHours(5));
    // Une heure masquée conserve exactement la part diffuse.
    const shaded = f[11].find((v) => v < 1);
    expect(shaded).toBe(DIFFUSE_FRACTION_WHEN_SHADED);
  });

  it('applyShadeFactors : totaux re-intégrés cohérents, jamais de production gonflée', () => {
    const prod = fallbackPerKwc(1600);
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -8, effHeightM: 12, halfWidthM: 10 }];
    const f = hourlyShadeFactors(CASA_LAT, obs);
    const derated = applyShadeFactors(prod, f);
    // Jamais plus qu'avant, jamais moins que la part diffuse.
    expect(derated.annualKwh).toBeLessThan(prod.annualKwh);
    expect(derated.annualKwh).toBeGreaterThanOrEqual(prod.annualKwh * DIFFUSE_FRACTION_WHEN_SHADED);
    // Cohérence jour → mois → an.
    for (let m = 0; m < 12; m++) {
      const daily = derated.typicalDayByMonth[m].reduce((a, b) => a + b, 0);
      expect(derated.dailyKwhByMonth[m]).toBeCloseTo(daily, 9);
      expect(derated.monthlyKwh[m]).toBeCloseTo(daily * DAYS_IN_MONTH[m], 9);
    }
    expect(derated.annualKwh).toBeCloseTo(derated.monthlyKwh.reduce((a, b) => a + b, 0), 9);
    // L'original n'est pas muté.
    expect(prod.annualKwh).toBeCloseTo(1600, 6);
  });

  it('facteurs identité → production inchangée ; annualShadeFactor ∈ (0, 1]', () => {
    const prod = fallbackPerKwc(1600);
    const same = applyShadeFactors(prod, hourlyShadeFactors(CASA_LAT, []));
    expect(same.annualKwh).toBeCloseTo(prod.annualKwh, 9);
    expect(annualShadeFactor(prod, null)).toBe(1);
    const obs: ShadeObstructionENU[] = [{ x: 0, y: -8, effHeightM: 12, halfWidthM: 10 }];
    const f = annualShadeFactor(prod, hourlyShadeFactors(CASA_LAT, obs));
    expect(f).toBeGreaterThan(0);
    expect(f).toBeLessThan(1);
  });

  it('les jours représentatifs mensuels couvrent bien l’année', () => {
    expect(MID_MONTH_DAY_OF_YEAR.length).toBe(12);
    expect(MID_MONTH_DAY_OF_YEAR[0]).toBe(15);
    expect(MID_MONTH_DAY_OF_YEAR[11]).toBeGreaterThan(340);
  });
});

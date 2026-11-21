// CAL93 — le moteur PUR de l'horizon lointain : interpolation, matrice 12×24, heures
// masquées. Même discipline que setbacksPV63.test.ts : un profil absent/insuffisant ne
// dérate RIEN (comportement historique), jamais un horizon plat inventé.
import { describe, expect, it } from 'vitest';
import {
  sortedHorizonPoints,
  horizonHeightAtAzimuth,
  horizonMaxHeightDeg,
  hourlyHorizonFactors,
  maskedHourCount,
  HORIZON_KEPT_BY_ELEVATION,
  type HorizonPoint,
} from '../src/lib/horizonEngine';
import { DIFFUSE_FRACTION_WHEN_SHADED, annualShadeFactor } from '../src/lib/shadingEngine';
import { fallbackPerKwc } from '../src/lib/productionEngine';

const LAT_CASA = 33.5731;

describe('CAL93 — sortedHorizonPoints', () => {
  it('trie par azimut croissant, normalise 0–360, écarte les points non finis', () => {
    const points: HorizonPoint[] = [
      { azimuthDeg: 200, heightDeg: 5 },
      { azimuthDeg: -10, heightDeg: 2 }, // → 350
      { azimuthDeg: 90, heightDeg: 8 },
      { azimuthDeg: Number.NaN, heightDeg: 9 },
    ];
    const sorted = sortedHorizonPoints(points);
    expect(sorted.map((p) => p.azimuthDeg)).toEqual([90, 200, 350]);
  });
});

describe('CAL93 — horizonHeightAtAzimuth (interpolation circulaire)', () => {
  const points: HorizonPoint[] = [
    { azimuthDeg: 0, heightDeg: 2 },
    { azimuthDeg: 90, heightDeg: 10 },
    { azimuthDeg: 180, heightDeg: 4 },
    { azimuthDeg: 270, heightDeg: 0 },
  ];

  it('un point EXACT renvoie sa hauteur telle quelle', () => {
    expect(horizonHeightAtAzimuth(points, 90)).toBe(10);
  });

  it('interpole LINÉAIREMENT entre deux points encadrants', () => {
    expect(horizonHeightAtAzimuth(points, 45)).toBeCloseTo(6, 10); // milieu 0→90 : 2→10
  });

  it('boucle CIRCULAIREMENT entre le dernier et le premier point (270 → 360=0)', () => {
    // 270=0, 0(=360)=2 : à 315°, mi-chemin → 1
    expect(horizonHeightAtAzimuth(points, 315)).toBeCloseTo(1, 10);
  });

  it('moins de deux points exploitables → null (aucun horizon plat inventé)', () => {
    expect(horizonHeightAtAzimuth([], 90)).toBeNull();
    expect(horizonHeightAtAzimuth([{ azimuthDeg: 10, heightDeg: 5 }], 90)).toBe(5);
  });
});

describe('CAL93 — horizonMaxHeightDeg', () => {
  it('la hauteur maximale RÉELLE du profil, jamais recalculée ailleurs', () => {
    expect(horizonMaxHeightDeg([{ azimuthDeg: 0, heightDeg: 2 }, { azimuthDeg: 90, heightDeg: 10 }])).toBe(10);
  });
  it('profil vide → null', () => {
    expect(horizonMaxHeightDeg([])).toBeNull();
  });
});

describe('CAL93 — hourlyHorizonFactors (matrice 12×24)', () => {
  it('profil absent ou < 2 points → null (chiffres inchangés)', () => {
    expect(hourlyHorizonFactors(LAT_CASA, null)).toBeNull();
    expect(hourlyHorizonFactors(LAT_CASA, [{ azimuthDeg: 180, heightDeg: 5 }])).toBeNull();
  });

  it('horizon TRÈS HAUT partout (60°) masque de nombreuses heures de jour, jamais la nuit', () => {
    const wall: HorizonPoint[] = [
      { azimuthDeg: 0, heightDeg: 60 },
      { azimuthDeg: 90, heightDeg: 60 },
      { azimuthDeg: 180, heightDeg: 60 },
      { azimuthDeg: 270, heightDeg: 60 },
    ];
    const factors = hourlyHorizonFactors(LAT_CASA, wall);
    expect(factors).not.toBeNull();
    expect(maskedHourCount(factors)).toBeGreaterThan(0);
    // ACAL378 — chaque heure masquée retombe EXACTEMENT sur une part diffuse + réfléchie
    // mesurée (tranche de hauteur du soleil), jamais sous la part diffuse plancher, jamais 1.
    const parts = HORIZON_KEPT_BY_ELEVATION.map(([, v]) => Math.max(DIFFUSE_FRACTION_WHEN_SHADED, v));
    for (const row of factors!) {
      for (const v of row) {
        expect(v === 1 || parts.some((p) => Math.abs(v - p) < 1e-9)).toBe(true);
      }
    }
  });

  it('horizon plat à 0° partout → aucune heure masquée (identique à sans profil)', () => {
    const flat: HorizonPoint[] = [
      { azimuthDeg: 0, heightDeg: 0 },
      { azimuthDeg: 120, heightDeg: 0 },
      { azimuthDeg: 240, heightDeg: 0 },
    ];
    const factors = hourlyHorizonFactors(LAT_CASA, flat);
    expect(maskedHourCount(factors)).toBe(0);
  });
});

describe('ACAL378 — horizon lointain : même dérate que la simulation serveur (PVGIS)', () => {
  // Référence : rejeu PA2.5 du 19/11/2026 sur runner (run 44632020473), même calepinage (toit
  // plat 15° plein sud, Casablanca), horizon 25° sur 8 directions — trace
  // docs/audits/acceptation/ACAL/traces/2026-11-19/PA2.5-ACAL356-mesure.txt :
  // atelier 8846.29 → 7208.99 (× 0,815), simulation serveur PVGIS 12032.1 → 11066.6 (× 0,920).
  const ATELIER_AVANT = 8846.288372093024;
  const SIMULATION_AVANT = 12032.1;
  const SIMULATION_APRES = 11066.6;
  const RAPPORT_PVGIS = SIMULATION_APRES / SIMULATION_AVANT;
  const huitDirections: HorizonPoint[] = [0, 45, 90, 135, 180, 225, 270, 315].map((azimuthDeg) => ({
    azimuthDeg,
    heightDeg: 25,
  }));

  it('horizon 25° sur 8 directions : rapport annuel ≈ celui de PVGIS sur le même profil', () => {
    // Même chaîne que shadingUi.recomputeHorizonFactors sur le runner (jour-type de repli).
    const prod = fallbackPerKwc();
    const rapport = annualShadeFactor(prod, hourlyHorizonFactors(LAT_CASA, huitDirections, undefined, prod));
    expect(Math.abs(rapport - RAPPORT_PVGIS)).toBeLessThan(0.02);
    // L'écart atelier ↔ simulation après horizon n'est pas plus grand qu'avant.
    const ecartAvant = (SIMULATION_AVANT - ATELIER_AVANT) / SIMULATION_AVANT;
    const ecartApres = (SIMULATION_APRES - ATELIER_AVANT * rapport) / SIMULATION_APRES;
    expect(ecartApres).toBeLessThanOrEqual(ecartAvant);
  });

  it('la répartition mensuelle ne change pas les heures masquées (compte affiché identique)', () => {
    const prod = fallbackPerKwc();
    const sans = hourlyHorizonFactors(LAT_CASA, huitDirections);
    const avec = hourlyHorizonFactors(LAT_CASA, huitDirections, undefined, prod);
    expect(maskedHourCount(avec)).toBe(maskedHourCount(sans));
    expect(maskedHourCount(sans)).toBeGreaterThan(0);
  });
});

describe('CAL93 — maskedHourCount', () => {
  it('compte les cases < 1 sur la matrice EFFECTIVEMENT appliquée', () => {
    expect(maskedHourCount(null)).toBe(0);
    expect(maskedHourCount([[1, 1, 0.25], [1, 1, 1]])).toBe(1);
  });
});

// ACAL517 — la provenance « relevé téléphone » survit à l'aller-retour du document.
import { serializeHorizonProfile, deserializeHorizonProfileFromLayout } from '../src/lib/horizonEngine';

describe('ACAL517 — releve : serializeHorizonProfile ↔ deserializeHorizonProfileFromLayout', () => {
  const points: HorizonPoint[] = [
    { azimuthDeg: 0, heightDeg: 3 },
    { azimuthDeg: 120, heightDeg: 8 },
    { azimuthDeg: 240, heightDeg: 5 },
  ];
  const releve = { mode: 'telephone' as const, date: '2026-11-21', precisionDeg: 5 };

  it('`releve` survit à l’aller-retour', () => {
    const emis = serializeHorizonProfile({ source: 'saisie', points, hauteurMaxDeg: 8, releve });
    const relu = deserializeHorizonProfileFromLayout({ horizonProfile: JSON.parse(JSON.stringify(emis)) });
    expect(relu?.releve).toEqual(releve);
    expect(relu?.source).toBe('saisie');
  });

  it('sans `releve` : aucune clé ; un `releve` non conforme est écarté', () => {
    expect('releve' in serializeHorizonProfile({ source: 'saisie', points, hauteurMaxDeg: 8 })).toBe(false);
    for (const faux of [{ ...releve, mode: 'gps' }, { ...releve, date: 'hier' }, { ...releve, precisionDeg: 0 }]) {
      const relu = deserializeHorizonProfileFromLayout({ horizonProfile: { source: 'saisie', points, releve: faux } });
      expect(relu && 'releve' in relu).toBe(false);
    }
  });
});

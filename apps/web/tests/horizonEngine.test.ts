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
  type HorizonPoint,
} from '../src/lib/horizonEngine';
import { DIFFUSE_FRACTION_WHEN_SHADED } from '../src/lib/shadingEngine';

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
    // Chaque heure masquée retombe EXACTEMENT sur la part diffuse (jamais 0, jamais >1).
    for (const row of factors!) {
      for (const v of row) {
        expect(v === 1 || Math.abs(v - DIFFUSE_FRACTION_WHEN_SHADED) < 1e-9).toBe(true);
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

describe('CAL93 — maskedHourCount', () => {
  it('compte les cases < 1 sur la matrice EFFECTIVEMENT appliquée', () => {
    expect(maskedHourCount(null)).toBe(0);
    expect(maskedHourCount([[1, 1, 0.25], [1, 1, 1]])).toBe(1);
  });
});

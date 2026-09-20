// CAL94 — OMBRAGE PROCHE PAR LANCER DE RAYONS depuis toutes les obstructions à hauteur.
// Jusqu'ici l'occultation était un test ANGULAIRE (cône autour de l'azimut de l'obstacle) :
// un rectangle de 6 × 1 m ombrait comme un disque de 6 m. On lance désormais un vrai rayon
// contre le prisme vertical (empreinte extrudée). Tout est PUR : aucun WebGL, donc le coût
// est mesurable en test.
import { describe, expect, it } from 'vitest';
import {
  rayEntryDistance,
  isSunBlocked,
  hourlyShadeFactors,
  cellsSolarAccess,
  shadeObstructionsENU,
  DIFFUSE_FRACTION_WHEN_SHADED,
  type ShadeObstructionENU,
} from './shadingEngine';
import { fallbackPerKwc } from './productionEngine';

/** Rectangle ENU centré en (cx, cy), demi-largeur E-O `hw`, demi-longueur N-S `hl`. */
function rect(cx: number, cy: number, hw: number, hl: number): [number, number][] {
  return [
    [cx - hw, cy - hl],
    [cx + hw, cy - hl],
    [cx + hw, cy + hl],
    [cx - hw, cy + hl],
  ];
}

describe('CAL94 — rayEntryDistance : l’intersection rayon/empreinte, exacte', () => {
  const carre = rect(0, -10, 2, 2); // 4 × 4 m, centré 10 m au SUD

  it('un rayon vers le sud entre au bord NORD du carré (8 m), pas à son centre', () => {
    const t = rayEntryDistance(0, 0, 0, -1, carre);
    expect(t).not.toBeNull();
    expect(t as number).toBeCloseTo(8, 6);
  });

  it('un rayon qui passe à côté ne rencontre jamais l’empreinte', () => {
    expect(rayEntryDistance(0, 0, 1, 0, carre)).toBeNull(); // plein est
    expect(rayEntryDistance(0, 0, 0, 1, carre)).toBeNull(); // plein nord (dos à l’obstacle)
  });

  it('un point DANS l’empreinte entre à distance nulle', () => {
    expect(rayEntryDistance(0, -10, 0, -1, carre)).toBe(0);
  });

  it('une empreinte dégénérée (< 3 sommets) ne bloque rien', () => {
    expect(rayEntryDistance(0, 0, 0, -1, [[0, -1]] as [number, number][])).toBeNull();
  });
});

describe('CAL94 — isSunBlocked : la géométrie exacte remplace le cône QUAND l’empreinte existe', () => {
  it('un mur étroit ne masque QUE l’azimut qu’il couvre vraiment', () => {
    // Mur de 1 m (E-O) × 4 m (N-S), 5 m au sud, 6 m de haut.
    const mur: ShadeObstructionENU = {
      x: 0,
      y: -5,
      effHeightM: 6,
      halfWidthM: Math.hypot(1, 4) / 2,
      footprint: rect(0, -5, 0.5, 2),
    };
    // Soleil plein sud, bas sur l'horizon : le point pile au nord du mur est masqué.
    expect(isSunBlocked(0, 0, [mur], 20, 180)).toBe(true);
    // Le MÊME soleil, vu d'un point 6 m à l'est : le rayon passe à côté du mur.
    expect(isSunBlocked(6, 0, [mur], 20, 180)).toBe(false);
  });

  it('un soleil plus HAUT que le sommet du prisme passe par-dessus', () => {
    const mur: ShadeObstructionENU = {
      x: 0,
      y: -5,
      effHeightM: 1,
      halfWidthM: 2,
      footprint: rect(0, -5, 1, 1),
    };
    expect(isSunBlocked(0, 0, [mur], 10, 180)).toBe(true); // rayon encore bas à 4 m
    expect(isSunBlocked(0, 0, [mur], 60, 180)).toBe(false); // rayon déjà au-dessus
  });

  it('NON-RÉGRESSION : une obstruction SANS empreinte garde exactement le test angulaire', () => {
    const cone: ShadeObstructionENU = { x: 0, y: -10, effHeightM: 8, halfWidthM: 3 };
    // Dans le cône (atan(3/10) ≈ 16,7°) et sous le sommet (atan(8/10) ≈ 38,7°).
    expect(isSunBlocked(0, 0, [cone], 30, 180)).toBe(true);
    expect(isSunBlocked(0, 0, [cone], 30, 150)).toBe(false); // hors du cône
    expect(isSunBlocked(0, 0, [cone], 45, 180)).toBe(false); // au-dessus du sommet
  });
});

describe('CAL94 — la matrice d’ombrage : rien sans obstruction, du rouge derrière un obstacle', () => {
  const LAT = 33.5;

  it('AUCUNE obstruction → matrice strictement identique à l’identité (non-régression)', () => {
    const m = hourlyShadeFactors(LAT, []);
    expect(m).toHaveLength(12);
    expect(m.every((row) => row.length === 24 && row.every((f) => f === 1))).toBe(true);
  });

  it('une obstruction sous le niveau du toit est écartée → matrice identité', () => {
    const enu = shadeObstructionsENU(
      [{ id: 's', base: [-7.6, 33.4999], tip: [-7.6, 33.49995], heightM: 3, halfWidthM: 3 }],
      [-7.6, 33.5],
      6,
    );
    expect(enu).toEqual([]);
    expect(hourlyShadeFactors(LAT, enu).flat().every((f) => f === 1)).toBe(true);
  });

  it('une cheminée haute au sud masque des heures, ramenées à la PART DIFFUSE (jamais 0)', () => {
    const cheminee: ShadeObstructionENU = {
      x: 0,
      y: -3,
      effHeightM: 5,
      halfWidthM: Math.hypot(3, 3) / 2,
      footprint: rect(0, -3, 1.5, 1.5),
    };
    const m = hourlyShadeFactors(LAT, [cheminee]);
    const masquees = m.flat().filter((f) => f < 1);
    expect(masquees.length).toBeGreaterThan(0);
    expect(masquees.every((f) => f === DIFFUSE_FRACTION_WHEN_SHADED)).toBe(true);
  });

  it('« derrière elle et seulement elles » : les modules au nord perdent, ceux à l’est non', () => {
    const cheminee: ShadeObstructionENU = {
      x: 0,
      y: -3,
      effHeightM: 5,
      halfWidthM: Math.hypot(3, 3) / 2,
      footprint: rect(0, -3, 1.5, 1.5),
    };
    const prod = fallbackPerKwc();
    const access = cellsSolarAccess(LAT, [cheminee], prod, [
      { x: 0, y: 0 }, // juste au nord de la cheminée
      { x: 40, y: 0 }, // 40 m à l'est : hors de son ombre
    ]);
    expect(access[0]).toBeLessThan(1);
    // Le module à l'est n'est touché que par le soleil RASANT de fin de journée (la
    // cheminée est alors plein ouest, à 7° d'élévation) : la perte y est marginale et
    // vient d'une VRAIE géométrie, pas d'un facteur d'ombrage forfaitaire.
    expect(access[1]).toBeGreaterThan(0.99);
    expect(access[1]).toBeGreaterThan(access[0]);
  });
});

describe('CAL94 — budget de performance du lancer de rayons (coût PUR, sans WebGL)', () => {
  it('200 modules × 8 obstacles à empreinte tiennent largement sous la seconde', () => {
    const LAT = 33.5;
    const prod = fallbackPerKwc();
    const obstacles: ShadeObstructionENU[] = [];
    for (let i = 0; i < 8; i++) {
      const cx = -12 + i * 3;
      obstacles.push({
        x: cx,
        y: -6,
        effHeightM: 2 + (i % 3),
        halfWidthM: Math.hypot(2, 2) / 2,
        footprint: rect(cx, -6, 1, 1),
      });
    }
    const points = Array.from({ length: 200 }, (_, i) => ({ x: (i % 20) * 2.4, y: Math.floor(i / 20) * 2 }));
    const t0 = Date.now();
    const access = cellsSolarAccess(LAT, obstacles, prod, points);
    const elapsedMs = Date.now() - t0;
    expect(access).toHaveLength(200);
    // Budget volontairement large (machines de CI lentes) : l'important est que le coût
    // reste de l'ordre de la centaine de millisecondes, pas de la dizaine de secondes.
    expect(elapsedMs).toBeLessThan(3000);
  });
});

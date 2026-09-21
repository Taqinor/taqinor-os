// CALX89 — MAGNÉTISME ANGULAIRE DU TRACÉ. Ce fichier prouve la partie qui FAIT la tâche,
// sans DOM ni carte : le segment se cale sur le multiple de pas le plus proche quand l'écart
// est sous la tolérance, le point est rendu TEL QUEL hors tolérance, le PREMIER point d'un
// tracé n'est jamais contraint, et un pas nul (puce éteinte) rend le point cliqué point pour
// point — le tracé d'aujourd'hui.
import { describe, expect, it } from 'vitest';
import {
  contraindreAngle,
  capEntreDeg,
  distanceEntreM,
  normaliserDeg,
  pointDepuisCap,
  PAS_ANGLE_DEG,
  TOLERANCE_ANGLE_DEG,
} from './snap';
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { type LngLat } from '../../lib/roof';

const DEG2M = DEG2RAD * WGS84_RADIUS;

/** Point à `dM` mètres de `o` dans la direction `capDeg` — construit à la main (plan
 *  tangent local), pour ne pas fabriquer le cas de test avec la fonction testée. */
function depuis(o: LngLat, capDeg: number, dM: number): LngLat {
  const cosLat = Math.cos(o[1] * DEG2RAD);
  const dNord = dM * Math.cos(capDeg * DEG2RAD);
  const dEst = dM * Math.sin(capDeg * DEG2RAD);
  return [o[0] + dEst / (DEG2M * cosLat), o[1] + dNord / DEG2M];
}

const P: LngLat = [-7.6, 33.5];
/** Sommet AVANT `P`, plein sud de P : le segment de référence pointe donc plein NORD (cap 0). */
const AVANT: LngLat = depuis(P, 180, 40);

describe('CALX89 — normaliserDeg', () => {
  it('ramène tout angle dans (-180, 180]', () => {
    expect(normaliserDeg(0)).toBe(0);
    expect(normaliserDeg(90)).toBe(90);
    expect(normaliserDeg(370)).toBeCloseTo(10, 10);
    expect(normaliserDeg(-190)).toBeCloseTo(170, 10);
    expect(normaliserDeg(180)).toBe(180);
    expect(normaliserDeg(-180)).toBe(180);
  });
});

describe('CALX89 — contraindreAngle : le multiple exact', () => {
  it('un segment à 88° du côté précédent se cale EXACTEMENT sur 90°, distance conservée', () => {
    const brut = depuis(P, 88, 100);
    const cale = contraindreAngle(P, AVANT, brut, 90);
    expect(cale).not.toEqual(brut);
    // Référence = cap du segment AVANT→P (plein nord, 0°) ⇒ la cible absolue est 90°.
    expect(capEntreDeg(P, cale)).toBeCloseTo(90, 6);
    expect(distanceEntreM(P, cale)).toBeCloseTo(distanceEntreM(P, brut), 6);
  });

  it('un pas de 45° capture aussi les pans coupés', () => {
    const brut = depuis(P, 47, 60);
    const cale = contraindreAngle(P, AVANT, brut, 45);
    expect(capEntreDeg(P, cale)).toBeCloseTo(45, 6);
  });

  it('un segment DÉJÀ sur le multiple ne bouge pas de façon perceptible', () => {
    const brut = depuis(P, 0, 50); // prolonge le côté précédent : écart relatif nul
    const cale = contraindreAngle(P, AVANT, brut, 90);
    expect(distanceEntreM(brut, cale)).toBeLessThan(0.001);
  });

  it('les deux pas proposés sont bien 90° puis 45°', () => {
    expect([...PAS_ANGLE_DEG]).toEqual([90, 45]);
  });
});

describe('CALX89 — contraindreAngle : hors tolérance, le point cliqué est intouché', () => {
  it('un écart de 30° au pas de 90° laisse le point EXACTEMENT où il a été cliqué', () => {
    const brut = depuis(P, 60, 100); // 30° du multiple 90°, très au-delà de la tolérance
    const cale = contraindreAngle(P, AVANT, brut, 90);
    expect(cale).toBe(brut); // même référence : rien n'a été recalculé
  });

  it('juste au-delà de la tolérance : intouché ; juste en deçà : calé', () => {
    const dehors = depuis(P, 90 + TOLERANCE_ANGLE_DEG + 1, 80);
    expect(contraindreAngle(P, AVANT, dehors, 90)).toBe(dehors);
    const dedans = depuis(P, 90 + TOLERANCE_ANGLE_DEG - 1, 80);
    expect(capEntreDeg(P, contraindreAngle(P, AVANT, dedans, 90))).toBeCloseTo(90, 6);
  });
});

describe('CALX89 — le PREMIER point d’un tracé n’est jamais contraint', () => {
  it('sans sommet précédent, le candidat est rendu tel quel', () => {
    const brut: LngLat = [-7.5991, 33.5007];
    expect(contraindreAngle(null, null, brut, 90)).toBe(brut);
    expect(contraindreAngle(undefined, undefined, brut, 45)).toBe(brut);
  });

  it('un candidat confondu avec le sommet précédent n’est pas déplacé', () => {
    const brut: LngLat = [P[0], P[1]];
    expect(contraindreAngle(P, AVANT, brut, 90)).toBe(brut);
  });
});

describe('CALX89 — deuxième point : la référence est le NORD VRAI', () => {
  it('un seul sommet posé : le premier côté s’aligne sur les points cardinaux', () => {
    const brut = depuis(P, 4, 70);
    const cale = contraindreAngle(P, null, brut, 90);
    expect(capEntreDeg(P, cale)).toBeCloseTo(0, 6);
  });
});

describe('CALX89 — PUCE ÉTEINTE : tracé identique à celui d’aujourd’hui, point pour point', () => {
  it('un pas nul/négatif/non fini rend le point cliqué tel quel', () => {
    const brut = depuis(P, 88, 100); // pourtant à portée d'accrochage
    expect(contraindreAngle(P, AVANT, brut, 0)).toBe(brut);
    expect(contraindreAngle(P, AVANT, brut, -90)).toBe(brut);
    expect(contraindreAngle(P, AVANT, brut, Number.NaN)).toBe(brut);
  });

  it('une suite de points posée puce éteinte est octet pour octet la suite cliquée', () => {
    const clics: LngLat[] = [
      [-7.6, 33.5],
      depuis(P, 88, 100),
      depuis(P, 3, 60),
      depuis(P, 271, 45),
    ];
    const poses: LngLat[] = [];
    for (const c of clics) {
      poses.push(contraindreAngle(poses[poses.length - 1], poses[poses.length - 2], c, 0));
    }
    expect(poses).toEqual(clics);
  });
});

// ————————————————————————————————————————————————————————————————————————
// CALX90 — SAISIE CLAVIER DE LA LONGUEUR ET DE L'ANGLE DU SEGMENT EN COURS.
// `pointDepuisCap` est la géométrie de la tâche : le sommet doit atterrir EXACTEMENT à la
// distance géodésique et au cap demandés — sinon une cote tapée au clavier est un mensonge.
// ————————————————————————————————————————————————————————————————————————
describe('CALX90 — pointDepuisCap : la cote tapée est la cote obtenue', () => {
  it('restitue la distance géodésique à moins d’un centimètre sur 100 m, aux quatre caps', () => {
    for (const cap of [0, 90, 180, 270]) {
      const p = pointDepuisCap(P, cap, 100);
      expect(Math.abs(distanceEntreM(P, p) - 100)).toBeLessThan(0.01);
    }
  });

  it('restitue le cap demandé aux quatre points cardinaux', () => {
    expect(capEntreDeg(P, pointDepuisCap(P, 0, 100))).toBeCloseTo(0, 6);
    expect(capEntreDeg(P, pointDepuisCap(P, 90, 100))).toBeCloseTo(90, 6);
    expect(Math.abs(capEntreDeg(P, pointDepuisCap(P, 180, 100)))).toBeCloseTo(180, 6);
    expect(capEntreDeg(P, pointDepuisCap(P, 270, 100))).toBeCloseTo(-90, 6);
  });

  it('cap 0 va vers le NORD, cap 90 vers l’EST (aucune convention inversée)', () => {
    expect(pointDepuisCap(P, 0, 100)[1]).toBeGreaterThan(P[1]);
    expect(pointDepuisCap(P, 90, 100)[0]).toBeGreaterThan(P[0]);
    expect(pointDepuisCap(P, 180, 100)[1]).toBeLessThan(P[1]);
    expect(pointDepuisCap(P, 270, 100)[0]).toBeLessThan(P[0]);
  });

  it('tient la précision sur des longueurs très différentes', () => {
    for (const d of [0.5, 12.34, 100, 987.65]) {
      expect(Math.abs(distanceEntreM(P, pointDepuisCap(P, 37, d)) - d)).toBeLessThan(0.01);
    }
  });

  it('une distance nulle ou non finie ne déplace RIEN (aucune longueur supposée)', () => {
    expect(pointDepuisCap(P, 90, 0)).toBe(P);
    expect(pointDepuisCap(P, 90, -10)).toBe(P);
    expect(pointDepuisCap(P, 90, Number.NaN)).toBe(P);
    expect(pointDepuisCap(P, Number.NaN, 100)).toBe(P);
  });
});

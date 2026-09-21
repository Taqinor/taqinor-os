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
  projeterSurArete,
  distanceAAreteM,
  insertionSurContour,
  supprimerSommet,
  metresParPixel,
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

// ————————————————————————————————————————————————————————————————————————
// CALX91 — INSÉRER ET SUPPRIMER UN SOMMET SUR UNE ARÊTE D'UN CONTOUR FERMÉ.
// ————————————————————————————————————————————————————————————————————————
const A_ARETE: LngLat = [-7.6, 33.5];
const B_ARETE: LngLat = [-7.599, 33.5]; // plein est de A

describe('CALX91 — projeterSurArete', () => {
  it('un clic au-dessus du milieu rend le MILIEU exact de l’arête', () => {
    const milieuVrai: LngLat = [(A_ARETE[0] + B_ARETE[0]) / 2, (A_ARETE[1] + B_ARETE[1]) / 2];
    const clic: LngLat = [milieuVrai[0], milieuVrai[1] + 0.0002]; // au nord du milieu
    const projete = projeterSurArete(A_ARETE, B_ARETE, clic);
    expect(projete).not.toBeNull();
    expect(projete![0]).toBeCloseTo(milieuVrai[0], 12);
    expect(projete![1]).toBeCloseTo(milieuVrai[1], 12);
  });

  it('rend le point au quart quand le clic est au quart', () => {
    const clic: LngLat = [A_ARETE[0] + 0.00025, A_ARETE[1] + 0.0003];
    const projete = projeterSurArete(A_ARETE, B_ARETE, clic);
    expect(projete).not.toBeNull();
    expect(projete![0]).toBeCloseTo(A_ARETE[0] + 0.00025, 12);
  });

  it('un projeté HORS du segment est refusé (avant A comme après B)', () => {
    expect(projeterSurArete(A_ARETE, B_ARETE, [A_ARETE[0] - 0.0005, 33.5003])).toBeNull();
    expect(projeterSurArete(A_ARETE, B_ARETE, [B_ARETE[0] + 0.0005, 33.5003])).toBeNull();
  });

  it('un clic pile sur un sommet existant n’insère pas de doublon', () => {
    expect(projeterSurArete(A_ARETE, B_ARETE, A_ARETE)).toBeNull();
    expect(projeterSurArete(A_ARETE, B_ARETE, B_ARETE)).toBeNull();
  });

  it('une arête dégénérée (deux sommets confondus) n’a aucun projeté', () => {
    expect(projeterSurArete(A_ARETE, [...A_ARETE] as LngLat, [-7.5995, 33.5003])).toBeNull();
  });

  it('distanceAAreteM mesure bien l’écart perpendiculaire, en mètres', () => {
    const milieu: LngLat = [(A_ARETE[0] + B_ARETE[0]) / 2, A_ARETE[1]];
    const clic: LngLat = [milieu[0], milieu[1] + 0.0002];
    const d = distanceAAreteM(A_ARETE, B_ARETE, clic);
    expect(d).not.toBeNull();
    expect(d!).toBeCloseTo(distanceEntreM(clic, milieu), 6);
    expect(distanceAAreteM(A_ARETE, B_ARETE, [B_ARETE[0] + 0.001, 33.5])).toBeNull();
  });
});

describe('CALX91 — insertionSurContour', () => {
  const carre: LngLat[] = [
    [-7.6, 33.5],
    [-7.599, 33.5],
    [-7.599, 33.501],
    [-7.6, 33.501],
  ];

  it('désigne l’arête cliquée et le point d’insertion, sous la tolérance', () => {
    const clic: LngLat = [-7.5995, 33.50002]; // juste au-dessus du côté sud
    const trouve = insertionSurContour(carre, clic, 10);
    expect(trouve).not.toBeNull();
    expect(trouve!.index).toBe(0); // le nouveau sommet s'insère en index + 1
    expect(trouve!.point[1]).toBeCloseTo(33.5, 10);
  });

  it('un clic loin de tout côté n’insère RIEN', () => {
    expect(insertionSurContour(carre, [-7.5995, 33.5005], 5)).toBeNull();
  });

  it('une tolérance nulle ou absente n’insère RIEN', () => {
    const clic: LngLat = [-7.5995, 33.50002];
    expect(insertionSurContour(carre, clic, 0)).toBeNull();
    expect(insertionSurContour(carre, clic, Number.NaN)).toBeNull();
  });

  it('retient l’arête la PLUS PROCHE quand deux sont à portée', () => {
    const coin: LngLat = [-7.59995, 33.50001]; // proche du côté sud ET du côté ouest
    const trouve = insertionSurContour(carre, coin, 50);
    expect(trouve).not.toBeNull();
    // Le côté sud (index 0) est à ~1 m, le côté ouest (index 3) à ~4 m.
    expect(trouve!.index).toBe(0);
  });
});

describe('CALX91 — supprimerSommet', () => {
  const carre: LngLat[] = [
    [-7.6, 33.5],
    [-7.599, 33.5],
    [-7.599, 33.501],
    [-7.6, 33.501],
  ];

  it('retire le sommet demandé sans toucher aux autres', () => {
    const v = supprimerSommet(carre, 1);
    expect(v.ok).toBe(true);
    if (!v.ok) throw new Error('suppression attendue');
    expect(v.anneau).toHaveLength(3);
    expect(v.anneau).toEqual([carre[0], carre[2], carre[3]]);
    expect(carre).toHaveLength(4); // l'anneau d'origine est intact
  });

  it('refuse en NOMMANT la raison quand il ne resterait plus 3 sommets', () => {
    const triangle = carre.slice(0, 3);
    const v = supprimerSommet(triangle, 0);
    expect(v.ok).toBe(false);
    if (v.ok) throw new Error('refus attendu');
    expect(v.motif).toContain('au moins 3 sommets');
  });

  it('refuse en NOMMANT la raison un index qui ne désigne aucun sommet', () => {
    for (const i of [-1, 4, 1.5]) {
      const v = supprimerSommet(carre, i);
      expect(v.ok).toBe(false);
      if (!v.ok) expect(v.motif).toContain('Sommet introuvable');
    }
  });

  it('refuse, en nommant la raison, la suppression qui ferait CROISER le contour', () => {
    // Contour SIMPLE dont le retrait du sommet 1 fait passer la corde à travers une arête
    // non adjacente (nœud papillon). Coordonnées ancrées près de Casablanca.
    const base: LngLat = [-7.6, 33.5];
    const pt = (x: number, y: number): LngLat => [base[0] + x * 0.0001, base[1] + y * 0.0001];
    const contour: LngLat[] = [pt(0, 0), pt(5, 10), pt(10, 0), pt(8, -4), pt(3, 4)];
    // Prémisse du test : le contour de départ est bien simple.
    expect(supprimerSommet(contour, 0).ok).toBe(true);

    const v = supprimerSommet(contour, 1);
    expect(v.ok).toBe(false);
    if (v.ok) throw new Error('refus attendu');
    expect(v.motif).toContain('se croiserait');
    expect(v.motif).toContain('nœud papillon');
  });
});

describe('CALX91 — metresParPixel : la tolérance pixel se lit en mètres', () => {
  it('décroît d’un facteur 2 à chaque niveau de zoom', () => {
    const a = metresParPixel(33.5, 18);
    const b = metresParPixel(33.5, 19);
    expect(a / b).toBeCloseTo(2, 10);
  });

  it('vaut 0 pour une latitude ou un zoom illisibles (aucune tolérance inventée)', () => {
    expect(metresParPixel(Number.NaN, 19)).toBe(0);
    expect(metresParPixel(33.5, Number.NaN)).toBe(0);
  });

  it('au zoom de travail du builder, un rayon de saisie reste de l’ordre du mètre', () => {
    expect(metresParPixel(33.5, 19)).toBeGreaterThan(0);
    expect(metresParPixel(33.5, 19)).toBeLessThan(1);
  });
});

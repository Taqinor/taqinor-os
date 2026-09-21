/**
 * CALX89 — MAGNÉTISME DU TRACÉ (angles droits / 45°) du builder roofPro11.
 *
 * `addVertex` ne refusait qu'un nœud papillon (`mapDraw.ts`, garde W76) et ne corrigeait
 * JAMAIS l'angle : aucune grille, aucun magnétisme angulaire n'existait dans le module.
 * Ce module apporte la géométrie PURE de l'aide au tracé — aucun DOM, aucune carte,
 * aucun Three — donc testable seule.
 *
 * RÈGLE DU MODULE : il ne porte AUCUN seuil métier. Les tolérances qu'il expose sont des
 * CONVENTIONS DE DESSIN (aide au pointage) : elles ne changent ni une surface posable, ni
 * une production, ni une dimension publiée — seulement l'endroit où atterrit le sommet que
 * l'utilisateur vient de cliquer. Chacune est un PARAMÈTRE surchargeable par l'appelant, et
 * un pas nul/absent rend le point cliqué TEL QUEL (comportement d'aujourd'hui, point pour
 * point).
 *
 * Les primitives géodésiques (cap, distance) sont celles de la sphère WGS84 déjà utilisée
 * partout ailleurs dans le builder (`constants.ts`) : aucun rayon ni facteur neuf.
 */
import { DEG2RAD, WGS84_RADIUS } from './constants';
import { type LngLat } from '../../lib/roof';

const RAD2DEG = 180 / Math.PI;

/**
 * Pas d'angle proposés par la puce « Angles droits », du plus grossier au plus fin.
 * CONVENTION DE DESSIN (parité OpenSolar « snap on 90 and 180 degree lines ») : 90° trace
 * un contour orthogonal, 45° autorise les pans coupés. Rien d'autre n'est proposé.
 */
export const PAS_ANGLE_DEG: readonly number[] = [90, 45];

/**
 * Tolérance ANGULAIRE d'accrochage (°). CONVENTION DE DESSIN, pas un seuil métier : au-delà
 * de cet écart, le point cliqué est conservé tel quel. 8° reste très en deçà du demi-pas le
 * plus fin (22,5° pour un pas de 45°), donc un angle volontairement libre n'est jamais
 * capturé contre la volonté du dessinateur.
 */
export const TOLERANCE_ANGLE_DEG = 8;

/** Un couple [lng, lat] exploitable ? (les appelants passent parfois null/undefined). */
function estPoint(v: LngLat | null | undefined): v is LngLat {
  return Array.isArray(v) && v.length === 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]);
}

/** Ramène un angle en degrés dans (-180, 180]. */
export function normaliserDeg(deg: number): number {
  const d = ((deg + 180) % 360 + 360) % 360 - 180;
  // -180 et +180 désignent la même direction : on choisit +180 pour que l'écart au pas
  // soit toujours mesuré du même côté.
  return d === -180 ? 180 : d;
}

/** Cap INITIAL (°, depuis le nord vrai, sens horaire) du segment `a` → `b`. */
export function capEntreDeg(a: LngLat, b: LngLat): number {
  const phi1 = a[1] * DEG2RAD;
  const phi2 = b[1] * DEG2RAD;
  const dLambda = (b[0] - a[0]) * DEG2RAD;
  const y = Math.sin(dLambda) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda);
  return Math.atan2(y, x) * RAD2DEG;
}

/** Distance GÉODÉSIQUE (m) entre deux points (haversine, sphère WGS84 de `constants.ts`). */
export function distanceEntreM(a: LngLat, b: LngLat): number {
  const phi1 = a[1] * DEG2RAD;
  const phi2 = b[1] * DEG2RAD;
  const dPhi = phi2 - phi1;
  const dLambda = (b[0] - a[0]) * DEG2RAD;
  const h =
    Math.sin(dPhi / 2) * Math.sin(dPhi / 2) +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) * Math.sin(dLambda / 2);
  return 2 * WGS84_RADIUS * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * CALX90 — point situé à `distanceM` mètres de `origine`, dans la direction `capDeg`
 * (° depuis le nord vrai, sens horaire). Formule du point de destination sur la sphère —
 * EXACTE, donc le couple (cap, distance) est restitué à la précision flottante par
 * `capEntreDeg`/`distanceEntreM` : la longueur tapée au clavier est la longueur obtenue.
 *
 * Une distance nulle/négative/non finie ou un cap non fini rend l'origine inchangée : rien
 * n'est supposé à la place d'une saisie manquante (c'est l'appelant qui refuse, en nommant
 * le champ fautif).
 */
export function pointDepuisCap(origine: LngLat, capDeg: number, distanceM: number): LngLat {
  if (!estPoint(origine)) return origine;
  if (!Number.isFinite(capDeg) || !Number.isFinite(distanceM) || distanceM <= 0) return origine;
  return destination(origine, capDeg, distanceM);
}

/**
 * Point situé à `distanceM` mètres de `origine`, dans la direction `cap` (° depuis le nord
 * vrai). Formule du point de destination sur la sphère — exacte, donc le couple
 * (cap, distance) est restitué à la précision flottante par `capEntreDeg`/`distanceEntreM`.
 */
function destination(origine: LngLat, cap: number, distanceM: number): LngLat {
  const delta = distanceM / WGS84_RADIUS;
  const theta = cap * DEG2RAD;
  const phi1 = origine[1] * DEG2RAD;
  const lambda1 = origine[0] * DEG2RAD;
  const sinPhi2 = Math.sin(phi1) * Math.cos(delta) + Math.cos(phi1) * Math.sin(delta) * Math.cos(theta);
  const phi2 = Math.asin(Math.max(-1, Math.min(1, sinPhi2)));
  const lambda2 =
    lambda1 +
    Math.atan2(
      Math.sin(theta) * Math.sin(delta) * Math.cos(phi1),
      Math.cos(delta) - Math.sin(phi1) * Math.sin(phi2),
    );
  return [lambda2 * RAD2DEG, phi2 * RAD2DEG];
}

/**
 * CALX89 — ramène le segment `precedent` → `candidat` au multiple de `pasDeg` le plus
 * proche, quand l'écart est sous `toleranceDeg`. La DISTANCE cliquée est conservée : seule
 * la direction est corrigée.
 *
 * La référence angulaire est le segment PRÉCÉDENT (`avantPrecedent` → `precedent`), c'est-à-
 * dire un angle RELATIF entre côtés — la parité OpenSolar « snap on 90 and 180 degree
 * lines ». Au tout premier segment d'un tracé il n'existe aucun côté de référence : la
 * référence est alors le NORD VRAI (convention de dessin : le premier côté s'aligne sur les
 * points cardinaux).
 *
 * RIEN N'EST CONTRAINT quand :
 *  - il n'y a pas encore de sommet précédent (le PREMIER point d'un tracé, jamais contraint) ;
 *  - `pasDeg` est nul/négatif/non fini — c'est le cas PUCE ÉTEINTE : le point cliqué est
 *    rendu tel quel, référence comprise (tracé identique à celui d'aujourd'hui) ;
 *  - l'écart au multiple le plus proche dépasse `toleranceDeg` ;
 *  - le candidat est confondu avec le sommet précédent (aucune direction à corriger).
 */
export function contraindreAngle(
  precedent: LngLat | null | undefined,
  avantPrecedent: LngLat | null | undefined,
  candidat: LngLat,
  pasDeg: number,
  toleranceDeg: number = TOLERANCE_ANGLE_DEG,
): LngLat {
  if (!estPoint(candidat)) return candidat;
  if (!estPoint(precedent)) return candidat; // premier point d'un tracé : rien à contraindre
  if (!Number.isFinite(pasDeg) || pasDeg <= 0) return candidat; // puce éteinte
  if (!Number.isFinite(toleranceDeg) || toleranceDeg < 0) return candidat;
  const distance = distanceEntreM(precedent, candidat);
  if (!(distance > 0)) return candidat;
  const capCandidat = capEntreDeg(precedent, candidat);
  const capReference = estPoint(avantPrecedent) ? capEntreDeg(avantPrecedent, precedent) : 0;
  const relatif = normaliserDeg(capCandidat - capReference);
  const cible = Math.round(relatif / pasDeg) * pasDeg;
  if (Math.abs(normaliserDeg(relatif - cible)) > toleranceDeg) return candidat;
  return destination(precedent, capReference + cible, distance);
}

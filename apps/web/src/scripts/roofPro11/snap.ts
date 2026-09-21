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
import { DEG2M, DEG2RAD, WGS84_RADIUS } from './constants';
import { isSimplePolygon, type LngLat } from '../../lib/roof';

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

// ————————————————————————————————————————————————————————————————————————
// CALX91 — INSÉRER ET SUPPRIMER UN SOMMET SUR UNE ARÊTE D'UN CONTOUR FERMÉ
//
// Après fermeture, seul le glissé d'un sommet EXISTANT était possible, et « Annuler le
// dernier point » n'agissait que pendant le tracé : rien ne permettait d'ajouter un coin au
// milieu d'un côté ni d'en retirer un. Parité Aurora SmartRoof (insertion de « fold » et
// édition des nœuds). Géométrie PURE, gestes câblés dans `obstaclesUi.ts`.
// ————————————————————————————————————————————————————————————————————————

/**
 * Mètres couverts par UN pixel écran au zoom MapLibre courant, à la latitude donnée
 * (tuiles de 512 px — convention MapLibre GL). Sert à exprimer une tolérance de SAISIE
 * pixel (ex. `VERTEX_GRAB_PX`) en mètres : c'est la même tolérance de dessin, lue dans
 * l'unité du calcul. Aucun nombre neuf : le tour de Terre vient de `WGS84_RADIUS`.
 */
export function metresParPixel(latDeg: number, zoom: number): number {
  if (!Number.isFinite(latDeg) || !Number.isFinite(zoom)) return 0;
  const cosLat = Math.max(1e-6, Math.cos(latDeg * DEG2RAD));
  return (2 * Math.PI * WGS84_RADIUS * cosLat) / (512 * Math.pow(2, zoom));
}

/**
 * CALX91 — projeté ORTHOGONAL de `p` sur l'arête `a`→`b`, ou `null` quand le projeté tombe
 * HORS du segment (y compris exactement sur `a` ou `b` : il y a déjà un sommet là, insérer
 * un doublon n'a aucun sens).
 *
 * Le rapport de projection est calculé dans le plan tangent local (est/nord en mètres,
 * longitude corrigée du cosinus de la latitude) puis appliqué en lng/lat : un clic pile au
 * milieu d'un côté rend le MILIEU exact.
 */
export function projeterSurArete(a: LngLat, b: LngLat, p: LngLat): LngLat | null {
  if (!estPoint(a) || !estPoint(b) || !estPoint(p)) return null;
  const cosLat = Math.max(1e-6, Math.cos(a[1] * DEG2RAD));
  const abX = (b[0] - a[0]) * cosLat;
  const abY = b[1] - a[1];
  const carre = abX * abX + abY * abY;
  if (!(carre > 0)) return null; // arête dégénérée : aucun projeté défini
  const apX = (p[0] - a[0]) * cosLat;
  const apY = p[1] - a[1];
  const t = (apX * abX + apY * abY) / carre;
  if (!(t > 0) || !(t < 1)) return null; // hors du segment (ou sur un sommet existant)
  return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])];
}

/** Distance (m) de `p` à son projeté orthogonal sur `a`→`b`, ou null si hors du segment. */
export function distanceAAreteM(a: LngLat, b: LngLat, p: LngLat): number | null {
  const projete = projeterSurArete(a, b, p);
  return projete ? distanceEntreM(p, projete) : null;
}

/**
 * CALX91 — arête du contour FERMÉ la plus proche de `p`, dont le projeté orthogonal est à
 * moins de `tolM`. `index` est le rang du PREMIER sommet de l'arête : le nouveau sommet
 * s'insère donc en `index + 1`. `null` quand aucune arête n'est assez proche (le geste ne
 * fabrique alors AUCUN sommet).
 */
export function insertionSurContour(
  anneau: readonly LngLat[],
  p: LngLat,
  tolM: number,
): { index: number; point: LngLat } | null {
  if (!Array.isArray(anneau) || anneau.length < 3 || !estPoint(p)) return null;
  if (!Number.isFinite(tolM) || tolM <= 0) return null;
  let meilleur: { index: number; point: LngLat } | null = null;
  let meilleureDistance = Infinity;
  for (let i = 0; i < anneau.length; i++) {
    const a = anneau[i];
    const b = anneau[(i + 1) % anneau.length];
    const projete = projeterSurArete(a, b, p);
    if (!projete) continue;
    const d = distanceEntreM(p, projete);
    if (d <= tolM && d < meilleureDistance) {
      meilleureDistance = d;
      meilleur = { index: i, point: projete };
    }
  }
  return meilleur;
}

/** Verdict d'une suppression de sommet — un refus NOMME toujours sa raison. */
export type VerdictSuppression = { ok: true; anneau: LngLat[] } | { ok: false; motif: string };

/**
 * CALX91 — retire le sommet `index` du contour. REFUSE, en nommant la raison :
 *  - un index qui ne désigne aucun sommet ;
 *  - une suppression qui laisserait moins de 3 sommets (il n'y a plus de contour) ;
 *  - une suppression qui ferait CROISER le contour (nœud papillon) — même garde W76 que
 *    la pose d'un sommet : un anneau croisé fausse l'aire géodésique et le pavage.
 */
export function supprimerSommet(anneau: readonly LngLat[], index: number): VerdictSuppression {
  if (!Array.isArray(anneau) || !Number.isInteger(index) || index < 0 || index >= anneau.length) {
    return { ok: false, motif: 'Sommet introuvable — rien à supprimer.' };
  }
  if (anneau.length <= 3) {
    return {
      ok: false,
      motif: `Suppression refusée : un contour garde au moins 3 sommets (celui-ci n’en a que ${anneau.length}).`,
    };
  }
  const restant = anneau.filter((_, i) => i !== index).map((v) => [v[0], v[1]] as LngLat);
  if (!isSimplePolygon(restant)) {
    return {
      ok: false,
      motif: 'Suppression refusée : le contour se croiserait (nœud papillon) — déplacez d’abord les sommets voisins.',
    };
  }
  return { ok: true, anneau: restant };
}

// ————————————————————————————————————————————————————————————————————————
// CALX92 — AIMANTER LE TRACÉ AUX SOMMETS ET AUX ARÊTES DES PANS DÉJÀ TRACÉS
//
// L'aimantation existante (`layoutEditor.ts`) ne concerne QUE les panneaux en placement
// libre : rien n'aimantait un nouveau pan à un pan voisin, alors que c'est l'adjacence
// entre pans qui fait remonter une faîtière commune (`scene3d.ts`). Parité HelioScope
// (« object-snap »). Le sommet COMMUN devient exact, donc les deux pans partagent
// réellement leur arête au lieu de se frôler à quelques centimètres.
//
// `tolM` est une tolérance de SAISIE (convention de dessin) : elle vient de la puce, ou du
// rayon de saisie de sommet lu en mètres (`metresParPixel` × VERTEX_GRAB_PX). Une tolérance
// nulle/absente (puce éteinte) rend le candidat TEL QUEL.
// ————————————————————————————————————————————————————————————————————————

/** Ce à quoi un sommet s'est accroché — utile pour le dire à l'écran, jamais pour calculer. */
export type NatureAccroche = 'sommet' | 'arete';

export interface Accroche {
  point: LngLat;
  nature: NatureAccroche;
  /** Rang de l'anneau accroché dans la liste passée. */
  anneau: number;
  /** Distance réellement franchie (m). */
  distanceM: number;
}

/**
 * CALX92 — accroche `candidat` au SOMMET ou au point d'ARÊTE le plus proche des anneaux
 * fournis, sous `tolM`. Un sommet l'emporte toujours sur une arête à portée : c'est le
 * point que le dessinateur vise (convention partagée par tous les outils de dessin).
 * `null` quand rien n'est à portée — le point cliqué reste alors exactement où il est.
 */
export function accrocheAuxZones(
  candidat: LngLat,
  anneaux: readonly (readonly LngLat[])[] | null | undefined,
  tolM: number,
): Accroche | null {
  if (!estPoint(candidat)) return null;
  if (!Array.isArray(anneaux) || anneaux.length === 0) return null;
  if (!Number.isFinite(tolM) || tolM <= 0) return null; // puce éteinte : aucun déplacement
  let meilleurSommet: Accroche | null = null;
  let meilleureArete: Accroche | null = null;
  for (let a = 0; a < anneaux.length; a++) {
    const anneau = anneaux[a];
    if (!Array.isArray(anneau) || anneau.length < 2) continue;
    for (const v of anneau) {
      if (!estPoint(v)) continue;
      const d = distanceEntreM(candidat, v);
      if (d <= tolM && (!meilleurSommet || d < meilleurSommet.distanceM)) {
        meilleurSommet = { point: [v[0], v[1]], nature: 'sommet', anneau: a, distanceM: d };
      }
    }
    if (anneau.length < 3) continue; // pas d'anneau fermé : aucune arête à viser
    for (let i = 0; i < anneau.length; i++) {
      const projete = projeterSurArete(anneau[i], anneau[(i + 1) % anneau.length], candidat);
      if (!projete) continue;
      const d = distanceEntreM(candidat, projete);
      if (d <= tolM && (!meilleureArete || d < meilleureArete.distanceM)) {
        meilleureArete = { point: projete, nature: 'arete', anneau: a, distanceM: d };
      }
    }
  }
  return meilleurSommet ?? meilleureArete;
}

/**
 * CALX92 — version « poseuse » : rend le point accroché, ou le CANDIDAT TEL QUEL (même
 * référence) quand rien n'est à portée ou que l'aimantation est éteinte (`tolM` nul).
 */
export function aimanterAuxZones(
  candidat: LngLat,
  anneaux: readonly (readonly LngLat[])[] | null | undefined,
  tolM: number,
): LngLat {
  return accrocheAuxZones(candidat, anneaux, tolM)?.point ?? candidat;
}

// ————————————————————————————————————————————————————————————————————————
// CALX97 — SAISIR LES COTES EXACTES D'UN PAN ET LE FAIRE PIVOTER D'UN BLOC
//
// Un pan ne se modifiait qu'au glissé de ses sommets : aucune saisie de largeur/longueur,
// aucune rotation d'ensemble (la rotation absolue n'existait que sur une sélection de
// panneaux en placement libre). Parité HelioScope (cotes exactes à deux décimales + menu
// « Rotate Field Segments/Keepouts »). Géométrie PURE ; les gestes sont dans `zones.ts`.
//
// CONVENTION D'ANGLE : une rotation POSITIVE tourne dans le SENS HORAIRE, comme un cap
// (0° = nord, 90° = est) — le même repère que `capEntreDeg`/`pointDepuisCap`, pour qu'un
// seul sens d'angle circule dans tout le module.
// ————————————————————————————————————————————————————————————————————————

/** Centroïde d'un anneau : moyenne de ses sommets — la MÊME définition que le reste du
 *  builder (`roof-tool-pro11.ts` `close()`), pour qu'un pan pivote autour du point déjà
 *  affiché comme son centre. `null` si l'anneau est vide. */
export function centroideAnneau(anneau: readonly LngLat[]): LngLat | null {
  if (!Array.isArray(anneau) || anneau.length === 0) return null;
  let lng = 0;
  let lat = 0;
  let n = 0;
  for (const v of anneau) {
    if (!estPoint(v)) continue;
    lng += v[0];
    lat += v[1];
    n++;
  }
  return n > 0 ? [lng / n, lat / n] : null;
}

/** CALX97 — fait tourner UN point de `angleDeg` (sens horaire) autour de `centre`. */
export function pivoterPoint(p: LngLat, angleDeg: number, centre: LngLat): LngLat {
  if (!estPoint(p) || !estPoint(centre) || !Number.isFinite(angleDeg)) return p;
  const cosLat = Math.max(1e-6, Math.cos(centre[1] * DEG2RAD));
  const dx = (p[0] - centre[0]) * cosLat;
  const dy = p[1] - centre[1];
  const a = angleDeg * DEG2RAD;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  const rx = dx * cos + dy * sin; // sens HORAIRE (nord → est pour +90°)
  const ry = -dx * sin + dy * cos;
  return [centre[0] + rx / cosLat, centre[1] + ry];
}

/**
 * CALX97 — fait tourner un anneau de `angleDeg` (sens horaire) autour de son centroïde,
 * ou d'un `centre` imposé (pour faire suivre les obstacles d'un pan AUTOUR DU MÊME point).
 * Le centroïde est conservé par construction.
 */
export function pivoterAnneau(anneau: readonly LngLat[], angleDeg: number, centre?: LngLat): LngLat[] {
  const c = centre ?? centroideAnneau(anneau);
  if (!c) return (anneau ?? []).map((v) => [v[0], v[1]] as LngLat);
  return anneau.map((v) => {
    const r = pivoterPoint(v, angleDeg, c);
    return [r[0], r[1]] as LngLat;
  });
}

/** Verdict d'un redimensionnement — un refus NOMME toujours sa raison. */
export type VerdictRectangle = { ok: true; anneau: LngLat[] } | { ok: false; motif: string };

/**
 * CALX97 — cotes RÉELLES (m) d'un pan à 4 côtés : `longueurM` le long du PREMIER côté
 * (sommet 0 → sommet 1), `largeurM` perpendiculairement. `null` si l'anneau n'est pas un
 * quadrilatère — on ne devine jamais les cotes d'une forme quelconque.
 */
export function dimensionsRectangleM(anneau: readonly LngLat[]): { longueurM: number; largeurM: number } | null {
  if (!Array.isArray(anneau) || anneau.length !== 4) return null;
  if (!anneau.every(estPoint)) return null;
  const longueurM = (distanceEntreM(anneau[0], anneau[1]) + distanceEntreM(anneau[3], anneau[2])) / 2;
  const largeurM = (distanceEntreM(anneau[1], anneau[2]) + distanceEntreM(anneau[0], anneau[3])) / 2;
  return { longueurM, largeurM };
}

/**
 * CALX97 — repose les 4 sommets d'un pan rectangulaire aux cotes SAISIES, AUTOUR DE SON
 * CENTROÏDE (qui est donc conservé exactement) et sur ses propres axes : `longueurM` le long
 * du premier côté, `largeurM` perpendiculairement. L'ordre des sommets est préservé.
 *
 * REFUS NOMMÉS : un contour qui n'est pas un quadrilatère (la saisie largeur/longueur n'a
 * alors aucun sens), une cote absente ou ≤ 0, un premier côté dégénéré (aucun axe lisible).
 * L'appelant préfixe le motif du NOM du pan.
 */
export function redimensionnerRectangle(
  anneau: readonly LngLat[],
  largeurM: number,
  longueurM: number,
): VerdictRectangle {
  if (!Array.isArray(anneau) || anneau.length !== 4 || !anneau.every(estPoint)) {
    const n = Array.isArray(anneau) ? anneau.length : 0;
    return {
      ok: false,
      motif: `cotes refusées — la saisie largeur/longueur ne s’applique qu’à un pan à 4 côtés (celui-ci en a ${n}). Ajustez-le au glissé de ses sommets, ou utilisez la rotation.`,
    };
  }
  if (!Number.isFinite(longueurM) || longueurM <= 0) {
    return { ok: false, motif: 'longueur refusée — saisissez une longueur en mètres supérieure à 0.' };
  }
  if (!Number.isFinite(largeurM) || largeurM <= 0) {
    return { ok: false, motif: 'largeur refusée — saisissez une largeur en mètres supérieure à 0.' };
  }
  const centre = centroideAnneau(anneau) as LngLat;
  const cosLat = Math.max(1e-6, Math.cos(centre[1] * DEG2RAD));
  const enu = (v: LngLat): [number, number] => [(v[0] - centre[0]) * cosLat * DEG2M, (v[1] - centre[1]) * DEG2M];
  const [x0, y0] = enu(anneau[0]);
  const [x1, y1] = enu(anneau[1]);
  const [x3, y3] = enu(anneau[3]);
  const ux = x1 - x0;
  const uy = y1 - y0;
  const norme = Math.hypot(ux, uy);
  if (!(norme > 0)) {
    return { ok: false, motif: 'cotes refusées — le premier côté du pan est dégénéré : aucun axe de longueur lisible.' };
  }
  const u: [number, number] = [ux / norme, uy / norme];
  // Perpendiculaire à u, ORIENTÉE vers le 4ᵉ sommet : l'ordre des sommets est préservé.
  let w: [number, number] = [-u[1], u[0]];
  if ((x3 - x0) * w[0] + (y3 - y0) * w[1] < 0) w = [-w[0], -w[1]];
  const demiL = longueurM / 2;
  const demil = largeurM / 2;
  const coin = (su: number, sw: number): LngLat => {
    const ex = su * demiL * u[0] + sw * demil * w[0];
    const ey = su * demiL * u[1] + sw * demil * w[1];
    return [centre[0] + ex / (DEG2M * cosLat), centre[1] + ey / DEG2M];
  };
  return { ok: true, anneau: [coin(-1, -1), coin(1, -1), coin(1, 1), coin(-1, 1)] };
}


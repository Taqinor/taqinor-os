/**
 * CALX95 — RETRAIT PROPRE À CHAQUE ARÊTE PHYSIQUE du contour.
 *
 * Jusqu'ici les retraits se règlent par CATÉGORIE (latérale / extrémité / acrotère /
 * joint — `roofPro2.resolveSetbacks`) et s'appliquent au pourtour ENTIER : les quatre
 * catégories ne savent pas désigner UN segment. Or un rampant qui longe une limite de
 * propriété, un chemin de circulation imposé le long d'un seul bord, ou une bande de
 * sécurité devant une façade, n'ont aucune raison de valoir pour les autres bords du même
 * pan. Le document le porte depuis CALX81 (`zones[].edges[].retraitM`, OPTIONNEL) ; ce
 * module est la géométrie qui l'applique.
 *
 * Règle, sans exception :
 *  - une arête qui porte `retraitM` est rognée de CETTE valeur, EN PLUS du retrait de
 *    catégorie déjà appliqué au pourtour (CALX95) ;
 *  - une arête SANS `retraitM` n'ajoute RIEN : seul le retrait de catégorie s'applique,
 *    soit exactement le comportement d'aujourd'hui, anneau posable identique ;
 *  - aucune valeur n'est proposée, complétée ni arrondie : un retrait non saisi est
 *    ABSENT, jamais un zéro « mesuré à ras » ni une moyenne des autres arêtes.
 *
 * Géométrie PURE, en MÈTRES, dans un repère plan (ENU local — celui de `roofPro2.ringENU`) :
 * aucune projection, aucun DOM, aucune dépendance. Le rognage est un découpage par
 * demi-plans (Sutherland–Hodgman) calculés sur les segments du contour D'ORIGINE, donc
 * l'ordre des arêtes rognées ne change pas le résultat.
 */

/** Un point plan, en mètres. */
export type PointM = [number, number];

/** CALX95 — convention de dessin : deux sommets plus proches que ça (m) après découpage
 *  sont le MÊME sommet (les intersections de demi-plans en produisent naturellement des
 *  doublons). Ne modifie aucune distance de retrait ; sert uniquement à ne pas renvoyer un
 *  anneau avec des points superposés. */
const MEME_POINT_M = 1e-9;

/** Aire signée d'un anneau (m²) — positive si les sommets tournent dans le sens direct. */
function aireSignee(anneau: readonly (readonly [number, number])[]): number {
  let s = 0;
  for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
    s += anneau[j][0] * anneau[i][1] - anneau[i][0] * anneau[j][1];
  }
  return s / 2;
}

/** Découpe `poly` par le demi-plan « à au moins `retraitM` en dedans du segment a→b ».
 *  `sens` vaut +1 quand l'anneau tourne dans le sens direct, −1 sinon (il fixe de quel
 *  côté du segment se trouve l'intérieur). Renvoie [] quand le demi-plan ne laisse rien. */
function couperDemiPlan(
  poly: readonly PointM[],
  a: readonly [number, number],
  b: readonly [number, number],
  retraitM: number,
  sens: number,
): PointM[] {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy);
  // Segment dégénéré (deux sommets confondus) : il ne porte aucune direction, donc aucun
  // retrait ne peut en être déduit — on ne coupe rien plutôt que de couper au hasard.
  if (len <= 0) return [...poly];
  const nx = (sens >= 0 ? -dy : dy) / len;
  const ny = (sens >= 0 ? dx : -dx) / len;
  /** Distance signée au demi-plan : ≥ 0 = le point est assez en dedans. */
  const f = (p: readonly [number, number]): number => (p[0] - a[0]) * nx + (p[1] - a[1]) * ny - retraitM;
  const out: PointM[] = [];
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const pj = poly[j];
    const pi = poly[i];
    const fj = f(pj);
    const fi = f(pi);
    if (fj >= 0 && fi >= 0) {
      out.push([pi[0], pi[1]]);
    } else if (fj >= 0 && fi < 0) {
      const t = fj / (fj - fi);
      out.push([pj[0] + (pi[0] - pj[0]) * t, pj[1] + (pi[1] - pj[1]) * t]);
    } else if (fj < 0 && fi >= 0) {
      const t = fj / (fj - fi);
      out.push([pj[0] + (pi[0] - pj[0]) * t, pj[1] + (pi[1] - pj[1]) * t]);
      out.push([pi[0], pi[1]]);
    }
  }
  return out;
}

/** Retire les sommets consécutifs confondus (et le doublon de fermeture). */
function sansDoublons(poly: readonly PointM[]): PointM[] {
  const out: PointM[] = [];
  for (const p of poly) {
    const dernier = out[out.length - 1];
    if (dernier && Math.hypot(p[0] - dernier[0], p[1] - dernier[1]) <= MEME_POINT_M) continue;
    out.push([p[0], p[1]]);
  }
  while (out.length >= 2) {
    const a = out[0];
    const b = out[out.length - 1];
    if (Math.hypot(a[0] - b[0], a[1] - b[1]) <= MEME_POINT_M) out.pop();
    else break;
  }
  return out;
}

/**
 * CALX95 — anneau POSABLE obtenu en rognant `anneau` (mètres, repère plan) de la valeur
 * propre à chaque arête. `retraitsParIndex` est indexé par le RANG du segment, exactement
 * comme `zones[].edges[].index` du document : le segment `i` va de `anneau[i]` à
 * `anneau[i + 1]` (le dernier reboucle sur `anneau[0]`).
 *
 * - Un index absent, non entier, hors du contour, ou dont la valeur n'est pas un nombre
 *   fini strictement positif, n'entraîne AUCUN rognage : on ne devine pas un retrait.
 * - Aucune entrée exploitable ⇒ l'anneau est renvoyé TEL QUEL (mêmes points, même ordre),
 *   donc la surface posable d'aujourd'hui est inchangée.
 * - Si les retraits mangent tout le pan, le résultat est `[]` : « plus aucune surface
 *   posable » est une réponse, pas une erreur — jamais un anneau de repli inventé.
 *
 * Fonction PURE : n'écrit ni ne mute son entrée.
 */
export function rognerParArete(
  anneau: readonly (readonly [number, number])[],
  retraitsParIndex: Readonly<Record<number, number>> = {},
): PointM[] {
  const n = anneau.length;
  const copie = (): PointM[] => anneau.map(([x, y]) => [x, y] as PointM);
  if (n < 3) return copie();
  const retenus: Array<{ index: number; retraitM: number }> = [];
  for (const [cle, valeur] of Object.entries(retraitsParIndex ?? {})) {
    const index = Number(cle);
    if (!Number.isInteger(index) || index < 0 || index >= n) continue;
    if (typeof valeur !== 'number' || !Number.isFinite(valeur) || valeur <= 0) continue;
    retenus.push({ index, retraitM: valeur });
  }
  if (!retenus.length) return copie();
  const sens = aireSignee(anneau) >= 0 ? 1 : -1;
  let poly: PointM[] = copie();
  for (const { index, retraitM } of retenus) {
    poly = couperDemiPlan(poly, anneau[index], anneau[(index + 1) % n], retraitM, sens);
    if (poly.length < 3) return [];
  }
  const net = sansDoublons(poly);
  return net.length >= 3 ? net : [];
}

/** Ce qui s'applique RÉELLEMENT à un segment, et d'où ça vient (pour l'affichage comme
 *  pour le calcul) — aucune des deux valeurs n'est inventée. */
export interface RetraitArete {
  /** Retrait total appliqué à ce segment (m) : catégorie + retrait propre éventuel. */
  totalM: number;
  /** Ce que ce segment AJOUTE au pourtour déjà rogné par la catégorie (m). */
  supplementM: number;
  /** `arête` = un retrait propre est saisi sur ce segment ; `catégorie` = aucun, seul le
   *  réglage de catégorie s'applique (comportement d'aujourd'hui). */
  origine: 'arête' | 'catégorie';
}

/**
 * CALX95 — décision, pour UN segment : un `retraitM` saisi s'AJOUTE au retrait de
 * catégorie déjà appliqué au pourtour entier ; absent (ou illisible : non fini, négatif),
 * le segment garde exactement le retrait de catégorie, sans supplément. Le repli sur la
 * catégorie est EXPLICITE et nommé (`origine`) — jamais un nombre choisi par défaut.
 * `retraitCategorieM` illisible est traité comme 0 (aucune catégorie exploitable), pour
 * que la fonction ne fabrique jamais un total douteux.
 */
export function retraitArete(retraitAreteM: number | undefined, retraitCategorieM: number): RetraitArete {
  const categorie = Number.isFinite(retraitCategorieM) && retraitCategorieM > 0 ? retraitCategorieM : 0;
  const saisi =
    typeof retraitAreteM === 'number' && Number.isFinite(retraitAreteM) && retraitAreteM > 0 ? retraitAreteM : null;
  if (saisi === null) return { totalM: categorie, supplementM: 0, origine: 'catégorie' };
  return { totalM: categorie + saisi, supplementM: saisi, origine: 'arête' };
}

/** Une arête du document, réduite à ce dont ce module a besoin (forme de
 *  `zones[].edges[]`, CALX81) — aucun import du builder : la géométrie reste autonome. */
export interface AreteRetrait {
  index: number;
  retraitM?: number;
}

/**
 * CALX95 — table `index → supplément (m)` à passer à `rognerParArete`, construite depuis
 * les arêtes du document. Seules les arêtes qui portent un `retraitM` exploitable y
 * figurent : les autres sont ABSENTES de la table (et non à zéro), pour que « aucune
 * arête saisie » produise très exactement l'anneau posable d'aujourd'hui.
 */
export function supplementsParArete(
  edges: readonly AreteRetrait[] | undefined,
  retraitCategorieM: number,
): Record<number, number> {
  const out: Record<number, number> = {};
  for (const e of edges ?? []) {
    if (!e || !Number.isInteger(e.index) || e.index < 0) continue;
    const { supplementM, origine } = retraitArete(e.retraitM, retraitCategorieM);
    if (origine === 'arête' && supplementM > 0) out[e.index] = supplementM;
  }
  return out;
}

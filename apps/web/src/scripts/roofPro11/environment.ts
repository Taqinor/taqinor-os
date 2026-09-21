/**
 * CAL67 — objets d'ENVIRONNEMENT (arbres, bâtiments voisins) posés HORS du contour de
 * toiture, avec leurs dimensions RÉELLES. Géométrie PURE (aucun Three, aucun DOM) :
 * création/édition/anneau d'affichage + conversion en obstructions d'ombrage — même
 * pipeline que `shadingEngine.ts` (isSunBlocked/hourlyShadeFactors/pointSolarAccess),
 * réutilisé tel quel. Toutes les dimensions sont SAISIES ; RIEN n'est estimé — un objet
 * sans `heightM` ne porte simplement aucune ombre (comportement identique à l'absence
 * d'objet), jamais une hauteur inventée.
 */
import { type LngLat } from '../../lib/roof';
import { type ShadeObstructionENU } from '../../lib/shadingEngine';

const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;

export type EnvironmentKind = 'arbre' | 'batiment';

export interface EnvironmentObject {
  id: string;
  label?: string;
  kind: EnvironmentKind;
  centerLng: number;
  centerLat: number;
  /** Hauteur SAISIE (m). Absente = l'objet ne porte AUCUNE ombre. */
  heightM?: number;
  /** Arbre : diamètre du houppier (m), SAISI. */
  crownDiameterM?: number;
  /** Arbre : feuillage persistant (true) ou caduc (false). Absent = non renseigné. */
  evergreen?: boolean;
  /** Bâtiment : emprise réelle (lng/lat), à défaut lengthM/widthM décrivent un rectangle
   *  centré. */
  footprint?: LngLat[];
  lengthM?: number;
  widthM?: number;
}

/** Diamètre/emprise PLANCHER/PLAFOND (m) d'un objet d'environnement — mêmes ordres de
 *  grandeur que les obstacles de toiture. */
export const ENV_MIN_DIM_M = 0.5;
export const ENV_MAX_DIM_M = 60;
export const ENV_MIN_HEIGHT_M = 0.5;
export const ENV_MAX_HEIGHT_M = 60;

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Un objet d'environnement fraîchement posé : AUCUNE dimension inventée — seuls id,
 *  genre et position sont connus tant que l'utilisateur n'a rien saisi. */
export function newEnvironmentObject(id: string, kind: EnvironmentKind, center: LngLat): EnvironmentObject {
  return { id, kind, centerLng: center[0], centerLat: center[1] };
}

/**
 * CALX105 — repose un objet d'environnement sur le point donné (clic sur la carte, ou fin
 * d'un glissé de son marqueur). Son EMPRISE explicite suit le même déplacement : sans cela,
 * un bâtiment voisin laisserait son polygone d'emprise derrière lui, et l'ombre porterait
 * depuis un endroit où l'objet n'est plus.
 *
 * AUCUNE DIMENSION N'EST TOUCHÉE : un objet sans hauteur saisie reste sans hauteur, donc
 * sans ombre — déplacer un objet ne lui invente jamais de dimensions.
 */
export function deplacerEnvironment(o: EnvironmentObject, centre: LngLat): EnvironmentObject {
  if (!Array.isArray(centre) || centre.length !== 2) return o;
  const [lng, lat] = centre;
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return o;
  const dLng = lng - o.centerLng;
  const dLat = lat - o.centerLat;
  const out: EnvironmentObject = { ...o, centerLng: lng, centerLat: lat };
  if (o.footprint && o.footprint.length > 0) {
    out.footprint = o.footprint.map(([fLng, fLat]) => [fLng + dLng, fLat + dLat] as LngLat);
  }
  return out;
}

export function withEnvHeight(o: EnvironmentObject, heightM: number | null | undefined): EnvironmentObject {
  if (heightM == null || !Number.isFinite(heightM) || heightM <= 0) {
    const { heightM: _drop, ...rest } = o;
    return rest;
  }
  return { ...o, heightM: clamp(heightM, ENV_MIN_HEIGHT_M, ENV_MAX_HEIGHT_M) };
}

export function withCrownDiameter(o: EnvironmentObject, diameterM: number | null | undefined): EnvironmentObject {
  if (diameterM == null || !Number.isFinite(diameterM) || diameterM <= 0) {
    const { crownDiameterM: _drop, ...rest } = o;
    return rest;
  }
  return { ...o, crownDiameterM: clamp(diameterM, ENV_MIN_DIM_M, ENV_MAX_DIM_M) };
}

export function withFootprintDims(o: EnvironmentObject, lengthM: number | null | undefined, widthM: number | null | undefined): EnvironmentObject {
  const out: EnvironmentObject = { ...o };
  if (lengthM == null || !Number.isFinite(lengthM) || lengthM <= 0) delete out.lengthM;
  else out.lengthM = clamp(lengthM, ENV_MIN_DIM_M, ENV_MAX_DIM_M);
  if (widthM == null || !Number.isFinite(widthM) || widthM <= 0) delete out.widthM;
  else out.widthM = clamp(widthM, ENV_MIN_DIM_M, ENV_MAX_DIM_M);
  return out;
}

export function withEvergreen(o: EnvironmentObject, evergreen: boolean | null | undefined): EnvironmentObject {
  if (evergreen == null) {
    const { evergreen: _drop, ...rest } = o;
    return rest;
  }
  return { ...o, evergreen };
}

/** Anneau lng/lat pour l'affichage : un footprint explicite (bâtiment) prime, sinon un
 *  polygone régulier (16 côtés, cercle approché) de rayon `crownDiameterM/2` (arbre) ou
 *  `max(lengthM,widthM)/2` (bâtiment sans emprise saisie). null si aucune dimension
 *  n'est connue (rien à dessiner — jamais un cercle de taille inventée). */
export function environmentRing(o: EnvironmentObject): LngLat[] | null {
  if (o.footprint && o.footprint.length >= 3) return o.footprint;
  const diameterM = o.kind === 'arbre' ? o.crownDiameterM : (o.lengthM ?? o.widthM);
  if (!diameterM || diameterM <= 0) return null;
  const r = diameterM / 2;
  const cosLat = Math.max(1e-6, Math.cos(o.centerLat * DEG2RAD));
  const N = 16;
  const ring: LngLat[] = [];
  for (let i = 0; i < N; i++) {
    const a = (2 * Math.PI * i) / N;
    const dLng = (r * Math.cos(a)) / (DEG2M * cosLat);
    const dLat = (r * Math.sin(a)) / DEG2M;
    ring.push([o.centerLng + dLng, o.centerLat + dLat]);
  }
  return ring;
}

/**
 * CORRECTIF (lane web/roofpro, 20/09) — un objet d'environnement n'a d'EMPRISE que si
 * l'utilisateur l'a saisie : emprise polygonale explicite, houppier (arbre) ou
 * longueur/largeur (bâtiment). Sans elle, la demi-largeur d'occultation est INCONNUE —
 * elle n'est JAMAIS remplacée par un nombre de repli (l'ancien 1,5 m n'avait aucune
 * source). Un tel objet ne porte donc AUCUNE ombre et l'écran le signale
 * « emprise à saisir ».
 */
export function environmentFootprintHalfWidthM(o: EnvironmentObject): number | null {
  if (o.footprint && o.footprint.length >= 3) {
    const cosLat = Math.max(1e-6, Math.cos(o.centerLat * DEG2RAD));
    let maxR = 0;
    for (const [lng, lat] of o.footprint) {
      const dx = (lng - o.centerLng) * DEG2M * cosLat;
      const dy = (lat - o.centerLat) * DEG2M;
      const r = Math.hypot(dx, dy);
      if (r > maxR) maxR = r;
    }
    if (maxR > 0) return maxR;
  }
  const diameterM = o.kind === 'arbre' ? o.crownDiameterM : (o.lengthM ?? o.widthM ?? o.crownDiameterM);
  return diameterM && diameterM > 0 ? diameterM / 2 : null;
}

/** Vrai quand l'objet a une HAUTEUR saisie mais AUCUNE emprise : il ne peut pas porter
 *  d'ombre tant que l'emprise n'est pas saisie — l'écran doit le dire. */
export function environmentNeedsFootprint(o: EnvironmentObject): boolean {
  if (!Number.isFinite(o.heightM) || (o.heightM as number) <= 0) return false;
  return environmentFootprintHalfWidthM(o) == null;
}

/**
 * CAL67 — convertit les objets d'environnement en obstructions ENU prêtes pour
 * `isSunBlocked`/`hourlyShadeFactors`/`pointSolarAccess` (même pipeline que les ombres
 * tracées et les obstacles de toiture, WJ19/CAL66). Un objet SANS `heightM` (ou ≤ 0) est
 * écarté : sans hauteur saisie, il ne porte aucune ombre — comportement identique à son
 * absence. Idem sans EMPRISE saisie (houppier, longueur/largeur ou polygone) : la
 * demi-largeur d'occultation est inconnue et n'est jamais remplacée par un repli.
 *
 * `roofHeightM` (CAL66/CAL67, branchement de l'ombrage vivant) : un arbre ou un bâtiment
 * voisin est posé au SOL, alors que les modules sont sur le TOIT — seule la part qui
 * DÉPASSE le plan du champ peut masquer le soleil, exactement la règle déjà appliquée
 * aux ombres tracées (`shadeObstructionsENU`). Un objet entièrement sous le niveau du
 * toit est donc écarté. La valeur par défaut 0 garde la géométrie brute (référentiel
 * sol), pour les appelants qui raisonnent au niveau du sol.
 */
export function environmentShadeEntries(
  list: readonly EnvironmentObject[],
  origin: LngLat,
  roofHeightM = 0,
): ShadeObstructionENU[] {
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  const roofH = Number.isFinite(roofHeightM) && roofHeightM > 0 ? roofHeightM : 0;
  const out: ShadeObstructionENU[] = [];
  for (const o of list) {
    if (!Number.isFinite(o.heightM) || (o.heightM as number) <= 0) continue;
    const eff = (o.heightM as number) - roofH;
    if (eff <= 0) continue;
    // CORRECTIF — aucune emprise saisie ⇒ aucune ombre (jamais une demi-largeur inventée).
    const halfWidthM = environmentFootprintHalfWidthM(o);
    if (halfWidthM == null) continue;
    const x = (o.centerLng - origin[0]) * DEG2M * cosLat;
    const y = (o.centerLat - origin[1]) * DEG2M;
    // CAL94 — empreinte RÉELLE en ENU (emprise saisie du bâtiment, houppier de l'arbre)
    // pour le lancer de rayon. L'emprise étant désormais obligatoire pour porter une
    // ombre, elle est toujours connue ici — jamais une forme inventée.
    const ring = environmentRing(o);
    const footprint = ring
      ? ring.map(([lng, lat]) => [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M] as [number, number])
      : undefined;
    out.push({
      x,
      y,
      effHeightM: eff,
      halfWidthM,
      ...(footprint ? { footprint } : {}),
    });
  }
  return out;
}

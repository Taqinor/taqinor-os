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
 * CAL67 — convertit les objets d'environnement en obstructions ENU prêtes pour
 * `isSunBlocked`/`hourlyShadeFactors`/`pointSolarAccess` (même pipeline que les ombres
 * tracées et les obstacles de toiture, WJ19/CAL66). Un objet SANS `heightM` (ou ≤ 0) est
 * écarté : sans hauteur saisie, il ne porte aucune ombre — comportement identique à son
 * absence.
 */
export function environmentShadeEntries(list: readonly EnvironmentObject[], origin: LngLat): ShadeObstructionENU[] {
  const cosLat = Math.max(1e-6, Math.cos(origin[1] * DEG2RAD));
  const out: ShadeObstructionENU[] = [];
  for (const o of list) {
    if (!Number.isFinite(o.heightM) || (o.heightM as number) <= 0) continue;
    const diameterM = o.kind === 'arbre' ? o.crownDiameterM : (o.lengthM ?? o.widthM ?? o.crownDiameterM);
    const halfWidthM = diameterM && diameterM > 0 ? diameterM / 2 : 1.5;
    out.push({
      x: (o.centerLng - origin[0]) * DEG2M * cosLat,
      y: (o.centerLat - origin[1]) * DEG2M,
      effHeightM: o.heightM as number,
      halfWidthM,
    });
  }
  return out;
}

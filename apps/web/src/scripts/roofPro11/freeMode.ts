/**
 * PV30 — PONT entre le pavage de l'optimiseur et le module PUR `lib/freeLayout.ts`.
 *
 * Rien de géométrique n'est décidé ici : on se contente de LIRE le plan gagnant (axes,
 * dimensions du panneau, contour, obstacles) et de le traduire dans la forme qu'attend
 * le module pur. Aucune dimension n'est ré-inventée — la largeur vient de
 * `grid.rowWidthM`, la profondeur au sol de `footprintPerPanelM2 / rowWidthM` (le
 * L·cos β que le pavage a réellement utilisé), les axes de `pack.azimuthDeg`.
 */
import { PERIMETER_SETBACK_M } from '../../lib/roofPro2';
import { obstacleRing, type Obstacle } from '../../lib/obstacles';
import { clearanceForType, type LayoutPlan } from './types';
import { DEG2M, DEG2RAD } from './constants';
import {
  geomAxes,
  freeStateFrom,
  type FreeGeom,
  type FreeMargins,
  type FreeLayoutState,
  type FreePanel,
  type Vec2,
} from '../../lib/freeLayout';

/**
 * ÉCART par défaut entre deux panneaux (m) — le jeu de pose d'une rangée du pavage
 * (2 cm). C'est la valeur de l'ÉTUDE, pas un chiffre de confort : le mode libre démarre
 * exactement là où l'optimiseur s'était arrêté, et c'est l'utilisateur qui décide ensuite
 * de la réduire (ou non).
 */
export const FREE_PANEL_GAP_M = 0.02;

/** Marges de départ du placement libre = celles de l'étude (retrait de rive 0,50 m,
 *  écart entre panneaux 2 cm). Baissables par l'utilisateur, jamais en douce. */
export const DEFAULT_FREE_MARGINS: FreeMargins = {
  setbackM: PERIMETER_SETBACK_M,
  gapM: FREE_PANEL_GAP_M,
};

/** Pas de STABILITÉ du glissé libre (m) : 1 cm. Assez fin pour « gagner un panneau »,
 *  assez grossier pour que deux glissés identiques donnent le même chiffre (et que le
 *  JSON enregistré ne porte pas 14 décimales de bruit). Ce n'est PAS une lattice : le
 *  panneau n'est contraint à aucune position pré-calculée. */
export const FREE_STEP_M = 0.01;

/** Quantifie une coordonnée sur le pas de stabilité. */
export function quantizeFree(v: number): number {
  return Math.round(v / FREE_STEP_M) * FREE_STEP_M;
}

/** lng/lat → ENU (m) dans le repère d'origine donné — la même projection que partout
 *  ailleurs dans l'outil (screenToENU, hydrateLayout…). */
function toEnu(lng: number, lat: number, origin: readonly [number, number]): Vec2 {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  return [(lng - origin[0]) * DEG2M * cosLat, (lat - origin[1]) * DEG2M];
}

/**
 * Contexte géométrique du placement libre pour le plan courant. `null` si le plan n'a
 * pas de quoi décrire un panneau (pavage vide) — l'appelant reste alors en lattice.
 */
export function freeGeomFrom(plan: LayoutPlan | null, obstacles: readonly Obstacle[]): FreeGeom | null {
  if (!plan) return null;
  const { grid, pack } = plan;
  const widthM = Number.isFinite(grid.rowWidthM) && grid.rowWidthM > 0 ? grid.rowWidthM : 0;
  // Profondeur AU SOL réellement employée par le pavage (L·cos β), relue de l'empreinte
  // plutôt que re-calculée : aucune trigonométrie dupliquée, donc aucune divergence.
  const depthM =
    widthM > 0 && Number.isFinite(grid.footprintPerPanelM2) && grid.footprintPerPanelM2 > 0
      ? grid.footprintPerPanelM2 / widthM
      : grid.slopeLenM * Math.cos((plan.tiltDeg || 0) * DEG2RAD);
  if (!(widthM > 0) || !(depthM > 0)) return null;
  const { u, s } = geomAxes(pack.azimuthDeg);
  const ringENU: Vec2[] = (pack.ringENU ?? []).map(([x, y]) => [x, y] as Vec2);
  const origin = pack.origin;
  const obs = obstacles.map((o) => ({
    ring: obstacleRing(o).map(([lng, lat]) => toEnu(lng, lat, origin)),
    clearanceM: clearanceForType(o.type),
  }));
  return { u, s, widthM, depthM, ringENU, obstacles: obs };
}

/** Bascule LATTICE → LIBRE : les panneaux posés gardent EXACTEMENT leur position (aucun
 *  re-snap, aucun recalcul) ; seule la règle qui les gouverne change. */
export function freeStateFromCenters(centers: readonly FreePanel[]): FreeLayoutState {
  return freeStateFrom(centers);
}

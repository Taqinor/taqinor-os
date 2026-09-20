/**
 * CAL84 — statistiques PAR PAN (modules, kWc, orientation, pente, surface utile, taux
 * d'occupation), totalisées par bâtiment (CAL59) puis par site. Géométrie PURE (aucun
 * Three, aucun DOM) : toutes les colonnes sont CALCULÉES depuis la géométrie/le résultat
 * déjà connus — rien n'est saisi ici, rien n'est inventé.
 */
import { geodesicAreaM2, PANEL_LENGTH_M, PANEL_WIDTH_M } from '../../lib/roof';
import { type AreaResult } from '../../lib/roofAreas';
import { type AreaRecord } from './types';

/** Surface au sol (m²) d'UN panneau — même constante physique que le reste de l'outil
 *  (PANEL_LENGTH_M × PANEL_WIDTH_M). Sert à CALCULER le taux d'occupation, jamais à
 *  dimensionner un pavage. */
export const PANEL_FOOTPRINT_M2 = PANEL_LENGTH_M * PANEL_WIDTH_M;

export interface PanStat {
  id: string;
  label: string;
  buildingId: string | null;
  panels: number;
  kwc: number;
  azimuthDeg: number | null;
  pitchDeg: number | null;
  /** Surface utile du pan (m²), déduite du contour tracé. 0 si aucun contour (< 3 sommets). */
  areaM2: number;
  /** Taux d'occupation (0–1) : surface au sol des panneaux posés / surface utile.
   *  null si le pan n'a pas de surface exploitable (division par zéro évitée). */
  occupancyRate: number | null;
  /** Motif d'un pan à ZÉRO panneau (jamais un total vide sans explication). '' si le
   *  pan porte des panneaux. */
  zeroReason: string;
}

export interface BuildingTotal {
  buildingId: string | null;
  panels: number;
  kwc: number;
  areaM2: number;
}

export interface PanStatsResult {
  pans: PanStat[];
  byBuilding: BuildingTotal[];
  site: BuildingTotal;
}

/** Une ligne par pan : `resultFor(a)` fournit le résultat (live pour la zone active,
 *  snapshot sinon) — injecté pour rester pur (aucun accès à `ctx` ici). */
export function computePanStats(areas: readonly AreaRecord[], resultFor: (a: AreaRecord) => AreaResult | null): PanStatsResult {
  const pans: PanStat[] = areas.map((a) => {
    const r = resultFor(a);
    const areaM2 = a.vertices.length >= 3 ? geodesicAreaM2(a.vertices) : 0;
    const panels = r?.panels ?? 0;
    const kwc = r?.kwc ?? 0;
    const occupancyRate = areaM2 > 0 ? (panels * PANEL_FOOTPRINT_M2) / areaM2 : null;
    let zeroReason = '';
    if (panels <= 0) {
      zeroReason = a.vertices.length < 3 ? 'toit non tracé' : r ? 'aucun panneau ne tient (obstacles/retraits)' : 'à calculer';
    }
    return {
      id: a.id,
      label: a.label,
      buildingId: a.buildingId ?? null,
      panels,
      kwc,
      azimuthDeg: a.roofType === 'pitched' ? a.facingAzimuthDeg : null,
      pitchDeg: a.roofType === 'pitched' ? a.pitchDeg : null,
      areaM2,
      occupancyRate,
      zeroReason,
    };
  });

  const groupKeys = Array.from(new Set(pans.map((p) => p.buildingId)));
  const byBuilding: BuildingTotal[] = groupKeys.map((buildingId) => {
    const rows = pans.filter((p) => p.buildingId === buildingId);
    return {
      buildingId,
      panels: rows.reduce((s, p) => s + p.panels, 0),
      kwc: rows.reduce((s, p) => s + p.kwc, 0),
      areaM2: rows.reduce((s, p) => s + p.areaM2, 0),
    };
  });

  const site: BuildingTotal = {
    buildingId: null,
    panels: pans.reduce((s, p) => s + p.panels, 0),
    kwc: pans.reduce((s, p) => s + p.kwc, 0),
    areaM2: pans.reduce((s, p) => s + p.areaM2, 0),
  };

  return { pans, byBuilding, site };
}

/** true si AU MOINS un pan porte un `buildingId` — sinon un seul groupe (site == le
 *  seul « bâtiment »), pas la peine d'afficher des sous-totaux redondants. */
export function hasMultipleBuildings(result: PanStatsResult): boolean {
  return result.byBuilding.length > 1 || (result.byBuilding.length === 1 && result.byBuilding[0].buildingId !== null);
}

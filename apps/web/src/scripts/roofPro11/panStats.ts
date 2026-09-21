/**
 * CAL84 — statistiques PAR PAN (modules, kWc, orientation, pente, surface utile, taux
 * d'occupation), totalisées par bâtiment (CAL59) puis par site. Géométrie PURE (aucun
 * Three, aucun DOM) : toutes les colonnes sont CALCULÉES depuis la géométrie/le résultat
 * déjà connus — rien n'est saisi ici, rien n'est inventé.
 */
import { geodesicAreaM2, PANEL_LENGTH_M, PANEL_WIDTH_M } from '../../lib/roof';
import { type AreaResult } from '../../lib/roofAreas';
import { type AreaRecord } from './types';
// CALX110 — le kWc d'un pan vient de SON module, et la mention « plusieurs modèles »
// est prononcée par la seule fonction qui sait la prononcer (`moduleSelect.ts`).
import {
  kwcDuPan,
  syntheseModules,
  type ModuleDocument,
  type SyntheseModules,
} from './moduleSelect';

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
  /** CALX110 — le modèle de module posé sur CE pan (`id` du catalogue), ou `null` quand
   *  le pan reste sur le module par défaut de l'atelier. Additif : une colonne de plus,
   *  jamais une colonne changée. */
  moduleId: string | null;
  /** CALX110 — son libellé, pour que l'écran NOMME le modèle au lieu d'un identifiant. */
  moduleLibelle: string | null;
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
  /** CALX110 — la synthèse des modèles posés sur le site : watt du modèle majoritaire,
   *  « plusieurs modèles » dès que les pans divergent, et la mention à afficher. Sans
   *  résolveur de module, elle décrit le module unique d'aujourd'hui. */
  modules: SyntheseModules;
}

/** Une ligne par pan : `resultFor(a)` fournit le résultat (live pour la zone active,
 *  snapshot sinon) — injecté pour rester pur (aucun accès à `ctx` ici).
 *
 *  CALX110 — `moduleFor` (OPTIONNEL) donne le module posé sur chaque pan. Absent, tout se
 *  comporte comme avant : le kWc reste celui du résultat de zone et l'empreinte celle du
 *  module unique. Présent, le kWc d'un pan vaut `nombre × puissance de SON module` — c'est
 *  ce qui empêche deux modèles de rendre le même kWc — et le taux d'occupation se mesure
 *  sur l'empreinte RÉELLE de ce module. Un module sans puissance ne fabrique aucun chiffre :
 *  le kWc du résultat de zone reste affiché tel quel. */
export function computePanStats(
  areas: readonly AreaRecord[],
  resultFor: (a: AreaRecord) => AreaResult | null,
  moduleFor?: (a: AreaRecord) => ModuleDocument | null,
): PanStatsResult {
  const modulesParPan: Record<string, string | undefined> = {};
  const catalogue: ModuleDocument[] = [];
  const pans: PanStat[] = areas.map((a) => {
    const r = resultFor(a);
    const areaM2 = a.vertices.length >= 3 ? geodesicAreaM2(a.vertices) : 0;
    const panels = r?.panels ?? 0;
    const modulePan = moduleFor?.(a) ?? null;
    if (modulePan) {
      modulesParPan[a.id] = modulePan.id;
      if (!catalogue.some((m) => m.id === modulePan.id)) catalogue.push(modulePan);
    }
    // CALX110 — la puissance de CE module fait foi ; si elle manque, on n'invente rien et
    // le chiffre déjà calculé pour la zone reste celui qui s'affiche.
    const kwc = (modulePan ? kwcDuPan(panels, modulePan) : null) ?? r?.kwc ?? 0;
    const empreinteM2 = modulePan && modulePan.longueurMm && modulePan.largeurMm
      ? (modulePan.longueurMm * modulePan.largeurMm) / 1e6
      : PANEL_FOOTPRINT_M2;
    const occupancyRate = areaM2 > 0 ? (panels * empreinteM2) / areaM2 : null;
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
      moduleId: modulePan?.id ?? null,
      moduleLibelle: modulePan?.libelle ?? null,
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

  // CALX110 — la mention affichée au-dessus des totaux : elle NOMME les modèles posés, et
  // dit « plusieurs modèles » dès que deux pans divergent. Le catalogue passé ici est celui
  // que les pans désignent vraiment (ordre de première apparition) — aucun modèle du stock
  // qui ne serait posé nulle part n'y entre.
  const modules = syntheseModules(
    { catalogue, parPan: modulesParPan },
    pans.map((p) => ({ id: p.id, panels: p.panels })),
  );

  return { pans, byBuilding, site, modules };
}

/** true si AU MOINS un pan porte un `buildingId` — sinon un seul groupe (site == le
 *  seul « bâtiment »), pas la peine d'afficher des sous-totaux redondants. */
export function hasMultipleBuildings(result: PanStatsResult): boolean {
  return result.byBuilding.length > 1 || (result.byBuilding.length === 1 && result.byBuilding[0].buildingId !== null);
}

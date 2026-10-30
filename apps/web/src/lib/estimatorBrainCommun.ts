/**
 * ENF19 — types PARTAGÉS des « cerveaux » d'estimation toit plat/incliné V3…V8.
 *
 * Les versions successives (V3, V4, V6, V7, V8) recopiaient la même liste de
 * champs de production dans chacune de leurs interfaces de résultat. Ce module
 * en est l'unique définition ; V4 ré-exporte `YieldFn` / `YieldSource` pour que
 * ses importeurs ne changent pas. Types seulement : aucun octet de JS émis.
 */

/** Rendement spécifique PVGIS au GPS exact : (tilt°, aspect PVGIS) → kWh/kWc/an,
 *  ou null si indisponible pour ce couple (la table committée prend le relais).
 *  Convention aspect : Sud=0, Est=−90, Ouest=+90, Nord=180. */
export type YieldFn = (tiltDeg: number, aspectDeg: number) => number | null;

/** Source du chiffre de production retenu. */
export type YieldSource = 'pvgis' | 'estimate';

/** Champs de production communs à toute configuration évaluée (plafonnée au besoin). */
export interface EvalProduction {
  /** Panneaux qui TIENNENT réellement à cette config (avant plafond besoin). */
  fitCount: number;
  /** Posés = min(besoin, fit) si besoin>0, sinon fit. */
  placedCount: number;
  kwc: number;
  /** Production annuelle (kWh, face avant) des panneaux POSÉS. */
  annualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  /** Rendement par panneau (kWh/kWc/an) — départage à énergie égale. */
  perPanelYield: number;
}

/** Idem, avec la source (PVGIS ou table) du chiffre de production. */
export interface EvalProductionSourced extends EvalProduction {
  yieldSource: YieldSource;
}

// — Logique PARTAGÉE de l'évaluation toit plat (V3 / V4) et du départage (V3/V4/V6/V7) —
import type { LngLat } from './roof';
import { PANEL2_WATT, packConfig, type ConfigFamily } from './estimatorBrainV2';
import type { AxisAzimuth, FlatConfig } from './estimatorBrainV3';

const EVAL_EPS = 1e-6;

/** Azimut de visée résolu pour un axe + famille, sur ce toit. Jamais inventé :
 *  ∈ {canonique famille, aligné arêtes}. Sud aligné = roofAz ; E-O aligné = roofAz−90. */
export function resolveAzimuthDeg(family: ConfigFamily, axis: AxisAzimuth, roofAz: number): number {
  if (axis === 'south') return family === 'eastwest' ? 90 : 180;
  return family === 'eastwest' ? (roofAz - 90 + 360) % 360 : roofAz;
}

/** Cache de pavage par (famille|tilt|azimut|setback) — réutilisé entre la recherche
 *  pleine et la recherche contrainte d'un même appel `reoptimize`. */
export function packCacheKey(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, setbackM: number): string {
  return `${family}|${tiltDeg}|${Math.round(azimuthDeg * 1000)}|${Math.round(setbackM * 1000)}`;
}

/** Pavage d'UNE config toit plat, plafonné au besoin — même physique que `packConfig` (V2).
 *  `head` = champs communs du résultat (azimut posé, retrait, comptes, kWc). */
export function packFlat(
  ring: LngLat[],
  latitudeDeg: number,
  cfg: FlatConfig,
  needed: number,
  roofAz: number,
  defaultSetbackM: number,
  obstructions: LngLat[][],
  cache?: Map<string, ReturnType<typeof packConfig>>,
) {
  const azimuthDeg = resolveAzimuthDeg(cfg.family, cfg.azimuth, roofAz);
  const setbackM = cfg.margin === 'keep' ? defaultSetbackM : 0;
  const key = cache ? packCacheKey(cfg.family, cfg.tiltDeg, azimuthDeg, setbackM) : '';
  let pack = cache?.get(key);
  if (!pack) {
    pack = packConfig(ring, latitudeDeg, {
      family: cfg.family,
      tiltDeg: cfg.tiltDeg,
      azimuthDeg,
      obstructions,
      setbackM,
    });
    cache?.set(key, pack);
  }
  const grid = cfg.orientation === 'portrait' ? pack.portrait : pack.landscape;
  const fitCount = grid.count;
  const placedCount = needed > 0 ? Math.min(needed, fitCount) : fitCount;
  const kwc = (placedCount * PANEL2_WATT) / 1000;
  return { pack, kwc, head: { azimuthDeg: pack.azimuthDeg, setbackM, fitCount, placedCount, kwc } };
}

/** Départage commun « a meilleure que b ? » : énergie posée, rendement/panneau, moins de
 *  matériel, garder la marge, Sud avant E-O. `undefined` = égalité sur ces critères. */
export function departageBase(
  a: { annualKwh: number; perPanelYield: number; placedCount: number; margin: string; family: string },
  b: { annualKwh: number; perPanelYield: number; placedCount: number; margin: string; family: string },
): boolean | undefined {
  if (a.annualKwh > b.annualKwh + EVAL_EPS) return true;
  if (a.annualKwh < b.annualKwh - EVAL_EPS) return false;
  if (a.perPanelYield !== b.perPanelYield) return a.perPanelYield > b.perPanelYield;
  if (a.placedCount !== b.placedCount) return a.placedCount < b.placedCount;
  if (a.margin !== b.margin) return a.margin === 'keep';
  if (a.family !== b.family) return a.family === 'south';
  return undefined;
}

/** Départage commun V6/V7 (suite de `departageBase`) : plus proche du plein sud, puis
 *  inclinaison plus raide. `undefined` = égalité (reste à départager sur l'orientation). */
export function departageAspect(
  a: { aspect: number; tiltDeg: number },
  b: { aspect: number; tiltDeg: number },
): boolean | undefined {
  const sa = Math.abs(a.aspect);
  const sb = Math.abs(b.aspect);
  if (Math.abs(sa - sb) > EVAL_EPS) return sa < sb;
  if (a.tiltDeg !== b.tiltDeg) return a.tiltDeg > b.tiltDeg;
  return undefined;
}

/** Champs de production d'une config évaluée, depuis une production sourcée (PVGIS/table). */
export function productionFields(
  prod: { kwh: number; perPanelYield: number; source: YieldSource },
  target: number,
  savings: { low: number; high: number },
) {
  return {
    annualKwh: prod.kwh,
    pctOfTarget: target > 0 ? (prod.kwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield: prod.perPanelYield,
    yieldSource: prod.source,
  };
}

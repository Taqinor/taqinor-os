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

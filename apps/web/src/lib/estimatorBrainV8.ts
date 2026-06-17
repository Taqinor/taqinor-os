/**
 * CERVEAU V8 de l'estimateur (preview privé /preview/toiture-3d-pro-11). Module PUR,
 * testé (tests/estimatorBrainV8.test.ts), sans DOM, sans carte, sans dépendance
 * nouvelle. COMPOSE sur V2 (production/économies) et V3 (pavage AFFLEURANT
 * `packFlushPlane`), SANS en modifier UN OCTET — pro-3..pro-10 restent intacts.
 *
 * V8 = l'OPTIMISEUR CONTRAINT VIVANT pour TOIT EN PENTE / TUILES, jumeau de V7 (toit
 * plat, W34) avec exactement DEUX différences imposées par la physique de la pose
 * affleurante :
 *
 *  1. PAS d'axe INCLINAISON — un panneau affleurant a pour inclinaison la PENTE du
 *     toit, fixée par la toiture (jamais optimisée).
 *  2. ORIENTATION verrouillée sur « aligné toit » — un panneau affleurant ne peut être
 *     tourné plein sud ni mis en tente Est-Ouest : ces orientations sont PHYSIQUEMENT
 *     impossibles ici (omises). L'azimut = la FACE du pan, fixée par la toiture.
 *
 *  Les axes LIBRES en pente sont donc : la POSE (portrait / paysage), la MARGE de rive
 *  (garder / pleine rive) et la cible « panneaux nécessaires ». Tout le reste est
 *  identique à V7 : verrouiller un axe le TIENT et re-résout les autres axes AUTO pour
 *  maximiser la génération ; les verrous s'accumulent ; chaque axe montre sa valeur
 *  « Recommandé » (axe libéré, autres verrous tenus) ; le plafond « besoin » est
 *  toujours respecté (posé = min(besoin, ce qui tient)).
 *
 *  PRODUCTION = PVGIS au SEUL couple (pente, face) pour le GPS EXACT, pose
 *  `mountingplace='building'` (affleurant → moins ventilé → rendement légèrement plus
 *  bas, honnête pour un toit hors sud / hors inclinaison optimale). Repli gracieux sur
 *  la table committée (« estimé ») si PVGIS est injoignable. JAMAIS un devis.
 */
import { type LngLat } from './roof';
import { PERIMETER_SETBACK_M } from './roofPro2';
import {
  PANEL2_WATT,
  type TariffGrid,
  annualSavingsMad,
  billToAnnualKwh,
  neededPanelsForTarget,
  tariffForCity,
} from './estimatorBrainV2';
import {
  flushPlaneYield,
  packFlushPlane,
  type AxisOrient,
  type FlushGrid,
  type FlushPack,
} from './estimatorBrainV3';
import { type YieldSource } from './estimatorBrainV6';

export { PANEL2_WATT };
export type { YieldSource };

const EVAL_EPS = 1e-6;

/** Pose des panneaux (axe libre). */
export type PitchedLayoutAxis = AxisOrient; // 'portrait' | 'landscape'
/** Marge de rive (axe libre). */
export type PitchedMarginAxis = 'keep' | 'remove';
/** Rendement spécifique PVGIS (kWh/kWc/an) du plan (pente, face), pose 'building'. */
export type PitchedYieldFn = (pitchDeg: number, facingAzimuthDeg: number) => number | null;

/** Verrous courants : axe absent = AUTO (re-résolu), axe présent = tenu fixe. */
export interface PitchedLocks {
  layout?: PitchedLayoutAxis;
  margin?: PitchedMarginAxis;
  need?: number;
}

export interface PitchedLiveEval {
  layout: PitchedLayoutAxis;
  margin: PitchedMarginAxis;
  fitCount: number;
  placedCount: number;
  kwc: number;
  annualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  perPanelYield: number;
  yieldSource: YieldSource;
  /** Pavage affleurant (pour le rendu 3D) et la grille de la pose retenue. */
  pack: FlushPack;
  grid: FlushGrid;
  layoutLabel: string;
  marginLabel: string;
  label: string;
}

const LAYOUT_FR: Record<PitchedLayoutAxis, string> = { portrait: 'portrait', landscape: 'paysage' };
const MARGIN_FR: Record<PitchedMarginAxis, string> = { keep: 'marge gardée', remove: 'pleine rive' };

/** Rendement résolu pour le plan (pente, face) : PVGIS si dispo/valide, sinon table. */
function resolvePitchedYield(
  yieldFn: PitchedYieldFn | undefined,
  latitudeDeg: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
): { value: number; source: YieldSource } {
  if (yieldFn) {
    const v = yieldFn(pitchDeg, facingAzimuthDeg);
    if (v != null && Number.isFinite(v) && v > 0) return { value: v, source: 'pvgis' };
  }
  return { value: flushPlaneYield(latitudeDeg, pitchDeg, facingAzimuthDeg), source: 'estimate' };
}

/**
 * `a` meilleure que `b` ? Énergie POSÉE d'abord (encode l'adéquation, plafonné au
 * besoin), puis moins de matériel, garder la marge, portrait. Départages déterministes.
 */
export function betterPitched(a: PitchedLiveEval, b: PitchedLiveEval): boolean {
  if (a.annualKwh > b.annualKwh + EVAL_EPS) return true;
  if (a.annualKwh < b.annualKwh - EVAL_EPS) return false;
  if (a.placedCount !== b.placedCount) return a.placedCount < b.placedCount;
  if (a.margin !== b.margin) return a.margin === 'keep';
  return a.layout === 'portrait' && b.layout !== 'portrait';
}

interface PitchedCtx {
  ring: LngLat[];
  latitudeDeg: number;
  pitchDeg: number;
  facingAzimuthDeg: number;
  target: number;
  effectiveNeed: number;
  obstructions: LngLat[][];
  tariff: TariffGrid;
  yieldFn: PitchedYieldFn | undefined;
  packCache: Map<string, FlushPack>;
}

function evalPitched(ctx: PitchedCtx, layout: PitchedLayoutAxis, margin: PitchedMarginAxis): PitchedLiveEval {
  const setbackM = margin === 'keep' ? PERIMETER_SETBACK_M : 0;
  const key = String(Math.round(setbackM * 1000));
  let pack = ctx.packCache.get(key);
  if (!pack) {
    pack = packFlushPlane(
      { ring: ctx.ring, pitchDeg: ctx.pitchDeg, facingAzimuthDeg: ctx.facingAzimuthDeg, obstructions: ctx.obstructions },
      { setbackM },
    );
    ctx.packCache.set(key, pack);
  }
  const grid = layout === 'portrait' ? pack.portrait : pack.landscape;
  const fitCount = grid.count;
  // Pan orienté nord : on ne pose RIEN (honnêteté — surplus nord non rentable).
  const placedCount = pack.northFacing ? 0 : ctx.effectiveNeed > 0 ? Math.min(ctx.effectiveNeed, fitCount) : fitCount;
  const perKwcPanel = grid.count > 0 ? grid.kwc / grid.count : PANEL2_WATT / 1000;
  const kwc = placedCount * perKwcPanel;
  const y = resolvePitchedYield(ctx.yieldFn, ctx.latitudeDeg, ctx.pitchDeg, ctx.facingAzimuthDeg);
  const annualKwh = kwc * y.value;
  const savings = annualSavingsMad(annualKwh, ctx.target, ctx.tariff);
  return {
    layout,
    margin,
    fitCount,
    placedCount,
    kwc,
    annualKwh,
    pctOfTarget: ctx.target > 0 ? (annualKwh / ctx.target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield: y.value,
    yieldSource: y.source,
    pack,
    grid,
    layoutLabel: LAYOUT_FR[layout],
    marginLabel: MARGIN_FR[margin],
    label: `Pente · ${LAYOUT_FR[layout]} · ${MARGIN_FR[margin]}`,
  };
}

function layoutCandidates(locked: PitchedLayoutAxis | undefined): PitchedLayoutAxis[] {
  return locked ? [locked] : ['portrait', 'landscape'];
}
function marginCandidates(locked: PitchedMarginAxis | undefined): PitchedMarginAxis[] {
  return locked ? [locked] : ['keep', 'remove'];
}

function solvePitchedConstrained(ctx: PitchedCtx, locks: PitchedLocks): { winner: PitchedLiveEval; rows: PitchedLiveEval[] } {
  let winner: PitchedLiveEval | null = null;
  const rows: PitchedLiveEval[] = [];
  for (const layout of layoutCandidates(locks.layout)) {
    for (const margin of marginCandidates(locks.margin)) {
      const e = evalPitched(ctx, layout, margin);
      rows.push(e);
      if (!winner || betterPitched(e, winner)) winner = e;
    }
  }
  return { winner: winner!, rows };
}

export interface PitchedSolveOptions {
  city?: string;
  /** Rendement spécifique PVGIS (kWh/kWc/an) du plan (pente, face), pose 'building'. */
  yieldFn?: PitchedYieldFn;
}

export interface PitchedLiveResult {
  target: number;
  neededPanels: number;
  effectiveNeed: number;
  pitchDeg: number;
  facingAzimuthDeg: number;
  offSouthDeg: number;
  northFacing: boolean;
  winner: PitchedLiveEval;
  globalWinner: PitchedLiveEval;
  recommended: {
    layout: PitchedLayoutAxis;
    margin: PitchedMarginAxis;
    need: number;
  };
  /** Espace libre évalué (≤ 4 configs : pose × marge) pour le tableau comparatif. */
  rows: PitchedLiveEval[];
  roofLimited: boolean;
}

/**
 * Résolution VIVANTE de l'optimiseur contraint EN PENTE. Mêmes règles que V7 (toit
 * plat) ; seuls axes libres : pose + marge (+ cible besoin). Inclinaison = pente,
 * azimut = face — imposés. Production PVGIS (pente, face) pose 'building', repli table.
 */
export function solveLivePitched(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
  obstructions: LngLat[][],
  locks: PitchedLocks,
  options: PitchedSolveOptions = {},
): PitchedLiveResult {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const neededPanels = neededPanelsForTarget(target, latitudeDeg);
  const lockedNeed = locks.need != null && locks.need > 0 ? Math.round(locks.need) : undefined;
  const effectiveNeed = lockedNeed ?? neededPanels;

  const ctx: PitchedCtx = {
    ring,
    latitudeDeg,
    pitchDeg,
    facingAzimuthDeg,
    target,
    effectiveNeed,
    obstructions,
    tariff,
    yieldFn: options.yieldFn,
    packCache: new Map<string, FlushPack>(),
  };

  const { winner, rows } = solvePitchedConstrained(ctx, locks);
  const offSouthDeg = winner.pack.offSouthDeg;
  const northFacing = winner.pack.northFacing;

  // Optimum GLOBAL = axes libres, besoin dérivé de la facture (cible de « Réinitialiser »).
  let globalWinner = winner;
  if (locks.layout || locks.margin || effectiveNeed !== neededPanels) {
    const globalCtx: PitchedCtx = { ...ctx, effectiveNeed: neededPanels, packCache: new Map() };
    globalWinner = solvePitchedConstrained(globalCtx, {}).winner;
  }

  // « Recommandé » par axe : libère CET axe en tenant l'AUTRE verrou courant.
  const freed = (drop: 'layout' | 'margin'): PitchedLiveEval =>
    solvePitchedConstrained(ctx, { ...locks, [drop]: undefined, need: locks.need }).winner;

  return {
    target,
    neededPanels,
    effectiveNeed,
    pitchDeg,
    facingAzimuthDeg,
    offSouthDeg,
    northFacing,
    winner,
    globalWinner,
    recommended: {
      layout: freed('layout').layout,
      margin: freed('margin').margin,
      need: neededPanels,
    },
    rows,
    roofLimited: !northFacing && effectiveNeed > 0 && winner.placedCount < effectiveNeed,
  };
}

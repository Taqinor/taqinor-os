/**
 * CERVEAU V7 de l'estimateur (preview privé /preview/toiture-3d-pro-10). Module PUR,
 * testé (tests/estimatorBrainV7.test.ts), sans DOM, sans carte, sans dépendance
 * nouvelle. COMPOSE sur V2 (calepinage + production) et V6 (grille d'inclinaison),
 * SANS en modifier UN OCTET — pro-3..pro-9 restent des baselines intactes.
 *
 * V7 = l'OPTIMISEUR CONTRAINT VIVANT pour TOIT PLAT. Là où pro-9 ne re-résolvait
 * qu'au clic sur « Optimum », V7 re-résout à CHAQUE changement d'option et fait
 * S'ACCUMULER les verrous :
 *
 *  - Chaque option visible est un AXE : orientation (plein sud / aligné toit /
 *    Est-Ouest), inclinaison (grille fine 0–35°), pose (portrait / paysage), marge de
 *    rive (garder / pleine rive) et la cible « panneaux nécessaires ».
 *  - État par défaut : TOUS les axes en AUTO → l'optimum global (chaque axe à sa
 *    meilleure valeur, marquée « Recommandé »).
 *  - VERROU : quand l'utilisateur fixe une valeur sur un axe, cet axe est VERROUILLÉ
 *    (« votre choix ») et on RE-RÉSOUT immédiatement tous les axes encore AUTO — en
 *    tenant chaque axe verrouillé fixe — pour MAXIMISER la génération annuelle totale.
 *  - Les verrous s'ACCUMULENT : un 2ᵉ verrou ne laisse flotter que les axes encore
 *    AUTO en tenant les DEUX ; etc.
 *  - « Recommandé » par axe = la valeur que CET axe prendrait s'il était libéré pendant
 *    que les autres verrous courants sont tenus — pour que l'utilisateur VOIE la valeur
 *    recommandée même quand il en choisit une autre, et ce qu'elle lui coûte.
 *
 *  « Génération la plus haute » = panneaux posés × kWc/panneau × le RENDEMENT SPÉCIFIQUE
 *  PVGIS (kWh/kWc/an) au GPS EXACT pour ce couple (inclinaison, azimut) — JAMAIS un
 *  facteur générique — avec panneaux posés = min(besoin, ce qui tient physiquement),
 *  donc le plafond « besoin » est TOUJOURS respecté (jamais sur-remplir un toit
 *  spacieux : le surplus n'est pas rémunéré au Maroc). Repli gracieux sur la table
 *  committée (« estimé ») si PVGIS est injoignable. JAMAIS un devis : une fourchette.
 */
import { type LngLat } from './roof';
import { PERIMETER_SETBACK_M } from './roofPro2';
import {
  PANEL2_WATT,
  type ConfigFamily,
  type PackResult,
  type TariffGrid,
  annualSavingsMad,
  aspectForAzimuth,
  billToAnnualKwh,
  neededPanelsForTarget,
  optimalSouthTiltDeg,
  packConfig,
  roofDominantAzimuthDeg,
  specificYield,
  tariffForCity,
} from './estimatorBrainV2';
import { matrixTiltGrid, type YieldFn, type YieldSource } from './estimatorBrainV6';

export { PANEL2_WATT };
export type { YieldFn, YieldSource };

const EVAL_EPS = 1e-6;
const round1 = (n: number) => Math.round(n * 10) / 10;
const norm360 = (a: number) => ((a % 360) + 360) % 360;

// ════════════════════════════ Axes & verrous ════════════════════════════

/** Orientation = ce que les puces proposent réellement (3 valeurs discrètes). */
export type OrientationAxis = 'south' | 'aligned' | 'eastwest';
/** Pose des panneaux. */
export type LayoutAxis = 'portrait' | 'landscape';
/** Marge de rive : garder le retrait, ou poser pleine rive. */
export type MarginAxis = 'keep' | 'remove';

/** Au-delà de ce décalage au sud (degrés), le toit est « tourné » et « aligné toit »
 *  devient un choix réel distinct de « plein sud ». */
export const ALIGNED_MIN_OFFSET_DEG = 2;

/**
 * Verrous courants : un axe ABSENT est AUTO (re-résolu), un axe PRÉSENT est tenu fixe.
 * `need` verrouille la cible de panneaux ; absent → cible dérivée de la facture.
 */
export interface AxisLocks {
  orientation?: OrientationAxis;
  tiltDeg?: number;
  layout?: LayoutAxis;
  margin?: MarginAxis;
  need?: number;
}

/** Une configuration évaluée (un point de l'espace d'axes), production PVGIS/estimé. */
export interface LiveConfigEval {
  orientation: OrientationAxis;
  family: ConfigFamily;
  /** Azimut de face réel (boussole) du pavage. */
  azimuthDeg: number;
  /** Aspect PVGIS (south: az−180 ; eastwest: az−90). */
  aspect: number;
  tiltDeg: number;
  layout: LayoutAxis;
  margin: MarginAxis;
  fitCount: number;
  placedCount: number;
  kwc: number;
  annualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  perPanelYield: number;
  yieldSource: YieldSource;
  orientationLabel: string;
  layoutLabel: string;
  label: string;
}

const ORIENT_FR: Record<OrientationAxis, string> = {
  south: 'plein sud',
  aligned: 'aligné toit',
  eastwest: 'Est-Ouest',
};
const LAYOUT_FR: Record<LayoutAxis, string> = { portrait: 'portrait', landscape: 'paysage' };

/** Rendement résolu pour un (tilt, aspect) : PVGIS si dispo/valide, sinon table. */
function resolveYield(
  yieldFn: YieldFn | undefined,
  latitudeDeg: number,
  tiltDeg: number,
  aspect: number,
): { value: number; source: YieldSource } {
  if (yieldFn) {
    const v = yieldFn(tiltDeg, aspect);
    if (v != null && Number.isFinite(v) && v > 0) return { value: v, source: 'pvgis' };
  }
  return { value: specificYield(latitudeDeg, tiltDeg, aspect), source: 'estimate' };
}

/**
 * `a` meilleure que `b` ? Énergie POSÉE d'abord (encode l'adéquation, tout plafonné au
 * besoin), puis rendement/panneau, moins de matériel, garder la marge, Sud avant E-O,
 * plus proche du plein sud, inclinaison plus raide, portrait. Départages déterministes —
 * JAMAIS de hasard (calque de `betterMatrixV6`). */
export function betterLive(a: LiveConfigEval, b: LiveConfigEval): boolean {
  if (a.annualKwh > b.annualKwh + EVAL_EPS) return true;
  if (a.annualKwh < b.annualKwh - EVAL_EPS) return false;
  if (a.perPanelYield !== b.perPanelYield) return a.perPanelYield > b.perPanelYield;
  if (a.placedCount !== b.placedCount) return a.placedCount < b.placedCount;
  if (a.margin !== b.margin) return a.margin === 'keep';
  if (a.family !== b.family) return a.family === 'south';
  const sa = Math.abs(a.aspect);
  const sb = Math.abs(b.aspect);
  if (Math.abs(sa - sb) > EVAL_EPS) return sa < sb;
  if (a.tiltDeg !== b.tiltDeg) return a.tiltDeg > b.tiltDeg;
  return a.layout === 'portrait' && b.layout !== 'portrait';
}

interface SolveCtx {
  ring: LngLat[];
  latitudeDeg: number;
  target: number;
  effectiveNeed: number;
  obstructions: LngLat[][];
  defaultSetbackM: number;
  tariff: TariffGrid;
  yieldFn: YieldFn | undefined;
  roofAz: number;
  cache: Map<string, PackResult>;
}

/** (family, azimuthDeg) candidats pour une valeur d'orientation. E-O essaie l'azimut
 *  plein (90°) ET l'azimut aligné toit, et garde le meilleur. */
function familyAzes(orientation: OrientationAxis, roofAz: number): { family: ConfigFamily; azimuthDeg: number }[] {
  if (orientation === 'eastwest') {
    return [
      { family: 'eastwest', azimuthDeg: 90 },
      { family: 'eastwest', azimuthDeg: round1(norm360(roofAz - 90)) },
    ];
  }
  if (orientation === 'aligned') return [{ family: 'south', azimuthDeg: round1(norm360(roofAz)) }];
  return [{ family: 'south', azimuthDeg: 180 }];
}

function evalOne(
  ctx: SolveCtx,
  orientation: OrientationAxis,
  family: ConfigFamily,
  azimuthDeg: number,
  tiltDeg: number,
  layout: LayoutAxis,
  margin: MarginAxis,
): LiveConfigEval {
  const setbackM = margin === 'keep' ? ctx.defaultSetbackM : 0;
  const key = `${family}|${tiltDeg}|${Math.round(azimuthDeg * 1000)}|${Math.round(setbackM * 1000)}`;
  let pack = ctx.cache.get(key);
  if (!pack) {
    pack = packConfig(ctx.ring, ctx.latitudeDeg, { family, tiltDeg, azimuthDeg, obstructions: ctx.obstructions, setbackM });
    ctx.cache.set(key, pack);
  }
  const grid = layout === 'portrait' ? pack.portrait : pack.landscape;
  const fitCount = grid.count;
  const placedCount = ctx.effectiveNeed > 0 ? Math.min(ctx.effectiveNeed, fitCount) : fitCount;
  const kwc = (placedCount * PANEL2_WATT) / 1000;
  const aspect = aspectForAzimuth(family, pack.azimuthDeg);
  let annualKwh: number;
  let perPanelYield: number;
  let source: YieldSource;
  if (family === 'eastwest') {
    const e = resolveYield(ctx.yieldFn, ctx.latitudeDeg, tiltDeg, aspect - 90);
    const w = resolveYield(ctx.yieldFn, ctx.latitudeDeg, tiltDeg, aspect + 90);
    annualKwh = (kwc / 2) * e.value + (kwc / 2) * w.value;
    perPanelYield = (e.value + w.value) / 2;
    source = e.source === 'pvgis' && w.source === 'pvgis' ? 'pvgis' : 'estimate';
  } else {
    const s = resolveYield(ctx.yieldFn, ctx.latitudeDeg, tiltDeg, aspect);
    annualKwh = kwc * s.value;
    perPanelYield = s.value;
    source = s.source;
  }
  const savings = annualSavingsMad(annualKwh, ctx.target, ctx.tariff);
  const orientationLabel = ORIENT_FR[orientation];
  return {
    orientation,
    family,
    azimuthDeg: pack.azimuthDeg,
    aspect,
    tiltDeg,
    layout,
    margin,
    fitCount,
    placedCount,
    kwc,
    annualKwh,
    pctOfTarget: ctx.target > 0 ? (annualKwh / ctx.target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield,
    yieldSource: source,
    orientationLabel,
    layoutLabel: LAYOUT_FR[layout],
    label: `${tiltDeg}° · ${orientationLabel} · ${LAYOUT_FR[layout]}`,
  };
}

/** Meilleure éval pour une valeur d'orientation (E-O départage ses deux azimuts). */
function bestForOrientation(
  ctx: SolveCtx,
  orientation: OrientationAxis,
  tiltDeg: number,
  layout: LayoutAxis,
  margin: MarginAxis,
): LiveConfigEval {
  let best: LiveConfigEval | null = null;
  for (const { family, azimuthDeg } of familyAzes(orientation, ctx.roofAz)) {
    const e = evalOne(ctx, orientation, family, azimuthDeg, tiltDeg, layout, margin);
    if (!best || betterLive(e, best)) best = e;
  }
  return best!;
}

/** Valeurs candidates d'un axe : la valeur verrouillée seule, sinon le balayage complet. */
function orientationCandidates(ctx: SolveCtx, locked: OrientationAxis | undefined, turned: boolean): OrientationAxis[] {
  if (locked) return [locked];
  return turned ? ['south', 'aligned', 'eastwest'] : ['south', 'eastwest'];
}
function tiltCandidates(ctx: SolveCtx, locked: number | undefined): number[] {
  if (locked != null) return [locked];
  return matrixTiltGrid(ctx.latitudeDeg);
}
function layoutCandidates(locked: LayoutAxis | undefined): LayoutAxis[] {
  return locked ? [locked] : ['portrait', 'landscape'];
}
function marginCandidates(locked: MarginAxis | undefined): MarginAxis[] {
  return locked ? [locked] : ['keep', 'remove'];
}

/** Re-résolution CONTRAINTE : tient chaque axe verrouillé fixe, balaie les axes AUTO,
 *  renvoie le gagnant (max d'énergie POSÉE, plafonnée au besoin). */
function solveConstrained(ctx: SolveCtx, locks: AxisLocks, turned: boolean): LiveConfigEval {
  let winner: LiveConfigEval | null = null;
  for (const orientation of orientationCandidates(ctx, locks.orientation, turned)) {
    for (const tiltDeg of tiltCandidates(ctx, locks.tiltDeg)) {
      for (const layout of layoutCandidates(locks.layout)) {
        for (const margin of marginCandidates(locks.margin)) {
          const e = bestForOrientation(ctx, orientation, tiltDeg, layout, margin);
          if (!winner || betterLive(e, winner)) winner = e;
        }
      }
    }
  }
  return winner!;
}

export interface LiveSolveOptions {
  city?: string;
  /** Rendement spécifique PVGIS injecté (sinon table committée seule). */
  yieldFn?: YieldFn;
}

export interface LiveSolveResult {
  /** Besoin énergétique annuel (kWh) déduit de la facture. */
  target: number;
  /** Panneaux nécessaires dérivés de la facture (la valeur « Recommandé » du besoin). */
  neededPanels: number;
  /** Besoin EFFECTIF utilisé (verrou `need` sinon `neededPanels`). */
  effectiveNeed: number;
  roofAlignedAzimuthDeg: number;
  offSouthDeg: number;
  /** Le toit est-il assez tourné pour que « aligné toit » soit un choix réel ? */
  hasAlignedChoice: boolean;
  /** Gagnant CONTRAINT (axes verrouillés tenus, axes AUTO re-résolus). */
  winner: LiveConfigEval;
  /** Gagnant GLOBAL (tous axes libres, besoin = facture) — l'état « Réinitialiser ». */
  globalWinner: LiveConfigEval;
  /** Valeur « Recommandé » par axe = la valeur de l'axe libéré, autres verrous tenus. */
  recommended: {
    orientation: OrientationAxis;
    tiltDeg: number;
    layout: LayoutAxis;
    margin: MarginAxis;
    need: number;
  };
  /** Toit limité : le gagnant ne loge pas le besoin entier. */
  roofLimited: boolean;
}

/**
 * Résolution VIVANTE de l'optimiseur contraint. Donne le gagnant contraint par les
 * verrous courants, l'optimum global (réinitialisation), et la valeur recommandée par
 * axe (axe libéré, autres verrous tenus). PVGIS = source de vérité via `options.yieldFn`,
 * repli table « estimé ». Pur, déterministe, sans état caché.
 */
export function solveLive(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][],
  locks: AxisLocks,
  options: LiveSolveOptions = {},
): LiveSolveResult {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const neededPanels = neededPanelsForTarget(target, latitudeDeg);
  const lockedNeed = locks.need != null && locks.need > 0 ? Math.round(locks.need) : undefined;
  const effectiveNeed = lockedNeed ?? neededPanels;
  const roofAz = roofDominantAzimuthDeg(ring);
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const hasAlignedChoice = Math.abs(offSouthDeg) >= ALIGNED_MIN_OFFSET_DEG;

  const ctx: SolveCtx = {
    ring,
    latitudeDeg,
    target,
    effectiveNeed,
    obstructions,
    defaultSetbackM: PERIMETER_SETBACK_M,
    tariff,
    yieldFn: options.yieldFn,
    roofAz,
    cache: new Map<string, PackResult>(),
  };

  // Verrous géométriques courants (sans le besoin, porté par effectiveNeed).
  const geomLocks: AxisLocks = {
    orientation: locks.orientation,
    tiltDeg: locks.tiltDeg,
    layout: locks.layout,
    margin: locks.margin,
  };

  const winner = solveConstrained(ctx, geomLocks, hasAlignedChoice);

  // Optimum GLOBAL = tous axes libres, besoin dérivé de la facture.
  let globalWinner = winner;
  if (Object.values(geomLocks).some((v) => v != null) || effectiveNeed !== neededPanels) {
    const globalCtx: SolveCtx = { ...ctx, effectiveNeed: neededPanels, cache: new Map() };
    globalWinner = solveConstrained(globalCtx, {}, hasAlignedChoice);
  }

  // « Recommandé » par axe : libère CET axe en tenant les AUTRES verrous courants.
  const freed = (drop: keyof AxisLocks): LiveConfigEval =>
    solveConstrained(ctx, { ...geomLocks, [drop]: undefined }, hasAlignedChoice);

  const recommended = {
    orientation: freed('orientation').orientation,
    tiltDeg: freed('tiltDeg').tiltDeg,
    layout: freed('layout').layout,
    margin: freed('margin').margin,
    need: neededPanels, // libérer le besoin → couvrir la facture
  };

  return {
    target,
    neededPanels,
    effectiveNeed,
    roofAlignedAzimuthDeg: roofAz,
    offSouthDeg,
    hasAlignedChoice,
    winner,
    globalWinner,
    recommended,
    roofLimited: effectiveNeed > 0 && winner.placedCount < effectiveNeed,
  };
}

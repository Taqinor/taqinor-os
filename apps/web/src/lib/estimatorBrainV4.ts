/**
 * CERVEAU V4 de l'estimateur piloté par la facture (preview privé
 * /preview/toiture-3d-pro-7). Module PUR, testé (tests/estimatorBrainV4.test.ts) :
 * aucun DOM, aucune carte, aucune dépendance nouvelle. COMPOSE sur V2/V3
 * (src/lib/estimatorBrainV2.ts, estimatorBrainV3.ts) sans les modifier d'un octet —
 * pro-3/pro-4/pro-5/pro-6 restent des baselines intactes.
 *
 * Ce que V4 AJOUTE par rapport au plein-balayage de V3 :
 *
 *  1. PVGIS = SOURCE DE VÉRITÉ DE LA PRODUCTION. La recherche du vrai optimum ne se
 *     fait plus sur le seul rendement de la table committée, mais sur le rendement
 *     SPÉCIFIQUE (kWh/kWc/an) lu sur PVGIS au GPS EXACT du toit, injecté via une
 *     fonction `YieldFn(tilt, aspect)`. Le rendement spécifique est INDÉPENDANT de
 *     la taille du système : on l'interroge une fois par (tilt, aspect), puis on
 *     met à l'échelle par kWc. Quand PVGIS ne répond pas pour un (tilt, aspect),
 *     on retombe gracieusement sur la table committée (rendu « estimé »).
 *
 *  2. BALAYAGE EN GRILLE FINE. On balaie l'inclinaison par pas d'environ 5° jusqu'à
 *     ~35° (pas seulement 2-3 presets), l'azimut {plein sud, aligné toit, Est-Ouest}
 *     en portrait ET paysage, marge gardée/retirée — chaque config plafonnée au
 *     besoin et notée sur l'énergie POSÉE (qui encode l'adéquation au besoin). Le
 *     VRAI maximum est retenu, même s'il ne correspond à AUCUNE ligne standard du
 *     tableau.
 *
 *  3. OPTIMUM COMME SA PROPRE LIGNE. Quand l'optimum calculé n'est pas une config
 *     standard du tableau, on le décrit comme une ligne à part (« Optimum calculé —
 *     inclinaison X°, orientation Y ») avec une raison en une phrase et la SOURCE du
 *     chiffre (pvgis | estimé).
 *
 * L'espace de RECHERCHE (riche) reste découplé du TABLEAU affiché (court, lisible).
 * Le pavage réutilise EXACTEMENT `packConfig` de V2 — aucune fork du chemin toit
 * plat. JAMAIS un devis : une fourchette indicative. Voir apps/web/BRAIN_V4_NOTES.md.
 */
import { type LngLat } from './roof';
import { PERIMETER_SETBACK_M } from './roofPro2';
import {
  PANEL2_WATT,
  type ConfigFamily,
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
import type { AxisAzimuth, AxisOrient, AxisMargin, FlatConfig } from './estimatorBrainV3';

export type { AxisAzimuth, AxisOrient, AxisMargin, FlatConfig } from './estimatorBrainV3';
export { PANEL2_WATT };

const EVAL_EPS = 1e-6;

/** Rendement spécifique PVGIS au GPS exact : (tilt°, aspect PVGIS) → kWh/kWc/an,
 *  ou null si indisponible pour ce couple (la table committée prend le relais).
 *  Convention aspect : Sud=0, Est=−90, Ouest=+90, Nord=180. */
export type YieldFn = (tiltDeg: number, aspectDeg: number) => number | null;

/** Source du chiffre de production retenu. */
export type YieldSource = 'pvgis' | 'estimate';

/**
 * Mappe un azimut BOUSSOLE (0=N, 90=E, 180=S, 270=O) vers l'aspect PVGIS
 * (Sud=0, Est=−90, Ouest=+90, Nord=180). Un mauvais signe corrompt silencieusement
 * la production — d'où le test dédié. Normalisé dans (−180, 180], Nord → +180.
 */
export function aspectFromCompass(azimuthDeg: number): number {
  let a = ((azimuthDeg - 180) % 360 + 360) % 360; // [0, 360)
  if (a > 180) a -= 360; // (−180, 180]
  return a === -180 ? 180 : a;
}

/**
 * Jambes PVGIS d'une config : Sud = une jambe (aspect = azimut−180) ; Est-Ouest =
 * deux jambes (base = azimut−90, puis base∓90). `kwc` réparti par jambe. Sert au
 * page-script à savoir QUOI interroger ; identique à la logique pro-5/pro-6.
 */
export function pvgisLegs(
  family: ConfigFamily,
  tiltDeg: number,
  azimuthDeg: number,
  kwc: number,
): { kwc: number; tiltDeg: number; aspect: number }[] {
  if (family === 'eastwest') {
    const base = azimuthDeg - 90;
    return [
      { kwc: kwc / 2, tiltDeg, aspect: base - 90 },
      { kwc: kwc / 2, tiltDeg, aspect: base + 90 },
    ];
  }
  return [{ kwc, tiltDeg, aspect: azimuthDeg - 180 }];
}

/** Grille fine d'inclinaisons toit plat (pas ~5° jusqu'à ~35°), + l'optimum Sud de
 *  la table pour ne jamais rater le pic. Bornée [5, 35]. */
export function fineTiltGrid(latitudeDeg: number): number[] {
  const base = [5, 10, 15, 20, 25, 30, 35];
  const opt = optimalSouthTiltDeg(latitudeDeg);
  const set = new Set(base);
  if (opt >= 5 && opt <= 35) set.add(opt);
  return [...set].sort((a, b) => a - b);
}

/** Inclinaisons Est-Ouest candidates (l'E-O joue déjà la densité). */
const EW_TILTS = [10, 12, 15] as const;

function resolveAzimuthDeg(family: ConfigFamily, axis: AxisAzimuth, roofAz: number): number {
  if (axis === 'south') return family === 'eastwest' ? 90 : 180;
  return family === 'eastwest' ? (roofAz - 90 + 360) % 360 : roofAz;
}

/**
 * Couples (tilt°, aspect PVGIS) que l'optimiseur va RÉELLEMENT interroger sur ce
 * toit — exactement ceux des jambes des configs balayées. Le page-script préfetch
 * leur rendement spécifique (kWc=1) au GPS exact, met en cache, et bâtit `YieldFn`.
 * Garde page et moteur synchronisés (mêmes aspects, même grille).
 */
export function pvgisCandidatePairs(
  latitudeDeg: number,
  roofAz: number,
  forceAligned = false,
): { tiltDeg: number; aspect: number }[] {
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const aligned = forceAligned || Math.abs(offSouthDeg) >= 2;
  const southTilts = fineTiltGrid(latitudeDeg);
  const out = new Map<string, { tiltDeg: number; aspect: number }>();
  const add = (t: number, a: number) => out.set(`${t}|${Math.round(a * 10) / 10}`, { tiltDeg: t, aspect: Math.round(a * 10) / 10 });
  const axes: AxisAzimuth[] = aligned ? ['south', 'aligned'] : ['south'];
  for (const axis of axes) {
    const southAz = axis === 'south' ? 180 : roofAz;
    for (const t of southTilts) for (const leg of pvgisLegs('south', t, southAz, 1)) add(t, leg.aspect);
    const ewAz = axis === 'south' ? 90 : (roofAz - 90 + 360) % 360;
    for (const t of EW_TILTS) for (const leg of pvgisLegs('eastwest', t, ewAz, 1)) add(t, leg.aspect);
  }
  return [...out.values()];
}

/** Rendement résolu pour un (tilt, aspect) : PVGIS si dispo et valide, sinon table. */
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

/** Production annuelle (kWh) d'une config via la source PVGIS (repli table). */
function configProduction(
  family: ConfigFamily,
  tiltDeg: number,
  azimuthDeg: number,
  kwc: number,
  yieldFn: YieldFn | undefined,
  latitudeDeg: number,
): { kwh: number; perPanelYield: number; source: YieldSource } {
  const aspect = aspectForAzimuth(family, azimuthDeg);
  if (family === 'eastwest') {
    const e = resolveYield(yieldFn, latitudeDeg, tiltDeg, aspect - 90);
    const w = resolveYield(yieldFn, latitudeDeg, tiltDeg, aspect + 90);
    const perPanelYield = (e.value + w.value) / 2;
    return {
      kwh: (kwc / 2) * e.value + (kwc / 2) * w.value,
      perPanelYield,
      source: e.source === 'pvgis' && w.source === 'pvgis' ? 'pvgis' : 'estimate',
    };
  }
  const s = resolveYield(yieldFn, latitudeDeg, tiltDeg, aspect);
  return { kwh: kwc * s.value, perPanelYield: s.value, source: s.source };
}

export interface FlatEvalV4 extends FlatConfig {
  azimuthDeg: number;
  setbackM: number;
  fitCount: number;
  placedCount: number;
  kwc: number;
  annualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  perPanelYield: number;
  yieldSource: YieldSource;
}

export function evalFlatConfigV4(
  ring: LngLat[],
  latitudeDeg: number,
  cfg: FlatConfig,
  needed: number,
  target: number,
  obstructions: LngLat[][],
  roofAz: number,
  defaultSetbackM: number,
  tariff: TariffGrid,
  yieldFn: YieldFn | undefined,
  cache?: Map<string, ReturnType<typeof packConfig>>,
): FlatEvalV4 {
  const azimuthDeg = resolveAzimuthDeg(cfg.family, cfg.azimuth, roofAz);
  const setbackM = cfg.margin === 'keep' ? defaultSetbackM : 0;
  const key = cache ? `${cfg.family}|${cfg.tiltDeg}|${Math.round(azimuthDeg * 1000)}|${Math.round(setbackM * 1000)}` : '';
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
  const prod = configProduction(cfg.family, cfg.tiltDeg, pack.azimuthDeg, kwc, yieldFn, latitudeDeg);
  const savings = annualSavingsMad(prod.kwh, target, tariff);
  return {
    ...cfg,
    azimuthDeg: pack.azimuthDeg,
    setbackM,
    fitCount,
    placedCount,
    kwc,
    annualKwh: prod.kwh,
    pctOfTarget: target > 0 ? (prod.kwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield: prod.perPanelYield,
    yieldSource: prod.source,
  };
}

/** `a` meilleure que `b` ? Énergie posée d'abord (encode l'adéquation, tout est
 *  plafonné au besoin), puis rendement/panneau, puis moins de matériel, garder la
 *  marge, Sud avant E-O, inclinaison plus raide, portrait. Départages déterministes. */
export function betterFlatV4(a: FlatEvalV4, b: FlatEvalV4): boolean {
  if (a.annualKwh > b.annualKwh + EVAL_EPS) return true;
  if (a.annualKwh < b.annualKwh - EVAL_EPS) return false;
  if (a.perPanelYield !== b.perPanelYield) return a.perPanelYield > b.perPanelYield;
  if (a.placedCount !== b.placedCount) return a.placedCount < b.placedCount;
  if (a.margin !== b.margin) return a.margin === 'keep';
  if (a.family !== b.family) return a.family === 'south';
  if (a.tiltDeg !== b.tiltDeg) return a.tiltDeg > b.tiltDeg;
  return a.orientation === 'portrait' && b.orientation !== 'portrait';
}

export interface FineGridOptions {
  city?: string;
  /** Rendement spécifique PVGIS injecté (sinon table committée seule). */
  yieldFn?: YieldFn;
  /** Ouvre l'axe aligné-toit même si le toit est ~aligné (tests). */
  forceAligned?: boolean;
}

export interface OptimumRow {
  /** Étiquette de la ligne « Optimum calculé — inclinaison X°, orientation Y ». */
  label: string;
  /** Raison en une phrase (français), traçable. */
  reason: string;
  /** L'optimum coïncide-t-il avec une config standard du tableau ? */
  isStandard: boolean;
  /** Source du chiffre de production retenu. */
  yieldSource: YieldSource;
}

export interface OptimumV4Result {
  targetAnnualKwh: number;
  neededPanels: number;
  roofAlignedAzimuthDeg: number;
  offSouthDeg: number;
  roofLimited: boolean;
  winner: FlatEvalV4;
  recommendedOptions: FlatConfig;
  /** Description « ligne à part » de l'optimum (label + raison + source). */
  optimumRow: OptimumRow;
  /** Configs réellement évaluées (info / découplage tableau). */
  evaluated: number;
  /** Source globale de la recommandation (pvgis dès qu'un chiffre PVGIS a servi). */
  yieldSource: YieldSource;
}

const ORIENT_FR: Record<AxisOrient, string> = { portrait: 'portrait', landscape: 'paysage' };

function familyAzimuthLabel(e: FlatEvalV4): string {
  if (e.family === 'eastwest') return e.azimuth === 'aligned' ? 'Est-Ouest aligné toit' : 'Est-Ouest';
  return e.azimuth === 'aligned' ? `orienté toit (${Math.round(e.azimuthDeg)}°)` : 'plein sud';
}

/** L'optimum est-il une config « standard » du tableau ? (Sud, plein sud, marge
 *  gardée, inclinaison ∈ presets standard). Sinon → ligne à part. */
function isStandardConfig(e: FlatEvalV4, standardTilts: number[]): boolean {
  if (e.family !== 'south') return false;
  if (e.azimuth !== 'south') return false;
  if (e.margin !== 'keep') return false;
  return standardTilts.some((t) => Math.abs(t - e.tiltDeg) < 0.5);
}

/**
 * Recherche le VRAI optimum en grille fine, production PVGIS au GPS exact (repli
 * table). Le gagnant est le maximum d'énergie POSÉE sur tout le produit cartésien,
 * plafonné au besoin. C'est ce que le bouton « Optimum » applique sans épingle.
 */
export function fineGridOptimum(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  options: FineGridOptions = {},
): OptimumV4Result {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const needed = neededPanelsForTarget(target, latitudeDeg);
  const roofAz = roofDominantAzimuthDeg(ring);
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const aligned = options.forceAligned === true || Math.abs(offSouthDeg) >= 2;
  const setback = PERIMETER_SETBACK_M;
  const southTilts = fineTiltGrid(latitudeDeg);
  const azimuths: AxisAzimuth[] = aligned ? ['south', 'aligned'] : ['south'];
  const orientations: AxisOrient[] = ['portrait', 'landscape'];
  const margins: AxisMargin[] = ['keep', 'remove'];
  const cache = new Map<string, ReturnType<typeof packConfig>>();

  let winner: FlatEvalV4 | null = null;
  let count = 0;
  let anyPvgis = false;
  for (const family of ['south', 'eastwest'] as ConfigFamily[]) {
    const tilts = family === 'eastwest' ? [...EW_TILTS] : southTilts;
    for (const tiltDeg of tilts) {
      for (const azimuth of azimuths) {
        for (const margin of margins) {
          for (const orientation of orientations) {
            const e = evalFlatConfigV4(
              ring,
              latitudeDeg,
              { family, tiltDeg, azimuth, orientation, margin },
              needed,
              target,
              obstructions,
              roofAz,
              setback,
              tariff,
              options.yieldFn,
              cache,
            );
            count++;
            if (e.yieldSource === 'pvgis') anyPvgis = true;
            if (!winner || betterFlatV4(e, winner)) winner = e;
          }
        }
      }
    }
  }
  const w = winner!;
  const optTilt = optimalSouthTiltDeg(latitudeDeg);
  const standardTilts = [optTilt, 29, 15, 10];
  const isStd = isStandardConfig(w, standardTilts);
  const pct = Math.round(w.pctOfTarget);
  const reason = w.family === 'eastwest'
    ? `Sur ce toit tourné, l'Est-Ouest dos à dos loge ${w.placedCount} panneaux et couvre ~${pct} % du besoin — plus d'énergie totale que le plein sud.`
    : w.azimuth === 'aligned'
      ? `Aligner les rangées sur les arêtes du toit (${Math.round(w.azimuthDeg)}°) loge ${w.placedCount} panneaux et couvre ~${pct} % du besoin.`
      : `À ${w.tiltDeg}° plein sud, ${w.placedCount} panneaux couvrent ~${pct} % du besoin avec le meilleur rendement par panneau.`;
  return {
    targetAnnualKwh: target,
    neededPanels: needed,
    roofAlignedAzimuthDeg: roofAz,
    offSouthDeg,
    roofLimited: needed > 0 && w.placedCount < needed,
    winner: w,
    recommendedOptions: {
      family: w.family,
      tiltDeg: w.tiltDeg,
      azimuth: w.azimuth,
      orientation: w.orientation,
      margin: w.margin,
    },
    optimumRow: {
      label: `Optimum calculé — ${w.tiltDeg}°, ${familyAzimuthLabel(w)}, ${ORIENT_FR[w.orientation]}`,
      reason,
      isStandard: isStd,
      yieldSource: anyPvgis ? 'pvgis' : 'estimate',
    },
    evaluated: count,
    yieldSource: anyPvgis ? 'pvgis' : 'estimate',
  };
}

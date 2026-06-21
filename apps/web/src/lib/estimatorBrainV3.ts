/**
 * CERVEAU V3 de l'estimateur piloté par la facture (preview privé
 * /preview/toiture-3d-pro-6). Module PUR, testé (tests/estimatorBrainV3.test.ts) :
 * aucun DOM, aucune carte, aucune dépendance nouvelle. COMPOSE sur le cerveau V2
 * (src/lib/estimatorBrainV2.ts) sans le modifier d'un octet — pro-3/pro-4/pro-5
 * restent des baselines intactes. V3 N'AJOUTE que :
 *
 *  1. RECHERCHE PLEINE (`fullSearchOptimum`) : au lieu de comparer une poignée de
 *     lignes, on balaie le PRODUIT cartésien (famille × inclinaison fine × azimut
 *     {plein sud, aligné toit} × calepinage {portrait, paysage} × marge {garder,
 *     retirer}), chaque config évaluée PLAFONNÉE au besoin, et on retient le VRAI
 *     gagnant (énergie posée + adéquation au besoin). L'espace de RECHERCHE (riche)
 *     est découplé du TABLEAU affiché (qui reste court et lisible). Réutilise la
 *     physique de pavage de V2 (`packConfig`) — aucune fork du chemin toit plat.
 *
 *  2. RÉ-OPTIMISATION CONTRAINTE (`reoptimize`) : on FIGE les axes épinglés par
 *     l'utilisateur (ex. inclinaison 15°, ou Est-Ouest forcé) et on re-résout TOUS
 *     les autres au mieux sous cette contrainte. Le badge « Recommandé » de chaque
 *     groupe reste celui de l'optimum GLOBAL (sans épingle), donc l'utilisateur voit
 *     toujours qu'il a choisi une option mais qu'une autre est recommandée.
 *
 *  3. MODÈLE TOIT EN PENTE / TUILES (`packFlushPlane`, `recommendPitched`) : un
 *     SECOND modèle de toit où les panneaux sont posés AFFLEURANTS sur la pente.
 *     Physique exacte : l'inclinaison de l'array = la PENTE du toit, l'azimut de
 *     l'array = la FACE du pan — tous deux IMPOSÉS par la toiture (lecture seule,
 *     jamais balayés). Des panneaux coplanaires sur un même pan ne s'auto-ombrent
 *     pas → AUCUN pas inter-rangées solaire : tuile bord à bord moins un petit jeu
 *     de maintenance/sécurité (FLUSH_MAINTENANCE_GAP_M). Ça loge bien plus qu'un
 *     toit plat de même surface. La production par pan vient de PVGIS à
 *     l'inclinaison + l'azimut RÉELS du pan (table committée, déjà dans la stack).
 *     Multi-pans : on place sur les pans utiles seulement et on SAUTE/SIGNALE un pan
 *     orienté nord. Plafond besoin, plafond économies et « dimensionner au besoin »
 *     s'appliquent à l'identique.
 *
 * La pente NE PEUT PAS être mesurée sur l'imagerie marocaine (satellite top-down
 * uniquement ; pas de vols aériens ni de Street View exploitable — Aurora/Project
 * Sunroof s'appuient sur du LiDAR + photogrammétrie HD, sinon repli sur tracé
 * manuel + pente saisie). La pente est donc SAISIE par l'utilisateur, jamais devinée.
 *
 * JAMAIS un devis : une fourchette indicative. Voir apps/web/BRAIN_V3_NOTES.md.
 */
import { geodesicAreaM2, geodesicPerimeterM, pointInPolygon, type LngLat } from './roof';
import { PANEL2_LONG_M, PANEL2_SHORT_M, PERIMETER_SETBACK_M } from './roofPro2';
import {
  PANEL2_WATT,
  REGIE_TARIFF,
  type ConfigFamily,
  type TariffGrid,
  aspectForAzimuth,
  annualSavingsMad,
  billToAnnualKwh,
  neededPanelsForTarget,
  obstructionOverlapM2,
  optimalSouthTiltDeg,
  packConfig,
  productionKwh,
  roofDominantAzimuthDeg,
  specificYield,
  tariffForCity,
  TILT_SWEEP_MIN,
  TILT_SWEEP_STEP,
  OBSTACLE_CLEARANCE_M,
} from './estimatorBrainV2';

export { PANEL2_WATT };

const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;
const MAX_CELLS = 200000;
const PANEL_SIDE_GAP_M = 0.02;
const EDGE_EPS_M = 1e-3;
const EVAL_EPS = 1e-6;

/** Inclinaisons E-O candidates de la recherche pleine (l'E-O joue déjà la densité). */
const EW_SWEEP_TILTS = [10, 12, 15] as const;

// ════════════════════════════════════════════════════════════════════════
// 1 + 2 — RECHERCHE PLEINE & RÉ-OPTIMISATION CONTRAINTE (toit plat)
// ════════════════════════════════════════════════════════════════════════

export type AxisAzimuth = 'south' | 'aligned';
export type AxisOrient = 'portrait' | 'landscape';
export type AxisMargin = 'keep' | 'remove';

/** Une configuration toit-plat complète sur les 5 axes optimisés. */
export interface FlatConfig {
  family: ConfigFamily;
  tiltDeg: number;
  azimuth: AxisAzimuth;
  orientation: AxisOrient;
  margin: AxisMargin;
}

/** Évaluation PLAFONNÉE d'une config toit-plat sur ce toit (physique = V2). */
export interface FlatConfigEval extends FlatConfig {
  /** Azimut de visée résolu (180 = plein sud ; sinon aligné sur les arêtes). */
  azimuthDeg: number;
  setbackM: number;
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

/** Épingles utilisateur pour la ré-optimisation contrainte. Axe absent = libre. */
export interface FlatPins {
  family?: ConfigFamily;
  tiltDeg?: number;
  azimuth?: AxisAzimuth;
  orientation?: AxisOrient;
  margin?: AxisMargin;
}

export interface FullSearchOptions {
  city?: string;
  /** Force le balayage aligné-toit même sur un toit ~aligné (tests). Par défaut
   *  on n'ouvre l'axe « aligné » que si le toit est franchement tourné (≥2°). */
  forceAligned?: boolean;
}

export interface OptimumResult {
  targetAnnualKwh: number;
  neededPanels: number;
  roofAlignedAzimuthDeg: number;
  offSouthDeg: number;
  roofLimited: boolean;
  /** Le VRAI gagnant de la recherche pleine (ce sur quoi « Optimum » se cale). */
  winner: FlatConfigEval;
  /** Recommandation par groupe = axes du gagnant GLOBAL (badges « Recommandé »). */
  recommendedOptions: FlatConfig;
  /** Nombre de configurations réellement évaluées (info / découplage tableau). */
  evaluated: number;
}

export interface ReoptimizeResult {
  /** Gagnant CONTRAINT (respecte les épingles) — ce sur quoi les contrôles se calent. */
  winner: FlatConfigEval;
  /** Gagnant GLOBAL non contraint — sert les badges « Recommandé ». */
  recommendedOptions: FlatConfig;
  globalWinner: FlatConfigEval;
  targetAnnualKwh: number;
  neededPanels: number;
}

/** Azimut de visée résolu pour un axe + famille, sur ce toit. Jamais inventé :
 *  ∈ {canonique famille, aligné arêtes}. Sud aligné = roofAz ; E-O aligné = roofAz−90. */
function resolveAzimuthDeg(family: ConfigFamily, axis: AxisAzimuth, roofAz: number): number {
  if (axis === 'south') return family === 'eastwest' ? 90 : 180;
  return family === 'eastwest' ? (roofAz - 90 + 360) % 360 : roofAz;
}

/** Cache de pavage par (famille|tilt|azimut|setback) — réutilisé entre la recherche
 *  pleine et la recherche contrainte d'un même appel `reoptimize`. */
function packCacheKey(family: ConfigFamily, tiltDeg: number, azimuthDeg: number, setbackM: number): string {
  return `${family}|${tiltDeg}|${Math.round(azimuthDeg * 1000)}|${Math.round(setbackM * 1000)}`;
}

/**
 * Évalue UNE config toit-plat, plafonnée au besoin, en réutilisant EXACTEMENT la
 * physique de pavage de V2 (`packConfig`). Aucune fork : le chemin toit plat reste
 * celui de pro-5.
 */
export function evalFlatConfig(
  ring: LngLat[],
  latitudeDeg: number,
  cfg: FlatConfig,
  needed: number,
  target: number,
  obstructions: LngLat[][],
  roofAz: number,
  defaultSetbackM: number,
  tariff: TariffGrid,
  cache?: Map<string, ReturnType<typeof packConfig>>,
): FlatConfigEval {
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
  const aspect = aspectForAzimuth(cfg.family, pack.azimuthDeg);
  const annualKwh = productionKwh(latitudeDeg, cfg.family, cfg.tiltDeg, kwc, aspect);
  const perPanelYield =
    cfg.family === 'eastwest'
      ? (specificYield(latitudeDeg, cfg.tiltDeg, aspect - 90) + specificYield(latitudeDeg, cfg.tiltDeg, aspect + 90)) / 2
      : specificYield(latitudeDeg, cfg.tiltDeg, aspect);
  const savings = annualSavingsMad(annualKwh, target, tariff);
  return {
    ...cfg,
    azimuthDeg: pack.azimuthDeg,
    setbackM,
    fitCount,
    placedCount,
    kwc,
    annualKwh,
    pctOfTarget: target > 0 ? (annualKwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield,
  };
}

/**
 * `a` est-il une MEILLEURE config que `b` ? Critère principal : plus d'énergie
 * POSÉE (qui encode déjà l'adéquation au besoin, puisque tout est plafonné au
 * besoin). Départages déterministes : meilleur rendement/panneau (config plus
 * « propre »), puis MOINS de matériel à énergie égale, puis garder la marge, puis
 * Sud avant Est-Ouest (mono-MPPT), puis inclinaison plus raide, puis portrait.
 */
export function betterFlat(a: FlatConfigEval, b: FlatConfigEval): boolean {
  if (a.annualKwh > b.annualKwh + EVAL_EPS) return true;
  if (a.annualKwh < b.annualKwh - EVAL_EPS) return false;
  if (a.perPanelYield !== b.perPanelYield) return a.perPanelYield > b.perPanelYield;
  if (a.placedCount !== b.placedCount) return a.placedCount < b.placedCount;
  if (a.margin !== b.margin) return a.margin === 'keep';
  if (a.family !== b.family) return a.family === 'south';
  if (a.tiltDeg !== b.tiltDeg) return a.tiltDeg > b.tiltDeg;
  return a.orientation === 'portrait' && b.orientation !== 'portrait';
}

interface AxisChoices {
  families: ConfigFamily[];
  azimuths: AxisAzimuth[];
  orientations: AxisOrient[];
  margins: AxisMargin[];
  southTilts: number[];
  ewTilts: number[];
}

/** Liste des inclinaisons Sud balayées finement (TILT_SWEEP_MIN..optimal, pas fin). */
function southTiltSweep(latitudeDeg: number): number[] {
  const optTilt = optimalSouthTiltDeg(latitudeDeg);
  const tilts: number[] = [];
  for (let t = TILT_SWEEP_MIN; t <= optTilt; t += TILT_SWEEP_STEP) tilts.push(t);
  if (tilts[tilts.length - 1] !== optTilt) tilts.push(optTilt);
  return tilts;
}

function enumerateFlat(
  ring: LngLat[],
  latitudeDeg: number,
  needed: number,
  target: number,
  obstructions: LngLat[][],
  roofAz: number,
  defaultSetbackM: number,
  tariff: TariffGrid,
  axes: AxisChoices,
  cache: Map<string, ReturnType<typeof packConfig>>,
): { winner: FlatConfigEval; count: number } {
  let winner: FlatConfigEval | null = null;
  let count = 0;
  for (const family of axes.families) {
    const tilts = family === 'eastwest' ? axes.ewTilts : axes.southTilts;
    for (const tiltDeg of tilts) {
      for (const azimuth of axes.azimuths) {
        for (const margin of axes.margins) {
          for (const orientation of axes.orientations) {
            const e = evalFlatConfig(
              ring,
              latitudeDeg,
              { family, tiltDeg, azimuth, orientation, margin },
              needed,
              target,
              obstructions,
              roofAz,
              defaultSetbackM,
              tariff,
              cache,
            );
            count++;
            if (!winner || betterFlat(e, winner)) winner = e;
          }
        }
      }
    }
  }
  return { winner: winner!, count };
}

/** Axes complets de la recherche pleine, selon le toit (azimut aligné ouvert si tourné). */
function fullAxes(latitudeDeg: number, roofAz: number, forceAligned: boolean): AxisChoices {
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const aligned = forceAligned || Math.abs(offSouthDeg) >= 2;
  return {
    families: ['south', 'eastwest'],
    azimuths: aligned ? ['south', 'aligned'] : ['south'],
    orientations: ['portrait', 'landscape'],
    margins: ['keep', 'remove'],
    southTilts: southTiltSweep(latitudeDeg),
    ewTilts: [...EW_SWEEP_TILTS],
  };
}

function pinnedAxes(base: AxisChoices, pins: FlatPins): AxisChoices {
  return {
    families: pins.family ? [pins.family] : base.families,
    azimuths: pins.azimuth ? [pins.azimuth] : base.azimuths,
    orientations: pins.orientation ? [pins.orientation] : base.orientations,
    margins: pins.margin ? [pins.margin] : base.margins,
    // Une inclinaison épinglée fige l'axe (valeur exacte du curseur), sinon balayage.
    southTilts: pins.tiltDeg != null ? [pins.tiltDeg] : base.southTilts,
    ewTilts: pins.tiltDeg != null ? [pins.tiltDeg] : base.ewTilts,
  };
}

function toFlatConfig(e: FlatConfigEval): FlatConfig {
  return {
    family: e.family,
    tiltDeg: e.tiltDeg,
    azimuth: e.azimuth,
    orientation: e.orientation,
    margin: e.margin,
  };
}

/**
 * RECHERCHE PLEINE : le vrai optimum sur tout le produit cartésien d'axes, plafonné
 * au besoin. C'est ce que le bouton « Optimum » applique quand rien n'est épinglé.
 */
export function fullSearchOptimum(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  options: FullSearchOptions = {},
): OptimumResult {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const needed = neededPanelsForTarget(target, latitudeDeg);
  const roofAz = roofDominantAzimuthDeg(ring);
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const defaultSetbackM = PERIMETER_SETBACK_M;
  const axes = fullAxes(latitudeDeg, roofAz, options.forceAligned === true);
  const cache = new Map<string, ReturnType<typeof packConfig>>();
  const { winner, count } = enumerateFlat(
    ring,
    latitudeDeg,
    needed,
    target,
    obstructions,
    roofAz,
    defaultSetbackM,
    tariff,
    axes,
    cache,
  );
  return {
    targetAnnualKwh: target,
    neededPanels: needed,
    roofAlignedAzimuthDeg: roofAz,
    offSouthDeg,
    roofLimited: needed > 0 && winner.placedCount < needed,
    winner,
    recommendedOptions: toFlatConfig(winner),
    evaluated: count,
  };
}

/**
 * RÉ-OPTIMISATION CONTRAINTE : fige les axes épinglés, re-résout les autres au
 * mieux. Les badges « Recommandé » suivent l'optimum GLOBAL (sans épingle), donc
 * restent corrects quel que soit le choix de l'utilisateur.
 */
export function reoptimize(
  pins: FlatPins,
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  options: FullSearchOptions = {},
): ReoptimizeResult {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const needed = neededPanelsForTarget(target, latitudeDeg);
  const roofAz = roofDominantAzimuthDeg(ring);
  const defaultSetbackM = PERIMETER_SETBACK_M;
  const base = fullAxes(latitudeDeg, roofAz, options.forceAligned === true);
  const cache = new Map<string, ReturnType<typeof packConfig>>();

  const global = enumerateFlat(ring, latitudeDeg, needed, target, obstructions, roofAz, defaultSetbackM, tariff, base, cache);
  const constrained = enumerateFlat(
    ring,
    latitudeDeg,
    needed,
    target,
    obstructions,
    roofAz,
    defaultSetbackM,
    tariff,
    pinnedAxes(base, pins),
    cache,
  );
  return {
    winner: constrained.winner,
    recommendedOptions: toFlatConfig(global.winner),
    globalWinner: global.winner,
    targetAnnualKwh: target,
    neededPanels: needed,
  };
}

// ════════════════════════════════════════════════════════════════════════
// 3 — MODÈLE TOIT EN PENTE / TUILES (pose affleurante, multi-pans)
// ════════════════════════════════════════════════════════════════════════

/** Presets de pente tuile marocains (réglables côté écran). */
export const PITCH_PRESETS_DEG = [15, 22, 30] as const;
/** Jeu de maintenance/sécurité incendie entre rangées affleurantes (m, en plan).
 *  CE N'EST PAS un pas de rangée solaire : des panneaux coplanaires ne s'ombrent
 *  pas. C'est uniquement un passage d'accès. */
export const FLUSH_MAINTENANCE_GAP_M = 0.15;
/** Au-delà de cet écart au sud (deg), une face est trop au nord → pan non retenu. */
export const NORTH_FACING_OFFSOUTH_DEG = 90;

/** Un pan de toiture en pente : tracé + pente saisie + face (azimut) saisie. */
export interface RoofPlane {
  ring: LngLat[];
  /** Pente du pan (deg), SAISIE — non mesurable sur l'imagerie marocaine. */
  pitchDeg: number;
  /** Azimut de la face / sens de la pente descendante (0=N, 90=E, 180=S, 270=O). */
  facingAzimuthDeg: number;
  obstructions?: LngLat[][];
}

export interface FlushGrid {
  orientation: AxisOrient;
  count: number;
  kwc: number;
  panels: { cx: number; cy: number }[];
  /** Pas de rangée appliqué (m, en plan) = empreinte plan + jeu de maintenance. */
  rowPitchM: number;
  /** Empreinte EN PLAN d'un panneau (m²) = (longueur·cos pente) × largeur. */
  footprintPerPanelM2: number;
}

export interface FlushPack {
  origin: LngLat;
  ringENU: [number, number][];
  areaM2: number;
  usableAreaM2: number;
  pitchDeg: number;
  /** Azimut imposé par la toiture (= face du pan), JAMAIS choisi ni balayé. */
  facingAzimuthDeg: number;
  /** Écart au sud de la face (deg) — sert l'aspect PVGIS et le test nord. */
  offSouthDeg: number;
  northFacing: boolean;
  portrait: FlushGrid;
  landscape: FlushGrid;
  best: FlushGrid;
}

function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  }
  return min;
}

/** Écart signé au sud (deg) d'un azimut de face : 180=plein sud → 0. */
function offSouth(facingAzimuthDeg: number): number {
  return ((facingAzimuthDeg - 180 + 540) % 360) - 180;
}

interface FlushCellParams {
  panelPlanDepthM: number;
  rowPitchM: number;
  rowWidthM: number;
}

/**
 * Pave des panneaux AFFLEURANTS sur un pan en pente. Le pas de rangée EN PLAN est
 * l'empreinte plan + un petit jeu de maintenance — PAS d'ombre solaire (panneaux
 * coplanaires). Les coins de chaque empreinte doivent être DANS le tracé et à au
 * moins `setbackM` de la rive ; les obstacles (+ dégagement) retirent un panneau
 * dont le centre tombe dedans.
 */
function packFlushCells(
  ringENU: [number, number][],
  obstructionsENU: [number, number][][],
  azimuthDeg: number,
  setbackM: number,
  p: FlushCellParams,
  clearanceM: number,
  overhangM = 0,
): { cx: number; cy: number }[] {
  if (ringENU.length < 3) return [];
  const azRad = azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
  const s = f; // empilement des rangées vers le bas de la pente (la face)
  const u: [number, number] = [-f[1], f[0]]; // axe long des rangées

  const ringUV = ringENU.map(([x, y]) => [x * u[0] + y * u[1], x * s[0] + y * s[1]] as [number, number]);
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }

  const colPitch = p.rowWidthM + PANEL_SIDE_GAP_M;
  // W108 — débord : fenêtre de balayage étendue d'un nombre ENTIER de pas de chaque
  // côté (phase du lattice inchangée → panneaux intérieurs identiques). overhangM=0
  // → ohRows=ohCols=0 → calepinage identique à aujourd'hui.
  const ohRows = overhangM > 0 ? Math.ceil(overhangM / p.rowPitchM) : 0;
  const ohCols = overhangM > 0 ? Math.ceil(overhangM / colPitch) : 0;
  const rows = Math.floor((vMax - vMin) / p.rowPitchM) + 2 * ohRows;
  const cols = Math.floor((uMax - uMin) / colPitch) + 2 * ohCols;
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) return [];

  const toENU = (uu: number, vv: number): [number, number] => [uu * u[0] + vv * s[0], uu * u[1] + vv * s[1]];
  const inObstruction = (c: [number, number]): boolean =>
    obstructionsENU.some((o) => pointInPolygon(c, o) || distToBoundary(c, o) <= clearanceM);
  // W108 — distance SIGNÉE au bord (+ dedans, − dehors) : un coin tient s'il est à
  // au moins `setbackM` à l'intérieur OU déborde d'au plus `overhangM`. overhangM=0
  // → équivaut exactement à l'ancienne règle (dedans/pile-rive ET retrait).
  const cellInside = (corners: [number, number][]): boolean =>
    corners.every((c) => {
      const d = distToBoundary(c, ringENU);
      const sd = pointInPolygon(c, ringENU) ? d : -d;
      return sd >= setbackM - overhangM - EDGE_EPS_M;
    });

  const vStart = vMin + setbackM - ohRows * p.rowPitchM;
  const uStart = uMin + setbackM - ohCols * colPitch;
  const panels: { cx: number; cy: number }[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vStart + r * p.rowPitchM;
    const v1 = v0 + p.panelPlanDepthM;
    if (v1 > vMax - setbackM + overhangM + EDGE_EPS_M) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uStart + c * colPitch;
      const u1 = u0 + p.rowWidthM;
      const corners: [number, number][] = [toENU(u0, v0), toENU(u1, v0), toENU(u1, v1), toENU(u0, v1)];
      if (!cellInside(corners)) continue;
      const center = toENU(u0 + p.rowWidthM / 2, v0 + p.panelPlanDepthM / 2);
      if (inObstruction(center)) continue;
      panels.push({ cx: center[0], cy: center[1] });
    }
  }
  return panels;
}

/**
 * Pave UN pan en pente, en portrait ET paysage, garde le meilleur. L'inclinaison =
 * la pente du pan, l'azimut = la face du pan — imposés, jamais balayés.
 */
export function packFlushPlane(plane: RoofPlane, opts: { setbackM?: number; clearanceM?: number; overhangM?: number } = {}): FlushPack {
  const { ring, pitchDeg, facingAzimuthDeg } = plane;
  const areaM2 = geodesicAreaM2(ring);
  const setbackM = opts.setbackM ?? PERIMETER_SETBACK_M;
  const clearanceM = opts.clearanceM ?? OBSTACLE_CLEARANCE_M;
  // W108 — débord autorisé des panneaux au-delà de la rive (rails sur le toit).
  const overhangM = Math.max(0, opts.overhangM ?? 0);
  const beta = pitchDeg * DEG2RAD;
  const obstructions = plane.obstructions ?? [];
  // W108 — borne « Σ empreintes ≤ utile » élargie de l'anneau de débord (Minkowski).
  const overhangRingM2 = overhangM > 0 ? geodesicPerimeterM(ring) * overhangM + Math.PI * overhangM * overhangM : 0;
  const usableAreaM2 = Math.max(0, areaM2 + overhangRingM2 - obstructionOverlapM2(ring, obstructions, areaM2));
  const off = offSouth(facingAzimuthDeg);
  const northFacing = Math.abs(off) > NORTH_FACING_OFFSOUTH_DEG;

  const buildGrid = (orientation: AxisOrient, slopeLenM: number, rowWidthM: number, ringENU: [number, number][], obsENU: [number, number][][]): FlushGrid => {
    const panelPlanDepthM = slopeLenM * Math.cos(beta);
    const rowPitchM = panelPlanDepthM + FLUSH_MAINTENANCE_GAP_M;
    const panels = packFlushCells(ringENU, obsENU, facingAzimuthDeg, setbackM, { panelPlanDepthM, rowPitchM, rowWidthM }, clearanceM, overhangM);
    return {
      orientation,
      count: panels.length,
      kwc: (panels.length * PANEL2_WATT) / 1000,
      panels,
      rowPitchM,
      footprintPerPanelM2: panelPlanDepthM * rowWidthM,
    };
  };

  const emptyGrid = (orientation: AxisOrient, slopeLenM: number, rowWidthM: number): FlushGrid => {
    const panelPlanDepthM = slopeLenM * Math.cos(beta);
    return {
      orientation,
      count: 0,
      kwc: 0,
      panels: [],
      rowPitchM: panelPlanDepthM + FLUSH_MAINTENANCE_GAP_M,
      footprintPerPanelM2: panelPlanDepthM * rowWidthM,
    };
  };

  if (!Array.isArray(ring) || ring.length < 3) {
    const portrait = emptyGrid('portrait', PANEL2_LONG_M, PANEL2_SHORT_M);
    const landscape = emptyGrid('landscape', PANEL2_SHORT_M, PANEL2_LONG_M);
    return {
      origin: ring?.[0] ?? [0, 0],
      ringENU: [],
      areaM2,
      usableAreaM2,
      pitchDeg,
      facingAzimuthDeg,
      offSouthDeg: off,
      northFacing,
      portrait,
      landscape,
      best: portrait,
    };
  }

  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  const cosLat = Math.cos(olat * DEG2RAD);
  const toENU = ([lng, lat]: LngLat): [number, number] => [(lng - olng) * DEG2M * cosLat, (lat - olat) * DEG2M];
  const ringENU = ring.map(toENU);
  const obsENU = obstructions.map((o) => o.map(toENU));

  // Portrait : grand côté (2,384) dans le sens de la pente. Paysage : l'inverse.
  const portrait = buildGrid('portrait', PANEL2_LONG_M, PANEL2_SHORT_M, ringENU, obsENU);
  const landscape = buildGrid('landscape', PANEL2_SHORT_M, PANEL2_LONG_M, ringENU, obsENU);
  const best = portrait.count >= landscape.count ? portrait : landscape;

  return {
    origin: [olng, olat],
    ringENU,
    areaM2,
    usableAreaM2,
    pitchDeg,
    facingAzimuthDeg,
    offSouthDeg: off,
    northFacing,
    portrait,
    landscape,
    best,
  };
}

/** Rendement par panneau (kWh/kWc/an) d'un pan : PVGIS à SA pente + SA face. */
export function flushPlaneYield(latitudeDeg: number, pitchDeg: number, facingAzimuthDeg: number): number {
  return specificYield(latitudeDeg, pitchDeg, offSouth(facingAzimuthDeg));
}

export interface PitchedPlaneResult {
  index: number;
  pitchDeg: number;
  facingAzimuthDeg: number;
  offSouthDeg: number;
  northFacing: boolean;
  /** Panneaux qui TIENNENT sur ce pan (orientation best). */
  fitCount: number;
  /** Posés sur ce pan après plafond besoin partagé entre pans. */
  placedCount: number;
  orientation: AxisOrient;
  perPanelYield: number;
  kwc: number;
  annualKwh: number;
  /** Motif si le pan est ignoré (nord, ou besoin déjà couvert). */
  skipped?: 'north' | 'need-met' | 'no-fit';
  pack: FlushPack;
}

export interface PitchedRecommendation {
  targetAnnualKwh: number;
  neededPanels: number;
  /** Pans réellement retenus (au moins 1 panneau posé). */
  planes: PitchedPlaneResult[];
  totalPlacedCount: number;
  totalKwc: number;
  totalAnnualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  roofLimited: boolean;
  /** Pans signalés non retenus (ex. orientés nord) — honnêteté. */
  skippedNorth: number;
}

/**
 * Recommandation TOIT EN PENTE multi-pans. On classe les pans par rendement/panneau
 * (meilleure face/pente d'abord), on SAUTE les pans orientés nord, puis on remplit
 * du meilleur pan au moins bon jusqu'à couvrir le BESOIN (plafond partagé) — jamais
 * au-delà. Production = somme par pan à SON PVGIS réel ; économies plafonnées au
 * coût énergie évitable (mêmes règles que le toit plat).
 */
export function recommendPitched(
  planes: RoofPlane[],
  latitudeDeg: number,
  monthlyBillMad: number,
  options: { city?: string; setbackM?: number } = {},
): PitchedRecommendation {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const needed = neededPanelsForTarget(target, latitudeDeg);

  // Évalue chaque pan : pavage affleurant + rendement réel. On garde l'orientation
  // qui loge le plus (best).
  const evaluated = planes.map((plane, index): PitchedPlaneResult => {
    const pack = packFlushPlane(plane, { setbackM: options.setbackM });
    const perPanelYield = flushPlaneYield(latitudeDeg, plane.pitchDeg, plane.facingAzimuthDeg);
    return {
      index,
      pitchDeg: plane.pitchDeg,
      facingAzimuthDeg: plane.facingAzimuthDeg,
      offSouthDeg: pack.offSouthDeg,
      northFacing: pack.northFacing,
      fitCount: pack.best.count,
      placedCount: 0,
      orientation: pack.best.orientation,
      perPanelYield,
      kwc: 0,
      annualKwh: 0,
      pack,
    };
  });

  // Pans utilisables = orientés au moins est/ouest et qui logent au moins un panneau.
  // Tri par rendement/panneau décroissant (la meilleure face/pente sert le besoin
  // en premier).
  const usable = evaluated
    .filter((p) => !p.northFacing && p.fitCount > 0)
    .sort((a, b) => b.perPanelYield - a.perPanelYield);

  let remaining = needed > 0 ? needed : Infinity;
  for (const p of usable) {
    if (remaining <= 0) {
      p.skipped = 'need-met';
      continue;
    }
    const take = needed > 0 ? Math.min(remaining, p.fitCount) : p.fitCount;
    p.placedCount = take;
    p.kwc = (take * PANEL2_WATT) / 1000;
    p.annualKwh = p.kwc * p.perPanelYield;
    remaining -= take;
  }
  for (const p of evaluated) {
    if (p.northFacing) p.skipped = 'north';
    else if (p.fitCount === 0) p.skipped = 'no-fit';
  }

  const used = evaluated.filter((p) => p.placedCount > 0);
  const totalPlacedCount = used.reduce((s, p) => s + p.placedCount, 0);
  const totalKwc = used.reduce((s, p) => s + p.kwc, 0);
  const totalAnnualKwh = used.reduce((s, p) => s + p.annualKwh, 0);
  const savings = annualSavingsMad(totalAnnualKwh, target, tariff);

  return {
    targetAnnualKwh: target,
    neededPanels: needed,
    planes: evaluated,
    totalPlacedCount,
    totalKwc,
    totalAnnualKwh,
    pctOfTarget: target > 0 ? (totalAnnualKwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    roofLimited: needed > 0 && totalPlacedCount < needed,
    skippedNorth: evaluated.filter((p) => p.northFacing).length,
  };
}

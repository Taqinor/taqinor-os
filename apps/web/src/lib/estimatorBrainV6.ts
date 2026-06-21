/**
 * CERVEAU V6 de l'estimateur (preview privé /preview/toiture-3d-pro-9). Module PUR,
 * testé (tests/estimatorBrainV6.test.ts), sans DOM, sans carte, sans dépendance
 * nouvelle. COMPOSE sur V2/V4/V5 sans en modifier UN OCTET — pro-3..pro-8 restent des
 * baselines intactes. V6 corrige DEUX choses de pro-8 :
 *
 *  FIX 1 — TOIT EN PENTE = VRAI PLAN INCLINÉ (affleurant, sans châssis). pro-8 gardait
 *  le calepinage TOIT PLAT et se contentait d'incliner chaque panneau de la pente :
 *  tous les panneaux restaient À LA MÊME HAUTEUR sur un toit horizontal — un montage
 *  lesté à plat, pas une vraie pente. V6 fournit la GÉOMÉTRIE pure et vérifiable :
 *    - `roofPlaneNormal(pitch, facing)` : la normale du toit penche vers la FACE ;
 *      elle n'est PLUS le vecteur vertical dès que pitch > 0.
 *    - `flushPanelPose(...)` / `flushPanelCenterAt(...)` : chaque panneau est COPLANAIRE
 *      (même normale que le toit), posé à un MÊME petit décalage constant (standoff)
 *      au-dessus du plan le long de la normale — pas de hauteurs variables (= châssis).
 *      Les panneaux haut-de-pente sont PHYSIQUEMENT plus hauts (vrai plan incliné).
 *    - `pitchedDeckZ(...)` : la SURFACE de toit elle-même devient un plan incliné
 *      (la photo détourée, mappée par position horizontale, reste géo-alignée).
 *  Le rendu n'instancie AUCUN châssis triangulaire en pente (garde `flush`). Comme le
 *  build ne voit pas la carte rendue, tout est ancré sur cette géométrie + tests.
 *
 *  FIX 2 — L'OPTIMISEUR BALAIE *ET AFFICHE* LA MATRICE COMPLÈTE (toit plat). pro-8
 *  ne montrait que ~6 configs nommées et recommandait la meilleure des six — ratant
 *  le vrai optimum (souvent entre deux lignes) et cachant l'espace d'options. V6
 *  `fineGridMatrixV6(...)` BALAIE dense : inclinaison 0→35° par pas de 5°, azimut
 *  {plein sud, aligné toit, sud ±45° par pas de 15°} + le mode Est-Ouest dos à dos,
 *  chacun en portrait ET paysage, marge gardée/retirée, en conservant l'espacement
 *  inter-rangées sans-ombre du solstice d'hiver (production honnête). Pour CHAQUE
 *  combinaison : panneaux posés, kWc, kWh/an (PVGIS au GPS exact, repli table
 *  « estimé »), % du besoin, fourchette d'économies. Le RECOMMANDÉ est le VRAI maximum
 *  sur TOUT le balayage (plafonné au besoin). `fineGridMatrixV6` RENVOIE toutes les
 *  lignes évaluées (la matrice) pour que le tableau les AFFICHE (triables, filtrables) ;
 *  `sortMatrix`/`matrixGroupKey` outillent ce tableau. Le rendement spécifique
 *  (kWh/kWc/an) étant indépendant de la taille, le page-script préfetche
 *  `pvgisMatrixCandidatePairs(...)` une fois par plan, met en cache, et bascule en
 *  table committée si PVGIS est injoignable.
 *
 * NOTE (à ne PAS construire ici) : l'espacement inter-rangées / le taux d'occupation
 * du sol (GCR) pourrait devenir un axe d'optimisation supplémentaire, mais SEULEMENT
 * avec un vrai modèle d'auto-ombrage rangée-à-rangée que le moteur n'a pas encore
 * (PVGIS chiffre UN plan, pas l'auto-ombrage). Resserrer l'espacement sous le seuil
 * sans-ombre maintenant introduirait de l'ombre non modélisée : volontairement différé
 * pour garder chaque chiffre honnête. JAMAIS un devis : une fourchette indicative.
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
import { type YieldFn, type YieldSource } from './estimatorBrainV4';

export { PANEL2_WATT };
export type { YieldFn, YieldSource };

const DEG2RAD = Math.PI / 180;
const EVAL_EPS = 1e-6;

// ════════════════════════════ FIX 1 — géométrie du PLAN INCLINÉ ════════════════════════════

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/** Petit décalage FIXE (m) des panneaux affleurants au-dessus du plan de toit, le
 *  long de la normale (rails/standoffs bas). Constant pour TOUS les panneaux : des
 *  hauteurs variables trahiraient des châssis. */
export const PITCHED_FLUSH_STANDOFF_M = 0.06;

/** Tolérance de coplanarité (produit scalaire de normales) pour les tests/garde-fous. */
export const COPLANAR_TOL = 1e-6;

/** Direction horizontale de FACE (aval / down-slope) en repère scène ENU
 *  (x = Est, y = Nord), pour un azimut BOUSSOLE (0=N, 90=E, 180=S, 270=O). */
export function facingUnit(facingAzimuthDeg: number): { x: number; y: number } {
  const b = facingAzimuthDeg * DEG2RAD;
  return { x: Math.sin(b), y: Math.cos(b) };
}

/** Direction horizontale MONTANTE (amont / up-slope) = opposée à la face. */
export function upSlopeUnit(facingAzimuthDeg: number): { x: number; y: number } {
  const f = facingUnit(facingAzimuthDeg);
  return { x: -f.x, y: -f.y };
}

/** Direction horizontale TRAVERS-PENTE (perpendiculaire à la face), unitaire. */
export function acrossUnit(facingAzimuthDeg: number): { x: number; y: number } {
  const us = upSlopeUnit(facingAzimuthDeg);
  return { x: -us.y, y: us.x }; // up-slope tourné +90° autour de Z
}

/**
 * Normale UNITAIRE du PLAN DE TOIT incliné de `pitchDeg` vers la face
 * `facingAzimuthDeg`. Toit plat (pitch 0) → (0,0,1). pitch > 0 → la normale PENCHE
 * vers la face, composante horizontale = sin(pitch) > 0 ⇒ elle n'est PLUS verticale.
 * C'est EXACTEMENT la normale que le rendu donne au panneau (compose(yaw, tilt)).
 */
export function roofPlaneNormal(pitchDeg: number, facingAzimuthDeg: number): Vec3 {
  const t = pitchDeg * DEG2RAD;
  const f = facingUnit(facingAzimuthDeg);
  return { x: Math.sin(t) * f.x, y: Math.sin(t) * f.y, z: Math.cos(t) };
}

/** Hauteur du plan incliné AU-DESSUS de l'égout, à un décalage MONTANT (m). */
export function pitchedRise(upSlopeOffsetM: number, pitchDeg: number): number {
  return upSlopeOffsetM * Math.tan(pitchDeg * DEG2RAD);
}

/** Coordonnée MONTANTE (scalaire) d'un point (x,y) ENU le long de l'amont. */
export function upSlopeCoord(x: number, y: number, facingAzimuthDeg: number): number {
  const us = upSlopeUnit(facingAzimuthDeg);
  return x * us.x + y * us.y;
}

/** Coordonnée MONTANTE de l'ÉGOUT (le point le plus aval) d'un contour ENU : sert de
 *  référence pour que toute la pente monte À PARTIR de baseZ (rien sous le toit). */
export function eaveUpSlopeCoord(ringENU: [number, number][], facingAzimuthDeg: number): number {
  let m = Infinity;
  for (const [x, y] of ringENU) m = Math.min(m, upSlopeCoord(x, y, facingAzimuthDeg));
  return Number.isFinite(m) ? m : 0;
}

/** Z de la SURFACE de toit inclinée en un point horizontal (x,y) — plan passant par
 *  l'égout (réf. `eaveCoordM`) à la hauteur `baseZ`, montant de `pitchDeg`. */
export function pitchedDeckZ(
  x: number,
  y: number,
  eaveCoordM: number,
  baseZ: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
): number {
  return baseZ + pitchedRise(upSlopeCoord(x, y, facingAzimuthDeg) - eaveCoordM, pitchDeg);
}

/**
 * Centre 3D d'un panneau affleurant à la position horizontale ABSOLUE (cx,cy) du
 * calepinage : posé sur le plan incliné puis décalé de `standoffM` le long de la
 * normale. Seuls Z (monte avec l'amont) et un infime glissement horizontal
 * (standoff·n) changent vs le calepinage plat — l'orientation du panneau est déjà la
 * normale du plan (compose(yaw, tilt)).
 */
export function flushPanelCenterAt(
  cx: number,
  cy: number,
  eaveCoordM: number,
  baseZ: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
  standoffM: number = PITCHED_FLUSH_STANDOFF_M,
): Vec3 {
  const n = roofPlaneNormal(pitchDeg, facingAzimuthDeg);
  return {
    x: cx + standoffM * n.x,
    y: cy + standoffM * n.y,
    z: pitchedDeckZ(cx, cy, eaveCoordM, baseZ, pitchDeg, facingAzimuthDeg) + standoffM * n.z,
  };
}

/**
 * Pose d'un panneau affleurant repérée par ses décalages DANS LE PLAN (amont,
 * travers) depuis l'égout (0,0,baseZ). Renvoie centre + normale. Utilisé par les
 * tests : la normale vaut la normale du toit (coplanaire) et la distance signée au
 * plan vaut EXACTEMENT `standoffM` pour TOUS les panneaux (décalage constant).
 */
export function flushPanelPose(
  upOffsetM: number,
  acrossOffsetM: number,
  baseZ: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
  standoffM: number = PITCHED_FLUSH_STANDOFF_M,
): { center: Vec3; normal: Vec3 } {
  const us = upSlopeUnit(facingAzimuthDeg);
  const ac = acrossUnit(facingAzimuthDeg);
  const n = roofPlaneNormal(pitchDeg, facingAzimuthDeg);
  return {
    center: {
      x: upOffsetM * us.x + acrossOffsetM * ac.x + standoffM * n.x,
      y: upOffsetM * us.y + acrossOffsetM * ac.y + standoffM * n.y,
      z: baseZ + pitchedRise(upOffsetM, pitchDeg) + standoffM * n.z,
    },
    normal: n,
  };
}

/**
 * Les 4 COINS d'un panneau affleurant, repérés par le centre (amont, travers) et ses
 * demi-dimensions DANS LE PLAN (demi-longueur amont, demi-largeur travers). Chaque coin
 * passe par `flushPanelPose` → il est posé SUR le plan incliné au MÊME standoff que le
 * centre (le panneau est plat dans le plan : tous les coins sont coplanaires, « sur le
 * plan incliné »). Sert au test « chaque coin se projette sur le plan incliné ».
 */
export function flushPanelCorners(
  upOffsetM: number,
  acrossOffsetM: number,
  halfUpM: number,
  halfAcrossM: number,
  baseZ: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
  standoffM: number = PITCHED_FLUSH_STANDOFF_M,
): Vec3[] {
  const combos: [number, number][] = [
    [1, 1],
    [1, -1],
    [-1, -1],
    [-1, 1],
  ];
  return combos.map(
    ([su, sa]) =>
      flushPanelPose(
        upOffsetM + su * halfUpM,
        acrossOffsetM + sa * halfAcrossM,
        baseZ,
        pitchDeg,
        facingAzimuthDeg,
        standoffM,
      ).center,
  );
}

/** Produit scalaire de deux Vec3. */
export function dot3(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/**
 * Distance SIGNÉE d'un point au plan de toit (passant par l'égout (0,0,baseZ),
 * normale = roofPlaneNormal) — vaut le standoff pour un panneau bien posé. */
export function signedDistanceToPlane(
  point: Vec3,
  baseZ: number,
  pitchDeg: number,
  facingAzimuthDeg: number,
): number {
  const n = roofPlaneNormal(pitchDeg, facingAzimuthDeg);
  return dot3(n, { x: point.x, y: point.y, z: point.z - baseZ });
}

// ════════════════════════════ FIX 2 — MATRICE d'optimisation toit plat ════════════════════════════

/** Pas/demi-ouverture du balayage d'azimut autour du sud (degrés). */
export const SOUTH_SPAN_STEP_DEG = 15;
export const SOUTH_SPAN_HALF_DEG = 45;

/** Inclinaisons Est-Ouest candidates (l'E-O joue déjà la densité). */
const EW_TILTS = [10, 12, 15] as const;

const round1 = (n: number) => Math.round(n * 10) / 10;
const norm360 = (a: number) => ((a % 360) + 360) % 360;

/** Grille fine d'inclinaisons toit plat : 0→35° par pas de 5°, + l'optimum Sud de la
 *  table pour ne jamais rater le pic. Bornée [0, 35]. */
export function matrixTiltGrid(latitudeDeg: number): number[] {
  const base = [0, 5, 10, 15, 20, 25, 30, 35];
  const opt = optimalSouthTiltDeg(latitudeDeg);
  const set = new Set(base);
  if (opt >= 0 && opt <= 35) set.add(opt);
  return [...set].sort((a, b) => a - b);
}

/** Azimuts (boussole) du balayage autour du sud : 180 ± 45° par pas de 15° → 135..225. */
export function southSpanAzimuths(): number[] {
  const out: number[] = [];
  for (let d = -SOUTH_SPAN_HALF_DEG; d <= SOUTH_SPAN_HALF_DEG + 1e-9; d += SOUTH_SPAN_STEP_DEG) {
    out.push(180 + d);
  }
  return out;
}

function uniqueAz(list: number[]): number[] {
  const seen = new Set<number>();
  const out: number[] = [];
  for (const a of list) {
    const r = round1(norm360(a));
    if (!seen.has(r)) {
      seen.add(r);
      out.push(r);
    }
  }
  return out;
}

export type AxisOrient = 'portrait' | 'landscape';
export type AxisMargin = 'keep' | 'remove';
export type AzimuthAxis = 'south' | 'aligned' | 'span';

export interface MatrixEvalV6 {
  family: ConfigFamily;
  tiltDeg: number;
  /** Azimut de face réel (boussole) du pavage. */
  azimuthDeg: number;
  /** Aspect PVGIS (south: az−180 ; eastwest: az−90). */
  aspect: number;
  orientation: AxisOrient;
  margin: AxisMargin;
  azimuthAxis: AzimuthAxis;
  fitCount: number;
  placedCount: number;
  kwc: number;
  annualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  perPanelYield: number;
  yieldSource: YieldSource;
  /** Libellé d'orientation FR (« plein sud », « orienté sud-ouest (210°) », « Est-Ouest »). */
  orientationLabel: string;
  /** Libellé de pose FR (« portrait » / « paysage »). */
  layoutLabel: string;
  /** Libellé complet de la ligne. */
  label: string;
}

const ORIENT_FR: Record<AxisOrient, string> = { portrait: 'portrait', landscape: 'paysage' };

function southOrientationLabel(azimuthDeg: number, axis: AzimuthAxis): string {
  const off = ((azimuthDeg - 180 + 540) % 360) - 180; // écart au sud, (−180,180]
  if (Math.abs(off) < 1) return 'plein sud';
  const side = off < 0 ? 'sud-est' : 'sud-ouest';
  const aligned = axis === 'aligned' ? ' (aligné toit)' : '';
  return `orienté ${side} (${Math.round(norm360(azimuthDeg))}°)${aligned}`;
}

function ewOrientationLabel(axis: AzimuthAxis): string {
  return axis === 'aligned' ? 'Est-Ouest aligné toit' : 'Est-Ouest';
}

/** Rendement résolu pour un (tilt, aspect) : PVGIS si dispo/valide, sinon table. */
function resolveYieldV6(
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
function matrixProduction(
  family: ConfigFamily,
  tiltDeg: number,
  azimuthDeg: number,
  kwc: number,
  yieldFn: YieldFn | undefined,
  latitudeDeg: number,
): { kwh: number; perPanelYield: number; source: YieldSource; aspect: number } {
  const aspect = aspectForAzimuth(family, azimuthDeg);
  if (family === 'eastwest') {
    const e = resolveYieldV6(yieldFn, latitudeDeg, tiltDeg, aspect - 90);
    const w = resolveYieldV6(yieldFn, latitudeDeg, tiltDeg, aspect + 90);
    return {
      kwh: (kwc / 2) * e.value + (kwc / 2) * w.value,
      perPanelYield: (e.value + w.value) / 2,
      source: e.source === 'pvgis' && w.source === 'pvgis' ? 'pvgis' : 'estimate',
      aspect,
    };
  }
  const s = resolveYieldV6(yieldFn, latitudeDeg, tiltDeg, aspect);
  return { kwh: kwc * s.value, perPanelYield: s.value, source: s.source, aspect };
}

interface MatrixCfg {
  family: ConfigFamily;
  tiltDeg: number;
  azimuthDeg: number;
  orientation: AxisOrient;
  margin: AxisMargin;
  azimuthAxis: AzimuthAxis;
}

function evalMatrixConfig(
  ring: LngLat[],
  latitudeDeg: number,
  cfg: MatrixCfg,
  needed: number,
  target: number,
  obstructions: LngLat[][],
  defaultSetbackM: number,
  overhangM: number,
  tariff: TariffGrid,
  yieldFn: YieldFn | undefined,
  cache: Map<string, PackResult>,
): MatrixEvalV6 {
  const setbackM = cfg.margin === 'keep' ? defaultSetbackM : 0;
  // W109 — overhangM dans la clé (sinon collision entre overhangs) ; 0 → clé/pavage inchangés.
  const key = `${cfg.family}|${cfg.tiltDeg}|${Math.round(cfg.azimuthDeg * 1000)}|${Math.round(setbackM * 1000)}|${Math.round(overhangM * 1000)}`;
  let pack = cache.get(key);
  if (!pack) {
    pack = packConfig(ring, latitudeDeg, {
      family: cfg.family,
      tiltDeg: cfg.tiltDeg,
      azimuthDeg: cfg.azimuthDeg,
      obstructions,
      setbackM,
      overhangM,
    });
    cache.set(key, pack);
  }
  const grid = cfg.orientation === 'portrait' ? pack.portrait : pack.landscape;
  const fitCount = grid.count;
  const placedCount = needed > 0 ? Math.min(needed, fitCount) : fitCount;
  const kwc = (placedCount * PANEL2_WATT) / 1000;
  const prod = matrixProduction(cfg.family, cfg.tiltDeg, pack.azimuthDeg, kwc, yieldFn, latitudeDeg);
  const savings = annualSavingsMad(prod.kwh, target, tariff);
  const orientationLabel =
    cfg.family === 'eastwest'
      ? ewOrientationLabel(cfg.azimuthAxis)
      : southOrientationLabel(pack.azimuthDeg, cfg.azimuthAxis);
  return {
    family: cfg.family,
    tiltDeg: cfg.tiltDeg,
    azimuthDeg: pack.azimuthDeg,
    aspect: prod.aspect,
    orientation: cfg.orientation,
    margin: cfg.margin,
    azimuthAxis: cfg.azimuthAxis,
    fitCount,
    placedCount,
    kwc,
    annualKwh: prod.kwh,
    pctOfTarget: target > 0 ? (prod.kwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    perPanelYield: prod.perPanelYield,
    yieldSource: prod.source,
    orientationLabel,
    layoutLabel: ORIENT_FR[cfg.orientation],
    label: `${cfg.tiltDeg}° · ${orientationLabel} · ${ORIENT_FR[cfg.orientation]}`,
  };
}

/**
 * `a` meilleure que `b` ? Énergie POSÉE d'abord (encode l'adéquation, tout plafonné
 * au besoin), puis rendement/panneau, moins de matériel, garder la marge, Sud avant
 * E-O, plus proche du plein sud, inclinaison plus raide, portrait. Départages
 * déterministes — JAMAIS de hasard.
 */
export function betterMatrixV6(a: MatrixEvalV6, b: MatrixEvalV6): boolean {
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
  return a.orientation === 'portrait' && b.orientation !== 'portrait';
}

export interface MatrixV6Options {
  city?: string;
  /** Rendement spécifique PVGIS injecté (sinon table committée seule). */
  yieldFn?: YieldFn;
  /** Ouvre l'axe aligné-toit même si le toit est ~plein-sud (tests/cohérence). */
  forceAligned?: boolean;
  /** W109 — débord panneaux autorisé au-delà de la rive (m). Défaut 0 → calepinage inchangé. */
  overhangM?: number;
}

export interface MatrixV6Result {
  targetAnnualKwh: number;
  neededPanels: number;
  roofAlignedAzimuthDeg: number;
  offSouthDeg: number;
  roofLimited: boolean;
  /** TOUTES les configs évaluées : la MATRICE complète à afficher. */
  rows: MatrixEvalV6[];
  /** Le VRAI maximum sur tout le balayage (plafonné au besoin). */
  winner: MatrixEvalV6;
  /** Description « ligne à part » de l'optimum, badge « Recommandé ». */
  optimumRow: { label: string; reason: string; yieldSource: YieldSource };
  evaluated: number;
  yieldSource: YieldSource;
}

/**
 * BALAYAGE DENSE qui RENVOIE la matrice complète + le vrai optimum. Couvre la grille
 * fine d'inclinaisons, l'azimut {sud ±45° par pas de 15°, aligné toit} et le mode
 * Est-Ouest dos à dos, en portrait ET paysage, marge gardée/retirée. Production PVGIS
 * au GPS exact (repli table), espacement inter-rangées sans-ombre conservé. Le gagnant
 * est le maximum d'énergie POSÉE, plafonné au besoin.
 */
export function fineGridMatrixV6(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  options: MatrixV6Options = {},
): MatrixV6Result {
  const tariff = tariffForCity(options.city);
  const target = billToAnnualKwh(monthlyBillMad, tariff);
  const needed = neededPanelsForTarget(target, latitudeDeg);
  const roofAz = roofDominantAzimuthDeg(ring);
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const setback = PERIMETER_SETBACK_M;
  const overhang = Math.max(0, options.overhangM ?? 0); // W109 — défaut 0 → balayage inchangé
  const southTilts = matrixTiltGrid(latitudeDeg);
  const orientations: AxisOrient[] = ['portrait', 'landscape'];
  const margins: AxisMargin[] = ['keep', 'remove'];
  const cache = new Map<string, PackResult>();

  const span = uniqueAz(southSpanAzimuths());
  const alignedAz = round1(norm360(roofAz));
  const southAzes = uniqueAz([...span, alignedAz]);
  const ewAzes = uniqueAz([90, norm360(roofAz - 90)]);

  const rows: MatrixEvalV6[] = [];
  let winner: MatrixEvalV6 | null = null;
  let anyPvgis = false;

  const consider = (cfg: MatrixCfg) => {
    const e = evalMatrixConfig(ring, latitudeDeg, cfg, needed, target, obstructions, setback, overhang, tariff, options.yieldFn, cache);
    rows.push(e);
    if (e.yieldSource === 'pvgis') anyPvgis = true;
    if (!winner || betterMatrixV6(e, winner)) winner = e;
  };

  for (const az of southAzes) {
    const axis: AzimuthAxis = Math.abs(az - alignedAz) < 0.5 && Math.abs(offSouthDeg) >= 2 ? 'aligned' : Math.abs(az - 180) < 0.5 ? 'south' : 'span';
    for (const tiltDeg of southTilts) {
      for (const margin of margins) {
        for (const orientation of orientations) {
          consider({ family: 'south', tiltDeg, azimuthDeg: az, orientation, margin, azimuthAxis: axis });
        }
      }
    }
  }
  for (const az of ewAzes) {
    const axis: AzimuthAxis = Math.abs(az - 90) < 0.5 ? 'south' : 'aligned';
    for (const tiltDeg of EW_TILTS) {
      for (const margin of margins) {
        for (const orientation of orientations) {
          consider({ family: 'eastwest', tiltDeg, azimuthDeg: az, orientation, margin, azimuthAxis: axis });
        }
      }
    }
  }

  const w = winner!;
  const pct = Math.round(w.pctOfTarget);
  const reason =
    w.family === 'eastwest'
      ? `L'Est-Ouest dos à dos loge ${w.placedCount} panneaux et couvre ~${pct} % du besoin — plus d'énergie totale que le plein sud sur ce toit.`
      : w.orientationLabel === 'plein sud'
        ? `À ${w.tiltDeg}° plein sud, ${w.placedCount} panneaux couvrent ~${pct} % du besoin avec le meilleur rendement par panneau.`
        : `${w.orientationLabel} à ${w.tiltDeg}° loge ${w.placedCount} panneaux et couvre ~${pct} % — plus d'énergie totale que les configs standard.`;

  return {
    targetAnnualKwh: target,
    neededPanels: needed,
    roofAlignedAzimuthDeg: roofAz,
    offSouthDeg,
    roofLimited: needed > 0 && w.placedCount < needed,
    rows,
    winner: w,
    optimumRow: {
      label: `Optimum calculé — inclinaison ${w.tiltDeg}°, ${w.orientationLabel}, ${w.layoutLabel}`,
      reason,
      yieldSource: anyPvgis ? 'pvgis' : 'estimate',
    },
    evaluated: rows.length,
    yieldSource: anyPvgis ? 'pvgis' : 'estimate',
  };
}

/**
 * Couples (tilt°, aspect PVGIS) que la matrice va RÉELLEMENT interroger sur ce toit.
 * Le rendement spécifique étant indépendant de la taille, le page-script les préfetche
 * (kWc=1) au GPS exact, met en cache, et bâtit `YieldFn` — réutilisé par tout le
 * tableau et tous les bascules. Garde page et moteur synchronisés.
 */
export function pvgisMatrixCandidatePairs(
  latitudeDeg: number,
  roofAz: number,
): { tiltDeg: number; aspect: number }[] {
  const out = new Map<string, { tiltDeg: number; aspect: number }>();
  const add = (t: number, a: number) => out.set(`${t}|${round1(a)}`, { tiltDeg: t, aspect: round1(a) });
  const tilts = matrixTiltGrid(latitudeDeg);
  const southAzes = uniqueAz([...southSpanAzimuths(), norm360(roofAz)]);
  for (const az of southAzes) for (const t of tilts) add(t, az - 180);
  const ewAzes = uniqueAz([90, norm360(roofAz - 90)]);
  for (const az of ewAzes) for (const t of EW_TILTS) {
    const base = az - 90;
    add(t, base - 90);
    add(t, base + 90);
  }
  return [...out.values()];
}

// ── Balayage PVGIS COARSE-THEN-FINE (rapide, dans les limites de débit) ───────────
// Le rendement spécifique est indépendant de la taille → on l'interroge UNE fois par
// (tilt, aspect). Pour rester rapide et poli avec PVGIS, on procède en deux temps :
// 1) une grille GROSSIÈRE d'inclinaisons (tous les aspects) pour trouver la BASE ;
// 2) un RAFFINEMENT (grille fine complète) autour de l'aspect gagnant. Les cellules
//    non interrogées retombent gracieusement sur l'estimation maison (« estimé »).

/** Grille GROSSIÈRE d'inclinaisons (0/15/30° + optimum), bornée [0, 35]. */
export function coarseTiltGrid(latitudeDeg: number): number[] {
  const base = [0, 15, 30];
  const opt = optimalSouthTiltDeg(latitudeDeg);
  const set = new Set(base);
  if (opt >= 0 && opt <= 35) set.add(opt);
  return [...set].sort((a, b) => a - b);
}

/** PHASE 1 — couples (tilt°, aspect) GROSSIERS : tous les aspects candidats, mais
 *  seulement les inclinaisons grossières → trouve la base sans saturer PVGIS. */
export function pvgisCoarsePairs(
  latitudeDeg: number,
  roofAz: number,
): { tiltDeg: number; aspect: number }[] {
  const out = new Map<string, { tiltDeg: number; aspect: number }>();
  const add = (t: number, a: number) => out.set(`${t}|${round1(a)}`, { tiltDeg: t, aspect: round1(a) });
  const tilts = coarseTiltGrid(latitudeDeg);
  const southAzes = uniqueAz([...southSpanAzimuths(), norm360(roofAz)]);
  for (const az of southAzes) for (const t of tilts) add(t, az - 180);
  // L'Est-Ouest n'a que 3 inclinaisons : on les couvre toutes dès la phase grossière.
  const ewAzes = uniqueAz([90, norm360(roofAz - 90)]);
  for (const az of ewAzes) for (const t of EW_TILTS) {
    const base = az - 90;
    add(t, base - 90);
    add(t, base + 90);
  }
  return [...out.values()];
}

/** PHASE 2 — couples (tilt°, aspect) de RAFFINEMENT : la grille FINE complète aux
 *  aspects voisins (± un pas) de l'aspect gagnant trouvé en phase 1, pour résoudre
 *  précisément l'inclinaison optimale dans la base. Les aspects loin de la base
 *  gardent leurs cellules fines en « estimé » (volontaire). */
export function pvgisRefinePairs(
  latitudeDeg: number,
  roofAz: number,
  winnerAspectDeg: number,
): { tiltDeg: number; aspect: number }[] {
  const out = new Map<string, { tiltDeg: number; aspect: number }>();
  const add = (t: number, a: number) => out.set(`${t}|${round1(a)}`, { tiltDeg: t, aspect: round1(a) });
  const tilts = matrixTiltGrid(latitudeDeg); // grille FINE complète
  const wa = round1(winnerAspectDeg);
  const southAspects = uniqueAz([...southSpanAzimuths(), norm360(roofAz)]).map((az) => round1(az - 180));
  const near = southAspects.filter((a) => Math.abs(a - wa) <= SOUTH_SPAN_STEP_DEG + 0.5);
  for (const a of near) for (const t of tilts) add(t, a);
  return [...out.values()];
}

export type MatrixSortKey = 'annualKwh' | 'placedCount' | 'pctOfTarget';

/** Tri stable du tableau par kWh/an, nombre de panneaux, ou % du besoin couvert. */
export function sortMatrix(rows: MatrixEvalV6[], key: MatrixSortKey, dir: 'asc' | 'desc' = 'desc'): MatrixEvalV6[] {
  const sign = dir === 'desc' ? -1 : 1;
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const d = a.r[key] - b.r[key];
      if (Math.abs(d) > EVAL_EPS) return sign * d;
      return a.i - b.i; // stable
    })
    .map((x) => x.r);
}

/** Clé de regroupement/filtre du tableau (par orientation/pose) — garde la longue
 *  liste lisible sur un téléphone. */
export function matrixGroupKey(row: MatrixEvalV6): string {
  if (row.family === 'eastwest') return `Est-Ouest · ${row.layoutLabel}`;
  return `${row.orientationLabel.replace(/\s*\(\d+°\)/, '').replace(/\s*\(aligné toit\)/, '')} · ${row.layoutLabel}`;
}

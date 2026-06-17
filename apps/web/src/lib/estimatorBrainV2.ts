/**
 * CERVEAU V2 de l'estimateur piloté par la facture (preview privé
 * /preview/toiture-3d-pro-4). Module PUR, testé (tests/estimatorBrainV2.test.ts) :
 * aucun DOM, aucune carte, aucune dépendance.
 *
 * COPIE VERSIONNÉE de estimatorBrain.ts (pro-3) : pro-3 reste octet pour octet
 * identique comme baseline. SEULE la recommandation change ici (voir
 * apps/web/BRAIN_V2_NOTES.md) :
 *  - balayage d'inclinaison FIN qui, sur un toit LIMITÉ, choisit une inclinaison
 *    plus plate pour loger plus de panneaux (plus de production TOTALE) — sans
 *    JAMAIS dépasser le plafond « besoin » ; sur un toit spacieux il garde
 *    l'optimal (~29–30°) et ne sur-remplit pas.
 *  - l'objet `recommended` est TOUJOURS plafonné au besoin (posés = min(besoin,
 *    fit)), production/économies dérivés des panneaux POSÉS — plus de branche
 *    non-capée.
 *
 * Entrées : tracé du toit (lng/lat), latitude du toit, facture mensuelle (MAD).
 * Sorties : configurations classées (Sud optimal, Sud basse inclinaison,
 * Est-Ouest) avec compte de panneaux, kWc, production annuelle, % de la facture
 * couverte, fourchette d'économies — et une recommandation dimensionnée au besoin.
 *
 * PHYSIQUE EXACTE (corrigée 2026-06) :
 *  - UNE seule règle d'espacement solaire (solstice d'hiver, soleil 10 h) gouverne
 *    TOUTES les configs — rangées Sud ET intervalle entre chevrons Est-Ouest. Aucune
 *    densité/GCR codée en dur.
 *  - Pavage de vrais rectangles de panneaux dans le tracé (pas une surface × ratio) :
 *    Σ empreintes au sol ≤ surface utile pour chaque config (borne physique testée).
 *  - Économies plafonnées à la consommation : autoconsommation au tarif MARGINAL,
 *    jamais > la facture ; surplus au tarif d'export (nul par défaut, conservateur).
 *  - Facture → conso au tarif MOYEN mélangé ; économies au tarif MARGINAL.
 *
 * Réutilise la géométrie pure de roof.ts (aire géodésique, point-dans-polygone), le
 * vrai panneau Canadian Solar 720 W de roofPro2.ts, et la table PVGIS committée
 * (yieldTable.ts). JAMAIS un devis. Voir apps/web/ESTIMATOR_BRAIN_NOTES.md.
 */
import { geodesicAreaM2, pointInPolygon, type LngLat } from './roof';
import { PANEL2_LONG_M, PANEL2_SHORT_M, PANEL2_WATT, PERIMETER_SETBACK_M } from './roofPro2';
import { YIELD_TABLE } from './yieldTable';

export { PANEL2_WATT };

const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;
const MAX_CELLS = 200000;

// — Règle de design de l'espacement (échangeable ici) —
/** Solstice d'hiver. Soleil de 10 h = point le plus défavorable de la fenêtre
 * pro 10 h–14 h. Passer à 12 h donne une règle « midi solaire » plus dense. */
export const DESIGN_SOLAR_HOUR = 10;
const SOLAR_DECLINATION_DEG = -23.44; // déclinaison au solstice d'hiver (hémisphère nord)
const PANEL_SIDE_GAP_M = 0.02; // jeu entre panneaux d'une rangée
const SHADOW_MARGIN_M = 0.05; // marge en plus de l'ombre calculée
/** Jeu de maintenance/aération entre deux chevrons Est-Ouest dos à dos (m). Un
 * chevron en A absorbe sa PROPRE ombre de faîte tant que l'ombre < empreinte d'un
 * panneau — vrai à toutes les inclinaisons E-O réalistes (≤29°). L'écart entre
 * chevrons n'est donc PAS un pas de rangée sud : c'est l'ombre résiduelle (≈0 ici)
 * + ce passage. Réglable ici. */
const EW_MAINTENANCE_GAP_M = 0.2;
const EDGE_EPS_M = 1e-3; // tolérance flottante au retrait (anti-bruit sin(180°)≈1e−16)
/** Dégagement autour d'un obstacle marqué (m) : un panneau dont le centre tombe
 * à moins de cette distance d'un obstacle (ou dedans) est retiré. Modèle prudent
 * et honnête (zone d'exclusion + dégagement) : moins de panneaux = moins de
 * production, jamais l'inverse. Réglable ici. */
export const OBSTACLE_CLEARANCE_M = 0.3;
/** Côté de l'échantillonnage du recouvrement obstacle∩toit (surface utile). */
const OVERLAP_SAMPLES = 110;

// ===== Modèle de facturation ONEE/Lydec — BT « usage domestique » (2026) =====
// Coût de l'ÉNERGIE uniquement (les tranches au kWh). Les frais fixes (TPPAN,
// redevances, taxes d'abonnement) ne sont PAS modélisés : invariants au solaire,
// ils s'annulent dans le calcul d'économies. CALIBRATION exacte (HT vs TTC, frais
// fixes) = un seul ajustement de ce bloc, à valider sur une vraie facture Lydec.
/** Tranches PROGRESSIVES (≤ 150 kWh/mois) : chaque tranche à son tarif. */
const ONEE_PROGRESSIVE = [
  { upToKwh: 100, rate: 0.9 },
  { upToKwh: 150, rate: 1.07 },
];
/** Tranches SÉLECTIVES (> 150 kWh/mois) : TOUTE la conso au tarif de SA tranche. */
const ONEE_SELECTIVE = [
  { upToKwh: 200, rate: 1.07 },
  { upToKwh: 300, rate: 1.18 },
  { upToKwh: 500, rate: 1.45 },
  { upToKwh: Infinity, rate: 1.66 },
];
const ONEE_SELECTIVE_THRESHOLD_KWH = 150; // au-delà → facturation sélective
const ONEE_BOUNDARY_TOLERANCE_KWH = 10; // tolérance de tranche (on n'entre qu'à +10 kWh)
/** Part autoconsommée réellement alignée dans le temps (borne basse de la fourchette). */
const SELF_CONSUMPTION_TIMING_LOW = 0.75;

/** Coût progressif (≤ 150 kWh) — somme des tranches à leur tarif. */
function progressiveBillMAD(monthlyKwh: number): number {
  let cost = 0;
  let prev = 0;
  for (const b of ONEE_PROGRESSIVE) {
    const upper = Math.min(monthlyKwh, b.upToKwh);
    if (upper > prev) cost += (upper - prev) * b.rate;
    prev = b.upToKwh;
    if (monthlyKwh <= b.upToKwh) break;
  }
  return cost;
}

/**
 * Facture ÉNERGIE mensuelle (MAD) pour une conso mensuelle (kWh), grille ONEE BT
 * domestique : progressive ≤ 150 kWh, sinon SÉLECTIVE (toute la conso au tarif de sa
 * tranche, tolérance de 10 kWh à la borne). Monotone non-décroissante par
 * construction (les tarifs montent à chaque tranche), garantie au raccord
 * progressif→sélectif par un plancher.
 */
export function billMAD(monthlyKwh: number): number {
  if (!Number.isFinite(monthlyKwh) || monthlyKwh <= 0) return 0;
  const k = monthlyKwh;
  if (k <= ONEE_SELECTIVE_THRESHOLD_KWH) return progressiveBillMAD(k);
  let rate = ONEE_SELECTIVE[ONEE_SELECTIVE.length - 1].rate;
  for (const b of ONEE_SELECTIVE) {
    if (k <= b.upToKwh + ONEE_BOUNDARY_TOLERANCE_KWH) {
      rate = b.rate;
      break;
    }
  }
  // Plancher au seuil : un client juste au-dessus de 150 kWh ne paie jamais moins
  // que la facture progressive de 150 kWh.
  return Math.max(k * rate, progressiveBillMAD(ONEE_SELECTIVE_THRESHOLD_KWH));
}

// — Bifacial : JAMAIS dans le chiffre de tête (face avant uniquement). —
/** Gain bifacial prudent, affiché en ligne séparée et étiquetée. */
export const BIFACIAL_GAIN_TILTED = 0.05; // sud incliné, bien espacé
export const BIFACIAL_GAIN_FLAT = 0.03; // pose dense/plate (E-O)

// — Dimensionnement de la recommandation —
const COVERAGE_MARGIN = 1.1; // couvrir la cible + 10 %

/** Position solaire au solstice d'hiver à `solarHour` (heure solaire locale). */
export function sunPositionWinterSolstice(
  latitudeDeg: number,
  solarHour: number,
): { elevationDeg: number; azimuthFromSouthDeg: number } {
  const phi = latitudeDeg * DEG2RAD;
  const delta = SOLAR_DECLINATION_DEG * DEG2RAD;
  const h = 15 * (solarHour - 12) * DEG2RAD;
  const sinAlpha = Math.sin(phi) * Math.sin(delta) + Math.cos(phi) * Math.cos(delta) * Math.cos(h);
  const alpha = Math.asin(Math.max(-1, Math.min(1, sinAlpha)));
  const sinGamma = (-Math.cos(delta) * Math.sin(h)) / Math.cos(alpha);
  const gamma = Math.asin(Math.max(-1, Math.min(1, sinGamma)));
  return { elevationDeg: alpha / DEG2RAD, azimuthFromSouthDeg: gamma / DEG2RAD };
}

/**
 * Longueur d'ombre horizontale (m) projetée par une arête haute de hauteur `riseM`
 * au moment de design, dans la direction d'empilement des rangées. C'est LE terme
 * d'ombre partagé par toutes les configs :
 *   ombre = riseM · (composante directionnelle du soleil) / tan(α_s).
 * - Sud : rangées E-O empilées vers le sud → composante = cos(γ_s) (γ_s = azimut/sud).
 * - Est-Ouest : chevrons N-S empilés vers l'est → composante = |sin(γ_s)|.
 */
function shadeLengthM(riseM: number, latitudeDeg: number, solarHour: number, eastWest: boolean): number {
  const sun = sunPositionWinterSolstice(latitudeDeg, solarHour);
  const alpha = Math.max(5, sun.elevationDeg) * DEG2RAD; // garde-fou soleil très bas
  const gamma = sun.azimuthFromSouthDeg * DEG2RAD;
  const dir = eastWest ? Math.abs(Math.sin(gamma)) : Math.abs(Math.cos(gamma));
  return Math.max(0, (riseM * dir) / Math.tan(alpha));
}

export interface PitchOptions {
  /** Heure solaire du moment de design (défaut DESIGN_SOLAR_HOUR = 10 h). */
  solarHour?: number;
}

/**
 * Pas inter-rangées SUD (m, centre à centre dans le sens de la pente) pour qu'une
 * rangée n'ombre pas la suivante au moment de design :
 *   D = L · cos β + L · sin β · cos(γ_s)/tan(α_s) + marge.
 */
export function rowPitchM(
  slopeLenM: number,
  tiltDeg: number,
  latitudeDeg: number,
  opts: PitchOptions = {},
): number {
  const beta = tiltDeg * DEG2RAD;
  const footprint = slopeLenM * Math.cos(beta);
  const rise = slopeLenM * Math.sin(beta);
  const shadow = shadeLengthM(rise, latitudeDeg, opts.solarHour ?? DESIGN_SOLAR_HOUR, false);
  return footprint + shadow + SHADOW_MARGIN_M;
}

// — Productible (kWh/kWc/an) depuis la table committée, interpolé en latitude —

function interpAspect(
  grid: Record<string, Record<string, number>>,
  aspect: number,
  tiltDeg: number,
): number {
  const aspects = Object.keys(grid)
    .map(Number)
    .sort((a, b) => a - b);
  let aLo = aspects[0];
  let aHi = aspects[aspects.length - 1];
  for (let i = 0; i < aspects.length - 1; i++) {
    if (aspect >= aspects[i] && aspect <= aspects[i + 1]) {
      aLo = aspects[i];
      aHi = aspects[i + 1];
      break;
    }
  }
  const yLo = interpTilt(grid[String(aLo)], tiltDeg);
  const yHi = interpTilt(grid[String(aHi)], tiltDeg);
  if (aHi === aLo) return yLo;
  const f = (aspect - aLo) / (aHi - aLo);
  return yLo + (yHi - yLo) * Math.max(0, Math.min(1, f));
}

function interpTilt(row: Record<string, number>, tiltDeg: number): number {
  const tilts = Object.keys(row)
    .map(Number)
    .sort((a, b) => a - b);
  if (tiltDeg <= tilts[0]) return row[String(tilts[0])];
  if (tiltDeg >= tilts[tilts.length - 1]) return row[String(tilts[tilts.length - 1])];
  for (let i = 0; i < tilts.length - 1; i++) {
    if (tiltDeg >= tilts[i] && tiltDeg <= tilts[i + 1]) {
      const f = (tiltDeg - tilts[i]) / (tilts[i + 1] - tilts[i]);
      return row[String(tilts[i])] + (row[String(tilts[i + 1])] - row[String(tilts[i])]) * f;
    }
  }
  return row[String(tilts[0])];
}

/** Productible (kWh/kWc/an, face avant, pertes 14 %) depuis la table committée.
 * @param aspect azimut PVGIS : 0=Sud, −90=Est, 90=Ouest. */
export function specificYield(latitudeDeg: number, tiltDeg: number, aspect: number): number {
  const cities = Object.values(YIELD_TABLE).sort((a, b) => a.lat - b.lat);
  if (latitudeDeg <= cities[0].lat) return interpAspect(cities[0].grid, aspect, tiltDeg);
  if (latitudeDeg >= cities[cities.length - 1].lat)
    return interpAspect(cities[cities.length - 1].grid, aspect, tiltDeg);
  for (let i = 0; i < cities.length - 1; i++) {
    if (latitudeDeg >= cities[i].lat && latitudeDeg <= cities[i + 1].lat) {
      const lo = interpAspect(cities[i].grid, aspect, tiltDeg);
      const hi = interpAspect(cities[i + 1].grid, aspect, tiltDeg);
      const f = (latitudeDeg - cities[i].lat) / (cities[i + 1].lat - cities[i].lat);
      return lo + (hi - lo) * f;
    }
  }
  return interpAspect(cities[0].grid, aspect, tiltDeg);
}

/** Inclinaison sud optimale (max kWh/kWc) à cette latitude, lue dans la table. */
export function optimalSouthTiltDeg(latitudeDeg: number): number {
  let best = -1;
  let bestTilt = 29;
  for (let t = 0; t <= 35; t++) {
    const y = specificYield(latitudeDeg, t, 0);
    if (y > best) {
      best = y;
      bestTilt = t;
    }
  }
  return bestTilt;
}

/**
 * Facture mensuelle (MAD) → consommation ANNUELLE estimée (kWh). On inverse
 * numériquement billMAD (monotone) : on cherche la conso mensuelle dont la facture
 * énergie égale la facture saisie, ×12. Pour une grosse facture, ceci donne le
 * tarif effectif de la tranche haute (donc beaucoup moins de kWh qu'un diviseur
 * moyen plat) — c'est le bon comportement sélectif.
 */
export function billToAnnualKwh(monthlyBillMad: number): number {
  if (!Number.isFinite(monthlyBillMad) || monthlyBillMad <= 0) return 0;
  let lo = 0;
  let hi = 1000;
  while (billMAD(hi) < monthlyBillMad && hi < 1e6) hi *= 2;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (billMAD(mid) < monthlyBillMad) lo = mid;
    else hi = mid;
  }
  return ((lo + hi) / 2) * 12;
}

/**
 * Économies annuelles (MAD) = RÉDUCTION de la facture énergie :
 *   économies = [ billMAD(conso) − billMAD(conso − autoconsommé) ] × 12.
 * Comme on retire l'autoconsommation de la facture sélective, l'économie ne peut
 * jamais dépasser billMAD(conso) (le coût énergie évitable) — plafond automatique
 * et plus serré que « ≤ facture totale ». Le surplus au-delà de la conso vaut 0
 * (pas de net-billing BT clair au Maroc — conservateur). Fourchette : alignement
 * temporel réel de l'autoconsommation (75–100 %).
 */
export function annualSavingsMad(
  productionKwhYr: number,
  consumptionKwhYr: number,
): { low: number; high: number } {
  const consMo = Math.max(0, consumptionKwhYr) / 12;
  const prodMo = Math.max(0, productionKwhYr) / 12;
  const selfHi = Math.min(prodMo, consMo);
  const selfLo = SELF_CONSUMPTION_TIMING_LOW * selfHi;
  const billCons = billMAD(consMo);
  const high = (billCons - billMAD(consMo - selfHi)) * 12;
  const low = (billCons - billMAD(consMo - selfLo)) * 12;
  return { low: Math.max(0, low), high: Math.max(0, high) };
}

// — Pavage —

export type ConfigFamily = 'south' | 'eastwest';
export type PanelFace = 'E' | 'W';

export interface PackOptions {
  family: ConfigFamily;
  tiltDeg: number;
  /** Tracés d'obstructions (cheminée, skylight, bâche) à déduire. */
  obstructions?: LngLat[][];
  setbackM?: number;
  /** Dégagement autour des obstacles (m). Défaut OBSTACLE_CLEARANCE_M. */
  clearanceM?: number;
  /**
   * Azimut d'empilement des rangées (degrés, 0=N, 90=E, 180=S, 270=O). Par défaut
   * l'azimut canonique de la famille (Sud=180, Est-Ouest=90). En le forçant à
   * l'azimut réel des arêtes du toit (roofDominantAzimuthDeg), les rangées SUIVENT
   * le toit au lieu d'être plein sud — sur un toit tourné, ça pave bien plus de
   * panneaux. La production est alors calculée à l'aspect correspondant (le
   * rendement par panneau baisse honnêtement à mesure qu'on s'écarte du sud).
   */
  azimuthDeg?: number;
}

/**
 * Azimut de FACE (degrés, 0=N, 90=E, 180=S, 270=O) le plus proche du sud qu'on
 * obtient en alignant les rangées sur les vraies arêtes du toit. On prend l'arête
 * la plus longue (le grand côté donne le sens des rangées), puis la perpendiculaire
 * orientée vers l'hémisphère sud. Toit aligné nord-sud/est-ouest → 180° (plein sud).
 * PUR (testé) : c'est de la géométrie, jamais une donnée inventée.
 */
export function roofDominantAzimuthDeg(ring: LngLat[]): number {
  if (!Array.isArray(ring) || ring.length < 3) return 180;
  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  const cosLat = Math.cos(olat * DEG2RAD);
  const pts = ring.map(
    ([lng, lat]) => [(lng - olng) * DEG2M * cosLat, (lat - olat) * DEG2M] as [number, number],
  );
  let bestLen = -1;
  let dirE = 1;
  let dirN = 0;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const de = pts[i][0] - pts[j][0];
    const dn = pts[i][1] - pts[j][1];
    const len = de * de + dn * dn;
    if (len > bestLen) {
      bestLen = len;
      dirE = de;
      dirN = dn;
    }
  }
  // Rotation du toit modulo 90° : les arêtes d'un toit rectangulaire viennent par
  // paires perpendiculaires, donc la grille du toit est définie à 90° près. On
  // ramène cette rotation dans (−45°, 45°] et on la fait pivoter le plein sud. Un
  // toit aligné (ou carré, peu importe l'arête « la plus longue ») → 0° → 180°.
  const edgeAz = (Math.atan2(dirE, dirN) / DEG2RAD + 360) % 360;
  let theta = edgeAz % 90;
  if (theta > 45) theta -= 90;
  return 180 + theta;
}

/**
 * Surface (m²) du recouvrement obstacles ∩ toit, par échantillonnage régulier de
 * la boîte englobante du toit : la fraction de points DANS le toit ET dans au
 * moins un obstacle, multipliée par l'aire géodésique exacte du toit. Gère
 * naturellement l'UNION d'obstacles superposés (« dans au moins un ») et la part
 * d'un obstacle qui DÉBORDE du toit (« ET dans le toit ») — donc jamais de
 * double-comptage ni de retrait de surface hors toit. Sans dégagement ici : un
 * minorant honnête de la zone réellement perdue au calepinage.
 */
export function obstructionOverlapM2(ring: LngLat[], obstructions: LngLat[][], roofAreaM2: number): number {
  if (!obstructions.length || !Array.isArray(ring) || ring.length < 3 || roofAreaM2 <= 0) return 0;
  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  for (const [lng, lat] of ring) {
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  const n = OVERLAP_SAMPLES;
  let inRoof = 0;
  let blocked = 0;
  for (let i = 0; i < n; i++) {
    const lng = minLng + ((i + 0.5) / n) * (maxLng - minLng);
    for (let j = 0; j < n; j++) {
      const lat = minLat + ((j + 0.5) / n) * (maxLat - minLat);
      const pt: [number, number] = [lng, lat];
      if (!pointInPolygon(pt, ring)) continue;
      inRoof++;
      if (obstructions.some((o) => pointInPolygon(pt, o))) blocked++;
    }
  }
  if (inRoof === 0) return 0;
  return roofAreaM2 * (blocked / inRoof);
}

export interface PackedPanel {
  cx: number;
  cy: number;
  /** Sens de la pente, pour le rendu Est-Ouest en chevrons (sinon absent). */
  face?: PanelFace;
}

export interface PanelGrid {
  panelOrientation: 'portrait' | 'landscape';
  count: number;
  kwc: number;
  /** Pas d'empilement appliqué (m) : rangée Sud, ou paire de chevrons E-O. */
  rowPitchM: number;
  panels: PackedPanel[];
  /** Sens de la pente du panneau (m). */
  slopeLenM: number;
  /** Largeur le long de la rangée (m). */
  rowWidthM: number;
  /** Empreinte au sol d'UN panneau (m²) = L·cos β × largeur. */
  footprintPerPanelM2: number;
}

export interface PackResult {
  origin: LngLat;
  ringENU: [number, number][];
  azimuthDeg: number;
  tiltDeg: number;
  family: ConfigFamily;
  areaM2: number;
  /** Surface utile (m²) = aire tracée − obstructions (la borne empreinte). */
  usableAreaM2: number;
  portrait: PanelGrid;
  landscape: PanelGrid;
  /** La meilleure des deux orientations sur CE tracé. */
  best: PanelGrid;
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

/** Azimut de visée (degrés, 0=N, 90=E, 180=S, 270=O) pour l'empilement des rangées. */
function familyAzimuthDeg(family: ConfigFamily): number {
  return family === 'eastwest' ? 90 : 180; // E-O empile vers l'est ; sud vers le sud
}

interface CellParams {
  /** Empreinte au sol d'UN panneau dans le sens d'empilement (m) = L·cos β. */
  panelDepthM: number;
  /** Profondeur de la cellule posée (m) : Sud = panelDepth ; E-O = 2·panelDepth. */
  cellDepthM: number;
  /** Pas cellule-à-cellule dans le sens d'empilement (m). */
  pitchM: number;
  /** Largeur le long de la rangée (m). */
  rowWidthM: number;
  /** Panneaux par cellule : 1 (Sud) ou 2 (chevron E-O dos à dos). */
  panelsPerCell: number;
}

/**
 * Pave de vrais rectangles de panneaux dans le tracé. Chaque CELLULE (rectangle
 * largeur × cellDepth) doit tenir entièrement dans le tracé (retrait inclus) ; on y
 * pose `panelsPerCell` panneaux empilés. Les obstructions retirent les panneaux dont
 * le centre tombe dedans. Aucune surface × ratio : on compte les panneaux réels.
 */
function packCells(
  ringENU: [number, number][],
  obstructionsENU: [number, number][][],
  azimuthDeg: number,
  setbackM: number,
  p: CellParams,
  clearanceM: number,
): PackedPanel[] {
  if (ringENU.length < 3) return [];
  const azRad = azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
  const s = f; // empilement vers la visée
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
  const rows = Math.floor((vMax - vMin) / p.pitchM);
  const cols = Math.floor((uMax - uMin) / colPitch);
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) return [];

  const toENU = (uu: number, vv: number): [number, number] => [uu * u[0] + vv * s[0], uu * u[1] + vv * s[1]];
  // Un panneau est retiré si son centre tombe DANS un obstacle OU à moins de
  // `clearanceM` de son bord (zone d'exclusion + dégagement) — une seule règle
  // qui couvre l'union d'obstacles superposés et la part qui chevauche le toit.
  const inObstruction = (c: [number, number]): boolean =>
    obstructionsENU.some((o) => pointInPolygon(c, o) || distToBoundary(c, o) <= clearanceM);
  // EPS : les vecteurs de base portent un bruit flottant (sin(180°) ≈ 1e−16) qui
  // place les cellules pile au retrait à 0,5 − ε ; sans tolérance on perdrait toute
  // la première rangée/colonne (asymétrique entre Sud et E-O sur petits toits).
  // Une cellule tient si chaque coin est dans le toit (ou pile sur la rive, à
  // EDGE_EPS près) ET à au moins `setbackM` du bord. La tolérance « pile sur la
  // rive » rend le retrait nul (marge retirée) non dégénéré : sans elle, un coin
  // exactement sur la frontière échoue pointInPolygon et toute la rangée de rive
  // serait perdue → « retirer la marge » donnerait paradoxalement MOINS de
  // panneaux. À retrait positif, la 2nde condition rejette de toute façon les
  // coins de rive, donc ce relâchement n'agit qu'à retrait ≈ 0.
  const cellInside = (corners: [number, number][]): boolean =>
    corners.every((c) => {
      const d = distToBoundary(c, ringENU);
      return (pointInPolygon(c, ringENU) || d <= EDGE_EPS_M) && d >= setbackM - EDGE_EPS_M;
    });

  const panels: PackedPanel[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + setbackM + r * p.pitchM;
    const v1 = v0 + p.cellDepthM;
    if (v1 > vMax - setbackM + EDGE_EPS_M) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + setbackM + c * colPitch;
      const u1 = u0 + p.rowWidthM;
      const corners: [number, number][] = [toENU(u0, v0), toENU(u1, v0), toENU(u1, v1), toENU(u0, v1)];
      if (!cellInside(corners)) continue;
      const uMid = u0 + p.rowWidthM / 2;
      for (let k = 0; k < p.panelsPerCell; k++) {
        const vc = v0 + p.panelDepthM * (k + 0.5);
        const center = toENU(uMid, vc);
        if (inObstruction(center)) continue;
        const panel: PackedPanel = { cx: center[0], cy: center[1] };
        if (p.panelsPerCell === 2) panel.face = k === 0 ? 'W' : 'E';
        panels.push(panel);
      }
    }
  }
  return panels;
}

/** Pave le toit pour une config donnée, en portrait ET paysage, garde le meilleur. */
export function packConfig(ring: LngLat[], latitudeDeg: number, opts: PackOptions): PackResult {
  const areaM2 = geodesicAreaM2(ring);
  const azimuthDeg = opts.azimuthDeg ?? familyAzimuthDeg(opts.family);
  const setbackM = opts.setbackM ?? PERIMETER_SETBACK_M;
  const clearanceM = opts.clearanceM ?? OBSTACLE_CLEARANCE_M;
  const tiltDeg = opts.tiltDeg;
  const beta = tiltDeg * DEG2RAD;
  const eastWest = opts.family === 'eastwest';

  // Surface utile = aire tracée − recouvrement RÉEL obstacles ∩ toit (union des
  // obstacles, part hors toit exclue) — la borne « Σ empreintes ≤ utile ».
  const obstructions = opts.obstructions ?? [];
  const usableAreaM2 = Math.max(0, areaM2 - obstructionOverlapM2(ring, obstructions, areaM2));

  const buildEmpty = (
    panelOrientation: 'portrait' | 'landscape',
    slopeLenM: number,
    rowWidthM: number,
    pitchM: number,
  ): PanelGrid => ({
    panelOrientation,
    count: 0,
    kwc: 0,
    rowPitchM: pitchM,
    panels: [],
    slopeLenM,
    rowWidthM,
    footprintPerPanelM2: slopeLenM * Math.cos(beta) * rowWidthM,
  });

  // Pas d'empilement, UNE seule règle solaire pour les deux familles.
  //  - Sud : 1 panneau/cellule, pas = empreinte + ombre(cos) + marge.
  //  - Est-Ouest : 2 panneaux/cellule (chevron dos à dos), profondeur = 2 empreintes,
  //    intervalle entre chevrons = MÊME terme d'ombre (composante E-O, sin).
  const cellFor = (slopeLenM: number, rowWidthM: number): CellParams => {
    const panelDepthM = slopeLenM * Math.cos(beta);
    const rise = slopeLenM * Math.sin(beta);
    if (eastWest) {
      // Chevron en A dos à dos (faces E/O), profondeur = 2 empreintes. L'ombre de
      // faîte au moment de design se projette dans la moitié OUEST du chevron et
      // est absorbée par sa propre empreinte tant qu'elle est < panelDepthM (vrai à
      // toutes les inclinaisons E-O réalistes). L'écart entre chevrons = ombre
      // RÉSIDUELLE qui déborde (≈0 ici) + un passage de maintenance — JAMAIS un pas
      // de rangée sud, sinon on gaspillerait du toit entre les chevrons.
      const ridgeShade = shadeLengthM(rise, latitudeDeg, DESIGN_SOLAR_HOUR, true);
      const interTentGap = Math.max(0, ridgeShade - panelDepthM) + EW_MAINTENANCE_GAP_M;
      return {
        panelDepthM,
        cellDepthM: 2 * panelDepthM,
        pitchM: 2 * panelDepthM + interTentGap,
        rowWidthM,
        panelsPerCell: 2,
      };
    }
    return {
      panelDepthM,
      cellDepthM: panelDepthM,
      pitchM: rowPitchM(slopeLenM, tiltDeg, latitudeDeg),
      rowWidthM,
      panelsPerCell: 1,
    };
  };

  if (!Array.isArray(ring) || ring.length < 3) {
    const cP = cellFor(PANEL2_LONG_M, PANEL2_SHORT_M);
    const cL = cellFor(PANEL2_SHORT_M, PANEL2_LONG_M);
    const portrait = buildEmpty('portrait', PANEL2_LONG_M, PANEL2_SHORT_M, cP.pitchM);
    const landscape = buildEmpty('landscape', PANEL2_SHORT_M, PANEL2_LONG_M, cL.pitchM);
    return {
      origin: ring?.[0] ?? [0, 0],
      ringENU: [],
      azimuthDeg,
      tiltDeg,
      family: opts.family,
      areaM2,
      usableAreaM2,
      portrait,
      landscape,
      best: portrait,
    };
  }

  // Projection ENU centrée sur le centroïde.
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
  const obstructionsENU = obstructions.map((o) => o.map(toENU));

  const makeGrid = (panelOrientation: 'portrait' | 'landscape', slopeLenM: number, rowWidthM: number): PanelGrid => {
    const cell = cellFor(slopeLenM, rowWidthM);
    const panels = packCells(ringENU, obstructionsENU, azimuthDeg, setbackM, cell, clearanceM);
    return {
      panelOrientation,
      count: panels.length,
      kwc: (panels.length * PANEL2_WATT) / 1000,
      rowPitchM: cell.pitchM,
      panels,
      slopeLenM,
      rowWidthM,
      footprintPerPanelM2: slopeLenM * Math.cos(beta) * rowWidthM,
    };
  };

  // Portrait : grand côté (2,384) dans le sens de la pente. Paysage : l'inverse.
  const portrait = makeGrid('portrait', PANEL2_LONG_M, PANEL2_SHORT_M);
  const landscape = makeGrid('landscape', PANEL2_SHORT_M, PANEL2_LONG_M);
  const best = portrait.count >= landscape.count ? portrait : landscape;

  return {
    origin: [olng, olat],
    ringENU,
    azimuthDeg,
    tiltDeg,
    family: opts.family,
    areaM2,
    usableAreaM2,
    portrait,
    landscape,
    best,
  };
}

// — Évaluation d'une config (production + économies) —

export interface ConfigResult {
  id: string;
  family: ConfigFamily;
  tiltDeg: number;
  /** Azimut de face réel (180 = plein sud ; ≠180 = aligné sur un toit tourné). */
  azimuthDeg: number;
  label: string;
  panelOrientation: 'portrait' | 'landscape';
  count: number;
  kwc: number;
  specificYield: number;
  annualKwh: number;
  bifacialAnnualKwh: number;
  pctOfTarget: number;
  savingsLow: number;
  savingsHigh: number;
  notes: string;
}

/** Production annuelle (kWh, face avant) pour une puissance donnée selon la
 * famille/inclinaison. E-O = somme des sous-champs Est (base−90°) et Ouest
 * (base+90°). `aspectDeg` = écart au sud de la FACE (Sud) ou du faîte (E-O) :
 * 0 par défaut (plein sud / faîte nord-sud), non nul quand l'array suit un toit
 * tourné — le rendement par panneau baisse alors d'après la vraie table PVGIS. */
export function productionKwh(
  latitudeDeg: number,
  family: ConfigFamily,
  tiltDeg: number,
  kwc: number,
  aspectDeg = 0,
): number {
  if (family === 'eastwest') {
    const yE = specificYield(latitudeDeg, tiltDeg, aspectDeg - 90);
    const yW = specificYield(latitudeDeg, tiltDeg, aspectDeg + 90);
    return (kwc / 2) * yE + (kwc / 2) * yW;
  }
  return kwc * specificYield(latitudeDeg, tiltDeg, aspectDeg);
}

/** Aspect PVGIS (écart au sud) d'un pavage selon sa famille et son azimut réel :
 * Sud → azimut−180 (180=plein sud→0) ; E-O → azimut−90 (90=faîte N-S→0). */
export function aspectForAzimuth(family: ConfigFamily, azimuthDeg: number): number {
  return family === 'eastwest' ? azimuthDeg - 90 : azimuthDeg - 180;
}

function gridAnnualKwh(
  grid: PanelGrid,
  family: ConfigFamily,
  tiltDeg: number,
  latitudeDeg: number,
  azimuthDeg = familyAzimuthDeg(family),
): number {
  return productionKwh(latitudeDeg, family, tiltDeg, grid.kwc, aspectForAzimuth(family, azimuthDeg));
}

function buildConfigResult(
  id: string,
  label: string,
  notes: string,
  pack: PackResult,
  grid: PanelGrid,
  latitudeDeg: number,
  consumptionKwh: number,
): ConfigResult {
  const annualKwh = gridAnnualKwh(grid, pack.family, pack.tiltDeg, latitudeDeg, pack.azimuthDeg);
  const bifGain = pack.family === 'eastwest' || pack.tiltDeg < 12 ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
  const savings = annualSavingsMad(annualKwh, consumptionKwh);
  return {
    id,
    family: pack.family,
    tiltDeg: pack.tiltDeg,
    azimuthDeg: pack.azimuthDeg,
    label,
    panelOrientation: grid.panelOrientation,
    count: grid.count,
    kwc: grid.kwc,
    specificYield: grid.kwc > 0 ? annualKwh / grid.kwc : 0,
    annualKwh,
    bifacialAnnualKwh: annualKwh * (1 + bifGain),
    pctOfTarget: consumptionKwh > 0 ? (annualKwh / consumptionKwh) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    notes,
  };
}

// — Recommandation —

/** Choix recommandé, GROUPE par GROUPE, calculé indépendamment de toute sélection
 * de l'utilisateur (recommend() est pur). L'UI s'en sert pour poser un badge
 * « Recommandé » sur la bonne option de chaque groupe, qui reste correct même si
 * l'utilisateur choisit une autre option. `azimuthDeg` est le choix du groupe
 * AZIMUT pour l'array sud (180 = plein sud, sinon aligné toit) — distinct de la
 * famille recommandée (qui peut être Est-Ouest). `margin`: garder ou retirer la
 * marge de rive. */
export interface RecommendedOptions {
  family: ConfigFamily;
  panelOrientation: 'portrait' | 'landscape';
  tiltDeg: number;
  azimuthDeg: number;
  margin: 'keep' | 'remove';
}

export interface Recommendation {
  targetAnnualKwh: number;
  recommended: ConfigResult & { roofMaxCount: number };
  comparison: ConfigResult[];
  roofLimited: boolean;
  maxPerPanelTiltDeg: number;
  maxRoofEnergyTiltDeg: number;
  maxRoofEnergyKwh: number;
  /** Facture ÉNERGIE annuelle modélisée (MAD) = billMAD(conso mensuelle) × 12. */
  annualBillMad: number;
  /** Tarif effectif (MAD/kWh) = facture énergie ÷ conso (info, à confirmer). */
  effectiveRateMadPerKwh: number;
  // — V2 : balayage d'inclinaison —
  /** Besoin dicté par la facture (cible +10 % au rendement Sud optimal). */
  neededPanels: number;
  /** Inclinaison Sud retenue par le balayage capé (= optimal sur toit spacieux,
   * plus plate sur toit limité). */
  recommendedTiltDeg: number;
  /** True si la reco aplatit l'inclinaison Sud SOUS l'optimal pour loger plus de
   * panneaux (toit limité) — déclenche le message d'honnêteté FR. */
  flatterTiltChosen: boolean;
  /** Gain de production TOTALE de l'inclinaison plate vs l'optimal, sur ce toit
   * (% ; 0 si l'optimal est gardé). */
  flatterTiltExtraEnergyPct: number;
  /** Perte de rendement PAR PANNEAU de l'inclinaison plate vs l'optimal (% ; 0 si
   * l'optimal est gardé). */
  flatterTiltYieldLossPct: number;
  // — W1 : azimut réel, marge de rive, options recommandées par groupe —
  /** Azimut de face qu'on obtient en alignant les rangées sur les arêtes du toit. */
  roofAlignedAzimuthDeg: number;
  /** Marge de rive (m) utilisée pour CE calcul (reflète le toggle marge de l'UI). */
  setbackM: number;
  /** Recommandation calculée par groupe d'options (badges « Recommandé »). */
  recommendedOptions: RecommendedOptions;
}

interface ConfigSpec {
  id: string;
  family: ConfigFamily;
  tiltDeg: number;
  label: string;
  notes: string;
}

export interface RecommendOptions {
  /** Marge de rive (m). Défaut PERIMETER_SETBACK_M (marge active). 0 = pleine rive. */
  setbackM?: number;
  /**
   * Active le balayage d'azimut « aligné toit » (W1, route pro-5). Par DÉFAUT
   * `false` : `recommend()` reste alors STRICTEMENT identique au moteur d'origine
   * (familles Sud/Est-Ouest plein sud uniquement) — c'est ce qui garantit que
   * pro-4, qui n'opte pas, ne change PAS de comportement. pro-5 passe `true` pour
   * autoriser une config alignée sur les arêtes du toit à remporter la reco.
   */
  enableRoofAligned?: boolean;
}

/**
 * Nombre de panneaux STRICTEMENT dicté par la facture (le « besoin ») : de quoi
 * couvrir la cible annuelle + la marge de couverture (10 %), au rendement du sud
 * optimal de la latitude. INDÉPENDANT du toit et des obstacles — c'est un plafond
 * « besoin » que le calepinage ne dépasse jamais : panneaux posés = min(besoin, ce
 * qui tient réellement après retrait/obstacles). Même formule que la branche
 * « couvre » de recommend(), isolée ici pour piloter le curseur côté écran. */
export function neededPanelsForTarget(targetAnnualKwh: number, latitudeDeg: number): number {
  if (!(targetAnnualKwh > 0)) return 0;
  const yld = specificYield(latitudeDeg, optimalSouthTiltDeg(latitudeDeg), 0);
  if (!(yld > 0)) return 0;
  const kwcNeeded = (targetAnnualKwh * COVERAGE_MARGIN) / yld;
  return Math.max(1, Math.ceil(kwcNeeded / (PANEL2_WATT / 1000)));
}

// ===== V2 : évaluateur CAPÉ + balayage d'inclinaison =====

const EVAL_EPS = 1e-6;
/** Pas (°) du balayage Sud capé. Fin mais borné (perf : ~1 pavage/pas). */
export const TILT_SWEEP_STEP = 1;
/** Inclinaison Sud minimale balayée (°). Sous ~5° le gain de densité sature et la
 * pose à plat pose des soucis d'aération/salissure — borne prudente. */
export const TILT_SWEEP_MIN = 5;
/** Inclinaisons E-O candidates (l'E-O joue déjà la densité maximale). */
const EW_SWEEP_TILTS = [10, 15] as const;

/** Évaluation CAPÉE d'une config sur ce toit : pave, puis applique le plafond
 * besoin (posés = besoin>0 ? min(besoin, fit) : fit) et dérive production +
 * économies des panneaux RÉELLEMENT posés — jamais du toit plein. */
export interface CappedEval {
  family: ConfigFamily;
  tiltDeg: number;
  /** Azimut de face réel du pavage (180 = plein sud ; ≠180 = aligné toit). */
  azimuthDeg: number;
  pack: PackResult;
  grid: PanelGrid;
  /** Ce qui tient réellement (avant plafond besoin). */
  fitCount: number;
  /** Posés = min(besoin, fit) si besoin>0, sinon fit. */
  placedCount: number;
  /** Production annuelle (kWh, face avant) des panneaux POSÉS. */
  placedAnnualKwh: number;
  /** Rendement par panneau (kWh/kWc/an) à cette config (info départage). */
  perPanelYield: number;
}

/** Options de pavage capé : azimut forcé (suit le toit) + marge de rive.
 * Défauts = azimut canonique de la famille + marge active → rétro-compatible. */
interface CappedOpts {
  azimuthDeg?: number;
  setbackM?: number;
}

function evalCapped(
  ring: LngLat[],
  latitudeDeg: number,
  family: ConfigFamily,
  tiltDeg: number,
  needed: number,
  obstructions: LngLat[][],
  capOpts: CappedOpts = {},
): CappedEval {
  const azimuthDeg = capOpts.azimuthDeg ?? familyAzimuthDeg(family);
  const pack = packConfig(ring, latitudeDeg, {
    family,
    tiltDeg,
    azimuthDeg,
    obstructions,
    setbackM: capOpts.setbackM,
  });
  const grid = pack.best;
  const fitCount = grid.count;
  const placedCount = needed > 0 ? Math.min(needed, fitCount) : fitCount;
  const kwc = (placedCount * PANEL2_WATT) / 1000;
  // Aspect réel (écart au sud) : le rendement par panneau baisse honnêtement hors-sud.
  const aspect = aspectForAzimuth(family, pack.azimuthDeg);
  const placedAnnualKwh = productionKwh(latitudeDeg, family, tiltDeg, kwc, aspect);
  const perPanelYield = family === 'eastwest'
    ? (specificYield(latitudeDeg, tiltDeg, aspect - 90) + specificYield(latitudeDeg, tiltDeg, aspect + 90)) / 2
    : specificYield(latitudeDeg, tiltDeg, aspect);
  return { family, tiltDeg, azimuthDeg: pack.azimuthDeg, pack, grid, fitCount, placedCount, placedAnnualKwh, perPanelYield };
}

/** Vrai si `a` est une MEILLEURE reco que `b` : plus de production POSÉE ; à
 * production égale, l'inclinaison la plus RAIDE (meilleur rendement/panneau, donc
 * moins de matériel pour la même énergie). C'est ce départage qui garde l'optimal
 * sur un toit spacieux (là où tous les angles posent le même `besoin`). */
function betterCapped(a: CappedEval, b: CappedEval): boolean {
  if (a.placedAnnualKwh > b.placedAnnualKwh + EVAL_EPS) return true;
  if (a.placedAnnualKwh < b.placedAnnualKwh - EVAL_EPS) return false;
  return a.tiltDeg > b.tiltDeg; // égalité de production → préférer le plus raide
}

/**
 * Balayage Sud capé : pour chaque inclinaison de TILT_SWEEP_MIN à l'optimal, pave
 * le toit, plafonne au besoin et garde l'inclinaison qui MAXIMISE la production des
 * panneaux POSÉS (départage `betterCapped`). Calcule au passage le « max énergie
 * totale sur ce toit » NON capé (info), borné par l'optimal par panneau.
 *  - Toit spacieux (fit ≥ besoin partout) : posés = besoin constant → la production
 *    posée vaut besoin × rendement/panneau, maximisée à l'optimal → garde l'optimal,
 *    aucun sur-remplissage.
 *  - Toit limité : aplatir augmente le fit plus vite que le rendement/panneau ne
 *    baisse → la production posée monte → choisit une inclinaison plus plate, MAIS
 *    plafonnée : dès que le fit atteint le besoin, le raide reprend l'avantage.
 */
export function tiltSweepSouth(
  ring: LngLat[],
  latitudeDeg: number,
  needed: number,
  obstructions: LngLat[][] = [],
  capOpts: CappedOpts = {},
): { best: CappedEval; maxRoofEnergyTiltDeg: number; maxRoofEnergyKwh: number } {
  const optTilt = optimalSouthTiltDeg(latitudeDeg);
  const azimuthDeg = capOpts.azimuthDeg ?? familyAzimuthDeg('south');
  let best: CappedEval | null = null;
  let maxRoofEnergyKwh = -1;
  let maxRoofEnergyTiltDeg = optTilt;
  for (let t = TILT_SWEEP_MIN; t <= optTilt; t += TILT_SWEEP_STEP) {
    const e = evalCapped(ring, latitudeDeg, 'south', t, needed, obstructions, capOpts);
    if (!best || betterCapped(e, best)) best = e;
    // Énergie totale NON capée (info « max sur ce toit ») : départage plus plat.
    const fullKwh = gridAnnualKwh(e.grid, 'south', t, latitudeDeg, azimuthDeg);
    if (fullKwh > maxRoofEnergyKwh + EVAL_EPS || (Math.abs(fullKwh - maxRoofEnergyKwh) <= EVAL_EPS && t < maxRoofEnergyTiltDeg)) {
      maxRoofEnergyKwh = fullKwh;
      maxRoofEnergyTiltDeg = t;
    }
  }
  // Garantit l'optimal exact dans le balayage même si (optTilt − MIN) % STEP ≠ 0.
  if (!best || best.tiltDeg !== optTilt) {
    const e = evalCapped(ring, latitudeDeg, 'south', optTilt, needed, obstructions, capOpts);
    if (!best || betterCapped(e, best)) best = e;
  }
  return { best: best!, maxRoofEnergyTiltDeg, maxRoofEnergyKwh: Math.max(0, maxRoofEnergyKwh) };
}

/** Meilleur Est-Ouest capé sur les inclinaisons candidates. */
function bestEastWest(
  ring: LngLat[],
  latitudeDeg: number,
  needed: number,
  obstructions: LngLat[][],
  capOpts: CappedOpts = {},
): CappedEval {
  let best: CappedEval | null = null;
  for (const t of EW_SWEEP_TILTS) {
    const e = evalCapped(ring, latitudeDeg, 'eastwest', t, needed, obstructions, capOpts);
    if (!best || betterCapped(e, best)) best = e;
  }
  return best!;
}

function configResultFromCapped(
  id: string,
  label: string,
  notes: string,
  e: CappedEval,
  target: number,
): ConfigResult {
  const annualKwh = e.placedAnnualKwh;
  const kwc = (e.placedCount * PANEL2_WATT) / 1000;
  const bifGain = e.family === 'eastwest' || e.tiltDeg < 12 ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
  const savings = annualSavingsMad(annualKwh, target);
  return {
    id,
    family: e.family,
    tiltDeg: e.tiltDeg,
    azimuthDeg: e.azimuthDeg,
    label,
    panelOrientation: e.grid.panelOrientation,
    count: e.placedCount,
    kwc,
    specificYield: kwc > 0 ? annualKwh / kwc : 0,
    annualKwh,
    bifacialAnnualKwh: annualKwh * (1 + bifGain),
    pctOfTarget: target > 0 ? (annualKwh / target) * 100 : 0,
    savingsLow: savings.low,
    savingsHigh: savings.high,
    notes,
  };
}

/** Évalue le panel complet de configurations + l'algorithme de recommandation V2. */
export function recommend(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  options: RecommendOptions = {},
): Recommendation {
  const target = billToAnnualKwh(monthlyBillMad);
  const annualBillMad = billMAD(target / 12) * 12; // facture énergie modélisée
  const effectiveRateMadPerKwh = target > 0 ? annualBillMad / target : 0;
  const optTilt = optimalSouthTiltDeg(latitudeDeg);
  const needed = neededPanelsForTarget(target, latitudeDeg);
  const defaultSetbackM = PERIMETER_SETBACK_M;
  const setbackM = options.setbackM ?? defaultSetbackM;

  // Azimut réel des arêtes du toit. Un toit franchement tourné (> 2° du sud) ouvre
  // un candidat « aligné toit » qui suit ses arêtes au lieu d'être plein sud.
  const roofAz = roofDominantAzimuthDeg(ring);
  const offSouthDeg = ((roofAz - 180 + 540) % 360) - 180;
  const offSouthRounded = Math.round(Math.abs(offSouthDeg));
  // Opt-in (pro-5) ET toit franchement tourné. Sans l'opt-in, roofAligned reste
  // false → aucun candidat aligné, recommandation identique au moteur d'origine
  // (pro-4 inchangé). `roofAlignedAzimuthDeg` reste exposé pour info.
  const roofAligned = options.enableRoofAligned === true && Math.abs(offSouthDeg) >= 2;

  // Comparatif FIXE (compte RAW = ce qui tient ; l'écran re-plafonne au besoin
  // LIVE via placedFor — inchangé vs pro-3). À setback courant pour refléter le
  // toggle marge de l'UI.
  const specs: ConfigSpec[] = [
    { id: 'south-opt', family: 'south', tiltDeg: optTilt, label: `Sud ${optTilt}° (optimal)`, notes: 'Meilleur rendement par panneau, rangées larges.' },
    { id: 'south-15', family: 'south', tiltDeg: 15, label: 'Sud 15°', notes: 'Plus de panneaux, rendement/kWc légèrement moindre.' },
    { id: 'south-10', family: 'south', tiltDeg: 10, label: 'Sud 10°', notes: 'Encore plus dense ; reste au-dessus du plat.' },
    { id: 'ew-10', family: 'eastwest', tiltDeg: 10, label: 'Est-Ouest 10°', notes: 'Densité kWc maximale (onduleur double-MPPT requis).' },
    { id: 'ew-15', family: 'eastwest', tiltDeg: 15, label: 'Est-Ouest 15°', notes: 'Est-Ouest un peu plus incliné.' },
  ];

  const comparison: ConfigResult[] = [];
  for (const spec of specs) {
    const pack = packConfig(ring, latitudeDeg, { family: spec.family, tiltDeg: spec.tiltDeg, obstructions, setbackM });
    comparison.push(buildConfigResult(spec.id, spec.label, spec.notes, pack, pack.best, latitudeDeg, target));
  }

  // — Balayage capé : meilleur Sud (inclinaison libre) vs meilleur Est-Ouest. —
  const sweep = tiltSweepSouth(ring, latitudeDeg, needed, obstructions, { setbackM });
  const southBest = sweep.best;
  const ewBest = bestEastWest(ring, latitudeDeg, needed, obstructions, { setbackM });
  // Référence « Sud à l'optimal » (pour le toit-limité + le message d'honnêteté).
  const optEval = southBest.tiltDeg === optTilt
    ? southBest
    : evalCapped(ring, latitudeDeg, 'south', optTilt, needed, obstructions, { setbackM });

  const roofLimited = needed > 0 && optEval.fitCount < needed;

  // — Candidat ALIGNÉ TOIT : balayage Sud aux arêtes du toit. On ne le consulte QUE
  //   quand le plein sud standard NE COUVRE PAS le besoin (densifier) ou pour
  //   maximiser l'énergie totale (plafond toit) — jamais quand le sud suffit déjà
  //   dans le cap « besoin ». Sur un toit aligné (carré/orthogonal), roofAligned est
  //   faux → ce bloc est inerte et la reco reste octet pour octet celle de la V2.
  const standardWinner = betterCapped(ewBest, southBest) ? ewBest : southBest;
  const standardMeetsNeed = needed > 0 && standardWinner.placedCount >= needed;
  let alignedBest: CappedEval | null = null;
  if (roofAligned && !standardMeetsNeed) {
    alignedBest = tiltSweepSouth(ring, latitudeDeg, needed, obstructions, { setbackM, azimuthDeg: roofAz }).best;
  }

  // L'E-O ne gagne que s'il pose STRICTEMENT plus de production utile (départage
  // `betterCapped` : sinon on garde le Sud, plus simple et meilleur rendement). Le
  // candidat aligné-toit n'entre en lice que lorsqu'il existe (toit tourné non
  // couvert au standard) et qu'il pose strictement plus que le standard.
  let winner = standardWinner;
  if (alignedBest && betterCapped(alignedBest, winner)) winner = alignedBest;

  // « Inclinaison plus plate retenue » ne décrit QUE le cas où la reco est un Sud
  // PLEIN (azimut 180) aplati sous l'optimal qui loge plus de panneaux (toit
  // limité). Un Sud ALIGNÉ-TOIT gagne pour une autre raison (l'azimut, pas
  // l'inclinaison) — il ne déclenche pas ce message.
  const flatterTiltChosen = winner.family === 'south'
    && winner.azimuthDeg === 180
    && winner.tiltDeg < optTilt - EVAL_EPS
    && winner.placedCount > optEval.placedCount;
  const flatterTiltExtraEnergyPct = flatterTiltChosen && optEval.placedAnnualKwh > 0
    ? (winner.placedAnnualKwh / optEval.placedAnnualKwh - 1) * 100
    : 0;
  const flatterTiltYieldLossPct = flatterTiltChosen && optEval.perPanelYield > 0
    ? (1 - winner.perPanelYield / optEval.perPanelYield) * 100
    : 0;

  // Un Sud dont l'azimut suit les arêtes (≠ 180) gagne pour une raison distincte.
  const winnerAligned = winner.family === 'south' && winner.azimuthDeg !== 180;

  // Identité d'affichage : on réutilise un id du comparatif quand l'angle coïncide,
  // sinon on insère une ligne « reco » dédiée pour que le tableau porte le ✓.
  let id: string;
  let label: string;
  if (winner.family === 'eastwest') {
    id = winner.tiltDeg === 15 ? 'ew-15' : 'ew-10';
    label = `Est-Ouest ${winner.tiltDeg}°`;
  } else if (winnerAligned) {
    id = 'south-aligned-reco';
    label = `Sud aligné toit ${winner.tiltDeg}°`;
  } else if (winner.tiltDeg === optTilt) {
    id = 'south-opt';
    label = `Sud ${winner.tiltDeg}° (optimal)`;
  } else if (winner.tiltDeg === 15) {
    id = 'south-15';
    label = 'Sud 15°';
  } else if (winner.tiltDeg === 10) {
    id = 'south-10';
    label = 'Sud 10°';
  } else {
    id = 'south-reco';
    label = `Sud ${winner.tiltDeg}°`;
  }

  // Message FR honnête selon la situation.
  const winnerPct = target > 0 ? Math.round((winner.placedAnnualKwh / target) * 100) : 0;
  let notes: string;
  if (winner.family === 'eastwest') {
    notes = roofLimited
      ? `Ce toit ne loge pas tout le besoin plein sud ; en Est-Ouest dos à dos on densifie au maximum — ~${Math.round(winner.placedAnnualKwh)} kWh/an, soit ~${winnerPct} % de votre consommation.`
      : `L'Est-Ouest dos à dos maximise la production sur ce toit (onduleur double-MPPT requis).`;
  } else if (winnerAligned) {
    notes = `Le plein sud ne suffit pas sur ce toit tourné ; aligner les rangées sur les arêtes (≈${offSouthRounded}° du sud) loge plus de panneaux — ~${Math.round(winner.placedAnnualKwh)} kWh/an, soit ~${winnerPct} % de votre consommation.`;
  } else if (flatterTiltChosen) {
    notes = `Incliné à ~${winner.tiltDeg}° (au lieu de ~${optTilt}° optimal) pour faire tenir plus de panneaux : +${Math.round(flatterTiltExtraEnergyPct)} % de production totale malgré ~${Math.round(flatterTiltYieldLossPct)} % de rendement par panneau en moins — c'est le meilleur choix sur ce toit limité.`;
  } else if (roofLimited) {
    notes = `Ce toit plafonne à ~${Math.round(winner.placedAnnualKwh)} kWh/an au mieux ; ${winner.tiltDeg}° plein sud y maximise la production des panneaux qui tiennent.`;
  } else {
    notes = `${winner.tiltDeg}° plein sud est l'angle optimal pour votre latitude et couvre votre consommation — aucun compromis ; il reste de la place sur le toit.`;
  }

  const recommended = configResultFromCapped(id, label, notes, winner, target);

  // Insère la ligne « reco » dans le comparatif si son id n'y figure pas déjà
  // (Sud à un angle balayé non listé, ou Sud aligné-toit) — pour que le ✓ s'affiche.
  if (id === 'south-reco' || id === 'south-aligned-reco') {
    const pack = packConfig(ring, latitudeDeg, {
      family: 'south',
      tiltDeg: winner.tiltDeg,
      azimuthDeg: winner.azimuthDeg,
      obstructions,
      setbackM,
    });
    comparison.push(buildConfigResult(id, `${label} (recommandé)`, notes, pack, pack.best, latitudeDeg, target));
  }

  // — Groupe AZIMUT : plein sud par défaut ; aligné-toit seulement si la config
  //   recommandée est elle-même alignée, OU (toit limité) si l'array sud aligné
  //   produit plus d'énergie totale que le plein sud. Jamais un azimut inventé :
  //   azimuthRec ∈ {180, roofAz}.
  let azimuthRec = 180;
  if (winnerAligned) {
    azimuthRec = winner.azimuthDeg;
  } else if (roofAligned && roofLimited) {
    const alignedFull = gridAnnualKwh(
      packConfig(ring, latitudeDeg, { family: 'south', tiltDeg: optTilt, azimuthDeg: roofAz, obstructions, setbackM }).best,
      'south',
      optTilt,
      latitudeDeg,
      roofAz,
    );
    const southFull = gridAnnualKwh(optEval.grid, 'south', optTilt, latitudeDeg, 180);
    if (alignedFull > southFull + EVAL_EPS) azimuthRec = roofAz;
  }

  // — Groupe MARGE : garder si le besoin est DÉJÀ atteint avec la marge en place ;
  //   la retirer (récupérer la rive) seulement sinon. Question posée À MARGE ACTIVE,
  //   indépendamment de la marge affichée par l'UI.
  const metAtDefaultMargin =
    setbackM === defaultSetbackM
      ? !roofLimited
      : (() => {
          const need = needed;
          const s = tiltSweepSouth(ring, latitudeDeg, need, obstructions, { setbackM: defaultSetbackM }).best;
          const e = bestEastWest(ring, latitudeDeg, need, obstructions, { setbackM: defaultSetbackM });
          const w = betterCapped(e, s) ? e : s;
          return need > 0 && w.placedCount >= need;
        })();
  const marginRec: 'keep' | 'remove' = metAtDefaultMargin ? 'keep' : 'remove';

  const recommendedOptions: RecommendedOptions = {
    family: recommended.family,
    panelOrientation: recommended.panelOrientation,
    tiltDeg: recommended.tiltDeg,
    azimuthDeg: azimuthRec,
    margin: marginRec,
  };

  return {
    targetAnnualKwh: target,
    recommended: { ...recommended, roofMaxCount: winner.fitCount },
    comparison,
    roofLimited,
    maxPerPanelTiltDeg: optTilt,
    maxRoofEnergyTiltDeg: sweep.maxRoofEnergyTiltDeg,
    maxRoofEnergyKwh: sweep.maxRoofEnergyKwh,
    annualBillMad,
    effectiveRateMadPerKwh,
    neededPanels: needed,
    recommendedTiltDeg: winner.tiltDeg,
    flatterTiltChosen,
    flatterTiltExtraEnergyPct,
    flatterTiltYieldLossPct,
    roofAlignedAzimuthDeg: roofAz,
    setbackM,
    recommendedOptions,
  };
}

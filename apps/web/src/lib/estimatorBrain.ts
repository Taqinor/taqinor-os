/**
 * CERVEAU de l'estimateur piloté par la facture (preview privé
 * /preview/toiture-3d-pro-3). Module PUR, testé (tests/estimatorBrain.test.ts) :
 * aucun DOM, aucune carte, aucune dépendance.
 *
 * WJ69 — DÉPRÉCIÉ, LABO SEULEMENT (2026-07). Ce module (« V1 ») n'est plus le
 * moteur du parcours PUBLIC : `billEstimate.ts` (le calcul qui alimente
 * /devis/mon-toit, donc CHAQUE estimation client) pointe désormais vers
 * `estimatorBrainV2.ts`, qui est une copie versionnée à parité PROUVÉE de V1
 * (mêmes fonctions/mêmes corps, cf. tests/estimatorBrainV2.test.ts) PLUS les
 * améliorations honnêtes non rétro-portées ici (tarifs par régie WJ23, bande
 * de confiance climatique WJ22, modèle batterie approfondi WJ24, plafond
 * DC:AC, dégradation annuelle…). Ce fichier reste vivant UNIQUEMENT pour le
 * preview privé /preview/toiture-3d-pro-3 (roof-tool-pro3.ts) — NE PAS lui
 * ajouter de nouveau call-site public ; tout nouveau besoin PUBLIC doit
 * consommer estimatorBrainV2.ts. Ne pas supprimer (le lab en dépend encore).
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

// ===== Modèle de facturation — barème RÉGIE ONEE « usage domestique » (juin 2026) =====
// Coût de l'ÉNERGIE uniquement (les tranches au kWh). Prix CONSOMMATEUR TTC : la
// TVA 20 % est DÉJÀ incluse dans ces taux — ne JAMAIS rajouter de TVA par-dessus.
// Les frais fixes (TPPAN, redevances, taxes d'abonnement) ne sont PAS modélisés :
// invariants au solaire, ils s'annulent dans le calcul d'économies.
//
// DEUX RÉGIMES au Maroc : le barème RÉGIE/gouvernement (Marrakech, Agadir, El Jadida
// et toutes les zones ONEE/régie) et des grilles contractuelles plus chères dans les
// trois villes ex-délégataires (Casablanca/Lydec, Rabat/Redal, Tanger/Amendis).
// POUR L'INSTANT toutes les villes utilisent le barème RÉGIE (défaut conservateur) —
// voir TARIFF_BY_CITY et ESTIMATOR_BRAIN_NOTES.md.

export interface TariffTranche {
  upToKwh: number;
  rate: number;
}
export interface TariffGrid {
  /** Tranches PROGRESSIVES (≤ seuil) : chaque tranche facturée à son propre tarif. */
  progressive: TariffTranche[];
  /** Tranches SÉLECTIVES (> seuil) : TOUTE la conso au tarif de SA tranche. */
  selective: TariffTranche[];
  /** Conso mensuelle (kWh) au-delà de laquelle on bascule en facturation sélective. */
  selectiveThresholdKwh: number;
  /** Tolérance de tranche (kWh) : on n'entre dans la tranche suivante qu'à +tolérance. */
  boundaryToleranceKwh: number;
}

/**
 * Barème RÉGIE ONEE « usage domestique » — prix consommateur TTC (TVA 20 % DÉJÀ
 * incluse), juin 2026, fourni et vérifié par le fondateur :
 *  - ≤ 150 kWh/mois → PROGRESSIF : 0–100 = 0,9010 ; 101–150 = 1,0732.
 *  - > 150 kWh/mois → SÉLECTIF (toute la conso au tarif de sa tranche) :
 *    151–210 = 1,0732 ; 211–310 = 1,1676 ; 311–510 = 1,3817 ; > 510 = 1,5958.
 * Les bornes nominales 200/300/500 + la tolérance de 10 kWh donnent les bornes
 * EFFECTIVES 210/310/510 (un client n'entre dans la tranche supérieure qu'à +10 kWh).
 * Remplace l'ancienne grille trop haute (201–300=1,18 ; 301–500=1,45 ; >500=1,66 —
 * 1,66 était le tarif FORCE-MOTRICE, pas le domestique).
 */
export const REGIE_TARIFF: TariffGrid = {
  progressive: [
    { upToKwh: 100, rate: 0.901 },
    { upToKwh: 150, rate: 1.0732 },
  ],
  selective: [
    { upToKwh: 200, rate: 1.0732 }, // effectif 151–210
    { upToKwh: 300, rate: 1.1676 }, // effectif 211–310
    { upToKwh: 500, rate: 1.3817 }, // effectif 311–510
    { upToKwh: Infinity, rate: 1.5958 }, // > 510
  ],
  selectiveThresholdKwh: 150,
  boundaryToleranceKwh: 10,
};

/**
 * Grille tarifaire par ville. POUR L'INSTANT chaque ville est égalée au barème RÉGIE
 * (défaut conservateur) : cela SOUS-estime légèrement les économies dans les trois
 * villes ex-délégataires — la posture SÛRE, jamais l'inverse. Les grilles
 * délégataires EXACTES attendent une vraie facture récente par ville.
 */
export const TARIFF_BY_CITY: Record<string, TariffGrid> = {
  // Casablanca/Lydec — la prime réelle sur le haut de grille ≈ +10,5 % (relevés HT :
  // 1,0220 pour 151–210 · 1,1119 pour 211–310 · 1,5193 pour > 510). Égalée au barème
  // régie POUR L'INSTANT (grille exacte en attente d'une vraie facture Lydec).
  Casablanca: REGIE_TARIFF,
  // Rabat/Redal — la MOINS chère des trois (au plus proche du barème régie). Égalée
  // au barème régie pour l'instant.
  Rabat: REGIE_TARIFF,
  // Tanger/Amendis — la PLUS chère des trois. Égalée au barème régie pour l'instant
  // (grille exacte en attente d'une vraie facture Amendis).
  Tanger: REGIE_TARIFF,
};

/** Grille tarifaire à appliquer pour une ville (défaut : barème RÉGIE conservateur). */
export function tariffForCity(city?: string): TariffGrid {
  if (city && Object.prototype.hasOwnProperty.call(TARIFF_BY_CITY, city)) return TARIFF_BY_CITY[city];
  return REGIE_TARIFF;
}

/** Part autoconsommée réellement alignée dans le temps (borne basse de la fourchette). */
const SELF_CONSUMPTION_TIMING_LOW = 0.75;

/** Coût progressif (≤ seuil) — somme des tranches à leur tarif. */
function progressiveBillMAD(monthlyKwh: number, grid: TariffGrid = REGIE_TARIFF): number {
  let cost = 0;
  let prev = 0;
  for (const b of grid.progressive) {
    const upper = Math.min(monthlyKwh, b.upToKwh);
    if (upper > prev) cost += (upper - prev) * b.rate;
    prev = b.upToKwh;
    if (monthlyKwh <= b.upToKwh) break;
  }
  return cost;
}

/**
 * Facture ÉNERGIE mensuelle (MAD) pour une conso mensuelle (kWh), barème `grid`
 * (défaut : RÉGIE) : progressive ≤ seuil, sinon SÉLECTIVE (toute la conso au tarif de
 * sa tranche, tolérance de bord). Monotone non-décroissante par construction (les
 * tarifs montent à chaque tranche), garantie au raccord progressif→sélectif par un
 * plancher.
 */
export function billMAD(monthlyKwh: number, grid: TariffGrid = REGIE_TARIFF): number {
  if (!Number.isFinite(monthlyKwh) || monthlyKwh <= 0) return 0;
  const k = monthlyKwh;
  if (k <= grid.selectiveThresholdKwh) return progressiveBillMAD(k, grid);
  let rate = grid.selective[grid.selective.length - 1].rate;
  for (const b of grid.selective) {
    if (k <= b.upToKwh + grid.boundaryToleranceKwh) {
      rate = b.rate;
      break;
    }
  }
  // Plancher au seuil : un client juste au-dessus du seuil ne paie jamais moins que
  // la facture progressive au seuil.
  return Math.max(k * rate, progressiveBillMAD(grid.selectiveThresholdKwh, grid));
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
export function billToAnnualKwh(monthlyBillMad: number, grid: TariffGrid = REGIE_TARIFF): number {
  if (!Number.isFinite(monthlyBillMad) || monthlyBillMad <= 0) return 0;
  let lo = 0;
  let hi = 1000;
  while (billMAD(hi, grid) < monthlyBillMad && hi < 1e6) hi *= 2;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (billMAD(mid, grid) < monthlyBillMad) lo = mid;
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
  grid: TariffGrid = REGIE_TARIFF,
): { low: number; high: number } {
  const consMo = Math.max(0, consumptionKwhYr) / 12;
  const prodMo = Math.max(0, productionKwhYr) / 12;
  const selfHi = Math.min(prodMo, consMo);
  const selfLo = SELF_CONSUMPTION_TIMING_LOW * selfHi;
  const billCons = billMAD(consMo, grid);
  const high = (billCons - billMAD(consMo - selfHi, grid)) * 12;
  const low = (billCons - billMAD(consMo - selfLo, grid)) * 12;
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
  const cellInside = (corners: [number, number][]): boolean =>
    corners.every((c) => pointInPolygon(c, ringENU) && distToBoundary(c, ringENU) >= setbackM - EDGE_EPS_M);

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
  const azimuthDeg = familyAzimuthDeg(opts.family);
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
 * famille/inclinaison. E-O = somme des sous-champs Est (−90°) et Ouest (+90°). */
export function productionKwh(
  latitudeDeg: number,
  family: ConfigFamily,
  tiltDeg: number,
  kwc: number,
): number {
  if (family === 'eastwest') {
    const yE = specificYield(latitudeDeg, tiltDeg, -90);
    const yW = specificYield(latitudeDeg, tiltDeg, 90);
    return (kwc / 2) * yE + (kwc / 2) * yW;
  }
  return kwc * specificYield(latitudeDeg, tiltDeg, 0);
}

function gridAnnualKwh(grid: PanelGrid, family: ConfigFamily, tiltDeg: number, latitudeDeg: number): number {
  return productionKwh(latitudeDeg, family, tiltDeg, grid.kwc);
}

function buildConfigResult(
  id: string,
  label: string,
  notes: string,
  pack: PackResult,
  grid: PanelGrid,
  latitudeDeg: number,
  consumptionKwh: number,
  tariff: TariffGrid = REGIE_TARIFF,
): ConfigResult {
  const annualKwh = gridAnnualKwh(grid, pack.family, pack.tiltDeg, latitudeDeg);
  const bifGain = pack.family === 'eastwest' || pack.tiltDeg < 12 ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
  const savings = annualSavingsMad(annualKwh, consumptionKwh, tariff);
  return {
    id,
    family: pack.family,
    tiltDeg: pack.tiltDeg,
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
}

interface ConfigSpec {
  id: string;
  family: ConfigFamily;
  tiltDeg: number;
  label: string;
  notes: string;
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

/** Évalue le panel complet de configurations + l'algorithme de recommandation. */
export function recommend(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
  city?: string,
): Recommendation {
  // Barème tarifaire selon la ville (défaut : RÉGIE conservateur ; toutes les villes
  // y sont égalées pour l'instant — voir TARIFF_BY_CITY).
  const grid = tariffForCity(city);
  const target = billToAnnualKwh(monthlyBillMad, grid);
  const annualBillMad = billMAD(target / 12, grid) * 12; // facture énergie modélisée
  const effectiveRateMadPerKwh = target > 0 ? annualBillMad / target : 0;
  const optTilt = optimalSouthTiltDeg(latitudeDeg);

  const specs: ConfigSpec[] = [
    { id: 'south-opt', family: 'south', tiltDeg: optTilt, label: `Sud ${optTilt}° (optimal)`, notes: 'Meilleur rendement par panneau, rangées larges.' },
    { id: 'south-15', family: 'south', tiltDeg: 15, label: 'Sud 15°', notes: 'Plus de panneaux, rendement/kWc légèrement moindre.' },
    { id: 'south-10', family: 'south', tiltDeg: 10, label: 'Sud 10°', notes: 'Encore plus dense ; reste au-dessus du plat.' },
    { id: 'ew-10', family: 'eastwest', tiltDeg: 10, label: 'Est-Ouest 10°', notes: 'Densité kWc maximale (onduleur double-MPPT requis).' },
    { id: 'ew-15', family: 'eastwest', tiltDeg: 15, label: 'Est-Ouest 15°', notes: 'Est-Ouest un peu plus incliné.' },
  ];

  const comparison: ConfigResult[] = [];
  for (const spec of specs) {
    const pack = packConfig(ring, latitudeDeg, { family: spec.family, tiltDeg: spec.tiltDeg, obstructions });
    comparison.push(buildConfigResult(spec.id, spec.label, spec.notes, pack, pack.best, latitudeDeg, target, grid));
  }

  // « Max énergie totale sur CE toit » : balayage sud 5°→30°.
  let maxRoofEnergyKwh = -1;
  let maxRoofEnergyTiltDeg = optTilt;
  for (let t = 5; t <= 30; t++) {
    const pack = packConfig(ring, latitudeDeg, { family: 'south', tiltDeg: t, obstructions });
    const kwh = gridAnnualKwh(pack.best, 'south', t, latitudeDeg);
    if (kwh > maxRoofEnergyKwh) {
      maxRoofEnergyKwh = kwh;
      maxRoofEnergyTiltDeg = t;
    }
  }

  const byId = (id: string) => comparison.find((c) => c.id === id)!;
  const configA = byId('south-opt');
  const roofMaxCount = configA.count;

  let recommended: ConfigResult;
  let roofLimited = false;

  if (configA.annualKwh >= target && target > 0) {
    // Couvre à l'optimal → dimensionner au besoin (cible + 10 %, plafonné au toit).
    const yld = specificYield(latitudeDeg, configA.tiltDeg, 0);
    const kwcNeeded = (target * COVERAGE_MARGIN) / yld;
    const panelsNeeded = Math.min(configA.count, Math.max(1, Math.ceil(kwcNeeded / (PANEL2_WATT / 1000))));
    const kwc = (panelsNeeded * PANEL2_WATT) / 1000;
    const annualKwh = kwc * yld;
    const savings = annualSavingsMad(annualKwh, target, grid);
    recommended = {
      ...configA,
      count: panelsNeeded,
      kwc,
      annualKwh,
      bifacialAnnualKwh: annualKwh * (1 + BIFACIAL_GAIN_TILTED),
      pctOfTarget: target > 0 ? (annualKwh / target) * 100 : 0,
      savingsLow: savings.low,
      savingsHigh: savings.high,
      notes: `${configA.tiltDeg}° plein sud est l'angle optimal pour votre latitude et couvre votre consommation — aucun compromis ; il reste de la place sur le toit.`,
    };
  } else {
    // Densifier en s'arrêtant à la première config (meilleure qualité) qui couvre.
    const order = ['south-15', 'south-10', 'ew-10', 'ew-15'];
    let pick: ConfigResult | undefined;
    for (const id of order) {
      const c = byId(id);
      if (c.annualKwh >= target && target > 0) {
        pick = c;
        break;
      }
    }
    if (pick) {
      recommended = { ...pick, notes: `Le sud à l'inclinaison optimale ne suffit pas sur ce toit ; ${pick.label.toLowerCase()} densifie l'installation pour couvrir votre consommation.` };
    } else {
      // Plafond toit : E-O max densité + message honnête.
      roofLimited = true;
      const ew = [byId('ew-10'), byId('ew-15')].sort((a, b) => b.annualKwh - a.annualKwh)[0];
      const best = [ew, configA, byId('south-10')].sort((a, b) => b.annualKwh - a.annualKwh)[0];
      const chosen = best.family === 'eastwest' ? best : ew; // privilégier l'E-O en plafond densité
      const pct = chosen.pctOfTarget;
      recommended = {
        ...chosen,
        notes: `Ce toit plafonne à ~${Math.round(chosen.annualKwh)} kWh/an, soit ~${Math.round(pct)} % de votre consommation. L'Est-Ouest maximise ce qui est possible ici.`,
      };
    }
  }

  return {
    targetAnnualKwh: target,
    recommended: { ...recommended, roofMaxCount },
    comparison,
    roofLimited,
    maxPerPanelTiltDeg: optTilt,
    maxRoofEnergyTiltDeg,
    maxRoofEnergyKwh: Math.max(0, maxRoofEnergyKwh),
    annualBillMad,
    effectiveRateMadPerKwh,
  };
}

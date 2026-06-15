/**
 * CERVEAU de l'estimateur piloté par la facture (preview privé
 * /preview/toiture-3d-pro-3). Module PUR, testé (tests/estimatorBrain.test.ts) :
 * aucun DOM, aucune carte, aucune dépendance.
 *
 * Entrées : tracé du toit (lng/lat), latitude du toit, facture mensuelle (MAD).
 * Sorties : configurations classées (Sud optimal, Sud basse inclinaison,
 * Est-Ouest) avec compte de panneaux, kWc, production annuelle, % de la facture
 * couverte, fourchette d'économies — et une recommandation dimensionnée au besoin.
 *
 * Réutilise :
 *  - la géométrie pure de roof.ts (aire géodésique, point-dans-polygone, tarif,
 *    fourchette d'économies — base PARTAGÉE avec le reste du site) ;
 *  - le vrai panneau Canadian Solar 720 W de roofPro2.ts ;
 *  - la table de productible PVGIS committée (yieldTable.ts).
 *
 * JAMAIS un devis : une fourchette indicative. Voir apps/web/ESTIMATOR_BRAIN_NOTES.md.
 */
import {
  geodesicAreaM2,
  pointInPolygon,
  annualSavingsBandMad,
  TARIFF_MAD_PER_KWH,
  type LngLat,
} from './roof';
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
const EW_RIDGE_GAP_M = 0.15; // petit jeu entre paires Est-Ouest dos à dos (≈ jointif)
const SHADOW_MARGIN_M = 0.05; // marge en plus de l'ombre calculée

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

export interface PitchOptions {
  /** Heure solaire du moment de design (défaut DESIGN_SOLAR_HOUR = 10 h). */
  solarHour?: number;
}

/**
 * Pas inter-rangées (m, centre à centre dans le sens de la pente) pour qu'une
 * rangée n'ombre pas la suivante au moment de design :
 *   D = L · [ cos β + sin β · cos γ_s / tan α_s ]
 */
export function rowPitchM(
  slopeLenM: number,
  tiltDeg: number,
  latitudeDeg: number,
  opts: PitchOptions = {},
): number {
  const beta = tiltDeg * DEG2RAD;
  const sun = sunPositionWinterSolstice(latitudeDeg, opts.solarHour ?? DESIGN_SOLAR_HOUR);
  const alpha = Math.max(5, sun.elevationDeg) * DEG2RAD; // garde-fou soleil très bas
  const gamma = sun.azimuthFromSouthDeg * DEG2RAD;
  const footprint = slopeLenM * Math.cos(beta);
  const shadow = (slopeLenM * Math.sin(beta) * Math.cos(gamma)) / Math.tan(alpha);
  return footprint + Math.max(0, shadow) + SHADOW_MARGIN_M;
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
  // azimut encadrant
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
  // ville encadrante en latitude
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

/** Facture mensuelle (MAD) → consommation annuelle estimée (kWh).
 * Base RÉUTILISÉE du site : tarif moyen 1,4 MAD/kWh (roof.ts / billRange.ts). */
export function billToAnnualKwh(monthlyBillMad: number): number {
  if (!Number.isFinite(monthlyBillMad) || monthlyBillMad <= 0) return 0;
  return (monthlyBillMad * 12) / TARIFF_MAD_PER_KWH;
}

// — Pavage —

export type ConfigFamily = 'south' | 'eastwest';

export interface PackOptions {
  family: ConfigFamily;
  tiltDeg: number;
  /** Tracés d'obstructions (cheminée, skylight, bâche) à déduire. */
  obstructions?: LngLat[][];
  setbackM?: number;
}

export interface PanelGrid {
  panelOrientation: 'portrait' | 'landscape';
  count: number;
  kwc: number;
  rowPitchM: number;
  panels: { cx: number; cy: number }[];
  /** Sens de la pente du panneau (m). */
  slopeLenM: number;
  /** Largeur le long de la rangée (m). */
  rowWidthM: number;
}

export interface PackResult {
  origin: LngLat;
  ringENU: [number, number][];
  azimuthDeg: number;
  tiltDeg: number;
  family: ConfigFamily;
  areaM2: number;
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

interface OneGridParams {
  slopeLenM: number;
  rowWidthM: number;
  pitchM: number;
}

function packOneGrid(
  ringENU: [number, number][],
  obstructionsENU: [number, number][][],
  azimuthDeg: number,
  setbackM: number,
  p: OneGridParams,
): { count: number; panels: { cx: number; cy: number }[] } {
  if (ringENU.length < 3) return { count: 0, panels: [] };
  const azRad = azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
  const s = f; // les rangées s'empilent vers la visée
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
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) return { count: 0, panels: [] };

  const toENU = (uu: number, vv: number): [number, number] => [
    uu * u[0] + vv * s[0],
    uu * u[1] + vv * s[1],
  ];
  const inObstruction = (c: [number, number]): boolean =>
    obstructionsENU.some((o) => pointInPolygon(c, o));
  const ok = (corners: [number, number][], center: [number, number]): boolean =>
    corners.every((c) => pointInPolygon(c, ringENU) && distToBoundary(c, ringENU) >= setbackM) &&
    !inObstruction(center);

  const panels: { cx: number; cy: number }[] = [];
  const depthFootprint = p.slopeLenM * Math.cos(0); // empreinte gérée via pitch ; coin = slope projeté
  // L'empreinte projetée est < slopeLenM ; on pose le coin haut à pitch utile.
  const footprint = Math.min(p.slopeLenM, p.pitchM - SHADOW_MARGIN_M);
  void depthFootprint;
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + setbackM + r * p.pitchM;
    const v1 = v0 + footprint;
    if (v1 > vMax - setbackM + 1e-6) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + setbackM + c * colPitch;
      const u1 = u0 + p.rowWidthM;
      const corners: [number, number][] = [toENU(u0, v0), toENU(u1, v0), toENU(u1, v1), toENU(u0, v1)];
      const center = toENU(u0 + p.rowWidthM / 2, v0 + footprint / 2);
      if (!ok(corners, center)) continue;
      panels.push({ cx: center[0], cy: center[1] });
    }
  }
  return { count: panels.length, panels };
}

/** Pave le toit pour une config donnée, en portrait ET paysage, garde le meilleur. */
export function packConfig(ring: LngLat[], latitudeDeg: number, opts: PackOptions): PackResult {
  const areaM2 = geodesicAreaM2(ring);
  const azimuthDeg = familyAzimuthDeg(opts.family);
  const setbackM = opts.setbackM ?? PERIMETER_SETBACK_M;
  const tiltDeg = opts.tiltDeg;

  const empty = (panelOrientation: 'portrait' | 'landscape', slopeLenM: number, rowWidthM: number, pitchM: number): PanelGrid => ({
    panelOrientation,
    count: 0,
    kwc: 0,
    rowPitchM: pitchM,
    panels: [],
    slopeLenM,
    rowWidthM,
  });

  if (!Array.isArray(ring) || ring.length < 3) {
    const pPit = rowPitchM(PANEL2_LONG_M, tiltDeg, latitudeDeg);
    const lPit = rowPitchM(PANEL2_SHORT_M, tiltDeg, latitudeDeg);
    const portrait = empty('portrait', PANEL2_LONG_M, PANEL2_SHORT_M, pPit);
    const landscape = empty('landscape', PANEL2_SHORT_M, PANEL2_LONG_M, lPit);
    return { origin: ring?.[0] ?? [0, 0], ringENU: [], azimuthDeg, tiltDeg, family: opts.family, areaM2, portrait, landscape, best: portrait };
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
  const obstructionsENU = (opts.obstructions ?? []).map((o) => o.map(toENU));

  // Pas inter-rangées : Est-Ouest dos à dos = quasi jointif (pas d'ombre solaire) ;
  // sud = géométrie solaire anti-ombrage à la latitude du toit.
  const pitchFor = (slopeLenM: number): number =>
    opts.family === 'eastwest'
      ? slopeLenM * Math.cos(tiltDeg * DEG2RAD) + EW_RIDGE_GAP_M
      : rowPitchM(slopeLenM, tiltDeg, latitudeDeg);

  const makeGrid = (
    panelOrientation: 'portrait' | 'landscape',
    slopeLenM: number,
    rowWidthM: number,
  ): PanelGrid => {
    const pitchM = pitchFor(slopeLenM);
    const { count, panels } = packOneGrid(ringENU, obstructionsENU, azimuthDeg, setbackM, {
      slopeLenM,
      rowWidthM,
      pitchM,
    });
    return { panelOrientation, count, kwc: (count * PANEL2_WATT) / 1000, rowPitchM: pitchM, panels, slopeLenM, rowWidthM };
  };

  // Portrait : grand côté (2,384) dans le sens de la pente. Paysage : l'inverse.
  const portrait = makeGrid('portrait', PANEL2_LONG_M, PANEL2_SHORT_M);
  const landscape = makeGrid('landscape', PANEL2_SHORT_M, PANEL2_LONG_M);
  const best = portrait.count >= landscape.count ? portrait : landscape;

  return { origin: [olng, olat], ringENU, azimuthDeg, tiltDeg, family: opts.family, areaM2, portrait, landscape, best };
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

/** Production annuelle (kWh, face avant) d'une grille selon la famille/inclinaison. */
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
  targetAnnualKwh: number,
): ConfigResult {
  const annualKwh = gridAnnualKwh(grid, pack.family, pack.tiltDeg, latitudeDeg);
  const bifGain = pack.family === 'eastwest' || pack.tiltDeg < 12 ? BIFACIAL_GAIN_FLAT : BIFACIAL_GAIN_TILTED;
  const savings = annualSavingsBandMad(annualKwh);
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
    pctOfTarget: targetAnnualKwh > 0 ? (annualKwh / targetAnnualKwh) * 100 : 0,
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
  /** Tarif utilisé pour facture→énergie→économies (à confirmer). */
  tariffMadPerKwh: number;
}

interface ConfigSpec {
  id: string;
  family: ConfigFamily;
  tiltDeg: number;
  label: string;
  notes: string;
}

/** Évalue le panel complet de configurations + l'algorithme de recommandation. */
export function recommend(
  ring: LngLat[],
  latitudeDeg: number,
  monthlyBillMad: number,
  obstructions: LngLat[][] = [],
): Recommendation {
  const target = billToAnnualKwh(monthlyBillMad);
  const optTilt = optimalSouthTiltDeg(latitudeDeg);

  const specs: ConfigSpec[] = [
    { id: 'south-opt', family: 'south', tiltDeg: optTilt, label: `Sud ${optTilt}° (optimal)`, notes: 'Meilleur rendement par panneau, rangées larges.' },
    { id: 'south-15', family: 'south', tiltDeg: 15, label: 'Sud 15°', notes: 'Plus de panneaux, rendement/kWc légèrement moindre.' },
    { id: 'south-10', family: 'south', tiltDeg: 10, label: 'Sud 10°', notes: 'Encore plus dense ; reste au-dessus du plat.' },
    { id: 'ew-10', family: 'eastwest', tiltDeg: 10, label: 'Est-Ouest 10°', notes: 'Densité kWc maximale (onduleur double-MPPT requis).' },
    { id: 'ew-15', family: 'eastwest', tiltDeg: 15, label: 'Est-Ouest 15°', notes: 'Est-Ouest un peu plus incliné.' },
  ];

  const packs = new Map<string, PackResult>();
  const comparison: ConfigResult[] = [];
  for (const spec of specs) {
    const pack = packConfig(ring, latitudeDeg, { family: spec.family, tiltDeg: spec.tiltDeg, obstructions });
    packs.set(spec.id, pack);
    comparison.push(buildConfigResult(spec.id, spec.label, spec.notes, pack, pack.best, latitudeDeg, target));
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
    const savings = annualSavingsBandMad(annualKwh);
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
    tariffMadPerKwh: TARIFF_MAD_PER_KWH,
  };
}

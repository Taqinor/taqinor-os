/**
 * Moteur de DONNÉES DE PRODUCTION server-side (W49) — pour l'estimateur toiture.
 *
 * PURE LOGIQUE, testable hors réseau : toutes les fonctions reçoivent leurs
 * données PVGIS déjà récupérées (la récupération réseau vit dans
 * roofEstimate.ts, appelée uniquement côté serveur par /api/roof-production —
 * le navigateur ne touche JAMAIS PVGIS, CORS oblige).
 *
 * Tout est calculé PAR 1 kWc puis MIS À L'ÉCHELLE par la taille réellement
 * posée (placedKwc) — la production PVGIS est linéaire en kWc, donc on interroge
 * à 1 kWc et on multiplie ensuite. Convention azimut PVGIS : Sud=0, Est=−90,
 * Ouest=+90, Nord=180 (identique à roofEstimate.ts).
 *
 * RÉCONCILIATION DES ÉCHELLES (énoncée dans le rapport) : PVcalc fournit l'ANCRE
 * — la production annuelle E_y et les 12 totaux mensuels E_m (moyennes long
 * terme de PVGIS). seriescalc fournit la FORME horaire multi-années (jours
 * types, dates précises). On dérive les silhouettes horaires de seriescalc puis
 * on RECALE chaque mois pour que l'intégrale du jour-type × nombre de jours du
 * mois égale exactement E_m de PVcalc. Ainsi : jour-type → total journalier →
 * total mensuel → total annuel sont mutuellement cohérents et ancrés sur PVcalc.
 *
 * Le moteur ne fabrique AUCUN chiffre d'économies : il ne renvoie que de la
 * PRODUCTION (kWh). Le modèle d'économies honnête plafonné (autoconsommation
 * seule, surplus non rémunéré) reste celui d'estimatorBrain* — non touché ici.
 */

import {
  fetchPvgisMonthlySeries,
  fetchPvgisHourlySeries,
  fetchPvgisDailyProfiles,
  type PvcalcMonthly,
  type SeriesHourlyPoint,
  type DrcalcDailyPoint,
} from './roofEstimate';

/** Puissance crête d'un panneau Canadian Solar 720 W (kWc). */
export const PANEL_KWC = 0.72;

/** Nombre de jours par mois (année non bissextile — moyenne long terme). */
export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

/** Étiquettes mensuelles FR courtes (index 0 = janvier). */
export const MONTH_LABELS_FR = [
  'janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin',
  'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.',
];

/** kWc posé à partir d'un nombre de panneaux (Canadian Solar 720 W). */
export function placedKwcFromPanels(panels: number): number {
  if (!Number.isFinite(panels) || panels <= 0) return 0;
  return panels * PANEL_KWC;
}

/** Le plan courant interrogé : GPS + orientation + type de pose. */
export interface ProductionPlane {
  lat: number;
  lon: number;
  /** Inclinaison en degrés (0 = plat). */
  tiltDeg: number;
  /** Azimut PVGIS : Sud=0, Est=−90, Ouest=+90, Nord=180. */
  aspect: number;
  /** 'free' = toit PLAT racké (panneaux aérés) ; 'building' = pose pitched intégrée. */
  mountingplace: 'building' | 'free';
}

/** Une série de profil horaire (24 valeurs, index = heure 0–23). */
export type HourlyProfile = number[];

/** Production complète PAR 1 kWc, ancrée sur PVcalc. */
export interface PerKwcProduction {
  /** Source réelle des données : PVGIS complet, PVGIS partiel, ou repli interne. */
  source: 'pvgis' | 'pvgis-monthly' | 'estimate';
  /** Production annuelle (kWh/kWc/an). */
  annualKwh: number;
  /** 12 totaux mensuels (kWh/kWc), index 0 = janvier. */
  monthlyKwh: number[];
  /**
   * Jour TYPE par mois : 12 profils horaires de PUISSANCE moyenne (kW par kWc),
   * index 0 = janvier ; chaque profil = 24 valeurs (heure 0–23). Moyenne sur
   * tous les jours du mois et toutes les années du relevé PVGIS.
   */
  typicalDayByMonth: HourlyProfile[];
  /**
   * Total journalier par mois (kWh/kWc/jour) = intégrale du jour-type ; recalé
   * pour que ×(jours du mois) = total mensuel.
   */
  dailyKwhByMonth: number[];
}

/** Production MISE À L'ÉCHELLE par le système posé (placedKwc). */
export interface ScaledProduction extends PerKwcProduction {
  /** kWc réellement posé ayant servi à l'échelle. */
  placedKwc: number;
}

/** Profil d'une date précise (« 15 mars type »), inter-années. */
export interface SpecificDateProfile {
  month: number;
  day: number;
  /** 24 valeurs de puissance moyenne (kW par kWc), heure 0–23. */
  hourlyKw: HourlyProfile;
  /** Total journalier de cette date (kWh/kWc). */
  dailyKwh: number;
  /** Nombre d'années PVGIS moyennées pour cette date. */
  yearsAveraged: number;
}

const EMPTY_24 = (): HourlyProfile => new Array<number>(24).fill(0);

function sum(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0);
}

/**
 * Jour-type d'un mois à partir de la série horaire : moyenne de la PUISSANCE (W)
 * heure-par-heure sur tous les jours de ce mois et toutes les années. Renvoyé en
 * kW (÷1000). Heures absentes → 0.
 */
export function typicalDayFromSeries(series: SeriesHourlyPoint[], month: number): HourlyProfile {
  const sumByHour = EMPTY_24();
  const cntByHour = new Array<number>(24).fill(0);
  for (const p of series) {
    if (p.month !== month) continue;
    if (p.hour < 0 || p.hour > 23) continue;
    sumByHour[p.hour] += p.powerW;
    cntByHour[p.hour] += 1;
  }
  return sumByHour.map((s, h) => (cntByHour[h] > 0 ? s / cntByHour[h] / 1000 : 0));
}

/**
 * Profil d'une DATE précise (mois/jour), moyenné sur toutes les années
 * disponibles — « 15 mars type », jamais une seule année arbitraire. Renvoie la
 * puissance moyenne (kW) par heure + le total journalier (kWh) + le nombre
 * d'années moyennées.
 */
export function specificDateFromSeries(
  series: SeriesHourlyPoint[],
  month: number,
  day: number,
): SpecificDateProfile {
  const sumByHour = EMPTY_24();
  const years = new Set<number>();
  for (const p of series) {
    if (p.month !== month || p.day !== day) continue;
    if (p.hour < 0 || p.hour > 23) continue;
    sumByHour[p.hour] += p.powerW;
    years.add(p.year);
  }
  const n = years.size;
  const hourlyKw = sumByHour.map((s) => (n > 0 ? s / n / 1000 : 0));
  // Le pas horaire est de 1 h → l'énergie (kWh) = somme des puissances (kW).
  return { month, day, hourlyKw, dailyKwh: sum(hourlyKw), yearsAveraged: n };
}

/**
 * Construit la production PAR 1 kWc à partir des données PVGIS récupérées.
 * PVcalc (pvcalc) est l'ANCRE annuelle/mensuelle ; la série horaire (series) ou,
 * à défaut, les profils DRcalc (drProfiles) donnent la FORME des jours types,
 * recalée pour rester cohérente avec PVcalc.
 *
 * Priorité de source :
 *  1. pvcalc + series → 'pvgis' (jours types réels, recalés sur E_m) ;
 *  2. pvcalc + drProfiles → 'pvgis' (forme DRcalc d'irradiance, recalée) ;
 *  3. pvcalc seul → 'pvgis-monthly' (jours types reconstruits par une cloche) ;
 *  4. rien d'utilisable → null (l'appelant bascule sur le repli interne).
 */
export function buildPerKwc(
  pvcalc: PvcalcMonthly | null,
  series: SeriesHourlyPoint[] | null,
  drProfiles: DrcalcDailyPoint[] | null,
): PerKwcProduction | null {
  if (!pvcalc || !Array.isArray(pvcalc.monthlyKwh) || pvcalc.monthlyKwh.length !== 12) return null;

  const monthlyKwh = pvcalc.monthlyKwh.slice();
  const annualKwh = pvcalc.annualKwh;

  // Forme horaire de chaque mois (puissance kW/kWc), normalisée puis recalée.
  let typicalDayByMonth: HourlyProfile[];
  let source: PerKwcProduction['source'] = 'pvgis';

  if (series && series.length) {
    typicalDayByMonth = Array.from({ length: 12 }, (_, i) => typicalDayFromSeries(series, i + 1));
  } else if (drProfiles && drProfiles.length) {
    typicalDayByMonth = shapeFromDailyProfiles(drProfiles);
  } else {
    // Pas de forme horaire PVGIS : on synthétise une cloche solaire plausible
    // par mois (source dégradée 'pvgis-monthly', totaux toujours ancrés PVcalc).
    typicalDayByMonth = Array.from({ length: 12 }, () => bellCurveShape());
    source = 'pvgis-monthly';
  }

  // RECALAGE sur PVcalc : pour chaque mois, le jour-type intégré × jours du mois
  // doit égaler E_m. On échelonne la silhouette en conséquence (énergie kWh =
  // somme des puissances kW, pas horaire 1 h).
  const dailyKwhByMonth = new Array<number>(12).fill(0);
  for (let m = 0; m < 12; m++) {
    const days = DAYS_IN_MONTH[m];
    const targetDaily = days > 0 ? monthlyKwh[m] / days : 0;
    const rawDaily = sum(typicalDayByMonth[m]);
    if (rawDaily > 0 && targetDaily > 0) {
      const k = targetDaily / rawDaily;
      typicalDayByMonth[m] = typicalDayByMonth[m].map((v) => v * k);
    } else {
      // Mois sans forme exploitable : jour-type plat nul, total mensuel préservé.
      typicalDayByMonth[m] = EMPTY_24();
    }
    dailyKwhByMonth[m] = sum(typicalDayByMonth[m]);
  }

  return { source, annualKwh, monthlyKwh, typicalDayByMonth, dailyKwhByMonth };
}

/**
 * Met à l'échelle une production PAR 1 kWc par le kWc réellement posé.
 * Linéaire : toutes les énergies × placedKwc. placedKwc ≤ 0 → tout à zéro.
 */
export function scaleByKwc(perKwc: PerKwcProduction, placedKwc: number): ScaledProduction {
  const k = Number.isFinite(placedKwc) && placedKwc > 0 ? placedKwc : 0;
  return {
    source: perKwc.source,
    placedKwc: k,
    annualKwh: perKwc.annualKwh * k,
    monthlyKwh: perKwc.monthlyKwh.map((v) => v * k),
    typicalDayByMonth: perKwc.typicalDayByMonth.map((prof) => prof.map((v) => v * k)),
    dailyKwhByMonth: perKwc.dailyKwhByMonth.map((v) => v * k),
  };
}

/** Met à l'échelle un profil de date précise par le kWc posé. */
export function scaleDateProfile(profile: SpecificDateProfile, placedKwc: number): SpecificDateProfile {
  const k = Number.isFinite(placedKwc) && placedKwc > 0 ? placedKwc : 0;
  return {
    month: profile.month,
    day: profile.day,
    hourlyKw: profile.hourlyKw.map((v) => v * k),
    dailyKwh: profile.dailyKwh * k,
    yearsAveraged: profile.yearsAveraged,
  };
}

/**
 * Cloche solaire normalisée par défaut (24 valeurs) — silhouette de jour clair
 * plausible, centrée à midi (≈ 06 h–18 h). Sert UNIQUEMENT de forme quand aucune
 * donnée horaire PVGIS n'est disponible ; les totaux restent ancrés sur PVcalc
 * après recalage. Somme normalisée à 1.
 */
export function bellCurveShape(): HourlyProfile {
  const out = EMPTY_24();
  const noon = 12.5; // léger décalage après-midi typique
  const halfWidth = 5.5; // demi-largeur du jour solaire
  let total = 0;
  for (let h = 0; h < 24; h++) {
    const x = (h - noon) / halfWidth;
    const v = Math.exp(-0.5 * x * x); // gaussienne
    const clamped = h >= 5 && h <= 20 ? v : 0; // nuit = 0
    out[h] = clamped;
    total += clamped;
  }
  return total > 0 ? out.map((v) => v / total) : out;
}

/**
 * Construit 12 silhouettes horaires (puissance relative) à partir des profils
 * journaliers DRcalc d'irradiance G(i) : pour chaque mois on échantillonne sur
 * 24 heures entières (la puissance PV suit l'irradiance, à un rendement près qui
 * disparaît au recalage sur E_m). Heures absentes → 0.
 */
export function shapeFromDailyProfiles(profiles: DrcalcDailyPoint[]): HourlyProfile[] {
  const byMonth: HourlyProfile[] = Array.from({ length: 12 }, () => EMPTY_24());
  const cntByMonth: number[][] = Array.from({ length: 12 }, () => new Array<number>(24).fill(0));
  for (const p of profiles) {
    if (p.month < 1 || p.month > 12) continue;
    const h = Math.round(p.hour);
    if (h < 0 || h > 23) continue;
    byMonth[p.month - 1][h] += p.gi;
    cntByMonth[p.month - 1][h] += 1;
  }
  return byMonth.map((prof, mi) => prof.map((s, h) => (cntByMonth[mi][h] > 0 ? s / cntByMonth[mi][h] : 0)));
}

/**
 * Repli INTERNE « estimé » (clairement étiqueté) quand PVGIS est injoignable :
 * un rendement spécifique conservateur pour le Maroc (kWh/kWc/an) réparti sur
 * une saisonnalité plausible, avec des jours types en cloche. JAMAIS présenté
 * comme une mesure PVGIS — source:'estimate'.
 *
 * @param specificYieldKwhPerKwc rendement annuel par kWc (défaut 1600, prudent).
 */
export function fallbackPerKwc(specificYieldKwhPerKwc = 1600): PerKwcProduction {
  const annualKwh = specificYieldKwhPerKwc;
  // Saisonnalité Maroc plausible (poids relatifs, normalisés ensuite).
  const seasonWeights = [0.72, 0.8, 0.95, 1.05, 1.15, 1.2, 1.22, 1.18, 1.05, 0.92, 0.78, 0.68];
  const wTotal = sum(seasonWeights);
  const monthlyKwh = seasonWeights.map((w, m) => (annualKwh * w * DAYS_IN_MONTH[m]) / (wTotal * 30.4375));
  // Re-normalise pour que la somme mensuelle = annuel exactement.
  const got = sum(monthlyKwh);
  const corr = got > 0 ? annualKwh / got : 1;
  const monthly = monthlyKwh.map((v) => v * corr);

  const shape = bellCurveShape();
  const typicalDayByMonth: HourlyProfile[] = [];
  const dailyKwhByMonth = new Array<number>(12).fill(0);
  for (let m = 0; m < 12; m++) {
    const targetDaily = DAYS_IN_MONTH[m] > 0 ? monthly[m] / DAYS_IN_MONTH[m] : 0;
    const prof = shape.map((v) => v * targetDaily); // shape sommée à 1 → total = targetDaily
    typicalDayByMonth.push(prof);
    dailyKwhByMonth[m] = sum(prof);
  }
  return { source: 'estimate', annualKwh, monthlyKwh: monthly, typicalDayByMonth, dailyKwhByMonth };
}

/** Clé de cache canonique pour un plan (arrondi pour regrouper les re-rendus). */
export function cacheKeyForPlane(plane: ProductionPlane): string {
  const lat = plane.lat.toFixed(3);
  const lon = plane.lon.toFixed(3);
  const tilt = Math.round(plane.tiltDeg);
  const aspect = Math.round(plane.aspect);
  return `${lat},${lon},${tilt},${aspect},${plane.mountingplace}`;
}

/**
 * Orchestration server-side (UN appel réseau PVGIS minimal + cohérent) : récupère
 * les données PVGIS PAR 1 kWc pour le plan, construit la production par kWc, et
 * bascule proprement sur le repli interne si PVGIS est injoignable.
 *
 * Combinaison minimale : PVcalc (annuel + 12 mensuels en 1 appel) + seriescalc
 * (forme horaire multi-années en 1 appel). DRcalc n'est sollicité QUE si
 * seriescalc échoue (repli de forme). PVGIS est interrogé à 1 kWc ; la mise à
 * l'échelle par le système posé se fait après (scaleByKwc).
 *
 * @param startYear/endYear fenêtre seriescalc (multi-années → vraies moyennes).
 */
export async function fetchPerKwcProduction(
  plane: ProductionPlane,
  startYear: number,
  endYear: number,
  fetchFn: typeof fetch = fetch,
): Promise<{ perKwc: PerKwcProduction; series: SeriesHourlyPoint[] | null }> {
  const { lat, lon, tiltDeg, aspect, mountingplace } = plane;

  // Les deux appels riches en parallèle (PVcalc rapide + seriescalc lourd).
  const [pvcalc, series] = await Promise.all([
    fetchPvgisMonthlySeries(lat, lon, 1, aspect, tiltDeg, fetchFn, mountingplace),
    fetchPvgisHourlySeries(lat, lon, 1, aspect, tiltDeg, startYear, endYear, fetchFn, mountingplace),
  ]);

  // DRcalc seulement si la série horaire a échoué mais PVcalc est là (forme).
  let drProfiles: DrcalcDailyPoint[] | null = null;
  if (pvcalc && !series) {
    drProfiles = await fetchPvgisDailyProfiles(lat, lon, aspect, tiltDeg, fetchFn);
  }

  const built = buildPerKwc(pvcalc, series, drProfiles);
  if (built) return { perKwc: built, series };

  // PVGIS injoignable → repli interne clairement étiqueté.
  return { perKwc: fallbackPerKwc(), series: null };
}

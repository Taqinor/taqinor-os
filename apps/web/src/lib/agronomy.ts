/**
 * WJ124 — Moteur agronomique v2 (FAO-56 réel, série MENSUELLE).
 * MIROIR STRICT de SOURCE: backend/django_core/apps/ventes/quote_engine/agricole/
 * agronomy.py (section QX48), lui-même miroir de
 * frontend/src/features/ventes/agronomy.js. Tout changement ici DOIT être
 * répliqué là-bas (test de parité). CHAQUE constante porte sa source ;
 * « EST. » = estimé (à vérifier fondateur). Mois indexé 0 = janvier … 11 = déc.
 *
 * Le Python porte un helper `_jsround` qui réplique EXACTEMENT le
 * Math.round(x·10^d)/10^d du JS (arrondi half-up) — ici, en JS, `jsround`
 * s'appuie donc directement sur Math.round via Math.floor(x·f + 0.5). Objectif :
 * parité numérique byte-identique avec le backend. Module PUR : aucun DOM.
 */

/** Réplique EXACTEMENT le Math.round(x·10^d)/10^d (half-up) — parité front/back. */
export function jsround(x: number, digits = 0): number {
  const f = 10 ** digits;
  return Math.floor(x * f + 0.5) / f;
}

/** Kc mid-season défaut (culture inconnue). */
export const KC_MID_DEFAUT = 0.85;

export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] as const;

// ET0 de référence MENSUEL (mm/jour) par région — Penman-Monteith, stations FAO
// CLIMWAT représentatives. Valeurs ESTIMÉES (station proxy), à vérifier fondateur.
export const ET0_MONTHLY: Record<string, number[]> = {
  'souss-massa': [2.4, 3.0, 4.0, 4.7, 5.4, 5.9, 6.2, 6.0, 5.0, 4.0, 3.0, 2.3], // Agadir — EST.
  doukkala: [2.2, 2.8, 3.8, 4.5, 5.2, 5.8, 6.3, 6.1, 5.0, 3.9, 2.8, 2.1], // El Jadida — EST.
  tadla: [2.0, 2.9, 4.2, 5.4, 6.6, 7.6, 8.2, 7.7, 5.9, 4.2, 2.8, 2.0], // Béni Mellal — EST.
  saiss: [1.8, 2.5, 3.7, 4.8, 6.0, 7.0, 7.6, 7.1, 5.3, 3.7, 2.4, 1.7], // Fès-Meknès — EST.
  oriental: [2.0, 2.7, 3.9, 5.0, 6.2, 7.1, 7.7, 7.2, 5.5, 3.9, 2.6, 1.9], // Berkane/Oujda — EST.
  'draa-tafilalet': [2.2, 3.1, 4.5, 5.8, 7.0, 8.0, 8.5, 7.9, 6.2, 4.4, 2.9, 2.1], // Errachidia — EST.
  'gharb-loukkos': [2.0, 2.6, 3.6, 4.4, 5.3, 6.0, 6.5, 6.2, 5.0, 3.7, 2.6, 1.9], // Kénitra/Larache — EST.
  haouz: [2.3, 3.1, 4.4, 5.6, 6.8, 7.8, 8.4, 7.8, 6.0, 4.3, 2.9, 2.2], // Marrakech — EST.
};
export const ET0_MONTHLY_DEFAUT = [2.1, 2.8, 4.0, 5.0, 6.1, 7.0, 7.6, 7.1, 5.5, 4.0, 2.7, 2.0]; // médiane MA — EST.

// Pluie EFFICACE mensuelle (mm/mois) par région — USDA-SCS simplifiée sur les
// normales pluviométriques MA. Créditée au besoin net. Valeurs ESTIMÉES.
export const RAIN_EFF_MONTHLY: Record<string, number[]> = {
  'gharb-loukkos': [60, 55, 50, 40, 20, 5, 0, 0, 10, 40, 60, 65], // ~405 mm/an eff — EST.
  saiss: [45, 42, 45, 40, 22, 6, 1, 1, 10, 30, 48, 50], // EST.
  oriental: [30, 28, 30, 30, 20, 6, 1, 2, 10, 28, 32, 30], // EST.
  doukkala: [35, 30, 28, 18, 8, 1, 0, 0, 5, 20, 35, 40], // EST.
  tadla: [30, 30, 30, 25, 12, 3, 0, 0, 5, 22, 33, 35], // EST.
  haouz: [25, 25, 28, 25, 12, 3, 0, 1, 6, 22, 28, 26], // EST.
  'souss-massa': [25, 20, 20, 12, 5, 0, 0, 0, 3, 12, 22, 28], // EST.
  'draa-tafilalet': [8, 8, 10, 8, 5, 2, 1, 3, 6, 8, 8, 7], // EST.
};
export const RAIN_EFF_DEFAUT = [20, 18, 20, 16, 8, 2, 0, 0, 5, 15, 22, 22]; // EST.

// Rendement d'irrigation par technique (FAO).
export const IRRIGATION_EFFICIENCY: Record<string, number> = { goutte: 0.9, aspersion: 0.75, gravitaire: 0.55 };
export const IRRIGATION_EFFICIENCY_DEFAUT = 0.75;

export interface CropStage {
  evergreen?: boolean;
  start?: number;
  stages?: [number, number, number, number];
  kc_ini?: number;
  kc_mid: number;
  kc_end?: number;
  kc_estimated?: boolean;
}

// Stades culturaux FAO-56 (Table 11 durées / Table 12 Kc), calendrier MA.
// evergreen=true → Kc ~constant. Sinon start (mois 1-12), stages en MOIS
// [ini, dev, mid, late], Kc ini/mid/end. kc_estimated=true = hors FAO / estimé.
export const CROP_STAGES: Record<string, CropStage> = {
  agrumes: { evergreen: true, kc_mid: 0.65 }, // FAO-56 T12 citrus (no ground cover)
  olivier: { evergreen: true, kc_mid: 0.65 }, // FAO-56 T12 olive
  dattier: { evergreen: true, kc_mid: 0.95 }, // FAO-56 T12 date palm ; MA 51 m³/arbre/an
  avocatier: { evergreen: true, kc_mid: 0.85 }, // FAO-56 T12 avocado ; MA Gharb 8-12 000 m³/ha/an
  arganier: { evergreen: true, kc_mid: 0.55, kc_estimated: true }, // EST.
  'banane-serre': { evergreen: true, kc_mid: 1.1 }, // FAO-56 T12 banana
  luzerne: { evergreen: true, kc_mid: 0.95, kc_estimated: true }, // EST. (moyenne inter-coupes)
  myrtille: { evergreen: true, kc_mid: 1.05, kc_estimated: true }, // EST. ; MA pics ~80 m³/ha/j
  amandier: { start: 3, stages: [1, 1, 5, 2], kc_ini: 0.4, kc_mid: 0.9, kc_end: 0.65 }, // FAO-56 T12 almond
  vigne: { start: 4, stages: [1, 1, 3, 2], kc_ini: 0.3, kc_mid: 0.7, kc_end: 0.45 }, // FAO-56 T12 grape (table)
  grenadier: { start: 3, stages: [1, 2, 4, 2], kc_ini: 0.35, kc_mid: 0.85, kc_end: 0.55, kc_estimated: true }, // EST.
  figuier: { start: 3, stages: [1, 2, 4, 2], kc_ini: 0.35, kc_mid: 0.7, kc_end: 0.5, kc_estimated: true }, // EST.
  'tomate-serre': { start: 9, stages: [1, 2, 3, 1], kc_ini: 0.6, kc_mid: 1.1, kc_end: 0.8 }, // FAO-56 T12 tomato
  'poivron-serre': { start: 9, stages: [1, 2, 3, 1], kc_ini: 0.6, kc_mid: 1.05, kc_end: 0.9 }, // FAO-56 T12 bell pepper
  'pomme-de-terre': { start: 1, stages: [1, 1, 2, 1], kc_ini: 0.5, kc_mid: 1.15, kc_end: 0.75 }, // FAO-56 T12 potato
  oignon: { start: 10, stages: [1, 2, 3, 1], kc_ini: 0.7, kc_mid: 1.05, kc_end: 0.75 }, // FAO-56 T12 onion (dry)
  'melon-pasteque': { start: 3, stages: [1, 1, 2, 1], kc_ini: 0.5, kc_mid: 1.0, kc_end: 0.75 }, // FAO-56 T12 melon/watermelon
  cereales: { start: 11, stages: [1, 2, 2, 1], kc_ini: 0.4, kc_mid: 1.15, kc_end: 0.4 }, // FAO-56 T12 wheat
  fraise: { start: 10, stages: [1, 2, 3, 1], kc_ini: 0.4, kc_mid: 1.0, kc_end: 0.75, kc_estimated: true }, // EST.
  cannabis: { start: 5, stages: [1, 1, 2, 1], kc_ini: 0.4, kc_mid: 1.0, kc_end: 0.6, kc_estimated: true }, // EST. (cannabis licite, flag ANRAC)
};

function num(v: unknown): number {
  const f = Number(v);
  return Number.isFinite(f) ? f : 0;
}

/**
 * Kc mensuel (0=janv…11=déc) depuis les stades FAO-56. Miroir de crop_kc_monthly()
 * / cropKcMonthly(). Culture inconnue → KC_MID_DEFAUT plat ; évergreen → constant.
 */
export function cropKcMonthly(cropKey?: string | null): number[] {
  const kc = new Array<number>(12).fill(0);
  const spec = cropKey != null ? CROP_STAGES[cropKey] : undefined;
  if (!spec) return new Array<number>(12).fill(KC_MID_DEFAUT);
  if (spec.evergreen) return new Array<number>(12).fill(spec.kc_mid);
  const start = spec.start ?? 1;
  const stages = spec.stages ?? [1, 1, 1, 1];
  const kcIni = spec.kc_ini ?? 0.4;
  const kcMid = spec.kc_mid ?? 1.0;
  const kcEnd = spec.kc_end ?? 0.6;
  const [ini, dev, mid, late] = stages;
  let m = (start - 1) % 12;
  const put = (v: number) => {
    kc[m] = jsround(v, 3);
    m = (m + 1) % 12;
  };
  for (let i = 0; i < ini; i++) put(kcIni);
  for (let i = 0; i < dev; i++) put(kcIni + (kcMid - kcIni) * ((i + 1) / (dev + 1)));
  for (let i = 0; i < mid; i++) put(kcMid);
  for (let i = 0; i < late; i++) put(kcMid + (kcEnd - kcMid) * ((i + 1) / (late + 1)));
  return kc;
}

export interface MonthlyWaterDemand {
  kc: number[];
  etc_mm_day: number[];
  crop_need_mm_month: number[];
  net_mm_month: number[];
  gross_m3_ha_month: number[];
  gross_m3_farm_day: number[];
  annual_net_m3_ha: number;
  annual_gross_m3_ha: number;
  annual_gross_m3_farm: number;
  peak_m3_ha_day: number;
  peak_m3_farm_day: number;
  kc_estimated: boolean;
  inputs: { crop?: string | null; region?: string | null; surface_ha: number; method?: string | null; efficiency: number };
}

/**
 * Besoin en eau MENSUEL d'une culture (le graphe QX47). Miroir STRICT de
 * monthly_water_demand() / monthlyWaterDemand(). Défensif : jamais d'exception.
 */
export function monthlyWaterDemand(
  crop?: string | null,
  region?: string | null,
  surfaceHa?: number | null,
  method?: string | null,
): MonthlyWaterDemand {
  const surface = num(surfaceHa);
  const et0 = (region != null && ET0_MONTHLY[region]) || ET0_MONTHLY_DEFAUT;
  const rain = (region != null && RAIN_EFF_MONTHLY[region]) || RAIN_EFF_DEFAUT;
  const eff = (method != null && IRRIGATION_EFFICIENCY[method]) || IRRIGATION_EFFICIENCY_DEFAUT;
  const kc = cropKcMonthly(crop);
  const etc_mm_day: number[] = [];
  const crop_need_mm_month: number[] = [];
  const net_mm_month: number[] = [];
  const gross_m3_ha_month: number[] = [];
  const gross_m3_farm_day: number[] = [];
  for (let m = 0; m < 12; m++) {
    const etc = et0[m] * kc[m];
    const grossMm = etc * DAYS_IN_MONTH[m];
    const netMm = Math.max(0, grossMm - rain[m]);
    const grossHa = eff > 0 ? (netMm * 10) / eff : 0;
    etc_mm_day.push(jsround(etc, 3));
    crop_need_mm_month.push(jsround(grossMm, 1));
    net_mm_month.push(jsround(netMm, 1));
    gross_m3_ha_month.push(jsround(grossHa, 1));
    gross_m3_farm_day.push(surface > 0 ? jsround((grossHa * surface) / DAYS_IN_MONTH[m], 1) : 0);
  }
  const annual_net_m3_ha = jsround(net_mm_month.reduce((a, b) => a + b, 0) * 10);
  const annual_gross_m3_ha = jsround(gross_m3_ha_month.reduce((a, b) => a + b, 0));
  const annual_gross_m3_farm = surface > 0 ? jsround(annual_gross_m3_ha * surface) : 0;
  const peak_m3_ha_day = jsround(Math.max(...gross_m3_ha_month.map((v, m) => v / DAYS_IN_MONTH[m])), 1);
  const peak_m3_farm_day = jsround(Math.max(0, ...gross_m3_farm_day), 1);
  return {
    kc,
    etc_mm_day,
    crop_need_mm_month,
    net_mm_month,
    gross_m3_ha_month,
    gross_m3_farm_day,
    annual_net_m3_ha,
    annual_gross_m3_ha,
    annual_gross_m3_farm,
    peak_m3_ha_day,
    peak_m3_farm_day,
    kc_estimated: Boolean(crop != null && CROP_STAGES[crop]?.kc_estimated),
    inputs: { crop, region, surface_ha: surface, method, efficiency: eff },
  };
}

/**
 * Annualisation par INTÉGRALE de la série mensuelle. Miroir de
 * annual_water_from_monthly() — remplace le forfait plat sur le chemin agricole v2.
 */
export function annualWaterFromMonthly(monthly: MonthlyWaterDemand | null | undefined): number {
  if (!monthly || !Array.isArray(monthly.gross_m3_farm_day)) return 0;
  const total = monthly.gross_m3_farm_day.reduce((sum, v, m) => sum + num(v) * DAYS_IN_MONTH[m], 0);
  return jsround(total);
}

/** Liste ordonnée des cultures (clés CROP_STAGES) pour les cartes de sélection. */
export const CROP_KEYS = Object.keys(CROP_STAGES);
/** Liste ordonnée des régions agronomiques (clés ET0_MONTHLY). */
export const REGION_KEYS = Object.keys(ET0_MONTHLY);

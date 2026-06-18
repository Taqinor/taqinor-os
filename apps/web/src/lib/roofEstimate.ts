/**
 * Production solaire annuelle via PVGIS (API PVcalc de la Commission
 * européenne, JRC — gratuite, sans clé, couvre le Maroc). Appelée UNIQUEMENT
 * côté serveur (la route /api/roof-estimate) : le navigateur ne touche jamais
 * PVGIS. Paramétrée par fetchFn → testable hors réseau.
 *
 * Robustesse avant tout : toute panne (timeout, statut, JSON malformé,
 * coordonnées absurdes) renvoie `null` en silence. L'appelant bascule alors
 * sur le repli local (fallbackAnnualKwh) — le visiteur n'a jamais d'erreur.
 */

const PVGIS_ENDPOINT = 'https://re.jrc.ec.europa.eu/api/v5_2/PVcalc';
const DEFAULT_TILT_DEG = 15; // inclinaison « sensée » (pose Maroc, conservatrice)
const SYSTEM_LOSS_PCT = 14; // pertes système PVGIS par défaut
const TIMEOUT_MS = 6000;

/**
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 * @returns production annuelle (kWh) ou null si indisponible.
 */
export async function fetchPvgisAnnualKwh(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  fetchFn: typeof fetch = fetch,
): Promise<number | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(DEFAULT_TILT_DEG),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    mountingplace: 'building',
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${PVGIS_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { outputs?: { totals?: { fixed?: { E_y?: unknown } } } };
    const eY = data?.outputs?.totals?.fixed?.E_y;
    if (typeof eY !== 'number' || !Number.isFinite(eY) || eY <= 0) return null;
    return eY;
  } catch {
    return null;
  }
}

/**
 * Variante PARAMÉTRÉE PAR L'INCLINAISON pour l'estimateur « cerveau »
 * (/preview/toiture-3d-pro-3) : même API PVGIS, même robustesse (null en silence),
 * mais l'angle est fourni (la table committée reste le repli instantané). N'altère
 * PAS fetchPvgisAnnualKwh (route /api/roof-estimate inchangée).
 *
 * @param tilt inclinaison en degrés.
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 */
export async function fetchPvgisAnnualKwhAtTilt(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  tilt: number,
  fetchFn: typeof fetch = fetch,
  mountingplace: 'building' | 'free' = 'building',
): Promise<number | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  if (!Number.isFinite(tilt) || tilt < 0 || tilt > 90) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(tilt),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    // 'building' (pose intégrée, moins ventilée) par défaut — inchangé pour
    // pro-3/4/5/6 ; 'free' (panneaux sur racks aérés) pour le toit PLAT de pro-7,
    // PVGIS comme source de vérité (W20).
    mountingplace,
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${PVGIS_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { outputs?: { totals?: { fixed?: { E_y?: unknown } } } };
    const eY = data?.outputs?.totals?.fixed?.E_y;
    if (typeof eY !== 'number' || !Number.isFinite(eY) || eY <= 0) return null;
    return eY;
  } catch {
    return null;
  }
}

// — Endpoints additionnels (W49) —————————————————————————————————————————
// AJOUTS PURS pour le moteur de production server-side (productionEngine.ts).
// Même base v5_2, même base de rayonnement/version PVGIS, mêmes pertes 14 % et
// même technologie 'crystSi' que ci-dessus → AUCUN décalage des nombres existants.
// fetchPvgisAnnualKwh(...) et fetchPvgisAnnualKwhAtTilt(...) restent inchangés.

const PVGIS_BASE = 'https://re.jrc.ec.europa.eu/api/v5_2';
const PVCALC_ENDPOINT = `${PVGIS_BASE}/PVcalc`;
const SERIESCALC_ENDPOINT = `${PVGIS_BASE}/seriescalc`;
const DRCALC_ENDPOINT = `${PVGIS_BASE}/DRcalc`;
// seriescalc/DRcalc renvoient bien plus de données → délai un peu plus large.
const SERIES_TIMEOUT_MS = 12000;

/** Une « jambe » résultat PVcalc : annuel + 12 totaux mensuels (kWh). */
export interface PvcalcMonthly {
  /** Production annuelle E_y (kWh). */
  annualKwh: number;
  /** 12 totaux mensuels E_m (kWh), index 0 = janvier … 11 = décembre. */
  monthlyKwh: number[];
}

/** Un point d'un profil journalier moyen DRcalc (irradiance sur le plan). */
export interface DrcalcDailyPoint {
  /** Mois 1–12. */
  month: number;
  /** Heure décimale du point (ex. 9.5 pour 09:30). */
  hour: number;
  /** Irradiance globale G(i) sur le plan (W/m²). */
  gi: number;
}

/** Un point horaire seriescalc (puissance PV). */
export interface SeriesHourlyPoint {
  /** Année (UTC) du point. */
  year: number;
  /** Mois 1–12. */
  month: number;
  /** Jour du mois 1–31. */
  day: number;
  /** Heure 0–23 (du champ HH du timestamp PVGIS). */
  hour: number;
  /** Puissance PV instantanée P (W) pour le système interrogé. */
  powerW: number;
}

/**
 * PVcalc PARAMÉTRÉ — renvoie l'annuel ET les 12 totaux mensuels en UN appel.
 * C'est l'ancre « moyennes long terme » de PVGIS (réconciliation, voir
 * productionEngine.ts). Robustesse identique : null en silence sur toute panne.
 *
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 * @param tilt inclinaison en degrés.
 */
export async function fetchPvgisMonthlySeries(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  tilt: number,
  fetchFn: typeof fetch = fetch,
  mountingplace: 'building' | 'free' = 'building',
): Promise<PvcalcMonthly | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  if (!Number.isFinite(tilt) || tilt < 0 || tilt > 90) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(tilt),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    mountingplace,
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${PVCALC_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      outputs?: {
        totals?: { fixed?: { E_y?: unknown } };
        monthly?: { fixed?: Array<{ month?: unknown; E_m?: unknown }> };
      };
    };
    const eY = data?.outputs?.totals?.fixed?.E_y;
    const rows = data?.outputs?.monthly?.fixed;
    if (typeof eY !== 'number' || !Number.isFinite(eY) || eY <= 0) return null;
    if (!Array.isArray(rows) || rows.length !== 12) return null;
    const monthlyKwh = new Array<number>(12).fill(0);
    for (const r of rows) {
      const m = r?.month;
      const em = r?.E_m;
      if (typeof m !== 'number' || m < 1 || m > 12) return null;
      if (typeof em !== 'number' || !Number.isFinite(em) || em < 0) return null;
      monthlyKwh[m - 1] = em;
    }
    return { annualKwh: eY, monthlyKwh };
  } catch {
    return null;
  }
}

/**
 * DRcalc (month=0) — profil JOURNALIER MOYEN d'irradiance pour les 12 mois en UN
 * appel. Sert de repli de FORME quand seriescalc n'est pas disponible : on a la
 * silhouette horaire (G(i)) de chaque mois, qu'on normalise puis qu'on cale sur
 * les totaux PVcalc. Robustesse : null en silence.
 *
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 * @param tilt inclinaison en degrés.
 */
export async function fetchPvgisDailyProfiles(
  lat: number,
  lon: number,
  aspect: number,
  tilt: number,
  fetchFn: typeof fetch = fetch,
): Promise<DrcalcDailyPoint[] | null> {
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  if (!Number.isFinite(tilt) || tilt < 0 || tilt > 90) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    month: '0', // 0 = les 12 mois en un seul appel
    angle: String(tilt),
    aspect: String(aspect),
    global: '1', // demande G(i) sur le plan
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${DRCALC_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(SERIES_TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      outputs?: { daily_profile?: Array<Record<string, unknown>> };
    };
    const rows = data?.outputs?.daily_profile;
    if (!Array.isArray(rows) || rows.length === 0) return null;
    const out: DrcalcDailyPoint[] = [];
    for (const r of rows) {
      const month = typeof r.month === 'number' ? r.month : NaN;
      const hour = parseClockHour(r.time);
      const gi = typeof r['G(i)'] === 'number' ? (r['G(i)'] as number) : NaN;
      if (!Number.isFinite(month) || month < 1 || month > 12) continue;
      if (!Number.isFinite(hour)) continue;
      if (!Number.isFinite(gi)) continue;
      out.push({ month, hour, gi: Math.max(0, gi) });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}

/**
 * seriescalc (pvcalculation=1) — série HORAIRE PV multi-années (puissance P en
 * W) sur [startYear, endYear]. SOURCE RICHE du moteur : jour type par mois,
 * date précise inter-années, totaux journaliers/mensuels/annuel en dérivent.
 * Robustesse : null en silence.
 *
 * @param aspect azimut PVGIS (0=Sud, -90=Est, 90=Ouest, 180=Nord).
 * @param tilt inclinaison en degrés.
 */
export async function fetchPvgisHourlySeries(
  lat: number,
  lon: number,
  kwc: number,
  aspect: number,
  tilt: number,
  startYear: number,
  endYear: number,
  fetchFn: typeof fetch = fetch,
  mountingplace: 'building' | 'free' = 'building',
): Promise<SeriesHourlyPoint[] | null> {
  if (!Number.isFinite(kwc) || kwc <= 0) return null;
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return null;
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return null;
  if (!Number.isFinite(tilt) || tilt < 0 || tilt > 90) return null;
  if (!Number.isFinite(startYear) || !Number.isFinite(endYear) || endYear < startYear) return null;

  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    startyear: String(startYear),
    endyear: String(endYear),
    pvcalculation: '1',
    peakpower: String(kwc),
    loss: String(SYSTEM_LOSS_PCT),
    angle: String(tilt),
    aspect: String(aspect),
    pvtechchoice: 'crystSi',
    mountingplace,
    outputformat: 'json',
  });

  try {
    const res = await fetchFn(`${SERIESCALC_ENDPOINT}?${params.toString()}`, {
      signal: AbortSignal.timeout(SERIES_TIMEOUT_MS),
      headers: { accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      outputs?: { hourly?: Array<{ time?: unknown; P?: unknown }> };
    };
    const rows = data?.outputs?.hourly;
    if (!Array.isArray(rows) || rows.length === 0) return null;
    const out: SeriesHourlyPoint[] = [];
    for (const r of rows) {
      const parsed = parseSeriesTimestamp(r.time);
      const p = typeof r.P === 'number' ? r.P : NaN;
      if (!parsed || !Number.isFinite(p)) continue;
      out.push({ ...parsed, powerW: Math.max(0, p) });
    }
    return out.length ? out : null;
  } catch {
    return null;
  }
}

/** Parse "YYYYMMDD:HHMM" → {year, month, day, hour}. Heure = champ HH. */
export function parseSeriesTimestamp(
  raw: unknown,
): { year: number; month: number; day: number; hour: number } | null {
  if (typeof raw !== 'string') return null;
  const m = /^(\d{4})(\d{2})(\d{2}):(\d{2})(\d{2})$/.exec(raw.trim());
  if (!m) return null;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  const hour = Number(m[4]);
  if (month < 1 || month > 12 || day < 1 || day > 31 || hour < 0 || hour > 23) return null;
  return { year, month, day, hour };
}

/** Parse "HH:MM" (DRcalc) → heure décimale (ex. 9.5). Tolère un nombre déjà parsé. */
export function parseClockHour(raw: unknown): number {
  if (typeof raw === 'number') return raw;
  if (typeof raw !== 'string') return NaN;
  const m = /^(\d{1,2}):(\d{2})$/.exec(raw.trim());
  if (!m) return NaN;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h < 0 || h > 23 || min < 0 || min > 59) return NaN;
  return h + min / 60;
}

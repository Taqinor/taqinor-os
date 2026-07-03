/**
 * POST /api/roof-production — DONNÉES DE PRODUCTION server-side (W49) pour
 * l'estimateur toiture (« cerveau »). PROXY SERVEUR : le navigateur n'appelle
 * JAMAIS PVGIS (CORS bloqué). On reçoit le plan courant (GPS + inclinaison +
 * azimut + type de pose) et le nombre de panneaux posés, et on renvoie la
 * production complète, MISE À L'ÉCHELLE par le système posé :
 *  - annuel (kWh/an),
 *  - 12 totaux mensuels (kWh/mois),
 *  - jour TYPE horaire par mois (24 valeurs kW, moyenne multi-années),
 *  - option : profil d'une DATE précise (« 15 mars type », inter-années),
 *  - totaux journaliers par mois (kWh/jour).
 *
 * Tout est interrogé PAR 1 kWc puis multiplié par placedPanels × 0,72 kWc
 * (Canadian Solar 720 W). PVGIS lent/injoignable → repli interne clairement
 * étiqueté source:'estimate'. CACHE par (lat,lon,tilt,azimut,pose) arrondis :
 * un re-rendu ou un ajustement identique ne refait aucun appel PVGIS (on reste
 * largement sous la limite des 30 appels/s de PVGIS).
 *
 * Ne touche AUCUNE donnée de lead. Route purement additive — /api/roof-yield et
 * /api/roof-estimate restent inchangées.
 *
 * W316 — rate-limit GÉNÉREUX et DÉDIÉ (même esprit que roof-yield/roof-estimate) :
 * le cache par plan arrondi (ci-dessous) absorbe déjà l'essentiel du répétitif ;
 * ce garde-fou écrête seulement un balayage automatisé pur.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import {
  fetchPerKwcProduction,
  scaleByKwc,
  scaleDateProfile,
  specificDateFromSeries,
  placedKwcFromPanels,
  cacheKeyForPlane,
  PANEL_KWC,
  type ProductionPlane,
  type PerKwcProduction,
  type SpecificDateProfile,
} from '../../lib/productionEngine';
import type { SeriesHourlyPoint } from '../../lib/roofEstimate';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

// Fenêtre seriescalc multi-années (SARAH2 bien couvert) → vraies moyennes
// inter-années pour le jour type et les dates précises. Surchargeable dans le
// corps (tests / réglages), bornée pour rester raisonnable.
const DEFAULT_START_YEAR = 2016;
const DEFAULT_END_YEAR = 2020;

// — Cache module (par instance Worker) ——————————————————————————————————
// On met en cache le RÉSULTAT PVGIS par 1 kWc + la série horaire, par plan
// arrondi. Les ajustements qui ne changent pas le plan arrondi (ni la date) sont
// servis instantanément. TTL généreux (les moyennes long terme PVGIS ne bougent
// pas d'un rendu à l'autre).
interface CacheEntry {
  perKwc: PerKwcProduction;
  series: SeriesHourlyPoint[] | null;
  at: number;
}
const CACHE = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 h
const CACHE_MAX = 200;

function cacheGet(key: string): CacheEntry | null {
  const e = CACHE.get(key);
  if (!e) return null;
  if (Date.now() - e.at > CACHE_TTL_MS) {
    CACHE.delete(key);
    return null;
  }
  return e;
}

function cacheSet(key: string, entry: CacheEntry): void {
  if (CACHE.size >= CACHE_MAX) {
    const oldest = CACHE.keys().next().value;
    if (oldest !== undefined) CACHE.delete(oldest);
  }
  CACHE.set(key, entry);
}

/** Vide le cache (tests uniquement). */
export function __clearProductionCache(): void {
  CACHE.clear();
}

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

// W317 — Origin/Sec-Fetch-Site : garde-fou LOCAL (jamais importé de lib/lead —
// cette route reste volontairement découplée de toute plomberie de lead/CRM).
// Voir lib/lead.ts pour la version jumelle utilisée par les endpoints
// lead/proposition.
function isSameOriginRequest(request: Request): boolean {
  const secFetchSite = request.headers.get('sec-fetch-site');
  if (secFetchSite) return secFetchSite !== 'cross-site';
  const origin = request.headers.get('origin');
  if (!origin) return true;
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false;
  }
}
function crossSiteRejection(): Response {
  return json({ ok: false, error: 'Requête refusée.' }, 403);
}

function num(v: unknown): number {
  return typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.'));
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`roof-production:${clientIpFromRequest(request)}`, { limit: 60, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false, error: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, error: 'JSON invalide' }, 400);
  }

  const lat = num(body.lat);
  const lon = num(body.lon);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return json({ ok: false, error: 'lat invalide' }, 400);
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return json({ ok: false, error: 'lon invalide' }, 400);

  const tiltDeg = num(body.tiltDeg);
  const aspect = num(body.aspect);
  if (!Number.isFinite(tiltDeg) || tiltDeg < 0 || tiltDeg > 90) return json({ ok: false, error: 'tiltDeg invalide' }, 400);
  if (!Number.isFinite(aspect) || aspect < -180 || aspect > 180) return json({ ok: false, error: 'aspect invalide' }, 400);

  // Pose : 'free' pour le toit PLAT racké, 'building' (par défaut) sinon.
  const mountingplace: 'building' | 'free' = body.mountingplace === 'free' ? 'free' : 'building';

  // Taille posée : nombre de panneaux Canadian Solar 720 W → kWc.
  const placedPanels = num(body.placedPanels);
  if (!Number.isFinite(placedPanels) || placedPanels <= 0) return json({ ok: false, error: 'placedPanels invalide' }, 400);
  const placedKwc = placedKwcFromPanels(placedPanels);

  // Fenêtre multi-années (surchargeable, bornée).
  let startYear = Math.trunc(num(body.startYear));
  let endYear = Math.trunc(num(body.endYear));
  if (!Number.isFinite(startYear) || startYear < 2005 || startYear > 2100) startYear = DEFAULT_START_YEAR;
  if (!Number.isFinite(endYear) || endYear < startYear || endYear > 2100) endYear = DEFAULT_END_YEAR;

  // Date précise optionnelle (« 15 mars type »).
  const dateMonth = num(body.dateMonth);
  const dateDay = num(body.dateDay);
  const wantsDate =
    Number.isFinite(dateMonth) && dateMonth >= 1 && dateMonth <= 12 &&
    Number.isFinite(dateDay) && dateDay >= 1 && dateDay <= 31;

  const plane: ProductionPlane = { lat, lon, tiltDeg, aspect, mountingplace };
  const key = cacheKeyForPlane(plane);

  // Cache HIT → aucun appel PVGIS.
  let cached = cacheGet(key);
  let cacheHit = !!cached;
  if (!cached) {
    const fetched = await fetchPerKwcProduction(plane, startYear, endYear, fetch);
    cached = { perKwc: fetched.perKwc, series: fetched.series, at: Date.now() };
    cacheSet(key, cached);
    cacheHit = false;
  }

  const scaled = scaleByKwc(cached.perKwc, placedKwc);

  // Date précise : seulement si on a la série horaire (sinon non disponible).
  let specificDate: SpecificDateProfile | null = null;
  if (wantsDate && cached.series && cached.series.length) {
    const perKwcDate = specificDateFromSeries(cached.series, Math.trunc(dateMonth), Math.trunc(dateDay));
    specificDate = scaleDateProfile(perKwcDate, placedKwc);
  }

  return json({
    ok: true,
    source: scaled.source,
    cacheHit,
    placedPanels: Math.trunc(placedPanels),
    panelKwc: PANEL_KWC,
    placedKwc: scaled.placedKwc,
    annualKwh: scaled.annualKwh,
    monthlyKwh: scaled.monthlyKwh,
    dailyKwhByMonth: scaled.dailyKwhByMonth,
    typicalDayByMonth: scaled.typicalDayByMonth,
    specificDate,
  });
};

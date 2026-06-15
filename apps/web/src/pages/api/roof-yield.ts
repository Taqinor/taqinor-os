/**
 * POST /api/roof-yield — production annuelle (kWh) PVGIS pour l'estimateur
 * « cerveau » (/preview/toiture-3d-pro-3), inclinaison ET azimut paramétrés.
 *
 * Proxy serveur (le navigateur n'appelle JAMAIS PVGIS). On reçoit une ou
 * plusieurs « jambes » { kwc, tiltDeg, aspect } et on SOMME leur production —
 * une jambe pour le sud, deux jambes (−90/+90) pour l'Est-Ouest. PVGIS
 * lent/injoignable → la page bascule sur sa table committée (repli instantané) :
 * ici on renvoie simplement source:'estimate' sans jambe PVGIS.
 *
 * Ne touche AUCUNE donnée de lead. Route additive : /api/roof-estimate (15°,
 * formulaire live) reste strictement inchangée.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { fetchPvgisAnnualKwhAtTilt } from '../../lib/roofEstimate';

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

function num(v: unknown): number {
  return typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.'));
}

interface Leg {
  kwc: number;
  tiltDeg: number;
  aspect: number;
}

export const POST: APIRoute = async ({ request }) => {
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

  const rawLegs = Array.isArray(body.legs) ? (body.legs as unknown[]) : [];
  const legs: Leg[] = rawLegs
    .map((l) => l as Record<string, unknown>)
    .map((l) => ({ kwc: num(l.kwc), tiltDeg: num(l.tiltDeg), aspect: num(l.aspect) }))
    .filter((l) => Number.isFinite(l.kwc) && l.kwc > 0 && Number.isFinite(l.tiltDeg) && Number.isFinite(l.aspect));

  if (!legs.length) return json({ ok: false, error: 'aucune jambe valide' }, 400);
  if (legs.length > 4) return json({ ok: false, error: 'trop de jambes' }, 400);

  let total = 0;
  for (const leg of legs) {
    const e = await fetchPvgisAnnualKwhAtTilt(lat, lon, leg.kwc, leg.aspect, leg.tiltDeg, fetch);
    if (e === null) return json({ ok: true, annualKwh: null, source: 'estimate' }); // repli table côté page
    total += e;
  }

  return json({ ok: true, annualKwh: Math.round(total), source: 'pvgis' });
};

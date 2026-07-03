/**
 * POST /api/roof-estimate — production solaire annuelle + fourchette
 * d'économies pour l'estimateur de toiture (preview privé).
 *
 * Proxy serveur vers PVGIS (le navigateur n'appelle JAMAIS PVGIS directement).
 * Entrée : { lat, lon, kwc, orientation }. PVGIS lent/injoignable → repli local
 * (fallbackAnnualKwh), jamais d'erreur côté visiteur. Cette route ne touche
 * AUCUNE donnée de lead : elle n'alimente que l'affichage indicatif de l'outil.
 * Le lead, lui, garde sa propre bande ROI (via /api/preview-lead, inchangé).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { fetchPvgisAnnualKwh } from '../../lib/roofEstimate';
import { annualSavingsBandMad, fallbackAnnualKwh, orientationToAspect } from '../../lib/roof';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

// W317 — Origin/Sec-Fetch-Site : garde-fou LOCAL (jamais importé de lib/lead —
// cette route reste volontairement découplée de toute plomberie de lead/CRM,
// garanti par un test dédié). Voir lib/lead.ts pour la version jumelle utilisée
// par les endpoints lead/proposition.
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

  // W316 — rate-limit GÉNÉREUX et DÉDIÉ (même esprit que roof-yield/roof-production) :
  // appelé à chaque ajustement live du formulaire, plusieurs appels/minute sont
  // un usage normal.
  const rl = rateLimit(`roof-estimate:${clientIpFromRequest(request)}`, { limit: 60, windowMs: 60_000 });
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
  const kwc = num(body.kwc);
  const orientation = typeof body.orientation === 'string' ? body.orientation : 'inconnu';
  // Facture annuelle estimée (MAD) : plafonne l'économie modélisée (ERR113).
  // Facultative — sans elle, le comportement reste celui d'avant.
  const annualBillMad = num(body.annualBillMad);

  if (!Number.isFinite(lat) || lat < -90 || lat > 90) return json({ ok: false, error: 'lat invalide' }, 400);
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) return json({ ok: false, error: 'lon invalide' }, 400);
  if (!Number.isFinite(kwc) || kwc <= 0) return json({ ok: false, error: 'kwc invalide' }, 400);

  const aspect = orientationToAspect(orientation);
  const pvgis = await fetchPvgisAnnualKwh(lat, lon, kwc, aspect, fetch);
  const annualKwh = pvgis ?? fallbackAnnualKwh(kwc);
  const savings = annualSavingsBandMad(
    annualKwh,
    Number.isFinite(annualBillMad) && annualBillMad > 0 ? { annualBillMad } : {},
  );

  return json({
    ok: true,
    annualKwh: Math.round(annualKwh),
    savings: { low: Math.round(savings.low), high: Math.round(savings.high) },
    source: pvgis !== null ? 'pvgis' : 'estimate',
  });
};

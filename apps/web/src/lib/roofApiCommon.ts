/**
 * Socle commun des routes `src/pages/api/roof-*` (ENF19 : une seule copie). Volontairement
 * découplé de lib/lead (aucune plomberie de lead/CRM) : réponse de rejet cross-site propre à ces
 * routes (`error`, pas `detail`/`errors.origin`) et lecture tolérante d'un nombre (virgule FR).
 */
import { jsonResponse } from './apiJson';
import { clientIpFromRequest, rateLimit } from './rateLimit';
import { isSameOriginRequest } from './sameOrigin';

export function crossSiteRejection(): Response {
  return jsonResponse({ ok: false, error: 'Requête refusée.' }, 403);
}

export function num(v: unknown): number {
  return typeof v === 'number' ? v : parseFloat(String(v ?? '').replace(',', '.'));
}

/**
 * Prélude commun des proxys `roof-*` : garde same-origin (W317), rate-limit GÉNÉREUX et DÉDIÉ par
 * route (W316), corps JSON, puis lat/lon bornés. Renvoie soit la `response` de rejet à retourner
 * telle quelle, soit le corps et les coordonnées validés. Mêmes messages, mêmes statuts qu'avant.
 */
export async function preludeRoofProxy(
  request: Request,
  scope: string,
): Promise<{ response: Response } | { body: Record<string, unknown>; lat: number; lon: number }> {
  if (!isSameOriginRequest(request)) return { response: crossSiteRejection() };

  const rl = rateLimit(`${scope}:${clientIpFromRequest(request)}`, { limit: 60, windowMs: 60_000 });
  if (!rl.allowed) {
    return {
      response: jsonResponse({ ok: false, error: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
        'retry-after': String(rl.retryAfterSec),
      }),
    };
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return { response: jsonResponse({ ok: false, error: 'JSON invalide' }, 400) };
  }

  const lat = num(body.lat);
  const lon = num(body.lon);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
    return { response: jsonResponse({ ok: false, error: 'lat invalide' }, 400) };
  }
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) {
    return { response: jsonResponse({ ok: false, error: 'lon invalide' }, 400) };
  }
  return { body, lat, lon };
}

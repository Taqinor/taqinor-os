/**
 * Prélude commun des proxys à jeton (`proposition-accept`, `proposition-otp`,
 * `questionnaire-repondre`) : same-origin (W317), rate-limit par route, corps JSON, jeton non vide.
 * Extrait tel quel de ces trois routes (dette « duplicats littéraux ») : mêmes messages, mêmes
 * statuts, même ordre de contrôle. Renvoie la `response` de rejet, ou le corps et le jeton.
 */
import { crossSiteRejection, isSameOriginRequest } from './lead';
import { clientIpFromRequest, rateLimit } from './rateLimit';
import { jsonResponse as json } from './apiJson';

export async function preludeJeton(
  request: Request,
  opts: { scope: string; limit: number; jetonManquant: string },
): Promise<{ response: Response } | { body: Record<string, unknown>; token: string }> {
  if (!isSameOriginRequest(request)) return { response: crossSiteRejection() };

  const rl = rateLimit(`${opts.scope}:${clientIpFromRequest(request)}`, { limit: opts.limit, windowMs: 60_000 });
  if (!rl.allowed) {
    return {
      response: json({ ok: false, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
        'retry-after': String(rl.retryAfterSec),
      }),
    };
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return { response: json({ ok: false, detail: 'Requête invalide.' }, 400) };
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) return { response: json({ ok: false, detail: opts.jetonManquant }, 400) };
  return { body, token };
}

/**
 * Prélude commun des balises/événements (`proposition-engagement`, `proposition-track`,
 * `funnel-beacon`, `visite`) : same-origin, rate-limit par route, corps JSON ; échecs sans détail
 * (`{ ok: false }`) — ces routes ne parlent jamais au visiteur. Renvoie la `response` ou le corps.
 */
export async function preludeBalise(
  request: Request,
  opts: { scope: string; limit: number },
): Promise<{ response: Response } | { body: unknown }> {
  if (!isSameOriginRequest(request)) return { response: crossSiteRejection() };

  const rl = rateLimit(`${opts.scope}:${clientIpFromRequest(request)}`, { limit: opts.limit, windowMs: 60_000 });
  if (!rl.allowed) {
    return { response: json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) }) };
  }

  try {
    return { body: await request.json() };
  } catch {
    return { response: json({ ok: false }, 400) };
  }
}

/**
 * Appel du backend ERP en JSON (proxys `proposition-accept`, `proposition-otp`,
 * `lead-ref-lookup`) : renvoie le statut amont et le corps JSON (`null` si illisible), ou `null`
 * quand le backend est injoignable (l'appelant répond alors 502 sans détail).
 */
export async function appelAmontJson(
  url: string,
  init: RequestInit,
): Promise<{ status: number; payload: unknown } | null> {
  try {
    const res = await fetch(url, init);
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
    return { status: res.status, payload };
  } catch {
    return null;
  }
}

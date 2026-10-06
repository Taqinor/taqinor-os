/**
 * POST /api/lead-affiner — proxy SAME-ORIGIN de la relève « Affiner »
 * (CIW405, D-CIQ-8, contrat CIQ400 `lead_affiner_pro.json`, backend CIQ413).
 *
 * CONTEXTE. Après la porte de contact, un lead COMMERCIAL ou INDUSTRIEL peut
 * (facultativement) préciser sa demande dans le questionnaire pro. Le site n'a
 * que l'`idempotencyKey` de sa soumission (l'envoi du lead est fire-and-forget,
 * une seconde soumission créerait un NOUVEAU lead). Ce proxy relaie
 * `POST {API_BASE}/api/django/crm/public/lead-affiner/<key>/` et renvoie le
 * jeton du questionnaire pro de CETTE soumission, rien d'autre.
 *
 * MÊME PATRON que lead-ref-lookup.ts : API_BASE (PUBLIC_API_BASE runtime cf.env
 * OU build, sinon https://api.taqinor.ma), garde same-origin, rate-limit
 * dédié, JAMAIS LEAD_WEBHOOK_URL (secret réservé à la capture, cf. WJ109).
 *
 * Réponse toujours { ok: boolean, token?, url? }, jamais une erreur brute : un
 * 404 opaque du CRM, une panne ou une réponse inexploitable → { ok:false } ;
 * l'appelant retire alors son bouton sans message alarmant.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';
import { jsonResponse as json, relayJson, resolveApiBase } from './_proxy';

// Même forme que `idempotencyKey` (lib/lead.ts) et lead-ref-lookup.ts.
const IDEMPOTENCY_KEY_RE = /^[A-Za-z0-9_-]{8,64}$/;
// Jeton de questionnaire : alphabet URL-safe, jamais un chemin ni une query.
const TOKEN_RE = /^[A-Za-z0-9_-]{8,200}$/;

function affinerEndpoint(apiBase: string, key: string): string {
  return `${apiBase.replace(/\/+$/, '')}/api/django/crm/public/lead-affiner/${encodeURIComponent(key)}/`;
}

export const POST: APIRoute = async ({ request }) => {
  // Garde same-origin (W317) : un POST cross-site forgé est refusé avant tout
  // appel amont.
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // Bucket DÉDIÉ : un clic volontaire par soumission, jamais une boucle.
  const rl = rateLimit(`lead-affiner:${clientIpFromRequest(request)}`, { limit: 10, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  let key = '';
  try {
    const body = (await request.json()) as Record<string, unknown> | null;
    key = typeof body?.key === 'string' ? body.key.trim() : '';
  } catch {
    return json({ ok: false }, 400);
  }
  if (!IDEMPOTENCY_KEY_RE.test(key)) return json({ ok: false }, 400);

  const relais = await relayJson(affinerEndpoint(resolveApiBase(), key), {
    method: 'POST',
    headers: { accept: 'application/json' },
    signal: AbortSignal.timeout(5000),
  });
  if (!relais) return json({ ok: false }, 502);
  const { status: upstreamStatus, payload: upstreamPayload } = relais;

  const raw =
    upstreamStatus === 200 && upstreamPayload && typeof upstreamPayload === 'object'
      ? (upstreamPayload as Record<string, unknown>).questionnaire_token
      : null;
  const token = typeof raw === 'string' ? raw.trim() : '';
  if (!token || !TOKEN_RE.test(token)) {
    return json({ ok: false }, upstreamStatus === 404 ? 404 : 502);
  }
  return json({ ok: true, token, url: `/questionnaire/${encodeURIComponent(token)}` });
};

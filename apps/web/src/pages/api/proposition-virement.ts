/**
 * POST /api/proposition-virement — proxy SAME-ORIGIN de « J'ai effectué le virement » (ADEV53).
 *
 * Le navigateur poste ici { token } ; ce handler relaie vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/virement/` (QX33be : note chatter + notification
 * du conseiller, AUCUN statut changé, aucun Paiement créé ; idempotent par heure ; 403
 * `otp_required` si la lecture du lien exige un code non saisi ; 403 sur un aperçu interne).
 * Même convention que `proposition-option.ts` : garde same-origin, rate-limit dédié, IP du client.
 * Corps amont vide : le jeton authentifie, rien d'autre n'est relayé.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { normalizeVirementResponse, virementEndpoint } from '../../lib/paiementAcceptation';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';
import { jsonResponse as json, relayJson, resolveApiBase } from './_proxy';

export const POST: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`proposition-virement:${clientIpFromRequest(request)}`, { limit: 10, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false, status: 429, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, status: 400, detail: 'Requête invalide.' }, 400);
  }
  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) return json({ ok: false, status: 400, detail: 'Lien de proposition manquant.' }, 400);

  const clientIp = clientIpFromRequest(request);
  const ip = clientIp && clientIp !== 'unknown' ? clientIp : '';
  const relais = await relayJson(virementEndpoint(resolveApiBase(), token), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      ...(ip ? { 'X-Forwarded-For': ip, 'CF-Connecting-IP': ip } : {}),
    },
    body: '{}',
  });
  if (!relais) {
    return json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }
  const status = relais.status >= 200 && relais.status < 600 ? relais.status : 502;
  return json(normalizeVirementResponse(relais.status, relais.payload), status);
};

/**
 * POST /api/proposition-option — proxy SAME-ORIGIN de l'activation d'une option du kit (AGW308).
 *
 * Le navigateur du client n'appelle JAMAIS le backend en cross-origin : il poste ici
 * { token, ligne_id } et ce handler relaie côté serveur vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/activer-option/` (XSAL5, endpoint public
 * tokenisé, idempotent : aucun statut de devis n'est touché ; 409 si le devis est figé ;
 * 403 `otp_required` si la lecture exige un code ; 403 sur un lien d'aperçu interne).
 * Même convention que `proposition-accept.ts` : API_BASE (PUBLIC_API_BASE runtime cf.env OU
 * build, sinon https://api.taqinor.ma), garde same-origin, rate-limit dédié.
 *
 * Le corps relayé est `{ ligne_id }` SEUL (entier > 0) ; le statut amont est reflété tel quel
 * (200 / 400 / 403 / 404 / 409) avec un JSON normalisé { ok, status, detail, ligneId? }.
 * Aucune donnée de prix n'est manipulée ici : les totaux sont rechargés par la page depuis le
 * serveur, jamais recalculés.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { buildOptionBody, normalizeOptionResponse, optionEndpoint } from '../../lib/proposition';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

function resolveApiBase(): string {
  const env = (cf.env ?? {}) as { PUBLIC_API_BASE?: string };
  const runtime = env.PUBLIC_API_BASE?.trim();
  const build = (import.meta.env.PUBLIC_API_BASE as string | undefined)?.trim();
  return runtime || build || 'https://api.taqinor.ma';
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — un POST cross-site forgé est refusé avant tout traitement : activer une option
  // CHANGE le périmètre facturé du devis.
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`proposition-option:${clientIpFromRequest(request)}`, { limit: 20, windowMs: 60_000 });
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

  const upstreamBody = buildOptionBody(body.ligne_id);
  if (!upstreamBody) return json({ ok: false, status: 400, detail: 'Option invalide.' }, 400);

  // L'activation d'une option étant un acte du client (jamais du proxy), l'IP du client est
  // transmise comme pour la signature : jamais l'IP de sortie du Worker, jamais 'unknown'.
  const clientIp = clientIpFromRequest(request);
  const ip = clientIp && clientIp !== 'unknown' ? clientIp : '';

  let upstreamStatus = 502;
  let upstreamPayload: unknown = null;
  try {
    const res = await fetch(optionEndpoint(resolveApiBase(), token), {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
        ...(ip ? { 'X-Forwarded-For': ip, 'CF-Connecting-IP': ip } : {}),
      },
      body: JSON.stringify(upstreamBody),
    });
    upstreamStatus = res.status;
    try {
      upstreamPayload = await res.json();
    } catch {
      upstreamPayload = null;
    }
  } catch {
    return json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }

  // On relaie le statut backend (200 / 400 / 403 / 404 / 409) et l'objet normalisé : la page
  // choisit le message amical dans OPTION_MSG, sans jamais afficher un détail technique.
  const result = normalizeOptionResponse(upstreamStatus, upstreamPayload);
  const status = upstreamStatus >= 200 && upstreamStatus < 600 ? upstreamStatus : 502;
  // `otp_required` doit rester lisible côté page pour redemander le code.
  const detail =
    upstreamPayload && typeof upstreamPayload === 'object' && (upstreamPayload as { detail?: unknown }).detail === 'otp_required'
      ? 'otp_required'
      : result.detail;
  return json({ ...result, detail }, status);
};

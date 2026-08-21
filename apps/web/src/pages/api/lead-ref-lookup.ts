/**
 * GET /api/lead-ref-lookup?key=… — proxy SAME-ORIGIN de la relève PUBLIQUE de
 * la référence serveur (WREF2-L3, GO fondateur 21/08/2026 — option B).
 *
 * CONTEXTE. L'envoi du lead (/api/capture-lead) est délibérément fire-and-
 * forget : le formulaire n'attend JAMAIS la réponse du webhook CRM, donc
 * l'écran de succès ne connaît que le code PROVISOIRE tiré par le navigateur
 * (« TQ-XXXX », buildClientRef() dans lib/lead.ts). La vraie référence
 * serveur (« NOM-N ») n'est attribuée qu'APRÈS, côté récepteur taqinor-os
 * (apps.crm.webhooks.assign_client_ref). L'écran de succès interroge CETTE
 * route après coup (quelques tentatives espacées, cf. mon-toit.astro) pour
 * remplacer le code affiché dès que la vraie référence est disponible.
 *
 * MÊME RÉSOLUTION D'API_BASE que /api/proposition-accept|contact|otp
 * (PUBLIC_API_BASE runtime cf.env OU build import.meta.env, sinon
 * https://api.taqinor.ma) — PAS LEAD_WEBHOOK_URL : ce secret Worker sert
 * UNIQUEMENT le webhook de capture (POST, secret partagé x-webhook-secret) et
 * ne doit JAMAIS être réutilisé pour un autre appel (voir la note WJ109 en
 * tête de proposition-track.ts — une simple lecture n'est PAS une capture de
 * lead). Le endpoint Django ciblé ici est PUBLIC et SANS secret (throttlé,
 * 404 opaque), exactement comme /api/django/ventes/proposal/<token>/… : la
 * même famille de proxy « API_BASE + chemin public » s'applique.
 *
 * Réponse toujours { ok: boolean, client_ref? }, jamais une erreur brute — un
 * échec (backend injoignable, pas encore de référence, clé invalide) dégrade
 * en { ok:false } : l'appelant garde alors le code provisoire déjà affiché.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

// Même discipline anti-garbage que `idempotencyKey` côté lib/lead.ts (déjà
// validée avant envoi) — une valeur hors de cette forme ne peut être celle
// d'AUCUNE soumission réelle, jamais la peine d'appeler le backend.
const IDEMPOTENCY_KEY_RE = /^[A-Za-z0-9_-]{8,64}$/;

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

function leadRefEndpoint(apiBase: string, key: string): string {
  return `${apiBase.replace(/\/+$/, '')}/api/django/crm/public/lead-ref/${encodeURIComponent(key)}/`;
}

export const GET: APIRoute = async ({ request }) => {
  // W317 — même garde-fou que les autres proxies same-origin : un GET
  // cross-site forgé (widget tiers sondant des idempotencyKey) est refusé
  // avant tout appel amont.
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // Bucket DÉDIÉ, généreux : l'écran de succès ne fait que 2-3 tentatives
  // espacées par soumission (jamais un onglet ouvert qui boucle).
  const rl = rateLimit(`lead-ref-lookup:${clientIpFromRequest(request)}`, { limit: 20, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  const key = new URL(request.url).searchParams.get('key')?.trim() ?? '';
  if (!IDEMPOTENCY_KEY_RE.test(key)) {
    return json({ ok: false }, 400);
  }

  const target = leadRefEndpoint(resolveApiBase(), key);
  let upstreamStatus = 502;
  let upstreamPayload: unknown = null;
  try {
    const res = await fetch(target, {
      method: 'GET',
      headers: { accept: 'application/json' },
      signal: AbortSignal.timeout(5000),
    });
    upstreamStatus = res.status;
    try {
      upstreamPayload = await res.json();
    } catch {
      upstreamPayload = null;
    }
  } catch {
    // Backend injoignable/timeout : dégradation honnête, jamais une erreur
    // brute — l'appelant garde le code provisoire déjà affiché.
    return json({ ok: false }, 502);
  }

  const clientRef =
    upstreamStatus === 200 &&
    upstreamPayload &&
    typeof (upstreamPayload as Record<string, unknown>).client_ref === 'string'
      ? ((upstreamPayload as Record<string, unknown>).client_ref as string)
      : '';

  if (!clientRef) {
    return json({ ok: false }, upstreamStatus === 404 ? 404 : 502);
  }
  return json({ ok: true, client_ref: clientRef });
};

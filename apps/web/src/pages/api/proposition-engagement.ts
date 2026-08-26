/**
 * POST /api/proposition-engagement — proxy SAME-ORIGIN du beacon d'engagement
 * par section de la proposition (ANALYT1, audit item 64).
 *
 * Le navigateur du client n'appelle JAMAIS le backend en cross-origin (même
 * discipline que `proposition-accept.ts`/`proposition-otp.ts`) : il poste ici
 * `{ token, section, seconds, visit_id }` et ce handler relaie côté serveur
 * vers `{API_BASE}/api/django/public/proposal/<token>/engagement/`
 * (`apps/ventes/public_views.py proposal_engagement`, XSAL16 — endpoint
 * public/token, sans login, déjà rate-limité côté backend). Best-effort
 * strict : un échec ici ne doit JAMAIS remonter visiblement au client — la
 * page proposition ne dépend d'aucune manière de ce beacon pour fonctionner.
 *
 * `visit_id` (ANALYT1) — identifiant de VISITE généré côté navigateur
 * (`lib/engagementBeacon.ts creerVisitId`), JAMAIS persisté au-delà de
 * l'onglet : relayé tel quel, ignoré par un backend antérieur à cette lane.
 *
 * W316/W317 — même bucket de rate-limit ET même garde Origin/Sec-Fetch-Site
 * que les quatre autres proxies `proposition-*` de ce dossier ; généreux (un
 * flush périodique/débounce par section peut poster plusieurs fois par page).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { engagementEndpoint } from '../../lib/proposition';
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
  // W317 — refuse un POST cross-site forgé avant tout traitement.
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // W316 — bucket dédié, généreux (débounce ~4 s par section + flush au
  // pagehide : une page ouverte longtemps sur plusieurs sections poste
  // plusieurs fois, jamais un seul appel).
  const rl = rateLimit(`proposition-engagement:${clientIpFromRequest(request)}`, {
    limit: 40,
    windowMs: 60_000,
  });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false }, 400);
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  const section = typeof body.section === 'string' ? body.section.trim() : '';
  const seconds = body.seconds;
  const visitId = typeof body.visit_id === 'string' ? body.visit_id.trim() : '';

  if (!token || !section) return json({ ok: false }, 400);

  const url = engagementEndpoint(resolveApiBase(), token);
  const upstreamBody: Record<string, unknown> = { section, seconds };
  if (visitId) upstreamBody.visit_id = visitId;

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(upstreamBody),
      // Le beacon ne doit jamais faire traîner la navigation : l'appel
      // amont a son propre budget best-effort.
      signal: AbortSignal.timeout(8000),
    });
    return json({ ok: true }, res.status >= 200 && res.status < 500 ? 204 : 202);
  } catch {
    // Backend injoignable : jamais bloquant côté client (beacon fire-and-forget).
    return json({ ok: false, sent: false }, 202);
  }
};

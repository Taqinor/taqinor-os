/**
 * POST /api/visite — proxy SAME-ORIGIN de la balise de visite site entier
 * (LANE T-WEB). Voir `lib/visite.ts` pour le contrat complet, la discipline
 * anti-PII et la note sur le choix d'authentification.
 *
 * Relais direct vers `{API_BASE}/api/django/crm/public/visite/` — même patron
 * que `pages/api/questionnaire-repondre.ts` (le backend n'est jamais exposé
 * au navigateur, aucun CORS n'est ouvert, l'IP cliente reste côté
 * Cloudflare). Aucun secret statique : ce chemin est un endpoint PUBLIC
 * (`/api/django/crm/public/...`), pas le webhook de capture de lead
 * (`LEAD_WEBHOOK_URL`/`LEAD_WEBHOOK_SECRET`, `apps/crm/webhooks.py`) — la
 * garde d'entrée est la MÊME que tous les autres proxies same-origin de ce
 * dossier : `isSameOriginRequest`/`crossSiteRejection` (`lib/lead.ts`) +
 * rate-limit par IP.
 *
 * Best-effort strict, comme `funnel-beacon.ts` : ne bloque jamais l'appelant
 * (réponse en arrière-plan via `waitUntil` quand disponible), aucune erreur
 * réseau ne remonte au client.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { validateVisiteBody } from '../../lib/visite';
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

function visiteEndpoint(apiBase: string): string {
  return `${apiBase.replace(/\/+$/, '')}/api/django/crm/public/visite/`;
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : même garde-fou que les autres proxies
  // same-origin (funnel-beacon, proposition-track, questionnaire-repondre).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // Bucket dédié, généreux : un battement ~20 s + un envoi final par page —
  // un visiteur multi-onglets normal reste largement sous ce plafond.
  const rl = rateLimit(`visite:${clientIpFromRequest(request)}`, { limit: 60, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false }, 400);
  }

  const validated = validateVisiteBody(body);
  if (!validated) return json({ ok: false }, 400);

  const background = (async () => {
    try {
      await fetch(visiteEndpoint(resolveApiBase()), {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify(validated),
        signal: AbortSignal.timeout(5000),
      });
    } catch {
      // Best-effort strict : une panne backend ne doit jamais remonter au client
      // (la balise ne réessaie jamais — un battement suivant suffira).
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  return json({ ok: true });
};

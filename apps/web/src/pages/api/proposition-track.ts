/**
 * POST /api/proposition-track — proxy SAME-ORIGIN de la télémétrie de vue/
 * engagement de la proposition (WJ55).
 *
 * Le navigateur du client poste ici { token, reference, clientPhone, event }
 * (`event` ∈ 'proposal_first_view' | 'proposal_scrolled_financing') et ce
 * handler relaie côté serveur vers le MÊME fil lead que capture-lead/preview-
 * lead — `LEAD_WEBHOOK_URL` + en-tête `X-Webhook-Secret` (`LEAD_WEBHOOK_SECRET`)
 * — AUCUN nouvel endpoint backend, AUCUN nouveau secret. `buildProposalTrackPayload`
 * (lib/proposition.ts) porte le garde-fou anti-pollution CRM : sans téléphone
 * client exploitable, elle renvoie `null` et cette route répond 202 sans rien
 * poster (jamais un lead fantôme créé pour un simple événement de lecture).
 *
 * Best-effort strict : ne bloque JAMAIS l'UX (toujours 200/202 côté client),
 * aucune PII journalisée, tolère l'absence de configuration webhook.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { buildProposalTrackPayload, type ProposalEngagementEvent } from '../../lib/proposition';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

interface TrackEnv {
  LEAD_WEBHOOK_URL?: string;
  LEAD_WEBHOOK_SECRET?: string;
}

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

const VALID_EVENTS: ProposalEngagementEvent[] = ['proposal_first_view', 'proposal_scrolled_financing'];

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // W316 — bucket dédié, généreux : deux événements par vue de page suffisent,
  // mais un onglet laissé ouvert / un double-montage ne doit jamais bloquer.
  const rl = rateLimit(`proposition-track:${clientIpFromRequest(request)}`, { limit: 20, windowMs: 60_000 });
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
  const reference = typeof body.reference === 'string' ? body.reference.trim() : '';
  const clientPhone = typeof body.clientPhone === 'string' ? body.clientPhone : '';
  const eventRaw = body.event;
  const event: ProposalEngagementEvent | null = VALID_EVENTS.includes(eventRaw as ProposalEngagementEvent)
    ? (eventRaw as ProposalEngagementEvent)
    : null;

  if (!token || !event) return json({ ok: false }, 400);

  const payload = buildProposalTrackPayload({ reference, token, clientPhone }, event);
  if (!payload) {
    // Aucun téléphone client exploitable : événement abandonné proprement,
    // jamais un lead fantôme envoyé au CRM (voir la note dans lib/proposition.ts).
    return json({ ok: true, sent: false }, 202);
  }

  const env = (cf.env ?? {}) as TrackEnv;
  const url = env.LEAD_WEBHOOK_URL?.trim();
  if (!url) return json({ ok: true, sent: false }, 202);

  const background = (async () => {
    try {
      const headers: Record<string, string> = {
        'content-type': 'application/json',
        'x-webhook-timestamp': new Date().toISOString(),
      };
      const secret = env.LEAD_WEBHOOK_SECRET?.trim();
      if (secret) headers['x-webhook-secret'] = secret;
      await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(8000),
      });
    } catch {
      // Best-effort strict : une panne webhook ne doit jamais remonter au client.
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  return json({ ok: true, sent: true });
};

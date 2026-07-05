/**
 * POST /api/proposition-track — proxy SAME-ORIGIN de la télémétrie de vue/
 * engagement de la proposition (WJ55).
 *
 * Le navigateur du client poste ici { token, reference, clientPhone, event }
 * (`event` ∈ 'proposal_first_view' | 'proposal_scrolled_financing') et ce
 * handler relaie côté serveur vers le canal TÉLÉMÉTRIE/FUNNEL dédié
 * (`FUNNEL_WEBHOOK_URL` + `X-Webhook-Secret` optionnel via
 * `FUNNEL_WEBHOOK_SECRET`) — EXACTEMENT le même canal que
 * `pages/api/funnel-beacon.ts` (voir `lib/funnelBeacon.ts`).
 *
 * WJ109 — [CORRECTIF DE CORRUPTION DE DONNÉES EN PRODUCTION] Cette route
 * postait auparavant vers `LEAD_WEBHOOK_URL`, le webhook de CAPTURE DE LEAD du
 * CRM (`apps/crm/webhooks.py`). Ce webhook traite CHAQUE payload reçu comme une
 * mise à jour de lead ; sans nom exploitable dans l'événement, il écrasait le
 * NOM RÉEL du lead existant par « Lead site web » et le retaguait — un client
 * qui se contentait d'OUVRIR sa proposition corrompait donc sa propre fiche
 * CRM. `LEAD_WEBHOOK_URL`/`LEAD_WEBHOOK_SECRET` ne doivent PLUS JAMAIS être lus
 * ici : une simple vue de proposition n'est PAS une capture de lead. Quand
 * `FUNNEL_WEBHOOK_URL` n'est pas configuré, l'événement est journalisé
 * (log-only, comme `funnel-beacon.ts`) — jamais posté au fil lead.
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
  /** WJ109 — canal télémétrie DÉDIÉ, distinct du webhook de lead CRM (voir la
   *  note ci-dessus). Absent par défaut : log-only, jamais bloquant. */
  FUNNEL_WEBHOOK_URL?: string;
  FUNNEL_WEBHOOK_SECRET?: string;
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

  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- clientPhone kept for API compat, never forwarded (WJ109)
  void clientPhone;
  const payload = buildProposalTrackPayload({ reference, token }, event);
  if (!payload) {
    // Rien de corrélable (ni référence ni token) : événement abandonné
    // proprement, jamais rien posté nulle part.
    return json({ ok: true, sent: false }, 202);
  }

  const env = (cf.env ?? {}) as TrackEnv;
  // WJ109 — canal télémétrie/funnel UNIQUEMENT ; ne JAMAIS lire
  // LEAD_WEBHOOK_URL ici (voir la note en tête de fichier).
  const url = env.FUNNEL_WEBHOOK_URL?.trim();
  if (!url) {
    // Log-only, comme funnel-beacon.ts : aucune PII, jamais bloquant.
    console.log('[proposition-track]', JSON.stringify(payload));
    return json({ ok: true, sent: false }, 202);
  }

  const background = (async () => {
    try {
      const headers: Record<string, string> = {
        'content-type': 'application/json',
        'x-webhook-timestamp': new Date().toISOString(),
      };
      const secret = env.FUNNEL_WEBHOOK_SECRET?.trim();
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

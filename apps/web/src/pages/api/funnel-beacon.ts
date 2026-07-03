/**
 * POST /api/funnel-beacon — WJ59, step-level funnel analytics.
 *
 * A tiny privacy-light beacon posted by /devis/mon-toit on step reached /
 * step abandoned. See src/lib/funnelBeacon.ts for the full contract and the
 * reasoning behind NOT reusing the CRM lead webhook here (it would create a
 * spurious Lead row per event). Same-origin, no new dependency, same
 * rate-limit discipline as the other capture endpoints (distinct bucket).
 *
 * Never blocks the caller: `navigator.sendBeacon`/`fetch(..., keepalive)`
 * on the client don't wait for a meaningful response either way.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { forwardBeacon, redactBeaconForLog, validateBeaconEvent, type FunnelEnv } from '../../lib/funnelBeacon';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store', ...headers },
  });
}

export const POST: APIRoute = async ({ request }) => {
  // Bucket distinct + limite plus généreuse : un parcours normal envoie
  // plusieurs événements (un par étape), jamais une seule requête.
  const rl = rateLimit(`funnel-beacon:${clientIpFromRequest(request)}`, { limit: 40, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false }, 400);
  }

  const validation = validateBeaconEvent(body);
  if (!validation.ok) return json({ ok: false }, 400);

  const env = (cf.env ?? {}) as FunnelEnv;
  const background = (async () => {
    const fw = await forwardBeacon(validation.event, env, fetch);
    // Log-only par défaut (aucun webhook dédié configuré) : c'est le signal
    // exploitable aujourd'hui — jamais de PII possible ici (cf. lib/funnelBeacon).
    if (!fw.delivered) {
      console.log('[funnel-beacon]', JSON.stringify(redactBeaconForLog(validation.event)));
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  return json({ ok: true });
};

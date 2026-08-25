/**
 * POST /api/visite — proxy SAME-ORIGIN de la balise de visite site entier
 * (LANE T-WEB). Voir `lib/visite.ts` pour le contrat complet, la discipline
 * anti-PII et la note sur le choix d'authentification.
 *
 * Relais direct vers `{API_BASE}/api/django/crm/public/visite/` — même patron
 * que `pages/api/questionnaire-repondre.ts` (le backend n'est jamais exposé
 * au navigateur, aucun CORS n'est ouvert, l'IP cliente reste côté
 * Cloudflare). La garde d'ENTRÉE (navigateur → ce proxy) est la MÊME que tous
 * les autres proxies same-origin de ce dossier : `isSameOriginRequest`/
 * `crossSiteRejection` (`lib/lead.ts`) + rate-limit par IP. Côté SORTIE (ce
 * proxy → backend), recalage porte finale 25/08 (décision orchestrateur) : le
 * récepteur backend EXIGE la même auth webhook que la capture de lead
 * (`X-Webhook-Secret` = `LEAD_WEBHOOK_SECRET`, `apps/crm/webhooks.py`) —
 * voir le détail juste plus bas.
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

  // Recalage porte finale 25/08 (décision orchestrateur) — le récepteur
  // backend EXIGE l'auth du webhook lead (X-Webhook-Secret, valeur
  // LEAD_WEBHOOK_SECRET du Worker = WEBSITE_LEAD_WEBHOOK_SECRET côté Django,
  // hmac.compare_digest, refus 401) : ces visites alimentent les alertes
  // « concurrent » envoyées à la direction — un endpoint non signé serait
  // empoisonnable par de fausses visites. Secret absent du Worker → on
  // n'appelle même pas (le backend refuserait) ; la balise reste best-effort.
  const secret = ((cf.env ?? {}) as { LEAD_WEBHOOK_SECRET?: string })
    .LEAD_WEBHOOK_SECRET?.trim();
  // Finding 8 (même famille que les fetch SSR) — sans cet en-tête, l'IP vue
  // par le backend serait celle de SORTIE du Worker (identique pour tous les
  // visiteurs) et la corrélation IP rapprocherait des inconnus. Best-effort :
  // IP non identifiable → en-tête omis, le backend enregistre ip=''.
  const clientIp = clientIpFromRequest(request);
  const background = (async () => {
    if (!secret) return;
    try {
      await fetch(visiteEndpoint(resolveApiBase()), {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          accept: 'application/json',
          'X-Webhook-Secret': secret,
          'X-Webhook-Timestamp': new Date().toISOString(),
          ...(clientIp
            ? { 'X-Forwarded-For': clientIp, 'CF-Connecting-IP': clientIp }
            : {}),
        },
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

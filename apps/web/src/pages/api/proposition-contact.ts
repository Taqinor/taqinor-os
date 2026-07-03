/**
 * POST /api/proposition-contact — proxy SAME-ORIGIN de « Être contacté » /
 * « Demander un rappel » (WJ29).
 *
 * Aujourd'hui les boutons rappel/WhatsApp de /proposition/[token] sont des
 * liens client purs (tel:, wa.me) : rien ne notifie l'équipe côté serveur. Ce
 * proxy poste { token, channel, message? } et relaie côté serveur vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/contact/` — SYMÉTRIQUE de
 * /api/proposition-accept (même résolution d'API_BASE, même non-exposition du
 * backend au navigateur).
 *
 * Le backend n'expose PAS ENCORE cette route (PLAN2 QJ27, pas construite) :
 * un 404 amont, un 5xx, ou une panne réseau dégradent TOUS vers la même
 * réponse honnête { ok:false, degraded:true, detail:"…contactez-nous sur
 * WhatsApp…" } — jamais une erreur technique brute. Le lien wa.me instantané
 * reste toujours affiché à côté, quel que soit le résultat de cet appel :
 * cette route est un « mieux si possible », jamais un blocage.
 *
 * WJ54 — le même proxy porte aussi la demande de modification structurée
 * (« Demander une modification » : ajuster kWc / changer batterie / autre) —
 * canal `revision` DISTINCT, avec un `revision_kind` optionnel relayé tel
 * quel au backend. AUCUN nouvel endpoint : c'est le même contrat additif que
 * les canaux existants, le backend qui l'ignore continue de fonctionner
 * exactement comme avant.
 *
 * W316 — bucket de rate-limit DÉDIÉ (distinct d'accept/track/roof-*).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  contactEndpoint,
  buildContactBody,
  normalizeContactResponse,
  type ContactChannel,
} from '../../lib/proposition';
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
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`proposition-contact:${clientIpFromRequest(request)}`, { limit: 10, windowMs: 60_000 });
  if (!rl.allowed) {
    return json({ ok: false, degraded: true, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, degraded: true, detail: 'Requête invalide.' }, 400);
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) {
    return json({ ok: false, degraded: true, detail: 'Lien de proposition manquant.' }, 400);
  }

  const channelRaw = body.channel;
  const channel: ContactChannel =
    channelRaw === 'whatsapp' || channelRaw === 'question' || channelRaw === 'rappel' ||
    channelRaw === 'voice' || channelRaw === 'revision'
      ? channelRaw
      : 'rappel';
  const revisionKindRaw = body.revision_kind;
  const revisionKind =
    revisionKindRaw === 'kwc' || revisionKindRaw === 'batterie' || revisionKindRaw === 'autre'
      ? revisionKindRaw
      : undefined;
  const upstreamBody = buildContactBody({
    channel,
    message: typeof body.message === 'string' ? body.message : '',
    revisionKind,
  });

  const url = contactEndpoint(resolveApiBase(), token);

  let upstreamStatus = 502;
  let networkError = false;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ token, ...upstreamBody }),
    });
    upstreamStatus = res.status;
  } catch {
    // Backend injoignable (ou route pas encore déployée) : dégradation propre,
    // jamais une fuite de détail technique côté client.
    networkError = true;
  }

  const result = normalizeContactResponse(upstreamStatus, networkError);
  // On répond TOUJOURS 200 côté proxy : le client affiche `result.detail`
  // (confirmation OU repli WhatsApp honnête) — jamais un état d'erreur HTTP
  // qui casserait le flux « une question avant de signer ? ».
  return json(result, 200);
};

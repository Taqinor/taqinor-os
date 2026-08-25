/**
 * POST /api/questionnaire-repondre — proxy SAME-ORIGIN des réponses du
 * questionnaire client (lane Q, recalage orchestrateur 25/08).
 *
 * La page /questionnaire/[token] enregistre SECTION PAR SECTION (le client
 * reprend où il s'est arrêté). Le navigateur poste { token, section,
 * reponses, photo? } ICI, et le proxy relaie côté serveur vers
 * `{API_BASE}/api/django/crm/public/questionnaire/<token>/` — MÊME patron que
 * /api/proposition-contact : le backend n'est jamais exposé au navigateur,
 * aucun CORS n'est ouvert, l'IP cliente reste côté Cloudflare.
 *
 * Contrairement au proxy contact (« mieux si possible »), la RÉUSSITE compte
 * ici : la page marque la section « répondue » seulement sur { ok:true } — on
 * relaie donc fidèlement le { ok, enregistrees } du backend en 200, et tout
 * échec (token invalide/expiré → 404 générique amont, 5xx, réseau) redescend
 * en { ok:false, detail } SOBRE — jamais un détail technique, jamais un faux
 * succès.
 *
 * Bucket de rate-limit DÉDIÉ (les sections photo portent du base64 ~Mo) :
 * 30 requêtes/min/IP — au-dessus du parcours réel (9 sections + reprises),
 * en dessous d'un abus.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { questionnaireEndpoint } from '../../lib/questionnaire';
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

const DETAIL_ECHEC = 'Cette réponse n’a pas pu être enregistrée. Réessayez dans un instant.';

export const POST: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const rl = rateLimit(`questionnaire-repondre:${clientIpFromRequest(request)}`, {
    limit: 30, windowMs: 60_000,
  });
  if (!rl.allowed) {
    return json({ ok: false, detail: 'Trop de tentatives, réessayez dans un instant.' }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, detail: 'Requête invalide.' }, 400);
  }

  const token = typeof body.token === 'string' ? body.token.trim() : '';
  if (!token) return json({ ok: false, detail: 'Lien de questionnaire manquant.' }, 400);

  // Le corps amont est celui du contrat (section/reponses/photo) — le token
  // voyage dans l'URL amont, jamais dupliqué dans le corps relayé.
  const { token: _t, ...upstreamBody } = body;

  try {
    const res = await fetch(questionnaireEndpoint(resolveApiBase(), token), {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify(upstreamBody),
    });
    let upstream: unknown = null;
    try {
      upstream = await res.json();
    } catch {
      upstream = null;
    }
    if (res.ok && upstream && typeof upstream === 'object') {
      // Relais fidèle du { ok, enregistrees } backend — la page s'appuie dessus.
      return json(upstream, 200);
    }
    return json({ ok: false, detail: DETAIL_ECHEC }, 200);
  } catch {
    return json({ ok: false, detail: 'Connexion impossible. Vérifiez votre réseau et réessayez.' }, 200);
  }
};

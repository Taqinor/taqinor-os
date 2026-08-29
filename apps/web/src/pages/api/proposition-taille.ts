/**
 * GET /api/proposition-taille?token=…&cle=eco|max&variante=sans|avec — proxy
 * SAME-ORIGIN du DÉTAIL d'une taille explorable (OPTIONS CHARGEABLES, ordre
 * fondateur 29/08/2026).
 *
 * Le navigateur du client n'appelle JAMAIS le backend en cross-origin (même
 * discipline que `proposition-engagement.ts` / `proposition-accept.ts`) : il
 * demande ici, et ce handler relaie côté serveur vers
 * `{API_BASE}/api/django/public/proposal/<token>/taille/<cle>/?variante=…`
 * (`apps/ventes/public_views.py proposal_taille_detail` — endpoint public,
 * tokenisé, sans login, en LECTURE PURE et déjà rate-limité côté backend).
 *
 * DÉGRADATION HONNÊTE. Tout échec (jeton refusé, taille non envoyée à ce
 * client, backend injoignable) revient en `{ ok: false }` : la page garde
 * alors son comportement d'avant — la synchronisation des seuls chiffres de
 * tête — et propose de réessayer. Aucun chapitre profond n'affiche jamais les
 * chiffres du devis officiel sous une carte qui n'est pas lui.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import { estChargeable, tailleDetailEndpoint } from '../../lib/tailleDetail';
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

export const GET: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // Bucket dédié. Un client curieux bascule entre trois cartes et deux
  // variantes : au plus quatre allers-retours réels (la page met en cache par
  // taille+variante), donc cette borne est large sans être un canal d'abus.
  const rl = rateLimit(`proposition-taille:${clientIpFromRequest(request)}`, {
    limit: 30,
    windowMs: 60_000,
  });
  if (!rl.allowed) {
    return json({ ok: false }, 429, { 'retry-after': String(rl.retryAfterSec) });
  }

  const url = new URL(request.url);
  const token = (url.searchParams.get('token') || '').trim();
  const cle = (url.searchParams.get('cle') || '').trim();
  const variante = (url.searchParams.get('variante') || '').trim();

  // `recommande` n'a PAS d'endpoint (c'est le devis : la page le restaure
  // depuis ses originaux). On refuse ici plutôt que d'aller chercher un 404.
  if (!token || !estChargeable(cle) || (variante !== 'sans' && variante !== 'avec')) {
    return json({ ok: false }, 400);
  }

  try {
    const res = await fetch(tailleDetailEndpoint(resolveApiBase(), token, cle, variante), {
      method: 'GET',
      headers: { accept: 'application/json' },
      signal: AbortSignal.timeout(12_000),
    });
    if (!res.ok) return json({ ok: false }, 200);
    const detail = await res.json();
    return json({ ok: true, detail });
  } catch {
    return json({ ok: false }, 200);
  }
};

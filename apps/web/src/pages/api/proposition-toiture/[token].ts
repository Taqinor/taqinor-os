/**
 * GET /api/proposition-toiture/<token> — relais SAME-ORIGIN de l'affiche de toiture de la
 * proposition (ASEC53, D-ASEC-53-RELAIS, 29/10/2026).
 *
 * L'ERP sert l'image derrière le jeton (`/api/django/ventes/proposal/<token>/roof-image/`,
 * ACAL314) avec la MÊME garde de lecture que les données : sur un lien `otp_lecture`, seul le
 * navigateur vérifié (preuve ASEC23 en en-tête `X-Proposition-Preuve`) la reçoit. Le cookie
 * httpOnly `tq_prop_preuve` vivant sur le site, une `<img>` pointée sur `api.taqinor.ma`
 * rendait 403 au client vérifié : la page pointe ici, et ce handler relaie la preuve puis
 * renvoie les octets tels quels (statut, corps, content-type). Aucun comptage de vue côté ERP.
 * La preuve n'est jamais journalisée ni renvoyée. Amont injoignable → 502 JSON.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { crossSiteRejection, isSameOriginRequest } from '../../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../../lib/rateLimit';
import { jsonResponse as json, relayBinaire, resolveApiBase } from '../_proxy';
import { entetePreuve } from '../_apiBase';

/** URL ERP de l'affiche (même chemin que `roof_image_url` servi par l'ERP). */
function afficheToitureEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/roof-image/`;
}

export const GET: APIRoute = async ({ params, request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();
  // Une page charge l'affiche une ou deux fois (héros + chapitre) : borne large.
  const rl = rateLimit(`proposition-toiture:${clientIpFromRequest(request)}`, { limit: 60, windowMs: 60_000 });
  if (!rl.allowed) return json({ ok: false, status: 429 }, 429, { 'retry-after': String(rl.retryAfterSec) });

  const token = (params.token ?? '').trim();
  if (!token) return json({ ok: false, status: 400, detail: 'Lien de proposition manquant.' }, 400);

  const relais = await relayBinaire(afficheToitureEndpoint(resolveApiBase(), token), {
    method: 'GET',
    headers: { accept: 'image/*', ...entetePreuve(request) }, // ASEC53 — preuve de CE navigateur.
    signal: AbortSignal.timeout(12_000),
  });
  return relais ?? json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
};

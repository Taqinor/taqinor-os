/**
 * GET /api/proposition-pdf/<token>[?variante=sans|avec|les_deux] — relais SAME-ORIGIN du PDF
 * de la proposition (ASEC53, D-ASEC-53-RELAIS, 29/10/2026).
 *
 * Sur un lien `otp_lecture`, l'ERP n'ouvre le flux `/pdf/` qu'au navigateur VÉRIFIÉ (preuve
 * ASEC23 en en-tête `X-Proposition-Preuve`) ; ce cookie httpOnly (`tq_prop_preuve`) vit sur le
 * site, jamais sur `api.taqinor.ma` : un lien direct vers l'ERP rendait 403 au client vérifié.
 * Ce handler relaie donc vers `{API_BASE}/api/django/ventes/proposal/<token>/pdf/` avec la
 * preuve, et renvoie le flux tel quel (statut, corps, content-type, content-disposition).
 * Couvre aussi l'exemplaire SIGNÉ : l'ERP sert le PDF figé d'un devis accepté sur ce même `/pdf/`.
 *
 * Comme le lien direct d'avant, l'ERP compte l'ouverture du devis : l'User-Agent, l'IP du
 * VISITEUR et les marqueurs d'appareil d'équipe sont relayés (même patron que `proposition-vu`).
 * La preuve n'est jamais journalisée, jamais renvoyée, jamais dans une URL. Amont injoignable →
 * 502 JSON (même contrat que les autres proxys).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { proposalPdfEndpoint } from '../../../lib/proposition';
import { crossSiteRejection, isSameOriginRequest } from '../../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../../lib/rateLimit';
import { isPlausibleUuid, lireCookie } from '../../../lib/visite';
import { jsonResponse as json, relayBinaire, resolveApiBase } from '../_proxy';
import { entetePreuve, entetesIpVisiteur } from '../_apiBase';

/** Liste blanche de `?variante=` (la même que côté ERP, qui retombe sur le complet sinon). */
const VARIANTES = new Set(['sans', 'avec', 'les_deux']);

export const GET: APIRoute = async ({ params, request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();
  const ip = clientIpFromRequest(request);
  const rl = rateLimit(`proposition-pdf:${ip}`, { limit: 20, windowMs: 60_000 });
  if (!rl.allowed) return json({ ok: false, status: 429 }, 429, { 'retry-after': String(rl.retryAfterSec) });

  const token = (params.token ?? '').trim();
  if (!token) return json({ ok: false, status: 400, detail: 'Lien de proposition manquant.' }, 400);
  const variante = new URL(request.url).searchParams.get('variante') ?? '';
  const cible = proposalPdfEndpoint(resolveApiBase(), token) + (VARIANTES.has(variante) ? `?variante=${variante}` : '');

  const cookies = request.headers.get('cookie') ?? '';
  const appareil = lireCookie(cookies, 'tq_appareil');
  const ua = request.headers.get('user-agent') || '';
  const relais = await relayBinaire(cible, {
    method: 'GET',
    headers: {
      accept: 'application/pdf, application/json',
      ...entetesIpVisiteur(ip),
      ...(ua ? { 'user-agent': ua } : {}),
      ...(lireCookie(cookies, 'tq_equipe') === '1' ? { 'X-Equipe-Appareil': '1' } : {}),
      ...(isPlausibleUuid(appareil) ? { 'X-Appareil-Id': appareil as string } : {}),
      ...entetePreuve(cookies), // ASEC53 — preuve OTP de lecture de CE navigateur.
    },
    signal: AbortSignal.timeout(30_000),
  });
  return relais ?? json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
};

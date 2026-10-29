/**
 * POST /api/proposition-virement — proxy SAME-ORIGIN de « J'ai effectué le virement » (ADEV53).
 *
 * Le navigateur poste ici { token } ; ce handler relaie vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/virement/` (QX33be : note chatter + notification
 * du conseiller, AUCUN statut changé, aucun Paiement créé ; idempotent par heure ; 403
 * `otp_required` si la lecture du lien exige un code non saisi ; 403 sur un aperçu interne).
 * Même convention que `proposition-option.ts` : garde same-origin, rate-limit dédié, IP du client.
 * Corps amont vide : le jeton authentifie, rien d'autre n'est relayé.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { normalizeVirementResponse, virementEndpoint } from '../../lib/paiementAcceptation';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest } from '../../lib/rateLimit';
import { corpsAvecToken, jsonResponse as json, relayJson, resolveApiBase } from './_proxy';
import { entetesIpVisiteur, entetesJsonPreuve } from './_apiBase';

export const POST: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const garde = await corpsAvecToken(request, 'proposition-virement', 10);
  if (garde instanceof Response) return garde;
  const { body, token } = garde;

  const clientIp = clientIpFromRequest(request);
  const ip = clientIp && clientIp !== 'unknown' ? clientIp : '';
  const relais = await relayJson(virementEndpoint(resolveApiBase(), token), {
    method: 'POST',
    headers: { ...entetesJsonPreuve(request), ...entetesIpVisiteur(ip) }, // ASEC53 — preuve de CE navigateur.
    body: '{}',
  });
  if (!relais) {
    return json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }
  const status = relais.status >= 200 && relais.status < 600 ? relais.status : 502;
  return json(normalizeVirementResponse(relais.status, relais.payload), status);
};

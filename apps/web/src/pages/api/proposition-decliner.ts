/**
 * POST /api/proposition-decliner — proxy SAME-ORIGIN de « Décliner / demander un délai » (ADEV98).
 *
 * Le navigateur poste ici `{ token, motif, texte? }` ; ce handler relaie `{ motif, texte }`
 * (motif FERMÉ, contrôlé par `corpsDeclin`) vers
 * `{API_BASE}/api/django/ventes/proposal/<token>/decliner/` : l'ERP consigne le motif au
 * chatter du devis et du lead et prévient le conseiller — AUCUN statut ne change. Même
 * convention que `proposition-virement.ts` : garde same-origin, rate-limit dédié, IP du
 * client ; un amont injoignable ne devient JAMAIS `ok: true` (502).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { corpsDeclin, declinerEndpoint } from '../../lib/propositionSignaux';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest } from '../../lib/rateLimit';
import { corpsAvecToken, jsonResponse as json, relayJson, resolveApiBase } from './_proxy';
import { entetePreuve, entetesIpVisiteur } from './_apiBase';

export const POST: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  const garde = await corpsAvecToken(request, 'proposition-decliner', 10);
  if (garde instanceof Response) return garde;
  const { body, token } = garde;

  const corps = corpsDeclin(body.motif, body.texte);
  if (!corps) return json({ ok: false, status: 400, detail: 'Choisissez un motif.' }, 400);

  const clientIp = clientIpFromRequest(request);
  const ip = clientIp && clientIp !== 'unknown' ? clientIp : '';
  const relais = await relayJson(declinerEndpoint(resolveApiBase(), token), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      ...entetesIpVisiteur(ip),
      ...entetePreuve(request), // ASEC53 — preuve OTP de lecture de CE navigateur.
    },
    body: JSON.stringify(corps),
  });
  if (!relais) {
    return json({ ok: false, status: 502, detail: 'Service momentanément indisponible. Veuillez réessayer.' }, 502);
  }
  const status = relais.status >= 200 && relais.status < 600 ? relais.status : 502;
  const payload = (relais.payload ?? {}) as { detail?: unknown; already_sent?: unknown };
  return json(
    {
      ok: status >= 200 && status < 300,
      status,
      detail: typeof payload.detail === 'string' ? payload.detail : '',
      ...(payload.already_sent === true ? { already_sent: true } : {}),
    },
    status,
  );
};

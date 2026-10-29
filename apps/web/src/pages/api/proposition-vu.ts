/**
 * POST /api/proposition-vu — proxy SAME-ORIGIN de la balise « proposition lue » (ADEV98).
 *
 * La page poste ici `{ token }` après 3 s de visibilité (`lib/propositionSignaux.ts`) ; ce
 * handler relaie vers `{API_BASE}/api/django/ventes/proposal/<token>/vu/`, qui compte la
 * lecture HUMAINE (compteur, note chatter, notification au conseiller) — le rendu serveur de
 * la page n'est plus qu'un aperçu (les scanners de liens des messageries le déclenchent).
 *
 * L'ERP doit pouvoir écarter robots et appareils d'équipe exactement comme sur la lecture :
 * l'User-Agent et l'IP du VISITEUR sont relayés, ainsi que les marqueurs d'appareil d'équipe
 * (`tq_equipe` → `X-Equipe-Appareil`, `tq_appareil` → `X-Appareil-Id`), comme le fait le
 * rendu SSR de `/proposition`. Best-effort : 204 quand l'ERP a répondu, 202 `ok: false`
 * sinon (un amont en panne n'est jamais un succès), jamais bloquant pour la page.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { vuEndpoint } from '../../lib/propositionSignaux';
import { crossSiteRejection, isSameOriginRequest } from '../../lib/lead';
import { clientIpFromRequest } from '../../lib/rateLimit';
import { isPlausibleUuid, lireCookie } from '../../lib/visite';
import { corpsAvecToken, jsonResponse as json, relayJson, resolveApiBase } from './_proxy';
import { entetePreuve, entetesIpVisiteur } from './_apiBase';

export const POST: APIRoute = async ({ request }) => {
  if (!isSameOriginRequest(request)) return crossSiteRejection();
  const garde = await corpsAvecToken(request, 'proposition-vu', 20);
  if (garde instanceof Response) return garde;

  const ip = clientIpFromRequest(request);
  const cookies = request.headers.get('cookie') ?? '';
  const appareil = lireCookie(cookies, 'tq_appareil');
  const ua = request.headers.get('user-agent') || '';
  const relais = await relayJson(vuEndpoint(resolveApiBase(), garde.token), {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
      ...entetesIpVisiteur(ip),
      ...(ua ? { 'user-agent': ua } : {}),
      ...(lireCookie(cookies, 'tq_equipe') === '1' ? { 'X-Equipe-Appareil': '1' } : {}),
      ...(isPlausibleUuid(appareil) ? { 'X-Appareil-Id': appareil as string } : {}),
      ...entetePreuve(cookies), // ASEC53 — preuve OTP de lecture de CE navigateur.
    },
    body: '{}',
    signal: AbortSignal.timeout(8000),
  });
  // 204 est un « null body status » : jamais de corps (runtime Workers).
  if (relais && relais.status >= 200 && relais.status < 500) return new Response(null, { status: 204 });
  return json({ ok: false, sent: false }, 202);
};

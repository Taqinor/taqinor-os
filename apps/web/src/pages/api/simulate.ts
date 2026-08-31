/**
 * POST /api/simulate — unique point d'entrée du formulaire.
 * Proxy serveur : le navigateur n'appelle jamais l'API de simulation
 * directement (pas de CORS, URL swappable via SIMULATOR_API_URL).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  adsConsentFromBody,
  buildLeadRecord,
  crossSiteRejection,
  fireCapi,
  forwardLead,
  isHoneypotTripped,
  isSameOriginRequest,
  redactLeadForLog,
  runSimulation,
  validateLead,
  type LeadEnv,
} from '../../lib/lead';
import { leadWhatsappText, whatsappLink } from '../../lib/whatsapp';
import { NAP, WHATSAPP_LEADS } from '../../lib/nap';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout
  // traitement (même garde-fou que les autres proxies same-origin).
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // ERR112 — garde-fou anti-spam (best-effort, sans dépendance ni secret).
  // Limite les POST par IP : un humain ne soumet pas 8 fois par minute, un
  // script de spam si. Voir src/lib/rateLimit.ts pour la limitation assumée.
  const rl = rateLimit(`simulate:${clientIpFromRequest(request)}`);
  if (!rl.allowed) {
    return json({ ok: false, errors: { rate: 'Trop de tentatives, réessayez dans un instant.' } }, 429, {
      'retry-after': String(rl.retryAfterSec),
    });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, errors: { body: 'JSON invalide' } }, 400);
  }

  // QJW15 — GARDE HONEYPOT, enfin réelle sur le formulaire LIVE. Elle
  // n'existait que sur /api/preview-lead et /api/capture-lead, et n'y attrapait
  // rien : AUCUN des deux composants diagnostic ne rendait le champ
  // `website_url` (QJW15 les corrige tous les deux). Même contrat que les deux
  // autres endpoints : rejet EN SILENCE avec une réponse de succès factice —
  // jamais un signal au bot sur ce qui l'a trahi.
  if (isHoneypotTripped(body)) return json({ ok: true, qualified: false });

  const validation = validateLead(body);
  if (!validation.ok) return json({ ok: false, errors: validation.errors }, 400);
  const lead = validation.lead;

  // QJW14 — signal de consentement publicitaire transmis par le formulaire
  // (`tq_consent`, ConsentBanner.astro). Il ne gate QUE le beacon Meta ; le
  // lead lui-même part au CRM quoi qu'il arrive.
  const adsConsent = adsConsentFromBody(body);

  const env = (cf.env ?? {}) as LeadEnv;
  const band = await runSimulation(lead, env, fetch);
  const page = request.headers.get('referer');
  const record = buildLeadRecord(lead, band, new Date(), page);

  // Transfert CRM + CAPI en arrière-plan quand waitUntil est disponible,
  // sinon awaité (les deux tolèrent pannes et absence de configuration).
  const background = (async () => {
    const fw = await forwardLead(record, env, fetch);
    if (!fw.delivered && record.qualified) {
      // ERR32 : ne JAMAIS journaliser la PII du lead (nom/téléphone/ville/
      // consentement). On ne loggue qu'un diagnostic rédacté (id corrélable
      // haché, indicateurs, raison de l'échec) — jamais JSON.stringify(record).
      console.log(
        `[lead] non transmis au CRM (${fw.reason}) — lead qualifié:`,
        JSON.stringify(redactLeadForLog(record)),
      );
    }
    const capi = await fireCapi(record, env, fetch, { adsConsent });
    if (!capi.sent && record.qualified && capi.reason !== 'consent-denied') {
      console.log('[capi] non envoyé (service absent ou injoignable)');
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  const waNumber = env.WHATSAPP_NUMBER?.trim() || WHATSAPP_LEADS;
  const whatsappUrl = whatsappLink(
    waNumber,
    leadWhatsappText({
      fullName: lead.fullName,
      // WJ97 (lib/lead.ts) — `city` est désormais optionnel dans ValidatedLead
      // (chemin rappel rapide /contact) ; ce flux (simulate) ne l'utilise
      // jamais sans ville (validateLead l'exige toujours ici), `?? ''` ne fait
      // que satisfaire le type élargi, jamais un comportement différent.
      city: lead.city ?? '',
      kwcLabel: band.kwcLabel,
      paybackLabel: band.paybackLabel,
    }),
  );

  return json({
    ok: true,
    qualified: record.qualified,
    band: { kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel },
    whatsappUrl,
  });
};

/**
 * POST /api/preview-lead — endpoint PRIVÉ du diagnostic enrichi (preview).
 *
 * Miroir strict de /api/simulate : même validation, même simulation ROI,
 * même seuil 1 000 MAD, même transfert CRM, même CAPI, même lien WhatsApp.
 * La SEULE différence : si l'utilisateur a rempli les champs FACULTATIFS
 * (type d'alimentation, surface de toiture, orientation), ils sont ajoutés
 * tels quels à l'enregistrement transmis au CRM, dans la MÊME soumission.
 *
 * Sans champ facultatif, l'enregistrement transmis est rigoureusement
 * identique à celui de /api/simulate (garde-fou : tests/preview.test.ts +
 * tests/enrichment.test.ts). Cet endpoint existe à part pour que la route
 * publique /api/simulate et le formulaire live restent intacts jusqu'à
 * promotion.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  buildLeadRecord,
  crossSiteRejection,
  fireCapi,
  forwardLead,
  isSameOriginRequest,
  redactLeadForLog,
  runSimulation,
  validateLead,
  type LeadEnv,
} from '../../lib/lead';
import { cleanEnrichment, hasEnrichment } from '../../lib/enrichment';
import { leadWhatsappText, whatsappLink } from '../../lib/whatsapp';
import { WHATSAPP_LEADS } from '../../lib/nap';
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

  // ERR112 — même garde-fou anti-spam que /api/simulate (miroir strict),
  // bucket distinct par endpoint. Best-effort, sans dépendance ni secret.
  const rl = rateLimit(`preview-lead:${clientIpFromRequest(request)}`);
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

  const validation = validateLead(body);
  if (!validation.ok) return json({ ok: false, errors: validation.errors }, 400);
  const lead = validation.lead;

  const env = (cf.env ?? {}) as LeadEnv;
  const band = await runSimulation(lead, env, fetch);
  const page = request.headers.get('referer');
  const baseRecord = buildLeadRecord(lead, band, new Date(), page);

  // Champs facultatifs : ajoutés UNIQUEMENT s'ils sont remplis. Sans eux,
  // `record` est identique octet pour octet à celui de /api/simulate.
  const enrichment = cleanEnrichment(body);
  const record = hasEnrichment(enrichment) ? { ...baseRecord, enrichment } : baseRecord;

  const background = (async () => {
    const fw = await forwardLead(record, env, fetch);
    if (!fw.delivered && baseRecord.qualified) {
      // ERR32 : aucune PII dans les logs (nom/téléphone/ville/consentement).
      // Diagnostic rédacté seulement (id haché, indicateurs, raison) — l'objet
      // `record` enrichi n'est jamais sérialisé tel quel.
      console.log(
        `[lead] non transmis au CRM (${fw.reason}) — lead qualifié:`,
        JSON.stringify(redactLeadForLog(record)),
      );
    }
    // CAPI inchangé : l'événement publicitaire ne porte jamais les champs
    // facultatifs (signal propre, identique à la production).
    const capi = await fireCapi(baseRecord, env, fetch);
    if (!capi.sent && baseRecord.qualified) {
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
      city: lead.city,
      kwcLabel: band.kwcLabel,
      paybackLabel: band.paybackLabel,
    }),
  );

  return json({
    ok: true,
    qualified: baseRecord.qualified,
    band: { kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel },
    whatsappUrl,
  });
};

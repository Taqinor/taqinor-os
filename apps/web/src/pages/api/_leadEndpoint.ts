/**
 * ENF19 — socle commun des endpoints de capture de lead (`/api/simulate`,
 * `/api/preview-lead`, `/api/capture-lead`) : une seule copie de la garde
 * d'entrée (origine, rate-limit, corps JSON), du lien WhatsApp et du
 * transfert CRM + CAPI en arrière-plan. Aucun comportement propre à un
 * endpoint n'est ici : chacun garde sa validation, son honeypot et son record.
 */
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
import { WHATSAPP_LEADS } from '../../lib/nap';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

export function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

/** Origine + rate-limit (bucket propre à l'endpoint) + corps JSON + honeypot. */
export async function ouvrirRequeteLead(
  request: Request,
  bucket: string,
): Promise<{ response: Response } | { body: unknown }> {
  // W317 — Origin/Sec-Fetch-Site : refuse un POST cross-site forgé avant tout traitement.
  if (!isSameOriginRequest(request)) return { response: crossSiteRejection() };

  // ERR112 — garde-fou anti-spam best-effort, bucket distinct par endpoint.
  const rl = rateLimit(`${bucket}:${clientIpFromRequest(request)}`);
  if (!rl.allowed) {
    return {
      response: json({ ok: false, errors: { rate: 'Trop de tentatives, réessayez dans un instant.' } }, 429, {
        'retry-after': String(rl.retryAfterSec),
      }),
    };
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return { response: json({ ok: false, errors: { body: 'JSON invalide' } }, 400) };
  }

  // Honeypot (W317/WB32/QJW15) : un champ caché que seul un bot remplit. Rejeté EN SILENCE avec
  // une réponse de succès factice — jamais un signal au bot sur ce qui l'a trahi.
  if (isHoneypotTripped(body)) return { response: json({ ok: true, qualified: false }) };
  return { body };
}

/** Lien WhatsApp « étude » du lead ; `env` porte le numéro surchargeable. */
export function whatsappUrlDuLead(
  env: LeadEnv,
  lead: { fullName: string; city?: string },
  band: { kwcLabel: string; paybackLabel: string },
): string {
  const waNumber = env.WHATSAPP_NUMBER?.trim() || WHATSAPP_LEADS;
  return whatsappLink(
    waNumber,
    leadWhatsappText({
      fullName: lead.fullName,
      // WJ97 — `city` est optionnel dans ValidatedLead (rappel rapide /contact) ;
      // `?? ''` ne fait que satisfaire le type élargi.
      city: lead.city ?? '',
      kwcLabel: band.kwcLabel,
      paybackLabel: band.paybackLabel,
    }),
  );
}

/** Exécute `tache` via waitUntil quand disponible, sinon l'attend. */
export async function enArrierePlan(tache: Promise<unknown>): Promise<void> {
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(tache);
  else await tache;
}

type RecordCrm = Parameters<typeof forwardLead>[0];

/**
 * Transfert CRM puis CAPI (tolérants aux pannes). `recordCrm` part au CRM,
 * `recordCapi` au CAPI (identiques sauf enrichissement). Aucune PII dans les logs (ERR32).
 */
export async function transfererLead(
  recordCrm: RecordCrm,
  recordCapi: Parameters<typeof fireCapi>[0],
  env: LeadEnv,
  adsConsent: NonNullable<Parameters<typeof fireCapi>[3]>['adsConsent'],
): Promise<void> {
  const fw = await forwardLead(recordCrm, env, fetch);
  if (!fw.delivered && recordCapi.qualified) {
    console.log(
      `[lead] non transmis au CRM (${fw.reason}) — lead qualifié:`,
      JSON.stringify(redactLeadForLog(recordCrm)),
    );
  }
  const capi = await fireCapi(recordCapi, env, fetch, { adsConsent });
  if (!capi.sent && recordCapi.qualified && capi.reason !== 'consent-denied') {
    console.log('[capi] non envoyé (service absent ou injoignable)');
  }
}

/**
 * Validation + simulation + record de base (après le honeypot, propre à chaque
 * endpoint). `adsConsent` ne gate QUE le beacon Meta (QJW14), jamais le lead.
 */
export async function preparerLead(request: Request, body: unknown) {
  const validation = validateLead(body);
  if (!validation.ok) return { response: json({ ok: false, errors: validation.errors }, 400) };
  const lead = validation.lead;
  const adsConsent = adsConsentFromBody(body);
  const env = (cf.env ?? {}) as LeadEnv;
  const band = await runSimulation(lead, env, fetch);
  const page = request.headers.get('referer');
  const baseRecord = buildLeadRecord(lead, band, new Date(), page);
  return { lead, adsConsent, env, band, baseRecord };
}

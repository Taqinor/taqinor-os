/**
 * POST /api/simulate — unique point d'entrée du formulaire.
 * Proxy serveur : le navigateur n'appelle jamais l'API de simulation
 * directement (pas de CORS, URL swappable via SIMULATOR_API_URL).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  buildLeadRecord,
  fireCapi,
  forwardLead,
  runSimulation,
  validateLead,
  type LeadEnv,
} from '../../lib/lead';
import { leadWhatsappText, whatsappLink } from '../../lib/whatsapp';
import { NAP } from '../../lib/nap';

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

export const POST: APIRoute = async ({ request }) => {
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
  const record = buildLeadRecord(lead, band, new Date(), page);

  // Transfert CRM + CAPI en arrière-plan quand waitUntil est disponible,
  // sinon awaité (les deux tolèrent pannes et absence de configuration).
  const background = (async () => {
    const fw = await forwardLead(record, env, fetch);
    if (!fw.delivered && record.qualified) {
      console.log(`[lead] non transmis au CRM (${fw.reason}) — lead qualifié:`, JSON.stringify(record));
    }
    const capi = await fireCapi(record, env, fetch);
    if (!capi.sent && record.qualified) {
      console.log('[capi] non envoyé (service absent ou injoignable)');
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  const waNumber = env.WHATSAPP_NUMBER?.trim() || NAP.whatsapp;
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
    qualified: record.qualified,
    band: { kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel },
    whatsappUrl,
  });
};

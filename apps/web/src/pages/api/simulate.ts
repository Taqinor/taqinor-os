/**
 * POST /api/simulate — unique point d'entrée du formulaire.
 * Proxy serveur : le navigateur n'appelle jamais l'API de simulation
 * directement (pas de CORS, URL swappable via SIMULATOR_API_URL).
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import { enArrierePlan, json, ouvrirRequeteLead, preparerLead, transfererLead, whatsappUrlDuLead } from './_leadEndpoint';

export const POST: APIRoute = async ({ request }) => {
  const ouverture = await ouvrirRequeteLead(request, 'simulate');
  if ('response' in ouverture) return ouverture.response;
  const body = ouverture.body;

  const prep = await preparerLead(request, body);
  if ('response' in prep) return prep.response;
  const { lead, adsConsent, env, band, baseRecord } = prep;
  const record = baseRecord;

  // Transfert CRM + CAPI en arrière-plan quand waitUntil est disponible,
  // sinon awaité (les deux tolèrent pannes et absence de configuration).
  await enArrierePlan(transfererLead(record, record, env, adsConsent));

  const whatsappUrl = whatsappUrlDuLead(env, lead, band);

  return json({
    ok: true,
    qualified: record.qualified,
    band: { kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel },
    whatsappUrl,
  });
};

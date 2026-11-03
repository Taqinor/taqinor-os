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
import { cleanEnrichment, hasEnrichment } from '../../lib/enrichment';
import { enArrierePlan, json, ouvrirRequeteLead, preparerLead, transfererLead, whatsappUrlDuLead } from './_leadEndpoint';

export const POST: APIRoute = async ({ request }) => {
  const ouverture = await ouvrirRequeteLead(request, 'preview-lead');
  if ('response' in ouverture) return ouverture.response;
  const body = ouverture.body;

  const prep = await preparerLead(request, body);
  if ('response' in prep) return prep.response;
  const { lead, adsConsent, env, band, baseRecord } = prep;

  // Champs facultatifs : ajoutés UNIQUEMENT s'ils sont remplis. Sans eux,
  // `record` est identique octet pour octet à celui de /api/simulate.
  const enrichment = cleanEnrichment(body);
  const record = hasEnrichment(enrichment) ? { ...baseRecord, enrichment } : baseRecord;

  await enArrierePlan(transfererLead(record, baseRecord, env, adsConsent));

  const whatsappUrl = whatsappUrlDuLead(env, lead, band);

  return json({
    ok: true,
    qualified: baseRecord.qualified,
    band: { kwcLabel: band.kwcLabel, paybackLabel: band.paybackLabel },
    whatsappUrl,
  });
};

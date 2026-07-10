/**
 * POST /api/capture-lead — endpoint de la CAPTURE CLIENT (page /devis/mon-toit).
 *
 * W112. Miroir de la structure de /api/preview-lead : même rate-limit anti-spam
 * (bucket distinct), même validation (validateLead), même construction
 * (buildLeadRecord), même transfert CRM tolérant (forwardLead) — mais SANS toucher
 * /api/preview-lead. La SEULE différence : on joint au lead transmis le REPÈRE du
 * toit posé par le client (`roofPoint`), le contour optionnel (`roofOutline`) et la
 * consommation (`billKwh`) — exactement les champs supplémentaires que le récepteur
 * Django accepte. L'étude solaire (panneaux/optimiseur) se fait ENSUITE côté Meriem.
 *
 * Comme /api/preview-lead, on ne BLOQUE jamais l'UX sur une panne webhook (transfert
 * en arrière-plan, même tolérance) et on ne journalise AUCUNE PII.
 */
export const prerender = false;

import type { APIRoute } from 'astro';
import * as cf from 'cloudflare:workers';
import {
  buildLeadRecord,
  crossSiteRejection,
  fireCapi,
  forwardLead,
  isHoneypotTripped,
  isSameOriginRequest,
  redactLeadForLog,
  runSimulation,
  trackForwardLeadOutcome,
  validateLead,
  type LeadEnv,
} from '../../lib/lead';
import { clientIpFromRequest, rateLimit } from '../../lib/rateLimit';

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

export const POST: APIRoute = async ({ request }) => {
  // W317 — Origin/Sec-Fetch-Site : « proxy same-origin » n'était jusqu'ici que
  // de la documentation, jamais vérifiée (le rate-limit par IP est best-effort
  // par isolate, pas un blocage). Un POST cross-site forgé est refusé (403)
  // avant même le rate-limit.
  if (!isSameOriginRequest(request)) return crossSiteRejection();

  // Même garde-fou anti-spam que /api/preview-lead (bucket distinct par endpoint).
  const rl = rateLimit(`capture-lead:${clientIpFromRequest(request)}`);
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

  // W317 — honeypot : un champ caché que seul un bot remplit. Rejeté en
  // silence côté serveur avec une réponse de succès factice (jamais un signal
  // que révélerait au bot QUEL champ l'a trahi) — le contrat webhook existant
  // reste inchangé, ce lead n'est simplement jamais transmis.
  if (isHoneypotTripped(body)) return json({ ok: true, qualified: false });

  const validation = validateLead(body);
  if (!validation.ok) return json({ ok: false, errors: validation.errors }, 400);
  const lead = validation.lead;

  const env = (cf.env ?? {}) as LeadEnv;
  const band = await runSimulation(lead, env, fetch);
  const page = request.headers.get('referer');
  const baseRecord = buildLeadRecord(lead, band, new Date(), page);

  // WJ30 — les champs supplémentaires (repère, contour, consommation, profil
  // énergétique W1/W3, adresse/GPS, e-mail, mode, langue…) sont désormais validés
  // et JOINTS par validateLead (lib/lead.ts, validateOptionalFields) : baseRecord
  // les porte déjà, uniquement quand ils sont valides. La SEULE responsabilité
  // restante ici est le contrat W3 explicite : `factureEte` (number|null) et
  // `eteDifferente` sont TOUJOURS émis pour signaler « été identique » quand
  // eteDifferente est faux — le récepteur peut s'y fier.
  const eteDifferente = lead.eteDifferente === true;
  const record = {
    ...baseRecord,
    factureEte: eteDifferente ? lead.factureEte ?? null : null,
    eteDifferente,
  };

  const background = (async () => {
    const fw = await forwardLead(record, env, fetch);
    if (!fw.delivered && baseRecord.qualified) {
      // Aucune PII dans les logs (id haché, indicateurs, raison) — comme preview-lead.
      console.log(
        `[capture-lead] non transmis au CRM (${fw.reason}) — lead qualifié:`,
        JSON.stringify(redactLeadForLog(baseRecord)),
      );
    }
    // WJ66 — visibilité de panne de livraison : au-delà du seuil d'échecs
    // CONSÉCUTIFS (webhook configuré, lead qualifié, mais la livraison échoue
    // à répétition), une ligne d'ALERTE distincte et grep-able (`[capture-lead][ALERT]`)
    // signale une panne CRM probable — jusqu'ici un tel silence pouvait durer
    // des jours sans que personne ne soit notifié. Best-effort, en mémoire par
    // isolat (cf. trackForwardLeadOutcome) : jamais bloquant pour le visiteur.
    const { shouldAlert, streak } = trackForwardLeadOutcome(fw.delivered, fw.reason);
    if (shouldAlert) {
      console.error(
        `[capture-lead][ALERT] ${streak} échecs de livraison CRM consécutifs (dernier motif: ${fw.reason}) — vérifier LEAD_WEBHOOK_URL / le récepteur taqinor-os.`,
      );
    }
    // WJ110 — ce point d'entrée (CTA principal /devis/mon-toit) ne déclenchait
    // JAMAIS le Meta CAPI, contrairement aux flux secondaires (simulate,
    // preview-lead) : Meta optimisait donc les campagnes sur une tranche non
    // représentative du trafic. Même appel, même tolérance de panne (silencieux,
    // jamais bloquant), fireCapi se gate déjà lui-même sur `record.qualified`.
    const capi = await fireCapi(record, env, fetch);
    if (!capi.sent && baseRecord.qualified) {
      console.log('[capi] non envoyé (service absent ou injoignable)');
    }
  })();
  const waitUntil = (cf as { waitUntil?: (p: Promise<unknown>) => void }).waitUntil;
  if (typeof waitUntil === 'function') waitUntil(background);
  else await background;

  // Jamais bloquer l'UX sur le webhook (même tolérance que le flux existant).
  return json({ ok: true, qualified: baseRecord.qualified });
};

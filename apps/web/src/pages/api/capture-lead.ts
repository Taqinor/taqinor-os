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
import {
  fireCapi,
  forwardLead,
  redactLeadForLog,
  trackForwardLeadOutcome,
} from '../../lib/lead';
import { enArrierePlan, json, ouvrirRequeteLead, preparerLead } from './_leadEndpoint';

export const POST: APIRoute = async ({ request }) => {
  const ouverture = await ouvrirRequeteLead(request, 'capture-lead');
  if ('response' in ouverture) return ouverture.response;
  const body = ouverture.body;

  // QJW22 — CETTE LIGNE EST LA LISTE BLANCHE. Ce n'est PAS le corps construit
  // par le registre du tunnel qui part au webhook, mais `validation.lead` :
  // une clé correctement déclarée dans `src/lib/tunnel/champs.ts` mais jamais
  // ajoutée à la main dans `validateOptionalFields` (lib/lead.ts) est
  // SILENCIEUSEMENT JETÉE ici, sans une ligne de log. Les tests de parité
  // assertaient sur le corps d'AVANT : ils ne pouvaient structurellement pas le
  // voir. La garde d'appariement registre ↔ liste blanche vit désormais dans
  // tests/tunnelParite.test.ts (describe « QJW22 »), et les assertions de
  // parité portent sur le corps POST-liste-blanche — celui qui part vraiment.
  // Seule exception voulue : le honeypot `website_url`, jugé côté serveur et
  // qui ne doit JAMAIS atteindre le CRM.
  const prep = await preparerLead(request, body);
  if ('response' in prep) return prep.response;
  const { lead, adsConsent, env, band, baseRecord } = prep;

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
    // Les leads SOUS LE SEUIL partent AUSSI au CRM, avec leur `qualified: false`
    // intact. Jusqu'ici `forwardLead` les court-circuitait : un visiteur qui
    // avait repéré son toit, donné sa ville, son profil et son créneau de visite
    // disparaissait entièrement dès que sa facture passait sous 1 000 MAD. Le
    // récepteur accepte le drapeau et fait le tri lui-même ; ce que voit le
    // visiteur (`json.qualified`) et le Meta CAPI (qui se gate seul sur
    // `record.qualified`, cf. fireCapi) sont INCHANGÉS.
    const fw = await forwardLead(record, env, fetch, { includeUnqualified: true });
    if (!fw.delivered) {
      // Aucune PII dans les logs (id haché, indicateurs, raison) — comme preview-lead.
      console.log(
        `[capture-lead] non transmis au CRM (${fw.reason}) — lead:`,
        JSON.stringify(redactLeadForLog(baseRecord)),
      );
    }
    // WJ66 — visibilité de panne de livraison : au-delà du seuil d'échecs
    // CONSÉCUTIFS (webhook configuré, lead qualifié, mais la livraison échoue
    // à répétition), une ligne d'ALERTE distincte et grep-able (`[capture-lead][ALERT]`)
    // signale une panne CRM probable — jusqu'ici un tel silence pouvait durer
    // des jours sans que personne ne soit notifié. Best-effort, en mémoire par
    // isolat (cf. trackForwardLeadOutcome) : jamais bloquant pour le visiteur.
    const { shouldAlert, streak } = trackForwardLeadOutcome(fw.delivered, fw.reason, import.meta.env.PROD === true);
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
    const capi = await fireCapi(record, env, fetch, { adsConsent });
    if (!capi.sent && baseRecord.qualified && !capi.reason) {
      console.log('[capi] non envoyé (service absent ou injoignable)');
    }
  })();
  await enArrierePlan(background);

  // Jamais bloquer l'UX sur le webhook (même tolérance que le flux existant).
  return json({ ok: true, qualified: baseRecord.qualified });
};

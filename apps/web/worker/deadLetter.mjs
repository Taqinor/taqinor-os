/**
 * QJR663 — LETTRE MORTE des leads du site (décision fondateur 01/10/2026).
 *
 * Quand `forwardLead` (src/lib/lead.ts) échoue encore après ses 3 tentatives
 * (QJR631), le record COMPLET est déposé dans un espace Cloudflare KV AVEC
 * EXPIRATION (liaison `LEADS_DLQ`) ; le Worker (worker/redirect-entry.mjs,
 * déclencheur cron de wrangler.jsonc) le renvoie ensuite à LEAD_WEBHOOK_URL et
 * supprime la clé au premier succès. Sans doublon : la clé KV ET l'en-tête du
 * record portent la MÊME `idempotencyKey` (garantie par QJR631).
 *
 * DÉGRADATION GRACIEUSE : sans liaison `LEADS_DLQ` (espace pas encore créé au
 * tableau de bord), tout est un no-op + UN avertissement sans donnée
 * personnelle — jamais une exception, jamais un blocage du visiteur.
 *
 * AUCUNE DONNÉE PERSONNELLE DANS LES LOGS : seulement des compteurs et des
 * motifs. Le KV contient nom/téléphone jusqu'au renvoi ou à l'expiration.
 *
 * Fichier .mjs sans dépendance : importé par lead.ts (stockage) ET copié dans
 * dist/server/ par le hook astro:build:done pour le gestionnaire planifié.
 */

/** Préfixe des clés KV (une clé = `lead:<idempotencyKey>`). */
export const DEAD_LETTER_PREFIX = 'lead:';

/** Durée de conservation : 7 jours, puis le KV efface seul (borne la PII stockée). */
export const DEAD_LETTER_TTL_SECONDS = 7 * 24 * 60 * 60;

/**
 * ADCG51 — lead REFUSÉ par le CRM en 4xx (secret faux, JSON refusé…) : ce n'est
 * pas une panne passagère, il n'expirerait qu'en silence alors que le visiteur a
 * reçu `ok: true`. Il est gardé SANS expiration sous ce préfixe distinct
 * (`lead-refuse:<idempotencyKey>`, statut en métadonnée) et chaque renvoi le
 * signale en ERREUR jusqu'à livraison.
 */
export const DEAD_LETTER_REFUSED_PREFIX = 'lead-refuse:';

/** Plafond de clés renvoyées par déclenchement (reste sous les limites de sous-requêtes). */
export const DEAD_LETTER_MAX_PER_RUN = 25;

let warnedMissingBinding = false;

/** Remet à zéro l'avertissement « liaison absente » (tests uniquement). */
export function resetDeadLetterWarning() {
  warnedMissingBinding = false;
}

function warnMissingBindingOnce(log) {
  if (warnedMissingBinding) return;
  warnedMissingBinding = true;
  log('[dead-letter] liaison KV LEADS_DLQ absente — lettre morte inactive (aucun lead conservé après échec).');
}

/**
 * Dépose le record complet. Retourne true si stocké ; jamais ne lève.
 * @param {{ put: Function } | undefined} kv  liaison LEADS_DLQ
 * @param {object} record  record complet (avec `idempotencyKey` non vide)
 * @param {number} [refusedStatus]  statut 4xx du refus du CRM (ADCG51) : sans expiration
 */
export async function storeDeadLetter(kv, record, log = console.warn, refusedStatus) {
  if (!kv || typeof kv.put !== 'function') {
    warnMissingBindingOnce(log);
    return false;
  }
  const key = record && typeof record.idempotencyKey === 'string' ? record.idempotencyKey.trim() : '';
  if (!key) return false;
  try {
    if (refusedStatus) {
      await kv.put(DEAD_LETTER_REFUSED_PREFIX + key, JSON.stringify(record), {
        metadata: { statut: refusedStatus },
      });
    } else {
      await kv.put(DEAD_LETTER_PREFIX + key, JSON.stringify(record), {
        expirationTtl: DEAD_LETTER_TTL_SECONDS,
      });
    }
    return true;
  } catch (e) {
    log(`[dead-letter] écriture KV impossible (${e instanceof Error ? e.name : 'erreur'}).`);
    return false;
  }
}

/**
 * Renvoie les leads en attente à LEAD_WEBHOOK_URL (UNE tentative par clé et par
 * déclenchement ; la suivante sera pour le prochain cron). Supprime la clé
 * seulement sur réponse 2xx. Retourne des compteurs, jamais de contenu.
 */
export async function resendDeadLetters(env, fetchFn = fetch, log = console.log, logError = console.error) {
  const kv = env && env.LEADS_DLQ;
  if (!kv || typeof kv.list !== 'function') {
    warnMissingBindingOnce(console.warn);
    return { skipped: true, found: 0, delivered: 0, failed: 0 };
  }
  const url = typeof env.LEAD_WEBHOOK_URL === 'string' ? env.LEAD_WEBHOOK_URL.trim() : '';
  if (!url) return { skipped: true, found: 0, delivered: 0, failed: 0 };

  const headers = { 'content-type': 'application/json' };
  const secret = typeof env.LEAD_WEBHOOK_SECRET === 'string' ? env.LEAD_WEBHOOK_SECRET.trim() : '';
  if (secret) headers['x-webhook-secret'] = secret;

  let found = 0;
  let delivered = 0;
  let failed = 0;
  const refusParStatut = new Map(); // ADCG51 : statut 4xx -> nombre de leads refusés
  let listing;
  let refuses;
  try {
    listing = await kv.list({ prefix: DEAD_LETTER_PREFIX, limit: DEAD_LETTER_MAX_PER_RUN });
    refuses = await kv.list({ prefix: DEAD_LETTER_REFUSED_PREFIX, limit: DEAD_LETTER_MAX_PER_RUN });
  } catch (e) {
    log(`[dead-letter] liste KV impossible (${e instanceof Error ? e.name : 'erreur'}).`);
    return { skipped: false, found: 0, delivered: 0, failed: 0 };
  }
  for (const { name } of [...(listing.keys || []), ...(refuses.keys || [])]) {
    found += 1;
    try {
      const body = await kv.get(name);
      if (!body) continue; // expirée entre-temps
      const res = await fetchFn(url, {
        method: 'POST',
        headers: { ...headers, 'x-webhook-timestamp': new Date().toISOString() },
        body,
        signal: AbortSignal.timeout(8000),
      });
      if (res.ok) {
        await kv.delete(name);
        delivered += 1;
      } else if (name.startsWith(DEAD_LETTER_REFUSED_PREFIX)
        // ADCG114 — un lead: refusé en 4xx (hors 429) AU RENVOI passe sous lead-refuse: sans
        // expiration ; l'ancienne clé n'est supprimée qu'une fois la nouvelle écrite.
        || (res.status >= 400 && res.status < 500 && res.status !== 429
          && (await storeDeadLetter(kv, JSON.parse(body), log, res.status)))) {
        if (!name.startsWith(DEAD_LETTER_REFUSED_PREFIX)) await kv.delete(name);
        refusParStatut.set(res.status, (refusParStatut.get(res.status) || 0) + 1);
      } else {
        failed += 1;
      }
    } catch {
      failed += 1;
    }
  }
  log(`[dead-letter] renvoi : ${found} en attente, ${delivered} livrés, ${failed} en échec.`);
  let refused = 0;
  for (const [statut, n] of refusParStatut) {
    refused += n;
    logError(`[dead-letter] ${n} lead(s) refusé(s) par le CRM (HTTP ${statut}), conservé(s) sans expiration`);
  }
  return refused
    ? { skipped: false, found, delivered, failed, refused }
    : { skipped: false, found, delivered, failed };
}

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
 */
export async function storeDeadLetter(kv, record, log = console.warn) {
  if (!kv || typeof kv.put !== 'function') {
    warnMissingBindingOnce(log);
    return false;
  }
  const key = record && typeof record.idempotencyKey === 'string' ? record.idempotencyKey.trim() : '';
  if (!key) return false;
  try {
    await kv.put(DEAD_LETTER_PREFIX + key, JSON.stringify(record), {
      expirationTtl: DEAD_LETTER_TTL_SECONDS,
    });
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
export async function resendDeadLetters(env, fetchFn = fetch, log = console.log) {
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
  let listing;
  try {
    listing = await kv.list({ prefix: DEAD_LETTER_PREFIX, limit: DEAD_LETTER_MAX_PER_RUN });
  } catch (e) {
    log(`[dead-letter] liste KV impossible (${e instanceof Error ? e.name : 'erreur'}).`);
    return { skipped: false, found: 0, delivered: 0, failed: 0 };
  }
  for (const { name } of listing.keys || []) {
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
      } else {
        failed += 1;
      }
    } catch {
      failed += 1;
    }
  }
  log(`[dead-letter] renvoi : ${found} en attente, ${delivered} livrés, ${failed} en échec.`);
  return { skipped: false, found, delivered, failed };
}

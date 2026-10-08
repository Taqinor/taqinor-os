/**
 * Reprise des demandes de rendez-vous non livrées (YBW54) — espace KV
 * FACULTATIF (YBWM3 : il n'existe que si Reda le crée et déclare sa durée au
 * registre des sous-traitants, `KV_REPRISE_DUREE_JOURS`).
 *
 * - On stocke le CORPS (chaîne JSON exacte, `idempotency_key` comprise), jamais
 *   la signature : chaque rejeu RE-SIGNE avec un `t` frais (la tolérance de
 *   l'ERP est de 300 s), et garde la MÊME `idempotency_key` → l'ERP répond
 *   `deja_recu` si la première tentative était finalement passée.
 * - Liaison absente = un avertissement UNE fois par isolat, jamais d'exception.
 * - Aucune donnée personnelle dans les journaux (codes et compteurs seulement).
 */

export const PREFIXE = 'rdv:';

/**
 * @typedef {{
 *   get(cle: string): Promise<string | null>,
 *   put(cle: string, valeur: string, options?: { expirationTtl?: number }): Promise<void>,
 *   delete(cle: string): Promise<void>,
 *   list(options?: { prefix?: string, limit?: number }): Promise<{ keys: { name: string }[] }>,
 * }} EspaceKv
 * @typedef {'livre' | 'definitif' | 'reessayer'} Issue
 * @typedef {{ warn: (ligne: string) => void }} Journal
 */

let averti = false;

/** Remet l'avertissement « liaison absente » à zéro (tests). */
export function reinitialiserAvertissement() {
  averti = false;
}

/**
 * Renvoie l'espace KV utilisable, ou `null` (liaison absente OU durée non
 * déclarée au registre) avec un avertissement unique.
 * @param {unknown} liaison
 * @param {number | null} dureeJours
 * @param {Journal} journal
 * @returns {EspaceKv | null}
 */
export function espaceReprise(liaison, dureeJours, journal) {
  const ok =
    !!liaison &&
    typeof liaison === 'object' &&
    typeof (/** @type {any} */ (liaison).put) === 'function' &&
    typeof (/** @type {any} */ (liaison).list) === 'function';
  if (ok && typeof dureeJours === 'number' && dureeJours > 0) return /** @type {EspaceKv} */ (liaison);
  if (!averti) {
    averti = true;
    journal.warn(
      ok
        ? '[rendez-vous] espace de reprise lié mais durée absente du registre (KV_REPRISE_DUREE_JOURS) : reprise désactivée'
        : '[rendez-vous] aucun espace de reprise (RDV_REPRISE) : une demande non livrée ne sera pas rejouée',
    );
  }
  return null;
}

/**
 * Met une demande non livrée en reprise (clé = son `idempotency_key`).
 * @param {EspaceKv} kv
 * @param {string} idempotencyKey
 * @param {string} corps
 * @param {number} dureeJours
 */
export async function mettreEnReprise(kv, idempotencyKey, corps, dureeJours) {
  await kv.put(PREFIXE + idempotencyKey, corps, { expirationTtl: Math.round(dureeJours * 86400) });
}

/**
 * Rejoue jusqu'à `limite` demandes en attente. `envoyer(corps)` SIGNE au
 * moment de l'appel (t frais). Livrée ou refus définitif (4xx) → retirée ;
 * sinon gardée pour un prochain passage. Ne lève jamais.
 * @param {EspaceKv} kv
 * @param {(corps: string) => Promise<Issue>} envoyer
 * @param {{ limite?: number, journal: Journal }} options
 * @returns {Promise<{ livrees: number, definitives: number, restantes: number }>}
 */
export async function rejouerReprise(kv, envoyer, { limite = 5, journal }) {
  const bilan = { livrees: 0, definitives: 0, restantes: 0 };
  try {
    const { keys } = await kv.list({ prefix: PREFIXE, limit: limite });
    for (const { name } of keys) {
      const corps = await kv.get(name);
      if (corps === null) continue;
      const issue = await envoyer(corps);
      if (issue === 'reessayer') {
        bilan.restantes += 1;
        continue;
      }
      await kv.delete(name);
      if (issue === 'livre') bilan.livrees += 1;
      else bilan.definitives += 1;
    }
  } catch {
    journal.warn('[rendez-vous] reprise interrompue (espace KV indisponible)');
  }
  return bilan;
}

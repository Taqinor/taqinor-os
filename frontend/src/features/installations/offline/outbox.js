// N91/F21/EZ8 — le moteur d'outbox a DÉMÉNAGÉ (NTMOB1).
//
// Il n'est plus propre à la capture terrain : la même file sert désormais tous
// les modules (crm, ventes, stock, installations, sav) et vit dans
// `src/lib/offlineOutbox.js`. Ce fichier n'est PAS une seconde implémentation —
// c'est une réexportation, pour que les imports terrain existants
// (`fieldOutbox.js`, les tests N91/EZ8) continuent de pointer vers l'UNIQUE
// moteur (décision VX105 : un seul outbox, un seul badge).
// Extension EXPLICITE : `node --test` charge ce fichier sans bundler.
//
// ACHT33 — seule addition, propre au TERRAIN : `FieldOutbox` (le même moteur,
// plus l'horodatage à la saisie `client_ts` / `base_updated_at` du contrat
// `/installations/sync/`) et `conflitEnErreur` (une op revenue `conflit` reste
// EN FILE, marquée, jamais « appliquée »).
import { Outbox, makeOpId } from '../../../lib/offlineOutbox.js'

export * from '../../../lib/offlineOutbox.js'

// Préfixe du message d'une op revenue `conflit` (persisté dans `serverError`
// avec la valeur serveur : l'op survit à un rechargement hors-ligne).
export const CONFLIT_PREFIX = 'Conflit — '

export const estConflit = (op) =>
  typeof op?.serverError === 'string' && op.serverError.startsWith(CONFLIT_PREFIX)

// Traduit les résultats `conflit` du serveur (détail + valeur serveur) en
// erreur d'op : le moteur garde alors l'op en file, marquée, visible et
// abandonnable — il ne la retire que sur applied|replayed.
export function conflitEnErreur(resp) {
  if (!resp || !Array.isArray(resp.results)) return resp
  return {
    ...resp,
    results: resp.results.map((r) => {
      if (r?.status !== 'conflit') return r
      const valeur = r.valeur_serveur !== undefined
        ? ` Valeur serveur : ${JSON.stringify(r.valeur_serveur)}`
        : ''
      return {
        ...r,
        status: 'error',
        error: `${CONFLIT_PREFIX}${r.detail || 'enregistrement modifié en ligne.'}${valeur}`,
      }
    }),
  }
}

export class FieldOutbox extends Outbox {
  // `clientTs` : instant de la SAISIE sur le terminal (défaut : maintenant) ;
  // `baseUpdatedAt` : `date_modification` de l'enregistrement tel que chargé.
  async enqueue(opType, payload, { clientOpId, target, queuedAt, clientTs, baseUpdatedAt } = {}) {
    await this._ensureLoaded()
    const client_op_id = clientOpId || makeOpId()
    const op = {
      client_op_id, op_type: opType, client_ts: clientTs || new Date().toISOString(), payload,
    }
    if (baseUpdatedAt) op.base_updated_at = baseUpdatedAt
    if (target !== undefined && target !== null) op.target = target
    if (queuedAt) op.queued_at = queuedAt
    await this._mutate((cur) => (
      cur.some((x) => x.client_op_id === client_op_id) ? cur : [...cur, op]))
    return client_op_id
  }

  // Rejouer une op en conflit : le terminal choisit d'écraser — on retire la
  // marque d'erreur ET `base_updated_at` (sinon le serveur re-détecterait le
  // même conflit), l'op repart au prochain flush.
  async rejouer(clientOpId) {
    await this._ensureLoaded()
    await this._mutate((cur) => cur.map((op) => {
      if (op.client_op_id !== clientOpId) return op
      // eslint-disable-next-line no-unused-vars
      const { serverError, attempts, base_updated_at, ...reste } = op
      return reste
    }))
  }
}

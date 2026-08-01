// AOF191 — File hors-ligne de saisie de RELEVÉ AO, et RIEN d'autre.
//
// Ce module est volontairement restreint aux QUATRE opérations de relevé
// (cote, obstacle, photo, réponse Q/R) : accepter une opération de CALCUL ou
// de GÉNÉRATION documentaire rendrait possible un chiffre local non prouvé —
// ce que ce groupe interdit absolument (en-tête du Groupe AOF : « la cascade
// de prix se calcule à l'envers… », « le compte == poseur, jamais estimé »).
// Toute tentative d'enqueue hors de cette liste LÈVE — elle n'est jamais
// silencieusement ignorée (test dédié dans fileReleve.test.mjs).
//
// Design calqué sur l'Outbox de capture terrain
// (features/installations/offline/outbox.js : clé d'idempotence client, remise
// en file tant que le serveur n'a pas confirmé) mais volontairement AUTONOME —
// ce fichier ne dépend que de la stdlib JS, aucun import cross-feature — et
// diffère sur un point produit central : un CONFLIT serveur n'est JAMAIS
// résolu en silence par le flush. Il reste en file, marqué `conflict`, jusqu'à
// une résolution EXPLICITE de l'utilisateur (`resoudreConflit`) — jamais un
// effet de bord d'une resynchronisation.

export const OP_TYPES_AUTORISES = Object.freeze([
  'releve.cote',
  'releve.obstacle',
  'releve.photo',
  'releve.reponse_qr',
])

const STATUS_DONE = new Set(['applied', 'replayed'])

// UUID v4 robuste (crypto si dispo, repli Math.random pour Node sans crypto
// globale). Doit seulement être unique par op pour la dédup serveur.
export function makeOpId() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  } catch { /* repli ci-dessous */ }
  return 'releve-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Adaptateur en mémoire — défaut hors navigateur, base des tests.
export function memoryStore(initial = []) {
  let data = [...initial]
  return {
    async load() { return [...data] },
    async save(ops) { data = [...ops] },
  }
}

// Repli localStorage (survit au rechargement d'onglet). Pas d'IndexedDB ici :
// le volume d'une file de relevé (cotes, obstacles, réponses, quelques photos
// en attente) reste petit — la simplicité d'un store JSON synchrone est
// préférée à l'ouverture asynchrone d'une base.
export function localStorageStore(key = 'taqinor-ao-releve-queue') {
  return {
    async load() {
      try {
        const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null
        const parsed = raw ? JSON.parse(raw) : []
        return Array.isArray(parsed) ? parsed : []
      } catch { return [] }
    },
    async save(ops) {
      try {
        if (typeof localStorage !== 'undefined') localStorage.setItem(key, JSON.stringify(ops))
      } catch { /* quota / navigation privée */ }
    },
  }
}

// Choisit le meilleur store disponible dans l'environnement courant.
export function createFileReleveStore() {
  try {
    if (typeof localStorage !== 'undefined' && localStorage) return localStorageStore()
  } catch { /* repli */ }
  return memoryStore()
}

export class FileReleve {
  // store : { load(), save(ops) } ; sender : async(ops) => { results }.
  constructor({ store = memoryStore(), sender, maxBatch = 200 } = {}) {
    this.store = store
    this.sender = sender
    this.maxBatch = maxBatch
    this._ops = null
    this._flushing = false
  }

  async _ensureLoaded() {
    if (this._ops === null) this._ops = await this.store.load()
    return this._ops
  }

  async _persist() {
    await this.store.save(this._ops)
  }

  // Met une opération de RELEVÉ en file. Lève si `opType` n'est pas dans
  // OP_TYPES_AUTORISES : le calcul et la génération documentaire exigent le
  // serveur et ne peuvent JAMAIS entrer dans cette file.
  async enqueue(opType, payload, { clientOpId } = {}) {
    if (!OP_TYPES_AUTORISES.includes(opType)) {
      throw new Error(
        `fileReleve: type d'opération "${opType}" refusé — seules les opérations de relevé `
        + `(${OP_TYPES_AUTORISES.join(', ')}) peuvent entrer dans cette file. Le calcul et la `
        + 'génération documentaire exigent le serveur et ne se mettent jamais en file locale.',
      )
    }
    await this._ensureLoaded()
    const client_op_id = clientOpId || makeOpId()
    this._ops.push({ client_op_id, op_type: opType, payload })
    await this._persist()
    return client_op_id
  }

  async pending() {
    await this._ensureLoaded()
    return [...this._ops]
  }

  async count() {
    await this._ensureLoaded()
    return this._ops.length
  }

  async clear() {
    this._ops = []
    await this._persist()
  }

  // Conflits serveur en attente d'une résolution EXPLICITE — ne disparaissent
  // JAMAIS d'un simple flush.
  async conflicts() {
    await this._ensureLoaded()
    return this._ops.filter((op) => !!op.conflict)
  }

  // Ops en erreur serveur (hors conflit), survivant au flush.
  async failed() {
    await this._ensureLoaded()
    return this._ops.filter((op) => !!op.serverError && !op.conflict)
  }

  // Résolution EXPLICITE d'un conflit par l'utilisateur — ce module ne décide
  // JAMAIS lui-même quel côté gagne, il retire seulement l'op une fois la
  // décision prise en dehors de lui.
  async resoudreConflit(clientOpId) {
    await this._ensureLoaded()
    this._ops = this._ops.filter((op) => op.client_op_id !== clientOpId)
    await this._persist()
  }

  // Abandon explicite d'une op en erreur (non-conflit).
  async discard(clientOpId) {
    await this._ensureLoaded()
    this._ops = this._ops.filter((op) => op.client_op_id !== clientOpId)
    await this._persist()
  }

  // Resynchronisation IDEMPOTENTE : rejouer le même client_op_id après un
  // double envoi (réseau perdu juste après la réponse serveur) est un no-op
  // côté serveur (status `replayed`) — jamais un doublon. Un conflit serveur
  // (status `conflict`) est marqué et GARDÉ en file, jamais résolu en silence.
  // Réentrant-safe (un flush concurrent est ignoré) ; ne lève jamais sur un
  // échec réseau — la file reste intacte pour réessayer plus tard.
  async flush() {
    if (this._flushing) {
      return { skipped: true, flushed: 0, failed: 0, conflicts: 0, remaining: await this.count() }
    }
    if (!this.sender) throw new Error('fileReleve: aucun « sender » configuré.')
    this._flushing = true
    let flushed = 0
    let failed = 0
    let conflicts = 0
    try {
      await this._ensureLoaded()
      while (this._ops.length > 0) {
        const batch = this._ops.slice(0, this.maxBatch)
        let resp
        try {
          resp = await this.sender(batch)
        } catch {
          break // réseau retombé / serveur indispo : file intacte
        }
        const results = (resp && resp.results) || []
        const byId = new Map(results.map((r) => [r.client_op_id, r]))
        const doneIds = new Set(
          results.filter((r) => STATUS_DONE.has(r.status)).map((r) => r.client_op_id),
        )
        const batchIds = new Set(batch.map((op) => op.client_op_id))

        this._ops = this._ops
          .filter((op) => !doneIds.has(op.client_op_id))
          .map((op) => {
            if (!batchIds.has(op.client_op_id) || doneIds.has(op.client_op_id)) return op
            const r = byId.get(op.client_op_id)
            if (r && r.status === 'conflict') {
              return {
                ...op,
                conflict: true,
                serverConflict: r.conflict || r.error || 'Conflit serveur — résolution requise.',
              }
            }
            return {
              ...op,
              serverError: (r && r.error) || 'Rejetée par le serveur.',
              attempts: (op.attempts || 0) + 1,
            }
          })

        const batchConflicts = batch.filter(
          (op) => byId.get(op.client_op_id)?.status === 'conflict',
        ).length
        const batchFailed = batchIds.size - doneIds.size - batchConflicts
        flushed += doneIds.size
        failed += batchFailed
        conflicts += batchConflicts
        await this._persist()
        // Ce paquet contenait des ops en erreur/conflit : on s'arrête pour ne
        // pas les renvoyer en boucle dans ce même flush() — un prochain flush
        // (manuel ou au retour réseau) les retentera, sauf les conflits qui
        // attendent une résolution explicite.
        if (batchFailed > 0 || batchConflicts > 0) break
      }
      return { skipped: false, flushed, failed, conflicts, remaining: this._ops.length }
    } finally {
      this._flushing = false
    }
  }
}

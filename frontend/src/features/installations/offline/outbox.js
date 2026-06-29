// N91/F21 — OUTBOX tolérante au hors-ligne pour la capture terrain.
//
// Quand le réseau est mauvais, chaque action de la capture terrain (checklist
// chantier, n° de série, matériel consommé, réserves, sécurité, check-in GPS,
// signature PV…) est mise en FILE LOCALE avec une CLÉ D'IDEMPOTENCE générée
// côté client (un UUID). À la reconnexion, l'outbox vide la file vers le point
// de synchro `/installations/sync/` ; rejouer la même clé est un no-op côté
// serveur, donc le flush est SÛR À REJOUER même si le réseau retombe en plein
// envoi.
//
// Ce module est PUR et testable : il ne touche ni au DOM ni au réseau
// directement. On lui injecte :
//   * `store` — un adaptateur de persistance (IndexedDB dans le navigateur,
//     en mémoire dans les tests) qui expose load()/save(ops) ;
//   * `sender` — une fonction async(ops) → résultat serveur
//     ({ results: [{ client_op_id, status }] }).
// L'outbox ne supprime de la file QUE les ops confirmées par le serveur
// (status applied|replayed) — une op en erreur reste filée pour un prochain
// essai (réseau revenu mais cible pas encore prête, etc.).

// UUID v4 robuste (crypto si dispo, repli Math.random pour les tests Node sans
// crypto.randomUUID). La clé n'a pas besoin d'être cryptographiquement sûre :
// elle doit juste être unique par op pour la dédup serveur.
export function makeOpId() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
  } catch { /* repli ci-dessous */ }
  return 'op-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// Adaptateur en mémoire — défaut hors navigateur (et base des tests).
export function memoryStore(initial = []) {
  let data = [...initial]
  return {
    async load() { return [...data] },
    async save(ops) { data = [...ops] },
  }
}

const STATUS_DONE = new Set(['applied', 'replayed'])

export class Outbox {
  // store : { load(), save(ops) } ; sender : async(ops) => { results }.
  constructor({ store = memoryStore(), sender, maxBatch = 200 } = {}) {
    this.store = store
    this.sender = sender
    this.maxBatch = maxBatch
    this._ops = null        // cache mémoire de la file (chargé paresseusement)
    this._flushing = false   // garde anti-réentrance du flush
  }

  async _ensureLoaded() {
    if (this._ops === null) this._ops = await this.store.load()
    return this._ops
  }

  async _persist() {
    await this.store.save(this._ops)
  }

  // Met une opération en file. `payload` voyagera tel quel au serveur. Renvoie
  // le client_op_id attribué (utile pour corréler / tester).
  async enqueue(opType, payload, { clientOpId } = {}) {
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

  // Vide la file vers le serveur, par paquets de `maxBatch`. Retire UNIQUEMENT
  // les ops confirmées (applied|replayed) ; garde les ops en erreur pour un
  // prochain essai. Idempotent et ré-entrant-safe : un flush concurrent est
  // ignoré (renvoie un résumé « skipped »). Ne lève jamais — un échec réseau
  // laisse simplement la file intacte pour réessayer plus tard.
  async flush() {
    if (this._flushing) return { skipped: true, flushed: 0, remaining: await this.count() }
    if (!this.sender) throw new Error('Outbox: aucun « sender » configuré.')
    this._flushing = true
    let flushed = 0
    try {
      await this._ensureLoaded()
      while (this._ops.length > 0) {
        const batch = this._ops.slice(0, this.maxBatch)
        let resp
        try {
          resp = await this.sender(batch)
        } catch {
          // Réseau retombé / serveur indispo : on s'arrête, file intacte.
          break
        }
        const results = (resp && resp.results) || []
        const doneIds = new Set(
          results.filter((r) => STATUS_DONE.has(r.status)).map((r) => r.client_op_id),
        )
        if (doneIds.size === 0) {
          // Aucun progrès (toutes en erreur applicative) : on évite la boucle
          // infinie — on retire ce paquet pour ne pas le rejouer sans fin
          // côté CLIENT ; le serveur ne l'a de toute façon pas mémorisé.
          this._ops = this._ops.slice(batch.length)
          flushed += 0
        } else {
          this._ops = this._ops.filter((op) => !doneIds.has(op.client_op_id))
          flushed += doneIds.size
        }
        await this._persist()
        // Si rien n'a avancé ET qu'on a retiré le paquet en erreur, on continue
        // avec le reste de la file.
      }
      return { skipped: false, flushed, remaining: this._ops.length }
    } finally {
      this._flushing = false
    }
  }
}

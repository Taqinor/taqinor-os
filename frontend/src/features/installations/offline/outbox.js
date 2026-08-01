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
//     ({ results: [{ client_op_id, status, error? }] }).
// L'outbox ne supprime de la file QUE les ops confirmées par le serveur
// (status applied|replayed). Une op rejetée par le serveur (status error) NE
// DISPARAÎT PLUS JAMAIS EN SILENCE : elle reste en file, marquée
// `serverError` avec le message serveur + un compteur `attempts`, jusqu'à un
// abandon EXPLICITE (VX119 — une signature client capturée hors-ligne ne doit
// jamais s'évaporer sans trace).

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

// ── EZ8 — charges BINAIRES (photos) dans CE MÊME outbox ─────────────────────
// Jusqu'ici une coupure réseau pendant un upload photo = photo PERDUE (le
// panneau affichait un toast « reprenez-la »). L'outbox JSON ci-dessus ne peut
// pas les porter : une photo ne passe pas par le point de synchro JSON. On
// ajoute donc une file BINAIRE ici — dans le MÊME module, avec les mêmes
// règles (clé d'idempotence, rien ne disparaît en silence, abandon explicite),
// JAMAIS un deuxième outbox ni un deuxième badge (décision VX105 ×3).
//
// Choix assumés :
//  * on stocke des `ArrayBuffer`, pas des `Blob` : le stockage de Blob dans
//    IndexedDB est instable sur Safari iOS (références perdues au réveil) ;
//  * la photo est COMPRESSÉE avant la mise en file (VX77) — un toit fait 3-5 Mo
//    brut, la file exploserait sinon ;
//  * plafonds EXPLICITES (nombre + octets) : au-delà, l'enfilage ÉCHOUE avec un
//    message clair plutôt que de faire grossir le stockage en silence ;
//  * honnêteté iOS : Safari purge le stockage d'un site après ~7 jours sans
//    visite — la file n'est pas un coffre-fort, elle est un filet de quelques
//    heures. C'est écrit dans l'UI, pas seulement ici ;
//  * rejeu : on ne met en file QUE sur un échec RÉSEAU (aucune réponse
//    serveur). Le cas « la requête est passée mais la réponse s'est perdue »
//    peut donc produire un doublon de photo — un doublon se supprime d'un clic,
//    une photo perdue ne se récupère pas.
export const BINARY_MAX_OPS = 40
export const BINARY_MAX_BYTES = 60 * 1024 * 1024 // 60 Mo

export class OutboxQuotaError extends Error {
  constructor(message) {
    super(message)
    this.name = 'OutboxQuotaError'
    this.quota = true
  }
}

// Marge de sécurité : on refuse d'enfiler si le stockage du navigateur est déjà
// quasi plein (`navigator.storage.estimate()` — best-effort, absent = OK).
export async function espaceDisponible(tailleOctets) {
  try {
    if (typeof navigator === 'undefined' || !navigator.storage?.estimate) return true
    const { usage = 0, quota = 0 } = await navigator.storage.estimate()
    if (!quota) return true
    return usage + tailleOctets < quota * 0.9
  } catch { return true }
}

export class BinaryOutbox {
  // store : { load(), save(ops) } ; uploader : async(entry) => réponse serveur.
  constructor({
    store = memoryStore(), uploader, maxOps = BINARY_MAX_OPS,
    maxBytes = BINARY_MAX_BYTES, persistent = true,
  } = {}) {
    this.store = store
    this.uploader = uploader
    this.maxOps = maxOps
    this.maxBytes = maxBytes
    this.persistent = persistent
    this._ops = null
    this._flushing = false
  }

  async _ensureLoaded() {
    if (this._ops === null) this._ops = await this.store.load()
    return this._ops
  }

  async _persist() { await this.store.save(this._ops) }

  async bytes() {
    await this._ensureLoaded()
    return this._ops.reduce((n, op) => n + (op.size || 0), 0)
  }

  /**
   * Met une charge binaire en file. `bytes` DOIT être un ArrayBuffer.
   * Lève `OutboxQuotaError` (message français prêt à afficher) si un plafond
   * est atteint ou si le navigateur n'a plus de place — jamais un échec muet.
   */
  async enqueue(opType, meta, { bytes, name, type } = {}, { clientOpId } = {}) {
    if (!(bytes instanceof ArrayBuffer)) {
      throw new Error('BinaryOutbox: charge attendue en ArrayBuffer.')
    }
    await this._ensureLoaded()
    const size = bytes.byteLength
    if (this._ops.length >= this.maxOps) {
      throw new OutboxQuotaError(
        `File d’envoi pleine (${this.maxOps} photos en attente). `
        + 'Reconnectez-vous au réseau pour la vider avant d’en ajouter.')
    }
    const total = await this.bytes()
    if (total + size > this.maxBytes) {
      throw new OutboxQuotaError(
        'File d’envoi pleine (limite de taille atteinte). '
        + 'Reconnectez-vous au réseau pour la vider avant d’en ajouter.')
    }
    if (!(await espaceDisponible(size))) {
      throw new OutboxQuotaError(
        'Stockage du téléphone saturé — photo NON mise en file. '
        + 'Libérez de l’espace, puis reprenez la photo.')
    }
    const client_op_id = clientOpId || makeOpId()
    this._ops.push({
      client_op_id, op_type: opType, meta: meta ?? {},
      bytes, name: name || 'photo.jpg', type: type || 'image/jpeg',
      size, queuedAt: new Date().toISOString(),
    })
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

  async failed() {
    await this._ensureLoaded()
    return this._ops.filter((op) => !!op.serverError)
  }

  async discard(clientOpId) {
    await this._ensureLoaded()
    this._ops = this._ops.filter((op) => op.client_op_id !== clientOpId)
    await this._persist()
  }

  async clear() {
    this._ops = []
    await this._persist()
  }

  /**
   * Rejoue les envois un par un. Retire UNIQUEMENT ce que le serveur a accepté.
   * Échec RÉSEAU → on s'arrête, file intacte (on retentera). Refus SERVEUR
   * (4xx) → l'op reste en file, marquée `serverError` + `attempts`, exactement
   * comme l'outbox JSON : rien ne disparaît en silence (VX119).
   */
  async flush() {
    if (this._flushing) {
      return { skipped: true, flushed: 0, failed: 0, remaining: await this.count() }
    }
    if (!this.uploader) throw new Error('BinaryOutbox: aucun « uploader » configuré.')
    this._flushing = true
    let flushed = 0
    let failed = 0
    try {
      await this._ensureLoaded()
      // Copie : on itère sur un instantané, la file est réécrite au fil de l'eau.
      for (const op of [...this._ops]) {
        if (op.serverError) continue // déjà refusée : attend un abandon explicite
        try {
          await this.uploader(op)
          this._ops = this._ops.filter((x) => x.client_op_id !== op.client_op_id)
          flushed += 1
          await this._persist()
        } catch (err) {
          const reseau = !err?.response
          if (reseau) break // réseau retombé : file intacte, on retentera
          this._ops = this._ops.map((x) => (x.client_op_id === op.client_op_id
            ? {
              ...x,
              serverError: err?.response?.data?.detail || 'Refusée par le serveur.',
              attempts: (x.attempts || 0) + 1,
            }
            : x))
          failed += 1
          await this._persist()
        }
      }
      return { skipped: false, flushed, failed, remaining: this._ops.length }
    } finally {
      this._flushing = false
    }
  }
}

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

  // Ops actuellement marquées en erreur serveur (survivent au flush, restent
  // visibles à l'utilisateur — jamais retirées silencieusement).
  async failed() {
    await this._ensureLoaded()
    return this._ops.filter((op) => !!op.serverError)
  }

  // Abandon EXPLICITE d'une op en erreur (l'utilisateur a vu le message et
  // choisit de ne plus réessayer). Seule façon de faire disparaître une op —
  // jamais un effet de bord du flush.
  async discard(clientOpId) {
    await this._ensureLoaded()
    this._ops = this._ops.filter((op) => op.client_op_id !== clientOpId)
    await this._persist()
  }

  // Vide la file vers le serveur, par paquets de `maxBatch`. Retire
  // UNIQUEMENT les ops confirmées (applied|replayed). Une op rejetée par le
  // serveur (status error) est GARDÉE en file — marquée `serverError` (le
  // message serveur) + `attempts` incrémenté — pour un prochain essai ou un
  // abandon explicite par l'utilisateur ; elle ne disparaît JAMAIS toute
  // seule. Idempotent et ré-entrant-safe : un flush concurrent est ignoré
  // (renvoie un résumé « skipped »). Ne lève jamais — un échec réseau laisse
  // simplement la file intacte pour réessayer plus tard.
  async flush() {
    if (this._flushing) return { skipped: true, flushed: 0, failed: 0, remaining: await this.count() }
    if (!this.sender) throw new Error('Outbox: aucun « sender » configuré.')
    this._flushing = true
    let flushed = 0
    let failed = 0
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
        const byId = new Map(results.map((r) => [r.client_op_id, r]))
        const doneIds = new Set(
          results.filter((r) => STATUS_DONE.has(r.status)).map((r) => r.client_op_id),
        )
        const batchIds = new Set(batch.map((op) => op.client_op_id))
        // Ops confirmées (applied|replayed) sont retirées ; toute autre op du
        // paquet reste en file, marquée avec le message d'erreur serveur +
        // compteur de tentatives — JAMAIS retirée silencieusement (VX119).
        this._ops = this._ops
          .filter((op) => !doneIds.has(op.client_op_id))
          .map((op) => {
            if (!batchIds.has(op.client_op_id) || doneIds.has(op.client_op_id)) return op
            const r = byId.get(op.client_op_id)
            return {
              ...op,
              serverError: (r && r.error) || 'Rejetée par le serveur.',
              attempts: (op.attempts || 0) + 1,
            }
          })
        flushed += doneIds.size
        const batchFailed = batchIds.size - doneIds.size
        failed += batchFailed
        await this._persist()
        // Ce paquet contenait des ops en erreur : on s'arrête pour ne pas les
        // renvoyer en boucle dans ce même flush() — un prochain flush (manuel
        // ou au retour réseau) les retentera avec `attempts` à jour.
        if (batchFailed > 0) break
      }
      return { skipped: false, flushed, failed, remaining: this._ops.length }
    } finally {
      this._flushing = false
    }
  }
}

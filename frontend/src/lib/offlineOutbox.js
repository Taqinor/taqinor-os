// NTMOB1 — MOTEUR OFFLINE-FIRST GÉNÉRALISÉ (file d'attente multi-module).
//
// Ce fichier est le SEUL outbox de l'application (décision VX105, tenue depuis
// N91/F21 puis EZ8). Il ne DUPLIQUE rien : le moteur écrit pour la capture
// terrain a simplement DÉMÉNAGÉ ici et s'est généralisé à tous les modules
// (crm, ventes, stock, installations, sav). `features/installations/offline/
// outbox.js` réexporte désormais ce module — un seul code, un seul compteur, un
// seul badge d'en-tête (`SyncStatusBadge`, NTMOB3).
//
// Quand le réseau est mauvais, chaque action est mise en FILE LOCALE avec une
// CLÉ D'IDEMPOTENCE générée côté client (un UUID). À la reconnexion, l'outbox
// vide la file vers son point de synchro ; rejouer la même clé est un no-op
// côté serveur, donc le flush est SÛR À REJOUER même si le réseau retombe en
// plein envoi.
//
// Ce module reste PUR au CHARGEMENT : il ne touche ni au DOM ni au réseau à
// l'import (le client HTTP du point de synchro est chargé DYNAMIQUEMENT au
// premier envoi), ce qui le rend testable sous `node --test` sans bundler.
// On lui injecte :
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

// Extension EXPLICITE : ce module est chargé tel quel par `node --test` (tests
// de logique pure, sans bundler), où un import sans extension échoue.
import { createModuleOutboxStore } from './offlineStore.js'

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
  let chaine = Promise.resolve()
  return {
    async load() { return [...data] },
    async save(ops) { data = [...ops] },
    // ADEP17 — lecture-modification-écriture ATOMIQUE (sérialisée) : `fn` reçoit le
    // contenu COURANT et rend le nouveau ; jamais un instantané périmé.
    update(fn) {
      const p = chaine.then(() => { data = [...fn([...data])]; return [...data] })
      chaine = p.catch(() => {})
      return p
    },
  }
}

// ADEP17 — mise à jour ATOMIQUE d'une file : `store.update(fn)` quand le magasin la
// fournit (IndexedDB : UNE transaction readwrite get→put, atomique entre onglets) ;
// repli pour un magasin load/save nu : load→fn→save sous un verrou par file
// (`navigator.locks` entre onglets quand disponible, chaîne de promesses sinon).
// `fn` est SYNCHRONE et PURE : elle reçoit les ops courantes et rend les nouvelles.
const _chainesVerrou = new WeakMap()
export async function majAtomique(store, fn) {
  if (typeof store.update === 'function') return store.update(fn)
  const executer = async () => {
    const courant = await store.load()
    const suivant = fn(courant)
    await store.save(suivant)
    return suivant
  }
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
  const sousVerrou = locks && typeof locks.request === 'function'
    ? () => locks.request(`taqinor-outbox:${store.lockName || 'file'}`, executer)
    : executer
  const precedent = _chainesVerrou.get(store) || Promise.resolve()
  const p = precedent.then(sousVerrou)
  _chainesVerrou.set(store, p.catch(() => {}))
  return p
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
    this._loading = null
    this._flushing = false
  }

  // ADEP17 — UNE promesse de chargement : deux appels avant la fin du premier
  // chargement attendent le MÊME résultat (sinon le second écrasait le premier).
  async _ensureLoaded() {
    if (this._ops === null) {
      if (!this._loading) {
        this._loading = this.store.load().then((ops) => { this._ops = ops; return ops })
      }
      await this._loading
    }
    return this._ops
  }

  // ADEP17 — toute mutation = lecture-modification-écriture ATOMIQUE sur le contenu
  // COURANT du magasin (un autre onglet a pu écrire entre-temps).
  async _mutate(fn) {
    this._ops = await majAtomique(this.store, fn)
    return this._ops
  }

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
    const nouvelle = {
      client_op_id, op_type: opType, meta: meta ?? {},
      bytes, name: name || 'photo.jpg', type: type || 'image/jpeg',
      size, queuedAt: new Date().toISOString(),
    }
    // Plafonds RE-vérifiés sur le contenu courant, dans la mise à jour atomique.
    let refus = null
    await this._mutate((cur) => {
      if (cur.some((x) => x.client_op_id === client_op_id)) return cur
      if (cur.length >= this.maxOps) {
        refus = new OutboxQuotaError(
          `File d’envoi pleine (${this.maxOps} photos en attente). `
          + 'Reconnectez-vous au réseau pour la vider avant d’en ajouter.')
        return cur
      }
      if (cur.reduce((n, x) => n + (x.size || 0), 0) + size > this.maxBytes) {
        refus = new OutboxQuotaError(
          'File d’envoi pleine (limite de taille atteinte). '
          + 'Reconnectez-vous au réseau pour la vider avant d’en ajouter.')
        return cur
      }
      return [...cur, nouvelle]
    })
    if (refus) throw refus
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
    await this._mutate((cur) => cur.filter((op) => op.client_op_id !== clientOpId))
  }

  async clear() {
    await this._mutate(() => [])
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
      // ADEP17 — contenu COURANT du magasin (un autre onglet a pu y écrire).
      this._ops = await this.store.load()
      // Copie : on itère sur un instantané, la file est réécrite au fil de l'eau.
      for (const op of [...this._ops]) {
        if (op.serverError) continue // déjà refusée : attend un abandon explicite
        try {
          await this.uploader(op)
          await this._mutate((cur) => cur.filter((x) => x.client_op_id !== op.client_op_id))
          flushed += 1
        } catch (err) {
          const reseau = !err?.response
          if (reseau) break // réseau retombé : file intacte, on retentera
          await this._mutate((cur) => cur.map((x) => (x.client_op_id === op.client_op_id
            ? {
              ...x,
              serverError: err?.response?.data?.detail || 'Refusée par le serveur.',
              attempts: (x.attempts || 0) + 1,
            }
            : x)))
          failed += 1
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
    this._loading = null     // ADEP17 : promesse de chargement UNIQUE
    this._flushing = false   // garde anti-réentrance du flush
  }

  async _ensureLoaded() {
    if (this._ops === null) {
      if (!this._loading) {
        this._loading = this.store.load().then((ops) => { this._ops = ops; return ops })
      }
      await this._loading
    }
    return this._ops
  }

  // ADEP17 — lecture-modification-écriture ATOMIQUE sur le contenu COURANT du magasin
  // (un autre onglet / appel concurrent a pu écrire), fusionnée par `client_op_id`.
  async _mutate(fn) {
    this._ops = await majAtomique(this.store, fn)
    return this._ops
  }

  // Relit le magasin : les lectures voient aussi ce qu'un autre onglet a mis en file.
  async _refresh() {
    await this._ensureLoaded()
    this._ops = await this.store.load()
    return this._ops
  }

  // Met une opération en file. `payload` voyagera tel quel au serveur. Renvoie
  // le client_op_id attribué (utile pour corréler / tester).
  //
  // NTMOB1 — deux méta FACULTATIVES (absentes de l'op quand non fournies, donc
  // la file terrain historique garde exactement la même forme) :
  //   * `target` — l'enregistrement visé (id), pour le badge « modifications
  //     non synchronisées » par ligne de liste (NTMOB24) ;
  //   * `queuedAt` — l'horodatage de mise en file CÔTÉ TERMINAL, envoyé au
  //     serveur en `queued_at` (un technicien peut filer le lundi et se
  //     reconnecter le jeudi).
  async enqueue(opType, payload, { clientOpId, target, queuedAt } = {}) {
    await this._ensureLoaded()
    const client_op_id = clientOpId || makeOpId()
    const op = { client_op_id, op_type: opType, payload }
    if (target !== undefined && target !== null) op.target = target
    if (queuedAt) op.queued_at = queuedAt
    await this._ensureLoaded()
    await this._mutate((cur) => (
      cur.some((x) => x.client_op_id === client_op_id) ? cur : [...cur, op]))
    return client_op_id
  }

  async pending() {
    await this._refresh()
    return [...this._ops]
  }

  async count() {
    await this._refresh()
    return this._ops.length
  }

  async clear() {
    await this._ensureLoaded()
    await this._mutate(() => [])
  }

  // Ops actuellement marquées en erreur serveur (survivent au flush, restent
  // visibles à l'utilisateur — jamais retirées silencieusement).
  async failed() {
    await this._refresh()
    return this._ops.filter((op) => !!op.serverError)
  }

  // Abandon EXPLICITE d'une op en erreur (l'utilisateur a vu le message et
  // choisit de ne plus réessayer). Seule façon de faire disparaître une op —
  // jamais un effet de bord du flush.
  async discard(clientOpId) {
    await this._ensureLoaded()
    await this._mutate((cur) => cur.filter((op) => op.client_op_id !== clientOpId))
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
      await this._refresh()
      // ADEP18 — les ops déjà MARQUÉES (refusées) sont sautées en composant le lot : une
      // op refusée en tête ne bloque pas les suivantes. Elles ne sont retentées que
      // lorsqu'il ne reste QUE des ops marquées (VX119 : rejeu + `attempts`).
      const retenterMarquees = !this._ops.some((op) => !op.serverError)
      const aEnvoyer = () => (retenterMarquees ? this._ops : this._ops.filter((op) => !op.serverError))
      while (aEnvoyer().length > 0) {
        const batch = aEnvoyer().slice(0, this.maxBatch)
        let resp
        try {
          resp = await this.sender(batch)
        } catch (err) {
          const statut = err?.response?.status
          const transitoire = !statut || statut >= 500 || statut === 401
            || statut === 408 || statut === 429
          if (transitoire) break // Réseau retombé / serveur indispo : file intacte.
          // ADEP18 — réponse HTTP NON transitoire (400, 403, 404…) : ce n'est pas une
          // coupure. Les ops du lot sont marquées (visibles, abandonnables), comme le
          // fait `BinaryOutbox.flush`, au lieu de rester « en attente » en silence.
          const detail = err?.response?.data?.detail || 'Refusée par le serveur.'
          const ids = new Set(batch.map((op) => op.client_op_id))
          await this._mutate((cur) => cur.map((op) => (ids.has(op.client_op_id)
            ? { ...op, serverError: detail, attempts: (op.attempts || 0) + 1 }
            : op)))
          failed += ids.size
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
        // ADEP17 — appliqué au contenu COURANT du magasin : une op ajoutée par un
        // autre onglet pendant l'envoi est CONSERVÉE (jamais un `save` de l'instantané).
        await this._mutate((cur) => cur
          .filter((op) => !doneIds.has(op.client_op_id))
          .map((op) => {
            if (!batchIds.has(op.client_op_id) || doneIds.has(op.client_op_id)) return op
            const r = byId.get(op.client_op_id)
            return {
              ...op,
              serverError: (r && r.error) || 'Rejetée par le serveur.',
              attempts: (op.attempts || 0) + 1,
            }
          }))
        flushed += doneIds.size
        const batchFailed = batchIds.size - doneIds.size
        failed += batchFailed
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

// ── NTMOB1 — FILES PAR MODULE (le même moteur, une file par domaine) ────────
//
// Une file PAR MODULE (et non une file géante) pour trois raisons concrètes :
//   * un refus serveur sur une op CRM ne doit pas bloquer la synchro du stock
//     (le flush s'arrête au premier paquet contenant une erreur) ;
//   * le badge par écran (NTMOB24) lit le module de l'écran courant sans
//     filtrer toute la file ;
//   * la purge d'un module reste possible sans toucher aux autres.
// Elles partagent la MÊME base IndexedDB, le MÊME moteur et le MÊME badge : ce
// sont des clés, pas des outbox concurrents.

// source-choix: offlinesync.OfflineOperation.module
// VTA10 — `visites` rejoint la liste avec l'app autonome Visites terrain : le
// commercial saisit ses mesures dans un sous-sol ou un champ, donc HORS RÉSEAU.
// Sa contrepartie serveur est `offlinesync.OfflineOperation.Module.VISITES` +
// le handler `visite.mesures` (VTA10, moitié backend).
export const OFFLINE_MODULES = ['crm', 'ventes', 'stock', 'installations', 'sav', 'visites']

// Point de synchro unique, côté serveur : POST /offlinesync/operations/batch/.
// L'import du client HTTP est DYNAMIQUE et différé au premier envoi pour que ce
// module reste chargeable hors bundler (tests node:test) — ni axios ni
// `import.meta.env` ne sont touchés à l'import.
async function defaultSender(ops) {
  const { default: offlinesyncApi } = await import('../api/offlinesyncApi.js')
  const r = await offlinesyncApi.envoyerLot(ops)
  return r.data
}

const _moduleOutboxes = new Map()

// Indirection d'un niveau : les files mémoïsées appellent TOUJOURS `_sender`,
// si bien qu'un remplacement (tests de logique pure, sans réseau) vaut pour
// toutes les files, y compris celles déjà créées.
let _sender = defaultSender
const _senderProxy = (ops) => _sender(ops)

/** Remplace le point de synchro (tests). Sans argument, rétablit le défaut. */
export function setModuleSender(sender) {
  _sender = sender || defaultSender
}

/** Outbox (mémoïsée) d'un module. Crée la file au premier accès. */
export function getModuleOutbox(module) {
  if (!OFFLINE_MODULES.includes(module)) {
    throw new Error(`Module hors-ligne inconnu : ${module}.`)
  }
  let ob = _moduleOutboxes.get(module)
  if (!ob) {
    ob = new Outbox({ store: createModuleOutboxStore(module), sender: _senderProxy })
    _moduleOutboxes.set(module, ob)
  }
  return ob
}

// Abonnement léger : l'UI (badge global NTMOB3, badge par ligne NTMOB24) se
// rafraîchit après chaque mise en file / flush sans sondage périodique.
const _abonnes = new Set()

function _notifier() {
  for (const cb of [..._abonnes]) {
    try { cb() } catch { /* un abonné cassé n'empêche pas les autres */ }
  }
}

/** S'abonne aux changements de file. Renvoie la fonction de désabonnement. */
export function onOfflineOutboxChange(cb) {
  _abonnes.add(cb)
  return () => _abonnes.delete(cb)
}

/**
 * Signale un changement de file venu d'AILLEURS que ce module (la file terrain
 * historique, par exemple) : les badges — celui de l'en-tête comme ceux des
 * listes — se rafraîchissent alors immédiatement, sans sondage.
 */
export function notifyOfflineOutboxChange() {
  _notifier()
}

/**
 * Met une opération d'un module en file. `target` (facultatif) est l'id de
 * l'enregistrement visé : c'est lui qui alimente le badge par ligne (NTMOB24).
 */
export async function queueOperation(module, opType, payload, { target, clientOpId } = {}) {
  const id = await getModuleOutbox(module).enqueue(opType, payload, {
    clientOpId, target, queuedAt: new Date().toISOString(),
  })
  _notifier()
  return id
}

/**
 * Tente l'appel EN LIGNE d'abord ; si le réseau échoue (aucune réponse
 * serveur), met l'op en file et renvoie `{ queued: true }`. Une vraie erreur
 * applicative (réponse 4xx) est RELANCÉE — ce n'est pas un problème réseau,
 * l'utilisateur doit la voir. Pendant jumeau de `withOfflineFallback` (terrain),
 * généralisé aux autres modules.
 */
export async function queueIfOffline(module, onlineCall, opType, payload, { target } = {}) {
  // ADEP16 — UNE clé d'idempotence par action, générée AVANT l'appel : un timeout
  // (ECONNABORTED, aucune réponse) peut survenir APRÈS l'effet serveur ; l'op mise en
  // file doit alors porter la MÊME clé pour que le rejeu soit un `replayed`, pas un
  // second effet. L'appelant peut l'ignorer (argument facultatif).
  const clientOpId = makeOpId()
  try {
    const data = await onlineCall(clientOpId)
    return { queued: false, data }
  } catch (err) {
    if (err?.response) throw err // erreur applicative : jamais filée en silence
    await queueOperation(module, opType, payload, { target, clientOpId })
    return { queued: true, clientOpId }
  }
}

/** Toutes les ops en file, tous modules (chaque op porte son `module`). */
export async function pendingModuleOps() {
  const out = []
  for (const module of OFFLINE_MODULES) {
    const ob = _moduleOutboxes.get(module)
    if (!ob) continue // jamais utilisée : rien à charger (ni base à ouvrir)
    for (const op of await ob.pending()) out.push({ ...op, module })
  }
  return out
}

/** Ops refusées par le serveur, tous modules — visibles jusqu'à abandon. */
export async function failedModuleOps() {
  return (await pendingModuleOps()).filter((op) => !!op.serverError)
}

/** Vide toutes les files de module. Ne lève jamais (réseau = on retentera). */
export async function flushModuleOutboxes() {
  let flushed = 0
  let failed = 0
  let remaining = 0
  for (const module of OFFLINE_MODULES) {
    const ob = _moduleOutboxes.get(module)
    if (!ob) continue
    const res = await ob.flush().catch(() => null)
    if (!res) continue
    flushed += res.flushed || 0
    failed += res.failed || 0
    remaining += res.remaining || 0
  }
  _notifier()
  return { flushed, failed, remaining }
}

/** Abandon EXPLICITE d'une op refusée (VX119) — quel que soit son module. */
export async function discardModuleOp(clientOpId) {
  for (const module of OFFLINE_MODULES) {
    const ob = _moduleOutboxes.get(module)
    if (ob) await ob.discard(clientOpId)
  }
  _notifier()
}

/** Purge totale (déconnexion sur terminal PARTAGÉ — patron LW45). */
export async function purgeModuleOutboxes() {
  for (const module of OFFLINE_MODULES) {
    const ob = _moduleOutboxes.get(module)
    if (ob) await ob.clear().catch(() => undefined)
  }
  _notifier()
}

/**
 * NTMOB24 — nombre d'ops NON SYNCHRONISÉES par enregistrement d'un module :
 * `Map<String(target), n>`. Les ops refusées par le serveur comptent aussi
 * (elles ne sont PAS synchronisées et attendent une action de l'utilisateur) ;
 * une op sans `target` n'apparaît dans aucune ligne de liste.
 */
export async function pendingCountByTarget(module) {
  const compte = new Map()
  const ob = _moduleOutboxes.get(module)
  if (!ob) return compte
  for (const op of await ob.pending()) {
    if (op.target === undefined || op.target === null) continue
    const cle = String(op.target)
    compte.set(cle, (compte.get(cle) || 0) + 1)
  }
  return compte
}

/**
 * NTMOB24 — même comptage, mais pour une file dont la cible vit DANS le corps
 * de l'op (c'est le cas de la file terrain historique : `payload.chantier`,
 * `payload.intervention`). Fonction PURE : on lui passe les ops déjà chargées.
 */
export function countByPayloadKey(ops, cle) {
  const compte = new Map()
  for (const op of ops || []) {
    const valeur = op?.payload?.[cle]
    if (valeur === undefined || valeur === null || valeur === '') continue
    const k = String(valeur)
    compte.set(k, (compte.get(k) || 0) + 1)
  }
  return compte
}

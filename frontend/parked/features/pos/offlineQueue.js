// NTRET1 — Mode offline caisse : file de synchronisation.
//
// Quand la caisse perd le réseau (détecté via `navigator.onLine` + une sonde
// ping injectable), chaque vente comptoir créée hors-ligne reçoit un
// `uuid_client` généré côté navigateur et est mise en file LOCALE
// (IndexedDB, repli localStorage puis mémoire — même patron que
// features/installations/offline/idbStore.js). Dès la reconnexion, la file
// est rejouée FIFO contre `POST /api/django/pos/ventes/` avec retry +
// backoff : le serveur dédupe sur `uuid_client`
// (apps/pos/models.py::VenteComptoir.uuid_client, contrainte unique par
// société) — un rejeu en double ne crée donc jamais deux ventes.
//
// Module PUR et testable : aucun accès réseau direct — `sender` (async
// (payload) => réponse serveur) et `store` sont injectés par l'appelant.

const DB_NAME = 'taqinor-pos-offline'
const STORE = 'ops'
const KEY = 'queue-ventes'

// Paliers de backoff (ms) : 5s, 15s, 30s, 1min, 2min, puis 5min en régime
// permanent — évite de marteler le serveur pendant une coupure prolongée
// tout en rejouant vite une coupure courte.
export const BACKOFF_STEPS_MS = [5_000, 15_000, 30_000, 60_000, 120_000, 300_000]

function openDb() {
  return new Promise((resolve, reject) => {
    try {
      const req = indexedDB.open(DB_NAME, 1)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE)
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    } catch (e) { reject(e) }
  })
}

function idbAdapter() {
  return {
    async load() {
      const db = await openDb()
      return new Promise((resolve) => {
        const tx = db.transaction(STORE, 'readonly')
        const req = tx.objectStore(STORE).get(KEY)
        req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : [])
        req.onerror = () => resolve([])
      })
    },
    async save(ops) {
      const db = await openDb()
      return new Promise((resolve) => {
        const tx = db.transaction(STORE, 'readwrite')
        tx.objectStore(STORE).put(ops, KEY)
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
      })
    },
  }
}

function localStorageAdapter() {
  const k = `${DB_NAME}:${KEY}`
  return {
    async load() {
      try {
        const raw = localStorage.getItem(k)
        const parsed = raw ? JSON.parse(raw) : []
        return Array.isArray(parsed) ? parsed : []
      } catch { return [] }
    },
    async save(ops) {
      try { localStorage.setItem(k, JSON.stringify(ops)) } catch { /* quota/privé */ }
    },
  }
}

// Adaptateur en mémoire — base des tests, et dernier repli hors navigateur.
export function memoryStore(initial = []) {
  let data = [...initial]
  return {
    async load() { return [...data] },
    async save(ops) { data = [...ops] },
  }
}

// Choisit le meilleur store disponible dans l'environnement courant (même
// cascade que installations/offline/idbStore.js : IndexedDB → localStorage →
// mémoire, jamais d'exception qui ferait planter la caisse).
export function createOfflineStore() {
  try {
    if (typeof indexedDB !== 'undefined' && indexedDB) return idbAdapter()
  } catch { /* repli */ }
  try {
    if (typeof localStorage !== 'undefined' && localStorage) return localStorageAdapter()
  } catch { /* repli */ }
  return memoryStore()
}

// UUID v4 (crypto si dispo, repli Math.random pour Node sans crypto.randomUUID
// ou navigateurs très anciens) — n'a besoin que d'être unique par vente pour
// la dédup serveur, pas cryptographiquement sûr.
export function makeUuidClient() {
  try {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  } catch { /* repli ci-dessous */ }
  return 'vc-xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

// ── Détection hors-ligne : navigator.onLine + une sonde ping ────────────────
// `navigator.onLine` seul ment parfois (Wi-Fi associé mais sans Internet
// réel) : une sonde HTTP légère (injectable — un vrai `fetch('/health/')` en
// prod, un mock en test) confirme la perte réseau réelle avant de mettre une
// vente en file plutôt que de tenter l'appel direct.
export async function estHorsLigne({ ping } = {}) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true
  if (!ping) return false
  try {
    await ping()
    return false
  } catch {
    return true
  }
}

export class OfflineVenteQueue {
  // store : { load(), save(ops) } ; sender : async(payload) => réponse serveur
  // (POST /api/django/pos/ventes/ avec le payload tel quel, uuid_client inclus).
  constructor({ store = memoryStore(), sender } = {}) {
    this.store = store
    this.sender = sender
    this._ops = null
    this._flushing = false
  }

  async _ensureLoaded() {
    if (this._ops === null) this._ops = await this.store.load()
    return this._ops
  }

  async _persist() { await this.store.save(this._ops) }

  // Met une vente hors-ligne en file. `payload` voyagera tel quel au serveur
  // (client, note…). Génère (ou reprend) l'`uuid_client` de cette vente et le
  // renvoie — à afficher sur le ticket local en attendant le rejeu.
  async enqueue(payload = {}, { uuidClient } = {}) {
    await this._ensureLoaded()
    const uuid_client = uuidClient || makeUuidClient()
    this._ops.push({
      uuid_client,
      payload: { ...payload, uuid_client },
      queuedAt: new Date().toISOString(),
      attempts: 0,
      nextAttemptAt: 0,
    })
    await this._persist()
    return uuid_client
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

  // Ops actuellement en erreur serveur (refus 4xx, pas un problème réseau) —
  // jamais retirées silencieusement, restent visibles pour un abandon
  // explicite (même règle que l'outbox terrain existant).
  async failed() {
    await this._ensureLoaded()
    return this._ops.filter((op) => !!op.serverError)
  }

  async discard(uuidClient) {
    await this._ensureLoaded()
    this._ops = this._ops.filter((op) => op.uuid_client !== uuidClient)
    await this._persist()
  }

  _backoffDelay(attempts) {
    const idx = Math.min(Math.max(attempts - 1, 0), BACKOFF_STEPS_MS.length - 1)
    return BACKOFF_STEPS_MS[idx]
  }

  /**
   * Rejoue la file FIFO. Une op dont le backoff n'est pas écoulé est sautée
   * (sans bloquer les suivantes déjà mûres). Le serveur dédupe sur
   * `uuid_client` : rejouer une op déjà appliquée est un no-op sûr (la
   * réponse renvoie la vente existante) — l'op est retirée normalement.
   * Échec RÉSEAU (pas de réponse serveur) → on s'arrête, file intacte, on
   * retentera. Refus SERVEUR (4xx réel) → l'op reste en file marquée
   * `serverError`, jamais un échec muet.
   */
  async flush({ now = Date.now() } = {}) {
    if (this._flushing) {
      return { skipped: true, flushed: 0, remaining: await this.count() }
    }
    if (!this.sender) throw new Error('OfflineVenteQueue: aucun « sender » configuré.')
    this._flushing = true
    let flushed = 0
    try {
      await this._ensureLoaded()
      for (const op of [...this._ops]) {
        if (op.nextAttemptAt && op.nextAttemptAt > now) continue
        try {
          await this.sender(op.payload)
          this._ops = this._ops.filter((x) => x.uuid_client !== op.uuid_client)
          flushed += 1
          await this._persist()
        } catch (err) {
          const reseau = !err?.response
          const attempts = (op.attempts || 0) + 1
          this._ops = this._ops.map((x) => {
            if (x.uuid_client !== op.uuid_client) return x
            const next = { ...x, attempts, nextAttemptAt: now + this._backoffDelay(attempts) }
            if (!reseau) {
              next.serverError = err?.response?.data?.detail || 'Refusée par le serveur.'
            }
            return next
          })
          await this._persist()
          if (reseau) break // réseau retombé : on s'arrête, file intacte
        }
      }
      return { skipped: false, flushed, remaining: this._ops.length }
    } finally {
      this._flushing = false
    }
  }
}

// ── Instance partagée + auto-flush au retour réseau ─────────────────────────
let _shared = null

export function getOfflineVenteQueue(senderFn) {
  if (!_shared) {
    _shared = new OfflineVenteQueue({ store: createOfflineStore(), sender: senderFn })
  }
  return _shared
}

// Câble le flush automatique sur l'événement navigateur `online`. Renvoie une
// fonction de nettoyage (désinscription) — utile pour les tests/démontage.
export function wireAutoFlush(queue) {
  if (typeof window === 'undefined') return () => {}
  const onOnline = () => { queue.flush().catch(() => undefined) }
  window.addEventListener('online', onOnline)
  return () => window.removeEventListener('online', onOnline)
}

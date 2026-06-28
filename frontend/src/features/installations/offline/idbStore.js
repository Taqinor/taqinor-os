// N91/F21 — adaptateur IndexedDB pour l'outbox de capture terrain.
//
// Persiste la file d'opérations hors-ligne dans IndexedDB pour qu'elle SURVIVE
// à une fermeture d'onglet / un rechargement (un technicien qui perd le réseau
// sur un toit ne doit rien perdre). Expose load()/save(ops) — la même surface
// que `memoryStore`, donc l'outbox ne sait pas lequel l'alimente.
//
// Repli localStorage si IndexedDB est absent ; repli mémoire en dernier ressort
// (jamais d'exception). Tout est défensif : un store cassé ne fait pas planter
// la capture, il dégrade juste la persistance.

const DB_NAME = 'taqinor-field-outbox'
const STORE = 'ops'
const KEY = 'queue'

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
      try { localStorage.setItem(k, JSON.stringify(ops)) } catch { /* quota / privé */ }
    },
  }
}

function memoryAdapter() {
  let data = []
  return {
    async load() { return [...data] },
    async save(ops) { data = [...ops] },
  }
}

// Choisit le meilleur store disponible dans l'environnement courant.
export function createFieldOutboxStore() {
  try {
    if (typeof indexedDB !== 'undefined' && indexedDB) return idbAdapter()
  } catch { /* repli */ }
  try {
    if (typeof localStorage !== 'undefined' && localStorage) return localStorageAdapter()
  } catch { /* repli */ }
  return memoryAdapter()
}

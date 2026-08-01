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
// EZ8 — la file BINAIRE (photos) vit dans le MÊME object store, sous une autre
// clé : un seul outbox, une seule base, deux files (JSON / binaire).
const BINARY_KEY = 'queue-binaire'

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

function idbAdapter(key = KEY) {
  return {
    async load() {
      const db = await openDb()
      return new Promise((resolve) => {
        const tx = db.transaction(STORE, 'readonly')
        const req = tx.objectStore(STORE).get(key)
        req.onsuccess = () => resolve(Array.isArray(req.result) ? req.result : [])
        req.onerror = () => resolve([])
      })
    },
    async save(ops) {
      const db = await openDb()
      return new Promise((resolve) => {
        const tx = db.transaction(STORE, 'readwrite')
        tx.objectStore(STORE).put(ops, key)
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

// EZ8 — store de la file BINAIRE. PAS de repli localStorage : un ArrayBuffer
// n'y survit pas (JSON.stringify le réduirait à `{}` — une photo silencieusement
// vidée serait pire que pas de file du tout). Sans IndexedDB, on retombe sur la
// mémoire et on le DIT (`persistent: false`) pour que l'UI reste honnête : la
// file ne survivra pas à la fermeture de l'onglet.
export function createBinaryOutboxStore() {
  try {
    if (typeof indexedDB !== 'undefined' && indexedDB) {
      return { store: idbAdapter(BINARY_KEY), persistent: true }
    }
  } catch { /* repli */ }
  return { store: memoryAdapter(), persistent: false }
}

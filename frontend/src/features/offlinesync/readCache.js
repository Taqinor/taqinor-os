// NTMOB27 — Cache de LECTURE hors-ligne des fiches consultées récemment.
//
// FRONTIÈRE ABSOLUE : ce cache ne sert QU'À LIRE. Aucune action d'écriture ne
// passe par lui — les écritures hors-ligne vivent (et vivront) dans l'outbox
// dédiée, jamais ici. Rien de ce qui est lu ici ne peut être renvoyé au serveur.
//
// Contenu : les N dernières fiches OUVERTES (lead / client / devis / chantier /
// équipement…), cap configurable, éviction LRU. Chaque entrée retient son
// horodatage pour que l'écran affiche « Données hors-ligne, dernière synchro à
// HH:MM » plutôt que de faire passer une donnée périmée pour fraîche.
//
// Le module est PUR et testable : on lui injecte un `store` (IndexedDB dans le
// navigateur, mémoire dans les tests). Stockage indisponible (mode privé, SSR,
// quota) → le cache devient un NO-OP silencieux : l'app marche exactement comme
// avant, simplement sans lecture hors-ligne.

export const CAP_DEFAUT = 30
const DB_NAME = 'taqinor-read-cache'
const STORE_NAME = 'fiches'

/** Clé stable d'une fiche : type + identifiant. */
export function cleFiche(type, id) {
  return `${type}:${id}`
}

/** Adaptateur mémoire — défaut hors navigateur et base des tests. */
export function memoryStore(initial = {}) {
  let data = { ...initial }
  return {
    async load() { return { ...data } },
    async save(entries) { data = { ...entries } },
  }
}

/**
 * Adaptateur IndexedDB. Renvoie un `memoryStore` si IndexedDB est
 * indisponible : le cache dégrade alors en cache de session, jamais en erreur.
 */
export function idbStore() {
  if (typeof indexedDB === 'undefined') return memoryStore()

  const ouvrir = () => new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE_NAME)) {
        req.result.createObjectStore(STORE_NAME)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })

  return {
    async load() {
      try {
        const db = await ouvrir()
        return await new Promise((resolve, reject) => {
          const tx = db.transaction(STORE_NAME, 'readonly')
          const req = tx.objectStore(STORE_NAME).get('entries')
          req.onsuccess = () => resolve(req.result || {})
          req.onerror = () => reject(req.error)
        })
      } catch {
        return {}
      }
    },
    async save(entries) {
      try {
        const db = await ouvrir()
        await new Promise((resolve, reject) => {
          const tx = db.transaction(STORE_NAME, 'readwrite')
          tx.objectStore(STORE_NAME).put(entries, 'entries')
          tx.oncomplete = () => resolve()
          tx.onerror = () => reject(tx.error)
        })
      } catch { /* quota/mode privé : le cache est simplement sans effet */ }
    },
  }
}

/**
 * createReadCache — cache LRU borné, en LECTURE SEULE.
 *  • `put(type, id, data, now)` mémorise la fiche + son horodatage ;
 *  • `get(type, id)` renvoie `{ data, cachedAt }` ou `null` ;
 *  • au-delà de `cap` entrées, la plus ANCIENNEMENT consultée est évincée.
 */
export function createReadCache({ store = memoryStore(), cap = CAP_DEFAUT } = {}) {
  return {
    async put(type, id, data, now = Date.now()) {
      if (id == null || data == null) return
      const entries = await store.load()
      entries[cleFiche(type, id)] = { data, cachedAt: now }
      const cles = Object.keys(entries)
      if (cles.length > cap) {
        // Éviction LRU : on garde les `cap` entrées les plus récentes.
        cles
          .sort((a, b) => (entries[b].cachedAt || 0) - (entries[a].cachedAt || 0))
          .slice(cap)
          .forEach((k) => { delete entries[k] })
      }
      await store.save(entries)
    },

    async get(type, id) {
      const entries = await store.load()
      return entries[cleFiche(type, id)] || null
    },

    async taille() {
      return Object.keys(await store.load()).length
    },

    async vider() {
      await store.save({})
    },
  }
}

/** Cache partagé de l'application (IndexedDB), cap 30 fiches. */
export const readCache = createReadCache({ store: idbStore() })

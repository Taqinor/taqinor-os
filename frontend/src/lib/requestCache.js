/* O66 — Cache GET minimaliste, TTL, OPT-IN.
   ============================================================================
   IMPORTANT — ADOPTION VOLONTAIRE UNIQUEMENT.
   Ce module N'EST PAS branché sur l'instance axios globale et ne modifie EN
   RIEN le comportement par défaut de l'app : il n'est actif que pour les
   appelants qui l'utilisent explicitement. On NE met JAMAIS en cache toutes les
   requêtes globalement (risque de données périmées) — seul un appelant qui sait
   que sa ressource est « lente à changer » (ex. catalogue, paramètres) peut
   choisir d'envelopper son GET ici.

   Utilisation typique (opt-in) :

     import { cachedGet } from '../lib/requestCache'
     import api from '../api/axios'

     // 60 s de TTL ; les appels concurrents partagent la même promesse.
     const produits = await cachedGet('catalogue', () => api.get('/stock/produits/'))

   - Clé = chaîne fournie par l'appelant (à lui de la rendre unique/paramétrée).
   - TTL en millisecondes (défaut 30 s). Une entrée expirée est rejouée.
   - Déduplication en vol : pendant qu'un GET est en cours, les appels avec la
     même clé attendent la MÊME promesse (un seul appel réseau).
   - Une promesse rejetée n'est PAS mise en cache (on réessaiera au prochain appel).
   - `invalidate(key)` / `clearCache()` pour purger après une mutation. */

const store = new Map() // key -> { value, expiresAt } | { promise }

const DEFAULT_TTL = 30_000

/**
 * Récupère une valeur en cache (si fraîche) ou exécute `fetcher` et met en cache.
 * @param {string} key            clé de cache unique côté appelant
 * @param {() => Promise<any>} fetcher  fabrique la valeur (ex. `() => api.get(url)`)
 * @param {{ ttl?: number }} [opts]     TTL en ms (défaut 30 000)
 * @returns {Promise<any>}
 */
export function cachedGet(key, fetcher, { ttl = DEFAULT_TTL } = {}) {
  const now = Date.now()
  const hit = store.get(key)

  // Entrée résolue et encore fraîche.
  if (hit && hit.expiresAt !== undefined && hit.expiresAt > now) {
    return Promise.resolve(hit.value)
  }
  // Requête déjà en vol pour cette clé : on partage la promesse.
  if (hit && hit.promise) {
    return hit.promise
  }

  const promise = Promise.resolve()
    .then(fetcher)
    .then((value) => {
      store.set(key, { value, expiresAt: Date.now() + ttl })
      return value
    })
    .catch((err) => {
      // Échec : on ne met rien en cache (on réessaiera au prochain appel).
      store.delete(key)
      throw err
    })

  store.set(key, { promise })
  return promise
}

/** Purge une entrée précise (ex. après une mutation qui invalide la ressource). */
export function invalidate(key) {
  store.delete(key)
}

/** Vide tout le cache. */
export function clearCache() {
  store.clear()
}

export default cachedGet

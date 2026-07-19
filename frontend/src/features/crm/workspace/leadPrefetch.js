// LW24 — Pré-chargement des voisins de file (J/K instantané). Module PUR
// (aucun import React) : Map(id → {data, at}) TTL 60s, alimentée au repos
// (requestIdleCallback, repli setTimeout 300ms). Consommée par LOAD_LEAD
// (useLeadDraft.js) pour un PREMIER RENDU instantané — le GET frais repart
// quand même en arrière-plan et remplace (garde `res.id===leadId` du
// réducteur, cf. draftCore SET_SERVER) : ce cache n'est JAMAIS une source de
// vérité, juste une accélération perçue (recon 03 #24, patron Linear adapté
// à l'échelle 2 utilisateurs — zéro dépendance).

const TTL_MS = 60_000

// Cache module-level : partagé par toutes les instances de LeadWorkspace
// (une seule à la fois dans cet ERP), survit à une navigation J/K.
const cache = new Map()

/** getPrefetched — donnée en cache pour `id`, ou `null` si absente/expirée. */
export function getPrefetched(id) {
  if (id == null) return null
  const entry = cache.get(id)
  if (!entry) return null
  if (Date.now() - entry.at > TTL_MS) {
    cache.delete(id)
    return null
  }
  return entry.data
}

/** setPrefetched — pose/écrase l'entrée de `id`, horodatée maintenant. */
export function setPrefetched(id, data) {
  if (id == null || !data) return
  cache.set(id, { data, at: Date.now() })
}

/** clearPrefetched — retire une entrée (ex. après une erreur de fetch). */
export function clearPrefetched(id) {
  cache.delete(id)
}

/** resetPrefetchCache — vide tout le cache (tests uniquement). */
export function resetPrefetchCache() {
  cache.clear()
}

// requestIdleCallback avec repli setTimeout(delay) — Safari/Firefox n'ont pas
// rIC natif, node:test non plus, donc le repli est le chemin le plus testé.
function idle(cb, delay) {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    return { kind: 'idle', handle: window.requestIdleCallback(cb) }
  }
  return { kind: 'timeout', handle: setTimeout(cb, delay) }
}

function cancelIdle(ref) {
  if (!ref) return
  if (ref.kind === 'idle' && typeof window !== 'undefined' && typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(ref.handle)
  } else {
    clearTimeout(ref.handle)
  }
}

/**
 * schedulePrefetch — pré-charge en idle les `ids` donnés via `fetchFn(id)`
 * (Promise résolvant la donnée COMPLÈTE d'un lead). Les ids déjà en cache
 * frais sont sautés silencieusement ; aucun id valide → aucun timer posé
 * (« pas de fetch sans file »). Renvoie une fonction d'annulation (cleanup
 * d'effet React) qui empêche le déclenchement s'il n'a pas encore eu lieu.
 */
export function schedulePrefetch(ids, fetchFn, { delay = 300 } = {}) {
  const targets = [...new Set((ids || []).filter((id) => id != null))]
    .filter((id) => !getPrefetched(id))
  if (!targets.length) return () => {}
  const ref = idle(() => {
    for (const id of targets) {
      fetchFn(id)
        .then((data) => { if (data) setPrefetched(id, data) })
        .catch(() => { /* best-effort — un échec de pré-chargement est silencieux */ })
    }
  }, delay)
  return () => cancelIdle(ref)
}

export default { getPrefetched, setPrefetched, clearPrefetched, schedulePrefetch }

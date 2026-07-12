// VX170 — wrapper localStorage défensif : PLUS robuste que les petits helpers
// `safeGet/safeSet/safeRemove` réinventés localement (ex. `ui/useDraftAutosave.js`,
// VX62) qui abandonnent silencieusement dès que `setItem` lève. Ici, sur
// `QuotaExceededError` (Safari privé — quota ~0 — ou quota réellement plein),
// on ÉVINCE l'entrée la plus ANCIENNE sous le même préfixe puis on retente UNE
// fois, plutôt que de perdre la nouvelle écriture. Jamais de throw qui remonte
// à l'appelant : `safeSet` renvoie un booléen de succès.
//
// Consommé par `ui/useDirtyGuard.js` (persistance défensive `pagehide`, VX170)
// et, à terme, VX62/VX46/VX10/NTUX16 (mêmes brouillons localStorage).

const DEFAULT_PREFIX = 'taqinor:'

function isQuotaExceeded(err) {
  if (!err) return false
  return (
    err.name === 'QuotaExceededError'
    || err.name === 'NS_ERROR_DOM_QUOTA_REACHED' // Firefox
    || err.code === 22
    || err.code === 1014
  )
}

// Clé la plus ancienne sous `prefix` — par `savedAt` (ISO) quand la valeur en
// JSON l'expose (convention des brouillons de ce repo), sinon la première
// clé du préfixe rencontrée (ordre de `localStorage`, best-effort). Ne lève
// jamais : une lecture qui échoue est simplement ignorée pour le tri.
function oldestKey(prefix, storage) {
  let oldest = null
  let oldestAt = null
  for (let i = 0; i < storage.length; i += 1) {
    const k = storage.key(i)
    if (!k || !k.startsWith(prefix)) continue
    let at = null
    try {
      const parsed = JSON.parse(storage.getItem(k))
      at = parsed?.savedAt ? Date.parse(parsed.savedAt) : null
    } catch {
      at = null
    }
    if (oldest == null || (at != null && (oldestAt == null || at < oldestAt))) {
      oldest = k
      oldestAt = at
    }
  }
  return oldest
}

function storageOrNull() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    // Safari privé peut lever à l'ACCÈS même de `window.localStorage`.
    return null
  }
}

/** Lecture défensive — `null` si absent, invalide, ou localStorage indisponible. */
export function safeGet(key) {
  const storage = storageOrNull()
  if (!storage) return null
  try {
    const raw = storage.getItem(key)
    return raw == null ? null : JSON.parse(raw)
  } catch {
    return null
  }
}

/**
 * Écriture défensive avec éviction sur quota plein.
 * @param {string} key
 * @param {*} value           — sérialisé en JSON.
 * @param {{prefix?: string}} [options] — préfixe des clés candidates à éviction.
 * @returns {boolean} succès réel de l'écriture (jamais de throw).
 */
export function safeSet(key, value, { prefix = DEFAULT_PREFIX } = {}) {
  const storage = storageOrNull()
  if (!storage) return false
  const payload = JSON.stringify(value)
  try {
    storage.setItem(key, payload)
    return true
  } catch (err) {
    if (!isQuotaExceeded(err)) return false
    const victim = oldestKey(prefix, storage)
    if (!victim || victim === key) return false
    try { storage.removeItem(victim) } catch { /* no-op */ }
    try {
      storage.setItem(key, payload)
      return true
    } catch {
      return false
    }
  }
}

/** Suppression défensive — jamais de throw. */
export function safeRemove(key) {
  const storage = storageOrNull()
  if (!storage) return
  try { storage.removeItem(key) } catch { /* no-op */ }
}

export default { safeGet, safeSet, safeRemove }

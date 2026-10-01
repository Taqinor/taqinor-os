import { useCallback, useEffect, useRef, useState } from 'react'

/* VX62 — Brouillon auto pour les formulaires longs (générateur de devis, 20 min
   de saisie). Sauvegarde débouncée du snapshot dans localStorage, restauration au
   montage, purge au succès. Zéro dépendance externe, défensif face à un
   localStorage indisponible (Safari privé, QuotaExceededError).

   Usage :
     const { restored, restore, discard, clear } = useDraftAutosave(key, snapshot, {
       enabled: dirty,      // n'écrit que quand il y a réellement du contenu
     })
   - `restored` : l'objet brouillon trouvé au montage (ou null), avec `savedAt`.
   - `restore()` : renvoie le payload sauvegardé et masque le bandeau.
   - `discard()` : ignore le brouillon (le purge + masque le bandeau).
   - `clear()`  : purge sans toucher au bandeau (à appeler après un submit réussi).
   - QJR581 — option `version` (ex. `devis.updated_at`) : stockée avec le
     brouillon (`restored.version`) pour que l'appelant ne propose « Reprendre »
     que si l'objet serveur n'a pas bougé depuis (sinon il le purge).
*/

const DEBOUNCE_MS = 800
const PREFIX = 'taqinor:draft:'

function safeGet(storageKey) {
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function safeSet(storageKey, value) {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(value))
  } catch {
    /* localStorage plein / indisponible → on renonce silencieusement au brouillon */
  }
}

function safeRemove(storageKey) {
  try {
    window.localStorage.removeItem(storageKey)
  } catch {
    /* no-op */
  }
}

export function useDraftAutosave(key, snapshot, { enabled = true, version } = {}) {
  const storageKey = key ? PREFIX + key : null

  // Lecture UNE fois au montage (avant tout écrasement par l'autosave).
  const [restored, setRestored] = useState(() => (storageKey ? safeGet(storageKey) : null))
  // EZ4 — horodatage de la DERNIÈRE écriture réussie : la confiance vient de la
  // continuité VISIBLE (« Brouillon enregistré à HH:MM », patron Docs/Notion).
  // Ajout purement additif : les consommateurs existants l'ignorent.
  const [savedAt, setSavedAt] = useState(null)
  const timerRef = useRef(null)
  // Tant que l'utilisateur n'a pas tranché (restaurer/ignorer), on ne réécrit pas
  // par-dessus le brouillon existant — sinon un montage vide l'effacerait aussitôt.
  const decidedRef = useRef(restored == null)

  useEffect(() => {
    if (!storageKey || !enabled || !decidedRef.current) return undefined
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const stamp = new Date().toISOString()
      safeSet(storageKey, version === undefined
        ? { savedAt: stamp, data: snapshot }
        : { savedAt: stamp, version, data: snapshot })
      setSavedAt(stamp)
    }, DEBOUNCE_MS)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [storageKey, enabled, snapshot, version])

  const restore = useCallback(() => {
    const payload = restored?.data ?? null
    decidedRef.current = true
    setRestored(null)
    return payload
  }, [restored])

  const discard = useCallback(() => {
    if (storageKey) safeRemove(storageKey)
    decidedRef.current = true
    setRestored(null)
  }, [storageKey])

  const clear = useCallback(() => {
    if (storageKey) safeRemove(storageKey)
    if (timerRef.current) clearTimeout(timerRef.current)
    decidedRef.current = true
    setRestored(null)
    setSavedAt(null)
  }, [storageKey])

  return { restored, restore, discard, clear, savedAt }
}

export default useDraftAutosave

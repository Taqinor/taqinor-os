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

export function useDraftAutosave(key, snapshot, { enabled = true } = {}) {
  const storageKey = key ? PREFIX + key : null

  // Lecture UNE fois au montage (avant tout écrasement par l'autosave).
  const [restored, setRestored] = useState(() => (storageKey ? safeGet(storageKey) : null))
  const timerRef = useRef(null)
  // Tant que l'utilisateur n'a pas tranché (restaurer/ignorer), on ne réécrit pas
  // par-dessus le brouillon existant — sinon un montage vide l'effacerait aussitôt.
  const decidedRef = useRef(restored == null)

  useEffect(() => {
    if (!storageKey || !enabled || !decidedRef.current) return undefined
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      safeSet(storageKey, { savedAt: new Date().toISOString(), data: snapshot })
    }, DEBOUNCE_MS)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [storageKey, enabled, snapshot])

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
  }, [storageKey])

  return { restored, restore, discard, clear }
}

export default useDraftAutosave

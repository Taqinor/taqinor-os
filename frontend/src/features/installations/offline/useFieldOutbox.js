// N91/F21 — hook React : état en ligne/hors-ligne + flush auto de l'outbox.
//
// Monté une fois (par ex. dans le volet de capture terrain), il :
//   * suit l'état réseau (`online`) via les événements navigateur ;
//   * suit le nombre d'ops en attente (`pending`) ;
//   * vide automatiquement l'outbox au RETOUR du réseau (et au montage si déjà
//     en ligne avec une file non vide) ;
//   * expose `flush()` pour un déclenchement manuel (bouton « Synchroniser »).
import { useCallback, useEffect, useState } from 'react'
import { fieldOutbox } from './fieldOutbox'

export function useFieldOutbox() {
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine !== false,
  )
  const [pending, setPending] = useState(0)
  const [flushing, setFlushing] = useState(false)

  const refreshCount = useCallback(async () => {
    try { setPending(await fieldOutbox.count()) } catch { /* défensif */ }
  }, [])

  const flush = useCallback(async () => {
    setFlushing(true)
    try {
      const res = await fieldOutbox.flush()
      await refreshCount()
      return res
    } finally {
      setFlushing(false)
    }
  }, [refreshCount])

  useEffect(() => {
    refreshCount()
    const goOnline = () => { setOnline(true); flush() }
    const goOffline = () => setOnline(false)
    // Le service worker réveille la page (Background Sync) → on flushe.
    const onSwMessage = (e) => {
      if (e?.data?.type === 'FIELD_OUTBOX_FLUSH') flush()
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('online', goOnline)
      window.addEventListener('offline', goOffline)
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('message', onSwMessage)
      }
      // Flush au montage si déjà en ligne avec une file non vide.
      if (navigator.onLine !== false) flush()
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', goOnline)
        window.removeEventListener('offline', goOffline)
        if ('serviceWorker' in navigator) {
          navigator.serviceWorker.removeEventListener('message', onSwMessage)
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { online, pending, flushing, flush, refreshCount }
}

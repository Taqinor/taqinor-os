// N91/F21 — hook React : état en ligne/hors-ligne + flush auto de l'outbox.
//
// Monté une fois (par ex. dans le volet de capture terrain), il :
//   * suit l'état réseau (`online`) via les événements navigateur ;
//   * suit le nombre d'ops en attente (`pending`) ;
//   * vide automatiquement l'outbox au RETOUR du réseau (et au montage si déjà
//     en ligne avec une file non vide) ;
//   * expose `flush()` pour un déclenchement manuel (bouton « Synchroniser »).
//
// NTMOB1 — le hook agrège aussi les files PAR MODULE (crm, ventes, stock, sav)
// du moteur généralisé : le badge d'en-tête reste UNIQUE et son compteur
// comptabilise TOUT ce qui attend, quel que soit l'écran d'origine (décision
// VX105 : jamais un 2ᵉ badge, jamais un 2ᵉ compteur).
import { useCallback, useEffect, useState } from 'react'
import {
  discardModuleOp, flushModuleOutboxes, onOfflineOutboxChange, pendingModuleOps,
} from '../../../lib/offlineOutbox'
import { fieldOutbox, binaryOutbox } from './fieldOutbox'

export function useFieldOutbox() {
  const [online, setOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine !== false,
  )
  const [pending, setPending] = useState(0)
  // EZ8 — photos en attente : MÊME file, MÊME badge (jamais un 2ᵉ indicateur).
  const [pendingPhotos, setPendingPhotos] = useState(0)
  const [failed, setFailed] = useState([])
  const [flushing, setFlushing] = useState(false)

  const refreshCount = useCallback(async () => {
    try {
      const all = await fieldOutbox.pending()
      const fail = all.filter((op) => !!op.serverError)
      const bin = await binaryOutbox.pending()
      const binFail = bin.filter((op) => !!op.serverError)
      // NTMOB1 — files des autres modules : MÊME compteur, MÊME badge.
      const mods = await pendingModuleOps().catch(() => [])
      const modFail = mods.filter((op) => !!op.serverError)
      setPending((all.length - fail.length) + (mods.length - modFail.length))
      setPendingPhotos(bin.length - binFail.length)
      setFailed([...fail, ...binFail, ...modFail])
    } catch { /* défensif */ }
  }, [])

  const flush = useCallback(async () => {
    setFlushing(true)
    try {
      const res = await fieldOutbox.flush()
      // EZ8 — les photos partent dans le même geste (« Synchroniser » vide TOUT).
      const bin = await binaryOutbox.flush().catch(() => null)
      // NTMOB1 — et les files des autres modules avec (un seul geste, une
      // seule barre de progression : l'utilisateur ne synchronise pas « par
      // écran », il synchronise son terminal).
      const mods = await flushModuleOutboxes().catch(() => null)
      await refreshCount()
      const sortie = bin ? { ...res, photos: bin } : res
      return mods ? { ...sortie, modules: mods } : sortie
    } finally {
      setFlushing(false)
    }
  }, [refreshCount])

  // Abandon EXPLICITE d'une op en échec — la SEULE façon de la faire
  // disparaître (jamais un effet de bord du flush automatique).
  const discard = useCallback(async (clientOpId) => {
    await fieldOutbox.discard(clientOpId)
    // EZ8 — l'abandon explicite vaut aussi pour une photo refusée par le
    // serveur (l'id n'existe que dans une des deux files).
    await binaryOutbox.discard(clientOpId)
    // NTMOB1 — …et pour une op de module (l'id ne vit que dans UNE file).
    await discardModuleOp(clientOpId).catch(() => undefined)
    await refreshCount()
  }, [refreshCount])

  useEffect(() => {
    // Lecture initiale du compteur (état externe IndexedDB → React) ; c'est
    // exactement le rôle d'un effet de synchronisation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshCount()
    const goOnline = () => { setOnline(true); flush() }
    const goOffline = () => setOnline(false)
    // Le service worker réveille la page (Background Sync) → on flushe.
    const onSwMessage = (e) => {
      if (e?.data?.type === 'FIELD_OUTBOX_FLUSH') flush()
    }
    // NTMOB1 — une mise en file faite depuis N'IMPORTE quel écran rafraîchit le
    // badge d'en-tête immédiatement (aucun sondage périodique).
    const desabonner = onOfflineOutboxChange(() => { refreshCount() })
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
      desabonner()
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

  return {
    online, pending, pendingPhotos, failed, flushing, flush, refreshCount,
    discard, persistentPhotos: binaryOutbox.persistent,
  }
}

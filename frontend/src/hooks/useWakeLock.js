// NTMOB29 — Écran allumé pendant une session de capture active.
//
// Pendant une checklist chantier en cours d'édition, une prise de photo ou un
// scan de code-barres, l'écran s'éteignait au bout du délai système : le
// technicien devait le rallumer d'une main occupée. `navigator.wakeLock`
// (API standard, AUCUNE dépendance npm) maintient l'écran allumé tant que la
// session est ouverte, et la sentinelle est relâchée à la fermeture du panneau
// ou au démontage.
//
// Dégradation SILENCIEUSE : API absente (Safari ancien), permission refusée ou
// document en arrière-plan → le hook ne fait rien et ne lève jamais. Un
// retour au premier plan ré-acquiert la sentinelle (le navigateur la relâche
// automatiquement quand l'onglet est masqué).
import { useEffect, useRef } from 'react'

export function isWakeLockSupported() {
  return typeof navigator !== 'undefined' && 'wakeLock' in navigator
}

/**
 * @param {boolean} actif — true tant que la session de capture est ouverte.
 */
export default function useWakeLock(actif) {
  const sentinelleRef = useRef(null)

  useEffect(() => {
    if (!actif || !isWakeLockSupported()) return undefined
    let vivant = true

    const acquerir = async () => {
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return
      try {
        const sentinelle = await navigator.wakeLock.request('screen')
        if (!vivant) { sentinelle.release?.(); return }
        sentinelleRef.current = sentinelle
      } catch { /* refusée/indisponible : on continue sans, jamais d'erreur */ }
    }

    const onVisibility = () => {
      if (document.visibilityState === 'visible' && !sentinelleRef.current) acquerir()
    }

    acquerir()
    document.addEventListener('visibilitychange', onVisibility)

    return () => {
      vivant = false
      document.removeEventListener('visibilitychange', onVisibility)
      try {
        sentinelleRef.current?.release?.()
      } catch { /* déjà relâchée par le navigateur */ }
      sentinelleRef.current = null
    }
  }, [actif])
}

// VX56 — Hook partagé de sondage (short-poll) SENSIBLE À LA VISIBILITÉ de
// l'onglet. Extrait du patron déjà correct de
// `frontend/src/features/messaging/useChatPolling.js` (chat) pour que
// `NotificationBell.jsx` (`NotificationBell.jsx:198-210` avant ce commit)
// cesse de sonder un onglet caché — deux `setInterval` (30 s + 3 min) sans
// écoute `visibilitychange` gaspillaient radio/batterie/données sur le 4G des
// techniciens.
//
// Une ou plusieurs TÂCHES nommées, chacune avec sa propre cadence :
//   • amorçage immédiat au montage (sauf onglet déjà masqué),
//   • intervalle PROPRE par tâche tant que l'onglet est visible,
//   • coupé (`clearInterval`, aucun appel) dès que l'onglet est masqué,
//   • reprise avec rafraîchissement IMMÉDIAT de CHAQUE tâche au retour au
//     premier plan.
//
// N'introduit AUCUNE dépendance nouvelle : `setInterval` + l'API Page
// Visibility du navigateur, comme `useChatPolling`. Ne touche PAS au
// monitoring (VX30) ni aux onglets du panneau de notifications (VX14) — ce
// hook ne gère QUE le rythme des appels, jamais leur rendu.
import { useEffect, useRef } from 'react'

// Lecture défensive de la visibilité (jsdom/SSR : on suppose visible).
function isHidden() {
  try {
    return typeof document !== 'undefined' && document.visibilityState === 'hidden'
  } catch {
    return false
  }
}

/**
 * @param {Array<{ fn: () => void, intervalMs: number }>} tasks
 *   Chaque tâche est appelée immédiatement au montage puis à sa propre
 *   cadence `intervalMs`, tant que l'onglet est visible. `fn` doit être
 *   idempotente/sans argument (fermeture sur l'état appelant, comme
 *   `checkUnread`/`load` dans `NotificationBell`).
 * @param {{ enabled?: boolean }} [options]
 * @returns {{ resume: () => void }} `resume` réexécute immédiatement TOUTES
 *   les tâches (ex. bouton « Mise à jour interrompue — reprendre »).
 */
export default function useVisibilityAwarePolling(tasks, options = {}) {
  const { enabled = true } = options
  // Référence stable des tâches courantes : les callbacks d'intervalle lisent
  // toujours la DERNIÈRE version (fermetures re-créées à chaque rendu) sans
  // redémarrer les timers à chaque rendu.
  const tasksRef = useRef(tasks)
  const timersRef = useRef([])
  // Garder la référence à jour SANS muter pendant le rendu (react-hooks/refs) :
  // l'effet sans dépendances s'exécute après chaque commit, bien avant qu'un
  // timer d'intervalle (30 s+) ne lise `tasksRef.current`.
  useEffect(() => { tasksRef.current = tasks })

  const runAll = () => {
    tasksRef.current.forEach((t) => t.fn())
  }

  const stop = () => {
    timersRef.current.forEach((id) => clearInterval(id))
    timersRef.current = []
  }

  const start = () => {
    stop()
    if (!enabled) return
    timersRef.current = tasksRef.current.map((t) =>
      setInterval(() => t.fn(), t.intervalMs))
  }

  // Reprise manuelle : relance immédiatement toutes les tâches (ex. après une
  // panne prolongée signalée à l'utilisateur).
  const resume = () => {
    runAll()
  }

  useEffect(() => {
    if (!enabled) {
      stop()
      return undefined
    }
    // Amorçage immédiat (sauf onglet déjà masqué) puis démarrage des intervalles.
    if (!isHidden()) runAll()
    start()

    const onVisibility = () => {
      if (isHidden()) {
        // Onglet masqué : on coupe les intervalles pour ne rien sonder.
        stop()
      } else {
        // Retour au premier plan : rafraîchit tout de suite puis relance.
        runAll()
        start()
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled])

  return { resume }
}

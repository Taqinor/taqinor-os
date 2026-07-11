// VX86 — Compteur partagé des approbations en attente (boîte XKB1/ZCTR7-9),
// pour rendre l'inbox `/approbations` VISIBLE là où l'utilisateur regarde déjà
// (badge nav Sidebar, carte Dashboard, rangée cloche) sans tripler l'appel
// réseau : un seul hook, un seul `GET reporting/approbations-en-attente/`
// (total UNFILTRÉ, périmètre société résolu SERVEUR — jamais posté par le
// client), ré-utilisé par les trois consommateurs.
//
// Sondage périodique léger (30 s, comme `NotificationBell`'s `checkUnread`) ;
// se met en pause quand l'onglet est masqué (`document.visibilityState`) pour
// ne pas cogner l'API en arrière-plan — VX56 (`useVisibilityAwarePolling`)
// n'existe pas encore dans ce dépôt : ce hook implémente sa propre garde
// visibilité minimale et pourra migrer sur VX56 telle quelle plus tard sans
// changer sa forme de retour.
import { useEffect, useRef, useState } from 'react'
import reportingApi from '../api/reportingApi'

const POLL_MS = 30 * 1000

/**
 * @returns {{ total: number, loading: boolean, error: boolean }}
 *   `total` = nombre d'approbations en attente tous rôles/sources confondus
 *   pour la société de l'utilisateur courant ; 0 tant que rien n'est chargé
 *   ou en cas d'erreur (jamais de badge/carte affiché sur un `0` inventé —
 *   c'est aux consommateurs de vérifier `loading`/`error` avant de masquer).
 */
export function useApprobationsCount() {
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const aliveRef = useRef(true)

  useEffect(() => {
    aliveRef.current = true

    const load = () => {
      // Ne sonde pas un onglet masqué (économie réseau) ; le prochain sondage
      // visible ou le retour au premier plan rattrapera l'état réel.
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      reportingApi.approbationsEnAttente()
        .then((r) => {
          if (!aliveRef.current) return
          const items = r.data?.items ?? []
          setTotal(Array.isArray(items) ? items.length : 0)
          setError(false)
        })
        .catch(() => {
          if (!aliveRef.current) return
          setError(true)
        })
        .finally(() => {
          if (aliveRef.current) setLoading(false)
        })
    }

    load()
    const iv = setInterval(load, POLL_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      aliveRef.current = false
      clearInterval(iv)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  return { total, loading, error }
}

export default useApprobationsCount

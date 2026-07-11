import { useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import {
  fetchConversations,
  fetchUnreadCount,
  fetchMessages,
} from './store/messagingSlice'
// VX56 — cadence + suspension à la visibilité de l'onglet extraites dans un
// hook partagé (ce fichier en était le patron d'origine ; `NotificationBell`
// gaspillait radio/batterie/données sur un onglet caché faute de la même
// garde). Ce fichier ne garde que ce qui lui est propre : la RÉSOLUTION des
// trois sondages (Redux) + le suivi d'échecs PAR source.
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'

// VX204 — rien ne détectait une SÉRIE d'échecs de sondage (silence total :
// aucun `.catch`). Chaque source (liste / non-lus / messages actifs) a son
// PROPRE compteur d'échecs consécutifs — une source qui réussit ne doit
// jamais masquer une autre source en échec. `stalled` = au moins une source a
// atteint le seuil ; un succès de CETTE source relève aussitôt son compteur.
const STALL_THRESHOLD = 3

// S12 — Sondage intelligent (short-poll) du chat. Trois cadences :
//   • conversation OUVERTE : ~3 s (messages frais quasi temps réel),
//   • liste des conversations : plus lent (~15 s),
//   • compteur de non-lus (badge) : ~20 s.
// Le sondage est SUSPENDU quand l'onglet est masqué (visibilitychange) et
// reprend — avec un rafraîchissement immédiat — au retour, via
// `useVisibilityAwarePolling` (VX56).

export const ACTIVE_POLL_MS = 3000
export const LIST_POLL_MS = 15000
export const UNREAD_POLL_MS = 20000

export default function useChatPolling(
  activeConversationId,
  options = {},
) {
  const dispatch = useDispatch()
  const {
    activeMs = ACTIVE_POLL_MS,
    listMs = LIST_POLL_MS,
    unreadMs = UNREAD_POLL_MS,
    enabled = true,
  } = options

  // Référence stable de l'id actif pour les callbacks d'intervalle. On la met à
  // jour dans un effet (jamais pendant le rendu).
  const activeRef = useRef(activeConversationId)
  // Un compteur d'échecs consécutifs PAR source de sondage.
  const failCountsRef = useRef({ list: 0, unread: 0, active: 0 })
  const [stalled, setStalled] = useState(false)

  useEffect(() => {
    activeRef.current = activeConversationId
  }, [activeConversationId])

  // Comptabilise le résultat d'un dispatch de sondage pour SA source (rejected
  // → +1, sinon reset à 0). ≥3 échecs consécutifs sur une source → `stalled`;
  // un succès de cette même source le relève (les autres sources n'affectent
  // jamais son compteur).
  const trackResult = (source) => (action) => {
    const failed = action?.type?.endsWith('/rejected')
    const counts = failCountsRef.current
    counts[source] = failed ? counts[source] + 1 : 0
    setStalled(Object.values(counts).some((n) => n >= STALL_THRESHOLD))
  }

  const pollActive = () => {
    const id = activeRef.current
    if (id != null) dispatch(fetchMessages({ conversationId: id })).then(trackResult('active'))
  }
  const pollList = () => {
    dispatch(fetchConversations()).then(trackResult('list'))
  }
  const pollUnread = () => {
    dispatch(fetchUnreadCount()).then(trackResult('unread'))
  }

  // VX56 — la garde de visibilité (amorçage immédiat, suspension sur onglet
  // caché, rafraîchissement immédiat au retour) vit désormais dans le hook
  // partagé ; ce hook ne fournit que les TROIS tâches + leur cadence.
  const { resume } = useVisibilityAwarePolling(
    [
      { fn: pollActive, intervalMs: activeMs },
      { fn: pollList, intervalMs: listMs },
      { fn: pollUnread, intervalMs: unreadMs },
    ],
    { enabled },
  )

  return { stalled, resume }
}

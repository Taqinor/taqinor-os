import { useEffect, useRef } from 'react'
import { useDispatch } from 'react-redux'
import {
  fetchConversations,
  fetchUnreadCount,
  fetchMessages,
} from './store/messagingSlice'

// S12 — Sondage intelligent (short-poll) du chat. Trois cadences :
//   • conversation OUVERTE : ~3 s (messages frais quasi temps réel),
//   • liste des conversations : plus lent (~15 s),
//   • compteur de non-lus (badge) : ~20 s.
// Le sondage est SUSPENDU quand l'onglet est masqué (visibilitychange) et
// reprend — avec un rafraîchissement immédiat — au retour. Aucune dépendance
// nouvelle : setInterval + l'API Page Visibility du navigateur.

export const ACTIVE_POLL_MS = 3000
export const LIST_POLL_MS = 15000
export const UNREAD_POLL_MS = 20000

// Lecture défensive de la visibilité (jsdom/SSR : on suppose visible).
function isHidden() {
  try {
    return typeof document !== 'undefined' && document.visibilityState === 'hidden'
  } catch {
    return false
  }
}

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
  const timersRef = useRef([])

  useEffect(() => {
    activeRef.current = activeConversationId
  }, [activeConversationId])

  const pollActive = () => {
    if (isHidden()) return
    const id = activeRef.current
    if (id != null) dispatch(fetchMessages({ conversationId: id }))
  }
  const pollList = () => {
    if (isHidden()) return
    dispatch(fetchConversations())
  }
  const pollUnread = () => {
    if (isHidden()) return
    dispatch(fetchUnreadCount())
  }

  const stop = () => {
    timersRef.current.forEach((t) => clearInterval(t))
    timersRef.current = []
  }

  const start = () => {
    stop()
    if (!enabled) return
    timersRef.current = [
      setInterval(pollActive, activeMs),
      setInterval(pollList, listMs),
      setInterval(pollUnread, unreadMs),
    ]
  }

  useEffect(() => {
    if (!enabled) {
      stop()
      return undefined
    }
    // Amorçage immédiat (sauf si onglet masqué) puis démarrage des intervalles.
    pollList()
    pollUnread()
    pollActive()
    start()

    const onVisibility = () => {
      if (isHidden()) {
        // Onglet masqué : on coupe les intervalles pour ne rien sonder.
        stop()
      } else {
        // Retour au premier plan : rafraîchit tout de suite puis relance.
        pollList()
        pollUnread()
        pollActive()
        start()
      }
    }

    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, enabled, activeMs, listMs, unreadMs])
}

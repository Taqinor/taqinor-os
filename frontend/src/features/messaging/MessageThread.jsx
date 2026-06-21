import { useEffect, useRef, useState, useCallback } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Pin } from 'lucide-react'
import { Spinner } from '../../ui'
import MessageBubble from './MessageBubble'
import { bubbleTime } from './time'
import {
  selectMessages,
  selectActiveId,
  selectPinned,
  fetchOlderMessages,
  upsertConversation,
  toggleReaction,
} from './store/messagingSlice'
import messagesApi from '../../api/messagesApi'
import { toastError } from '../../lib/toast'

/* S15 — Pane de droite : fil de messages. Bulles own/others, slots pièce-
   jointe/vocal/carte, scroll infini INVERSÉ (charge les plus anciens en haut),
   auto-scroll au plus récent à l'envoi/arrivée, barre des messages épinglés,
   état de lecture. `onEditMessage` remonte au Composer (S16). */

const NEAR_TOP = 40 // px : seuil de déclenchement du chargement des anciens
const NEAR_BOTTOM = 80 // px : on n'auto-scrolle que si l'utilisateur est en bas

export default function MessageThread({ currentUserId, onEditMessage, onDeleteMessage, nextOlder }) {
  const dispatch = useDispatch()
  const messages = useSelector(selectMessages)
  const activeId = useSelector(selectActiveId)
  const pinned = useSelector(selectPinned)
  const scrollRef = useRef(null)
  const bottomRef = useRef(null)
  const prevLenRef = useRef(0)
  const prevHeightRef = useRef(0)
  const [loadingOlder, setLoadingOlder] = useState(false)

  // Auto-scroll au plus récent quand un message ARRIVE (longueur en hausse) et
  // que l'utilisateur est déjà en bas — on ne le tire pas vers le bas s'il lit
  // d'anciens messages.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const grew = messages.length > prevLenRef.current
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM
    if (grew && (atBottom || prevLenRef.current === 0)) {
      bottomRef.current?.scrollIntoView({ block: 'end' })
    }
    prevLenRef.current = messages.length
  }, [messages])

  // Quand on charge des messages PLUS ANCIENS, on préserve la position visuelle
  // (on compense le saut de hauteur) pour un scroll infini inversé fluide.
  const loadOlder = useCallback(async () => {
    if (loadingOlder || !nextOlder || activeId == null) return
    const el = scrollRef.current
    prevHeightRef.current = el ? el.scrollHeight : 0
    setLoadingOlder(true)
    const before = messages[0]?.id
    await dispatch(fetchOlderMessages({ conversationId: activeId, before }))
    setLoadingOlder(false)
    requestAnimationFrame(() => {
      const node = scrollRef.current
      if (node) node.scrollTop = node.scrollHeight - prevHeightRef.current
    })
  }, [dispatch, activeId, messages, nextOlder, loadingOlder])

  const onScroll = (e) => {
    if (e.currentTarget.scrollTop <= NEAR_TOP) loadOlder()
  }

  const handleTogglePin = async (m) => {
    try {
      if (m.pinned) await messagesApi.unpinMessage(m.id)
      else await messagesApi.pinMessage(m.id)
      if (activeId != null) {
        dispatch(upsertConversation({ id: activeId }))
      }
    } catch (err) {
      toastError(err.response?.data?.detail || 'Action impossible')
    }
  }

  const handleReact = (m, emoji) => {
    dispatch(toggleReaction({ messageId: m.id, emoji, userId: currentUserId }))
    messagesApi.toggleReaction(m.id, emoji).catch(() => {})
  }

  return (
    <div className="chat-thread flex min-h-0 flex-1 flex-col" data-testid="message-thread">
      {pinned.length > 0 && (
        <div className="chat-pinned-bar" role="region" aria-label="Messages épinglés">
          <Pin size={14} aria-hidden="true" />
          <ul className="chat-pinned-list">
            {pinned.map((p) => (
              <li key={p.id} className="chat-pinned-item" title={p.body}>
                <span>{p.body || 'Pièce jointe'}</span>
                <span className="chat-pinned-time">{bubbleTime(p.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="chat-thread-scroll flex-1 overflow-y-auto px-3 py-2" ref={scrollRef} onScroll={onScroll}>
        {nextOlder && (
          <div className="chat-thread-older">
            {loadingOlder ? <Spinner size="sm" /> : (
              <button type="button" onClick={loadOlder}>Charger les anciens messages</button>
            )}
          </div>
        )}
        {messages.length === 0 ? (
          <div className="chat-thread-empty">Aucun message pour l’instant.</div>
        ) : (
          messages.map((m, i) => {
            const prev = messages[i - 1]
            const own = m.sender?.id === currentUserId
            // Regroupe les messages consécutifs du même auteur (en-tête masqué).
            const showHeader = !prev || prev.sender?.id !== m.sender?.id
            return (
              <MessageBubble
                key={m.id}
                message={m}
                own={own}
                showHeader={showHeader}
                onEdit={own ? onEditMessage : undefined}
                onDelete={own ? onDeleteMessage : undefined}
                onTogglePin={handleTogglePin}
                onReact={handleReact}
              />
            )
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

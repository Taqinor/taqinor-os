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
   état de lecture. `onEditMessage` remonte au Composer (S16).
   VX118(a) — les classes `chat-thread-*`/`chat-pinned-*` n'avaient AUCUNE
   règle CSS (bandeau épinglé sans fond/bordure) ; migré sur Tailwind, zéro
   CSS ajouté. */

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
    <div className="flex min-h-0 flex-1 flex-col" data-testid="message-thread">
      {pinned.length > 0 && (
        <div
          className="flex items-start gap-2 border-b border-border bg-accent/30 px-3 py-2 text-sm"
          role="region"
          aria-label="Messages épinglés"
        >
          <Pin size={14} className="mt-0.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <ul className="flex min-w-0 flex-1 flex-wrap gap-x-4 gap-y-1">
            {pinned.map((p) => (
              <li key={p.id} className="flex min-w-0 items-center gap-1.5 truncate" title={p.body}>
                <span className="truncate">{p.body || 'Pièce jointe'}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{bubbleTime(p.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        className="flex-1 overflow-y-auto px-3 py-2"
        ref={scrollRef}
        onScroll={onScroll}
        role="log"
        tabIndex={0}
        aria-live="polite"
        aria-relevant="additions"
      >
        {nextOlder && (
          <div className="flex justify-center py-2">
            {loadingOlder ? <Spinner size="sm" /> : (
              <button
                type="button"
                onClick={loadOlder}
                className="text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                Charger les anciens messages
              </button>
            )}
          </div>
        )}
        {messages.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Aucun message pour l’instant.</div>
        ) : (
          messages.map((m, i) => {
            const prev = messages[i - 1]
            const own = m.sender?.id === currentUserId
            // Regroupe les messages consécutifs du même auteur (en-tête masqué).
            const showHeader = !prev || prev.sender?.id !== m.sender?.id
            // aria-relevant="additions" (ci-dessus) n'annonce QUE le dernier
            // message poussé dans le log — pas tout l'historique déjà rendu.
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

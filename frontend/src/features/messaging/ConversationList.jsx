import { useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Search, Plus, Hash, BellOff } from 'lucide-react'
import { Avatar, AvatarFallback, Badge, Input, initials } from '../../ui'
import { selectConversations, selectActiveId } from './store/messagingSlice'
import { shortTime, conversationTitle, displayName } from './time'

/* S14 — Pane de gauche : liste des conversations (DMs + canaux) avec avatar,
   dernier message, horodatage, badge de non-lus, recherche, indicateur muet,
   et un "+" pour démarrer un DM / créer un canal. Construit sur @/ui. */

function lastPreview(conv) {
  const lm = conv.last_message
  if (!lm) return 'Aucun message'
  if (lm.deleted) return 'Message supprimé'
  if (lm.attachment_count || lm.has_attachment) return '📎 Pièce jointe'
  return lm.body || ''
}

export default function ConversationList({ onSelect, onNew, currentUserId }) {
  const conversations = useSelector(selectConversations)
  const activeId = useSelector(selectActiveId)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return conversations
    return conversations.filter((c) => {
      const title = conversationTitle(c, currentUserId).toLowerCase()
      const preview = lastPreview(c).toLowerCase()
      return title.includes(q) || preview.includes(q)
    })
  }, [conversations, query, currentUserId])

  return (
    <div className="chat-list flex h-full flex-col" data-testid="conversation-list">
      <div className="chat-list-head flex items-center gap-2 border-b border-border p-2">
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher…"
          leading={<Search aria-hidden="true" />}
          aria-label="Rechercher une conversation"
        />
        <button type="button" className="chat-list-new" onClick={onNew}
                aria-label="Nouvelle conversation" title="Nouvelle conversation">
          <Plus size={18} aria-hidden="true" />
        </button>
      </div>

      <ul className="chat-list-items flex-1 overflow-y-auto" role="list">
        {filtered.length === 0 ? (
          <li className="chat-list-empty">Aucune conversation</li>
        ) : (
          filtered.map((c) => {
            const title = conversationTitle(c, currentUserId)
            const isChannel = c.kind === 'channel' || !!c.name
            const unread = c.unread_count || 0
            return (
              <li key={c.id}>
                <button
                  type="button"
                  className={`chat-list-item${c.id === activeId ? ' active' : ''}${unread ? ' unread' : ''}`}
                  onClick={() => onSelect?.(c.id)}
                  aria-current={c.id === activeId ? 'true' : undefined}
                >
                  <Avatar className="chat-list-avatar">
                    <AvatarFallback>
                      {isChannel ? <Hash size={16} aria-hidden="true" /> : (initials(title) || '?')}
                    </AvatarFallback>
                  </Avatar>
                  <span className="chat-list-body">
                    <span className="chat-list-row">
                      <span className="chat-list-title">
                        {title}
                        {c.muted && (
                          <BellOff size={12} aria-label="Notifications coupées"
                                   className="chat-list-mute" />
                        )}
                      </span>
                      <span className="chat-list-time">
                        {shortTime(c.last_message?.created_at || c.updated_at)}
                      </span>
                    </span>
                    <span className="chat-list-row">
                      <span className="chat-list-preview">
                        {c.last_message?.sender && isChannel && (
                          <strong>{displayName(c.last_message.sender)}: </strong>
                        )}
                        {lastPreview(c)}
                      </span>
                      {unread > 0 && (
                        <Badge tone="primary" className="chat-list-badge">
                          {unread > 99 ? '99+' : unread}
                        </Badge>
                      )}
                    </span>
                  </span>
                </button>
              </li>
            )
          })
        )}
      </ul>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Search, Plus, Hash, BellOff } from 'lucide-react'
import { Avatar, AvatarFallback, Badge, Input, initials } from '../../ui'
import { cn } from '../../lib/cn'
import { selectConversations, selectActiveId } from './store/messagingSlice'
import { shortTime, conversationTitle, displayName } from './time'

/* S14 — Pane de gauche : liste des conversations (DMs + canaux) avec avatar,
   dernier message, horodatage, badge de non-lus, recherche, indicateur muet,
   et un "+" pour démarrer un DM / créer un canal. Construit sur @/ui.
   VX118(a) — les classes `chat-list-*` n'avaient AUCUNE règle dans les 5
   fichiers CSS du repo (styles navigateur nus) ; migré sur des primitives
   déjà tokenisées (`cn()` + Tailwind), zéro CSS ajouté. */

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
    <div className="flex h-full flex-col" data-testid="conversation-list">
      <div className="flex items-center gap-2 border-b border-border p-2">
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Rechercher…"
          leading={<Search aria-hidden="true" />}
          aria-label="Rechercher une conversation"
        />
        <button
          type="button"
          onClick={onNew}
          aria-label="Nouvelle conversation"
          title="Nouvelle conversation"
          className="flex size-9 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-ring"
        >
          <Plus size={18} aria-hidden="true" />
        </button>
      </div>

      <ul className="flex-1 overflow-y-auto" role="list">
        {filtered.length === 0 ? (
          <li className="px-3 py-6 text-center text-sm text-muted-foreground">Aucune conversation</li>
        ) : (
          filtered.map((c) => {
            const title = conversationTitle(c, currentUserId)
            const isChannel = c.kind === 'channel' || !!c.name
            const unread = c.unread_count || 0
            const isActive = c.id === activeId
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelect?.(c.id)}
                  aria-current={isActive ? 'true' : undefined}
                  className={cn(
                    'flex w-full items-start gap-2.5 border-b border-border/60 px-3 py-2.5 text-left transition-colors hover:bg-muted/50',
                    isActive && 'bg-primary/5',
                    unread > 0 && 'bg-accent/20',
                  )}
                >
                  <Avatar>
                    <AvatarFallback>
                      {isChannel ? <Hash size={16} aria-hidden="true" /> : (initials(title) || '?')}
                    </AvatarFallback>
                  </Avatar>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="flex items-center justify-between gap-2">
                      <span className={cn('flex items-center gap-1 truncate text-sm', unread > 0 ? 'font-semibold text-foreground' : 'font-medium text-foreground')}>
                        {title}
                        {c.muted && (
                          <BellOff size={12} aria-label="Notifications coupées"
                                   className="shrink-0 text-muted-foreground" />
                        )}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {shortTime(c.last_message?.created_at || c.updated_at)}
                      </span>
                    </span>
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm text-muted-foreground">
                        {c.last_message?.sender && isChannel && (
                          <strong className="text-foreground">{displayName(c.last_message.sender)}: </strong>
                        )}
                        {lastPreview(c)}
                      </span>
                      {unread > 0 && (
                        <Badge tone="primary" className="shrink-0">
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

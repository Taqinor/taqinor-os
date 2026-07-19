import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Search, Plus, Hash, BellOff, Moon, Smile, X } from 'lucide-react'
import { Avatar, AvatarFallback, Badge, Input, initials } from '../../ui'
import { cn } from '../../lib/cn'
import messagesApi from '../../api/messagesApi'
import { selectConversations, selectActiveId } from './store/messagingSlice'
import { shortTime, conversationTitle, displayName } from './time'

// WIR156 / XKB26 — barre « mon statut » : statut personnalisé (emoji + texte),
// Ne pas déranger (DND), et effacement. Le statut est toujours celui de
// l'appelant côté serveur. Autonome : charge/écrit via messagesApi.status.
function MyStatusBar() {
  const [me, setMe] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ status_emoji: '', status_text: '' })

  // messagesApi.status peut être absent (mocks partiels préexistants dans
  // d'autres tests) : dégrade silencieusement plutôt que de faire planter
  // tout le sous-arbre de rendu.
  const load = () => {
    // setMe est différé (jamais appelé de façon synchrone dans l'effet, même
    // sur le chemin dégradé) pour respecter react-hooks/set-state-in-effect.
    if (!messagesApi.status?.me) return Promise.resolve().then(() => setMe(null))
    return messagesApi.status.me()
      .then((r) => setMe(r.data)).catch(() => setMe(null))
  }
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!messagesApi.status?.setStatus) return
    try {
      const r = await messagesApi.status.setStatus({
        status_emoji: draft.status_emoji, status_text: draft.status_text,
      })
      setMe(r.data); setEditing(false)
    } catch { /* best-effort */ }
  }
  const clear = async () => {
    if (!messagesApi.status?.clear) return
    try { const r = await messagesApi.status.clear(); setMe(r.data) }
    catch { /* best-effort */ }
  }
  const toggleDnd = async () => {
    if (!messagesApi.status?.setDnd) return
    try {
      const active = me?.is_dnd
      const body = active
        ? { start: null, end: null }
        : { start: new Date().toISOString(),
          end: new Date(Date.now() + 8 * 3600 * 1000).toISOString() }
      const r = await messagesApi.status.setDnd(body)
      setMe(r.data)
    } catch { /* best-effort */ }
  }

  const hasStatus = me && (me.status_emoji || me.status_text)

  return (
    <div className="border-b border-border px-2 py-1.5" data-testid="my-status-bar">
      {editing ? (
        <div className="flex items-center gap-1.5">
          <Input value={draft.status_emoji}
            onChange={(e) => setDraft((d) => ({ ...d, status_emoji: e.target.value }))}
            placeholder="🙂" aria-label="Emoji de statut" className="w-14" />
          <Input value={draft.status_text}
            onChange={(e) => setDraft((d) => ({ ...d, status_text: e.target.value }))}
            placeholder="En réunion…" aria-label="Texte de statut" className="flex-1" />
          <button type="button" onClick={save} aria-label="Enregistrer le statut"
            className="rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-muted">OK</button>
        </div>
      ) : (
        <div className="flex items-center gap-1.5">
          <button type="button"
            onClick={() => { setDraft({ status_emoji: me?.status_emoji || '', status_text: me?.status_text || '' }); setEditing(true) }}
            className="flex min-w-0 flex-1 items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-sm hover:bg-muted focus-ring"
            aria-label="Définir mon statut">
            {hasStatus
              ? <span className="truncate"><span aria-hidden="true">{me.status_emoji}</span> {me.status_text}</span>
              : <span className="flex items-center gap-1 text-muted-foreground"><Smile size={14} aria-hidden="true" /> Définir un statut</span>}
          </button>
          {hasStatus && (
            <button type="button" onClick={clear} aria-label="Effacer mon statut"
              className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-ring">
              <X size={14} aria-hidden="true" />
            </button>
          )}
          <button type="button" onClick={toggleDnd}
            aria-label={me?.is_dnd ? 'Désactiver Ne pas déranger' : 'Activer Ne pas déranger'}
            aria-pressed={!!me?.is_dnd}
            className={cn('rounded-md p-1 focus-ring hover:bg-muted',
              me?.is_dnd ? 'text-destructive' : 'text-muted-foreground hover:text-foreground')}>
            <Moon size={14} aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  )
}

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
  // WIR156 — statuts des collègues (indicateur emoji / DND dans la liste).
  const [colleagues, setColleagues] = useState({})
  useEffect(() => {
    if (!messagesApi.status?.colleagues) return
    messagesApi.status.colleagues()
      .then((r) => {
        const byId = {}
        for (const st of (r.data ?? [])) byId[st.user_id] = st
        setColleagues(byId)
      })
      .catch(() => { /* best-effort : aucun indicateur si l'appel échoue */ })
  }, [])

  // Statut du pair d'un DM (autre membre que moi), sinon null.
  const peerStatus = (conv) => {
    if (conv.kind === 'channel' || conv.name) return null
    const peer = (conv.members || []).find((m) => m.id !== currentUserId)
    return peer ? colleagues[peer.id] : null
  }

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
      {/* WIR156 — mon statut / DND en haut de la liste. */}
      <MyStatusBar />
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
            const peer = peerStatus(c)
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
                        {peer?.is_dnd && (
                          <Moon size={12} aria-label="Ne pas déranger"
                            className="shrink-0 text-destructive" />
                        )}
                        {peer?.status_emoji && (
                          <span aria-label="Statut du collègue" className="shrink-0">{peer.status_emoji}</span>
                        )}
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

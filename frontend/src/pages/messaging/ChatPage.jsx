import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Settings2, MessageSquare } from 'lucide-react'
import useChatPolling from '../../features/messaging/useChatPolling'
import ConversationList from '../../features/messaging/ConversationList'
import MessageThread from '../../features/messaging/MessageThread'
import Composer from '../../features/messaging/Composer'
import NewConversation from '../../features/messaging/NewConversation'
import ManageMembers from '../../features/messaging/ManageMembers'
import {
  fetchConversations,
  fetchMessages,
  fetchPinned,
  markConversationRead,
  clearConversationUnread,
  setActiveConversation,
  selectActiveId,
  selectActiveConversation,
} from '../../features/messaging/store/messagingSlice'
import { conversationTitle } from '../../features/messaging/time'

/* S13 — Écran /messages : shell deux-panneaux (liste | fil), réactif
   (drill-down un seul panneau sur mobile). Coordonne le store, le polling, et
   les modales de création / gestion des membres. Cible du deep-link push :
   /messages?c=<id>. */
export default function ChatPage() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const activeId = useSelector(selectActiveId)
  const activeConv = useSelector(selectActiveConversation)
  const nextOlder = useSelector((s) => s.messaging.nextOlder)
  const currentUser = useSelector((s) => s.auth.user)
  const currentUserId = currentUser?.id

  const [newOpen, setNewOpen] = useState(false)
  const [membersOpen, setMembersOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)

  // Charge la liste une fois, et le polling intelligent prend le relais.
  useEffect(() => {
    dispatch(fetchConversations())
  }, [dispatch])

  // Deep-link : /messages?c=<id> ouvre directement la conversation.
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const c = params.get('c')
    if (c && Number(c) !== activeId) dispatch(setActiveConversation(Number(c)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search])

  // À l'ouverture d'une conversation : charge le fil + épingles, marque lu.
  useEffect(() => {
    if (activeId == null) return
    dispatch(fetchMessages({ conversationId: activeId }))
    dispatch(fetchPinned(activeId))
    dispatch(clearConversationUnread(activeId))
    dispatch(markConversationRead({ conversationId: activeId }))
  }, [dispatch, activeId])

  const { stalled: pollingStalled, resume: resumePolling } = useChatPolling(activeId)

  const members = useMemo(() => {
    const list = activeConv?.members ?? []
    return list.map((m) => ({
      id: m.id,
      value: String(m.id),
      label: m.full_name || [m.first_name, m.last_name].filter(Boolean).join(' ') || m.username || `#${m.id}`,
      username: m.username,
    }))
  }, [activeConv])

  const openConversation = (id) => {
    dispatch(setActiveConversation(id))
    navigate(`/messages?c=${id}`, { replace: true })
  }

  const isChannel = activeConv && (activeConv.kind === 'channel' || !!activeConv.name)
  const isAdmin = !!(activeConv?.members || []).find(
    (m) => m.id === currentUserId && m.is_admin,
  )

  return (
    <div className="chat-shell-wrap flex h-[calc(100dvh-8rem)] flex-col gap-2">
      {pollingStalled && (
        <button
          type="button"
          className="chat-stalled-banner flex shrink-0 items-center justify-center gap-1.5 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/15"
          onClick={resumePolling}
        >
          Mise à jour interrompue — cliquer pour reprendre
        </button>
      )}
      <div
        className={`chat-shell${activeId != null ? ' has-active' : ''} grid min-h-0 flex-1 gap-3 md:grid-cols-[320px_1fr]`}
        data-testid="chat-page"
      >
      <aside
        className={`chat-pane-list min-h-0 overflow-hidden rounded-lg border border-border bg-card ${activeId != null ? 'hidden md:block' : 'block'}`}
      >
        <ConversationList
          onSelect={openConversation}
          onNew={() => setNewOpen(true)}
          currentUserId={currentUserId}
        />
      </aside>

      <section
        className={`chat-pane-thread flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card ${activeId == null ? 'hidden md:flex' : 'flex'}`}
      >
        {activeId == null ? (
          <div className="chat-pane-placeholder flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <MessageSquare size={40} aria-hidden="true" />
            <p>Sélectionnez une conversation</p>
          </div>
        ) : (
          <>
            <header className="chat-thread-head flex items-center gap-2 border-b border-border px-3 py-2">
              <button type="button" className="chat-thread-back md:hidden"
                      onClick={() => dispatch(setActiveConversation(null))}
                      aria-label="Retour à la liste">
                <ArrowLeft size={18} aria-hidden="true" />
              </button>
              <span className="chat-thread-title flex-1 truncate font-semibold">
                {conversationTitle(activeConv, currentUserId)}
              </span>
              {isChannel && (
                <button type="button" className="chat-thread-manage text-muted-foreground hover:text-foreground"
                        onClick={() => setMembersOpen(true)}
                        aria-label="Gérer les membres">
                  <Settings2 size={18} aria-hidden="true" />
                </button>
              )}
            </header>

            <MessageThread
              currentUserId={currentUserId}
              nextOlder={nextOlder}
              onEditMessage={setEditing}
              onDeleteMessage={setPendingDelete}
            />

            <Composer
              members={members}
              editing={editing}
              onEditDone={() => setEditing(null)}
              pendingDelete={pendingDelete}
              onDeleteResolved={() => setPendingDelete(null)}
            />
          </>
        )}
      </section>
      </div>

      <NewConversation
        open={newOpen}
        onOpenChange={setNewOpen}
        onCreated={(id) => navigate(`/messages?c=${id}`, { replace: true })}
      />
      {activeConv && (
        <ManageMembers
          open={membersOpen}
          onOpenChange={setMembersOpen}
          conversation={activeConv}
          currentUserId={currentUserId}
          isAdmin={isAdmin}
          onLeft={() => {
            setMembersOpen(false)
            dispatch(setActiveConversation(null))
            dispatch(fetchConversations())
          }}
        />
      )}
    </div>
  )
}

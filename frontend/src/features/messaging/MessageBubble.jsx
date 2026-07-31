import { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Paperclip, FileText, Pin, PinOff, Pencil, Check, MoreHorizontal, Trash2,
  Clock, Bookmark, BookmarkCheck, Send,
} from 'lucide-react'
import {
  Avatar, AvatarFallback, initials, Spinner,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../ui'
import { cn } from '../../lib/cn'
import messagesApi from '../../api/messagesApi'
import { toastError, toastSuccess } from '../../lib/toast'
import { sendMessage } from './store/messagingSlice'
import { bubbleTime, displayName } from './time'
import VoiceMessage from './VoiceMessage'
import Reactions from './Reactions'
import { renderRichText } from './richText'

/* S15/S17/S18 — Une bulle de message. `own` distingue mes messages (alignés à
   droite) des autres. Les emplacements pièce-jointe / vocal / carte-
   enregistrement sont des SLOTS de rendu : ils s'affichent selon le type des
   données du message, sans logique réseau.
   S18 : on lit `m.is_pinned` (le serializer expose `is_pinned`, pas `pinned`),
   on agrège `m.reactions` (liste plate de lignes) en puces, et le menu (…)
   porte épingler / désépingler + édition / suppression de ses messages.

   WIR155 — trois actions rapides additionnelles, toutes self-contained
   (aucun prop remonté à MessageThread/ChatPage, hors périmètre WIR155) :
     - « Répondre en fil » + fil inline (`ThreadPanel`, XKB24) : la réponse
       est postée via `/reply/` puis fusionnée dans le store en dispatchant
       manuellement `sendMessage.fulfilled` (même reducer qu'un envoi normal —
       aucun nouveau thunk) ;
     - « Me rappeler » (2 raccourcis horaires, XKB27) ;
     - favori personnel (toggle, XKB27) — état gardé localement (le
       serializer de liste des messages n'expose pas `is_bookmarked`, la
       vérité serveur vit dans l'onglet « Favoris » de `ConversationList`) ;
     - rendu options/vote/résultats d'un sondage (`PollBlock`, XKB30). */

function PollBlock({ message, currentUserId }) {
  const [poll, setPoll] = useState(null)
  const [loading, setLoading] = useState(true)
  const [voting, setVoting] = useState(false)

  useEffect(() => {
    let alive = true
    // Différé d'un microtask : un setState synchrone dans le corps d'un effet
    // déclenche un rendu en cascade (react-hooks/set-state-in-effect).
    Promise.resolve().then(() => { if (alive) setLoading(true) })
    messagesApi.poll.results(message.id)
      .then((r) => { if (alive) setPoll(r.data) })
      .catch(() => { if (alive) setPoll(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [message.id])

  if (loading || !poll) return null

  const totalVotes = poll.options.reduce((s, o) => s + o.vote_count, 0)
  const closed = !!poll.closed_at
  const isOwner = (message.sender_detail?.id ?? message.sender?.id) === currentUserId

  const toggleVote = async (optionId) => {
    if (closed || voting) return
    const already = (poll.my_vote_option_ids || []).includes(optionId)
    const next = poll.allow_multiple
      ? (already
        ? poll.my_vote_option_ids.filter((id) => id !== optionId)
        : [...poll.my_vote_option_ids, optionId])
      : (already ? [] : [optionId])
    setVoting(true)
    try {
      const res = await messagesApi.poll.vote(message.id, next)
      setPoll(res.data)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Vote impossible')
    } finally {
      setVoting(false)
    }
  }

  const closePoll = async () => {
    try {
      const res = await messagesApi.poll.close(message.id)
      setPoll(res.data)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Clôture impossible')
    }
  }

  return (
    <div className="mt-1 flex flex-col gap-1.5 rounded-md border border-border bg-card/60 p-2">
      <p className="text-sm font-medium text-foreground">{poll.question}</p>
      <ul className="flex flex-col gap-1">
        {poll.options.map((o) => {
          const pct = totalVotes > 0 ? Math.round((o.vote_count / totalVotes) * 100) : 0
          const mine = (poll.my_vote_option_ids || []).includes(o.id)
          return (
            <li key={o.id}>
              <button
                type="button"
                disabled={closed || voting}
                onClick={() => toggleVote(o.id)}
                aria-pressed={mine}
                className={cn(
                  'relative w-full overflow-hidden rounded border px-2 py-1.5 text-left text-sm',
                  mine ? 'border-primary' : 'border-border',
                  (closed || voting) ? 'cursor-default' : 'hover:border-primary/60',
                )}
              >
                <span
                  className="absolute inset-y-0 left-0 bg-primary/10"
                  style={{ width: `${pct}%` }}
                  aria-hidden="true"
                />
                <span className="relative flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1">
                    {mine && <Check size={12} className="text-primary" aria-hidden="true" />}
                    {o.label}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">{o.vote_count} · {pct}%</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {totalVotes} vote{totalVotes > 1 ? 's' : ''}
          {poll.is_anonymous ? ' · anonyme' : ''}
          {closed ? ' · clôturé' : ''}
        </span>
        {isOwner && !closed && (
          <button type="button" onClick={closePoll} className="font-medium text-foreground hover:underline">
            Clôturer
          </button>
        )}
      </div>
    </div>
  )
}

// WIR155 / XKB24 — fil inline : « N réponses » (ou « Répondre en fil » si le
// fil est vide) bascule un panneau listant les réponses + une mini zone de
// saisie. Restreint aux messages RACINE (`!m.reply_to`) — un fil reste sur un
// seul niveau (miroir du modèle `ThreadFollow.root_message`).
function ThreadPanel({ message }) {
  const dispatch = useDispatch()
  const [open, setOpen] = useState(false)
  const [replies, setReplies] = useState([])
  const [loading, setLoading] = useState(false)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await messagesApi.threads.list(message.id)
      setReplies(res.data || [])
    } catch {
      setReplies([])
    } finally {
      setLoading(false)
    }
  }

  const toggle = () => {
    setOpen((v) => {
      const next = !v
      if (next) load()
      return next
    })
  }

  const submit = async () => {
    const body = draft.trim()
    if (!body || sending) return
    setSending(true)
    try {
      const res = await messagesApi.threads.reply(message.id, { body })
      setReplies((r) => [...r, res.data])
      // Fusionne aussi dans le fil principal (même conversation, ordre
      // chronologique) — voir la note en tête de fichier.
      dispatch(sendMessage.fulfilled(res.data, `reply-${res.data?.id ?? Date.now()}`, {}))
      setDraft('')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Réponse impossible')
    } finally {
      setSending(false)
    }
  }

  const replyCount = message.reply_count || 0

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={toggle}
        className="text-xs font-medium text-primary hover:underline"
      >
        {replyCount > 0 ? `${replyCount} réponse${replyCount > 1 ? 's' : ''}` : 'Répondre en fil'}
      </button>
      {open && (
        <div className="mt-1 flex flex-col gap-1.5 border-l-2 border-border pl-2">
          {loading && <Spinner size="sm" />}
          {!loading && replies.map((r) => (
            <div key={r.id} className="text-sm">
              <span className="font-medium text-foreground">{displayName(r.sender_detail || r.sender)}</span>{' '}
              <span className="text-muted-foreground">{r.body}</span>
            </div>
          ))}
          <div className="flex items-center gap-1.5">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submit() } }}
              placeholder="Répondre en fil…"
              aria-label="Répondre en fil"
              className="w-full flex-1 rounded-md border border-input bg-card px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <button
              type="button"
              onClick={submit}
              disabled={!draft.trim() || sending}
              aria-label="Envoyer la réponse"
              className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
            >
              <Send size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function Attachment({ att }) {
  const isImage = (att.mime || att.content_type || '').startsWith('image/')
  if (isImage && att.url) {
    return (
      <a href={att.url} target="_blank" rel="noreferrer" className="chat-att-image">
        <img src={att.url} alt={att.filename || att.name || 'pièce jointe'} loading="lazy" />
      </a>
    )
  }
  return (
    <a href={att.url} target="_blank" rel="noreferrer" className="chat-att-file">
      <Paperclip size={14} aria-hidden="true" />
      <span>{att.filename || att.name || 'Fichier'}</span>
    </a>
  )
}

function RecordCard({ message }) {
  // Le serializer expose shared_label / shared_url. On retombe sur un éventuel
  // objet `record` (rendu local optimiste) pour la rétro-compatibilité.
  const label = message.shared_label || message.record?.label
  if (!label) return null
  const url = message.shared_url || message.record?.link || '#'
  const subtitle = message.record?.subtitle
  return (
    <a href={url} className="chat-record-card">
      <FileText size={15} aria-hidden="true" />
      <span className="chat-record-meta">
        <strong>{label}</strong>
        {subtitle && <span>{subtitle}</span>}
      </span>
    </a>
  )
}

// Une pièce jointe vocale est rendue par VoiceMessage ; les autres par Attachment.
function isVoice(att) {
  return att.kind === 'voice' || (att.mime || att.content_type || '').startsWith('audio/')
}

export default function MessageBubble({
  message,
  own = false,
  showHeader = true,
  currentUserId,
  onEdit,
  onDelete,
  onTogglePin,
  onReact,
}) {
  const m = message
  const sender = m.sender || m.sender_detail || {}
  const deleted = m.deleted || m.is_deleted || m.deleted_at != null
  const pinned = m.is_pinned ?? m.pinned
  // Repli sur l'utilisateur courant du store si le parent ne l'a pas fourni.
  const authUserId = useSelector((s) => s.auth?.user?.id)
  const me = currentUserId ?? authUserId

  const attachments = m.attachments || []
  const voiceAtts = attachments.filter(isVoice)
  const otherAtts = attachments.filter((a) => !isVoice(a))
  // Rétro-compat : un slot `m.voice` direct (rendu optimiste) reste supporté.
  const legacyVoice = m.voice
  const isPoll = m.kind === 'poll'
  // WIR155 — un fil ne se répond qu'au message RACINE (pas de fil-de-fil).
  const canThread = !deleted && !m.reply_to

  // WIR155 / XKB27 — « Me rappeler ce message » (2 raccourcis horaires,
  // suffisants pour le cas d'usage courant — pas de sélecteur de date libre
  // ici, gardé simple et sans nouvelle dépendance de date-picker).
  const remindMe = async (hours) => {
    try {
      const remindAt = new Date(Date.now() + hours * 3600 * 1000).toISOString()
      await messagesApi.remindMe(m.id, remindAt)
      toastSuccess('Rappel programmé.')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Rappel impossible')
    }
  }

  // WIR155 / XKB27 — favori personnel. Pas d'état serveur dans le
  // serializer de liste (`is_bookmarked` non exposé) : bascule locale +
  // confirmation par toast, la vérité serveur vit dans l'onglet « Favoris »
  // de ConversationList.
  const [bookmarked, setBookmarked] = useState(false)
  const toggleBookmark = async () => {
    try {
      const res = await messagesApi.toggleBookmark(m.id)
      const added = res.data?.status === 'added'
      setBookmarked(added)
      toastSuccess(added ? 'Ajouté aux favoris.' : 'Retiré des favoris.')
    } catch (err) {
      toastError(err.response?.data?.detail || 'Action impossible')
    }
  }

  return (
    <div className={`chat-bubble-row${own ? ' own' : ''}`} data-testid="message-bubble">
      {!own && showHeader && (
        <Avatar className="chat-bubble-avatar">
          <AvatarFallback>{initials(displayName(sender)) || '?'}</AvatarFallback>
        </Avatar>
      )}
      <div className="chat-bubble-stack">
        {showHeader && !own && (
          <span className="chat-bubble-author">{displayName(sender)}</span>
        )}
        <div className={`chat-bubble${deleted ? ' deleted' : ''}`}>
          {pinned && <Pin size={12} aria-label="Épinglé" className="chat-bubble-pin" />}

          {deleted ? (
            <em className="chat-bubble-deleted">Message supprimé</em>
          ) : (
            <>
              <RecordCard message={m} />
              {/* XKB29 — rendu sûr du gras/italique/code/listes/liens (aucun
                  dangerouslySetInnerHTML : renderRichText construit un arbre
                  d'éléments React, un payload script reste du texte). */}
              {m.body && <p className="chat-bubble-text">{renderRichText(m.body)}</p>}
              {legacyVoice && (
                <VoiceMessage messageId={m.id} attachment={legacyVoice} />
              )}
              {voiceAtts.map((att) => (
                <VoiceMessage key={att.id} messageId={m.id} attachment={att} />
              ))}
              {otherAtts.map((att) => (
                <Attachment key={att.id} att={att} />
              ))}
              {isPoll && <PollBlock message={m} currentUserId={me} />}
            </>
          )}

          <span className="chat-bubble-meta">
            {(m.edited || m.edited_at != null) && (
              <span className="chat-bubble-edited">modifié</span>
            )}
            <span className="chat-bubble-time">{bubbleTime(m.created_at)}</span>
            {own && m.read_by_count > 0 && (
              <Check size={12} aria-label="Lu" className="chat-bubble-read" />
            )}
          </span>
        </div>

        {!deleted && (m.reactions?.length > 0 || onReact) && (
          <Reactions
            reactions={m.reactions}
            currentUserId={me}
            onToggle={onReact ? (emoji) => onReact(m, emoji) : undefined}
          />
        )}

        {/* WIR155 — le fil reste disponible même sans callback de pin/édition
            (auparavant le menu (…) n'apparaissait que si le parent branchait
            une action ; remind/favori/fil sont désormais self-contained). */}
        {!deleted && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="chat-bubble-menu" aria-label="Actions du message">
                <MoreHorizontal size={14} aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align={own ? 'end' : 'start'}>
              {onTogglePin && (
                <DropdownMenuItem onSelect={() => onTogglePin(m)}>
                  {pinned ? <PinOff size={14} aria-hidden="true" /> : <Pin size={14} aria-hidden="true" />}
                  {pinned ? 'Désépingler' : 'Épingler'}
                </DropdownMenuItem>
              )}
              {own && onEdit && (
                <DropdownMenuItem onSelect={() => onEdit(m)}>
                  <Pencil size={14} aria-hidden="true" /> Modifier
                </DropdownMenuItem>
              )}
              {own && onDelete && (
                <DropdownMenuItem destructive onSelect={() => onDelete(m)}>
                  <Trash2 size={14} aria-hidden="true" /> Supprimer
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => remindMe(1)}>
                <Clock size={14} aria-hidden="true" /> Me rappeler dans 1 h
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => remindMe(24)}>
                <Clock size={14} aria-hidden="true" /> Me rappeler demain
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={toggleBookmark}>
                {bookmarked ? <BookmarkCheck size={14} aria-hidden="true" /> : <Bookmark size={14} aria-hidden="true" />}
                {bookmarked ? 'Retirer des favoris' : 'Ajouter aux favoris'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        {/* WIR155 / XKB24 — fil inline (répondre + réponses), messages racine
            uniquement. */}
        {canThread && <ThreadPanel message={m} />}
      </div>
    </div>
  )
}

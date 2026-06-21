import { useSelector } from 'react-redux'
import {
  Paperclip, FileText, Pin, PinOff, Pencil, Check, MoreHorizontal, Trash2,
} from 'lucide-react'
import {
  Avatar, AvatarFallback, initials,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../ui'
import { bubbleTime, displayName } from './time'
import VoiceMessage from './VoiceMessage'
import Reactions from './Reactions'

/* S15/S17/S18 — Une bulle de message. `own` distingue mes messages (alignés à
   droite) des autres. Les emplacements pièce-jointe / vocal / carte-
   enregistrement sont des SLOTS de rendu : ils s'affichent selon le type des
   données du message, sans logique réseau.
   S18 : on lit `m.is_pinned` (le serializer expose `is_pinned`, pas `pinned`),
   on agrège `m.reactions` (liste plate de lignes) en puces, et le menu (…)
   porte épingler / désépingler + édition / suppression de ses messages. */

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
              {m.body && <p className="chat-bubble-text">{m.body}</p>}
              {legacyVoice && (
                <VoiceMessage messageId={m.id} attachment={legacyVoice} />
              )}
              {voiceAtts.map((att) => (
                <VoiceMessage key={att.id} messageId={m.id} attachment={att} />
              ))}
              {otherAtts.map((att) => (
                <Attachment key={att.id} att={att} />
              ))}
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

        {!deleted && (onTogglePin || (own && (onEdit || onDelete))) && (
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
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  )
}

import { Paperclip, Mic, FileText, Pin, Pencil, Check } from 'lucide-react'
import { Avatar, AvatarFallback, initials } from '../../ui'
import { bubbleTime, displayName } from './time'

/* S15 — Une bulle de message. `own` distingue mes messages (alignés à droite)
   des autres. Les emplacements pièce-jointe / vocal / carte-enregistrement sont
   des SLOTS de rendu : ils s'affichent selon le type des données du message,
   sans logique réseau. */

function Attachment({ att }) {
  const isImage = (att.content_type || '').startsWith('image/')
  if (isImage && att.url) {
    return (
      <a href={att.url} target="_blank" rel="noreferrer" className="chat-att-image">
        <img src={att.url} alt={att.name || 'pièce jointe'} loading="lazy" />
      </a>
    )
  }
  return (
    <a href={att.url} target="_blank" rel="noreferrer" className="chat-att-file">
      <Paperclip size={14} aria-hidden="true" />
      <span>{att.name || 'Fichier'}</span>
    </a>
  )
}

function VoiceNote({ voice }) {
  return (
    <div className="chat-voice" aria-label="Note vocale">
      <Mic size={14} aria-hidden="true" />
      {voice.url ? (
        <audio controls src={voice.url} className="chat-voice-audio" />
      ) : (
        <span>Note vocale</span>
      )}
      {voice.duration != null && <span className="chat-voice-dur">{voice.duration}s</span>}
    </div>
  )
}

function RecordCard({ record }) {
  return (
    <a href={record.link || '#'} className="chat-record-card">
      <FileText size={15} aria-hidden="true" />
      <span className="chat-record-meta">
        <strong>{record.label || record.record_type}</strong>
        {record.subtitle && <span>{record.subtitle}</span>}
      </span>
    </a>
  )
}

export default function MessageBubble({
  message,
  own = false,
  showHeader = true,
  onEdit,
  onDelete,
  onTogglePin,
}) {
  const m = message
  const sender = m.sender || {}
  const deleted = m.deleted || m.is_deleted

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
          {m.pinned && <Pin size={12} aria-label="Épinglé" className="chat-bubble-pin" />}

          {deleted ? (
            <em className="chat-bubble-deleted">Message supprimé</em>
          ) : (
            <>
              {m.record && <RecordCard record={m.record} />}
              {m.body && <p className="chat-bubble-text">{m.body}</p>}
              {m.voice && <VoiceNote voice={m.voice} />}
              {(m.attachments || []).map((att) => (
                <Attachment key={att.id} att={att} />
              ))}
            </>
          )}

          <span className="chat-bubble-meta">
            {m.edited && <span className="chat-bubble-edited">modifié</span>}
            <span className="chat-bubble-time">{bubbleTime(m.created_at)}</span>
            {own && m.read_by_count > 0 && (
              <Check size={12} aria-label="Lu" className="chat-bubble-read" />
            )}
          </span>
        </div>

        {!deleted && (
          <span className="chat-bubble-actions">
            {onTogglePin && (
              <button type="button" onClick={() => onTogglePin(m)}
                      aria-label={m.pinned ? 'Désépingler' : 'Épingler'}>
                <Pin size={13} aria-hidden="true" />
              </button>
            )}
            {own && onEdit && (
              <button type="button" onClick={() => onEdit(m)} aria-label="Modifier">
                <Pencil size={13} aria-hidden="true" />
              </button>
            )}
            {own && onDelete && (
              <button type="button" onClick={() => onDelete(m)} aria-label="Supprimer"
                      className="chat-bubble-del">
                ×
              </button>
            )}
          </span>
        )}
      </div>
    </div>
  )
}

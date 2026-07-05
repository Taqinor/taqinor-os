import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Send, Paperclip, X } from 'lucide-react'
import {
  Button, FileUpload,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import messagesApi from '../../api/messagesApi'
import { toastError } from '../../lib/toast'
import {
  sendMessage, editMessage, deleteMessage, selectActiveId,
} from './store/messagingSlice'
import MentionAutocomplete from './MentionAutocomplete'
import { activeMention, insertMention, filterMembers, extractMentions } from './mentions'
import { applyShortcut } from './richText'

/* S16 — Composer : zone de saisie auto-dimensionnée, autocomplétion @mention
   (membres de la société), bouton joindre (image/fichier via FileUpload),
   envoi. Édition en ligne + suppression de SES propres messages avec
   confirmation AlertDialog. `editing` (message) bascule en mode édition ;
   `pendingDelete` arme le dialogue de confirmation (piloté par le parent). */

const MAX_ROWS_PX = 160

export default function Composer({
  members = [],
  editing,
  onEditDone,
  pendingDelete,
  onDeleteResolved,
}) {
  const dispatch = useDispatch()
  const activeId = useSelector(selectActiveId)
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState([]) // {id, name}
  const [sending, setSending] = useState(false)
  const [mention, setMention] = useState(null) // { items, index, start, queryLen }
  const taRef = useRef(null)

  // Bascule en mode édition : préremplit le texte.
  useEffect(() => {
    if (editing) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- préremplir le texte à l'entrée en mode édition
      setText(editing.body || '')
      taRef.current?.focus()
    }
  }, [editing])

  // Auto-dimensionnement de la zone de texte.
  const autosize = () => {
    const el = taRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_ROWS_PX)}px`
  }
  useEffect(autosize, [text])

  const updateMention = (value, caret) => {
    const tok = activeMention(value, caret)
    if (!tok) { setMention(null); return }
    const items = filterMembers(members, tok.query)
    if (!items.length) { setMention(null); return }
    setMention({ items, index: 0, start: tok.start, queryLen: tok.query.length })
  }

  const onChange = (e) => {
    const value = e.target.value
    setText(value)
    updateMention(value, e.target.selectionStart)
  }

  const pickMention = (m) => {
    if (!mention) return
    const { text: next, caret } = insertMention(text, mention.start, mention.queryLen, m.label)
    setText(next)
    setMention(null)
    requestAnimationFrame(() => {
      const el = taRef.current
      if (el) { el.focus(); el.setSelectionRange(caret, caret) }
    })
  }

  const onKeyDown = (e) => {
    if (mention) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setMention((s) => ({ ...s, index: (s.index + 1) % s.items.length }))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setMention((s) => ({ ...s, index: (s.index - 1 + s.items.length) % s.items.length }))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        pickMention(mention.items[mention.index])
        return
      }
      if (e.key === 'Escape') { setMention(null); return }
    }
    // XKB29 — raccourcis markdown : Ctrl/Cmd+B entoure la sélection de
    // `*gras*`, Ctrl/Cmd+E de `` `code` `` (symétrique au clic sur les
    // marqueurs eux-mêmes, qui restent tapables littéralement à tout moment).
    if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'e')) {
      e.preventDefault()
      const el = taRef.current
      if (!el) return
      const marker = e.key === 'b' ? '*' : '`'
      const { text: next, selectionStart, selectionEnd } = applyShortcut(
        text, el.selectionStart, el.selectionEnd, marker)
      setText(next)
      requestAnimationFrame(() => {
        el.focus()
        el.setSelectionRange(selectionStart, selectionEnd)
      })
      return
    }
    // Entrée = envoyer ; Maj+Entrée = nouvelle ligne.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
    if (e.key === 'Escape' && editing) onEditDone?.()
  }

  const uploadFiles = async (files) => {
    for (const file of files) {
      try {
        const res = await messagesApi.uploadAttachment(activeId, file)
        setAttachments((prev) => [...prev, { id: res.data.id, name: res.data.name || file.name }])
      } catch (err) {
        toastError(err.response?.data?.detail || `Échec de l’envoi de ${file.name}`)
      }
    }
  }

  const reset = () => {
    setText(''); setAttachments([]); setMention(null)
  }

  const submit = async () => {
    const body = text.trim()
    if (!body && attachments.length === 0) return
    setSending(true)
    try {
      if (editing) {
        await dispatch(editMessage({ id: editing.id, data: { body } }))
        onEditDone?.()
        reset()
      } else {
        await dispatch(sendMessage({
          conversation: activeId,
          body,
          mentions: extractMentions(body, members),
          attachment_ids: attachments.map((a) => a.id),
        }))
        reset()
      }
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat-composer border-t border-border p-2">
      {editing && (
        <div className="chat-composer-editing">
          Modification du message
          <button type="button" onClick={() => { onEditDone?.(); reset() }} aria-label="Annuler la modification">
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {attachments.length > 0 && (
        <ul className="chat-composer-atts">
          {attachments.map((a) => (
            <li key={a.id}>
              <Paperclip size={12} aria-hidden="true" /> {a.name}
              <button type="button" aria-label={`Retirer ${a.name}`}
                      onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}>
                <X size={12} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="chat-composer-row flex items-end gap-2">
        <FileUpload
          accept="image/*,application/pdf"
          multiple
          onFiles={uploadFiles}
          className="chat-composer-attach"
          aria-label="Joindre un fichier"
        >
          <Paperclip size={18} aria-hidden="true" />
        </FileUpload>

        <div className="chat-composer-field relative flex-1">
          <textarea
            ref={taRef}
            className="chat-composer-input w-full resize-none rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={text}
            onChange={onChange}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Écrire un message…  (@ pour mentionner)"
            aria-label="Message"
          />
          {mention && (
            <MentionAutocomplete
              items={mention.items}
              activeIndex={mention.index}
              onPick={pickMention}
              onClose={() => setMention(null)}
            />
          )}
        </div>

        <Button onClick={submit} loading={sending}
                disabled={!text.trim() && attachments.length === 0}
                aria-label={editing ? 'Enregistrer' : 'Envoyer'}>
          <Send size={16} aria-hidden="true" />
        </Button>
      </div>

      {/* Confirmation de suppression d'un message (piloté par le parent). */}
      <AlertDialog open={!!pendingDelete} onOpenChange={(v) => { if (!v) onDeleteResolved?.() }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce message ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le message sera retiré de la conversation. Cette action est définitive.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => onDeleteResolved?.()}>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={() => {
              if (pendingDelete) dispatch(deleteMessage(pendingDelete.id))
              onDeleteResolved?.()
            }}>
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

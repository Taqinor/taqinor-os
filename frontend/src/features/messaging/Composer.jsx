import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Send, Paperclip, X } from 'lucide-react'
import {
  Button, FileUpload,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import messagesApi from '../../api/messagesApi'
import iaApi from '../../api/iaApi'
import { buildAgentMessage } from '../ia/store/iaSlice'
import { toastError } from '../../lib/toast'
import {
  sendMessage, editMessage, deleteMessage, selectActiveId,
} from './store/messagingSlice'
import { useActiveDescendant } from '../../hooks/useActiveDescendant'
import MentionAutocomplete from './MentionAutocomplete'
import { activeMention, insertMention, filterMembers, extractMentions } from './mentions'
import { applyShortcut } from './richText'
import SlashCommandPicker from './SlashCommandPicker'
import SlashProposalCard from './SlashProposalCard'
import { activeSlashCommand, filterSlashCommands, resolveSlashSubmit, buildAideText } from './slashCommands'

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
  // XKB31 — commandes /. `slash` piloté l'ouverture du picker (liste filtrée +
  // index actif) ; `slashProposal` porte la carte de confirmation/résultat en
  // attente au-dessus du composer (jamais d'exécution sans passer par elle).
  const [slash, setSlash] = useState(null) // { items, index }
  const [allowedActionKeys, setAllowedActionKeys] = useState(null) // Set|null (chargé paresseusement)
  const [slashProposal, setSlashProposal] = useState(null) // { kind:'proposal'|'result', ... }
  const [slashConfirming, setSlashConfirming] = useState(false)
  const [slashError, setSlashError] = useState('')
  const taRef = useRef(null)
  // VX191 — `aria-activedescendant` : les popups @mention/slash annonçaient
  // déjà l'item survolé visuellement (`.active`), rien au lecteur d'écran.
  // Un seul des deux popups est ouvert à la fois (mention/slash exclusifs).
  const mentionA11y = useActiveDescendant(mention?.index ?? -1)
  const slashA11y = useActiveDescendant(slash?.index ?? -1)

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

  // XKB31 — le registre d'actions autorisées (`/api/django/agent/actions/`)
  // n'est chargé qu'à la première frappe d'un "/" (jamais au montage), et mis
  // en cache pour la session du composer. Best-effort : une erreur réseau
  // laisse `allowedActionKeys` à un Set vide (toutes les commandes à action
  // apparaissent indisponibles plutôt que de planter le picker).
  const ensureAllowedActions = async () => {
    if (allowedActionKeys) return allowedActionKeys
    try {
      const res = await iaApi.getAgentActions()
      const keys = new Set((res.data?.actions || []).map((a) => a.key))
      setAllowedActionKeys(keys)
      return keys
    } catch {
      const empty = new Set()
      setAllowedActionKeys(empty)
      return empty
    }
  }

  const updateSlash = async (value) => {
    const tok = activeSlashCommand(value)
    if (!tok) { setSlash(null); return }
    const keys = await ensureAllowedActions()
    const items = filterSlashCommands(tok.query, keys)
    if (!items.length) { setSlash(null); return }
    setSlash({ items, index: 0 })
  }

  const onChange = (e) => {
    const value = e.target.value
    setText(value)
    updateMention(value, e.target.selectionStart)
    updateSlash(value)
  }

  const pickSlash = (c) => {
    // Complète la commande + un espace de fin, laissant l'utilisateur taper
    // les arguments (nom, ville, etc.) avant Entrée.
    setText(`/${c.cmd} `)
    setSlash(null)
    requestAnimationFrame(() => taRef.current?.focus())
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
    if (slash) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlash((s) => ({ ...s, index: (s.index + 1) % s.items.length }))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlash((s) => ({ ...s, index: (s.index - 1 + s.items.length) % s.items.length }))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        const chosen = slash.items[slash.index]
        if (chosen.available) pickSlash(chosen)
        return
      }
      if (e.key === 'Escape') { setSlash(null); return }
    }
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
    setText(''); setAttachments([]); setMention(null); setSlash(null)
  }

  // XKB31 — envoie un message SYSTÈME simple (texte, aucune pièce jointe) dans
  // la conversation active. Réutilise le `sendMessage` existant : un message
  // avec `record_type`/`record_id` produit la carte record déjà rendue par
  // `MessageBubble`/`RecordCard` (S8/S19). Best-effort : une erreur d'envoi ne
  // doit jamais faire disparaître la carte de résultat déjà affichée localement.
  const postSlashResult = async (bodyText, { recordType, recordId } = {}) => {
    if (!activeId) return
    try {
      await dispatch(sendMessage({
        conversation: activeId,
        body: bodyText || '',
        ...(recordType && recordId ? { record_type: recordType, record_id: recordId } : {}),
      }))
    } catch {
      // best-effort — la carte de résultat locale reste visible même si la
      // conversation n'a pas pu recevoir le message de suivi.
    }
  }

  const cancelSlash = () => {
    setSlashProposal(null)
    setSlashError('')
    reset()
  }

  const confirmSlash = async () => {
    if (!slashProposal?.confirm_token) return
    setSlashConfirming(true)
    setSlashError('')
    try {
      const res = await iaApi.confirmAction(slashProposal.confirm_token)
      if (res.data && res.data.ok === false) {
        setSlashError(res.data.detail || 'L\'action n\'a pas pu être exécutée.')
        return
      }
      const msg = buildAgentMessage({
        answer: res.data?.detail || slashProposal.content || '',
        result: res.data?.data
          ? { type: 'result', action_key: res.data.action_key, data: res.data.data }
          : { type: 'result', action_key: res.data?.action_key, data: {} },
      })
      const data = res.data?.data || {}
      // Carte record best-effort : uniquement si le résultat de confirmation
      // porte explicitement un identifiant + type de record reconnu par le
      // backend chat (lead/devis/chantier) — jamais deviné depuis le texte.
      const recordId = data.lead_id ?? data.devis_id ?? data.chantier_id ?? null
      const recordType = data.lead_id ? 'lead' : data.devis_id ? 'devis' : data.chantier_id ? 'chantier' : null
      setSlashProposal({ kind: 'result', text: msg.content || msg.reference || 'Action effectuée.' })
      await postSlashResult(msg.content || msg.reference || 'Action effectuée.', { recordType, recordId })
      reset()
    } catch (err) {
      setSlashError(err.response?.data?.detail ?? 'Échec de la confirmation.')
    } finally {
      setSlashConfirming(false)
    }
  }

  // Envoie la commande / au pipeline propose→confirm existant (S8/S19 :
  // /sql-agent/query puis /sql-agent/confirm) — JAMAIS d'exécution directe
  // depuis le composer. `/aide` reste purement local (aucun appel réseau).
  const submitSlashCommand = async (resolved) => {
    if (resolved.command.cmd === 'aide') {
      const keys = await ensureAllowedActions()
      setSlashProposal({ kind: 'result', text: buildAideText(keys) })
      reset()
      return
    }
    setSlashError('')
    setSending(true)
    try {
      const res = await iaApi.queryAgent(resolved.question)
      const msg = buildAgentMessage(res.data)
      if (msg.kind === 'proposal') {
        setSlashProposal(msg)
      } else {
        // Réponse texte simple (pas de proposition structurée) : on la traite
        // comme un résultat direct, sans confirmation (rien n'a été écrit).
        setSlashProposal({ kind: 'result', text: msg.content || 'Terminé.' })
      }
      setText('')
    } finally {
      setSending(false)
    }
  }

  const submit = async () => {
    const body = text.trim()
    if (!body && attachments.length === 0) return
    if (!editing) {
      const resolved = resolveSlashSubmit(body)
      if (resolved) {
        await submitSlashCommand(resolved)
        return
      }
    }
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
      {/* XKB31 — carte de confirmation/résultat d'une commande /, au-dessus du
          composer tant qu'elle est active (bloque un nouvel envoi tant que non
          résolue, comme le Copilote). */}
      <SlashProposalCard
        proposal={slashProposal}
        confirming={slashConfirming}
        error={slashError}
        onConfirm={confirmSlash}
        onCancel={cancelSlash}
      />

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
            disabled={!!slashProposal}
            placeholder="Écrire un message…  (@ pour mentionner, / pour une commande)"
            aria-label="Message"
            role={mention || slash ? 'combobox' : undefined}
            aria-expanded={mention || slash ? true : undefined}
            aria-autocomplete={mention || slash ? 'list' : undefined}
            aria-controls={mention ? mentionA11y.listId : slash ? slashA11y.listId : undefined}
            aria-activedescendant={mention ? mentionA11y.activeId : slash ? slashA11y.activeId : undefined}
          />
          {mention && (
            <MentionAutocomplete
              items={mention.items}
              activeIndex={mention.index}
              onPick={pickMention}
              onClose={() => setMention(null)}
              listId={mentionA11y.listId}
              getOptionId={mentionA11y.getOptionId}
            />
          )}
          {slash && (
            <SlashCommandPicker
              items={slash.items}
              activeIndex={slash.index}
              onPick={pickSlash}
              onClose={() => setSlash(null)}
              listId={slashA11y.listId}
              getOptionId={slashA11y.getOptionId}
            />
          )}
        </div>

        <Button onClick={submit} loading={sending}
                disabled={(!text.trim() && attachments.length === 0) || !!slashProposal}
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

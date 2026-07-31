import { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Send, Paperclip, X, BarChart3, Clock, Plus } from 'lucide-react'
import {
  Button, FileUpload, Label, Checkbox, Input,
  Popover, PopoverTrigger, PopoverContent,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
import { cn } from '../../lib/cn'
import messagesApi from '../../api/messagesApi'
import iaApi from '../../api/iaApi'
import { buildAgentMessage } from '../ia/store/iaSlice'
import { toastError, toastSuccess } from '../../lib/toast'
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
   `pendingDelete` arme le dialogue de confirmation (piloté par le parent).

   WIR155 — trois actions rapides additionnelles, toutes self-contained (pas
   de nouveau prop remonté au parent ChatPage, qui reste hors périmètre) :
     - autocomplétion `:raccourci` (réponses enregistrées XKB28), même forme
       que @mention/slash (token détecté au curseur, popup, clavier ↑↓⏎Échap) ;
     - création de sondage (XKB30) via un Dialog, envoyé par
       `messagesApi.poll.create` puis fusionné dans le store en dispatchant
       manuellement `sendMessage.fulfilled` (même reducer que l'envoi normal —
       aucun nouveau thunk, `messagingSlice.js` reste hors périmètre) ;
     - « Programmer l'envoi » (XKB27) via un Popover (date/heure + liste
       d'attente des messages programmés de LA conversation active, annulables). */

// Détecte un token :raccourci en cours de frappe (même forme que activeMention
// dans ./mentions.js, mais déclenché par « : » et sans limite de caractères
// spéciaux — les raccourcis sont de simples mots).
function activeCannedToken(text, caret) {
  if (text == null) return null
  const upto = text.slice(0, caret)
  const m = /(^|\s):([\w-]*)$/.exec(upto)
  if (!m) return null
  return { query: m[2], start: caret - m[2].length - 1 }
}

// Remplace le token :query (à partir de `start`) par le corps du snippet.
function insertCanned(text, start, queryLen, body) {
  const before = text.slice(0, start)
  const after = text.slice(start + 1 + queryLen)
  const inserted = `${body} `
  return { text: before + inserted + after, caret: before.length + inserted.length }
}

function filterCanned(list, query, limit = 8) {
  const q = (query || '').toLowerCase()
  return (list || [])
    .filter((c) => c.shortcut.toLowerCase().startsWith(q))
    .slice(0, limit)
}

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

  // ── WIR155 / XKB28 — autocomplétion :raccourci (réponses enregistrées) ──
  const [canned, setCanned] = useState(null) // { items, index, start, queryLen }
  const [cannedList, setCannedList] = useState(null) // cache session (null = pas encore chargé)
  const cannedA11y = useActiveDescendant(canned?.index ?? -1)

  // ── WIR155 / XKB30 — création de sondage ──
  const [pollOpen, setPollOpen] = useState(false)
  const [pollQuestion, setPollQuestion] = useState('')
  const [pollOptions, setPollOptions] = useState(['', ''])
  const [pollMultiple, setPollMultiple] = useState(false)
  const [pollAnonymous, setPollAnonymous] = useState(false)
  const [pollSaving, setPollSaving] = useState(false)

  // ── WIR155 / XKB27 — « Programmer l'envoi » + liste d'attente ──
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [scheduleAt, setScheduleAt] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const [scheduledQueue, setScheduledQueue] = useState([])

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

  // WIR155 / XKB28 — le catalogue de réponses enregistrées (personnelles +
  // société) n'est chargé qu'à la première frappe d'un « : » (jamais au
  // montage), mis en cache pour la session du composer. Best-effort : une
  // erreur réseau laisse `cannedList` à un tableau vide (popup silencieusement
  // vide plutôt qu'une exception).
  const ensureCannedResponses = async () => {
    if (cannedList) return cannedList
    try {
      const res = await messagesApi.canned.list()
      const list = res.data?.results ?? res.data ?? []
      setCannedList(list)
      return list
    } catch {
      const empty = []
      setCannedList(empty)
      return empty
    }
  }

  const updateCanned = async (value, caret) => {
    const tok = activeCannedToken(value, caret)
    if (!tok) { setCanned(null); return }
    const list = await ensureCannedResponses()
    const items = filterCanned(list, tok.query)
    if (!items.length) { setCanned(null); return }
    setCanned({ items, index: 0, start: tok.start, queryLen: tok.query.length })
  }

  const onChange = (e) => {
    const value = e.target.value
    setText(value)
    updateMention(value, e.target.selectionStart)
    updateSlash(value)
    updateCanned(value, e.target.selectionStart)
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

  const pickCanned = (c) => {
    if (!canned) return
    const { text: next, caret } = insertCanned(text, canned.start, canned.queryLen, c.body)
    setText(next)
    setCanned(null)
    requestAnimationFrame(() => {
      const el = taRef.current
      if (el) { el.focus(); el.setSelectionRange(caret, caret) }
    })
  }

  const onKeyDown = (e) => {
    if (canned) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setCanned((s) => ({ ...s, index: (s.index + 1) % s.items.length }))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setCanned((s) => ({ ...s, index: (s.index - 1 + s.items.length) % s.items.length }))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        pickCanned(canned.items[canned.index])
        return
      }
      if (e.key === 'Escape') { setCanned(null); return }
    }
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
    setText(''); setAttachments([]); setMention(null); setSlash(null); setCanned(null)
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

  // ── WIR155 / XKB30 — création de sondage ──
  const resetPoll = () => {
    setPollQuestion(''); setPollOptions(['', '']); setPollMultiple(false); setPollAnonymous(false)
  }

  const updatePollOption = (i, value) => {
    setPollOptions((opts) => opts.map((o, idx) => (idx === i ? value : o)))
  }
  const addPollOption = () => {
    setPollOptions((opts) => (opts.length < 10 ? [...opts, ''] : opts))
  }
  const removePollOption = (i) => {
    setPollOptions((opts) => (opts.length > 2 ? opts.filter((_, idx) => idx !== i) : opts))
  }

  const submitPoll = async () => {
    const cleanedOptions = pollOptions.map((o) => o.trim()).filter(Boolean)
    if (!activeId || !pollQuestion.trim() || cleanedOptions.length < 2) return
    setPollSaving(true)
    try {
      const res = await messagesApi.poll.create({
        conversation: activeId,
        question: pollQuestion.trim(),
        options: cleanedOptions,
        allow_multiple: pollMultiple,
        is_anonymous: pollAnonymous,
      })
      // Pas de thunk dédié pour les sondages (le store `messagingSlice.js`
      // reste hors périmètre WIR155) : on réutilise le reducer de
      // `sendMessage.fulfilled` en le dispatchant manuellement — même fusion
      // messages/aperçu-conversation qu'un envoi normal, sans appel réseau
      // supplémentaire (RTK : `.fulfilled` est une simple action creator).
      dispatch(sendMessage.fulfilled(res.data, `poll-${res.data?.id ?? Date.now()}`, {}))
      setPollOpen(false)
      resetPoll()
    } catch (err) {
      toastError(err.response?.data?.detail || 'Sondage impossible à créer')
    } finally {
      setPollSaving(false)
    }
  }

  // ── WIR155 / XKB27 — « Programmer l'envoi » + liste d'attente ──
  const loadScheduledQueue = async () => {
    try {
      const res = await messagesApi.scheduled.list()
      const rows = res.data?.results ?? res.data ?? []
      setScheduledQueue(
        rows.filter((s) => s.conversation === activeId && s.status === 'pending'))
    } catch {
      setScheduledQueue([])
    }
  }
  useEffect(() => {
    // Différé d'un microtask : l'analyse statique ne peut pas prouver que cette
    // fonction async ne pose pas d'état de façon synchrone
    // (react-hooks/set-state-in-effect). Comportement inchangé.
    if (scheduleOpen) Promise.resolve().then(loadScheduledQueue)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rechargé à l'ouverture du popover uniquement
  }, [scheduleOpen, activeId])

  const submitSchedule = async () => {
    const body = text.trim()
    if (!activeId || !body || !scheduleAt) return
    setScheduling(true)
    try {
      const iso = new Date(scheduleAt).toISOString()
      await messagesApi.scheduled.create({
        conversation: activeId, body, scheduled_at: iso,
      })
      toastSuccess('Message programmé.')
      reset()
      setScheduleAt('')
      await loadScheduledQueue()
    } catch (err) {
      toastError(err.response?.data?.detail || 'Programmation impossible')
    } finally {
      setScheduling(false)
    }
  }

  const cancelScheduled = async (id) => {
    try {
      await messagesApi.scheduled.cancel(id)
      setScheduledQueue((q) => q.filter((s) => s.id !== id))
    } catch (err) {
      toastError(err.response?.data?.detail || 'Annulation impossible')
    }
  }

  return (
    <div className="border-t border-border p-2">
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
        <div className="mb-2 flex items-center justify-between gap-2 rounded-md bg-accent/30 px-3 py-1.5 text-xs text-muted-foreground">
          Modification du message
          <button
            type="button"
            onClick={() => { onEditDone?.(); reset() }}
            aria-label="Annuler la modification"
            className="rounded p-0.5 hover:bg-muted hover:text-foreground"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}

      {attachments.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="flex max-w-[12rem] items-center gap-1.5 rounded-full border border-border bg-muted/50 px-2.5 py-1 text-xs"
            >
              <Paperclip size={12} className="shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="truncate">{a.name}</span>
              <button
                type="button"
                aria-label={`Retirer ${a.name}`}
                onClick={() => setAttachments((p) => p.filter((x) => x.id !== a.id))}
                className="shrink-0 rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X size={12} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-end gap-2">
        <FileUpload
          accept="image/*,application/pdf"
          multiple
          onFiles={uploadFiles}
          aria-label="Joindre un fichier"
        >
          <Paperclip size={18} aria-hidden="true" />
        </FileUpload>

        {/* WIR155 — création de sondage (désactivée en mode édition). */}
        <Button
          type="button" variant="ghost" size="icon"
          onClick={() => setPollOpen(true)}
          disabled={!activeId || !!editing}
          aria-label="Créer un sondage" title="Créer un sondage"
        >
          <BarChart3 size={18} aria-hidden="true" />
        </Button>

        <div className="relative flex-1">
          <textarea
            ref={taRef}
            className="w-full resize-none rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={text}
            onChange={onChange}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={!!slashProposal}
            placeholder="Écrire un message…  (@ mentionner, / commande, : réponse enregistrée)"
            aria-label="Message"
            role={mention || slash || canned ? 'combobox' : undefined}
            aria-expanded={mention || slash || canned ? true : undefined}
            aria-autocomplete={mention || slash || canned ? 'list' : undefined}
            aria-controls={mention ? mentionA11y.listId : slash ? slashA11y.listId : canned ? cannedA11y.listId : undefined}
            aria-activedescendant={mention ? mentionA11y.activeId : slash ? slashA11y.activeId : canned ? cannedA11y.activeId : undefined}
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
          {/* WIR155 / XKB28 — popup :raccourci, même forme que @mention/slash. */}
          {canned && (
            <ul
              role="listbox" aria-label="Réponses enregistrées" id={cannedA11y.listId}
              className="absolute bottom-full left-0 z-10 mb-1 max-h-56 w-72 overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-md"
            >
              {canned.items.map((c, i) => (
                <li key={c.id} id={cannedA11y.getOptionId(i)} role="option" aria-selected={i === canned.index}>
                  <button
                    type="button"
                    className={cn(
                      'flex w-full flex-col items-start gap-0.5 rounded px-2 py-1.5 text-left text-sm',
                      i === canned.index ? 'bg-muted' : 'hover:bg-muted',
                    )}
                    onMouseDown={(e) => { e.preventDefault(); pickCanned(c) }}
                  >
                    <span className="font-medium text-foreground">:{c.shortcut}</span>
                    <span className="w-full truncate text-xs text-muted-foreground">{c.body}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* WIR155 / XKB27 — « Programmer l'envoi » + liste d'attente de la
            conversation active. */}
        <Popover open={scheduleOpen} onOpenChange={setScheduleOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button" variant="ghost" size="icon"
              disabled={!activeId || !!editing}
              aria-label="Programmer l'envoi" title="Programmer l'envoi"
            >
              <Clock size={18} aria-hidden="true" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72">
            <div className="grid gap-2">
              <Label htmlFor="chat-schedule-at">Envoyer le message actuel le</Label>
              <input
                id="chat-schedule-at"
                type="datetime-local"
                value={scheduleAt}
                onChange={(e) => setScheduleAt(e.target.value)}
                className="rounded-md border border-input bg-card px-2 py-1.5 text-sm"
              />
              <Button
                onClick={submitSchedule} loading={scheduling}
                disabled={!scheduleAt || !text.trim()}
              >
                Programmer
              </Button>
              {scheduledQueue.length > 0 && (
                <div className="mt-1 border-t border-border pt-2">
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    En attente ({scheduledQueue.length})
                  </p>
                  <ul className="flex max-h-40 flex-col gap-1 overflow-y-auto">
                    {scheduledQueue.map((s) => (
                      <li key={s.id} className="flex items-center justify-between gap-2 text-xs">
                        <span className="truncate">{s.body}</span>
                        <button
                          type="button"
                          onClick={() => cancelScheduled(s.id)}
                          aria-label={`Annuler le message programmé ${s.id}`}
                          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                          <X size={12} aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>

        <Button onClick={submit} loading={sending}
                disabled={(!text.trim() && attachments.length === 0) || !!slashProposal}
                aria-label={editing ? 'Enregistrer' : 'Envoyer'}>
          <Send size={16} aria-hidden="true" />
        </Button>
      </div>

      {/* WIR155 / XKB30 — création de sondage. */}
      <Dialog open={pollOpen} onOpenChange={(v) => { setPollOpen(v); if (!v) resetPoll() }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un sondage</DialogTitle>
            <DialogDescription>
              Posez une question à choix unique ou multiple dans cette conversation.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="chat-poll-question">Question</Label>
              <Input
                id="chat-poll-question"
                value={pollQuestion}
                onChange={(e) => setPollQuestion(e.target.value)}
                placeholder="ex. Quel jour pour la réunion d’équipe ?"
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Options</Label>
              {pollOptions.map((o, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <Input
                    value={o}
                    onChange={(e) => updatePollOption(i, e.target.value)}
                    placeholder={`Option ${i + 1}`}
                    aria-label={`Option ${i + 1}`}
                  />
                  {pollOptions.length > 2 && (
                    <button
                      type="button"
                      onClick={() => removePollOption(i)}
                      aria-label={`Retirer l’option ${i + 1}`}
                      className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <X size={14} aria-hidden="true" />
                    </button>
                  )}
                </div>
              ))}
              {pollOptions.length < 10 && (
                <button
                  type="button"
                  onClick={addPollOption}
                  className="flex w-fit items-center gap-1 text-xs font-medium text-primary hover:underline"
                >
                  <Plus size={14} aria-hidden="true" /> Ajouter une option
                </button>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={pollMultiple} onCheckedChange={(v) => setPollMultiple(!!v)} />
              Choix multiple
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={pollAnonymous} onCheckedChange={(v) => setPollAnonymous(!!v)} />
              Vote anonyme (masque les votants)
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => { setPollOpen(false); resetPoll() }}>
              Annuler
            </Button>
            <Button
              onClick={submitPoll} loading={pollSaving}
              disabled={!pollQuestion.trim()
                || pollOptions.map((o) => o.trim()).filter(Boolean).length < 2}
            >
              Créer le sondage
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

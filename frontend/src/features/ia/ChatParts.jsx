import { useState } from 'react'
import { useDispatch } from 'react-redux'
import { Code2, ChevronDown, ThumbsUp, ThumbsDown } from 'lucide-react'
import { Button, Textarea } from '../../ui'
import { noterEvenement } from './store/iaSlice'
import CartesDuMessage from './cartes/CartesDuMessage'
import { COMMENTAIRE_MAX, NOTE_NEGATIVE, NOTE_POSITIVE } from './copilotMessages'

/* ENF19 — briques de conversation partagées par le tiroir Copilote
   (features/ia/CopilotPanel.jsx) et l'écran Agent IA (pages/ia/AgentChat.jsx),
   extraites à l'identique de leurs deux copies. Seuls `testId` et `className`
   (padding) varient d'un appelant à l'autre. */

function SqlQueryDetails({ sqlQuery }) {
  return (
    <details className="group mt-2 rounded-md border border-border bg-card text-foreground">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-muted-foreground">
        <Code2 className="size-3.5" aria-hidden="true" />
        Requête SQL générée
        <ChevronDown
          className="ml-auto size-3.5 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <pre className="overflow-x-auto border-t border-border px-2.5 py-2 text-xs text-muted-foreground">
        <code>{sqlQuery}</code>
      </pre>
    </details>
  )
}

export function SuggestionButtons({ suggestions, onPick, buttonClassName }) {
  return suggestions.map((s) => (
    <Button
      key={s}
      variant="outline"
      size="sm"
      className={buttonClassName}
      onClick={() => onPick(s)}
    >
      {s}
    </Button>
  ))
}

export function TypingDots() {
  return (
    <>
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground" />
    </>
  )
}

// Cartes d'action (COP-F1 : `msg.cartes`, jamais le texte du modèle) + requête
// SQL d'un message agent. Les cartes vivent dans `features/ia/cartes/`.
export function MessageActions({ msg, index, variant }) {
  return (
    <>
      <CartesDuMessage msg={msg} index={index} variant={variant} />
      {msg.sql_query && <SqlQueryDetails sqlQuery={msg.sql_query} />}
    </>
  )
}

// AIC8 — note du commercial sous chaque réponse journalisée (`evenement_id`,
// AIC6) : 👍 = 1, 👎 et « ça n'a pas répondu » = −1, commentaire facultatif
// (≤ 200 car.). Une note par événement, modifiable ; après envoi : « Merci ».
export function NoteReponse({ msg, index }) {
  const dispatch = useDispatch()
  const [choix, setChoix] = useState(null)
  const [commentaire, setCommentaire] = useState('')
  if (msg?.role !== 'agent' || msg.evenement_id == null) return null
  const envoyer = (note, texte = null) => {
    dispatch(noterEvenement({ index, evenementId: msg.evenement_id, note, commentaire: texte }))
    setChoix(null)
  }
  if (choix != null) {
    return (
      <div className="mt-2 space-y-1.5" data-testid="note-commentaire">
        <Textarea
          rows={2}
          maxLength={COMMENTAIRE_MAX}
          value={commentaire}
          onChange={(e) => setCommentaire(e.target.value)}
          placeholder="Qu'est-ce qui manquait ? (facultatif)"
          aria-label="Commentaire sur la réponse"
        />
        <Button size="sm" variant="outline" onClick={() => envoyer(NOTE_NEGATIVE, commentaire.trim() || null)}>
          Envoyer le retour
        </Button>
      </div>
    )
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground" data-testid="note-reponse">
      {msg.noteEnvoyee && <span>Merci pour votre retour.</span>}
      <Button size="sm" variant={msg.note === NOTE_POSITIVE ? 'default' : 'ghost'}
        aria-label="Réponse utile" aria-pressed={msg.note === NOTE_POSITIVE}
        onClick={() => envoyer(NOTE_POSITIVE)}>
        <ThumbsUp className="size-3.5" aria-hidden="true" />
      </Button>
      <Button size="sm" variant={msg.note === NOTE_NEGATIVE ? 'default' : 'ghost'}
        aria-label="Réponse fausse" aria-pressed={msg.note === NOTE_NEGATIVE}
        onClick={() => setChoix('pouce_bas')}>
        <ThumbsDown className="size-3.5" aria-hidden="true" />
      </Button>
      <Button size="sm" variant="ghost" onClick={() => setChoix('pas_repondu')}>
        Ça n&apos;a pas répondu
      </Button>
    </div>
  )
}

export function QuestionForm({ onSubmit, inputRef, input, setInput, onKeyDown, disabled, children }) {
  return (
    <form className="flex items-end gap-2" onSubmit={onSubmit}>
      <Textarea
        ref={inputRef}
        rows={1}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Posez votre question en français…"
        disabled={disabled}
        autoComplete="off"
        className="max-h-32 min-h-[var(--control-h)] resize-none py-2.5"
      />
      {children}
    </form>
  )
}

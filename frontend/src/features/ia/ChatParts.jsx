import { useState } from 'react'
import { useDispatch } from 'react-redux'
import {
  Code2, ChevronDown, CheckCircle2, ShieldQuestion, Check, X, FileDown, MessageCircle,
  ThumbsUp, ThumbsDown,
} from 'lucide-react'
import { Button, buttonVariants, Textarea } from '../../ui'
import { cn } from '../../lib/cn'
import { confirmAgentAction, dismissProposal, noterEvenement } from './store/iaSlice'
import { COMMENTAIRE_MAX, NOTE_NEGATIVE, NOTE_POSITIVE } from './copilotMessages'

/* ENF19 — briques de conversation partagées par le tiroir Copilote
   (features/ia/CopilotPanel.jsx) et l'écran Agent IA (pages/ia/AgentChat.jsx),
   extraites à l'identique de leurs deux copies. Seuls `testId` et `className`
   (padding) varient d'un appelant à l'autre. */

// AG3 — carte CONFIRMATION pour une action proposée. La voie /confirm reste la
// SEULE manière d'exécuter une action sensible : jamais de confirmation auto.
function ProposalCard({ msg, index, confirmingIndex, confirmError, testId, className }) {
  const dispatch = useDispatch()
  return (
    <div data-testid={testId} className={className}>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 dark:text-amber-400">
        <ShieldQuestion className="size-3.5" aria-hidden="true" />
        Confirmation requise
      </p>
      {msg.human_preview && (
        <p className="mt-1.5 whitespace-pre-wrap break-words text-sm">
          {msg.human_preview}
        </p>
      )}
      {!msg.confirm_token && (
        <p className="mt-1.5 text-xs text-muted-foreground">
          Confirmation indisponible pour le moment.
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={!msg.confirm_token || confirmingIndex === index}
          loading={confirmingIndex === index}
          onClick={() =>
            dispatch(confirmAgentAction({ token: msg.confirm_token, index }))
          }
        >
          <Check className="size-4" aria-hidden="true" />
          Confirmer
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={confirmingIndex === index}
          onClick={() => dispatch(dismissProposal(index))}
        >
          <X className="size-4" aria-hidden="true" />
          Annuler
        </Button>
      </div>
      {confirmError && confirmingIndex == null && (
        <p className="mt-2 text-xs text-destructive">
          {typeof confirmError === 'string' ? confirmError : 'Échec de la confirmation.'}
        </p>
      )}
    </div>
  )
}

// AG3 — carte RÉSULTAT pour une action terminée. Le devis passe TOUJOURS par
// /proposal (règle fondateur #4).
function ResultCard({ msg, testId, className }) {
  return (
    <div data-testid={testId} className={className}>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
        Action effectuée
      </p>
      {msg.reference && (
        <p className="mt-1.5 text-sm">
          Référence : <span className="font-medium">{msg.reference}</span>
        </p>
      )}
      <div className="mt-2.5 flex flex-wrap gap-2">
        {msg.proposal_url && (
          <a
            href={msg.proposal_url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            <FileDown className="size-4" aria-hidden="true" />
            Télécharger le devis
          </a>
        )}
        {msg.wa_url && (
          <a
            href={msg.wa_url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            <MessageCircle className="size-4" aria-hidden="true" />
            Ouvrir WhatsApp
          </a>
        )}
      </div>
    </div>
  )
}

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

// Variante par surface : identifiants de test et padding des cartes d'action.
const VARIANTES = {
  copilot: { proposal: 'copilot-proposal-card', result: 'copilot-result-card', pad: 'p-2.5' },
  page: { proposal: 'proposal-card', result: 'result-card', pad: 'p-3' },
}

// Cartes d'action (confirmation / résultat) + requête SQL d'un message agent.
export function MessageActions({ msg, index, confirmingIndex, confirmError, variant }) {
  const v = VARIANTES[variant]
  return (
    <>
      {msg.kind === 'proposal' && (
        <ProposalCard
          msg={msg}
          index={index}
          confirmingIndex={confirmingIndex}
          confirmError={confirmError}
          testId={v.proposal}
          className={`mt-2 rounded-md border border-amber-500/40 bg-amber-500/10 ${v.pad} text-foreground`}
        />
      )}
      {msg.kind === 'result' && (
        <ResultCard
          msg={msg}
          testId={v.result}
          className={`mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 ${v.pad} text-foreground`}
        />
      )}
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

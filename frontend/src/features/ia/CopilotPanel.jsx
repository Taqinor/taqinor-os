import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Bot, MessageSquare, Send, Code2, ChevronDown, CheckCircle2,
  ShieldQuestion, Check, X, FileDown, MessageCircle,
} from 'lucide-react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Button, buttonVariants, IconButton, EmptyState, Textarea,
} from '../../ui'
import { cn } from '../../lib/cn'
import StateBlock from '../../components/StateBlock'
import {
  queryAgent, loadChatHistory, clearChatHistory,
  confirmAgentAction, dismissProposal, closeCopilot,
} from './store/iaSlice'
import { displayMessageText, formatAgentError, canSendQuestion } from './copilotMessages'

// FG350 — Copilote in-app : tiroir conversationnel GLOBAL câblé sur l'agent
// FastAPI (SQL + actions) déjà exposé par `iaApi`/`iaSlice` (POST
// /sql-agent/query). Disponible partout depuis l'app shell (bouton de l'en-tête
// → `toggleCopilot`), sans quitter la page courante. Réutilise EXACTEMENT la
// slice `ia` (messages/queryAgent/confirmAgentAction) — aucun backend nouveau.
//
// Dégradation gracieuse : quand la clé IA est absente, le backend renvoie un
// message de configuration ; on l'affiche proprement (helper pur
// `displayMessageText`) au lieu de crasher.

const SUGGESTIONS = [
  'Quels produits sont en rupture de stock ?',
  'Quel est le chiffre d\'affaires du mois ?',
  'Affiche les factures impayées',
]

export default function CopilotPanel() {
  const dispatch = useDispatch()
  const open = useSelector((s) => s.ia.copilotOpen)
  const { messages, agentLoading, agentError, confirmingIndex, confirmError } =
    useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  // L'historique n'est chargé qu'une fois, à la première ouverture du tiroir.
  const historyLoadedRef = useRef(false)

  useEffect(() => {
    if (open && !historyLoadedRef.current) {
      historyLoadedRef.current = true
      dispatch(loadChatHistory())
    }
  }, [open, dispatch])

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading, open])

  const send = (q) => {
    if (!canSendQuestion(q, agentLoading)) return
    dispatch(queryAgent(q.trim()))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    send(input)
    setInput('')
  }

  const handleSuggestion = (text) => {
    send(text)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) dispatch(closeCopilot()) }}>
      <SheetContent
        side="right"
        className="w-[min(30rem,calc(100%-1.5rem))] gap-3 p-0"
        data-testid="copilot-panel"
      >
        <SheetHeader className="border-b border-border px-4 py-3 pr-10">
          <SheetTitle className="flex items-center gap-2">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Bot className="size-4" aria-hidden="true" />
            </span>
            Copilote
          </SheetTitle>
          <SheetDescription>
            Posez une question sur vos données — réponses en temps réel.
          </SheetDescription>
        </SheetHeader>

        {/* ── Zone messages ── */}
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-3">
          {messages.length === 0 && !agentLoading && (
            <EmptyState
              icon={MessageSquare}
              title="Comment puis-je aider ?"
              description="L'agent analyse votre base de données et répond en français."
              className="border-0 py-6"
              action={
                <div className="flex flex-col gap-2">
                  {SUGGESTIONS.map((s) => (
                    <Button
                      key={s}
                      variant="outline"
                      size="sm"
                      className="h-auto whitespace-normal py-1.5 text-left"
                      onClick={() => handleSuggestion(s)}
                    >
                      {s}
                    </Button>
                  ))}
                </div>
              }
            />
          )}

          <div className="space-y-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-start gap-2',
                  msg.role === 'user' && 'flex-row-reverse',
                )}
              >
                {msg.role === 'agent' && (
                  <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                    <Bot className="size-3.5" aria-hidden="true" />
                  </span>
                )}
                <div
                  className={cn(
                    'max-w-[85%] rounded-xl px-3 py-2 text-sm',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground',
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">
                    {displayMessageText(msg)}
                  </p>
                  {msg.action_performed && (
                    <span className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      Action effectuée
                    </span>
                  )}

                  {/* AG3 — carte CONFIRMATION pour une action proposée. La voie
                      /confirm reste la SEULE manière d'exécuter une action
                      sensible : jamais de confirmation automatique. */}
                  {msg.kind === 'proposal' && (
                    <div
                      data-testid="copilot-proposal-card"
                      className="mt-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-2.5 text-foreground"
                    >
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
                          disabled={!msg.confirm_token || confirmingIndex === i}
                          loading={confirmingIndex === i}
                          onClick={() =>
                            dispatch(confirmAgentAction({ token: msg.confirm_token, index: i }))
                          }
                        >
                          <Check className="size-4" aria-hidden="true" />
                          Confirmer
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={confirmingIndex === i}
                          onClick={() => dispatch(dismissProposal(i))}
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
                  )}

                  {/* AG3 — carte RÉSULTAT pour une action terminée. Le devis
                      passe TOUJOURS par /proposal (rule founder #4). */}
                  {msg.kind === 'result' && (
                    <div
                      data-testid="copilot-result-card"
                      className="mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-foreground"
                    >
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
                  )}

                  {msg.sql_query && (
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
                        <code>{msg.sql_query}</code>
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}

            {agentLoading && (
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Bot className="size-3.5" aria-hidden="true" />
                </span>
                <div className="flex items-center gap-1 rounded-xl bg-muted px-3 py-2.5">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground" />
                </div>
              </div>
            )}

            {agentError && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10">
                <StateBlock error={formatAgentError(agentError)} />
              </div>
            )}
          </div>
          <div ref={messagesEndRef} />
        </div>

        {/* ── Saisie ── */}
        <div className="border-t border-border bg-card px-4 py-3">
          {messages.length > 0 && (
            <div className="mb-2 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => dispatch(clearChatHistory())}>
                Nouvelle conversation
              </Button>
            </div>
          )}
          <form className="flex items-end gap-2" onSubmit={handleSubmit}>
            <Textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question en français…"
              disabled={agentLoading}
              autoComplete="off"
              className="max-h-32 min-h-[var(--control-h)] resize-none py-2.5"
            />
            <IconButton
              type="submit"
              variant="default"
              label="Envoyer"
              disabled={!canSendQuestion(input, agentLoading)}
            >
              <Send />
            </IconButton>
          </form>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            L'agent peut faire des erreurs. Vérifiez les informations importantes.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

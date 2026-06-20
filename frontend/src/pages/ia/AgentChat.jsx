import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Bot, MessageSquare, Send, Code2, ChevronDown, CheckCircle2 } from 'lucide-react'
import {
  Button,
  IconButton,
  Card,
  CardContent,
  EmptyState,
  Textarea,
  TooltipProvider,
  SimpleTooltip,
} from '../../ui'
import { cn } from '../../lib/cn'
import StateBlock from '../../components/StateBlock'
import { queryAgent, loadChatHistory, clearChatHistory } from '../../features/ia/store/iaSlice'

const SUGGESTIONS = [
  'Quels produits sont en rupture de stock ?',
  // L9 — suggestions orientées stock (valorisation / réappro).
  'Quelle est la valeur totale du stock ?',
  'Quels produits sont sous le seuil d\'alerte ?',
  'Quel est le chiffre d\'affaires du mois ?',
  'Combien de clients actifs avons-nous ?',
  'Quels sont les 5 produits les plus vendus ?',
  'Affiche les factures impayées',
]

// L11 — message FR clair quand la fonctionnalité est key-gated (GROQ_API_KEY
// absente côté service IA). Le backend renvoie le texte d'erreur de
// configuration comme réponse ; on le reconnaît pour afficher un message net.
const CONFIG_MISSING_FR = 'Assistant indisponible (configuration manquante)'

function isConfigMissing(text) {
  if (!text || typeof text !== 'string') return false
  const t = text.toLowerCase()
  return (
    (t.includes('groq_api_key') || t.includes('api_key') || t.includes('api key'))
    && (t.includes('manquante') || t.includes('manquant') || t.includes('missing')
        || t.includes('.env') || t.includes('absente'))
  )
}

export default function AgentChat() {
  const dispatch = useDispatch()
  const { messages, agentLoading, agentError } = useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Charge l'historique Redis au montage du composant
  useEffect(() => {
    dispatch(loadChatHistory())
  }, [dispatch])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || agentLoading) return
    dispatch(queryAgent(q))
    setInput('')
  }

  const handleSuggestion = (text) => {
    if (agentLoading) return
    dispatch(queryAgent(text))
    inputRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root flex h-[calc(100vh-7rem)] min-h-[28rem] flex-col gap-3">

        {/* ── En-tête ── */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <Bot className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
                Agent IA Conversationnel
              </h2>
              <p className="text-xs text-muted-foreground">
                Groq · llama-3.3-70b · Données en temps réel
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <Button variant="outline" size="sm" onClick={() => dispatch(clearChatHistory())}>
              Nouvelle conversation
            </Button>
          )}
        </div>

        {/* ── Zone messages ── */}
        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">

            {messages.length === 0 && !agentLoading && (
              <EmptyState
                icon={MessageSquare}
                title="Posez une question sur vos données"
                description="L'agent analyse votre base de données en temps réel et répond en français."
                className="border-0 py-8"
                action={
                  <div className="flex flex-wrap justify-center gap-2">
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

            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-start gap-2.5',
                  msg.role === 'user' && 'flex-row-reverse',
                )}
              >
                {msg.role === 'agent' && (
                  <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                    <Bot className="size-4" aria-hidden="true" />
                  </span>
                )}
                <div
                  className={cn(
                    'max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-foreground',
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">
                    {msg.role === 'agent' && isConfigMissing(msg.content)
                      ? CONFIG_MISSING_FR
                      : msg.content}
                  </p>
                  {msg.action_performed && (
                    <span className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      Action effectuée
                    </span>
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
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Bot className="size-4" aria-hidden="true" />
                </span>
                <div className="flex items-center gap-1 rounded-xl bg-muted px-3.5 py-3">
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground" />
                </div>
              </div>
            )}

            {agentError && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10">
                {/* L11/L17 — patron d'état partagé. Si l'échec traduit une clé
                    API manquante (feature key-gated), message FR dédié. */}
                <StateBlock
                  error={
                    isConfigMissing(
                      typeof agentError === 'string'
                        ? agentError
                        : agentError?.detail || JSON.stringify(agentError),
                    )
                      ? CONFIG_MISSING_FR
                      : `Erreur : ${typeof agentError === 'string' ? agentError : JSON.stringify(agentError)}`
                  }
                />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* ── Saisie ── */}
          <div className="border-t border-border bg-card p-3 sm:p-4">
            {messages.length > 0 && !agentLoading && (
              <div className="mb-2 flex flex-wrap gap-2">
                {SUGGESTIONS.slice(0, 3).map((s) => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    className="h-auto whitespace-normal py-1 text-xs"
                    onClick={() => handleSuggestion(s)}
                  >
                    {s}
                  </Button>
                ))}
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
              <SimpleTooltip label="Envoyer">
                <IconButton
                  type="submit"
                  variant="default"
                  label="Envoyer"
                  disabled={agentLoading || !input.trim()}
                >
                  <Send />
                </IconButton>
              </SimpleTooltip>
            </form>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              L'agent peut faire des erreurs. Vérifiez les informations importantes.
            </p>
          </div>
        </Card>
      </div>
    </TooltipProvider>
  )
}

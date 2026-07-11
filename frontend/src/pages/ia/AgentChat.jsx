import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Bot, MessageSquare, Send, Code2, ChevronDown, CheckCircle2,
  ShieldQuestion, Check, X, FileDown, MessageCircle,
  Mic, MicOff, Volume2, Loader2, Headphones, Square,
} from 'lucide-react'
import {
  Button,
  buttonVariants,
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
import {
  queryAgent, loadChatHistory, clearChatHistory,
  confirmAgentAction, dismissProposal,
} from '../../features/ia/store/iaSlice'
import useVoiceChat from '../../features/ia/voice/useVoiceChat'
import { LOOP_STATES } from '../../features/ia/voice/conversationLoop'

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
  const { messages, agentLoading, agentError, confirmingIndex, confirmError } = useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // AG11/AG12 — voix : micro + transcription + lecture vocale, et mode
  // conversation mains-libres. Toutes les API navigateur sont gardées (repli
  // texte si non supportées). La voix NE confirme JAMAIS automatiquement une
  // action sensible (la boucle attend un « confirmer » explicite — AG3 reste
  // la seule voie).
  const {
    recordingSupported, conversationSupported,
    recording, transcribing, speaking, voiceError,
    conversationMode, loopState,
    toggleRecording, startConversation, stopConversation,
  } = useVoiceChat()

  // Libellé d'état vocal courant pour l'affichage (et l'a11y).
  const voiceStatus = recording
    ? 'Écoute en cours…'
    : transcribing
      ? 'Transcription…'
      : speaking
        ? 'Lecture de la réponse…'
        : loopState === LOOP_STATES.AWAITING_CONFIRM
          ? 'En attente de confirmation — dites « confirmer » ou utilisez le bouton.'
          : null

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
      <div className="ui-root flex h-[calc(100dvh-7rem)] min-h-[28rem] flex-col gap-3">

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
          <div className="flex items-center gap-2">
            {/* AG12 — bascule « Mode conversation » (mains-libres). Visible
                uniquement si le navigateur le supporte (repli texte sinon). */}
            {conversationSupported && (
              conversationMode ? (
                <Button
                  variant="destructive"
                  size="sm"
                  data-testid="conversation-stop"
                  onClick={stopConversation}
                >
                  <Square className="size-4" aria-hidden="true" />
                  Arrêter
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  data-testid="conversation-toggle"
                  onClick={startConversation}
                  disabled={agentLoading}
                >
                  <Headphones className="size-4" aria-hidden="true" />
                  Mode conversation
                </Button>
              )
            )}
            {messages.length > 0 && (
              <Button variant="outline" size="sm" onClick={() => dispatch(clearChatHistory())}>
                Nouvelle conversation
              </Button>
            )}
          </div>
        </div>

        {/* AG11/AG12 — bandeau d'état vocal (écoute / transcription / lecture /
            attente de confirmation) + repli. */}
        {(voiceStatus || voiceError) && (
          <div
            role="status"
            aria-live="polite"
            data-testid="voice-status"
            className={cn(
              'flex items-center gap-2 rounded-lg border px-3 py-2 text-xs',
              voiceError
                ? 'border-destructive/30 bg-destructive/10 text-destructive'
                : 'border-primary/30 bg-primary/10 text-primary',
            )}
          >
            {recording && <Mic className="size-4 animate-pulse" aria-hidden="true" />}
            {transcribing && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {speaking && <Volume2 className="size-4" aria-hidden="true" />}
            <span>{voiceError || voiceStatus}</span>
          </div>
        )}

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

                  {/* AG3 — carte CONFIRMATION pour une action proposée */}
                  {msg.kind === 'proposal' && (
                    <div
                      data-testid="proposal-card"
                      className="mt-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-foreground"
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

                  {/* AG3 — carte RÉSULTAT pour une action terminée */}
                  {msg.kind === 'result' && (
                    <div
                      data-testid="result-card"
                      className="mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-foreground"
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
              {/* AG11 — micro : capture audio → /transcribe → flux question.
                  Masqué quand le mode conversation pilote déjà le micro, et
                  caché si le navigateur ne supporte pas l'enregistrement (repli
                  texte). */}
              {recordingSupported && !conversationMode && (
                <SimpleTooltip label={recording ? 'Arrêter l\'enregistrement' : 'Parler'}>
                  <IconButton
                    type="button"
                    variant={recording ? 'destructive' : 'outline'}
                    label={recording ? 'Arrêter l\'enregistrement' : 'Parler'}
                    data-testid="mic-button"
                    aria-pressed={recording}
                    disabled={agentLoading || transcribing}
                    onClick={toggleRecording}
                  >
                    {recording ? <MicOff /> : <Mic />}
                  </IconButton>
                </SimpleTooltip>
              )}
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

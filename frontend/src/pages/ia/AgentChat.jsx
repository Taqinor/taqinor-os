import { useState, useRef, useEffect, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Bot, MessageSquare, Send, CheckCircle2,
  Mic, MicOff, Volume2, Loader2, Headphones, Square,
} from 'lucide-react'
import {
  Button,
  IconButton,
  Card,
  CardContent,
  EmptyState,
  TooltipProvider,
  SimpleTooltip,
} from '../../ui'
import { cn } from '../../lib/cn'
import {
  MessageActions, NoteReponse, SuggestionButtons, TypingDots, QuestionForm, ErreurAgent,
} from '../../features/ia/ChatParts'
import {
  queryAgent, loadChatHistory, clearChatHistory,
} from '../../features/ia/store/iaSlice'
import {
  enterSubmits, CONFIG_MISSING_FR, isConfigMissing, routeNormalisee,
} from '../../features/ia/copilotMessages'
import useVoiceChat from '../../features/ia/voice/useVoiceChat'
import { prefersReducedMotion } from '../../ui/charts/chart-theme'
import iaApi from '../../api/iaApi'
import { useIsAdmin } from '../../hooks/useHasPermission'

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

// VX37 — reconnaît un tableau de lignes structurées (objets plats homogènes)
// éventuellement porté par le payload agent, pour un mini-tableau inline à la
// place du seul `<details><pre>` SQL brut. Défensif : jamais de plantage sur
// une forme inattendue, aucun changement backend requis (inerte tant qu'aucun
// payload ne porte ce champ).
function extractStructuredRows(msg) {
  const candidate = msg?.rows ?? msg?.data
  if (!Array.isArray(candidate) || candidate.length === 0) return null
  const isPlainRow = (r) => r && typeof r === 'object' && !Array.isArray(r)
  if (!candidate.every(isPlainRow)) return null
  const columns = Object.keys(candidate[0])
  if (columns.length === 0) return null
  return { columns, rows: candidate }
}

// VX37 — mini-tableau de données inline (preuve lisible par un non-développeur).
function StructuredRowsTable({ columns, rows }) {
  return (
    <div data-testid="structured-rows-table" className="mt-2 overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border bg-muted/60">
            {columns.map((col) => (
              <th key={col} className="px-2.5 py-1.5 font-medium text-muted-foreground">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {columns.map((col) => (
                <td key={col} className="px-2.5 py-1.5 text-foreground">{String(row[col] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// VX37 — révélation incrémentale du texte agent (le texte complet est déjà
// côté client : on l'affiche mot à mot via requestAnimationFrame, sans aucun
// appel réseau). `prefers-reduced-motion` affiche le texte instantanément.
// `active` ne rejoue le reveal que sur le DERNIER message agent au moment de
// son arrivée — les messages déjà affichés restent statiques.
function RevealText({ text, active }) {
  const words = useMemo(() => (text ? text.split(/(\s+)/) : []), [text])
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const animating = active && !reduced
  const [count, setCount] = useState(animating ? 0 : words.length)

  // Réinitialisation en phase de rendu quand le texte/l'état change (patron
  // React « ajuster l'état pendant le rendu ») — pas de setState synchrone
  // dans l'effet ; l'effet ne fait plus que piloter le rAF.
  const revealKey = `${text}\u0000${animating}`
  const [prevKey, setPrevKey] = useState(revealKey)
  if (revealKey !== prevKey) {
    setPrevKey(revealKey)
    setCount(animating ? 0 : words.length)
  }

  useEffect(() => {
    if (!animating) return undefined
    let i = 0
    let frame
    let lastTime = 0
    const STEP_MS = 28
    const tick = (t) => {
      if (t - lastTime >= STEP_MS) {
        lastTime = t
        i += 1
        setCount(i)
      }
      if (i < words.length) {
        frame = requestAnimationFrame(tick)
      }
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [revealKey, animating, words.length])

  return <>{words.slice(0, count).join('')}</>
}

// AIC12 — carte « Assistant : coût et qualité » (admin seul) : questions par
// commercial et par semaine, non-supporté, repli, coût estimé, manques
// récents — tous calculés par GET /agent/evenements/stats/ ; lien d'export.
const pourcent = (x) => `${Math.round((Number(x) || 0) * 100)} %`

function AssistantStatsCard() {
  const isAdmin = useIsAdmin()
  const [stats, setStats] = useState(null)
  useEffect(() => {
    if (!isAdmin) return undefined
    let actif = true
    iaApi.statsAssistant(4)
      .then((res) => { if (actif && res?.data) setStats(res.data) })
      .catch(() => {})
    return () => { actif = false }
  }, [isAdmin])
  if (!isAdmin || !stats) return null
  const chiffres = [
    ['Questions (4 sem.)', stats.questions],
    ['Commerciaux actifs', stats.commerciaux_actifs],
    ['Questions / commercial / semaine', stats.questions_par_commercial_semaine],
    ['Non supporté', pourcent(stats.taux_non_supporte)],
    ['Réponses par le repli', pourcent(stats.part_repli)],
    ['Coût estimé', `${Number(stats.cout_estime_usd || 0).toFixed(2)} $`],
  ]
  return (
    <Card data-testid="assistant-stats-card">
      <CardContent className="space-y-2 p-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <p className="font-semibold">Assistant : coût et qualité</p>
          <a className="text-xs underline" href="/api/django/agent/evenements/export/">exporter</a>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
          {chiffres.map(([libelle, valeur]) => (
            <div key={libelle}>
              <dt className="text-xs text-muted-foreground">{libelle}</dt>
              <dd className="font-medium">{valeur}</dd>
            </div>
          ))}
        </dl>
        {stats.manques_recents?.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {stats.manques_recents.map((m) => (
              <li key={m.question_anonymisee}>{m.question_anonymisee} ({m.vu_n_fois}×)</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export default function AgentChat() {
  const dispatch = useDispatch()
  const { messages, agentLoading, agentError } = useSelector((s) => s.ia)
  const [input, setInput] = useState('')
  // COP-F8 — les questions suggérées viennent du manifeste de l'écran (comme le
  // tiroir), la liste codée en dur (orientée stock) ne sert que de repli.
  const [suggestions, setSuggestions] = useState(SUGGESTIONS)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // AG11/AG12 — voix : micro + transcription + lecture vocale, et mode
  // conversation mains-libres. Toutes les API navigateur sont gardées (repli
  // texte si non supportées). La voix NE confirme JAMAIS automatiquement une
  // action sensible (la boucle attend un « confirmer » explicite — AG3 reste
  // la seule voie).
  // COP-F6 — la dictée REMPLIT la zone de saisie pour relecture (elle ne part
  // plus toute seule) ; aucune confirmation à la voix : on confirme d'un doigt.
  const {
    recordingSupported, conversationSupported,
    recording, transcribing, speaking, voiceError,
    conversationMode,
    toggleRecording, startConversation, stopConversation,
  } = useVoiceChat({
    onTexte: (texte) => setInput((prev) => (prev.trim() ? `${prev.trim()} ${texte}` : texte)),
  })

  // Libellé d'état vocal courant pour l'affichage (et l'a11y).
  const voiceStatus = recording
    ? 'Écoute en cours…'
    : transcribing
      ? 'Transcription…'
      : speaking
        ? 'Lecture de la réponse…'
        : null

  // Charge l'historique Redis au montage du composant
  useEffect(() => {
    dispatch(loadChatHistory())
  }, [dispatch])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading])

  useEffect(() => {
    let actif = true
    Promise.resolve(iaApi.getSuggestions?.(routeNormalisee(window.location.pathname)))
      .then((res) => {
        const liste = Array.isArray(res?.data) ? res.data.filter((q) => typeof q === 'string') : []
        if (actif && liste.length) setSuggestions(liste.slice(0, 7))
      })
      .catch(() => {})
    return () => { actif = false }
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || agentLoading) return
    // COP-F5 — le contexte (route, fiche, foyer) est lu à l'envoi par `queryAgent`.
    dispatch(queryAgent(q))
    setInput('')
  }

  const handleSuggestion = (text) => {
    if (agentLoading) return
    dispatch(queryAgent(text))
    inputRef.current?.focus()
  }

  const handleKeyDown = enterSubmits(handleSubmit)
  // Le moteur qui a servi la dernière réponse (champ `moteur` du serveur).
  const dernierMoteur = [...messages].reverse().find((m) => m.moteur)?.moteur ?? ''

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
                {dernierMoteur ? `Moteur ${dernierMoteur} · ` : ''}Données en temps réel
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

        <AssistantStatsCard />

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
                    <SuggestionButtons suggestions={suggestions} onPick={handleSuggestion}
 buttonClassName="h-auto whitespace-normal py-1.5 text-left" />
                  </div>
                }
              />
            )}

            {messages.map((msg, i) => {
              // VX37 — seul le DERNIER message agent (à son arrivée, tant que
              // l'agent n'est plus en train de charger) rejoue le reveal
              // incrémental ; les messages déjà affichés restent statiques.
              const isLastAgentMsg = msg.role === 'agent' && i === messages.length - 1 && !agentLoading
              const structuredRows = msg.role === 'agent' ? extractStructuredRows(msg) : null
              const displayText = msg.role === 'agent' && isConfigMissing(msg.content)
                ? CONFIG_MISSING_FR
                : msg.content
              return (
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
                  {displayText && (
                    <p className="whitespace-pre-wrap break-words">
                      {msg.role === 'agent'
                        ? <RevealText text={displayText} active={isLastAgentMsg} />
                        : displayText}
                    </p>
                  )}
                  {structuredRows && (
                    <StructuredRowsTable columns={structuredRows.columns} rows={structuredRows.rows} />
                  )}
                  {msg.action_performed && (
                    <span className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      Action effectuée
                    </span>
                  )}

                  {/* AG3 — carte CONFIRMATION pour une action proposée */}
                  <MessageActions msg={msg} index={i} variant="page" />
                  <NoteReponse msg={msg} index={i} />
                </div>
              </div>
              )
            })}

            {agentLoading && (
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Bot className="size-4" aria-hidden="true" />
                </span>
                <div className="flex items-center gap-1 rounded-xl bg-muted px-3.5 py-3">
                  <TypingDots />
                </div>
              </div>
            )}

            {agentError && <ErreurAgent error={agentError} />}

            <div ref={messagesEndRef} />
          </div>

          {/* ── Saisie ── */}
          <div className="border-t border-border bg-card p-3 sm:p-4">
            {messages.length > 0 && !agentLoading && (
              <div className="mb-2 flex flex-wrap gap-2">
                <SuggestionButtons suggestions={suggestions.slice(0, 3)} onPick={handleSuggestion}
 buttonClassName="h-auto whitespace-normal py-1 text-xs" />
              </div>
            )}
            <QuestionForm onSubmit={handleSubmit} inputRef={inputRef} input={input} setInput={setInput}
                onKeyDown={handleKeyDown} disabled={agentLoading}>
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
            </QuestionForm>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              L'agent peut faire des erreurs. Vérifiez les informations importantes.
            </p>
          </div>
        </Card>
      </div>
    </TooltipProvider>
  )
}

import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Bot, MessageSquare, Send, CheckCircle2,
} from 'lucide-react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Button, IconButton, EmptyState,
} from '../../ui'
import { cn } from '../../lib/cn'
import StateBlock from '../../components/StateBlock'
import {
  MessageActions, NoteReponse, SuggestionButtons, TypingDots, QuestionForm,
} from './ChatParts'
import {
  queryAgent, loadChatHistory, clearChatHistory,
  closeCopilot, openCopilot,
} from './store/iaSlice'
import iaApi from '../../api/iaApi'
import {
  displayMessageText, formatAgentError, canSendQuestion, enterSubmits,
  EVENEMENT_OUVRIR, contexteEcran,
} from './copilotMessages'

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
  // AIC9 — contexte posé par l'événement `EVENEMENT_OUVRIR` (sinon la route).
  const [contexte, setContexte] = useState(null)
  const [suggestions, setSuggestions] = useState(SUGGESTIONS)
  const ecranCourant = () => contexte?.ecran
    || (typeof window !== 'undefined' ? window.location.pathname : '/')

  useEffect(() => {
    if (open && !historyLoadedRef.current) {
      historyLoadedRef.current = true
      dispatch(loadChatHistory())
    }
  }, [open, dispatch])

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading, open])

  const send = (q, ctx = contexte) => {
    if (!canSendQuestion(q, agentLoading)) return
    const ecran = contexteEcran(ctx, window.location.pathname)
    dispatch(queryAgent({ question: q.trim(), contexte: ecran }))
  }

  // AIC9 — un module ouvre le panneau avec le contexte de SON écran.
  useEffect(() => {
    const ouvrir = (e) => {
      const detail = e?.detail || {}
      setContexte(detail)
      dispatch(openCopilot())
      const question = typeof detail.question === 'string' ? detail.question.trim() : ''
      if (question && detail.envoyer) {
        dispatch(queryAgent({ question, contexte: contexteEcran(detail, window.location.pathname) }))
      } else if (question) {
        setInput(question)
      }
    }
    window.addEventListener(EVENEMENT_OUVRIR, ouvrir)
    return () => window.removeEventListener(EVENEMENT_OUVRIR, ouvrir)
  }, [dispatch])

  // AIC9 — trois questions du manifeste pour l'écran, conversation vide.
  useEffect(() => {
    if (!open || messages.length > 0) return undefined
    let actif = true
    Promise.resolve(iaApi.getSuggestions?.(ecranCourant()))
      .then((res) => {
        const liste = Array.isArray(res?.data) ? res.data.filter((q) => typeof q === 'string') : []
        if (actif && liste.length) setSuggestions(liste.slice(0, 3))
      })
      .catch(() => {})
    return () => { actif = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, contexte, messages.length])

  const handleSubmit = (e) => {
    e.preventDefault()
    send(input)
    setInput('')
  }

  const handleSuggestion = (text) => {
    send(text)
    inputRef.current?.focus()
  }

  const handleKeyDown = enterSubmits(handleSubmit)

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
                  <SuggestionButtons suggestions={suggestions} onPick={handleSuggestion}
 buttonClassName="h-auto whitespace-normal py-1.5 text-left" />
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
                  <MessageActions msg={msg} index={i} variant="copilot"
 confirmingIndex={confirmingIndex} confirmError={confirmError} />
                  {/* AIC8 — 👍 / 👎 / « ça n'a pas répondu » sous chaque réponse. */}
                  <NoteReponse msg={msg} index={i} />
                </div>
              </div>
            ))}

            {agentLoading && (
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Bot className="size-3.5" aria-hidden="true" />
                </span>
                <div className="flex items-center gap-1 rounded-xl bg-muted px-3 py-2.5">
                  <TypingDots />
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
          <QuestionForm onSubmit={handleSubmit} inputRef={inputRef} input={input} setInput={setInput}
              onKeyDown={handleKeyDown} disabled={agentLoading}>
            <IconButton
              type="submit"
              variant="default"
              label="Envoyer"
              disabled={!canSendQuestion(input, agentLoading)}
            >
              <Send />
            </IconButton>
          </QuestionForm>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            L'agent peut faire des erreurs. Vérifiez les informations importantes.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

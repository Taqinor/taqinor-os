import { useState, useRef, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  Bot, MessageSquare, Send, CheckCircle2, Bug, Sparkles,
} from 'lucide-react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Button, IconButton, EmptyState, Textarea,
} from '../../ui'
import { cn } from '../../lib/cn'
import {
  MessageActions, NoteReponse, SuggestionButtons, BulleAttente, QuestionForm, ErreurAgent, MarqueurImages,
} from './ChatParts'
import {
  queryAgent, loadChatHistory, clearChatHistory,
  closeCopilot, openCopilot, chargerCapacitesAssistant,
} from './store/iaSlice'
import useImagesJointes from './useImagesJointes'
import iaApi from '../../api/iaApi'
import {
  displayMessageText, canSendQuestion, enterSubmits,
  EVENEMENT_OUVRIR, routeNormalisee, PHRASE_SIGNALEMENT, CAPACITES_PAR_DEFAUT,
} from './copilotMessages'
import { instantaneDiagnostic } from '../../lib/tamponDiagnostic'
import { signalerPanneauMonte, prendreEnAttente } from './ecouteurOuverture'
// TCH118 / A12 — les quatre demandes prêtes de Tâches, sans modèle de langage.
import { ajouterMessageLocal } from './store/iaSlice'
import {
  DEMANDES_PRETES_TACHES, demandePreteTaches, estEcranTaches, lancerDemandePrete,
} from './copilotMessages'
// F3 acceptation ERR 3 — textes du panneau ouvert depuis un écran Tâches (textes.md §5.2).
import {
  CHAMP_TACHES, PHRASE_SANS_CONVERSATION, conversationLibreAbsente, nomEcranTaches,
} from './copilotMessages'
import * as tachesApi from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'

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

/** Passe visuelle n° 50 — un message du tiroir ouvert depuis Tâches (copilote.html) : la question dans la bulle
 *  d'accent `.ep-bulle-moi`, la réponse en texte simple `.ep-bulle-ia`, et ses cartes pleine largeur, sans bulle ni
 *  avatar autour (une carte Tâches = une seule carte, variante `copilot_taches` de CartesDuMessage). */
function MessageTaches({ msg, index }) {
  const texte = displayMessageText(msg)
  return (
    <div data-bulle={msg.role}>
      {texte ? (
        <div className="tch">
          <p className={msg.role === 'user' ? 'ep-bulle-moi' : 'ep-bulle-ia'}>{texte}</p>
        </div>
      ) : null}
      <MarqueurImages msg={msg} />
      {msg.action_performed && (
        <span className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="size-3.5" aria-hidden="true" />
          Action effectuée
        </span>
      )}
      <MessageActions msg={msg} index={index} variant="copilot_taches" />
      <NoteReponse msg={msg} index={index} />
    </div>
  )
}

export default function CopilotPanel() {
  const dispatch = useDispatch()
  const open = useSelector((s) => s.ia.copilotOpen)
  const { messages, agentLoading, agentError, etapes } = useSelector((s) => s.ia)
  // COP2-W2 — ce que le serveur permet à ce compte (longueur d'une question, images) ; défauts tant qu'il n'a pas répondu.
  const capacites = useSelector((s) => s.ia.capacites) ?? CAPACITES_PAR_DEFAUT
  const joints = useImagesJointes({ acceptees: capacites.images_acceptees })
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  // L'historique n'est chargé qu'une fois, à la première ouverture du tiroir.
  const historyLoadedRef = useRef(false)
  const [suggestions, setSuggestions] = useState(SUGGESTIONS)
  // COP-F7 — « Signaler un bug » : une phrase libre, puis le tampon technique.
  const [signalement, setSignalement] = useState(null)
  // A12 (TCH118) — sur un écran `/taches…`, pour un compte qui a le module (`taches_voir`, la garde
  // de ses routes), les quatre demandes prêtes appellent DIRECTEMENT la route déterministe : ni
  // modèle de langage ni clé d'IA ; ailleurs, rien ne change.
  const permissions = useSelector((s) => s.auth?.permissions)
  const [demandeEnCours, setDemandeEnCours] = useState(false)
  const demandesTaches = open && Array.isArray(permissions) && permissions.includes('taches_voir')
    && estEcranTaches(routeNormalisee(window.location.pathname))
  // ERR 3 — sans clé d'IA (dit par la réponse du service), le champ laisse la place à la phrase de §5.2.
  const sansConversationTaches = demandesTaches && conversationLibreAbsente(messages)
  // Passe visuelle n° 49 — la demande prête qu'on vient d'envoyer reste marquée (maquette copilote.html, `.envoyee`).
  const derniereQuestion = demandesTaches ? [...messages].reverse().find((m) => m.role === 'user')?.content : null

  useEffect(() => {
    if (open && !historyLoadedRef.current) {
      historyLoadedRef.current = true
      dispatch(loadChatHistory())
    }
  }, [open, dispatch])

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading, open])

  // COP2-W2 — les capacités se relisent à chaque ouverture (le réglage du compte a pu changer).
  useEffect(() => {
    if (open) dispatch(chargerCapacitesAssistant())
  }, [open, dispatch])

  // COP-F5 — le contexte (route, fiche ouverte, foyer) est lu par `queryAgent`
  // AU MOMENT de l'envoi : jamais l'état d'une ouverture précédente.
  // Rend `true` quand la question est partie (la saisie ne se vide qu'alors : une question trop longue reste là).
  const send = (q, images = []) => {
    if (!canSendQuestion(q, agentLoading, capacites.limite_question)) return false
    dispatch(queryAgent(images.length
      ? { question: q.trim(), images: images.map(({ media_type, data }) => ({ media_type, data })) }
      : q.trim()))
    return true
  }

  // AIC9 — un module ouvre le panneau avec le contexte de SON écran ; ce
  // contexte ne vaut que pour la question qu'il envoie (jamais mémorisé).
  useEffect(() => {
    const ouvrir = (detail = {}) => {
      dispatch(openCopilot())
      const question = typeof detail.question === 'string' ? detail.question.trim() : ''
      if (question && detail.envoyer) dispatch(queryAgent({ question, detail }))
      else if (question) setInput(question)
    }
    const surEvenement = (e) => ouvrir(e?.detail || {})
    window.addEventListener(EVENEMENT_OUVRIR, surEvenement)
    // COP-F5 — une demande émise AVANT le montage du panneau (premier clic).
    signalerPanneauMonte(true)
    const enAttente = prendreEnAttente()
    if (enAttente) ouvrir(enAttente)
    return () => {
      signalerPanneauMonte(false)
      window.removeEventListener(EVENEMENT_OUVRIR, surEvenement)
    }
  }, [dispatch])

  // AIC9 — trois questions du manifeste pour l'écran, conversation vide.
  useEffect(() => {
    if (!open || messages.length > 0) return undefined
    if (demandesTaches) return undefined // les quatre demandes prêtes sont déjà là, service ou pas
    let actif = true
    Promise.resolve(iaApi.getSuggestions?.(routeNormalisee(window.location.pathname)))
      .then((res) => {
        const liste = Array.isArray(res?.data) ? res.data.filter((q) => typeof q === 'string') : []
        if (actif && liste.length) setSuggestions(liste.slice(0, 3))
      })
      .catch(() => {})
    return () => { actif = false }
  }, [open, messages.length, demandesTaches])

  // « Range ma liste » range les tâches À trier : leurs ids viennent de l'API Tâches, jamais devinés.
  const lancerDemandeTaches = async (question) => {
    const demande = demandePreteTaches(question)
    if (!demande || agentLoading || demandeEnCours) return
    dispatch(ajouterMessageLocal({ role: 'user', content: question }))
    setDemandeEnCours(true)
    try {
      const ids = demande.lire === 'saisieRapide'
        ? ((await tachesApi.listerToutesLesTaches({ vue: 'boite' })) ?? []).map((t) => t.id) : []
      const msg = await lancerDemandePrete(question, { client: tachesApi, ids })
      dispatch(ajouterMessageLocal(msg ? { ...msg, local: true } : { role: 'agent', content: 'Rien à trier', local: true }))
    } catch (err) {
      dispatch(ajouterMessageLocal({ role: 'agent', content: frenchError(err), local: true }))
    } finally {
      setDemandeEnCours(false)
    }
  }

  const envoyerSignalement = () => {
    const phrase = (signalement || '').trim()
    if (!phrase || agentLoading) return
    dispatch(queryAgent({
      question: `${PHRASE_SIGNALEMENT} ${phrase}`, diagnostic: instantaneDiagnostic(),
    }))
    setSignalement(null)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (joints.occupe) return // une image est encore en cours de réduction
    if (send(input, joints.images)) {
      setInput('')
      joints.vider()
    }
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
            {/* Passe visuelle n° 49 — ouvert depuis Tâches : le logo ✦ de la maquette (copilote.html, `.ep-ia-tete .logo`). */}
            {demandesTaches ? (
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--tch-accent-doux)] text-[var(--tch-accent)]"
                data-logo="copilote-taches">
                <Sparkles className="size-4" aria-hidden="true" />
              </span>
            ) : (
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                <Bot className="size-4" aria-hidden="true" />
              </span>
            )}
            Copilote
          </SheetTitle>
          <SheetDescription>
            {demandesTaches
              ? `ouvert depuis ${nomEcranTaches(routeNormalisee(window.location.pathname))}`
              : 'Posez une question sur vos données — réponses en temps réel.'}
          </SheetDescription>
          <Button
            variant="outline" size="sm" className="min-h-10 self-start"
            onClick={() => setSignalement((v) => (v == null ? '' : null))}
          >
            <Bug className="size-4" aria-hidden="true" />
            Signaler un bug
          </Button>
        </SheetHeader>

        {signalement != null && (
          <div className="space-y-2 border-b border-border px-4 py-3" data-testid="signalement-bug">
            <Textarea
              rows={2} value={signalement} onChange={(e) => setSignalement(e.target.value)}
              placeholder="Que faisiez-vous quand ça s’est mal passé ?"
              aria-label="Que faisiez-vous ?"
            />
            <Button size="sm" className="min-h-10" disabled={!signalement.trim() || agentLoading} onClick={envoyerSignalement}>
              Envoyer le signalement
            </Button>
          </div>
        )}

        {/* ── Zone messages ── */}
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-3">
          {/* Passe visuelle n° 49 — les quatre demandes prêtes en puces teintées de la maquette (`.ep-demandes`,
              styles/taches/coeur.css), sous une racine `.tch` : le panneau vit hors du module. */}
          {demandesTaches && (
            <div className="tch">
              <div className="ep-demandes" role="group" aria-label="Demandes prêtes">
                {DEMANDES_PRETES_TACHES.map((d) => (
                  <button key={d.question} type="button" className={d.question === derniereQuestion ? 'envoyee' : undefined}
                    disabled={agentLoading || demandeEnCours} onClick={() => lancerDemandeTaches(d.question)}>
                    {d.question}
                  </button>
                ))}
              </div>
            </div>
          )}
          {/* n° 49 — ouvert depuis Tâches, ni l'accueil ni les questions de l'assistant ERP (« rupture de stock »…) :
              les quatre demandes prêtes en tiennent lieu (textes.md §5.2). */}
          {messages.length === 0 && !agentLoading && !demandesTaches && (
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
            {messages.map((msg, i) => (demandesTaches ? <MessageTaches key={i} msg={msg} index={i} /> : (
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
                  {displayMessageText(msg) && (
                    <p className="whitespace-pre-wrap break-words">
                      {displayMessageText(msg)}
                    </p>
                  )}
                  <MarqueurImages msg={msg} />
                  {msg.action_performed && (
                    <span className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      Action effectuée
                    </span>
                  )}

                  {/* AG3 — carte CONFIRMATION pour une action proposée. La voie
                      /confirm reste la SEULE manière d'exécuter une action
                      sensible : jamais de confirmation automatique. */}
                  <MessageActions msg={msg} index={i} variant="copilot" />
                  {/* AIC8 — 👍 / 👎 / « ça n'a pas répondu » sous chaque réponse. */}
                  <NoteReponse msg={msg} index={i} />
                </div>
              </div>
            )))}

            {agentLoading && (
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Bot className="size-3.5" aria-hidden="true" />
                </span>
                <BulleAttente etapes={etapes} bulleClassName="px-3 py-2.5" />
              </div>
            )}

            {agentError && <ErreurAgent error={agentError} />}
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
          {sansConversationTaches ? (
            <p className="text-sm text-muted-foreground" role="status">{PHRASE_SANS_CONVERSATION}</p>
          ) : (
          <QuestionForm onSubmit={handleSubmit} inputRef={inputRef} input={input} setInput={setInput}
              onKeyDown={handleKeyDown} disabled={agentLoading}
              limite={capacites.limite_question} joints={joints}
              {...(demandesTaches ? { placeholder: CHAMP_TACHES } : {})}>
            <IconButton
              type="submit"
              variant="default"
              label="Envoyer"
              disabled={!canSendQuestion(input, agentLoading, capacites.limite_question) || joints.occupe}
            >
              <Send />
            </IconButton>
          </QuestionForm>
          )}
          <p className="mt-2 text-center text-xs text-muted-foreground">
            L'agent peut faire des erreurs. Vérifiez les informations importantes.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  )
}

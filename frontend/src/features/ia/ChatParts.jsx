import { useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import { Code2, ChevronDown, ThumbsUp, ThumbsDown, Paperclip, Send, X } from 'lucide-react'
import { Button, IconButton, Textarea } from '../../ui'
import { noterEvenement } from './store/iaSlice'
import CartesDuMessage from './cartes/CartesDuMessage'
import StateBlock from '../../components/StateBlock'
import {
  COMMENTAIRE_MAX, NOTE_NEGATIVE, NOTE_POSITIVE, IMAGES_MAX, LIMITE_QUESTION_DEFAUT,
  formatAgentError, etatCompteur, marqueurImages, canSendQuestion,
} from './copilotMessages'
import { fichierImageOk } from './images'

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

// Erreur de l'assistant : une phrase française (jamais du JSON brut, EZ16).
export function ErreurAgent({ error }) {
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10">
      <StateBlock error={formatAgentError(error)} />
    </div>
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

// AIC91 — bulle d'attente partagée (panneau et page) : points + dernière étape du tour.
export function BulleAttente({ etapes = [], bulleClassName }) {
  return (
    <div className="flex flex-col gap-1">
      <div className={`flex items-center gap-1 rounded-xl bg-muted ${bulleClassName}`}>
        <TypingDots />
      </div>
      {etapes.map((e, i) => (
        <p key={`${i}-${e}`} className="text-xs text-muted-foreground" data-testid="etape-en-cours" aria-live="polite">{e}</p>
      ))}
    </div>
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

// COP2-W2 — « [image jointe] » : ce que l'historique garde d'un message de l'utilisateur qui portait une image
// (le magasin n'en conserve que le nombre, jamais l'image).
export function MarqueurImages({ msg, className = '' }) {
  const texte = marqueurImages(msg)
  if (!texte) return null
  return <p className={`min-w-0 break-words text-xs opacity-80 ${className}`} data-testid="marqueur-images">{texte}</p>
}

// COP2-W2 — ligne sous le champ quand une image est jointe (texte exact demandé par le fondateur).
const AVERTISSEMENT_IMAGES = "Jamais de facture ni de pièce d'identité."

// COP2-W2 — miniatures des images jointes, chacune avec son bouton « Retirer » (zone tactile ≥ 40 px).
function MiniaturesJointes({ joints }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-2.5" data-testid="images-jointes">
      {joints.images.map((im, i) => (
        <li key={im.id} className="relative">
          <img src={im.apercu} alt={`Image jointe ${i + 1}`} className="size-16 rounded-md border border-border object-cover" />
          <button
            type="button" aria-label={`Retirer l'image ${i + 1}`} onClick={() => joints.retirer(im.id)}
            className="absolute -right-2 -top-2 flex size-7 items-center justify-center rounded-full border border-border bg-background text-foreground shadow before:absolute before:-inset-1.5 before:content-['']"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </li>
      ))}
    </ul>
  )
}

// `placeholder` : F3 acceptation ERR 3 — « Écris ou dicte… » depuis un écran Tâches (textes.md §5.2) ; ailleurs, le défaut.
// COP2-W2 — `limite` : longueur maximale lue chez le serveur (compteur près de la limite) ; `joints` : le retour de
// `useImagesJointes` (le bouton « Joindre une image », le collage et les miniatures n'existent que si le serveur
// accepte les images pour ce compte). Sans ces deux propriétés, le formulaire est celui d'avant.
export function QuestionForm({
  onSubmit, inputRef, input, setInput, onKeyDown, disabled, children, placeholder = 'Posez votre question en français…',
  limite = LIMITE_QUESTION_DEFAUT, joints = null,
}) {
  const choixFichiers = useRef(null)
  const images = joints?.acceptees ? joints : null
  const compteur = etatCompteur(input, limite)
  const surColle = (e) => {
    if (!images) return
    const fichiers = Array.from(e.clipboardData?.files ?? []).filter(fichierImageOk)
    if (fichiers.length === 0) return // collage de TEXTE : comportement normal
    e.preventDefault()
    images.ajouter(fichiers)
  }
  return (
    <form className="flex flex-col gap-1.5" onSubmit={onSubmit}>
      {images && images.images.length > 0 && <MiniaturesJointes joints={images} />}
      <div className="flex items-end gap-2">
        <Textarea
          ref={inputRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onPaste={surColle}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          aria-describedby={compteur.visible ? 'compteur-question' : undefined}
          className="max-h-32 min-h-[var(--control-h)] resize-none py-2.5"
        />
        {images && (
          <>
            <input
              ref={choixFichiers} type="file" accept="image/*" multiple hidden data-testid="images-input"
              onChange={(e) => { images.ajouter(e.target.files); e.target.value = '' }}
            />
            <IconButton
              type="button" variant="outline" label="Joindre une image" data-testid="images-joindre"
              disabled={disabled || images.images.length >= IMAGES_MAX || images.occupe}
              onClick={() => choixFichiers.current?.click()}
            >
              <Paperclip />
            </IconButton>
          </>
        )}
        {children}
      </div>
      {images && images.images.length > 0 && (
        <p className="min-w-0 break-words text-xs text-muted-foreground" data-testid="images-avertissement">
          {AVERTISSEMENT_IMAGES}
        </p>
      )}
      {images?.erreur && (
        <p className="min-w-0 break-words text-xs text-destructive" role="alert" data-testid="images-erreur">{images.erreur}</p>
      )}
      {compteur.visible && (
        <p
          id="compteur-question" data-testid="compteur-question" aria-live="polite"
          className={`text-right text-xs ${compteur.depasse ? 'font-medium text-destructive' : 'text-muted-foreground'}`}
        >
          {compteur.depasse ? `Trop long : ${compteur.n} / ${compteur.limite} caractères.` : `${compteur.n} / ${compteur.limite}`}
        </p>
      )}
    </form>
  )
}

/** Bouton « Envoyer » des deux écrans de l'assistant (tiroir et page) : éteint
 *  tant que la question n'est pas envoyable ou qu'une image se réduit encore. */
export function BoutonEnvoyer({ input, loading, limite, occupe }) {
  return (
    <IconButton
      type="submit"
      variant="default"
      label="Envoyer"
      disabled={!canSendQuestion(input, loading, limite) || occupe}
    >
      <Send />
    </IconButton>
  )
}

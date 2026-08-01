// EZ15 — Dictée INLINE au BUREAU (Web Speech du navigateur).
// ----------------------------------------------------------------------------
// FRONTIÈRE NETTE avec NTMOB30, qui possède le TERRAIN :
//   • NTMOB30 = enregistrement audio + transcription SERVEUR (Whisper) pour les
//     surfaces terrain/mobile (une intervention, une checklist de chantier).
//   • EZ15 = dictée INLINE navigateur (`webkitSpeechRecognition`, fr-FR, texte
//     qui arrive AU FIL de la parole dans le champ), zéro backend, zéro clé,
//     pour le BUREAU : le composer du chatter lead, la note de ticket SAV, le
//     motif de perte.
// JAMAIS DEUX BOUTONS MICRO SUR UN MÊME CHAMP. Un champ terrain n'a que
// NTMOB30 ; un champ bureau n'a que celui-ci.
//
// HONNÊTETÉ SUR LA CONFIDENTIALITÉ (à ne jamais adoucir) : l'audio n'est PAS
// traité localement. `webkitSpeechRecognition` envoie le flux au service de
// reconnaissance DU NAVIGATEUR — Google pour Chrome et Edge. C'est écrit dans
// le HelpTip posé à côté du bouton, en clair.
//
// SUPPORT RÉEL (mesuré par la présence de l'API, jamais par un user-agent) :
//   • Chrome / Edge (bureau) : OK.
//   • Firefox : l'API n'existe pas → le bouton n'est pas rendu, le champ est
//     STRICTEMENT inchangé.
//   • Safari : partiel. Sur iPhone, le clavier natif dicte déjà — un second
//     micro serait du bruit.
//   • HTTPS + permission micro obligatoires ; un refus de permission n'est pas
//     une erreur à toaster, c'est une réponse : on s'arrête, en silence.
//   • Coupure automatique après ~60 s de silence : on RELANCE tant que
//     l'utilisateur n'a pas arrêté lui-même (sinon la dictée « meurt » au
//     milieu d'une phrase sans que personne ne comprenne pourquoi).
import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { cn } from '../lib/cn'

/** Constructeur Web Speech du navigateur, ou null. Testable : la détection
    passe par CETTE fonction, jamais par un sniffing de user-agent. */
export function getSpeechRecognition(win = typeof window !== 'undefined' ? window : undefined) {
  if (!win) return null
  return win.SpeechRecognition || win.webkitSpeechRecognition || null
}

/** isDictationSupported — le bouton ne se rend QUE si c'est vrai. */
export function isDictationSupported(win) {
  return getSpeechRecognition(win) != null
}

/**
 * DictationButton — micro de dictée inline.
 *
 * @param {object} props
 * @param {(texte: string) => void} props.onText  reçoit le texte FINAL de
 *   chaque segment reconnu (l'appelant décide comment il l'ajoute à son champ —
 *   ce composant ne touche jamais la valeur lui-même).
 * @param {string} [props.lang='fr-FR']
 * @param {string} [props.label='Dicter']  nom accessible de base.
 * @param {boolean} [props.disabled]
 */
export function DictationButton({
  onText, lang = 'fr-FR', label = 'Dicter', disabled = false, className,
}) {
  const [ecoute, setEcoute] = useState(false)
  const recRef = useRef(null)
  // L'utilisateur a-t-il demandé l'arrêt ? Distingue un `onend` de fin de
  // silence (à relancer) d'un arrêt volontaire (à respecter).
  const vouluRef = useRef(false)
  const onTextRef = useRef(onText)
  useEffect(() => { onTextRef.current = onText })

  // Rendu conditionnel : sur un navigateur sans l'API, il n'y a pas de bouton
  // du tout — le champ est strictement celui d'avant.
  const supporte = isDictationSupported()

  const arreter = useCallback(() => {
    vouluRef.current = true
    try { recRef.current?.stop() } catch { /* déjà arrêtée */ }
    setEcoute(false)
  }, [])

  // Arrêt propre au démontage : une reconnaissance laissée ouverte garderait le
  // micro actif après la fermeture du panneau.
  useEffect(() => () => {
    vouluRef.current = true
    try { recRef.current?.stop() } catch { /* no-op */ }
  }, [])

  const demarrer = useCallback(() => {
    const Ctor = getSpeechRecognition()
    if (!Ctor) return
    const rec = new Ctor()
    rec.lang = lang
    rec.continuous = true
    rec.interimResults = true
    rec.onresult = (e) => {
      let final = ''
      for (let i = e.resultIndex; i < e.results.length; i += 1) {
        const r = e.results[i]
        if (r.isFinal) final += r[0].transcript
      }
      if (final.trim()) onTextRef.current?.(final.trim())
    }
    rec.onerror = (e) => {
      // Un refus de permission (ou l'absence de parole) n'est pas une panne :
      // on s'arrête sans crier. Le seul vrai signal, c'est que le micro
      // s'éteint.
      if (e?.error === 'not-allowed' || e?.error === 'service-not-allowed') {
        vouluRef.current = true
      }
      setEcoute(false)
    }
    rec.onend = () => {
      // Le navigateur coupe tout seul après ~60 s de silence : on relance tant
      // que l'utilisateur n'a pas arrêté lui-même.
      if (vouluRef.current) { setEcoute(false); return }
      try { rec.start() } catch { setEcoute(false) }
    }
    vouluRef.current = false
    recRef.current = rec
    try {
      rec.start()
      setEcoute(true)
    } catch {
      setEcoute(false)
    }
  }, [lang])

  if (!supporte) return null

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => (ecoute ? arreter() : demarrer())}
      aria-pressed={ecoute}
      aria-label={ecoute ? `${label} — arrêter la dictée` : label}
      title={ecoute ? 'Arrêter la dictée' : 'Dicter (micro)'}
      className={cn(
        'inline-flex size-8 shrink-0 items-center justify-center rounded-md border border-input',
        'bg-card text-muted-foreground transition-colors hover:text-foreground focus-ring',
        'disabled:cursor-not-allowed disabled:opacity-60',
        ecoute && 'border-destructive/50 text-destructive',
        className,
      )}
    >
      {ecoute
        ? <MicOff className="size-4" aria-hidden="true" />
        : <Mic className="size-4" aria-hidden="true" />}
    </button>
  )
}

/** Le texte de confidentialité, EXPORTÉ pour que les trois surfaces disent
    exactement la même chose — et qu'aucune ne l'adoucisse. */
export const DICTATION_PRIVACY_FR = "La dictée utilise le service de reconnaissance vocale de votre navigateur : sur Chrome et Edge, l'audio est envoyé à Google. Ce n'est pas une transcription locale. Le bouton n'apparaît que sur les navigateurs qui proposent cette fonction, en HTTPS et après votre autorisation du micro."

export default DictationButton

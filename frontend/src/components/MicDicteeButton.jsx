import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { cn } from '../lib/cn'
import { getSpeechRecognition, isDictationSupported } from '../ui/DictationButton'

/* MicDicteeButton — bouton micro partagé (dictée vocale) pour les champs de
   notes/consignes du suivi commercial et des messages d'accueil.

   Réutilise la détection Web Speech de `ui/DictationButton.jsx` (EZ15,
   `getSpeechRecognition`/`isDictationSupported` — UNE seule source de vérité
   pour « ce navigateur sait-il dicter ? », jamais un sniffing dupliqué)
   mais ajoute, par rapport à EZ15, un message COURT visible sous le bouton
   en cas de refus de permission — EZ15 reste silencieux par choix (bureau,
   déjà accompagné d'un HelpTip) ; ici l'appelant n'a pas forcément ce
   contexte, donc l'échec doit se voir, jamais planter.

   webkitSpeechRecognition/SpeechRecognition (feature-detect ; MASQUÉ si
   absent), lang 'fr-FR', interimResults ; à chaque résultat FINAL, appelle
   `onTexte(texte)` — l'appelant décide comment l'ajouter à son champ (jamais
   modifié ici directement). JAMAIS deux boutons micro sur un même champ
   (cf. EZ15) : ce composant sert les champs qui n'ont pas déjà `DictationButton`. */
export default function MicDicteeButton({
  onTexte, lang = 'fr-FR', label = 'Dicter', disabled = false, className,
}) {
  const [ecoute, setEcoute] = useState(false)
  const [erreur, setErreur] = useState('')
  const recRef = useRef(null)
  // Arrêt VOULU par l'utilisateur ? Distingue une coupure de silence (à
  // relancer) d'un arrêt volontaire (à respecter) — même patron qu'EZ15.
  const vouluRef = useRef(false)
  const onTexteRef = useRef(onTexte)
  useEffect(() => { onTexteRef.current = onTexte })

  const supporte = isDictationSupported()

  const arreter = useCallback(() => {
    vouluRef.current = true
    try { recRef.current?.stop() } catch { /* déjà arrêtée */ }
    setEcoute(false)
  }, [])

  // Arrêt propre au démontage — un micro laissé ouvert survivrait à la
  // fermeture du formulaire.
  useEffect(() => () => {
    vouluRef.current = true
    try { recRef.current?.stop() } catch { /* no-op */ }
  }, [])

  const demarrer = useCallback(() => {
    const Ctor = getSpeechRecognition()
    if (!Ctor) return
    setErreur('')
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
      if (final.trim()) onTexteRef.current?.(final.trim())
    }
    rec.onerror = (e) => {
      if (e?.error === 'not-allowed' || e?.error === 'service-not-allowed') {
        vouluRef.current = true
        setErreur('Autorisez le micro dans votre navigateur pour dicter.')
      }
      setEcoute(false)
    }
    rec.onend = () => {
      // Coupure automatique après un silence prolongé : on relance tant que
      // l'utilisateur n'a pas arrêté lui-même.
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
    <div className="inline-flex flex-col items-center gap-1">
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
      {erreur && (
        <p role="alert" className="max-w-[8rem] text-center text-[10px] leading-tight text-destructive">
          {erreur}
        </p>
      )}
    </div>
  )
}

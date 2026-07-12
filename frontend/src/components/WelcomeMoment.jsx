import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import TaqinorMark from '../ui/TaqinorMark'
import { voice } from '../lib/voice'

/* VX156 — LE MOMENT D'ACCUEIL : à la toute première connexion, un panneau
   one-shot (mot-symbole animé + phrase de mission + « Commencer »), affiché
   UNE SEULE FOIS puis plus jamais. Ce n'est PAS le tour fonctionnel des
   coachmarks (FG16) : c'est l'accueil de marque.

   Flag localStorage DÉFENSIF (@coord safeStorage, VXD-B) : tout accès est
   enveloppé dans un try/catch — un navigateur en navigation privée / stockage
   bloqué ne doit jamais faire planter la coquille (au pire, l'accueil se
   réaffiche, il n'est jamais bloquant). */

const SEEN_KEY = 'taqinor:welcome:seen:v1'

function seenAlready() {
  try {
    return window.localStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false
  }
}
function markSeen() {
  try {
    window.localStorage.setItem(SEEN_KEY, '1')
  } catch {
    /* stockage indisponible : silencieux (non bloquant). */
  }
}

export default function WelcomeMoment() {
  // Ne s'affiche que pour un utilisateur connecté (première connexion réelle).
  const user = useSelector((s) => s.auth?.user)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot welcome on first login
    if (user && !seenAlready()) setOpen(true)
  }, [user])

  const dismiss = () => {
    markSeen()
    setOpen(false)
  }

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-moment-title"
      onClick={dismiss}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-card p-8 text-center shadow-ui-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex justify-center">
          <TaqinorMark size={64} animate />
        </div>
        <h2
          id="welcome-moment-title"
          className="font-display text-xl font-bold tracking-tight text-foreground"
        >
          {voice.welcome.title}
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {voice.welcome.mission}
        </p>
        <div className="mt-6 flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={dismiss}
            className="btn inline-flex items-center justify-center rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            {voice.welcome.cta}
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {voice.welcome.skip}
          </button>
        </div>
      </div>
    </div>
  )
}

// NTMOB18 — écran de verrouillage local, monté par `Layout` (donc sur tout
// écran authentifié). Rend `null` — coût zéro — tant que le verrou n'est pas
// activé sur cet appareil. Quand il l'est, il pose l'horloge de mise en veille
// et affiche un voile plein écran au retour au premier plan après le délai.
// La logique pure (persistance, WebAuthn, PIN haché) vit dans `appLock.js`.
import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import {
  isAppLockEnabled, markHidden, clearHidden, shouldLock,
  verifyBiometric, verifyPin, hasPin, hasBiometricCredential,
} from './appLock'

export default function AppLockGate() {
  // Initialisation PARESSEUSE : un rechargement de page survenu pendant la
  // veille doit rendre l'écran déjà verrouillé, sans passer par un setState
  // dans l'effet (cascade de rendus).
  const [locked, setLocked] = useState(() => shouldLock())
  const [pin, setPin] = useState('')
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    if (!isAppLockEnabled()) return undefined
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        markHidden()
      } else if (shouldLock()) {
        setLocked(true)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  const deverrouiller = () => {
    clearHidden()
    setPin('')
    setErreur('')
    setLocked(false)
  }

  const parBiometrie = async () => {
    setErreur('')
    if (await verifyBiometric()) deverrouiller()
    else setErreur('Vérification biométrique refusée.')
  }

  const parPin = async (e) => {
    e.preventDefault()
    setErreur('')
    if (await verifyPin(pin)) deverrouiller()
    else setErreur('Code incorrect.')
  }

  if (!locked) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Application verrouillée"
      data-app-lock="1"
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center gap-4 bg-background p-6 text-center"
    >
      <Lock className="size-10 text-muted-foreground" aria-hidden="true" />
      <h2 className="text-lg font-semibold text-foreground">Application verrouillée</h2>
      <p className="max-w-xs text-sm text-muted-foreground">
        Déverrouillez pour afficher à nouveau vos données. Votre session reste
        ouverte — c'est l'écran qui est protégé.
      </p>
      {hasBiometricCredential() && (
        <button
          type="button"
          onClick={parBiometrie}
          className="h-10 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground"
        >
          Déverrouiller avec la biométrie
        </button>
      )}
      {hasPin() && (
        <form onSubmit={parPin} className="flex flex-col items-center gap-2">
          <label htmlFor="app-lock-pin" className="text-xs text-muted-foreground">
            Ou saisissez votre code
          </label>
          <input
            id="app-lock-pin"
            type="password"
            inputMode="numeric"
            autoComplete="off"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className="h-10 w-32 rounded-md border border-border bg-card px-2 text-center text-sm text-foreground"
          />
          <button type="submit" className="h-9 rounded-md border border-border px-3 text-sm">
            Valider
          </button>
        </form>
      )}
      {erreur && <p role="alert" className="text-sm text-destructive">{erreur}</p>}
    </div>
  )
}

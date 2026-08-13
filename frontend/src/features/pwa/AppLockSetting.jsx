// NTMOB18 — réglage « Verrouiller avec Face ID / empreinte » dans Mes
// préférences. Propre à CET APPAREIL (comme le reste du panneau) : activer le
// verrou sur son téléphone ne verrouille pas le poste du bureau.
import { useState } from 'react'
import { Switch } from '../../ui/Switch'
import {
  isAppLockEnabled, disableAppLock, enrollBiometric, isBiometricApiAvailable,
  getLockDelayMinutes, setLockDelayMinutes, setPin, hasPin,
} from './appLock'

const DELAIS = [1, 5, 15, 60]

export default function AppLockSetting() {
  const [actif, setActif] = useState(isAppLockEnabled)
  const [delai, setDelai] = useState(getLockDelayMinutes)
  const [codePin, setCodePin] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const supporte = isBiometricApiAvailable()

  const onToggle = async (checked) => {
    setMessage('')
    if (!checked) {
      disableAppLock()
      setActif(false)
      return
    }
    setBusy(true)
    try {
      const ok = await enrollBiometric()
      setActif(ok)
      setMessage(ok
        ? ''
        : "La biométrie n'a pas pu être enrôlée sur cet appareil. Définissez un code de secours ci-dessous pour activer le verrouillage.")
    } finally {
      setBusy(false)
    }
  }

  const enregistrerPin = async () => {
    if (codePin.length < 4) {
      setMessage('Le code doit comporter au moins 4 chiffres.')
      return
    }
    await setPin(codePin)
    setCodePin('')
    setMessage('Code de secours enregistré.')
  }

  const onDelai = (e) => {
    const value = Number(e.target.value)
    setDelai(value)
    setLockDelayMinutes(value)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <label htmlFor="pref-app-lock" className="text-sm font-semibold text-foreground">
            Verrouiller avec Face ID / empreinte
          </label>
          <p className="text-xs text-muted-foreground">
            Masque l'écran quand l'app revient au premier plan après une mise en
            veille prolongée. C'est un verrou d'écran local : votre session
            reste ouverte, il ne remplace pas la connexion.
          </p>
        </div>
        <Switch
          id="pref-app-lock"
          checked={actif}
          disabled={busy || !supporte}
          onCheckedChange={onToggle}
        />
      </div>
      {!supporte && (
        <p className="text-xs text-muted-foreground">
          Cet appareil ou ce navigateur ne propose pas de verrouillage
          biométrique.
        </p>
      )}
      {actif && (
        <>
          <label htmlFor="pref-app-lock-delai" className="text-xs text-muted-foreground">
            Verrouiller après
          </label>
          <select
            id="pref-app-lock-delai"
            value={delai}
            onChange={onDelai}
            className="h-9 w-full rounded-md border border-border bg-card px-2.5 text-sm text-foreground"
          >
            {DELAIS.map((m) => (
              <option key={m} value={m}>{m} minute{m > 1 ? 's' : ''} en veille</option>
            ))}
          </select>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor="pref-app-lock-pin" className="text-xs text-muted-foreground">
                Code de secours {hasPin() ? '(défini)' : '(optionnel)'}
              </label>
              <input
                id="pref-app-lock-pin"
                type="password"
                inputMode="numeric"
                autoComplete="off"
                value={codePin}
                onChange={(e) => setCodePin(e.target.value)}
                className="h-9 w-full rounded-md border border-border bg-card px-2.5 text-sm text-foreground"
              />
            </div>
            <button
              type="button"
              onClick={enregistrerPin}
              className="h-9 rounded-md border border-border px-3 text-sm"
            >
              Enregistrer
            </button>
          </div>
        </>
      )}
      {message && <p className="text-xs text-muted-foreground">{message}</p>}
    </div>
  )
}

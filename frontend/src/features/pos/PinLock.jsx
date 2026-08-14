import { useState } from 'react'
import { Lock } from 'lucide-react'
import api from '../../api/axios'
import { Button, Input, Label, toast } from '../../ui'
import { errorMessageFrom } from '../../lib/toast'

// NTRET3 — Multi-caissiers avec PIN de session (verrouillage rapide).
//
// Un poste caisse reste connecté (JWT valide) toute la journée ; plusieurs
// caissiers s'y relaient. `PinLock` verrouille l'écran caisse entre deux
// ventes sans perdre le panier en cours (le parent garde son état — ce
// composant ne fait QUE bloquer visuellement l'écran tant que le PIN n'est
// pas vérifié) et sans re-login JWT complet (le cookie de session reste
// valide, seul l'accès à L'ÉCRAN est reverrouillé).

const CAISSIER_ACTIF_KEY = 'pos:caissier-actif'

// Le « caissier précédent » (pour la journalisation du changement côté
// serveur, apps.pos.services.verifier_pin) survit au verrouillage — stocké
// en localStorage, PAS en state React (le composant peut être démonté/
// remonté entre deux verrouillages).
export function lireCaissierActif(storage = safeStorage()) {
  try {
    const raw = storage?.getItem(CAISSIER_ACTIF_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function memoriserCaissierActif(user, storage = safeStorage()) {
  try {
    if (user?.id) storage?.setItem(CAISSIER_ACTIF_KEY, JSON.stringify(user))
    else storage?.removeItem(CAISSIER_ACTIF_KEY)
  } catch { /* quota/privé */ }
}

function safeStorage() {
  return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
}

/**
 * Vérifie un PIN contre le backend (POST /pos/verifier-pin/). Transmet le
 * caissier précédemment actif (localStorage) pour que le serveur journalise
 * un changement de caissier — jamais posé côté client (audit server-side
 * only, cf. CLAUDE.md).
 */
export async function verifierPin({ userId, pin }) {
  const precedent = lireCaissierActif()
  const res = await api.post('/pos/verifier-pin/', {
    user_id: userId,
    pin,
    caissier_precedent: precedent?.id || null,
  })
  memoriserCaissierActif(res.data)
  return res.data
}

export async function definirPin(pin) {
  return api.post('/pos/definir-pin/', { pin })
}

/**
 * Écran de verrouillage rapide. `userId` = utilisateur attendu au
 * déverrouillage (le compte JWT courant du poste) ; `onUnlock(user)` est
 * appelé une fois le PIN validé. Le parent (CaisseScreen) affiche ce
 * composant EN OVERLAY par-dessus l'écran caisse existant — le panier reste
 * intact dans l'état du parent pendant tout le verrouillage.
 */
export default function PinLock({ userId, onUnlock, verrouille = true }) {
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)

  if (!verrouille) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!pin) return
    setBusy(true)
    try {
      const user = await verifierPin({ userId, pin })
      setPin('')
      onUnlock?.(user)
    } catch (err) {
      toast.error(errorMessageFrom(err, 'PIN incorrect.'))
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm"
      data-testid="pin-lock-overlay"
    >
      <form
        noValidate
        onSubmit={handleSubmit}
        className="flex w-full max-w-xs flex-col items-center gap-4 rounded-lg border border-border bg-card p-6 text-center shadow-lg"
      >
        <Lock className="size-8 text-muted-foreground" />
        <div>
          <h2 className="font-display text-lg font-semibold">Écran verrouillé</h2>
          <p className="text-sm text-muted-foreground">
            Saisissez votre PIN pour reprendre la caisse.
          </p>
        </div>
        <div className="grid w-full gap-1.5">
          <Label htmlFor="pin-lock-input" required>PIN</Label>
          <Input
            id="pin-lock-input"
            type="password"
            inputMode="numeric"
            autoFocus
            maxLength={6}
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
            placeholder="••••"
          />
        </div>
        <Button type="submit" className="w-full" loading={busy} disabled={!pin}>
          Déverrouiller
        </Button>
      </form>
    </div>
  )
}

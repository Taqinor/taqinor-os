// L57 — Gestion du dépassement de session : ré-authentification gracieuse qui
// PRÉSERVE le formulaire en cours. Quand l'intercepteur axios détecte une
// session expirée (401 non rejouable), il émet `taqinor:session-expired` ; ce
// provider affiche un modal de reconnexion. À la reconnexion réussie, on
// rafraîchit l'utilisateur Redux et on ferme le modal — SANS rechargement de la
// page, donc l'état des composants (formulaire à moitié rempli) est intact.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useDispatch } from 'react-redux'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { Label } from '../ui/Label'
import api from '../api/axios'
import { setCredentials, logout } from '../features/auth/store/authSlice'
import { SESSION_EXPIRED_EVENT, subscribeToSessionLogout } from './session-bridge'
import { isAnyFormDirty, confirmLeaveIfDirty } from '../ui/useDirtyGuard'

export function SessionProvider({ children }) {
  const [open, setOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const dispatch = useDispatch()
  // Évite d'empiler plusieurs modals si plusieurs requêtes échouent en même temps.
  const openRef = useRef(false)

  useEffect(() => {
    const onExpired = () => {
      if (openRef.current) return
      openRef.current = true
      setError(null)
      setPassword('')
      setOpen(true)
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [])

  // VX162 — logout déclenché dans UN AUTRE onglet (poste partagé) : on se
  // déconnecte LOCALEMENT (reducer synchrone, aucun appel réseau) puis on
  // redirige vers /login — sans attendre le premier 401 de cet onglet.
  useEffect(() => subscribeToSessionLogout(() => {
    dispatch(logout())
    if (window.location?.pathname !== '/login') {
      window.location.href = '/login'
    }
  }), [dispatch])

  const dismiss = useCallback(() => {
    openRef.current = false
    setOpen(false)
    setPassword('')
    setError(null)
  }, [])

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      // Réinstalle les cookies httpOnly — aucun token visible côté front. On NE
      // recharge PAS la page : l'état des écrans ouverts est conservé.
      const res = await api.post('/token/', { username, password })
      dispatch(setCredentials({
        user: { username },
        role: res.data?.role || 'normal',
        role_nom: res.data?.role_nom || null,
        permissions: res.data?.permissions || [],
      }))
      dismiss()
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (detail) setError(detail)
      else if (err?.message === 'Network Error') {
        setError('Impossible de contacter le serveur. Vérifiez votre connexion.')
      } else {
        setError('Identifiants incorrects. Réessayez.')
      }
    } finally {
      setBusy(false)
    }
  }, [username, password, dispatch, dismiss])

  // Fermeture forcée vers le login si l'utilisateur abandonne la reconnexion.
  // VX62 — un rechargement dur (`window.location.href`) détruit tout formulaire
  // en cours : si un formulaire modifié est monté, on confirme d'abord.
  const goToLogin = useCallback(() => {
    if (isAnyFormDirty() && !confirmLeaveIfDirty(true)) return
    dismiss()
    window.location.href = '/login'
  }, [dismiss])

  return (
    <>
      {children}
      <Dialog
        open={open}
        onOpenChange={(v) => { if (!v) dismiss() }}
      >
        <DialogContent showClose={false} aria-label="Reconnexion">
          <DialogHeader>
            <DialogTitle>Session expirée</DialogTitle>
            <DialogDescription>
              Votre session a expiré. Reconnectez-vous pour continuer — votre travail en cours est conservé.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="reauth-username">Nom d’utilisateur</Label>
              <Input
                id="reauth-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="reauth-password">Mot de passe</Label>
              <Input
                id="reauth-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                autoFocus
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" role="alert">{error}</p>
            )}
            <div className="mt-1 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="ghost" onClick={goToLogin} disabled={busy}>
                Aller à la page de connexion
              </Button>
              <Button type="submit" disabled={busy}>
                {busy ? 'Connexion…' : 'Se reconnecter'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default SessionProvider

import { useCallback, useEffect, useRef, useState } from 'react'
import { Delete, Fingerprint } from 'lucide-react'
import { Button, Input, Label } from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   XRH10 — Guichet kiosque de pointage (plein écran, SANS session).
   ----------------------------------------------------------------------------
   Page autonome montée hors du layout ERP et hors authLoader : le kiosque
   s'authentifie par un jeton de DEVICE (en-tête X-Kiosque-Token), pas par une
   session utilisateur. Le jeton est saisi une fois puis mémorisé localement sur
   la tablette ; l'employé saisit ensuite son PIN pour pointer (arrivée/départ
   décidés côté serveur). Un PIN inconnu renvoie un message neutre.
   ========================================================================== */

const TOKEN_KEY = 'rh_kiosque_token'
// VX201 — le jeton de device restait en localStorage CLAIR et PERMANENT sur
// une tablette en libre-service (surface d'attaque physique). Timeout
// d'inactivité : au-delà de 5 min sans interaction sur le pavé PIN, le jeton
// est oublié (oublierToken()) et l'écran de configuration réapparaît — un
// device volé/laissé sans surveillance ne reste pas indéfiniment authentifié.
// Le try/catch localStorage existant DEJA sur ce fichier joue le rôle du
// helper défensif partagé `safeStorage` (VX170, pas encore construit) ; à
// remplacer par cet import unique quand VX170 atterrit.
const IDLE_TIMEOUT_MS = 5 * 60 * 1000

export default function Kiosque() {
  const [token, setToken] = useState('')
  const [tokenSaisi, setTokenSaisi] = useState('')
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)

  useEffect(() => {
    try {
      const t = window.localStorage.getItem(TOKEN_KEY)
      // eslint-disable-next-line react-hooks/set-state-in-effect -- lecture unique du jeton mémorisé au montage
      if (t) setToken(t)
    } catch { /* localStorage indisponible */ }
  }, [])

  const enregistrerToken = (e) => {
    e.preventDefault()
    const t = tokenSaisi.trim()
    if (!t) return
    try { window.localStorage.setItem(TOKEN_KEY, t) } catch { /* ignore */ }
    setToken(t)
    setTokenSaisi('')
  }

  const oublierToken = useCallback(() => {
    try { window.localStorage.removeItem(TOKEN_KEY) } catch { /* ignore */ }
    setToken('')
    setPin('')
    setFeedback(null)
  }, [])

  // VX201 — timeout d'inactivité : reset au dernier moment d'interaction avec
  // le pavé PIN (ajouter/effacer/pointer) tant qu'un jeton est configuré.
  const lastActivityRef = useRef(0)
  const marquerActivite = useCallback(() => { lastActivityRef.current = Date.now() }, [])
  useEffect(() => { lastActivityRef.current = Date.now() }, [])

  useEffect(() => {
    if (!token) return undefined
    marquerActivite()
    const id = setInterval(() => {
      if (Date.now() - lastActivityRef.current >= IDLE_TIMEOUT_MS) oublierToken()
    }, 5000)
    return () => clearInterval(id)
  }, [token, oublierToken, marquerActivite])

  const ajouter = (chiffre) => {
    marquerActivite()
    setFeedback(null)
    setPin((p) => (p.length >= 12 ? p : p + chiffre))
  }
  const effacer = () => { marquerActivite(); setPin((p) => p.slice(0, -1)) }

  const pointer = async () => {
    if (!pin || busy) return
    marquerActivite()
    setBusy(true)
    setFeedback(null)
    try {
      const res = await rhApi.kiosquePointer(pin, token)
      const d = res.data || {}
      setFeedback({
        ok: true,
        nom: d.nom || '',
        sens: d.sens === 'depart' ? 'Départ' : 'Arrivée',
      })
      setPin('')
    } catch (err) {
      if (err?.response?.status === 401) {
        setFeedback({ ok: false, message: 'Device non autorisé — reconfigurez le jeton.' })
      } else {
        // 404 neutre : PIN inconnu.
        setFeedback({ ok: false, message: 'PIN inconnu. Réessayez.' })
      }
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  // Écran de configuration initiale du device (jeton).
  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <form onSubmit={enregistrerToken} className="flex w-full max-w-md flex-col gap-4 rounded-2xl border border-border bg-card p-8 shadow-lg">
          <div className="flex flex-col items-center gap-2 text-center">
            <Fingerprint size={40} strokeWidth={1.5} aria-hidden="true" className="text-primary" />
            <h1 className="text-xl font-semibold">Configurer le kiosque</h1>
            <p className="text-sm text-muted-foreground">
              Collez le jeton de device fourni par l’administrateur RH.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ki-token">Jeton du device</Label>
            <Input id="ki-token" value={tokenSaisi} onChange={(e) => setTokenSaisi(e.target.value)} autoComplete="off" />
          </div>
          <Button type="submit" disabled={!tokenSaisi.trim()}>Activer ce kiosque</Button>
        </form>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background p-6">
      <div className="flex w-full max-w-sm flex-col gap-6 rounded-2xl border border-border bg-card p-8 shadow-lg">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Pointage</h1>
          <p className="text-sm text-muted-foreground">Saisissez votre code PIN</p>
        </div>

        <div className="flex h-12 items-center justify-center rounded-lg border border-border bg-muted text-2xl tracking-[0.4em]">
          {pin ? '•'.repeat(pin.length) : <span className="text-base tracking-normal text-muted-foreground">— — — —</span>}
        </div>

        <div className="grid grid-cols-3 gap-3">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((n) => (
            <Button key={n} variant="outline" className="h-14 text-xl" onClick={() => ajouter(n)}>{n}</Button>
          ))}
          <Button variant="outline" className="h-14 text-xl" onClick={effacer} aria-label="Effacer">
            <Delete size={22} strokeWidth={1.75} aria-hidden="true" />
          </Button>
          <Button variant="outline" className="h-14 text-xl" onClick={() => ajouter('0')}>0</Button>
          <Button className="h-14 text-lg" disabled={!pin || busy} onClick={pointer}>
            {busy ? '…' : 'OK'}
          </Button>
        </div>

        {feedback && (
          feedback.ok ? (
            <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-center text-sm text-success">
              <p className="font-medium">{feedback.sens} enregistré{feedback.sens === 'Arrivée' ? 'e' : ''}</p>
              {feedback.nom && <p>Bonjour {feedback.nom} 👋</p>}
            </div>
          ) : (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-center text-sm text-destructive">
              {feedback.message}
            </div>
          )
        )}
      </div>

      <button type="button" onClick={oublierToken} className="text-xs text-muted-foreground underline">
        Reconfigurer ce kiosque
      </button>
    </div>
  )
}

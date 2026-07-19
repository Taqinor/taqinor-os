/* WIR72 — Bouton « Suivre / Ne plus suivre » générique.
   Réutilise `records.Follower` (FollowerViewSet monté sur `records/followers/`,
   mêmes ALLOWED_TARGETS que les activités/pièces jointes). Passe model
   ('crm.lead', 'sav.ticket'…) + id — s'abonne/désabonne l'utilisateur courant
   (résolu SERVEUR via `?mine=1`, jamais un id client). Une cible non compatible
   (400) désactive simplement le bouton, sans casser l'écran hôte. */
import { useCallback, useEffect, useState } from 'react'
import { Bell, BellOff } from 'lucide-react'
import recordsApi from '../api/recordsApi'

export default function FollowToggle({ model, id }) {
  const [follower, setFollower] = useState(null) // ligne Follower de l'user, ou null
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [disabled, setDisabled] = useState(false)

  const load = useCallback(async () => {
    if (!model || !id) return
    try {
      const res = await recordsApi.getMyFollow(model, id)
      const rows = res.data?.results ?? res.data ?? []
      setFollower(rows[0] ?? null)
      setDisabled(false)
    } catch {
      // Cible non abonnable / erreur : bouton inerte plutôt qu'un crash.
      setDisabled(true)
    } finally {
      setLoaded(true)
    }
  }, [model, id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount: setState happens after the awaited request resolves, not synchronously
  useEffect(() => { load() }, [load])

  const toggle = async () => {
    if (busy || disabled) return
    setBusy(true)
    try {
      if (follower) {
        await recordsApi.unfollow(follower.id)
        setFollower(null)
      } else {
        const res = await recordsApi.follow(model, id)
        setFollower(res.data)
      }
    } catch {
      setDisabled(true)
    } finally {
      setBusy(false)
    }
  }

  if (!loaded) return null

  const following = Boolean(follower)
  const Icon = following ? BellOff : Bell
  return (
    <button
      type="button"
      className="btn btn-sm"
      aria-pressed={following}
      disabled={busy || disabled}
      onClick={toggle}
      title={following ? 'Ne plus suivre cet enregistrement' : 'Suivre cet enregistrement'}
    >
      <Icon size={14} strokeWidth={1.75} aria-hidden="true" />{' '}
      {following ? 'Ne plus suivre' : 'Suivre'}
    </button>
  )
}

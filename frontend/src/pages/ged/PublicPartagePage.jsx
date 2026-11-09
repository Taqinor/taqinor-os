/**
 * ASEC77 — Page PUBLIQUE d'ouverture d'un partage GED (sans login).
 *
 * Route /ged/partage/:token (hors coquille authentifiée) : la destination du
 * `public_url` d'un partage (ASEC78). Sans mot de passe, le document s'ouvre
 * directement (GET) ; protégé, le destinataire saisit le mot de passe, envoyé
 * dans le corps d'un POST (jamais dans l'adresse — ASEC39). Le gel après trop
 * d'essais est tenu par le SERVEUR : la page affiche son message tel quel.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import gedApi from '../../api/gedApi'
import { Button } from '../../ui'
import { errMessage } from '../../features/ged/advanced/shared.js'
import NoIndex from '../../components/NoIndex'

// Même throttle CLIENT que PublicDepotPage (VX202) : pas de ré-essai en rafale.
const THROTTLE_MS = 4000

export default function PublicPartagePage() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading') // loading | password | ok | invalid
  const [error, setError] = useState(null)
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [throttled, setThrottled] = useState(false)
  const [lien, setLien] = useState(null)
  const lienRef = useRef(null)

  const ouvrir = (res) => {
    const blob = res?.data
    const url = blob && typeof URL.createObjectURL === 'function'
      ? URL.createObjectURL(blob) : null
    lienRef.current = url
    setLien(url)
    setStatus('ok')
    if (url) window.location.assign(url)
  }

  const echec = (err, fallback) => {
    const code = err?.response?.status
    if (code === 404 || code === 410) {
      setError(errMessage(err, "Ce lien de partage est introuvable ou n'est plus disponible."))
      setStatus('invalid')
      return
    }
    setError(errMessage(err, fallback))
  }

  useEffect(() => {
    let alive = true
    gedApi.ouvrirPartagePublic(token)
      .then((res) => { if (alive) ouvrir(res) })
      .catch((err) => {
        if (!alive) return
        if (err?.response?.status === 403) { setStatus('password'); return }
        echec(err, "Ce lien de partage est introuvable ou n'est plus disponible.")
        setStatus('invalid')
      })
    return () => {
      alive = false
      if (lienRef.current && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(lienRef.current)
      }
    }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (throttled) return
    if (!password) { setError('Saisissez le mot de passe reçu.'); return }
    setError(null)
    setSubmitting(true)
    setThrottled(true)
    setTimeout(() => setThrottled(false), THROTTLE_MS)
    try {
      ouvrir(await gedApi.ouvrirPartagePublic(token, password))
    } catch (err) {
      echec(err, 'Mot de passe requis ou incorrect pour ce document.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 520, margin: '40px auto', padding: '0 16px' }}>
      <NoIndex />
      <h2>Document partagé</h2>

      {status === 'loading' && <p role="status">Chargement…</p>}
      {status === 'invalid' && <p role="alert" className="page-error">{error}</p>}
      {status === 'ok' && (
        <p role="status">
          Le document s'ouvre.{' '}
          {lien && <a href={lien}>Ouvrir le document</a>}
        </p>
      )}

      {status === 'password' && (
        <form onSubmit={handleSubmit} noValidate style={{ marginTop: 16 }}>
          <p>Ce document est protégé par un mot de passe.</p>
          <div style={{ marginBottom: 12 }}>
            <label className="form-label" htmlFor="ged-partage-mdp">Mot de passe</label>
            <input
              id="ged-partage-mdp"
              type="password"
              className="form-control"
              autoComplete="off"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p role="alert" className="page-error">{error}</p>}
          <Button type="submit" disabled={submitting || !password || throttled}>
            {submitting ? 'Ouverture…' : 'Ouvrir le document'}
          </Button>
          {throttled && !submitting && (
            <p className="text-sm text-muted-foreground">Veuillez patienter avant de réessayer.</p>
          )}
        </form>
      )}
    </div>
  )
}

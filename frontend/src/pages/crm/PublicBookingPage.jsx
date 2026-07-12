/**
 * XSAL17 — Page PUBLIQUE de réservation de visite (aucun login).
 *
 * Route /rdv/:token, autonome (pas de layout ERP) — c'est la destination du
 * placeholder {lien_rdv} dans les templates de messages/emails. Le token
 * identifie un crm.BookingLink (imprévisible, expirant), jamais un lead
 * directement. Sans jeton valide : message honnête (jamais un faux succès).
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import api from '../../api/axios'
import { Button } from '../../ui'
import NoIndex from '../../components/NoIndex'

export default function PublicBookingPage() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading') // loading | valid | invalid | booked
  const [prenom, setPrenom] = useState('')
  const [error, setError] = useState(null)
  const [scheduledAt, setScheduledAt] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let alive = true
    api.get(`/crm/public/booking/${token}/`)
      .then((res) => {
        if (!alive) return
        setPrenom(res.data?.prenom || '')
        setStatus('valid')
      })
      .catch((err) => {
        if (!alive) return
        setError(
          err?.response?.data?.detail
          || 'Ce lien de réservation est introuvable ou a expiré.')
        setStatus('invalid')
      })
    return () => { alive = false }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!scheduledAt) return
    setSubmitting(true)
    setError(null)
    try {
      await api.post(`/crm/public/booking/${token}/reserve/`, {
        scheduled_at: new Date(scheduledAt).toISOString(),
        notes,
      })
      setStatus('booked')
    } catch (err) {
      setError(
        err?.response?.data?.detail
        || 'Impossible de réserver ce créneau — réessayez ou contactez-nous.')
      if (err?.response?.status === 410 || err?.response?.status === 404) {
        setStatus('invalid')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <NoIndex />
      <h2>Réserver une visite</h2>
      {status === 'loading' && <p>Chargement…</p>}
      {status === 'invalid' && (
        <p role="alert" className="page-error">{error}</p>
      )}
      {status === 'booked' && (
        <p role="status">
          Merci{prenom ? ` ${prenom}` : ''} ! Votre visite est réservée —
          nous vous contacterons pour la confirmer.
        </p>
      )}
      {status === 'valid' && (
        <form onSubmit={handleSubmit} noValidate>
          {prenom && <p>Bonjour {prenom},</p>}
          <label className="form-label" htmlFor="pb-date">
            Date et heure souhaitées
          </label>
          <input
            id="pb-date"
            type="datetime-local"
            className="form-control"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            required
          />
          <label className="form-label" htmlFor="pb-notes">Notes (optionnel)</label>
          <textarea
            id="pb-notes"
            className="form-control"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          {error && <p role="alert" className="page-error">{error}</p>}
          <Button type="submit" disabled={submitting || !scheduledAt}>
            {submitting ? 'Réservation…' : 'Réserver'}
          </Button>
        </form>
      )}
    </div>
  )
}

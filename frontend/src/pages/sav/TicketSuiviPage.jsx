/**
 * XSAV10/FG86 — Page PUBLIQUE de suivi client d'un ticket SAV (aucun login).
 * Route /suivi/:token — autonome (pas de layout ERP). Affiche uniquement le
 * statut public (référence, statut, date_modification) et, une fois le
 * ticket résolu/clôturé, propose l'enquête de satisfaction (CSAT, une seule
 * réponse par ticket). Jamais de prix, chatter ou information client —
 * garanti côté serveur (voir apps/sav/public_views.py).
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Star } from 'lucide-react'
import api from '../../api/axios'
import { Button, Textarea } from '../../ui'
import { formatDateTime } from '../../lib/format'
import NoIndex from '../../components/NoIndex'

const RESOLU_STATUTS = ['resolu', 'cloture']

export default function TicketSuiviPage() {
  const { token } = useParams()
  const [status, setStatus] = useState('loading') // loading | valid | invalid
  const [ticket, setTicket] = useState(null)
  const [error, setError] = useState(null)

  const [note, setNote] = useState(0)
  const [commentaire, setCommentaire] = useState('')
  const [csatState, setCsatState] = useState('idle') // idle | sending | sent | error
  const [csatError, setCsatError] = useState(null)

  useEffect(() => {
    let alive = true
    api.get(`/public/sav/ticket/${token}/`)
      .then((res) => {
        if (!alive) return
        setTicket(res.data)
        setStatus('valid')
      })
      .catch((err) => {
        if (!alive) return
        setError(
          err?.response?.data?.detail
          || 'Ce lien de suivi est invalide ou introuvable.')
        setStatus('invalid')
      })
    return () => { alive = false }
  }, [token])

  const submitCsat = async (e) => {
    e.preventDefault()
    if (!note) return
    setCsatState('sending')
    setCsatError(null)
    try {
      await api.post(`/public/sav/ticket/${token}/satisfaction/`, {
        note, commentaire: commentaire.trim() || undefined,
      })
      setCsatState('sent')
    } catch (err) {
      const detail = err?.response?.data?.detail
      setCsatError(detail || "Impossible d'enregistrer votre réponse.")
      // 409 = déjà répondu : on considère l'enquête close côté client aussi.
      setCsatState(err?.response?.status === 409 ? 'sent' : 'error')
    }
  }

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <NoIndex />
      <h2>Suivi de votre ticket</h2>

      {status === 'loading' && <p>Chargement…</p>}
      {status === 'invalid' && (
        <p role="alert" className="page-error">{error}</p>
      )}

      {status === 'valid' && ticket && (
        <div className="flex flex-col gap-3">
          <p><strong>Référence :</strong> {ticket.reference}</p>
          <p><strong>Statut :</strong> {ticket.statut_display || ticket.statut}</p>
          {ticket.date_modification && (
            <p className="text-sm text-muted-foreground">
              Dernière mise à jour :{' '}
              {formatDateTime(ticket.date_modification)}
            </p>
          )}

          {RESOLU_STATUTS.includes(ticket.statut) && csatState !== 'sent' && (
            <form onSubmit={submitCsat} className="flex flex-col gap-2" noValidate>
              <p className="font-medium">Votre ticket est résolu — êtes-vous satisfait(e) ?</p>
              <div className="flex gap-1" role="radiogroup" aria-label="Note de satisfaction">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    aria-label={`${n} étoile${n > 1 ? 's' : ''}`}
                    aria-pressed={note === n}
                    onClick={() => setNote(n)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}
                  >
                    <Star
                      className="size-6"
                      fill={n <= note ? 'currentColor' : 'none'}
                      style={{ color: n <= note ? '#f5a623' : '#ccc' }}
                    />
                  </button>
                ))}
              </div>
              <Textarea
                placeholder="Commentaire (optionnel)"
                value={commentaire}
                onChange={(e) => setCommentaire(e.target.value)}
                rows={3}
              />
              {csatError && <p role="alert" className="page-error">{csatError}</p>}
              <Button type="submit" disabled={!note || csatState === 'sending'}>
                {csatState === 'sending' ? 'Envoi…' : 'Envoyer ma réponse'}
              </Button>
            </form>
          )}

          {csatState === 'sent' && (
            <p role="status">Merci pour votre retour !</p>
          )}
        </div>
      )}
    </div>
  )
}

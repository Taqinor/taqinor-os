import { Fragment, useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   PACT106 — Avis clients + routage Google Reviews (FG239).
   ----------------------------------------------------------------------------
   `AvisClientViewSet` (route `/marketing/avis-clients/`) capture une note
   (1-5) + un témoignage (action `recevoir`) puis route le client satisfait
   vers Google Reviews via `google_review_url_configuree()` (paramètre
   Django `GOOGLE_REVIEW_URL`, jamais une API payante — action
   `pousser_google`). Aucun écran ne l'appelait.

   Doctrine NO-OP : sans `GOOGLE_REVIEW_URL` configuré, `pousser_google`
   renvoie l'avis INCHANGÉ (statut/lien restent tels quels), jamais une
   erreur — le bouton reste donc TOUJOURS actionnable et neutre, exactement
   comme le serveur le traite (jamais un bouton mort ni une erreur brute).
   ========================================================================== */

const STATUT_LABEL = {
  sollicite: 'Sollicité',
  recu: 'Reçu',
  publie_google: 'Routé vers Google',
}
const STATUT_TONE = {
  sollicite: { background: '#f1f5f9', color: '#64748b' },
  recu: { background: '#fef9c3', color: '#854d0e' },
  publie_google: { background: '#dcfce7', color: '#166534' },
}

export default function AvisClients() {
  const [avis, setAvis] = useState([])
  const [loading, setLoading] = useState(true)
  const [clientId, setClientId] = useState('')
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')

  // Panneau « Enregistrer l'avis reçu » ouvert pour UN avis à la fois.
  const [ouvertId, setOuvertId] = useState(null)
  const [note, setNote] = useState('5')
  const [temoignage, setTemoignage] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.avisClients.list()
      .then(r => setAvis(marketingApi.unwrapList(r)))
      .catch(() => setAvis([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const solliciter = async (e) => {
    e.preventDefault()
    if (!clientId) return
    setCreating(true); setErr('')
    try {
      await marketingApi.avisClients.create({ client_id: Number(clientId) })
      setClientId('')
      load()
    } catch {
      setErr('Sollicitation impossible.')
    } finally {
      setCreating(false)
    }
  }

  const ouvrirRecevoir = (a) => {
    setOuvertId(ouvertId === a.id ? null : a.id)
    setNote('5'); setTemoignage('')
  }

  const enregistrerAvis = async (id) => {
    setBusyId(id); setErr('')
    try {
      const r = await marketingApi.avisClients.recevoir(id, { note: Number(note), temoignage })
      setAvis(list => list.map(a => a.id === id ? r.data : a))
      setOuvertId(null)
    } catch {
      setErr("Enregistrement de l'avis impossible.")
    } finally {
      setBusyId(null)
    }
  }

  // Doctrine NO-OP : la réponse serveur (avis inchangé ou routé) est
  // affichée TELLE QUELLE — aucune branche « succès »/« échec » fabriquée
  // côté client au-delà d'une vraie erreur réseau.
  const pousserGoogle = async (id) => {
    setBusyId(id); setErr('')
    try {
      const r = await marketingApi.avisClients.pousserGoogle(id)
      setAvis(list => list.map(a => a.id === id ? r.data : a))
    } catch {
      setErr('Routage vers Google impossible (erreur réseau).')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Avis clients</h2></div>

      <form onSubmit={solliciter} className="card" data-testid="avis-solliciter-form"
        style={{ marginBottom: '1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-end',
          maxWidth: 480 }} noValidate>
        <label style={{ flex: 1 }}>
          Client (id)
          <input className="form-control" type="number" data-testid="avis-client-id"
            value={clientId} onChange={e => setClientId(e.target.value)}
            placeholder="id du client" aria-label="Client (id)" />
        </label>
        <button className="btn btn-primary" type="submit" disabled={creating || !clientId}>
          Solliciter un avis
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }} role="alert" data-testid="avis-err">{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="avis-table">
            <thead>
              <tr>
                <th>Client</th><th>Note</th><th>Témoignage</th><th>Statut</th>
                <th>Lien Google</th><th>Créé le</th><th />
              </tr>
            </thead>
            <tbody>
              {avis.map(a => {
                const tone = STATUT_TONE[a.statut] || STATUT_TONE.sollicite
                const peutRecevoir = a.statut === 'sollicite'
                return (
                  <Fragment key={a.id}>
                    <tr data-testid="avis-row">
                      <td>Client #{a.client_id}</td>
                      <td>{a.note != null ? `${a.note}/5` : '—'}</td>
                      <td>{a.temoignage || '—'}</td>
                      <td>
                        <span className="badge" style={tone}>
                          {STATUT_LABEL[a.statut] || a.statut}
                        </span>
                      </td>
                      <td>
                        {a.google_review_url
                          ? <a href={a.google_review_url} target="_blank" rel="noopener noreferrer">
                              Voir le lien</a>
                          : '—'}
                      </td>
                      <td>{a.date_creation ? formatDateTime(a.date_creation) : '—'}</td>
                      <td style={{ display: 'flex', gap: '0.4rem', whiteSpace: 'nowrap' }}>
                        {peutRecevoir && (
                          <button type="button" className="btn btn-light" data-testid={`avis-recevoir-${a.id}`}
                            onClick={() => ouvrirRecevoir(a)}>
                            Avis reçu
                          </button>
                        )}
                        <button type="button" className="btn btn-light" data-testid={`avis-pousser-google-${a.id}`}
                          disabled={busyId === a.id} onClick={() => pousserGoogle(a.id)}>
                          Pousser vers Google
                        </button>
                      </td>
                    </tr>
                    {ouvertId === a.id && (
                      <tr>
                        <td colSpan={7}>
                          <div data-testid={`avis-recevoir-form-${a.id}`}
                            style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', padding: '0.5rem 0' }}>
                            <label>
                              Note (1-5)
                              <select className="form-control" data-testid={`avis-note-${a.id}`}
                                value={note} onChange={e => setNote(e.target.value)} aria-label="Note (1-5)">
                                {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
                              </select>
                            </label>
                            <label style={{ flex: 1 }}>
                              Témoignage
                              <input className="form-control" data-testid={`avis-temoignage-${a.id}`}
                                value={temoignage} onChange={e => setTemoignage(e.target.value)}
                                aria-label="Témoignage" />
                            </label>
                            <button type="button" className="btn btn-primary" data-testid={`avis-recevoir-confirm-${a.id}`}
                              disabled={busyId === a.id} onClick={() => enregistrerAvis(a.id)}>
                              Enregistrer
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
              {avis.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun avis client
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}

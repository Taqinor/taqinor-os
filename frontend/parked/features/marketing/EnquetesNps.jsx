import { Fragment, useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   PACT107 — Enquêtes NPS post-installation (FG238).
   ----------------------------------------------------------------------------
   `EnqueteNPSViewSet` (route `/marketing/enquetes-nps/`) est une enquête de
   satisfaction CLIENT post-chantier (score 0-10 → promoteur/passif/
   détracteur), DISTINCTE du Pulse eNPS interne aux employés (déjà câblé
   ailleurs) et du générique `Enquete` (où NPS n'est qu'un type de question
   parmi d'autres). Aucun écran n'appelait ce modèle.

   Le score consolidé (`%promoteurs - %détracteurs`) vient de l'action
   serveur `score` — jamais recalculé côté client à partir des réponses brutes.
   ========================================================================== */

const CATEGORIE_LABEL = { promoteur: 'Promoteur', passif: 'Passif', detracteur: 'Détracteur' }
const CATEGORIE_TONE = {
  promoteur: { background: '#dcfce7', color: '#166534' },
  passif: { background: '#fef9c3', color: '#854d0e' },
  detracteur: { background: '#fee2e2', color: '#991b1b' },
}
const STATUT_LABEL = { envoyee: 'Envoyée', repondue: 'Répondue' }

export default function EnquetesNps() {
  const [enquetes, setEnquetes] = useState([])
  const [loading, setLoading] = useState(true)
  const [score, setScore] = useState(null)

  const [clientId, setClientId] = useState('')
  const [chantierId, setChantierId] = useState('')
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')

  // Panneau « Enregistrer une réponse » ouvert pour UNE enquête à la fois.
  const [ouvertId, setOuvertId] = useState(null)
  const [reponseScore, setReponseScore] = useState('9')
  const [commentaire, setCommentaire] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.enquetesNps.list()
      .then(r => setEnquetes(marketingApi.unwrapList(r)))
      .catch(() => setEnquetes([]))
      .finally(() => setLoading(false))
    marketingApi.enquetesNps.score()
      .then(r => setScore(r.data))
      .catch(() => setScore(null))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const envoyer = async (e) => {
    e.preventDefault()
    if (!clientId) return
    setCreating(true); setErr('')
    const payload = { client_id: Number(clientId) }
    if (chantierId) payload.chantier_id = Number(chantierId)
    try {
      await marketingApi.enquetesNps.create(payload)
      setClientId(''); setChantierId('')
      load()
    } catch {
      setErr('Envoi impossible.')
    } finally {
      setCreating(false)
    }
  }

  const ouvrirRepondre = (n) => {
    setOuvertId(ouvertId === n.id ? null : n.id)
    setReponseScore('9'); setCommentaire('')
  }

  const enregistrerReponse = async (id) => {
    setBusyId(id); setErr('')
    try {
      const r = await marketingApi.enquetesNps.repondre(id,
        { score: Number(reponseScore), commentaire })
      setEnquetes(list => list.map(n => n.id === id ? r.data : n))
      setOuvertId(null)
      marketingApi.enquetesNps.score().then(res => setScore(res.data)).catch(() => {})
    } catch {
      setErr("Enregistrement de la réponse impossible.")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Enquêtes NPS</h2></div>

      {/* Score NPS consolidé — vient TEL QUEL de l'action serveur `score`. */}
      <section className="card" data-testid="nps-score" style={{ padding: '1rem', marginBottom: '1.25rem', maxWidth: 480 }}>
        {score == null
          ? <p style={{ color: '#64748b', margin: 0 }}>Score indisponible.</p>
          : score.nps == null
            ? <p style={{ color: '#64748b', margin: 0 }} data-testid="nps-score-vide">
                Aucune réponse pour le moment.</p>
            : (
              <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
                <strong data-testid="nps-score-valeur" style={{ fontSize: '1.6rem' }}>{score.nps}</strong>
                <span style={{ color: '#64748b' }}>
                  {score.total} réponse(s) — {score.promoteurs} promoteur(s),{' '}
                  {score.passifs} passif(s), {score.detracteurs} détracteur(s)
                </span>
              </div>
            )}
      </section>

      <form onSubmit={envoyer} className="card" data-testid="nps-envoyer-form"
        style={{ marginBottom: '1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'flex-end',
          maxWidth: 560 }} noValidate>
        <label style={{ flex: 1 }}>
          Client (id)
          <input className="form-control" type="number" data-testid="nps-client-id"
            value={clientId} onChange={e => setClientId(e.target.value)}
            placeholder="id du client" aria-label="Client (id)" />
        </label>
        <label style={{ flex: 1 }}>
          Chantier (id, optionnel)
          <input className="form-control" type="number" data-testid="nps-chantier-id"
            value={chantierId} onChange={e => setChantierId(e.target.value)}
            placeholder="id du chantier" aria-label="Chantier (id)" />
        </label>
        <button className="btn btn-primary" type="submit" disabled={creating || !clientId}>
          Envoyer l'enquête
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }} role="alert" data-testid="nps-err">{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="nps-table">
            <thead>
              <tr>
                <th>Client</th><th>Chantier</th><th>Note</th><th>Catégorie</th>
                <th>Commentaire</th><th>Statut</th><th>Envoyée le</th><th />
              </tr>
            </thead>
            <tbody>
              {enquetes.map(n => {
                const peutRepondre = n.statut === 'envoyee'
                const cTone = CATEGORIE_TONE[n.categorie]
                return (
                  <Fragment key={n.id}>
                    <tr data-testid="nps-row">
                      <td>Client #{n.client_id}</td>
                      <td>{n.chantier_id != null ? `#${n.chantier_id}` : '—'}</td>
                      <td>{n.score != null ? n.score : '—'}</td>
                      <td>
                        {n.categorie
                          ? <span className="badge" style={cTone}>
                              {CATEGORIE_LABEL[n.categorie] || n.categorie}</span>
                          : '—'}
                      </td>
                      <td>{n.commentaire || '—'}</td>
                      <td>{STATUT_LABEL[n.statut] || n.statut}</td>
                      <td>{n.envoyee_le ? formatDateTime(n.envoyee_le) : '—'}</td>
                      <td>
                        {peutRepondre && (
                          <button type="button" className="btn btn-light" data-testid={`nps-repondre-${n.id}`}
                            onClick={() => ouvrirRepondre(n)}>
                            Enregistrer une réponse
                          </button>
                        )}
                      </td>
                    </tr>
                    {ouvertId === n.id && (
                      <tr>
                        <td colSpan={8}>
                          <div data-testid={`nps-repondre-form-${n.id}`}
                            style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', padding: '0.5rem 0' }}>
                            <label>
                              Note (0-10)
                              <input className="form-control" type="number" min={0} max={10}
                                data-testid={`nps-repondre-score-${n.id}`}
                                value={reponseScore} onChange={e => setReponseScore(e.target.value)}
                                aria-label="Note (0-10)" style={{ width: 90 }} />
                            </label>
                            <label style={{ flex: 1 }}>
                              Commentaire
                              <input className="form-control" data-testid={`nps-repondre-commentaire-${n.id}`}
                                value={commentaire} onChange={e => setCommentaire(e.target.value)}
                                aria-label="Commentaire" />
                            </label>
                            <button type="button" className="btn btn-primary" data-testid={`nps-repondre-confirm-${n.id}`}
                              disabled={busyId === n.id} onClick={() => enregistrerReponse(n.id)}>
                              Enregistrer
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
              {enquetes.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune enquête NPS
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}

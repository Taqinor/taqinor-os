import { Fragment, useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT6 — Détail d'une séquence : étapes ordonnées + vue participant.
   ----------------------------------------------------------------------------
   `marketing/sequences-relance/<id>/` renvoie les `etapes` imbriquées (ordre,
   délai J+n, canal — condition XMKT18/action CRM XMKT19 pas encore exposées
   par le serializer backend). Onglet Participants :
   `marketing/inscriptions-sequence/?sequence=<id>` (statut actif/sorti/
   terminé), chaque ligne dépliable affiche sa trace `executions` (quel nœud,
   quand, quoi envoyé, erreur — XMKT1).
   ========================================================================== */

const STATUT_LABEL = { actif: 'Actif', sorti: 'Sorti', termine: 'Terminé' }

export default function SequenceDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [sequence, setSequence] = useState(null)
  const [onglet, setOnglet] = useState('etapes')
  const [participants, setParticipants] = useState([])
  const [ouvert, setOuvert] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.sequences.get(id)
      .then(r => setSequence(r.data))
      .catch(() => setErr('Séquence introuvable.'))
      .finally(() => setLoading(false))
  }, [id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (onglet !== 'participants') return
    marketingApi.inscriptionsSequence.list({ sequence: id })
      .then(r => setParticipants(marketingApi.unwrapList(r)))
      .catch(() => setParticipants([]))
  }, [onglet, id])

  if (loading) return <div className="page"><p className="page-loading">Chargement…</p></div>
  if (!sequence) return <div className="page"><p style={{ color: '#dc2626' }}>{err || 'Introuvable.'}</p></div>

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-light" onClick={() => navigate('/marketing/sequences')}>
          ← Séquences
        </button>
        <h2>{sequence.nom}</h2>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button className={`btn ${onglet === 'etapes' ? 'btn-primary' : 'btn-light'}`}
          data-testid="sequence-onglet-etapes" onClick={() => setOnglet('etapes')}>
          Étapes
        </button>
        <button className={`btn ${onglet === 'participants' ? 'btn-primary' : 'btn-light'}`}
          data-testid="sequence-onglet-participants" onClick={() => setOnglet('participants')}>
          Participants
        </button>
      </div>

      {onglet === 'etapes' && (
        <table className="data-table" data-testid="etapes-table">
          <thead><tr><th>Ordre</th><th>Délai</th><th>Canal</th><th>Message</th></tr></thead>
          <tbody>
            {(sequence.etapes || []).map(e => (
              <tr key={e.id} data-testid="etape-row">
                <td>{e.ordre}</td>
                <td>J+{e.delai_jours}</td>
                <td>{e.canal_display || e.canal}</td>
                <td>{(e.modele_message || '').slice(0, 80)}</td>
              </tr>
            ))}
            {(sequence.etapes || []).length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                Aucune étape
              </td></tr>
            )}
          </tbody>
        </table>
      )}

      {onglet === 'participants' && (
        <table className="data-table" data-testid="participants-table">
          <thead><tr><th>Lead</th><th>Statut</th><th /></tr></thead>
          <tbody>
            {participants.map(p => (
              <Fragment key={p.id}>
                <tr data-testid="participant-row" style={{ cursor: 'pointer' }}
                  onClick={() => setOuvert(o => (o === p.id ? null : p.id))}>
                  <td>{p.lead_reference || `Lead #${p.lead_id}`}</td>
                  <td>{STATUT_LABEL[p.statut] || p.statut}</td>
                  <td>{ouvert === p.id ? '▲' : '▼'}</td>
                </tr>
                {ouvert === p.id && (
                  <tr>
                    <td colSpan={3}>
                      <table className="data-table" data-testid="participant-executions">
                        <thead>
                          <tr><th>Étape</th><th>Exécutée le</th><th>Résultat</th><th>Erreur</th></tr>
                        </thead>
                        <tbody>
                          {(p.executions || []).map(x => (
                            <tr key={x.id}>
                              <td>{x.etape}</td>
                              <td>{x.execute_le ? new Date(x.execute_le).toLocaleString('fr-FR') : '—'}</td>
                              <td>{x.resultat}</td>
                              <td>{x.erreur || '—'}</td>
                            </tr>
                          ))}
                          {(p.executions || []).length === 0 && (
                            <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                              Aucune exécution
                            </td></tr>
                          )}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {participants.length === 0 && (
              <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>
                Aucun participant
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

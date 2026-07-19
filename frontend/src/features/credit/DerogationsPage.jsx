import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import creditApi from '../../api/creditApi'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   WIR55 / NTCRD9 — Écran « Dérogations crédit » : liste des demandes et
   traitement (approuver / rejeter) réservé Directeur/Administrateur. Le backend
   re-vérifie (`IsDirecteurOrAdmin`) ; l'UI dégrade proprement sur refus.
   ========================================================================== */

export default function DerogationsPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const charger = useCallback(() => {
    let alive = true
    setLoading(true)
    creditApi
      .getDerogations()
      .then((res) => {
        if (alive) {
          setRows(res.data?.results ?? res.data ?? [])
          setError(null)
        }
      })
      .catch(() => {
        if (alive) setError('Impossible de charger les dérogations.')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount: reuses the shared `charger` refresh helper
  useEffect(() => charger(), [charger])

  async function decider(id, action) {
    setBusyId(id)
    setError(null)
    try {
      if (action === 'approuver') await creditApi.approuverDerogation(id)
      else await creditApi.rejeterDerogation(id)
      charger()
    } catch {
      setError('Décision impossible (droits Directeur/Administrateur requis).')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <div className="credit-derogations">Chargement…</div>

  return (
    <div className="credit-derogations" data-testid="credit-derogations">
      {error && <p className="credit-derogations__error" role="alert">{error}</p>}
      {rows.length === 0 ? (
        <p>Aucune demande de dérogation.</p>
      ) : (
        <table className="credit-derogations__table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Montant</th>
              <th>Motif</th>
              <th>Statut</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td>
                  {d.client ? (
                    <Link to={`/credit/clients/${d.client}`}>#{d.client}</Link>
                  ) : '—'}
                </td>
                <td>{formatMAD(d.montant_demande)}</td>
                <td>{d.motif || '—'}</td>
                <td>{d.statut}{d.est_valide ? ' (valide)' : ''}</td>
                <td>
                  {d.statut === 'en_attente' ? (
                    <>
                      <button
                        type="button"
                        disabled={busyId === d.id}
                        onClick={() => decider(d.id, 'approuver')}
                      >
                        Approuver
                      </button>
                      <button
                        type="button"
                        disabled={busyId === d.id}
                        onClick={() => decider(d.id, 'rejeter')}
                      >
                        Rejeter
                      </button>
                    </>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

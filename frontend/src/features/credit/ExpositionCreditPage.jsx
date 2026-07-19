import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import creditApi from '../../api/creditApi'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   WIR55 / NTCRD19 — Écran « Exposition crédit » (rapport consolidé, trié par
   risque). Chaque ligne mène à la fiche crédit du client (sans URL tapée).
   Export .xlsx via `creditApi.exportExpositionXlsx`. Aucune donnée
   `prix_achat`/marge n'est jamais demandée ni rendue (règle #4).
   ========================================================================== */

export default function ExpositionCreditPage() {
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    creditApi
      .getExposition()
      .then((res) => {
        if (alive) {
          setLignes(res.data?.resultats ?? [])
          setError(null)
        }
      })
      .catch(() => {
        if (alive) setError("Impossible de charger l'exposition crédit.")
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  async function exporter() {
    try {
      const res = await creditApi.exportExpositionXlsx()
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'exposition_credit.xlsx'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setError("Export impossible.")
    }
  }

  if (loading) return <div className="credit-exposition">Chargement…</div>

  return (
    <div className="credit-exposition" data-testid="credit-exposition">
      <div className="credit-exposition__header">
        <button type="button" onClick={exporter}>Exporter (.xlsx)</button>
      </div>
      {error && <p className="credit-exposition__error" role="alert">{error}</p>}
      {lignes.length === 0 ? (
        <p>Aucun client avec exposition crédit.</p>
      ) : (
        <table className="credit-exposition__table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Encours</th>
              <th>Limite</th>
              <th>Disponible</th>
              <th>% utilisé</th>
              <th>Score</th>
              <th>Mode hold</th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l) => (
              <tr key={l.client_id} className={l.depasse ? 'credit-exposition__row--over' : undefined}>
                <td>
                  <Link to={`/credit/clients/${l.client_id}`}>{l.client_nom}</Link>
                </td>
                <td>{formatMAD(l.encours)}</td>
                <td>{formatMAD(l.limite)}</td>
                <td>{formatMAD(l.disponible)}</td>
                <td>
                  {l.pct_utilise === null || l.pct_utilise === undefined
                    ? '—'
                    : `${Math.round(l.pct_utilise * 100)}%`}
                </td>
                <td>{l.lettre_score || '—'}</td>
                <td>{l.mode_hold || 'aucun'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'

import creditApi from '../../api/creditApi'

/* ============================================================================
   NTCRD20 — Page « Exposition crédit » (route cible /ventes/exposition-credit,
   réservée Directeur/Commercial responsable — le backend re-vérifie et scope
   la société). Tableau trié par risque avec code couleur (vert/orange/rouge
   selon pct utilisé + lettre de score), export .xlsx, clic → fiche crédit
   client (NTCRD10). Aucune donnée `prix_achat` n'est jamais rendue.
   ========================================================================== */

function riskClass(row) {
  if (row.depasse) return 'credit-expo__row--red'
  const pct = row.pct_utilise ?? 0
  if (pct >= 0.8 || ['D', 'E'].includes(row.lettre_score)) {
    return 'credit-expo__row--orange'
  }
  return 'credit-expo__row--green'
}

function formatMAD(v) {
  if (v === null || v === undefined) return '—'
  return `${Number(v).toLocaleString('fr-FR')} MAD`
}

export default function ExpositionCreditPage({ onOpenClient }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    creditApi
      .getExposition()
      .then((res) => setRows(res.data.resultats || []))
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  async function exportXlsx() {
    try {
      const res = await creditApi.exportExpositionXlsx()
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'exposition_credit.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Export impossible.')
    }
  }

  if (loading) return <div className="credit-expo">Chargement…</div>

  return (
    <div className="credit-expo" data-testid="credit-exposition">
      <div className="credit-expo__header">
        <h2>Exposition crédit</h2>
        <button type="button" onClick={exportXlsx}>
          Exporter .xlsx
        </button>
      </div>
      {error && <p className="credit-expo__error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>Client</th>
            <th>Encours</th>
            <th>Limite</th>
            <th>Disponible</th>
            <th>% utilisé</th>
            <th>Score</th>
            <th>Garantie</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.client_id}
              className={riskClass(row)}
              onClick={() => onOpenClient && onOpenClient(row.client_id)}
            >
              <td>{row.client_nom}</td>
              <td>{formatMAD(row.encours)}</td>
              <td>{formatMAD(row.limite)}</td>
              <td>{formatMAD(row.disponible)}</td>
              <td>
                {row.pct_utilise === null || row.pct_utilise === undefined
                  ? '—'
                  : `${Math.round(row.pct_utilise * 100)}%`}
              </td>
              <td>{row.lettre_score}</td>
              <td>{formatMAD(row.garantie_assurance)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

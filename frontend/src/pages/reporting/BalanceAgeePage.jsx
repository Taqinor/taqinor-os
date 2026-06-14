import { useEffect, useState } from 'react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`

export default function BalanceAgeePage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    ventesApi.getBalanceAgee()
      .then(r => setRows(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const releve = async (r) => {
    try {
      const res = await ventesApi.getClientRelevePdf(r.client_id)
      openPdfBlob(res.data, `Releve_${r.client_nom}.pdf`)
    } catch { alert('Relevé indisponible.') }
  }

  const sum = (k) => rows.reduce((s, r) => s + Number(r[k] || 0), 0)

  return (
    <div className="page">
      <div className="page-header">
        <h2>Balance âgée</h2>
      </div>
      {loading ? <p className="page-loading">Chargement…</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Client</th>
              <th className="ta-right">0–30 j</th>
              <th className="ta-right">31–60 j</th>
              <th className="ta-right">61–90 j</th>
              <th className="ta-right">90+ j</th>
              <th className="ta-right">Total dû</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.client_id}>
                <td><strong>{r.client_nom}</strong></td>
                <td className="ta-right">{dh(r.b0_30)}</td>
                <td className="ta-right">{dh(r.b31_60)}</td>
                <td className="ta-right">{dh(r.b61_90)}</td>
                <td className="ta-right" style={{ color: '#dc2626' }}>{dh(r.b90_plus)}</td>
                <td className="ta-right"><strong>{dh(r.total)}</strong></td>
                <td className="ta-right">
                  <button className="btn btn-sm btn-outline" onClick={() => releve(r)}>Relevé</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#94a3b8', padding: '2rem' }}>
                Aucun encours client. 🎉
              </td></tr>
            )}
          </tbody>
          {rows.length > 0 && (
            <tfoot>
              <tr style={{ fontWeight: 700, background: '#f8fafc' }}>
                <td>Total</td>
                <td className="ta-right">{dh(sum('b0_30'))}</td>
                <td className="ta-right">{dh(sum('b31_60'))}</td>
                <td className="ta-right">{dh(sum('b61_90'))}</td>
                <td className="ta-right">{dh(sum('b90_plus'))}</td>
                <td className="ta-right">{dh(sum('total'))}</td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>
      )}
    </div>
  )
}

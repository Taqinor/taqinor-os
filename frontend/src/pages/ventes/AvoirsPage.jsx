import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`

export default function AvoirsPage() {
  const role = useSelector(s => s.auth.role)
  const isAdmin = role === 'admin'
  const [avoirs, setAvoirs] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    ventesApi.getAvoirs()
      .then(r => setAvoirs(r.data.results ?? r.data)).catch(() => {})
      .finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const download = async (a) => {
    try {
      const res = await ventesApi.telechargerAvoirPdf(a.id)
      openPdfBlob(res.data, `${a.reference}.pdf`)
    } catch { alert('PDF indisponible.') }
  }
  const annuler = async (a) => {
    if (!window.confirm(`Annuler l'avoir ${a.reference} ?`)) return
    try { await ventesApi.annulerAvoir(a.id); load() } catch { /* */ }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Avoirs (notes de crédit) <span className="count-badge">{avoirs.length}</span></h2>
      </div>
      {loading ? <p className="page-loading">Chargement…</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Référence</th><th>Facture</th><th>Client</th>
              <th className="ta-right">Total TTC</th><th>Motif</th>
              <th>Statut</th><th></th>
            </tr>
          </thead>
          <tbody>
            {avoirs.map(a => (
              <tr key={a.id}>
                <td><strong>{a.reference}</strong></td>
                <td>{a.facture_reference}</td>
                <td>{a.client_nom}</td>
                <td className="ta-right">{dh(a.total_ttc)}</td>
                <td>{a.motif || '—'}</td>
                <td>{a.statut_display}</td>
                <td className="ta-right">
                  <button className="btn btn-sm btn-outline" onClick={() => download(a)}>PDF</button>
                  {isAdmin && a.statut !== 'annulee' && (
                    <button className="btn btn-sm btn-danger" style={{ marginLeft: 6 }}
                            onClick={() => annuler(a)}>Annuler</button>
                  )}
                </td>
              </tr>
            ))}
            {avoirs.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#94a3b8', padding: '2rem' }}>
                Aucun avoir. Créez-en un depuis une facture émise.
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}

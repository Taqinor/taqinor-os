import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'
import PeriodFilter from './PeriodFilter'
import { downloadBlob } from '../../utils/downloadBlob'

export default function ServiceReportPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [params, setParams] = useState({})

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      try {
        const r = await reportingApi.getService(params)
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [params])

  const exportXlsx = async () => {
    try {
      const r = await reportingApi.getServiceXlsx(params)
      downloadBlob(r.data, 'rapport_service.xlsx')
    } catch { alert('Export indisponible.') }
  }

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <h2>Rapport service (chantiers + SAV)</h2>
        <button className="btn btn-sm" onClick={exportXlsx}>Exporter (.xlsx)</button>
      </div>
      <PeriodFilter onApply={setParams} />

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <Kpi label="SAV ouverts" value={data.sav.ouverts} color="#ef4444" />
            <Kpi label="SAV résolus" value={data.sav.resolus} color="#22c55e" />
            <Kpi label="Délai résolution moyen" value={`${data.sav.delai_resolution_moyen_jours} j`} color="#3b82f6" />
            <Kpi label="Délai pose moyen" value={`${data.completion.delai_moyen_jours} j`} color="#8b5cf6"
              sub={`${data.completion.nb_termines} chantiers posés`} />
          </div>

          <Card title="Chantiers par statut (charge de planning)">
            <table className="data-table">
              <thead><tr><th>Statut</th><th className="ta-right">Nombre</th></tr></thead>
              <tbody>
                {data.chantiers_par_statut.map(r => (
                  <tr key={r.statut}><td>{r.label}</td><td className="ta-right">{r.nb}</td></tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Délais de réalisation">
            <table className="data-table">
              <tbody>
                <tr><td>Chantiers posés</td><td className="ta-right">{data.completion.nb_termines}</td></tr>
                <tr><td>Délai moyen (jours)</td><td className="ta-right">{data.completion.delai_moyen_jours}</td></tr>
                <tr><td>Délai min (jours)</td><td className="ta-right">{data.completion.delai_min_jours}</td></tr>
                <tr><td>Délai max (jours)</td><td className="ta-right">{data.completion.delai_max_jours}</td></tr>
              </tbody>
            </table>
          </Card>

          <Card title="Activité par technicien">
            <table className="data-table">
              <thead><tr><th>Technicien</th><th className="ta-right">Chantiers</th><th className="ta-right">Clôturés</th></tr></thead>
              <tbody>
                {data.activite_techniciens.length === 0 ? (
                  <tr><td colSpan={3} style={empty}>Aucun chantier.</td></tr>
                ) : data.activite_techniciens.map((r, i) => (
                  <tr key={i}><td>{r.technicien}</td><td className="ta-right">{r.chantiers}</td><td className="ta-right">{r.termines}</td></tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title={`Garanties expirant (≤ ${data.horizon_garantie_jours} jours)`}>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead><tr><th>Produit</th><th>N° série</th><th>Client</th><th>Fin garantie</th><th className="ta-right">Jours restants</th></tr></thead>
                <tbody>
                  {data.garanties_expirant.length === 0 ? (
                    <tr><td colSpan={5} style={empty}>Aucune garantie n'expire dans la fenêtre.</td></tr>
                  ) : data.garanties_expirant.map((r, i) => (
                    <tr key={i}>
                      <td>{r.produit}</td><td>{r.numero_serie}</td><td>{r.client}</td>
                      <td>{r.date_fin_garantie}</td>
                      <td className="ta-right" style={{ color: r.jours_restants <= 30 ? '#dc2626' : '#d97706', fontWeight: 600 }}>{r.jours_restants}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

function Kpi({ label, value, color, sub }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)' }}>
      <div style={{ fontSize: 12.5, color: '#64748b', fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)', marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#1e293b', margin: '0 0 0.75rem' }}>{title}</h3>
      {children}
    </div>
  )
}

const empty = { textAlign: 'center', color: '#94a3b8', padding: '1.5rem' }

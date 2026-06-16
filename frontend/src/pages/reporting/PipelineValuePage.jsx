import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'
import PeriodFilter from './PeriodFilter'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} MAD`

export default function PipelineValuePage() {
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
        const r = await reportingApi.getPipelineValue(params)
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [params])

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header"><h2>Valeur du pipeline</h2></div>
      <PeriodFilter onApply={setParams} />

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem', marginBottom: '1.5rem',
          }}>
            <Kpi label="Valeur totale du pipeline" value={dh(data.total_pipeline)} color="#3b82f6" />
            <Kpi label="Prévision pondérée" value={dh(data.forecast_pondere)} color="#8b5cf6"
              sub="Pondérée par probabilité d'étape" />
            <Kpi label="Affaires gagnées" value={data.win_loss.gagnes} color="#22c55e" />
            <Kpi label="Affaires perdues" value={data.win_loss.perdus} color="#ef4444" />
          </div>

          <Card title="Valeur par étape du pipeline">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Étape</th>
                  <th className="ta-right">Leads</th>
                  <th className="ta-right">Poids</th>
                  <th className="ta-right">Valeur</th>
                  <th className="ta-right">Valeur pondérée</th>
                </tr>
              </thead>
              <tbody>
                {data.par_etape.map(r => (
                  <tr key={r.stage}>
                    <td><strong>{r.label}</strong></td>
                    <td className="ta-right">{r.nb}</td>
                    <td className="ta-right">{Math.round(r.poids * 100)}%</td>
                    <td className="ta-right">{dh(r.valeur)}</td>
                    <td className="ta-right">{dh(r.valeur_ponderee)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Devis par statut">
            <table className="data-table">
              <thead>
                <tr><th>Statut</th><th className="ta-right">Nombre</th><th className="ta-right">Valeur TTC</th></tr>
              </thead>
              <tbody>
                {data.devis_par_statut.map(r => (
                  <tr key={r.statut}>
                    <td>{r.label}</td>
                    <td className="ta-right">{r.nb}</td>
                    <td className="ta-right">{dh(r.valeur)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Gagné / Perdu par motif de perte">
            <table className="data-table">
              <thead><tr><th>Motif de perte</th><th className="ta-right">Nombre</th></tr></thead>
              <tbody>
                {data.win_loss.par_motif.length === 0 ? (
                  <tr><td colSpan={2} style={empty}>Aucune perte enregistrée.</td></tr>
                ) : data.win_loss.par_motif.map((r, i) => (
                  <tr key={i}><td>{r.motif}</td><td className="ta-right">{r.nb}</td></tr>
                ))}
              </tbody>
            </table>
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

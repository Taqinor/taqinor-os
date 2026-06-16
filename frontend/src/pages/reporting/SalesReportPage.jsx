import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'
import PeriodFilter from './PeriodFilter'
import { downloadBlob } from '../../utils/downloadBlob'

const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} MAD`

export default function SalesReportPage() {
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
        const r = await reportingApi.getSales(params)
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [params])

  const exportXlsx = async () => {
    try {
      const r = await reportingApi.getSalesXlsx(params)
      downloadBlob(r.data, `rapport_ventes.xlsx`)
    } catch { alert('Export indisponible.') }
  }

  const exportJournal = async () => {
    try {
      const r = await reportingApi.getJournalVentesXlsx(params)
      downloadBlob(r.data, `journal_ventes.xlsx`)
    } catch { alert('Export indisponible.') }
  }

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <h2>Rapport ventes & pipeline</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-outline" onClick={exportJournal}>Journal des ventes + TVA (.xlsx)</button>
          <button className="btn btn-sm" onClick={exportXlsx}>Exporter (.xlsx)</button>
        </div>
      </div>
      <PeriodFilter onApply={setParams} />

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <>
          <Card title="Entonnoir leads par étape">
            <table className="data-table">
              <thead><tr><th>Étape</th><th className="ta-right">Leads</th></tr></thead>
              <tbody>
                {data.funnel.map(r => (
                  <tr key={r.stage}><td>{r.label}</td><td className="ta-right">{r.nb}</td></tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card title="Devis par statut & valeur">
            <table className="data-table">
              <thead><tr><th>Statut</th><th className="ta-right">Nombre</th><th className="ta-right">Valeur TTC</th></tr></thead>
              <tbody>
                {data.devis_par_statut.map(r => (
                  <tr key={r.statut}><td>{r.label}</td><td className="ta-right">{r.nb}</td><td className="ta-right">{dh(r.valeur)}</td></tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
            <Card title="CA par responsable">
              <SimpleTable rows={data.ca_par_responsable} cols={['nom', 'ca']} labels={['Responsable', 'CA HT']} money={['ca']} />
            </Card>
            <Card title="CA par canal">
              <SimpleTable rows={data.ca_par_canal} cols={['canal', 'ca']} labels={['Canal', 'CA HT']} money={['ca']} />
            </Card>
          </div>

          <Card title="CA par mois">
            <SimpleTable rows={data.ca_par_mois} cols={['mois', 'ca']} labels={['Mois', 'CA HT']} money={['ca']} />
          </Card>

          <Card title="Gagné / Perdu par motif de perte">
            <div style={{ display: 'flex', gap: 16, marginBottom: 12, fontSize: 14 }}>
              <span>Gagnés : <strong style={{ color: '#22c55e' }}>{data.win_loss.gagnes}</strong></span>
              <span>Perdus : <strong style={{ color: '#ef4444' }}>{data.win_loss.perdus}</strong></span>
            </div>
            <table className="data-table">
              <thead><tr><th>Motif</th><th className="ta-right">Nombre</th></tr></thead>
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

function SimpleTable({ rows, cols, labels, money = [] }) {
  const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { maximumFractionDigits: 0 })} MAD`
  return (
    <table className="data-table">
      <thead><tr>{labels.map((l, i) => <th key={i} className={i > 0 ? 'ta-right' : ''}>{l}</th>)}</tr></thead>
      <tbody>
        {rows.length === 0 ? (
          <tr><td colSpan={cols.length} style={empty}>Aucune donnée.</td></tr>
        ) : rows.map((r, i) => (
          <tr key={i}>
            {cols.map((c, j) => (
              <td key={j} className={j > 0 ? 'ta-right' : ''}>
                {money.includes(c) ? dh(r[c]) : r[c]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
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

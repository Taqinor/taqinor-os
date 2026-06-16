import { useEffect, useState } from 'react'
import reportingApi from '../../api/reportingApi'

// N49 — Vue du chiffre d'affaires récurrent (contrats d'entretien).
// Lecture seule, scopée société. Affiche les contrats actifs (nombre + valeur
// mensuelle/annuelle), les renouvellements à venir et les contrats expirés.
const dh = (v) => `${Number(v ?? 0).toLocaleString('fr-MA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} MAD`

export default function RecurringRevenuePage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      try {
        const r = await reportingApi.getRecurringRevenue()
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [])

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <h2>Chiffre d'affaires récurrent</h2>
      </div>

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            <Kpi label="Contrats actifs" value={data.actifs.count} />
            <Kpi label="Valeur mensuelle" value={dh(data.actifs.valeur_mensuelle)} />
            <Kpi label="Valeur annuelle" value={dh(data.actifs.valeur_annuelle)} />
            <Kpi label="À renouveler" value={data.a_renouveler.count} />
            <Kpi label="Expirés / résiliés" value={data.expires.count} />
          </div>

          <Card title={`Renouvellements à venir (${data.a_renouveler.count})`}>
            <ContractTable rows={data.a_renouveler.contrats} />
          </Card>

          <Card title={`Contrats actifs (${data.actifs.count})`}>
            <ContractTable rows={data.contrats_actifs} />
          </Card>

          <Card title={`Contrats expirés / résiliés (${data.expires.count})`}>
            <ContractTable rows={data.expires.contrats} />
          </Card>
        </>
      )}
    </div>
  )
}

function ContractTable({ rows }) {
  if (!rows || rows.length === 0) return <p style={empty}>Aucun contrat.</p>
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Contrat</th><th>Client</th><th>Début</th><th>Fin</th>
          <th className="ta-right">Jours avant fin</th>
          <th className="ta-right">Valeur mensuelle</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r.id}>
            <td>{r.libelle}</td>
            <td>{r.client}</td>
            <td>{r.date_debut || '—'}</td>
            <td>{r.date_fin || '—'}</td>
            <td className="ta-right">{r.jours_avant_fin ?? '—'}</td>
            <td className="ta-right">{dh(r.montant_mensuel)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Kpi({ label, value }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: '1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)', minWidth: 160, flex: '1 1 160px' }}>
      <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#1e293b', marginTop: 4 }}>{value}</div>
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

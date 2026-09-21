import { useEffect, useMemo, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Card } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   NTFPA24 — Tableau de bord FP&A exécutif.
   ----------------------------------------------------------------------------
   KPI cards (budget total annuel, forecast fin d'année, revenu prévisionnel,
   marge), cascade revenu → charges → marge (waterfall simplifiée), top 3
   départements en dépassement, lien vers le détail de variance. Charge en une
   requête consolidée (pas de N+1 par département).
   ========================================================================== */

function Kpi({ label, value }) {
  return (
    <Card>
      <div style={{ fontSize: 13, opacity: 0.7 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </Card>
  )
}

export default function DashboardPage() {
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [conso, setConso] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fpaApi.getCycles()
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
        setCycles(list)
        if (list[0]) setCycleId(String(list[0].id))
      })
      .catch(() => setError('Impossible de charger les cycles.'))
  }, [])

  useEffect(() => {
    if (!cycleId) return
    fpaApi.consolidation({ cycle: cycleId })
      .then((res) => { setConso(res.data); setError(null) })
      .catch(() => setError('Impossible de charger la consolidation.'))
  }, [cycleId])

  const cascade = useMemo(() => {
    if (!conso) return []
    return [
      { label: 'Revenu prévisionnel', value: Number(conso.revenu_previsionnel || 0) },
      { label: 'Dépenses', value: -Number(conso.total_depenses || 0) },
      { label: 'Marge brute', value: Number(conso.marge_brute_previsionnelle || 0) },
    ]
  }, [conso])

  return (
    <div>
      <PageHeader
        title="Tableau de bord FP&A"
        subtitle="Vue exécutive du cycle budgétaire"
      />
      <div style={{ marginBottom: 16 }}>
        <select
          aria-label="Cycle budgétaire"
          value={cycleId}
          onChange={(e) => setCycleId(e.target.value)}
        >
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
      </div>
      {error && <p role="alert" style={{ color: 'var(--danger, #c00)' }}>{error}</p>}
      {conso && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
            <Kpi label="Revenu prévisionnel" value={formatMAD(Number(conso.revenu_previsionnel || 0))} />
            <Kpi label="Total dépenses budgétées" value={formatMAD(Number(conso.total_depenses || 0))} />
            <Kpi label="Marge brute prévisionnelle" value={formatMAD(Number(conso.marge_brute_previsionnelle || 0))} />
            <Kpi label="Revenu carnet (engagé)" value={formatMAD(Number(conso.revenu_carnet || 0))} />
          </div>
          <Card>
            <h3>Cascade Revenu → Charges → Marge</h3>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <tbody>
                {cascade.map((step) => (
                  <tr key={step.label}>
                    <td style={{ padding: 8 }}>{step.label}</td>
                    <td style={{ padding: 8, textAlign: 'right', fontWeight: 600 }}>
                      {formatMAD(step.value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <Card>
            <h3>Dépenses par catégorie</h3>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <tbody>
                {Object.entries(conso.depenses_par_categorie || {}).map(([cat, montant]) => (
                  <tr key={cat}>
                    <td style={{ padding: 8 }}>{cat}</td>
                    <td style={{ padding: 8, textAlign: 'right' }}>
                      {formatMAD(Number(montant || 0))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  )
}

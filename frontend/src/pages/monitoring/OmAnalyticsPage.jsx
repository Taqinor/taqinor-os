import { useEffect, useMemo, useState } from 'react'
import { Activity, CalendarClock, Droplets, Gauge, TrendingDown } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import { Badge, DataTable, EmptyState, Segmented } from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { AreaSansAxe, ChartEmpty } from '../../ui/charts'
import { formatNumber, formatPercent } from '../../lib/format'
import MonitoringNav from './MonitoringNav'
import SystemPicker from './SystemPicker'
import useSupervisedSystems from './useSupervisedSystems'

/* WR6 — Analytique O&M par système (FG279) : Performance Ratio, disponibilité,
   dégradation annualisée et suspicion de salissure, avec la série mensuelle de
   PR (graphique + tableau). 100 % lecture. */

const WINDOWS = [
  { value: 180, label: '6 mois' },
  { value: 365, label: '1 an' },
  { value: 730, label: '2 ans' },
]

export default function OmAnalyticsPage() {
  const { systems, loading: loadingSystems } = useSupervisedSystems()
  const [selectedId, setSelectedId] = useState('')
  const [windowDays, setWindowDays] = useState(365)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!selectedId) return undefined
    let active = true
    const load = async () => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await monitoringApi.getOmMetrics(selectedId, { window_days: windowDays })
        if (active) { setMetrics(r.data); setError(null) }
      } catch {
        if (active) setError('Impossible de charger l’analytique O&M.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [selectedId, windowDays])

  const stats = useMemo(() => (metrics ? [
    {
      label: 'Performance Ratio',
      value: metrics.pr_pct != null ? formatPercent(metrics.pr_pct, { decimals: 1 }) : '—',
      icon: Gauge,
      hint: metrics.expected_kwh != null
        ? `${formatNumber(metrics.production_kwh, { decimals: 0 })} / ${formatNumber(metrics.expected_kwh, { decimals: 0 })} kWh attendus`
        : 'Aucun attendu configuré',
    },
    {
      label: 'Disponibilité',
      value: metrics.availability_pct != null ? formatPercent(metrics.availability_pct, { decimals: 1 }) : '—',
      icon: Activity,
      hint: 'jours couverts par un relevé',
    },
    {
      label: 'Dégradation',
      value: metrics.degradation_pct_per_year != null
        ? `${formatNumber(metrics.degradation_pct_per_year, { decimals: 2 })} %/an`
        : '—',
      icon: TrendingDown,
    },
    {
      label: 'Production (fenêtre)',
      value: `${formatNumber(metrics.production_kwh, { decimals: 0 })} kWh`,
      icon: CalendarClock,
      hint: `sur ${metrics.window_days ?? windowDays} jours`,
    },
  ] : []), [metrics, windowDays])

  const monthly = useMemo(() => metrics?.monthly_pr ?? [], [metrics])
  const chartData = useMemo(() => monthly
    .filter((m) => m.pr_pct != null)
    .map((m) => ({ label: m.month, value: Number(m.pr_pct) })), [monthly])

  const columns = useMemo(() => [
    { id: 'month', header: 'Mois', width: 120, accessor: (r) => r.month },
    {
      id: 'kwh', header: 'Production (kWh)', width: 160, align: 'right',
      accessor: (r) => Number(r.kwh) || 0,
      cell: (v, r) => formatNumber(r.kwh, { decimals: 0 }),
    },
    {
      id: 'pr_pct', header: 'PR mensuel', width: 140, align: 'right',
      accessor: (r) => (r.pr_pct == null ? -1 : Number(r.pr_pct)),
      cell: (v, r) => (r.pr_pct == null ? '—' : formatPercent(r.pr_pct, { decimals: 1 })),
    },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Analytique O&M</h1>
        <div className="page-subtitle">
          PR, disponibilité, salissure et dégradation d’un système supervisé.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <SystemPicker
          systems={systems}
          loading={loadingSystems}
          value={selectedId}
          onChange={setSelectedId}
        />
        <Segmented
          size="sm"
          options={WINDOWS}
          value={windowDays}
          onChange={setWindowDays}
          aria-label="Fenêtre d'analyse"
        />
      </div>

      {!loadingSystems && systems.length === 0 ? (
        <EmptyState
          title="Aucun système supervisé"
          description="Configurez la supervision d'un système depuis l'écran Relevés pour l'analyser ici."
          className="my-6"
        />
      ) : !selectedId ? (
        <EmptyState
          title="Choisissez un système"
          description="Sélectionnez un système supervisé pour voir ses indicateurs O&M."
          className="my-6"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {metrics?.soiling_suspected && !loading && (
            <div
              data-testid="soiling-alert"
              className="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm"
            >
              <Droplets size={16} aria-hidden="true" />
              <span>Salissure suspectée — le PR mensuel décroît régulièrement.</span>
              <Badge tone="warning">À vérifier</Badge>
            </div>
          )}

          <ModuleDashboard
            stats={stats}
            loading={loading}
            error={error}
            charts={!loading && !error && metrics ? [{
              title: 'PR mensuel (%)',
              span: 'full',
              node: chartData.length > 0
                ? <AreaSansAxe data={chartData} height={220} name="PR" tone="info" tooltipFormat={(v) => formatPercent(v, { decimals: 1 })} />
                : <ChartEmpty />,
            }] : []}
          />

          {!loading && !error && monthly.length > 0 && (
            <DataTable
              data={monthly}
              columns={columns}
              getRowId={(row) => row.month}
              searchable={false}
              pageSize={25}
              aria-label="PR mensuel"
            />
          )}
        </div>
      )}
    </div>
  )
}

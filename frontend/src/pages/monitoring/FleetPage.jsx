import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Gauge, Sun, Zap } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import { Badge, DataTable, EmptyState, Segmented } from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { BarArrondie, ChartEmpty } from '../../ui/charts'
import { formatNumber, formatPercent } from '../../lib/format'
import MonitoringNav from './MonitoringNav'

/* WR6 — Vue PARC / FLOTTE multi-systèmes (FG281) : production totale, kWc
   installés, PR moyen pondéré et alertes de sous-performance ouvertes sur tous
   les systèmes supervisés de la société, sur une fenêtre glissante. */

const WINDOWS = [
  { value: 90, label: '90 j' },
  { value: 180, label: '180 j' },
  { value: 365, label: '1 an' },
]

export default function FleetPage() {
  const [fleet, setFleet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [windowDays, setWindowDays] = useState(365)

  useEffect(() => {
    let active = true
    const load = async () => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await monitoringApi.getFleet({ window_days: windowDays })
        if (active) { setFleet(r.data); setError(null) }
      } catch {
        if (active) setError('Impossible de charger la vue parc.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [windowDays])

  const systems = useMemo(() => fleet?.systems ?? [], [fleet])

  const stats = useMemo(() => (fleet ? [
    {
      label: 'Systèmes actifs',
      value: formatNumber(fleet.systems_active),
      icon: Sun,
    },
    {
      label: 'Puissance installée',
      value: `${formatNumber(fleet.total_kwc)} kWc`,
      icon: Zap,
    },
    {
      label: 'Production (fenêtre)',
      value: `${formatNumber(fleet.total_production_kwh)} kWh`,
      hint: `sur ${fleet.window_days ?? windowDays} jours`,
    },
    {
      label: 'PR parc',
      value: fleet.fleet_pr_pct != null ? formatPercent(fleet.fleet_pr_pct, { decimals: 1 }) : '—',
      icon: Gauge,
      hint: fleet.open_alerts > 0
        ? `${fleet.open_alerts} alerte(s) de sous-performance`
        : 'Aucune alerte ouverte',
    },
  ] : []), [fleet, windowDays])

  const chartData = useMemo(() => systems
    .filter((s) => s.pr_pct != null)
    .map((s) => ({
      label: s.reference || `#${s.installation}`,
      value: Number(s.pr_pct),
    })), [systems])

  const columns = useMemo(() => [
    {
      id: 'reference', header: 'Système',
      accessor: (r) => r.reference || `#${r.installation}`,
    },
    {
      id: 'puissance_kwc', header: 'kWc', width: 110, align: 'right',
      accessor: (r) => Number(r.puissance_kwc) || 0,
      cell: (v, r) => formatNumber(r.puissance_kwc, { decimals: 2 }),
    },
    {
      id: 'production_kwh', header: 'Production (kWh)', width: 160, align: 'right',
      accessor: (r) => Number(r.production_kwh) || 0,
      cell: (v, r) => formatNumber(r.production_kwh, { decimals: 0 }),
    },
    {
      id: 'pr_pct', header: 'PR', width: 120, align: 'right',
      accessor: (r) => (r.pr_pct == null ? -1 : Number(r.pr_pct)),
      cell: (v, r) => (r.pr_pct == null
        ? <span className="text-muted-foreground">—</span>
        : (
          <Badge tone={Number(r.pr_pct) < 80 ? 'danger' : 'success'}>
            {formatPercent(r.pr_pct, { decimals: 1 })}
          </Badge>
        )),
    },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Vue parc</h1>
        <div className="page-subtitle">
          Production, performance et alertes sur l’ensemble des systèmes supervisés.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">Fenêtre d’analyse</span>
        <Segmented
          size="sm"
          options={WINDOWS}
          value={windowDays}
          onChange={setWindowDays}
          aria-label="Fenêtre d'analyse"
        />
      </div>

      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
        charts={!loading && !error ? [{
          title: 'PR par système (%)',
          span: 'full',
          node: chartData.length > 0
            ? <BarArrondie data={chartData} height={220} name="PR" tooltipFormat={(v) => formatPercent(v, { decimals: 1 })} />
            : <ChartEmpty />,
        }] : []}
      />

      {!loading && !error && (
        systems.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="Aucun système supervisé"
            description="Configurez la supervision d'un système depuis l'écran Relevés pour le voir apparaître ici."
            className="my-6"
          />
        ) : (
          <div className="mt-6">
            <DataTable
              data={systems}
              columns={columns}
              getRowId={(row) => row.installation}
              searchable={false}
              pageSize={25}
              aria-label="Systèmes du parc"
            />
          </div>
        )
      )}
    </div>
  )
}

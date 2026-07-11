import { useEffect, useMemo, useState } from 'react'
import monitoringApi from '../../api/monitoringApi'
import { DataTable, EmptyState } from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { BarArrondie, ChartEmpty } from '../../ui/charts'
import { formatNumber } from '../../lib/format'
import { METRIC_ICONS } from '../../ui/metricIcons'
import MonitoringNav from './MonitoringNav'

/* WR7 — Suivi CO₂ évité (FG286) : CO₂ évité cumulé sur le parc + par système,
   depuis GET /monitoring/configs/co2-fleet/. Rend uniquement ce que renvoie le
   backend (kg / tonnes / production) — aucune donnée interne.
   VX157 — icônes de grandeur métier unifiées via ui/metricIcons.js (avant :
   Leaf/Sprout/Zap importées ad hoc ici), + accent d'impact sur le CO₂ évité. */

export default function Co2Page() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await monitoringApi.getCo2Fleet()
        if (active) { setData(r.data); setError(null) }
      } catch {
        if (active) setError('Impossible de charger le suivi CO₂.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [])

  const systems = useMemo(() => data?.systems ?? [], [data])

  const stats = useMemo(() => (data ? [
    {
      label: 'CO₂ évité (parc)',
      value: `${formatNumber(data.total_co2_tonnes, { decimals: 3 })} t`,
      icon: METRIC_ICONS.co2,
      hint: `${formatNumber(data.total_co2_kg, { decimals: 0 })} kg`,
      tone: 'impact',
    },
    {
      label: 'Production cumulée',
      value: `${formatNumber(data.total_production_kwh, { decimals: 0 })} kWh`,
      icon: METRIC_ICONS.production,
      tone: 'impact',
    },
    {
      label: 'Facteur réseau',
      value: `${formatNumber(data.co2_kg_par_kwh, { decimals: 2 })} kg/kWh`,
      icon: METRIC_ICONS.co2,
      hint: 'CO₂ évité par kWh autoproduit',
    },
  ] : []), [data])

  const chartData = useMemo(() => systems
    .map((s) => ({
      label: s.reference || `#${s.installation}`,
      value: Number(s.co2_tonnes) || 0,
    })), [systems])

  const columns = useMemo(() => [
    {
      id: 'reference', header: 'Système',
      accessor: (r) => r.reference || `#${r.installation}`,
    },
    {
      id: 'production_kwh', header: 'Production (kWh)', width: 160, align: 'right',
      accessor: (r) => Number(r.production_kwh) || 0,
      cell: (v, r) => formatNumber(r.production_kwh, { decimals: 0 }),
    },
    {
      id: 'co2_kg', header: 'CO₂ évité (kg)', width: 150, align: 'right',
      accessor: (r) => Number(r.co2_kg) || 0,
      cell: (v, r) => formatNumber(r.co2_kg, { decimals: 0 }),
    },
    {
      id: 'co2_tonnes', header: 'CO₂ évité (t)', width: 140, align: 'right',
      accessor: (r) => Number(r.co2_tonnes) || 0,
      cell: (v, r) => formatNumber(r.co2_tonnes, { decimals: 3 }),
    },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Suivi CO₂</h1>
        <div className="page-subtitle">
          CO₂ évité par la production solaire, cumulé sur le parc et par système.
        </div>
      </div>
      <MonitoringNav />

      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
        charts={!loading && !error ? [{
          title: 'CO₂ évité par système (tonnes)',
          span: 'full',
          node: chartData.length > 0
            ? <BarArrondie data={chartData} height={220} tone="success" name="CO₂ évité" tooltipFormat={(v) => `${formatNumber(v, { decimals: 3 })} t`} />
            : <ChartEmpty />,
        }] : []}
      />

      {!loading && !error && (
        systems.length === 0 ? (
          <EmptyState
            icon={METRIC_ICONS.co2}
            title="Aucune donnée CO₂"
            description="Le CO₂ évité apparaît dès qu'un système supervisé a des relevés de production."
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
              aria-label="CO₂ évité par système"
            />
          </div>
        )
      )}
    </div>
  )
}

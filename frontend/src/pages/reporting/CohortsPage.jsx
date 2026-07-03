import { useEffect, useMemo, useState } from 'react'
import { Users } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { DataTable, EmptyState, Segmented, Spinner } from '../../ui'
import { BarArrondie, ChartEmpty } from '../../ui/charts'
import { formatNumber, formatPercent } from '../../lib/format'

/* WR8 — Cohortes / saisonnalité (FG98). Leads groupés par mois d'acquisition :
   taux de signature + délai moyen lead→signé, depuis
   GET /reporting/insights/cohorts/ (?group_by=canal optionnel). Lecture seule,
   réservé responsable/admin (gate route). */

const GROUP_BY = [
  { value: '', label: 'Par mois' },
  { value: 'canal', label: 'Par mois & canal' },
]

export default function CohortsPage() {
  const [groupBy, setGroupBy] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    const load = async () => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await reportingApi.cohorts(groupBy ? { group_by: groupBy } : {})
        if (active) { setData(r.data); setError(false) }
      } catch {
        if (active) setError(true)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [groupBy])

  const cohorts = useMemo(() => data?.cohorts ?? [], [data])

  const chartData = useMemo(() => cohorts.map((c) => ({
    label: c.cohorte,
    value: Number(c.taux_signature) || 0,
  })), [cohorts])

  const columns = useMemo(() => [
    { id: 'cohorte', header: 'Cohorte', accessor: (r) => r.cohorte },
    {
      id: 'nb_leads', header: 'Leads', width: 100, align: 'right',
      accessor: (r) => Number(r.nb_leads) || 0,
    },
    {
      id: 'nb_signes', header: 'Signés', width: 100, align: 'right',
      accessor: (r) => Number(r.nb_signes) || 0,
    },
    {
      id: 'taux_signature', header: 'Taux signature', width: 150, align: 'right',
      accessor: (r) => Number(r.taux_signature) || 0,
      cell: (v, r) => formatPercent(r.taux_signature, { decimals: 1 }),
    },
    {
      id: 'avg_days_to_sign', header: 'Délai moyen', width: 140, align: 'right',
      accessor: (r) => (r.avg_days_to_sign == null ? -1 : Number(r.avg_days_to_sign)),
      cell: (v, r) => (r.avg_days_to_sign == null
        ? '—'
        : `${formatNumber(r.avg_days_to_sign, { decimals: 1 })} j`),
    },
  ], [])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Cohortes de leads</h1>
        <div className="page-subtitle">
          Taux de signature et délai moyen par mois d’acquisition.
        </div>
      </div>

      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">Regroupement</span>
        <Segmented
          size="sm"
          options={GROUP_BY}
          value={groupBy}
          onChange={setGroupBy}
          aria-label="Regroupement des cohortes"
        />
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error ? (
        <EmptyState
          icon={Users}
          title="Impossible de charger les cohortes"
          description="Une erreur est survenue lors du chargement des cohortes."
          className="my-6"
        />
      ) : cohorts.length === 0 ? (
        <EmptyState
          icon={Users}
          title="Aucune cohorte"
          description="Aucun lead sur la période analysée."
          className="my-6"
        />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
            <h3 className="mb-3 font-display text-base font-semibold tracking-tight">
              Taux de signature par cohorte (%)
            </h3>
            {chartData.length > 0
              ? <BarArrondie data={chartData} height={240} name="Taux signature" tooltipFormat={(v) => formatPercent(v, { decimals: 1 })} />
              : <ChartEmpty />}
          </div>
          <DataTable
            data={cohorts}
            columns={columns}
            getRowId={(row) => row.cohorte}
            searchable={false}
            pageSize={30}
            aria-label="Cohortes de leads"
          />
        </div>
      )}
    </div>
  )
}

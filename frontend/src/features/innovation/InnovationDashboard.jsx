import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lightbulb, ThumbsUp, Clock, LayoutGrid } from 'lucide-react'
import { ModuleDashboard } from '../../ui/module'
import { EmptyState } from '../../ui'
import { AreaSansAxe } from '../../ui/charts'
import innovationApi from '../../api/innovationApi'
import { STATUT_MAP, StatutIdeePill } from './innovationStatus'

/* ============================================================================
   NTIDE6 — Tableau de bord d'idées (admin) : KPI cards par statut, top 5 par
   votes, plus récentes, heat-chart par contexte. Drill-down vers la liste
   filtrée / le détail. Réservé au palier admin/responsable côté serveur
   (route elle-même gatée, voir module.config.jsx).
   NTIDE23 — timeline « idées par jour » (graphe Recharts) en bas de page.
   ========================================================================== */

export default function InnovationDashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [timeline, setTimeline] = useState([])

  useEffect(() => {
    innovationApi.tableauBord()
      .then((res) => setData(res.data))
      .catch(() => setError('Impossible de charger le tableau de bord.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    innovationApi.timeline()
      .then((res) => setTimeline(res.data?.results || []))
      .catch(() => setTimeline([]))
  }, [])

  const parStatut = data?.par_statut || {}
  const stats = [
    {
      label: 'Ouvertes', value: parStatut.ouvert ?? 0, icon: Lightbulb,
      to: '/innovation/idees?statut=ouvert',
    },
    {
      label: 'Examinées', value: parStatut.examinee ?? 0, icon: Clock,
      to: '/innovation/idees?statut=examinee',
    },
    {
      label: 'Retenues', value: parStatut.retenue ?? 0, icon: ThumbsUp,
      to: '/innovation/idees?statut=retenue',
    },
    {
      label: 'Total', value: parStatut.total ?? 0, icon: LayoutGrid,
      hint: `${parStatut.realisee ?? 0} réalisée(s) · ${parStatut.fermee ?? 0} fermée(s)`,
      to: '/innovation/idees',
    },
  ]

  const topVotesNode = (data?.top_votes?.length ?? 0) > 0 ? (
    <ul className="flex flex-col gap-2">
      {data.top_votes.map((i) => (
        <li key={i.id} className="flex items-center justify-between gap-2 text-sm">
          <button
            type="button"
            onClick={() => navigate(`/innovation/idees/${i.id}`)}
            className="truncate text-left font-medium hover:underline"
          >
            {i.titre}
          </button>
          <span className="inline-flex shrink-0 items-center gap-1 tabular-nums text-muted-foreground">
            <ThumbsUp className="size-3.5" aria-hidden="true" /> {i.votes_count}
          </span>
        </li>
      ))}
    </ul>
  ) : <EmptyState title="Aucune idée" description="Aucune idée n'a encore été proposée." />

  const recentesNode = (data?.plus_recentes?.length ?? 0) > 0 ? (
    <ul className="flex flex-col gap-2">
      {data.plus_recentes.map((i) => (
        <li key={i.id} className="flex items-center justify-between gap-2 text-sm">
          <button
            type="button"
            onClick={() => navigate(`/innovation/idees/${i.id}`)}
            className="truncate text-left font-medium hover:underline"
          >
            {i.titre}
          </button>
          <StatutIdeePill status={i.statut} />
        </li>
      ))}
    </ul>
  ) : <EmptyState title="Aucune idée" description="Aucune idée récente." />

  const heatNode = (data?.heat_contexte?.length ?? 0) > 0 ? (
    <ul className="flex flex-col gap-2">
      {data.heat_contexte.map((h) => {
        const max = data.heat_contexte[0].nombre || 1
        const pct = Math.round((h.nombre / max) * 100)
        return (
          <li key={h.contexte}>
            <button
              type="button"
              onClick={() => navigate(`/innovation/idees?contexte=${encodeURIComponent(h.contexte)}`)}
              className="flex w-full items-center justify-between gap-2 text-sm hover:underline"
            >
              <span className="truncate">{h.contexte}</span>
              <span className="tabular-nums text-muted-foreground">{h.nombre}</span>
            </button>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  ) : <EmptyState title="Aucun contexte" description="Aucune idée avec un contexte renseigné." />

  const timelineNode = timeline.length > 0 ? (
    <AreaSansAxe
      data={timeline.map((t) => ({ label: t.date, value: t.nombre }))}
      name="Idées proposées"
      tone="primary"
      height={180}
    />
  ) : <EmptyState title="Aucune donnée" description="Aucune idée proposée sur la période." />

  return (
    <div className="page flex flex-col gap-6">
      <h1 className="inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight">
        <Lightbulb className="size-5" aria-hidden="true" />
        Tableau de bord — Idées
      </h1>
      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
        charts={[
          { title: 'Top 5 par votes', node: topVotesNode },
          { title: 'Plus récentes', node: recentesNode },
          { title: 'Idées par contexte', node: heatNode, span: 'full' },
          { title: 'Idées par jour', node: timelineNode, span: 'full' },
        ]}
      />
    </div>
  )
}

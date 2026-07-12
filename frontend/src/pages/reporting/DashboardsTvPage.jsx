import { useEffect, useMemo, useState } from 'react'
import { Tv, LayoutGrid } from 'lucide-react'
import coreApi from '../../api/coreApi'
import { Spinner, Card, EmptyState } from '../../ui'
import { KpiSpark, AreaSansAxe, ChartEmpty } from '../../ui/charts'

/* ============================================================================
   XPLT10 — Kiosque TV (`/dashboards-tv`) : rotation plein écran des dashboards
   éligibles (`GET core/dashboards-tv/` — société + partagés internes de
   l'utilisateur). Page AUTONOME, sans layout ERP (pas de Sidebar/Header) :
   pensée pour un écran dédié affiché en continu. Rotation + rafraîchissement
   pilotés CÔTÉ ÉCRAN (le backend ne fournit que la liste + le layout déjà
   agrégé — jamais de prix d'achat/marge/liste nominative).

   VX118(c) — `current.layout` (JSON opaque `core.Dashboard.layout`, forme
   réelle documentée par `dashboardFilters.js` : `{widgets:[…], globalFilters}`)
   rendait en `<pre>{JSON.stringify(...)}</pre>` — du texte développeur brut
   sur l'écran regardé toute la journée. Rendu désormais avec le kit existant
   (`ui/charts` + `Card`), grands chiffres lisibles à 3 mètres, sparkline en
   grand pour les widgets porteurs d'une série, `ChartEmpty` pour un widget
   sans données exploitables — jamais de JSON brut.
   ========================================================================== */

const ROTATE_MS = 15000
const REFRESH_MS = 60000

// Normalise une série de widget (nombres bruts ou objets) en points
// {label, value} exploitables par AreaSansAxe/BarArrondie/KpiSpark.
function normalizeSerie(serie) {
  if (!Array.isArray(serie) || !serie.length) return null
  return serie.map((p, i) => (
    typeof p === 'number' || typeof p === 'string'
      ? { label: String(i + 1), value: Number(p) || 0 }
      : {
          label: p.label ?? p.libelle ?? String(i + 1),
          value: Number(p.value ?? p.valeur) || 0,
        }
  ))
}

function TvWidgetCard({ widget }) {
  const label = widget?.titre || widget?.title || widget?.label || 'Indicateur'
  const rawValue = widget?.valeur ?? widget?.value
  const hasValue = rawValue !== undefined && rawValue !== null && rawValue !== ''
  const points = normalizeSerie(widget?.serie ?? widget?.data)

  if (!hasValue && !points) {
    return (
      <Card className="flex flex-col gap-2 p-6">
        <span className="text-lg font-medium text-muted-foreground">{label}</span>
        <ChartEmpty description="Aucune donnée exploitable pour ce widget." />
      </Card>
    )
  }

  return (
    <Card className="flex flex-1 flex-col gap-3 p-6">
      <span className="text-lg font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {hasValue && (
        <span className="num text-6xl font-bold leading-none tabular-nums text-foreground">
          {rawValue}
        </span>
      )}
      {points && (
        hasValue
          ? <KpiSpark data={points.map((p) => p.value)} height={100} tone={widget?.tone || 'primary'} />
          : <AreaSansAxe data={points} height={240} tone={widget?.tone || 'info'} />
      )}
    </Card>
  )
}

export default function DashboardsTvPage() {
  const [dashboards, setDashboards] = useState([])
  const [loading, setLoading] = useState(true)
  const [index, setIndex] = useState(0)

  useEffect(() => {
    let active = true
    const fetchList = () => coreApi.dashboardsTv.list()
      .then((r) => { if (active) setDashboards(r.data?.dashboards ?? []) })
      .catch(() => { if (active) setDashboards([]) })
      .finally(() => { if (active) setLoading(false) })

    fetchList()
    const refreshTimer = setInterval(fetchList, REFRESH_MS)
    return () => { active = false; clearInterval(refreshTimer) }
  }, [])

  useEffect(() => {
    if (dashboards.length < 2) return undefined
    const rotateTimer = setInterval(() => {
      setIndex((i) => (i + 1) % dashboards.length)
    }, ROTATE_MS)
    return () => clearInterval(rotateTimer)
  }, [dashboards.length])

  const current = useMemo(
    () => dashboards[index % Math.max(dashboards.length, 1)],
    [dashboards, index],
  )

  const widgets = useMemo(
    () => (Array.isArray(current?.layout?.widgets) ? current.layout.widgets : []),
    [current],
  )

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <Spinner /> <span className="ml-2 text-sm text-muted-foreground">Chargement…</span>
      </div>
    )
  }

  if (!current) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center gap-3 bg-background text-muted-foreground">
        <Tv className="size-10" aria-hidden="true" />
        <p>Aucun dashboard partagé disponible pour le mode TV.</p>
      </div>
    )
  }

  return (
    <div className="flex h-screen w-screen flex-col bg-background p-6" data-testid="dashboards-tv">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{current.titre}</h1>
        {dashboards.length > 1 && (
          <span className="text-sm text-muted-foreground">
            {index + 1} / {dashboards.length}
          </span>
        )}
      </div>
      {widgets.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <EmptyState
            icon={LayoutGrid}
            title="Aucun widget configuré"
            description="Ce tableau de bord n'a pas encore de widgets à afficher en mode TV."
          />
        </div>
      ) : (
        <div className="grid flex-1 auto-rows-fr gap-4 overflow-auto sm:grid-cols-2 xl:grid-cols-3">
          {widgets.map((w, i) => <TvWidgetCard key={w.id ?? i} widget={w} />)}
        </div>
      )}
    </div>
  )
}

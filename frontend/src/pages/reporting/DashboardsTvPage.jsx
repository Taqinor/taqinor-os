import { useEffect, useMemo, useState } from 'react'
import { Tv } from 'lucide-react'
import coreApi from '../../api/coreApi'
import { Spinner } from '../../ui'

/* ============================================================================
   XPLT10 — Kiosque TV (`/dashboards-tv`) : rotation plein écran des dashboards
   éligibles (`GET core/dashboards-tv/` — société + partagés internes de
   l'utilisateur). Page AUTONOME, sans layout ERP (pas de Sidebar/Header) :
   pensée pour un écran dédié affiché en continu. Rotation + rafraîchissement
   pilotés CÔTÉ ÉCRAN (le backend ne fournit que la liste + le layout déjà
   agrégé — jamais de prix d'achat/marge/liste nominative).
   ========================================================================== */

const ROTATE_MS = 15000
const REFRESH_MS = 60000

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
      <pre className="flex-1 overflow-auto rounded-md border border-border bg-card p-4 text-xs">
        {JSON.stringify(current.layout, null, 2)}
      </pre>
    </div>
  )
}

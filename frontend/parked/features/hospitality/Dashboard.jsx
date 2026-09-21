import { useEffect, useState } from 'react'
import { Stat, EmptyState, Spinner } from '../../ui'
import { formatMAD } from '../../lib/format'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT11 — Tableau de bord RevPAR/ADR/TO (landing du module hôtellerie).
   ----------------------------------------------------------------------------
   4 KPI calculés serveur (selectors.dashboard_hotellerie) : ADR, RevPAR, taux
   d'occupation, taux de no-show — annulations/no-show exclus du dénominateur
   revenus. Fenêtre par défaut = 30 derniers jours (backend).
   ========================================================================== */

const pct = (value) => `${(Number(value) * 100).toFixed(1)}%`

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    hospitalityApi
      .tableauBord()
      .then((res) => setData(res.data))
      .catch(() => setError('Tableau de bord indisponible.'))
  }, [])

  if (error) {
    return <EmptyState title="Tableau de bord indisponible" description={error} />
  }
  if (!data) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement du tableau de bord…
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <Stat label="ADR (prix moyen/nuit)" value={formatMAD(data.adr)} />
      <Stat label="RevPAR" value={formatMAD(data.revpar)} />
      <Stat label="Taux d'occupation" value={pct(data.taux_occupation)} />
      <Stat label="Taux de no-show" value={pct(data.no_show_rate)} />
    </div>
  )
}

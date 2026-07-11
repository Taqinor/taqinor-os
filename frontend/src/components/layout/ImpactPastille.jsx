// VX157 — Pastille d'impact discrète en pied de Sidebar : la production +
// CO₂ évité cumulés du parc (déjà servis par monitoringApi.getCo2Fleet(),
// jusqu'ici enterrés dans un sous-écran monitoring), au repos partout dans
// l'app. Scoping company = SERVEUR (le endpoint co2-fleet filtre déjà par
// request.user.company) ; ce composant ne fait qu'afficher ce qui revient.
// MASQUÉE (rend null) tant que la donnée n'est pas là ou si le parc est vide
// — jamais un « 0 » inventé.
import { useEffect, useState } from 'react'
import monitoringApi from '../../api/monitoringApi'
import { formatNumber } from '../../lib/format'
import { METRIC_ICONS } from '../../ui/metricIcons'

export default function ImpactPastille({ collapsed }) {
  const [data, setData] = useState(null) // null = pas encore chargé / indisponible
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    monitoringApi.getCo2Fleet()
      .then((r) => { if (alive) setData(r.data ?? null) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [])

  if (error || data == null) return null

  const productionKwh = Number(data.total_production_kwh) || 0
  const co2Tonnes = Number(data.total_co2_tonnes) || 0
  // Aucune donnée réelle sur le parc → rien à afficher (pas de "0 MWh").
  if (productionKwh <= 0 && co2Tonnes <= 0) return null

  const mwh = productionKwh / 1000
  const label = `${formatNumber(mwh, { decimals: 1 })} MWh · ${formatNumber(co2Tonnes, { decimals: 1 })} t CO₂ évitées`
  const Icon = METRIC_ICONS.co2

  return (
    <div
      className="sidebar-impact"
      title={collapsed ? label : undefined}
      aria-label={`Impact cumulé du parc : ${label}`}
    >
      <Icon className="sidebar-impact-icon" size={14} strokeWidth={1.75} aria-hidden="true" />
      {!collapsed && <span className="sidebar-impact-label">{label}</span>}
    </div>
  )
}

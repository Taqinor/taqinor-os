import { NavLink } from 'react-router-dom'
import { cn } from '../../lib/cn'

/* WR6 — Navigation locale de la suite Production / O&M. Le menu latéral ne
   porte qu'une entrée « Production » : ce bandeau relie entre eux les écrans
   de la suite (relevés, vue parc, analytique, garanties…). Additif : aucune
   entrée de Sidebar n'est modifiée. */
const MONITORING_LINKS = [
  { to: '/production', label: 'Relevés', end: true },
  { to: '/production/parc', label: 'Vue parc' },
  { to: '/production/analytique', label: 'Analytique O&M' },
  { to: '/production/garanties', label: 'Garanties' },
  { to: '/production/co2', label: 'CO₂' },
  { to: '/production/nettoyages', label: 'Nettoyages' },
  { to: '/production/rapports', label: 'Rapports O&M' },
  { to: '/production/portail-client', label: 'Portail client' },
]

export default function MonitoringNav() {
  return (
    <nav
      aria-label="Sections production"
      className="mb-4 flex flex-wrap items-center gap-0.5 rounded-lg border border-border bg-muted p-0.5"
      data-testid="monitoring-nav"
    >
      {MONITORING_LINKS.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.end}
          className={({ isActive }) => cn(
            'inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            isActive
              ? 'bg-card text-foreground shadow-ui-xs'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  )
}

// Sélecteur de vue façon Odoo : groupe de 5 boutons-icônes joints (FG37 + Carte).
const ICON = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true }

const KanbanIcon = () => (
  <svg {...ICON}>
    <rect x="3" y="3" width="5" height="18" rx="1" />
    <rect x="10" y="3" width="5" height="12" rx="1" />
    <rect x="17" y="3" width="4" height="8" rx="1" />
  </svg>
)

const ListIcon = () => (
  <svg {...ICON}>
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="20" y2="12" />
    <line x1="4" y1="18" x2="20" y2="18" />
  </svg>
)

const CalendarIcon = () => (
  <svg {...ICON}>
    <rect x="3" y="4" width="18" height="17" rx="2" />
    <line x1="3" y1="9" x2="21" y2="9" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="16" y1="2" x2="16" y2="6" />
  </svg>
)

const ChartIcon = () => (
  <svg {...ICON}>
    <line x1="4" y1="20" x2="20" y2="20" />
    <rect x="6" y="11" width="3" height="9" rx="0.5" />
    <rect x="11" y="6" width="3" height="14" rx="0.5" />
    <rect x="16" y="14" width="3" height="6" rx="0.5" />
  </svg>
)

// FG37 — Icône carte (épingle de localisation).
const MapIcon = () => (
  <svg {...ICON}>
    <path d="M12 2a7 7 0 0 1 7 7c0 5.25-7 13-7 13S5 14.25 5 9a7 7 0 0 1 7-7z" />
    <circle cx="12" cy="9" r="2.5" />
  </svg>
)

// XSAL15 — Icône prévision (calendrier + tendance), la forecast view d'Odoo.
const ForecastIcon = () => (
  <svg {...ICON}>
    <rect x="3" y="4" width="18" height="17" rx="2" />
    <line x1="3" y1="9" x2="21" y2="9" />
    <path d="M7 17l3-4 3 2 4-6" />
  </svg>
)

const VIEWS = [
  { key: 'kanban', label: 'Vue kanban', Icon: KanbanIcon },
  { key: 'liste', label: 'Vue liste', Icon: ListIcon },
  { key: 'calendrier', label: 'Vue calendrier', Icon: CalendarIcon },
  { key: 'graphique', label: 'Vue graphique', Icon: ChartIcon },
  { key: 'carte', label: 'Vue carte', Icon: MapIcon },  // FG37
  { key: 'prevision', label: 'Vue prévision', Icon: ForecastIcon },  // XSAL15
]

export default function ViewSwitcher({ view, setView }) {
  return (
    <div className="vs-group" role="group" aria-label="Changer de vue">
      {VIEWS.map((v) => {
        const { key, label, Icon } = v
        return (
        <button
          key={key}
          type="button"
          className={`vs-btn${view === key ? ' vs-btn-active' : ''}`}
          aria-label={label}
          aria-pressed={view === key}
          title={label}
          onClick={() => setView(key)}
        >
          <Icon />
        </button>
        )
      })}
    </div>
  )
}

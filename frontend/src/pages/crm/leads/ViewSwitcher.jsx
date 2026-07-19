// Sélecteur de vue façon Odoo — LB32 : rebâti sur `ui/Segmented` (radiogroup
// + roving tabindex + flèches/Home/End au clavier, recon-05 a11y #2) au lieu
// du role=group main-roulé + SVG bruts d'origine. Icônes lucide alignées
// sur celles que CHAQUE vue importe déjà pour son propre empty state
// (KanbanView→LayoutGrid, ListView→List, ChartsView→BarChart3, CarteView→Map,
// ForecastView→CalendarClock) : la même icône représente la vue partout dans
// l'écran. Les 6 noms accessibles restent EXACTEMENT ceux pinnés par le
// blueprint ('Vue kanban'/'Vue liste'/… — e2e helpers.js#setLeadsView) mais
// deviennent visuellement masqués (`.sr-only`, idiome déjà utilisé par
// ui/Form.jsx, ui/Select.jsx, ui/SolarLoader.jsx) : `Segmented` rend
// toujours `label` comme contenu visible, donc c'est le seul moyen de
// garder à la fois le nom accessible pinné ET la présentation icône-seule
// d'origine (compact — le switcher partage sa rangée avec Nouveau/Express/⋯).
import { LayoutGrid, List, Calendar, BarChart3, Map, CalendarClock } from 'lucide-react'
import { Segmented } from '../../../ui'

const VIEWS = [
  { value: 'kanban', label: 'Vue kanban', icon: LayoutGrid },
  { value: 'liste', label: 'Vue liste', icon: List },
  { value: 'calendrier', label: 'Vue calendrier', icon: Calendar },
  { value: 'graphique', label: 'Vue graphique', icon: BarChart3 },
  { value: 'carte', label: 'Vue carte', icon: Map },  // FG37
  { value: 'prevision', label: 'Vue prévision', icon: CalendarClock },  // XSAL15
]

export default function ViewSwitcher({ view, setView }) {
  return (
    <Segmented
      className="vs-group"
      size="sm"
      aria-label="Changer de vue"
      value={view}
      onChange={setView}
      options={VIEWS.map(({ value, label, icon }) => ({
        value,
        icon,
        label: <span className="sr-only">{label}</span>,
      }))}
    />
  )
}

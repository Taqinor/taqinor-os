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

// LB47 — exportée : le menu ⋯ mobile de LeadsPage rend ces MÊMES vues en
// items (jamais une 2e liste déclarée ailleurs).
// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (même motif que STAGE_PROBABILITY, KanbanView.jsx)
export const VIEWS = [
  { value: 'kanban', label: 'Vue kanban', icon: LayoutGrid },
  // APX5 — `hint` : complément d'infobulle OPTIONNEL. Le nom accessible
  // (`label`) reste EXACTEMENT celui pinné par le blueprint (e2e
  // helpers.js#setLeadsView) ; l'infobulle en est le PRÉFIXE, jamais un second
  // libellé indépendant — l'invariant LB40 « les deux ne peuvent pas
  // diverger » est préservé par construction (`${label} — ${hint}`).
  { value: 'liste', label: 'Vue liste', icon: List, hint: 'la vue la plus dense' },
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
      // LB40 — `title` par radio : depuis LB32 les 6 libellés sont `.sr-only`
      // (présentation icône-seule), donc le nom accessible existait toujours
      // pour le clavier/lecteur d'écran mais RIEN ne s'affichait au survol
      // souris — six icônes muettes. L'infobulle DÉRIVE du nom accessible
      // (jamais un second libellé indépendant qui pourrait diverger) : elle
      // vaut `label`, éventuellement suivi du `hint` de la vue (APX5).
      options={VIEWS.map(({ value, label, icon, hint }) => ({
        value,
        icon,
        title: hint ? `${label} — ${hint}` : label,
        label: <span className="sr-only">{label}</span>,
      }))}
    />
  )
}

import { BarChart3 } from 'lucide-react'
import { EmptyState } from '../EmptyState'

/* K147 — État vide « en contexte » d'un graphique : même langage que les autres
   états vides de l'app, sans bordure (il vit déjà dans une carte). */
export function ChartEmpty({ icon = BarChart3, title = 'Aucune donnée', description, className }) {
  return (
    <EmptyState
      icon={icon}
      title={title}
      description={description}
      className={`border-0 py-8 ${className ?? ''}`.trim()}
    />
  )
}

export default ChartEmpty

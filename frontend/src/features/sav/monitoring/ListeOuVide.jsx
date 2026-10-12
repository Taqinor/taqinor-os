// Squelette pendant le chargement, état vide si aucune ligne, sinon `children`.
import { EmptyState, Skeleton } from '../../../ui'

export default function ListeOuVide({ loading, rows, icon, title, description, children }) {
  if (loading) return <Skeleton className="h-9 w-full" />
  if (rows.length === 0) {
    return <EmptyState icon={icon} title={title} description={description} />
  }
  return children
}

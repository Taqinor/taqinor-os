import { Spinner, EmptyState } from '../../ui'

/* Enchaînement chargement → erreur → vide → contenu PARTAGÉ des listes
   Chantiers. `children` vaut `false` quand la liste est vide
   (`rows.length > 0 && …`) : on teste la valeur, pas seulement null/undefined,
   sinon l'état vide ne s'afficherait jamais. */
export default function ListeEtat({ loading, error, empty, icon, children }) {
  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  if (!children) return <EmptyState icon={icon} title={empty} className="py-6" />
  return children
}

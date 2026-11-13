import { Spinner, EmptyState, Button } from '../../ui'

/* Enchaînement chargement → erreur → vide → contenu PARTAGÉ des listes
   Chantiers. `children` vaut `false` quand la liste est vide
   (`rows.length > 0 && …`) : on teste la valeur, pas seulement null/undefined,
   sinon l'état vide ne s'afficherait jamais. */
// AERR93 — chargement et erreur plein cadre SEULEMENT sans contenu : une relecture
// ratée garde la liste affichée, avec un avis « pas à jour » (+ « Réessayer »).
export default function ListeEtat({ loading, error, empty, icon, onRetry, children }) {
  const reessayer = onRetry && <Button size="sm" variant="outline" onClick={() => onRetry()}>Réessayer</Button>
  if (loading && !children) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error && !children) return <EmptyState title="Impossible de charger" description={error} action={reessayer} className="py-6" />
  if (!children) return <EmptyState icon={icon} title={empty} className="py-6" />
  if (!error) return children
  return (<>
    <p role="alert" className="flex flex-wrap items-center gap-2 py-2 text-sm text-destructive">
      Liste pas à jour : {error} {reessayer}
    </p>
    {children}
  </>)
}

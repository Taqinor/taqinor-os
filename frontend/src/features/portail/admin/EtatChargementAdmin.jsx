// ENF28 (ENF19) — état de chargement partagé des écrans d'administration du
// portail : squelette pendant le chargement, état d'erreur avec « Réessayer »
// en cas d'échec, sinon le contenu. Un seul exemplaire au lieu de six copies.
import { Button, Card, EmptyState, Skeleton } from '../../../ui'

export default function EtatChargementAdmin({ loading, loadError, erreur, onRetry, children }) {
  if (loading) {
    return (
      <Card className="space-y-2 p-4">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
      </Card>
    )
  }
  if (loadError) {
    return (
      <EmptyState title="Chargement impossible" description={erreur}
                  action={<Button size="sm" variant="outline" onClick={onRetry}>Réessayer</Button>} />
    )
  }
  return children
}

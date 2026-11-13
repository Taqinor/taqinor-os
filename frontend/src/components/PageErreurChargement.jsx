// Écran d'erreur pleine page d'une liste dont le chargement INITIAL a échoué
// (rien à l'écran) — partagé par les listes chantiers et interventions.
import { Button, EmptyState } from '../ui'

export default function PageErreurChargement({ title, error, onRetry }) {
  return (
    <div className="page lp-page">
      <EmptyState
        title={title}
        description={typeof error === 'string' ? error : 'Une erreur est survenue. Réessayez.'}
        action={<Button size="sm" onClick={onRetry}>Réessayer</Button>}
        className="my-8 border-destructive/40"
      />
    </div>
  )
}

// ENF28 (ENF19) — attente et erreur partagées des tableaux de bord des
// portails fournisseur et partenaire (voir useTableauDeBordExterne.js).
import { EmptyState, Spinner } from '../../ui'

/** Attente ou erreur du tableau de bord ; `null` quand le résumé est prêt. */
export default function EtatTableauDeBordExterne({ resume, loading, erreur }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de votre tableau de bord…
      </div>
    )
  }
  if (erreur || !resume) {
    return (
      <EmptyState
        title="Tableau de bord indisponible"
        description="Vos données n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }
  return null
}

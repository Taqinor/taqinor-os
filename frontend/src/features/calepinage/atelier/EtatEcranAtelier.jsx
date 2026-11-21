import { SkeletonCard, SkeletonText } from '../../../ui'
import RetourAtelier from './RetourAtelier'

/* État d'attente d'un écran de l'atelier (dossiers réglementaires, schéma
   unifilaire, pertes, production…) : lien de retour à l'atelier, puis le
   squelette de la forme du contenu (chargement, `role="status"`) ou le message
   d'erreur (`testIdErreur`). Le chargement l'emporte sur l'erreur. Un seul
   endroit pour les quatre écrans. */
export default function EtatEcranAtelier({ id, loading, error, testIdErreur }) {
  return (
    <>
      <RetourAtelier calepinageId={id} />
      {loading
        ? (
          <div role="status" aria-label="Chargement…" className="mt-3 space-y-3">
            <SkeletonCard />
            <SkeletonText lines={2} />
          </div>
        )
        : <p className="text-sm text-destructive" data-testid={testIdErreur}>{error}</p>}
    </>
  )
}

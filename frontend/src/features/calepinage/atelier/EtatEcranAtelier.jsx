import { Skeleton, SkeletonCard, SkeletonText } from '../../../ui'
import RetourAtelier from './RetourAtelier'

/* État d'attente d'un écran de l'atelier (dossiers réglementaires, schéma
   unifilaire, pertes, production…) : lien de retour à l'atelier, puis le
   squelette de la forme du contenu (chargement, `role="status"`) ou le message
   d'erreur (`testIdErreur`). Le chargement l'emporte sur l'erreur. Un seul
   endroit pour les quatre écrans.
   ACAL1822 — `forme="resultats"` : le squelette pose les DEUX blocs de l'écran Résultats (la carte héros de 540 px,
   puis « Pour un résultat complet », mêmes boîtes que 54-etape-resultats.css) et rien au-dessus : au passage du
   squelette au contenu, la carte bleu nuit ne bouge pas. Sans `forme`, le squelette d'avant (autres écrans). */
function SqueletteResultats() {
  return (
    <div role="status" aria-label="Chargement…" className="cal-res-squelette" data-testid="cal-res-squelette">
      <Skeleton className="cal-res-squelette-bloc cal-res-squelette-heros" />
      <Skeleton className="cal-res-squelette-bloc" />
    </div>
  )
}

export default function EtatEcranAtelier({ id, loading, error, testIdErreur, forme = null }) {
  if (loading && forme === 'resultats') return <SqueletteResultats />
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

import { Skeleton, SkeletonCard, SkeletonText } from '../../../ui'
import RetourAtelier from './RetourAtelier'
import { MESSAGE_CALCUL_LENT } from '../delaiReseau'

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

/* ACAL1905 — `onRetry` : un bouton « Réessayer » sous l'erreur. Un délai dépassé (`error === MESSAGE_CALCUL_LENT`, posé par
   `messageResultatIndisponible`) se dit « Calcul en cours… » en information — pas en erreur : la connexion n'est pas coupée. */
export default function EtatEcranAtelier({ id, loading, error, testIdErreur, forme = null, onRetry = null }) {
  if (loading && forme === 'resultats') return <SqueletteResultats />
  const lent = !loading && error === MESSAGE_CALCUL_LENT
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
        : (
          <div className="mt-3 flex flex-col items-start gap-3">
            {lent
              ? <p role="status" className="text-sm text-muted-foreground" data-testid="cal-calcul-lent">{error}</p>
              : <p className="text-sm text-destructive" data-testid={testIdErreur}>{error}</p>}
            {onRetry && (
              <button type="button" onClick={onRetry} data-testid="cal-reessayer-lecture"
                className="min-h-11 rounded-md border border-border bg-card px-4 text-sm font-semibold text-foreground">
                Réessayer
              </button>
            )}
          </div>
        )}
    </>
  )
}

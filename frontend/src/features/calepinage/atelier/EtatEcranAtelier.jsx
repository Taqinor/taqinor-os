import { Spinner } from '../../../ui'
import RetourAtelier from './RetourAtelier'

/* État d'attente d'un écran de l'atelier (dossiers réglementaires, schéma
   unifilaire, pertes, production…) : lien de retour à l'atelier, puis le
   spinner (chargement) ou le message d'erreur (`testIdErreur`). Le chargement
   l'emporte sur l'erreur. Un seul endroit pour les quatre écrans. */
export default function EtatEcranAtelier({ id, loading, error, testIdErreur }) {
  return (
    <>
      <RetourAtelier calepinageId={id} />
      {loading
        ? <Spinner />
        : <p className="text-sm text-destructive" data-testid={testIdErreur}>{error}</p>}
    </>
  )
}

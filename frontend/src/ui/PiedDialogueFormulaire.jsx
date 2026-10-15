import { Button } from './Button'
import { DialogFooter } from './Dialog'
import { AlerteErreur } from './AlertesServeur'

/* Pied de dialogue de formulaire : bandeau d'erreur serveur, puis Annuler /
   valider (libellé d'envoi pendant `busy`). Un seul endroit — jamais recopié
   modale par modale. Par défaut le bouton valider est un `submit` et Annuler
   est désactivé pendant l'envoi ; `onSubmit` fait du bouton valider un
   `button` à clic, `annulerActifPendantEnvoi` laisse Annuler cliquable. */
export default function PiedDialogueFormulaire({
  error, busy, onCancel, onSubmit, libelle, libelleEnCours,
  annulerActifPendantEnvoi = false,
}) {
  return (
    <>
      <AlerteErreur error={error} />
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onCancel}
                disabled={annulerActifPendantEnvoi ? undefined : busy}>
          Annuler
        </Button>
        <Button type={onSubmit ? 'button' : 'submit'} loading={busy} onClick={onSubmit}>
          {busy ? libelleEnCours : libelle}
        </Button>
      </DialogFooter>
    </>
  )
}

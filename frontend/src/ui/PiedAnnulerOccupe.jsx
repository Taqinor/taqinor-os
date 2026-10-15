import { Button } from './Button'
import { DialogFooter } from './Dialog'

/* Pied de dialogue d'action : « Annuler » (ou `libelle`, ex. « Retour »),
   désactivé pendant l'envoi (`busy`), puis le bouton d'action en enfant.
   Un seul endroit pour les dialogues Ateliers / Parc installé. */
export default function PiedAnnulerOccupe({ onClose, busy, libelle = 'Annuler', children }) {
  return (
    <DialogFooter>
      <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
        {libelle}
      </Button>
      {children}
    </DialogFooter>
  )
}

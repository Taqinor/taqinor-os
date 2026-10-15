import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui'
import PiedDialogueFormulaire from '../ui/PiedDialogueFormulaire'

/* Modale de création rapide (« + Nouveau client », « + Nouveau ticket »…) :
   en-tête, formulaire sans validation navigateur, champs en enfants, puis
   erreur serveur + Annuler / valider. Un seul endroit — jamais recopié modale
   par modale. `onFermer` est appelé à la fermeture ET sur Annuler. */
export default function ModaleCreationRapide({
  open, onFermer, titre, description, onSubmit, error, busy, libelle, libelleEnCours, children,
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onFermer() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{titre}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="grid gap-4">
          {children}
          <PiedDialogueFormulaire error={error} busy={busy} onCancel={onFermer}
                                  libelle={libelle} libelleEnCours={libelleEnCours} />
        </form>
      </DialogContent>
    </Dialog>
  )
}

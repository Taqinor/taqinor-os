// QP2 — LE DIALOGUE DE RENOMMAGE, sorti de DevisGenerator.jsx (C20 : le fichier-mur ne
// grossit pas) : deux choix explicites lorsqu'une ligne est renommée à l'écart du nom du
// produit lié (rôle autorisé). T4-X4-012 — la grille ne s'élargit plus au contenu et le
// texte comme les deux boutons passent à la ligne : à 1 440 px, comme sur tablette et sur
// téléphone, le nom du produit à créer se lit en entier.
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../../ui'
import { AlerteErreur } from '../../../ui/AlertesServeur'

const BOUTON_QUI_PASSE_A_LA_LIGNE = 'h-auto min-h-[var(--control-h)] whitespace-normal py-2 text-center'

export default function DialogueRenommage({
  renameDialog, setRenameDialog, renameBusy, renameError, renameHereOnly, renameAsNewProduct,
}) {
  return (
    <Dialog open={!!renameDialog} onOpenChange={(o) => { if (!o) setRenameDialog(null) }}>
      <DialogContent className="grid-cols-[minmax(0,1fr)] break-words sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Désignation modifiée</DialogTitle>
          <DialogDescription>
            Vous avez renommé cette ligne
            {renameDialog ? ` « ${renameDialog.nouveauNom} »` : ''} — elle diffère du
            produit du stock{renameDialog ? ` « ${renameDialog.ancienNom} »` : ''}.
            Que souhaitez-vous faire ?
          </DialogDescription>
        </DialogHeader>
        <AlerteErreur error={renameError} />
        <DialogFooter className="flex-col gap-2 sm:flex-col sm:items-stretch">
          <Button type="button" variant="outline" className={BOUTON_QUI_PASSE_A_LA_LIGNE} onClick={renameHereOnly} disabled={renameBusy}>
            Renommer sur ce devis seulement
          </Button>
          <Button type="button" className={BOUTON_QUI_PASSE_A_LA_LIGNE} onClick={renameAsNewProduct} loading={renameBusy}>
            {renameBusy
              ? 'Création…'
              : `Créer un nouveau produit « ${renameDialog?.nouveauNom ?? ''} » dans le stock`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

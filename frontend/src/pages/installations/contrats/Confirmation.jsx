// Petite confirmation de l'onglet « Contrats », bâtie sur l'AlertDialog de
// l'application et RENDUE DANS l'arbre React de l'écran qui la demande : pour
// Radix, un clic dans cette boîte reste « à l'intérieur » de l'éditeur (et du
// tiroir du chantier derrière lui). La confirmation globale de l'application
// vit à la racine, hors de ces couches : un clic dessus fermait l'éditeur, puis
// le tiroir entier (F10) — d'où cette boîte à nous.
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../../ui'

export default function Confirmation({
  open, titre, description, enfants = null,
  libelleRester = 'Annuler', libelleConfirmer, destructif = true,
  onRester, onConfirmer,
}) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) onRester?.() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{titre}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        {enfants}
        <AlertDialogFooter>
          <AlertDialogCancel className="contrats-acte__bouton" onClick={onRester}>
            {libelleRester}
          </AlertDialogCancel>
          <AlertDialogAction
            className="contrats-acte__bouton"
            variant={destructif ? 'destructive' : 'default'}
            onClick={onConfirmer}
          >
            {libelleConfirmer}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

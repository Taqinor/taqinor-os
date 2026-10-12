import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'

/* Coquille commune des dialogues de création GED (coffres, planifications,
   routages, tags, checklist, règles, rétention…) : titre, colonne de champs,
   pied « Annuler / Créer ». Un seul endroit — jamais recopié page par page. */
export default function DialogueFormulaire({
  titre, onClose, submit, saving, libelle = 'Créer', libelleEnCours = 'Création…', children,
}) {
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>{titre}</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          {children}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button onClick={submit} disabled={saving}>{saving ? libelleEnCours : libelle}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

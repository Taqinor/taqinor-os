import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Form,
} from '../../ui'
import { AlerteErreurStock } from './BandeauxListeStock'

/* Dialogue de formulaire des écrans Stock : en-tête (titre + description),
   corps du formulaire, bandeau d'erreur serveur et pied Annuler / valider.
   Un seul endroit — jamais recopié écran par écran. `libelleEnCours={null}`
   garde le libellé fixe pendant l'envoi. */
export default function DialogueFormulaireStock({
  title, description, onClose, onSubmit, error, saving,
  libelle = 'Enregistrer', libelleEnCours = 'Enregistrement…', size = 'max-w-lg',
  apres = null, children,
}) {
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className={size}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <Form onSubmit={onSubmit} className="gap-4">
          {children}
          <AlerteErreurStock error={error} enForm />
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving && libelleEnCours ? libelleEnCours : libelle}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
      {apres}
    </Dialog>
  )
}

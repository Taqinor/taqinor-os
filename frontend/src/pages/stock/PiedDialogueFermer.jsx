import { Button, DialogFooter } from '../../ui'

/* Pied de dialogue de consultation : un seul bouton « Fermer ». */
export default function PiedDialogueFermer({ onClose }) {
  return (
    <DialogFooter>
      <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
    </DialogFooter>
  )
}

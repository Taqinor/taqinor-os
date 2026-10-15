import { Button } from '../../ui'

/* Pied « Annuler / Créer » PARTAGÉ des dialogues de création Chantiers. */
export default function PiedCreation({ busy, onClose, onCreate }) {
  return (
    <div className="modal-footer">
      <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
      <Button type="button" loading={busy} disabled={busy} onClick={onCreate}>
        {busy ? 'Création…' : 'Créer'}
      </Button>
    </div>
  )
}

import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'

/* Coque des modales d'action sur un lead (Convertir en client, Appliquer un
   plan d'activité…) : ResponsiveDialog (Échap + focus-trap + bottom-sheet
   mobile) et en-tête titre + croix. Corps et pied en enfants. */
export default function ModaleLead({ titre, onClose, children }) {
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">{titre}</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      {children}
    </ResponsiveDialog>
  )
}

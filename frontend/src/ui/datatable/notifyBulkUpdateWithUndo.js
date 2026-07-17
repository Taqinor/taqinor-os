// NTUX6 — Colle le toast sonner (`../confirm`) au module pur `bulkEditUndo.js`
// (logique de conflit testée séparément, sans dépendance React/sonner).
// Appelé depuis `BulkEditDialog`'s `onDone(result)` (NTUX5) par l'écran
// consommateur : `notifyBulkUpdateWithUndo(result, { fieldLabel: 'statut', onUndo, getCurrentUpdatedAt })`.
import { toast } from '../confirm'
import { buildUndoAction, UNDO_WINDOW_MS } from './bulkEditUndo.js'

export function notifyBulkUpdateWithUndo(result, { fieldLabel, onUndo, getCurrentUpdatedAt } = {}) {
  const count = result?.updated?.length || 0
  if (count === 0) return
  const action = buildUndoAction(result, {
    onUndo,
    getCurrentUpdatedAt,
    onConflict: (conflicted) => {
      toast.error(
        conflicted.length === 1
          ? 'Annulation impossible — cette ligne a été modifiée entretemps.'
          : `Annulation impossible pour ${conflicted.length} ligne(s) — modifiées entretemps.`,
      )
    },
  })
  toast.success(
    `${count} ligne${count > 1 ? 's' : ''} ${fieldLabel ? `(${fieldLabel}) ` : ''}mise${count > 1 ? 's' : ''} à jour`,
    { duration: UNDO_WINDOW_MS, action },
  )
}

export default notifyBulkUpdateWithUndo

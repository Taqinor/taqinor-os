// NTUX6 — Undo pour l'édition en masse (NTUX5). Module PUR (aucun import
// React, testable côté node:test) : construit le toast de confirmation avec
// bouton « Annuler » (fenêtre de 10s, pattern déjà utilisé ailleurs — cf.
// pages/ui/DataTableDemo.jsx `toast.success(msg, { action: { label, onClick } })`).
//
// L'annulation RÉ-APPLIQUE les valeurs AVANT capturées dans `result.updated`
// (jamais une nouvelle lecture serveur) : c'est à l'appelant (`onUndo`) de les
// renvoyer via LE MÊME endpoint bulk-update de son app cible — ce module ne
// connaît aucune app métier, il orchestre seulement le toast + le garde-fou
// optimistic-lock.
export const UNDO_WINDOW_MS = 10000

/**
 * buildUndoAction(result, { getCurrentUpdatedAt, onUndo, onConflict }) →
 * `{ label, onClick }` prêt à passer à `toast.success(msg, { action, duration })`.
 *
 * `result.updated` = [{ id, before, after, updated_at? }] (retour de l'endpoint
 * bulk-update, NTUX5). `getCurrentUpdatedAt(id)` — optionnel — renvoie
 * l'`updated_at` ACTUEL d'une ligne (déjà en mémoire côté écran, aucun appel
 * réseau requis) ; s'il diffère de celui capturé au moment du bulk-update, la
 * ligne a été retouchée entretemps → conflit, l'annulation est refusée pour
 * CETTE ligne (jamais un refus total silencieux : `onConflict` reçoit le
 * détail pour un message clair).
 */
export function buildUndoAction(result, { onUndo, getCurrentUpdatedAt, onConflict } = {}) {
  const updated = result?.updated || []
  return {
    label: 'Annuler',
    onClick: () => {
      if (!updated.length) return
      const conflicted = []
      const clean = []
      for (const row of updated) {
        const current = typeof getCurrentUpdatedAt === 'function' ? getCurrentUpdatedAt(row.id) : undefined
        if (current != null && row.updated_at != null && String(current) !== String(row.updated_at)) {
          conflicted.push(row)
        } else {
          clean.push(row)
        }
      }
      if (conflicted.length > 0) onConflict?.(conflicted, clean)
      if (clean.length > 0) onUndo?.(clean)
    },
  }
}

/** isUndoWindowExpired — vrai si `elapsedMs` a dépassé la fenêtre d'annulation
 *  (utilitaire pur pour les tests / une éventuelle UI de compte à rebours ;
 *  sonner gère déjà l'expiration réelle du toast via `duration`). */
export function isUndoWindowExpired(elapsedMs) {
  return elapsedMs >= UNDO_WINDOW_MS
}

/* Réducteurs de chargement PARTAGÉS des slices métier (crm, stock, ventes) —
   VX165 : `pending` incrémente le compteur PARTAGÉ `pendingCount` ; `settleLoading`
   (appelé par CHAQUE fulfilled/rejected sœur) le décrémente et redérive
   `loading` — le premier thunk résolu n'éteint plus le spinner pendant que ses
   sœurs chargent encore. `rejected` pose l'erreur du payload. */
export const pending = (state) => {
  state.pendingCount = (state.pendingCount || 0) + 1
  state.loading = true
  state.error = null
}

export const settleLoading = (state) => {
  state.pendingCount = Math.max(0, (state.pendingCount || 0) - 1)
  state.loading = state.pendingCount > 0
}

export const rejected = (state, action) => {
  settleLoading(state)
  state.error = action.payload
}

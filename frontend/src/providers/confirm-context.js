import { createContext, useContext } from 'react'

// L54 — Contexte de confirmation. La valeur (fonction `confirm`) est fournie
// par <ConfirmProvider>. `useConfirm()` renvoie une fonction qui ouvre une
// boîte de dialogue de confirmation et résout une promesse booléenne.
export const ConfirmContext = createContext(null)

/**
 * useConfirm — renvoie `confirm(options) => Promise<boolean>`.
 *
 *   const confirm = useConfirm()
 *   const ok = await confirm({
 *     title: 'Supprimer ce devis ?',
 *     description: 'Cette action est irréversible.',
 *     confirmLabel: 'Supprimer',
 *     destructive: true,
 *   })
 *   if (ok) { … }
 *
 * Hors provider, renvoie un repli sûr (fenêtre `window.confirm` native) afin de
 * ne jamais planter le rendu si un appelant l'utilise trop tôt.
 */
export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (ctx) return ctx
  return (opts = {}) => {
    if (typeof window !== 'undefined' && typeof window.confirm === 'function') {
      return Promise.resolve(window.confirm(opts.description || opts.title || 'Confirmer ?'))
    }
    return Promise.resolve(true)
  }
}

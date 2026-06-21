// L152 — Helpers « confirmation + toast sur mutation ».
//
// But : donner aux pages (Groupe J et au-delà) UN seul import pour remplacer les
// `window.confirm(...)` / `alert(...)` natifs par la confirmation Radix maison et
// les toasts sonner thémés — sans réimplémenter ni remonter la moindre primitive.
// Ce module ENVELOPPE l'infrastructure déjà montée à la racine :
//   • <ConfirmProvider> (providers/ConfirmProvider.jsx) + useConfirm()
//   • <Toaster> (ui/Toaster.jsx) + toast (sonner)
// Il ne monte JAMAIS un second provider ni un second Toaster.
//
// Usage type dans une mutation :
//
//   import { useConfirmDialog, toast, toastPromise } from '../ui/confirm'
//
//   function Ligne({ devis }) {
//     const { confirmDelete } = useConfirmDialog()
//     async function onDelete() {
//       const ok = await confirmDelete({
//         title: 'Supprimer ce devis ?',
//         description: `Le devis ${devis.reference} sera définitivement supprimé.`,
//       })
//       if (!ok) return
//       // toastPromise affiche chargement → succès / erreur automatiquement.
//       await toastPromise(api.delete(devis.id), {
//         loading: 'Suppression…',
//         success: 'Devis supprimé.',
//         error: 'Suppression impossible.',
//       })
//     }
//     // … toast.success('Enregistré.') / toast.error('Échec.') pour les cas simples.
//   }

import { useCallback, useMemo } from 'react'
import { useConfirm } from '../providers/confirm-context'
import { toast } from './Toaster'

// Normalise l'argument : un appelant peut passer une simple chaîne (utilisée
// comme titre) plutôt qu'un objet d'options complet.
function normalize(arg) {
  if (typeof arg === 'string') return { title: arg }
  return arg || {}
}

/**
 * useConfirmDialog — hook ergonomique bâti sur `useConfirm()`.
 *
 * Renvoie deux fonctions, chacune `(options | titre) => Promise<boolean>` :
 *   • confirm(opts)       — confirmation générique (par défaut destructive,
 *                           comme le provider sous-jacent).
 *   • confirmDelete(opts) — préremplit les libellés d'une suppression
 *                           (« Supprimer » / « Annuler », destructive=true) ;
 *                           tout champ passé écrase ces défauts.
 *
 * @returns {{ confirm: (a?: object|string) => Promise<boolean>,
 *             confirmDelete: (a?: object|string) => Promise<boolean> }}
 */
export function useConfirmDialog() {
  const confirmFn = useConfirm()

  const confirm = useCallback(
    (arg) => confirmFn(normalize(arg)),
    [confirmFn],
  )

  const confirmDelete = useCallback(
    (arg) =>
      confirmFn({
        title: 'Supprimer cet élément ?',
        confirmLabel: 'Supprimer',
        cancelLabel: 'Annuler',
        destructive: true,
        ...normalize(arg),
      }),
    [confirmFn],
  )

  return useMemo(() => ({ confirm, confirmDelete }), [confirm, confirmDelete])
}

// Messages FR par défaut pour une opération longue (mutation réseau).
const PROMISE_DEFAULTS = {
  loading: 'Enregistrement…',
  success: 'Opération réussie.',
  error: 'Une erreur est survenue.',
}

/**
 * toastPromise — convention pour les opérations longues (mutations).
 * Affiche un toast « chargement » qui bascule en succès / erreur selon l'issue
 * de la promesse, puis RENVOIE la promesse d'origine pour permettre `await` /
 * chaînage par l'appelant.
 *
 * @template T
 * @param {Promise<T>} promise           promesse de la mutation
 * @param {{loading?: string|((...a:any)=>string),
 *          success?: string|((...a:any)=>string),
 *          error?: string|((...a:any)=>string)}} [messages]  libellés (FR par défaut)
 * @returns {Promise<T>} la promesse d'origine (inchangée)
 */
export function toastPromise(promise, messages = {}) {
  toast.promise(promise, { ...PROMISE_DEFAULTS, ...messages })
  return promise
}

// Réexport de `toast` (toast.success / toast.error / toast.message / toast.promise…)
// pour que les pages aient un import unique : `import { toast } from '../ui/confirm'`.
export { toast }

// L53 — Helpers de feedback asynchrone (toasts), bâtis sur sonner (réexporté
// depuis `@/ui`). Centralise des messages FR cohérents pour
// enregistrement / suppression / envoi WhatsApp / génération PDF, avec un
// motif « Annuler » (undo) là où c'est sans danger.
//
// Code en anglais, textes utilisateur en français. Aucun import React ici :
// ces helpers sont appelables depuis n'importe où (handlers, thunks, axios).
import { toast } from '../ui/Toaster'
// VX203 — l'extraction du message d'erreur est désormais PROMUE dans
// `lib/apiError.js` (contrat d'erreur unique, `{message, fieldErrors}`) ;
// `errorMessageFrom` ci-dessous ne fait plus que déléguer, pour ne rien
// casser des appelants existants (signature/nom inchangés).
import { apiErrorMessage } from './apiError'

// VX196 — sonner ne rend qu'UNE région aria-live="polite" pour tous les
// toasts : une erreur bloquante n'interrompt jamais le lecteur d'écran
// (sonner ne propose aucune option par-toast pour changer sa politesse).
// On relaie donc chaque erreur vers une région assertive dédiée, montée par
// `<Toaster>` (ui/Toaster.jsx) — mini pub-sub, aucune dépendance ajoutée.
const assertiveListeners = new Set()

/** S'abonne aux annonces assertives (erreurs). Renvoie la fonction de désabonnement. */
export function subscribeAssertiveAnnouncer(listener) {
  assertiveListeners.add(listener)
  return () => assertiveListeners.delete(listener)
}

function announceAssertive(message) {
  if (!message) return
  for (const listener of assertiveListeners) listener(String(message))
}

/** Toast de succès. `message` (FR) requis ; `description` optionnelle. */
export function toastSuccess(message, options = {}) {
  return toast.success(message, options)
}

/** Toast d'erreur — annoncé en `assertive` (interrompt), contrairement aux
 * toasts succès/info qui restent `polite`. */
export function toastError(message, options = {}) {
  announceAssertive(message)
  return toast.error(message, options)
}

/** Toast d'information neutre. */
export function toastInfo(message, options = {}) {
  return toast(message, options)
}

/**
 * toastPromise — lie un toast au cycle de vie d'une promesse : « … en cours »,
 * puis succès ou erreur. Renvoie la promesse d'origine (chaînable).
 *
 *   await toastPromise(api.save(...), {
 *     loading: 'Enregistrement…',
 *     success: 'Enregistré.',
 *     error: 'Échec de l’enregistrement.',
 *   })
 */
export function toastPromise(promise, messages = {}) {
  const {
    loading = 'Traitement…',
    success = 'Terminé.',
    error = 'Une erreur est survenue.',
  } = messages
  toast.promise(promise, { loading, success, error })
  return promise
}

/**
 * toastWithUndo — affiche un toast de succès offrant une action « Annuler ».
 * Le motif « safe undo » : l'effet réel est différé jusqu'à expiration du
 * toast ; si l'utilisateur clique « Annuler » avant, rien n'est commis.
 *
 *   toastWithUndo({
 *     message: '1 lead supprimé.',
 *     onCommit: () => api.delete(id),   // exécuté après le délai si non annulé
 *     onUndo:   () => restoreInUi(),    // restaure l'état optimiste si annulé
 *   })
 *
 * Si `onCommit` est omis (l'effet a déjà eu lieu), seul `onUndo` est appelé
 * au clic — utile quand le serveur a déjà été touché et qu'« Annuler » relance
 * une opération inverse.
 */
export function toastWithUndo({
  message,
  description,
  onUndo,
  onCommit,
  duration = 6000,
  undoLabel = 'Annuler',
} = {}) {
  let undone = false
  const id = toast.success(message, {
    description,
    duration,
    action: {
      label: undoLabel,
      onClick: () => {
        undone = true
        try { onUndo?.() } catch { /* l'undo ne doit jamais planter le toast */ }
      },
    },
  })
  if (typeof onCommit === 'function') {
    // Commit différé : laisse à l'utilisateur la fenêtre « Annuler ».
    setTimeout(() => {
      if (!undone) {
        try { onCommit() } catch { /* le commit gère ses propres erreurs */ }
      }
    }, duration)
  }
  return id
}

/** Petit utilitaire : extrait un message d'erreur FR lisible d'une erreur axios.
 *  VX203 — délègue à `apiError.js` (couvre en plus 429/500 HTML/timeout). */
export function errorMessageFrom(error, fallback = 'Une erreur est survenue.') {
  return apiErrorMessage(error, fallback)
}

export { toast }

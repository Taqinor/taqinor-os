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

/** Toast d'information neutre. `toast.info` (pas le `toast()` générique) pour
 * hériter du style/icône dédiés « info » posés dans Toaster.jsx (VX130). */
export function toastInfo(message, options = {}) {
  return toast.info(message, options)
}

/**
 * toastMilestone — VX155 : un cran au-dessus du succès plat pour les JALONS
 * clients (devis envoyé, facture payée…) — un signal visuellement distinct
 * d'un « ligne supprimée ». Icône soleil dédiée (surchargeable par l'appelant
 * — ex. `<TaqinorMark>` depuis un composant JSX) + `description` porte le
 * réf/client/montant du jalon. Reste un `toast.success` (mêmes garanties
 * a11y/polite) : ce n'est PAS une gamification de la routine (règle VX40),
 * seulement un jalon métier qui mérite mieux qu'un message plat.
 */
export function toastMilestone(message, options = {}) {
  const { icon = '☀️', ...rest } = options
  return toast.success(message, { icon, ...rest })
}

/** Toast d'avertissement — une situation à surveiller, PAS bloquante (sinon
 * `toastError`). `toast.warning` pour le style/icône dédiés (VX130) — avant,
 * seul `toast.error` existait pour tout signal non neutre (503 erreurs contre
 * 1 seul avertissement dans tout le repo, un vocabulaire binaire trompeur). */
export function toastWarning(message, options = {}) {
  return toast.warning(message, options)
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

/** Délai minimal (ms) du registre destructif — voir `toastDestructive`. */
export const DESTRUCTIVE_UNDO_MIN_MS = 6000

/**
 * toastDestructive — VX130 : le registre DESTRUCTIF que `toastWithUndo`
 * n'offrait pas (aucun registre à délai d'annulation prolongé jusqu'ici).
 * Même motif « safe undo » que `toastWithUndo`, mais pour une action à plus
 * fort enjeu (suppression définitive, résiliation…) : rendu visuel danger
 * (`toast.error`, style `error` de Toaster.jsx) ET délai d'annulation TOUJOURS
 * ≥ `DESTRUCTIVE_UNDO_MIN_MS` (6 s — contre ~4 s par défaut sur un toast
 * normal), pour laisser une vraie fenêtre de rattrapage sur un geste qu'on ne
 * peut pas défaire une fois `onCommit` exécuté.
 *
 *   toastDestructive({
 *     message: '1 lead supprimé définitivement.',
 *     onCommit: () => api.delete(id),
 *     onUndo:   () => restoreInUi(),
 *   })
 */
export function toastDestructive({
  message,
  description,
  onUndo,
  onCommit,
  duration = DESTRUCTIVE_UNDO_MIN_MS,
  undoLabel = 'Annuler',
} = {}) {
  const safeDuration = Math.max(duration, DESTRUCTIVE_UNDO_MIN_MS)
  let undone = false
  const id = toast.error(message, {
    description,
    duration: safeDuration,
    action: {
      label: undoLabel,
      onClick: () => {
        undone = true
        try { onUndo?.() } catch { /* l'undo ne doit jamais planter le toast */ }
      },
    },
  })
  if (typeof onCommit === 'function') {
    setTimeout(() => {
      if (!undone) {
        try { onCommit() } catch { /* le commit gère ses propres erreurs */ }
      }
    }, safeDuration)
  }
  return id
}

/** Petit utilitaire : extrait un message d'erreur FR lisible d'une erreur axios.
 *  VX203 — délègue à `apiError.js` (couvre en plus 429/500 HTML/timeout). */
export function errorMessageFrom(error, fallback = 'Une erreur est survenue.') {
  return apiErrorMessage(error, fallback)
}

export { toast }

import { useEffect } from 'react'
import { safeSet } from '../lib/safeStorage'

/* G27 — Garde « modifications non enregistrées ». Quand `dirty` est vrai,
   intercepte la fermeture/rafraîchissement de l'onglet (beforeunload natif).
   La navigation interne (react-router) est gardée par le composant Form via une
   confirmation au clic « Annuler »/sortie — ce hook couvre la sortie navigateur,
   indépendante du routeur. `message` est indicatif (les navigateurs modernes
   affichent leur propre texte). */
// VX62 — Registre PARTAGÉ « un formulaire modifié est monté quelque part ».
// Permet à des surfaces globales (SessionProvider : « Aller à la page de
// connexion ») de confirmer avant une navigation dure qui détruirait la saisie,
// sans coupler le provider à un formulaire précis. Simple compteur de refs.
let _dirtyForms = 0
export function isAnyFormDirty() {
  return _dirtyForms > 0
}

// VX170 — repli WebKit : `beforeunload` est quasi muet sur iOS Safari (un
// swipe-back ou une bascule d'app ne le déclenche pas) — l'événement fiable y
// est `pagehide` (+ `visibilitychange` → `hidden`, qui le précède souvent).
// On NE PEUT PAS bloquer un `pagehide` (aucune boîte de dialogue synchrone
// n'y survit) : la bonne UX WebKit est donc de SAUVER un brouillon défensif,
// jamais de bloquer. `persist` est optionnel et rétrocompatible : les
// adoptants existants (`useDirtyGuard(dirty)` / `useDirtyGuard(dirty, msg)`)
// ne branchent rien de nouveau tant qu'ils ne passent pas ce 3ᵉ argument.
export function useDirtyGuard(
  dirty,
  message = 'Modifications non enregistrées — quitter cette page ?',
  persist,
) {
  useEffect(() => {
    if (!dirty) return undefined
    _dirtyForms += 1
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = message // requis par certains navigateurs
      return message
    }
    window.addEventListener('beforeunload', handler)
    return () => {
      _dirtyForms = Math.max(0, _dirtyForms - 1)
      window.removeEventListener('beforeunload', handler)
    }
  }, [dirty, message])

  // `persist.getData` est lu au moment de l'événement (pas à l'abonnement)
  // pour toujours sauver le DERNIER état, sans réabonner à chaque frappe.
  useEffect(() => {
    if (!dirty || !persist?.key || typeof persist.getData !== 'function') return undefined
    const savePersistDraft = () => {
      const data = persist.getData()
      if (data === undefined) return
      safeSet(persist.key, { savedAt: new Date().toISOString(), data })
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') savePersistDraft()
    }
    window.addEventListener('pagehide', savePersistDraft)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.removeEventListener('pagehide', savePersistDraft)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [dirty, persist])
}

/** Confirmation impérative à utiliser sur une sortie volontaire (bouton Annuler,
    lien). Renvoie true si l'utilisateur accepte de partir (ou si non modifié). */
export function confirmLeaveIfDirty(
  dirty,
  message = 'Modifications non enregistrées — quitter cette page ?',
) {
  if (!dirty) return true
  return window.confirm(message)
}

export default useDirtyGuard

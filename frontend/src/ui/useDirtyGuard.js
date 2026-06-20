import { useEffect } from 'react'

/* G27 — Garde « modifications non enregistrées ». Quand `dirty` est vrai,
   intercepte la fermeture/rafraîchissement de l'onglet (beforeunload natif).
   La navigation interne (react-router) est gardée par le composant Form via une
   confirmation au clic « Annuler »/sortie — ce hook couvre la sortie navigateur,
   indépendante du routeur. `message` est indicatif (les navigateurs modernes
   affichent leur propre texte). */
export function useDirtyGuard(
  dirty,
  message = 'Modifications non enregistrées — quitter cette page ?',
) {
  useEffect(() => {
    if (!dirty) return undefined
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = message // requis par certains navigateurs
      return message
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty, message])
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

import { useEffect } from 'react'

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

export function useDirtyGuard(
  dirty,
  message = 'Modifications non enregistrées — quitter cette page ?',
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

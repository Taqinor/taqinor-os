import { useSyncExternalStore } from 'react'

/* TCH43 — « Suis-je en ligne ? » : UNE source pour toute l'app Tâches (coquille,
   BoutonCopilote, gestes grisés « Possible une fois connecté », file hors ligne).
   Lit `navigator.onLine` et suit les événements `online` / `offline` du navigateur ;
   sans `navigator` (rendu serveur, tests nus), on se dit en ligne.
   Source : reference/regles.md « Hors ligne et conflit entre appareils ». */

function abonner(rappel) {
  window.addEventListener('online', rappel)
  window.addEventListener('offline', rappel)
  return () => {
    window.removeEventListener('online', rappel)
    window.removeEventListener('offline', rappel)
  }
}

const lire = () => (typeof navigator === 'undefined' ? true : navigator.onLine !== false)

/** `true` tant que le navigateur se dit connecté ; bascule seul sur `offline` / `online`. */
export function useEnLigne() {
  return useSyncExternalStore(abonner, lire, () => true)
}

export default useEnLigne

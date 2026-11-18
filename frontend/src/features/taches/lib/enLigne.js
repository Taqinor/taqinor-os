import { useContext, useSyncExternalStore } from 'react'
import { ReactReduxContext } from 'react-redux'

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

/** Lecture ponctuelle (hors rendu : au moment d'un geste). */
export const estEnLigne = lire

/**
 * Raccord F2 — le compte connecté `{ userId, societe }`, lu dans le store de l'ERP SANS exiger de Provider
 * (une page de Tâches se monte aussi sans store dans les tests). Sert la clé du cache de la journée et du brouillon.
 */
export function useCompteTaches() {
  const contexte = useContext(ReactReduxContext)
  const user = contexte?.store?.getState?.()?.auth?.user
  return {
    userId: Number.isInteger(user?.id) ? user.id : null,
    societe: user?.active_company_id ?? user?.company_id ?? null,
  }
}

export default useEnLigne

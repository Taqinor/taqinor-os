import { useEffect } from 'react'
import { useBlocker } from 'react-router-dom'
import { useConfirmDialog } from '../ui/confirm'

/**
 * VX169 — useNavigationGuard(dirty, message)
 *
 * `useDirtyGuard` (ui/useDirtyGuard.js) ne couvre que `beforeunload` — la
 * fermeture/rafraîchissement d'ONGLET. Un clic sur un lien sidebar pendant la
 * saisie d'un formulaire ROUTE-LEVEL (pas un dialogue) navigue en interne
 * (`pushState` via react-router) sans jamais déclencher `beforeunload` : la
 * saisie est perdue instantanément, sans confirmation. `useBlocker` (react-
 * router-dom v7, disponible uniquement avec un routeur « data »,
 * `createBrowserRouter` confirmé sur ce repo — `router/index.jsx`) intercepte
 * cette navigation IN-APP.
 *
 * La confirmation utilise le dialogue design-system (`useConfirmDialog`),
 * jamais `window.confirm` brut — cohérent avec le reste du repo (L152).
 *
 * Repli NO-OP défensif : `useBlocker` lève une erreur hors d'un routeur data
 * (ex. un test monté avec un simple `<MemoryRouter>` plutôt qu'un routeur créé
 * par `createBrowserRouter`/`createMemoryRouter`) — on l'avale pour que le
 * hook ne fasse jamais planter un composant qui l'adopte.
 *
 * @param {boolean} dirty
 * @param {string}  [message]
 * @returns {import('react-router-dom').Blocker | null}
 */
export function useNavigationGuard(
  dirty,
  message = 'Modifications non enregistrées — quitter cette page ?',
) {
  const { confirm } = useConfirmDialog()

  // Toujours appelé (même chemin de code à chaque rendu pour une instance
  // donnée) ; seul le contexte routeur manquant peut faire lever une erreur,
  // jamais `dirty`.
  let blocker = null
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks -- cf. commentaire ci-dessus
    blocker = useBlocker(
      ({ currentLocation, nextLocation }) =>
        dirty && currentLocation.pathname !== nextLocation.pathname,
    )
  } catch {
    blocker = null
  }

  useEffect(() => {
    if (!blocker || blocker.state !== 'blocked') return undefined
    let alive = true
    confirm({
      title: 'Modifications non enregistrées',
      description: message,
      confirmLabel: 'Quitter sans enregistrer',
      cancelLabel: 'Rester sur la page',
      destructive: true,
    }).then((ok) => {
      if (!alive) return
      if (ok) blocker.proceed?.()
      else blocker.reset?.()
    })
    return () => { alive = false }
  }, [blocker, blocker?.state, confirm, message])

  return blocker
}

export default useNavigationGuard

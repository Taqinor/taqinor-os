// ODY11 — La transition signature app ↔ accueil.
// ----------------------------------------------------------------------------
// Odoo est perçu « lourd » à chaque re-navigation ; le paradigme ODY multiplie
// justement les allers-retours accueil ↔ app. La transition doit donc rendre
// ce mouvement délicieux, jamais laborieux :
//   • View Transitions API quand le navigateur la fournit
//     (`document.startViewTransition`) : fondu/échelle court piloté en CSS ;
//   • repli sinon : le fondu de route existant (`.route-fade`, VX134(c),
//     remonté par `key={pathname}` dans WithLayout) — RIEN à ajouter, on se
//     contente de ne pas le casser ;
//   • INSTANTANÉ sous `prefers-reduced-motion` OU sous la préférence app
//     (`data-reduced-motion="true"`, VX46/prefs.js) : aucune transition
//     démarrée du tout, pas seulement une durée raccourcie ;
//   • ZÉRO dépendance nouvelle (`flushSync` vient de react-dom, déjà là).
//
// `flushSync` est indispensable : React Router ne met pas le DOM à jour de
// façon synchrone dans le callback, et la View Transitions API capture
// l'instantané « après » à la fin de ce callback — sans flush, on animerait
// l'ancien écran vers lui-même.
import { flushSync } from 'react-dom'

/**
 * mouvementReduit — l'utilisateur a-t-il demandé moins de mouvement ? On
 * regarde les DEUX sources : le réglage OS et l'override app posé sur <html>
 * par `prefs.js` (un utilisateur peut vouloir le confort dans TAQINOR sans
 * changer son système).
 */
export function mouvementReduit({ doc = globalThis.document, win = globalThis.window } = {}) {
  try {
    if (doc?.documentElement?.getAttribute('data-reduced-motion') === 'true') return true
    return !!win?.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
  } catch {
    return false
  }
}

/** transitionsDisponibles — API View Transitions présente ? (feature-detect) */
export function transitionsDisponibles({ doc = globalThis.document } = {}) {
  return typeof doc?.startViewTransition === 'function'
}

/**
 * runAppTransition — exécute `run` (typiquement `navigate(to)`) dans une
 * transition de vue quand c'est pertinent, sinon immédiatement.
 *
 * Ne LÈVE jamais : une navigation ne doit pas dépendre d'un effet visuel. Si
 * quoi que ce soit échoue, on retombe sur l'exécution simple.
 *
 * @returns {{finished?: Promise}|null} la transition, ou `null` si exécution
 *   directe — l'appelant peut y accrocher son nettoyage.
 */
export function runAppTransition(run, { doc = globalThis.document, win = globalThis.window } = {}) {
  if (typeof run !== 'function') return null
  if (mouvementReduit({ doc, win }) || !transitionsDisponibles({ doc })) {
    run()
    return null
  }
  try {
    return doc.startViewTransition(() => {
      // Un échec de flushSync (rendu concurrent en cours, environnement
      // inattendu) ne doit pas annuler la navigation.
      try { flushSync(run) } catch { run() }
    })
  } catch {
    run()
    return null
  }
}

/** Nom de transition posé sur la pastille cliquée (cf. index.css, ODY11). */
export const NOM_TRANSITION_ICONE = 'taqinor-app-icon'

/**
 * marquerIconeSortante — pose `view-transition-name` sur la pastille de l'app
 * qu'on ouvre, pour qu'elle soit animée à part du reste de la page, puis rend
 * une fonction de nettoyage (un nom de transition doit être UNIQUE : le
 * laisser en place casserait la transition suivante).
 */
export function marquerIconeSortante(node) {
  const pastille = node?.querySelector?.('.app-icon')
  if (!pastille?.style) return () => {}
  pastille.style.viewTransitionName = NOM_TRANSITION_ICONE
  return () => { pastille.style.viewTransitionName = '' }
}

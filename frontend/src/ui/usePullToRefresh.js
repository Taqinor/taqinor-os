import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  dampenPull, shouldArmPull, shouldTriggerRefresh,
  DEFAULT_MAX_PULL, DEFAULT_THRESHOLD,
} from './pullToRefreshMath'

/* VX43 — Pull-to-refresh maison, sans dépendance.
   ----------------------------------------------------------------------------
   `overscroll-behavior: contain` (posé ailleurs dans le CSS terrain) a coupé le
   rubber-band natif iOS sans rien remettre à sa place : plus aucun geste
   « tirer pour rafraîchir » sur Ma journée / Interventions / le kanban leads.
   Ce hook reconstruit le geste au-dessus d'un conteneur scrollable, sans
   dépendance externe : un `touchstart` qui démarre alors que le scroll est à 0
   arme le geste ; tant que le doigt descend, on amortit la distance (résistance
   croissante, jamais 1:1) et on expose `pullDistance` pour le rendu (icône /
   texte qui suit le doigt) ; un lâcher au-delà du seuil déclenche `onRefresh`.

   Les maths (pures, testables sous `node --test`) vivent dans
   `pullToRefreshMath.js` ; ce fichier n'est qu'un fin branchement d'évènements
   React autour d'elles. */

/**
 * usePullToRefresh — attache le geste à un conteneur scrollable.
 *
 * @param {() => (void|Promise)} onRefresh appelé au relâchement au-delà du seuil.
 * @param {{ threshold?: number, maxPull?: number, disabled?: boolean }} [opts]
 * @returns {{
 *   containerProps: { ref, onTouchStart, onTouchEnd, onTouchCancel },
 *   pullDistance: number,
 *   refreshing: boolean,
 * }}
 *
 * `containerProps` se posent sur l'élément scrollable lui-même (celui qui a
 * `overflow: auto/scroll`) ; `scrollTop` y est lu directement via `currentTarget`.
 *
 * CAD177 — le `touchmove` n'est PAS un prop React : React enregistre
 * `touchstart`/`touchmove`/`wheel` en écouteurs PASSIFS à la racine, donc le
 * `preventDefault()` du tirage y était sans effet (le scroll natif n'était pas
 * retenu) et Chrome journalisait « Unable to preventDefault inside passive
 * event listener invocation » à chaque mouvement (marcheur aléatoire, QAH7).
 * Il est posé en écouteur NATIF `{ passive: false }` via la `ref` fournie
 * dans `containerProps` — l'appelant ne doit donc pas poser sa propre `ref`
 * sur ce même élément.
 */
export function usePullToRefresh(onRefresh, opts = {}) {
  const { threshold = DEFAULT_THRESHOLD, maxPull = DEFAULT_MAX_PULL, disabled = false } = opts
  const [pullDistance, setPullDistance] = useState(0)
  const [refreshing, setRefreshing] = useState(false)
  const start = useRef(null) // { x, y } au touchstart, ou null si non armé
  const armed = useRef(false)

  const reset = useCallback(() => {
    start.current = null
    armed.current = false
    setPullDistance(0)
  }, [])

  const onTouchStart = useCallback((e) => {
    if (disabled || refreshing) return
    const t = e.touches?.[0]
    if (!t) return
    start.current = { x: t.clientX, y: t.clientY }
    armed.current = e.currentTarget.scrollTop <= 0
  }, [disabled, refreshing])

  const onTouchMove = useCallback((e) => {
    if (disabled || refreshing || !start.current) return
    const t = e.touches?.[0]
    if (!t) return
    const deltaX = t.clientX - start.current.x
    const deltaY = t.clientY - start.current.y
    if (!armed.current) {
      armed.current = shouldArmPull({ scrollTop: e.currentTarget.scrollTop, deltaX, deltaY })
      if (!armed.current) return
    }
    if (!shouldArmPull({ scrollTop: e.currentTarget.scrollTop, deltaX, deltaY })) {
      // Le conteneur a défilé entre-temps (contenu plus long que l'écran) :
      // on désarme proprement sans laisser l'indicateur collé à l'écran.
      reset()
      return
    }
    // On n'empêche le scroll natif QUE lorsqu'on est réellement en train de
    // tirer (sinon le geste bloquerait un scroll vertical normal ailleurs).
    e.preventDefault?.()
    setPullDistance(dampenPull(deltaY, maxPull))
  }, [disabled, refreshing, maxPull, reset])

  // CAD177 — écouteur natif NON passif (voir l'en-tête) : la dernière version
  // du gestionnaire est lue via une ref, l'écouteur n'est posé qu'une fois par
  // élément.
  const [noeud, setNoeud] = useState(null)
  const moveRef = useRef(onTouchMove)
  useLayoutEffect(() => {
    moveRef.current = onTouchMove
  }, [onTouchMove])
  useEffect(() => {
    if (!noeud) return undefined
    const surMouvement = (e) => moveRef.current(e)
    noeud.addEventListener('touchmove', surMouvement, { passive: false })
    return () => noeud.removeEventListener('touchmove', surMouvement)
  }, [noeud])

  const onTouchEnd = useCallback(() => {
    if (disabled || refreshing) return
    const armedGesture = armed.current
    const distance = pullDistance
    reset()
    if (armedGesture && shouldTriggerRefresh(distance, threshold)) {
      setRefreshing(true)
      Promise.resolve()
        .then(() => onRefresh?.())
        .finally(() => setRefreshing(false))
    }
  }, [disabled, refreshing, pullDistance, threshold, onRefresh, reset])

  return {
    containerProps: {
      ref: setNoeud,
      onTouchStart,
      onTouchEnd,
      onTouchCancel: reset,
    },
    pullDistance,
    refreshing,
  }
}

export default usePullToRefresh

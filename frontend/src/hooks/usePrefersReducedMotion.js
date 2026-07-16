import { useEffect, useState } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function getInitial() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia(QUERY).matches
}

/**
 * VX135 — la garde globale reduced-motion (index.css, `@media
 * (prefers-reduced-motion: reduce) { *, *::before, *::after { ... } }`) ne
 * neutralise QUE les animations/transitions CSS DÉCLARATIVES. Les transforms
 * posés en JS (dnd-kit — tilt de la carte tenue, `dropAnimation`) y échappent
 * STRUCTURELLEMENT : aucune règle CSS ne peut intercepter un `style.transform`
 * écrit impérativement par une lib de drag-and-drop. Ce hook lit la
 * préférence (matchMedia + listener live — un utilisateur peut basculer le
 * réglage OS pendant que l'app tourne) pour que le code JS lui-même
 * désactive tilt/scale/dropAnimation à la source.
 */
export function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(getInitial)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined
    const mq = window.matchMedia(QUERY)
    const handler = () => setReduced(mq.matches)
    // Compat anciens navigateurs (Safari < 14) : addListener/removeListener.
    if (mq.addEventListener) mq.addEventListener('change', handler)
    else if (mq.addListener) mq.addListener(handler)
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', handler)
      else if (mq.removeListener) mq.removeListener(handler)
    }
  }, [])

  return reduced
}

export default usePrefersReducedMotion

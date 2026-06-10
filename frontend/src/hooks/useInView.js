import { useEffect, useRef, useState } from 'react'

/**
 * Observe un élément — retourne [ref, isVisible].
 * Une fois visible, reste visible (one-shot).
 */
export function useInView(threshold = 0.15) {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          obs.unobserve(el)
        }
      },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])

  return [ref, visible]
}

/**
 * Anime un compteur de 0 → target quand `active` passe à true.
 * Renvoie la valeur courante (entier).
 */
export function useCounter(target, duration = 1800, active = false) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    if (!active || target == null) return
    let raf
    const startTime = performance.now()

    const tick = (now) => {
      const t = Math.min((now - startTime) / duration, 1)
      const eased = 1 - (1 - t) ** 3   // easeOutCubic
      setValue(Math.round(eased * target))
      if (t < 1) raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active, target, duration])

  return value
}

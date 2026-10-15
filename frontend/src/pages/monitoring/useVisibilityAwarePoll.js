import { useEffect, useRef } from 'react'

/* ENF19 — sondage visibility-aware partagé (extrait de Co2Page.jsx / FleetPage.jsx
   où il était dupliqué à l'identique). Jamais un `setInterval` nu qui cogne
   l'API en onglet caché ; rappel immédiat au retour de visibilité. */
export default function useVisibilityAwarePoll(callback, intervalMs) {
  const cbRef = useRef(callback)
  useEffect(() => { cbRef.current = callback }, [callback])
  useEffect(() => {
    const tick = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      cbRef.current()
    }
    const iv = setInterval(tick, intervalMs)
    const onVisible = () => {
      if (document.visibilityState === 'visible') cbRef.current()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(iv)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [intervalMs])
}

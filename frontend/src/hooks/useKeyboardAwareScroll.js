import { useEffect } from 'react'

/**
 * VX51 — useKeyboardAwareScroll()
 *
 * Sur iOS, le clavier virtuel réduit le `visualViewport` sans redimensionner
 * `window` : un champ bas de formulaire (LeadForm, DevisGenerator) reste alors
 * caché SOUS le clavier — on tape sans voir ce qu'on écrit. Ce hook écoute
 * `visualViewport` `resize`/`scroll` et, si l'élément actif dépasse le bord
 * visible du clavier, le ramène au centre du cadre visible.
 *
 * No-op silencieux si `window.visualViewport` est absent (navigateurs sans
 * l'API, environnement de test) — jamais d'erreur, jamais de throw.
 *
 * @param {object} [options]
 * @param {React.RefObject<HTMLElement>} [options.containerRef] — conteneur à
 *   l'intérieur duquel chercher l'élément actif (défaut : document entier).
 */
export function useKeyboardAwareScroll(options = {}) {
  const { containerRef } = options

  useEffect(() => {
    const viewport = typeof window !== 'undefined' ? window.visualViewport : null
    // API absente (navigateur non-iOS, jsdom, ancien WebKit) : no-op silencieux.
    if (!viewport) return undefined

    const handleViewportChange = () => {
      // Lecture en requestAnimationFrame : on laisse le viewport/layout se
      // stabiliser avant de mesurer, pour éviter un scroll basé sur des
      // dimensions transitoires pendant l'animation du clavier.
      requestAnimationFrame(() => {
        const active = document.activeElement
        if (!active || active === document.body) return
        if (containerRef?.current && !containerRef.current.contains(active)) return

        const rect = active.getBoundingClientRect()
        // Bord bas réellement visible = offset du viewport visuel + sa hauteur
        // (le reste, sous ce bord, est recouvert par le clavier).
        const visibleBottom = viewport.offsetTop + viewport.height
        const visibleTop = viewport.offsetTop

        const hiddenBelow = rect.bottom > visibleBottom
        const hiddenAbove = rect.top < visibleTop
        if (hiddenBelow || hiddenAbove) {
          active.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }
      })
    }

    viewport.addEventListener('resize', handleViewportChange)
    viewport.addEventListener('scroll', handleViewportChange)

    return () => {
      viewport.removeEventListener('resize', handleViewportChange)
      viewport.removeEventListener('scroll', handleViewportChange)
    }
  }, [containerRef])
}

export default useKeyboardAwareScroll

import { useEffect, useState, useCallback, useMemo } from 'react'
import { ThemeContext } from './theme-context'
import {
  getStoredTheme, getStoredDensity, setStoredTheme, setStoredDensity,
  resolveTheme, applyThemeWithTransition, subscribeSystemTheme, initTheme,
} from './theme'

/**
 * F18 — Fournit thème (clair/sombre/système) + densité à toute l'app et les
 * applique au <html>. Suit l'OS en mode « système ». N'altère pas les écrans
 * existants (couleurs en dur) ; pilote les surfaces tokenisées (/src/ui).
 */
export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(getStoredTheme)
  const [density, setDensityState] = useState(getStoredDensity)
  const [resolvedTheme, setResolved] = useState(() => resolveTheme(getStoredTheme()))

  // Applique la préférence stockée au montage (thème + densité). L'état initial
  // est déjà résolu correctement (useState ci-dessus) → pas de setState ici.
  useEffect(() => {
    initTheme()
  }, [])

  // Réagit au basculement clair/sombre de l'OS quand on suit le système.
  useEffect(
    () =>
      subscribeSystemTheme(() => {
        if (getStoredTheme() === 'system') {
          // VX134(e) — bascule OS clair/sombre pendant que l'app tourne :
          // transition douce, comme un toggle explicite.
          applyThemeWithTransition('system')
          setResolved(resolveTheme('system'))
        }
      }),
    [],
  )

  const setTheme = useCallback((t) => {
    const v = setStoredTheme(t)
    setThemeState(v)
    setResolved(resolveTheme(v))
  }, [])

  const setDensity = useCallback((d) => {
    setDensityState(setStoredDensity(d))
  }, [])

  const value = useMemo(
    () => ({ theme, setTheme, resolvedTheme, density, setDensity }),
    [theme, resolvedTheme, density, setTheme, setDensity],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export default ThemeProvider

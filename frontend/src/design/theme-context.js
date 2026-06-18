import { createContext, useContext } from 'react'

/** Contexte de thème/densité. Valeur fournie par <ThemeProvider>. */
export const ThemeContext = createContext(null)

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme doit être utilisé dans <ThemeProvider>')
  return ctx
}

export function useDensity() {
  const { density, setDensity } = useTheme()
  return { density, setDensity }
}

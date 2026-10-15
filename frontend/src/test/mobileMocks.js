import { vi } from 'vitest'

/* Neutralisations COMMUNES des tests d'accueil mobile (ENF19) : importer ce
   module (de préférence en PREMIER) enregistre le `vi.mock` de
   `ui/ResponsiveDialog` dont `useIsMobile` est piloté par `isMobileMock`. */
export const isMobileMock = vi.fn(() => true)

vi.mock('../ui/ResponsiveDialog', async () => {
  const actual = await vi.importActual('../ui/ResponsiveDialog')
  return { ...actual, useIsMobile: () => isMobileMock() }
})

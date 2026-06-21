import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider.jsx'
import { UIShowcase } from './UIShowcase.jsx'

/* jsdom n'implémente ni ResizeObserver (mesuré par Radix Tooltip/Combobox) ni
   matchMedia (lu par ResponsiveDialog/useIsMobile). On les rend disponibles
   localement — sans toucher au setup partagé — pour pouvoir monter la vitrine
   complète. matchMedia répond « bureau » (matches=false) par défaut. */
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof window.matchMedia !== 'function') {
    window.matchMedia = (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() { return false },
    })
  }
})

/* ============================================================================
   P170 — Le guide de style vivant (/ui) doit se rendre ENTIÈREMENT sans lever
   d'exception. La page plante en entier si une section échoue au rendu, donc ce
   test est le filet de sécurité : il monte la vitrine complète (tous les
   primitifs + les nouvelles fondations documentées) dans les mêmes providers
   que l'app réelle.
     • <MemoryRouter> — le moteur DataTable lit useSearchParams.
     • <ThemeProvider> — useDensity (toggle densité + DataTable).
     • <ConfirmProvider> — la démo confirm/toast utilise useConfirmDialog.
   Un seul <Toaster> vit dans main.jsx ; on n'en monte pas un second ici.
   ========================================================================== */

function wrapper({ children }) {
  return (
    <MemoryRouter>
      <ThemeProvider>
        <ConfirmProvider>{children}</ConfirmProvider>
      </ThemeProvider>
    </MemoryRouter>
  )
}

// La vitrine complète (tous les primitifs + un DataTable virtualisé de 619
// lignes) est lourde à monter sous jsdom : on accorde un délai généreux par
// test pour que le rendu aboutisse (le rendu lui-même n'échoue pas).
const RENDER_TIMEOUT = 30000

describe('UIShowcase (/ui) — guide de style vivant', () => {
  it('se rend sans lever d\'exception', () => {
    expect(() => render(<UIShowcase />, { wrapper })).not.toThrow()
  }, RENDER_TIMEOUT)

  it('affiche le titre du système UI', () => {
    render(<UIShowcase />, { wrapper })
    expect(screen.getByText('Taqinor — Système UI')).toBeInTheDocument()
  }, RENDER_TIMEOUT)

  it('documente les fondations du design system (tokens, kit, densité, DoD)', () => {
    render(<UIShowcase />, { wrapper })
    // Jetons de marque OKLCH + échelle typo + élévation/focus + mouvement.
    expect(screen.getByText('Jetons de design (fondation F)')).toBeInTheDocument()
    // Modes de densité.
    expect(screen.getByText('Modes de densité')).toBeInTheDocument()
    // « Definition of done » par composant.
    expect(screen.getByText(/Definition of done/i)).toBeInTheDocument()
  }, RENDER_TIMEOUT)

  it('documente les nouveaux primitifs de fondation', () => {
    render(<UIShowcase />, { wrapper })
    expect(screen.getByText(/Confirmation & toasts/i)).toBeInTheDocument()
    expect(screen.getByText(/ResponsiveDialog/i)).toBeInTheDocument()
    expect(screen.getByText(/Squelettes/i)).toBeInTheDocument()
    expect(screen.getByText(/Chargement diff/i)).toBeInTheDocument()
    expect(screen.getByText(/Enregistrement optimiste/i)).toBeInTheDocument()
  }, RENDER_TIMEOUT)
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigateMock,
}))

// Les cloches font des appels API au montage : on les neutralise.
vi.mock('./NotificationBell', () => ({ default: () => null }))
vi.mock('./ChatBell', () => ({ default: () => null }))
vi.mock('./GlobalSearch', () => ({ default: () => null }))
// ThemeToggle dépend d'un ThemeProvider (hors périmètre de ce test).
vi.mock('../../design/ThemeToggle', () => ({ ThemeToggle: () => null }))
// VX46 — PreferencesPanel dépend lui aussi d'un ThemeProvider (useDensity),
// hors périmètre de ce test (comme ThemeToggle ci-dessus).
vi.mock('../../pages/preferences/PreferencesPanel', () => ({ default: () => null }))
// VX181 — Header appelle désormais useTheme() directement (3 options thème
// du menu utilisateur, seul accès sous md où ThemeToggle est masqué) : même
// hors-périmètre ThemeProvider que ci-dessus, on fournit un repli minimal.
vi.mock('../../design/theme-context', () => ({
  useTheme: () => ({ theme: 'system', setTheme: vi.fn() }),
}))

import Header from './Header'

function makeStore() {
  return configureStore({
    reducer: {
      auth: (s = { user: { username: 'reda', email: 'r@x.ma' } }) => s,
    },
  })
}

function renderHeader(path = '/dashboard') {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[path]}>
        <Header onMenu={() => {}} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('Header — I136 polissage en-tête', () => {
  beforeEach(() => navigateMock.mockClear())

  it('garde .header-title comme NON-heading (collision e2e avec le h2 de page)', () => {
    const { container } = renderHeader()
    const titleEl = container.querySelector('.header-title')
    expect(titleEl).toBeInTheDocument()
    // Ne doit JAMAIS être role=heading.
    expect(titleEl.getAttribute('role')).not.toBe('heading')
    expect(titleEl.tagName.toLowerCase()).not.toMatch(/^h[1-6]$/)
  })

  it('expose un repère de marque/logo CLIQUABLE qui ramène au dashboard', async () => {
    renderHeader('/ventes/devis')
    const brand = screen.getByRole('button', { name: /accueil|taqinor/i })
    expect(brand).toBeInTheDocument()
    await userEvent.click(brand)
    expect(navigateMock).toHaveBeenCalledWith('/dashboard')
  })

  it('affiche l\'affordance ⌘K avec une touche kbd', () => {
    const { container } = renderHeader()
    const kbd = container.querySelector('.header-cmdk-kbd')
    expect(kbd).toBeInTheDocument()
    expect(kbd.tagName.toLowerCase()).toBe('kbd')
  })

  it('le déclencheur ⌘K émet l\'événement de palette de commandes', async () => {
    renderHeader()
    const listener = vi.fn()
    window.addEventListener('taqinor:command-palette', listener)
    await userEvent.click(screen.getByLabelText(/Recherche et commandes/i))
    expect(listener).toHaveBeenCalled()
    window.removeEventListener('taqinor:command-palette', listener)
  })
})

/* ── U3 — Mobile header layout ─────────────────────────────────────────
   Garantit que le header est une RANGÉE PLATE sans chevauchement :
   header > header-left | header-right (frères directs, pas imbriqués).
   Ces tests couvrent la structure DOM — les règles CSS de z-index /
   safe-area ne sont pas vérifiables en jsdom (pas de layout réel),
   mais une régression de structure DOM suffit à casser le rendu mobile.
   ─────────────────────────────────────────────────────────────────── */
describe('Header — U3 layout mobile : rangée plate sans chevauchement', () => {
  beforeEach(() => navigateMock.mockClear())

  it('le <header> contient exactement .header-left et .header-right comme enfants directs de la rangée', () => {
    const { container } = renderHeader()
    const header = container.querySelector('header.header')
    expect(header).toBeInTheDocument()

    // Les deux groupes sont des enfants DIRECTS du <header>.
    const left  = header.querySelector(':scope > .header-left')
    const right = header.querySelector(':scope > .header-right')
    expect(left).toBeInTheDocument()
    expect(right).toBeInTheDocument()
  })

  it('le bouton hamburger (menu) est dans .header-left', () => {
    const { container } = renderHeader()
    const left = container.querySelector('.header-left')
    const menuBtn = left.querySelector('.header-menu-btn')
    expect(menuBtn).toBeInTheDocument()
    expect(menuBtn).toHaveAttribute('aria-label', 'Ouvrir le menu')
  })

  it('.header-heading (titre + fil d\'Ariane) est dans .header-left et NON dupliqué', () => {
    const { container } = renderHeader('/ventes')
    const headings = container.querySelectorAll('.header-heading')
    expect(headings.length).toBe(1)
    // Doit être dans .header-left, pas dans .header-right.
    const left = container.querySelector('.header-left')
    expect(left.contains(headings[0])).toBe(true)
  })

  it('.header-title est présent, non vide et dans .header-heading', () => {
    const { container } = renderHeader('/dashboard')
    const titleEl = container.querySelector('.header-title')
    expect(titleEl).toBeInTheDocument()
    // Le titre ne doit pas être vide (titleFor retourne au moins '')
    // et doit être DANS .header-heading (pas flottant hors du groupe).
    const heading = container.querySelector('.header-heading')
    expect(heading).toContainElement(titleEl)
  })

  it('le <header> est un <header> sémantique (balise landmark) avec un seul niveau', () => {
    const { container } = renderHeader()
    // Aucun <header> imbriqué (cela créerait deux landmarks header).
    const headers = container.querySelectorAll('header')
    expect(headers.length).toBe(1)
  })
})

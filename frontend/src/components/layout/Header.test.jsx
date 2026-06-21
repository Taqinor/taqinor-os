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

  it('affiche l’affordance ⌘K avec une touche kbd', () => {
    const { container } = renderHeader()
    const kbd = container.querySelector('.header-cmdk-kbd')
    expect(kbd).toBeInTheDocument()
    expect(kbd.tagName.toLowerCase()).toBe('kbd')
  })

  it('le déclencheur ⌘K émet l’événement de palette de commandes', async () => {
    renderHeader()
    const listener = vi.fn()
    window.addEventListener('taqinor:command-palette', listener)
    await userEvent.click(screen.getByLabelText(/Recherche et commandes/i))
    expect(listener).toHaveBeenCalled()
    window.removeEventListener('taqinor:command-palette', listener)
  })
})

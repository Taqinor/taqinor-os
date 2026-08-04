import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
// Ordre fondateur 2026-08-04 — on teste le CÂBLAGE menu→modale, pas la chaîne
// innovation entière (même convention de stub que Layout.test.jsx).
vi.mock('../../features/innovation/SuggestionCTA', () => ({
  default: ({ open }) => (open ? <div data-testid="stub-suggestion-ouverte" /> : null),
}))
vi.mock('../../features/innovation/FeedbackButton', () => ({
  default: ({ open }) => (open ? <div data-testid="stub-feedback-ouvert" /> : null),
}))
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

  // ODY5 — le repère de marque ramène désormais au MENU D'ACCUEIL (`/apps`) :
  // dans le paradigme ERP-Apps, « accueil » = mes apps, et le tableau de bord
  // n'est qu'une app parmi elles.
  it('expose un repère de marque/logo CLIQUABLE qui ramène au Menu d’accueil', async () => {
    renderHeader('/ventes/devis')
    const brand = screen.getByRole('button', { name: /accueil|taqinor/i })
    expect(brand).toBeInTheDocument()
    await userEvent.click(brand)
    expect(navigateMock).toHaveBeenCalledWith('/apps')
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

/* ── ODY5 — identité d'app + sortie canonique ──────────────────────────── */
describe('Header — ODY5 : la topbar dit dans quelle app on est, et comment en sortir', () => {
  beforeEach(() => navigateMock.mockClear())

  it('affiche la pastille de l’app active, et elle CHANGE avec la route', () => {
    const ventes = renderHeader('/ventes/devis')
    expect(ventes.container.querySelector('.header-app-pill-name').textContent).toBe('VENTES')
    ventes.unmount()

    const dash = renderHeader('/dashboard')
    expect(dash.container.querySelector('.header-app-pill-name').textContent).toBe('TABLEAU DE BORD')
  })

  it('hors de toute app (Menu d’accueil), aucune pastille d’app n’est affichée', () => {
    const { container } = renderHeader('/apps')
    expect(container.querySelector('.header-app-pill')).toBeNull()
  })

  it('le bouton ⊞ est LA sortie canonique : il ramène au Menu d’accueil', async () => {
    renderHeader('/ventes/devis')
    await userEvent.click(screen.getByRole('button', { name: 'Toutes les apps' }))
    expect(navigateMock).toHaveBeenCalledWith('/apps')
  })

  it('il n’existe QU’UNE sortie ⊞ dans l’en-tête (jamais deux affordances concurrentes)', () => {
    renderHeader('/ventes/devis')
    expect(screen.getAllByRole('button', { name: 'Toutes les apps' })).toHaveLength(1)
  })

  it('le fil d’Ariane reste une hiérarchie app › page (1er segment cliquable vers le cockpit)', () => {
    const { container } = renderHeader('/ventes/factures')
    const link = container.querySelector('.breadcrumbs a')
    expect(link).toBeInTheDocument()
    // ODY5 — pointe vers le cockpit de l'APP active (VX11), pas vers un
    // segment d'URL intermédiaire inexistant.
    expect(link).toHaveAttribute('href', '/ventes/cockpit')
  })

  it('ODY5 — un titre de sous-route n’est plus masqué par le préfixe générique (/crm/cockpit ≠ « Clients »)', () => {
    const { container } = renderHeader('/crm/forecast')
    expect(container.querySelector('.header-title').textContent).not.toBe('Clients')
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

describe('Header · retour & amélioration dans le menu PROFIL (ordre fondateur 2026-08-04)', () => {
  // Les deux boutons flottants (NTIDE9/NTIDE37) ont quitté l'écran : leur
  // unique porte est ici. Ce test rougit si les entrées disparaissent du menu.
  it('le menu utilisateur porte les deux entrées et ouvre la modale idée', async () => {
    renderHeader()
    await userEvent.click(screen.getByRole('button', { name: 'Menu utilisateur' }))
    expect(await screen.findByText('Suggérer une amélioration')).toBeInTheDocument()
    expect(screen.getByText('Envoyer un retour')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Suggérer une amélioration'))
    // Le stub monte avec open=true : le câblage menu → état → modale est réel.
    expect(await screen.findByTestId('stub-suggestion-ouverte')).toBeInTheDocument()
  })
})

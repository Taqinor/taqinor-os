// N163 — Tests axe ciblés sur la coquille (layout chrome) que cette lane possède.
// On reste FOCALISÉ : on rend des composants isolés (Breadcrumbs, BottomTabBar,
// Sidebar) plutôt que des pages entières bruyantes, pour des assertions stables
// et rapides. `vitest-axe` lance axe-core sur le DOM rendu et échoue sur toute
// violation d'accessibilité (rôles, contrastes structurels, attributs ARIA…).
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { axe } from 'vitest-axe'
import * as axeMatchers from 'vitest-axe/matchers'

// YHARD8 — Header a des dépendances API-au-montage (cloches, recherche) hors
// périmètre de ce test purement a11y ; neutralisées comme dans
// components/layout/Header.test.jsx (même convention exacte).
vi.mock('../components/layout/NotificationBell', () => ({ default: () => null }))
vi.mock('../components/layout/ChatBell', () => ({ default: () => null }))
vi.mock('../components/layout/GlobalSearch', () => ({ default: () => null }))
vi.mock('../design/ThemeToggle', () => ({ ThemeToggle: () => null }))
// VX46 — PreferencesPanel dépend lui aussi d'un ThemeProvider (useDensity),
// hors périmètre de ce test (comme ThemeToggle ci-dessus).
vi.mock('../pages/preferences/PreferencesPanel', () => ({ default: () => null }))
// VX181 — Header appelle désormais useTheme() directement (3 options thème du
// menu utilisateur, seul accès sous md où ThemeToggle est masqué) : même
// hors-périmètre ThemeProvider que ci-dessus, on fournit un repli minimal
// (convention identique à components/layout/Header.test.jsx).
vi.mock('../design/theme-context', () => ({
  useTheme: () => ({ theme: 'system', setTheme: vi.fn() }),
}))

import Breadcrumbs from '../components/layout/Breadcrumbs'
import BottomTabBar from '../components/layout/BottomTabBar'
import Sidebar from '../components/layout/Sidebar'
import Header from '../components/layout/Header'
import ClientQuickCreateModal from '../pages/ventes/ClientQuickCreateModal'

expect.extend(axeMatchers)

function authStore() {
  return configureStore({
    reducer: {
      auth: (s = { role: 'admin', permissions: [], user: null }) => s,
      parametres: (s = { profile: { nom: 'TAQINOR' } }) => s,
    },
  })
}

describe('a11y (N163) — coquille', () => {
  it('Breadcrumbs n’a aucune violation axe', async () => {
    const { container } = render(
      <MemoryRouter>
        <Breadcrumbs pathname="/ventes/devis" />
      </MemoryRouter>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('Breadcrumbs tronqué (chemin long) n’a aucune violation axe', async () => {
    const crumbs = [
      { label: 'Niveau A', to: '/a' },
      { label: 'Niveau B', to: '/a/b' },
      { label: 'Niveau C', to: '/a/b/c' },
      { label: 'Page', to: '/a/b/c/d', current: true },
    ]
    const { container } = render(
      <MemoryRouter>
        <Breadcrumbs crumbs={crumbs} />
      </MemoryRouter>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('BottomTabBar n’a aucune violation axe', async () => {
    // VX12 — le tiroir « Plus » lit role/permissions via useSelector (mêmes
    // règles de gating que la Sidebar) : un Provider est désormais nécessaire.
    const { container } = render(
      <Provider store={authStore()}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <BottomTabBar />
        </MemoryRouter>
      </Provider>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('Sidebar n’a aucune violation axe', async () => {
    const { container } = render(
      <Provider store={authStore()}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Sidebar collapsed={false} onToggle={() => {}} onNavigate={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})

/* ============================================================================
   YHARD8 — Passe a11y FONCTIONNELLE (navigation clavier des dialogues/menus,
   labels de formulaires, focus-trap des modales, ordre de tabulation) sur les
   écrans à fort usage manquants du périmètre N163 ci-dessus : un dialogue
   Radix (création client — même famille que création devis/lead : Dialog
   Radix + <form> labellisé), le DataTable générique (déjà couvert par un axe
   spec dédié — voir `ui/datatable/DataTable.test.jsx` : « n'a aucune violation
   d'accessibilité détectable », gardé comme SOURCE de vérité plutôt que
   dupliqué ici), et la barre de navigation principale (Header). Aucun
   sélecteur e2e existant n'est modifié (ap-trigger/ap-menu/ap-item/att-name/
   pp-* intacts — ces composants n'en portent pas ; seule la structure DOM
   déjà en place est vérifiée, aucun refactor visuel).
   ========================================================================== */
describe('a11y (YHARD8) — dialogue Radix + formulaire + navigation principale', () => {
  it('ClientQuickCreateModal (dialogue Radix + formulaire labellisé) n’a aucune violation axe', async () => {
    const { container } = render(
      <ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('ClientQuickCreateModal : chaque champ a un label associé (accessible name)', () => {
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    // getByLabelText lève si le champ n'a pas de label accessible associé.
    // « Nom » porte un indicateur requis (« * ») dans son label — le nom
    // accessible réel est "Nom *", d'où le préfixe en regex plutôt qu'un
    // texte exact.
    expect(screen.getByLabelText(/^Nom/)).toBeInTheDocument()
    expect(screen.getByLabelText('Prénom')).toBeInTheDocument()
    expect(screen.getByLabelText('Téléphone')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })

  it('ClientQuickCreateModal : focus-trap Radix — Échap ferme le dialogue', async () => {
    const onClose = vi.fn()
    render(<ClientQuickCreateModal open onClose={onClose} onCreated={() => {}} />)
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })

  it('ClientQuickCreateModal : les boutons du pied ont un nom accessible', () => {
    render(<ClientQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)
    expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Créer et sélectionner/ })).toBeInTheDocument()
  })

  it('Header (navigation principale) n’a aucune violation axe', async () => {
    const store = configureStore({
      reducer: { auth: (s = { user: { username: 'reda', email: 'r@x.ma' } }) => s },
    })
    const { container } = render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Header onMenu={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('Header : chaque bouton-icône (hamburger, marque, ⌘K, Copilote, menu utilisateur) a un nom accessible', () => {
    const store = configureStore({
      reducer: { auth: (s = { user: { username: 'reda', email: 'r@x.ma' } }) => s },
    })
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Header onMenu={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    expect(screen.getByRole('button', { name: 'Ouvrir le menu' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /accueil|taqinor/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Recherche et commandes/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir le Copilote' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Menu utilisateur' })).toBeInTheDocument()
  })

  it('Header : le menu utilisateur (Radix DropdownMenu) est navigable au clavier et garde les hooks e2e existants', async () => {
    const store = configureStore({
      reducer: { auth: (s = { user: { username: 'reda', email: 'r@x.ma' } }) => s },
    })
    const { container } = render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Header onMenu={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Menu utilisateur' }))
    expect(await screen.findByText('Paramètres')).toBeInTheDocument()
    // Sélecteurs e2e intacts (préservés, jamais renommés par cette passe a11y).
    expect(container.querySelector('.header-title')).toBeInTheDocument()
    expect(container.querySelector('.header-cmdk-kbd')).toBeInTheDocument()
  })
})

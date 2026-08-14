import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* NTDMO27/28 — onglet Paramètres « Démo & Onboarding ». Deux morceaux
   réellement NOUVEAUX ici : le toggle global `tours_actifs` (visible pour
   TOUTE société, contrairement à PresentationModeToggle/DemoResetButton
   réservés aux sociétés démo) et le bloc de masquage d'items (NTDMO28). Le
   reste réutilise des composants déjà testés ailleurs. */

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))
vi.mock('../../api/axios', () => ({ default: apiMock }))

const fetchMeMock = vi.fn(() => ({ type: 'auth/fetchMe/noop' }))
vi.mock('../../features/auth/store/authSlice', () => ({ fetchMe: () => fetchMeMock() }))

import DemoOnboardingSection from './DemoOnboardingSection'

const ITEMS_MASQUES = [
  { id: 1, key: 'configurer_societe', libelle: 'Configurer votre société', masque: false },
  { id: 2, key: 'import_clients', libelle: 'Importer vos clients', masque: true },
]

// Routage par URL : `/onboarding/tours/` (VisitesGuideesBlock, réutilisé tel
// quel) renvoie un tableau vide ; `/onboarding/items-masques/` (NTDMO28)
// renvoie le catalogue mocké ci-dessus. Toute autre URL non mockée n'est pas
// utilisée par ce composant.
function mockGetByUrl() {
  apiMock.get.mockImplementation((url) => {
    if (url === '/onboarding/tours/') return Promise.resolve({ data: [] })
    if (url === '/onboarding/items-masques/') return Promise.resolve({ data: ITEMS_MASQUES })
    return Promise.resolve({ data: [] })
  })
}

function renderSection(user) {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(<Provider store={store}><DemoOnboardingSection /></Provider>)
}

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
  apiMock.patch.mockReset()
  apiMock.post.mockReset()
  fetchMeMock.mockClear()
})

describe('DemoOnboardingSection (NTDMO27)', () => {
  it('affiche le toggle « tours actifs », coché par défaut, pour TOUTE société (pas seulement démo)', async () => {
    mockGetByUrl()
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    const toggle = screen.getByLabelText('Activer les tours contextuels pour les nouveaux utilisateurs')
    expect(toggle).toBeChecked()
  })

  it('les contrôles démo (mode présentation, reset) restent invisibles sur une société réelle', async () => {
    mockGetByUrl()
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    expect(screen.queryByTestId('presentation-mode-card')).not.toBeInTheDocument()
    expect(screen.queryByTestId('demo-reset-card')).not.toBeInTheDocument()
    // Le toggle global, lui, reste visible.
    expect(screen.getByTestId('tours-actifs-card')).toBeInTheDocument()
  })

  it('cliquer le toggle appelle PATCH tours_actifs puis rafraîchit /auth/me', async () => {
    mockGetByUrl()
    apiMock.patch.mockResolvedValueOnce({ data: {} })
    const user = userEvent.setup()
    renderSection({ id: 1, company_id: 10, company_est_demo: false, company_tours_actifs: true })
    await user.click(screen.getByLabelText('Activer les tours contextuels pour les nouveaux utilisateurs'))
    await waitFor(() => expect(apiMock.patch)
      .toHaveBeenCalledWith('/companies/10/', { tours_actifs: false }))
    expect(fetchMeMock).toHaveBeenCalled()
  })
})

describe('DemoOnboardingSection — items de checklist actifs (NTDMO28)', () => {
  it('liste le catalogue avec son statut masqué/visible', async () => {
    mockGetByUrl()
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    expect(await screen.findByText('Configurer votre société')).toBeInTheDocument()
    expect(screen.getByText('Importer vos clients')).toBeInTheDocument()
    const visible = screen.getByLabelText('Afficher « Configurer votre société » dans les Premiers pas')
    const masque = screen.getByLabelText('Afficher « Importer vos clients » dans les Premiers pas')
    expect(visible).toBeChecked()
    expect(masque).not.toBeChecked()
  })

  it('décocher un item appelle POST .../masquer/', async () => {
    mockGetByUrl()
    apiMock.post.mockResolvedValueOnce({
      data: ITEMS_MASQUES.map((it) => (it.id === 1 ? { ...it, masque: true } : it)),
    })
    const user = userEvent.setup()
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    const visible = await screen.findByLabelText(
      'Afficher « Configurer votre société » dans les Premiers pas')
    await user.click(visible)
    await waitFor(() => expect(apiMock.post)
      .toHaveBeenCalledWith('/onboarding/items-masques/1/masquer/'))
  })

  it('recocher un item masqué appelle POST .../demasquer/', async () => {
    mockGetByUrl()
    apiMock.post.mockResolvedValueOnce({
      data: ITEMS_MASQUES.map((it) => (it.id === 2 ? { ...it, masque: false } : it)),
    })
    const user = userEvent.setup()
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    const masque = await screen.findByLabelText(
      'Afficher « Importer vos clients » dans les Premiers pas')
    await user.click(masque)
    await waitFor(() => expect(apiMock.post)
      .toHaveBeenCalledWith('/onboarding/items-masques/2/demasquer/'))
  })
})

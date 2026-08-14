import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* NTDMO27 — onglet Paramètres « Démo & Onboarding ». Le toggle global
   `tours_actifs` (visible pour TOUTE société, contrairement à
   PresentationModeToggle/DemoResetButton réservés aux sociétés démo) est le
   seul morceau réellement NOUVEAU ici — le reste réutilise des composants
   déjà testés ailleurs (PresentationModeToggle.test.jsx, DemoResetButton
   éventuel, VisitesGuideesBlock.test.jsx). */

const { apiMock } = vi.hoisted(() => ({ apiMock: { get: vi.fn(), patch: vi.fn(), post: vi.fn() } }))
vi.mock('../../api/axios', () => ({ default: apiMock }))

const fetchMeMock = vi.fn(() => ({ type: 'auth/fetchMe/noop' }))
vi.mock('../../features/auth/store/authSlice', () => ({ fetchMe: () => fetchMeMock() }))

import DemoOnboardingSection from './DemoOnboardingSection'

function renderSection(user) {
  const store = configureStore({ reducer: { auth: (s = { user }) => s } })
  return render(<Provider store={store}><DemoOnboardingSection /></Provider>)
}

afterEach(() => {
  cleanup()
  apiMock.get.mockReset()
  apiMock.patch.mockReset()
  fetchMeMock.mockClear()
})

describe('DemoOnboardingSection (NTDMO27)', () => {
  it('affiche le toggle « tours actifs », coché par défaut, pour TOUTE société (pas seulement démo)', async () => {
    apiMock.get.mockResolvedValue({ data: { items: [], faits: 0, total: 0, termine: true } })
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    const toggle = screen.getByLabelText('Activer les tours contextuels pour les nouveaux utilisateurs')
    expect(toggle).toBeChecked()
  })

  it('les contrôles démo (mode présentation, reset) restent invisibles sur une société réelle', async () => {
    apiMock.get.mockResolvedValue({ data: { items: [], faits: 0, total: 0, termine: true } })
    renderSection({ id: 1, company_id: 10, company_est_demo: false })
    expect(screen.queryByTestId('presentation-mode-card')).not.toBeInTheDocument()
    expect(screen.queryByTestId('demo-reset-card')).not.toBeInTheDocument()
    // Le toggle global, lui, reste visible.
    expect(screen.getByTestId('tours-actifs-card')).toBeInTheDocument()
  })

  it('cliquer le toggle appelle PATCH tours_actifs puis rafraîchit /auth/me', async () => {
    apiMock.get.mockResolvedValue({ data: { items: [], faits: 0, total: 0, termine: true } })
    apiMock.patch.mockResolvedValueOnce({ data: {} })
    const user = userEvent.setup()
    renderSection({ id: 1, company_id: 10, company_est_demo: false, company_tours_actifs: true })
    await user.click(screen.getByLabelText('Activer les tours contextuels pour les nouveaux utilisateurs'))
    await waitFor(() => expect(apiMock.patch)
      .toHaveBeenCalledWith('/companies/10/', { tours_actifs: false }))
    expect(fetchMeMock).toHaveBeenCalled()
  })
})

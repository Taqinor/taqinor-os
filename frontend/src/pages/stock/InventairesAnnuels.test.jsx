import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'
import parametresReducer from '../../features/parametres/store/parametresSlice'

/* ============================================================================
   WIR109 — XSTK13 : inventaire annuel légal FIGÉ (CGNC). LECTURE SEULE côté
   modèle ; un snapshot n'est créé QUE par l'action `figer`, jamais réécrit —
   écran admin-only.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getInventairesAnnuels: vi.fn(),
    figerInventaireAnnuel: vi.fn(),
    exportInventaireAnnuelXlsx: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import InventairesAnnuels from './InventairesAnnuels'

function makeStore({ role = 'admin' } = {}) {
  return configureStore({
    reducer: { auth: authReducer, parametres: parametresReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><InventairesAnnuels /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('InventairesAnnuels (WIR109)', () => {
  it('refuse un rôle non admin', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    renderPage(makeStore({ role: 'responsable' }))
    expect(await screen.findByText(/Réservé à l'administrateur/)).toBeInTheDocument()
  })

  it('liste les exercices figés', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({
      data: [{ id: 1, exercice: 2025, nb_lignes: 42, total_valeur: 150000 }],
    })

    renderPage()

    expect(await screen.findByText(/Exercice 2025/)).toBeInTheDocument()
  })

  it('fige un nouvel exercice', async () => {
    stockApi.getInventairesAnnuels.mockResolvedValue({ data: [] })
    stockApi.figerInventaireAnnuel.mockResolvedValue({ data: { id: 2, exercice: 2026 } })
    window.confirm = vi.fn(() => true)

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Figer un exercice/ }))

    const dialog = await screen.findByRole('dialog')
    const input = within(dialog).getByLabelText(/Exercice/)
    await userEvent.clear(input)
    await userEvent.type(input, '2026')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Figer' }))

    await waitFor(() => {
      expect(stockApi.figerInventaireAnnuel).toHaveBeenCalledWith({ exercice: 2026 })
    })
  })
})

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR109 — XSTK14 : revalorisation manuelle du stock (document tracé,
   admin-only). Corrige le coût moyen d'un produit ; verrouillée après
   validation.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getRevalorisationsStock: vi.fn(),
    createRevalorisationStock: vi.fn(),
    validerRevalorisationStock: vi.fn(),
    deleteRevalorisationStock: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import RevalorisationsStock from './RevalorisationsStock'

function makeStore({ role = 'admin' } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
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
        <ThemeProvider><RevalorisationsStock /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('RevalorisationsStock (WIR109)', () => {
  it('refuse un rôle non admin', async () => {
    stockApi.getRevalorisationsStock.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: [] })
    renderPage(makeStore({ role: 'responsable' }))
    expect(await screen.findByText(/Réservé à l'administrateur/)).toBeInTheDocument()
  })

  it('crée une revalorisation', async () => {
    stockApi.getRevalorisationsStock.mockResolvedValue({ data: [] })
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 3, nom: 'Panneau 550W' }] })
    stockApi.createRevalorisationStock.mockResolvedValue({ data: {} })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Nouvelle revalorisation/ }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'Panneau 550W' }))
    await userEvent.type(within(dialog).getByLabelText(/Nouveau coût/), '900')
    await userEvent.type(within(dialog).getByLabelText('Motif'), 'Baisse mondiale du prix')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => {
      expect(stockApi.createRevalorisationStock).toHaveBeenCalledWith({
        produit: 3, nouveau_cout: 900, motif: 'Baisse mondiale du prix',
      })
    })
  })

  it('valide une revalorisation en brouillon', async () => {
    stockApi.getRevalorisationsStock.mockResolvedValue({
      data: [{
        id: 9, produit_nom: 'Panneau 550W', statut: 'brouillon',
        ancien_cout: 1000, nouveau_cout: 900, delta_valeur: -100,
      }],
    })
    stockApi.getProduits.mockResolvedValue({ data: [] })
    stockApi.validerRevalorisationStock.mockResolvedValue({ data: {} })
    window.confirm = vi.fn(() => true)

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Valider' }))

    await waitFor(() => {
      expect(stockApi.validerRevalorisationStock).toHaveBeenCalledWith(9)
    })
  })
})

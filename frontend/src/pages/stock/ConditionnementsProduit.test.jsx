import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR109 — XSTK15 : conditionnements d'achat d'un produit (« Touret 100 m »,
   « Carton 50 »). CRUD complet, jusqu'ici backend-only.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getConditionnementsProduit: vi.fn(),
    createConditionnementProduit: vi.fn(),
    updateConditionnementProduit: vi.fn(),
    deleteConditionnementProduit: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import ConditionnementsProduit from './ConditionnementsProduit'

function makeStore({ role = 'admin', permissions = ['stock_modifier', 'stock_voir'] } = {}) {
  return configureStore({
    reducer: { auth: authReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderPage(store = makeStore()) {
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider><ConditionnementsProduit /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ConditionnementsProduit (WIR109)', () => {
  it('liste les conditionnements existants', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Câble 6mm²' }] })
    stockApi.getConditionnementsProduit.mockResolvedValue({
      data: [{ id: 1, nom: 'Touret 100 m', produit_nom: 'Câble 6mm²', facteur: 100, unite_stock: 'm' }],
    })

    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Conditionnements produit' })
    expect(within(grid).getByText('Touret 100 m')).toBeInTheDocument()
  })

  it('crée un conditionnement rattaché à un produit', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Câble 6mm²' }] })
    stockApi.getConditionnementsProduit.mockResolvedValue({ data: [] })
    stockApi.createConditionnementProduit.mockResolvedValue({ data: {} })

    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Nouveau conditionnement/ }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'Câble 6mm²' }))
    await userEvent.type(within(dialog).getByLabelText('Nom'), 'Touret 100 m')
    await userEvent.type(within(dialog).getByLabelText(/Facteur/), '100')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => {
      expect(stockApi.createConditionnementProduit).toHaveBeenCalledWith({
        produit: 1, nom: 'Touret 100 m', facteur: 100, code_barres: null,
      })
    })
  })

  it('supprime un conditionnement', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [] })
    stockApi.getConditionnementsProduit.mockResolvedValue({
      data: [{ id: 1, nom: 'Touret 100 m', produit_nom: 'Câble 6mm²', facteur: 100, unite_stock: 'm' }],
    })
    stockApi.deleteConditionnementProduit.mockResolvedValue({})
    window.confirm = vi.fn(() => true)

    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Conditionnements produit' })
    await userEvent.click(within(grid).getByRole('button', { name: 'Supprimer' }))

    await waitFor(() => {
      expect(stockApi.deleteConditionnementProduit).toHaveBeenCalledWith(1)
    })
  })
})

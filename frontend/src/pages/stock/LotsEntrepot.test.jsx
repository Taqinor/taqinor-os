import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   WIR109 — XSTK6 : registre de lots en entrepôt (FEFO). LECTURE SEULE côté
   modèle ; ces tests couvrent la consultation + les deux actions serveur déjà
   testées (`sortir`, `fefo`).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getLotsEntrepot: vi.fn(),
    getLotFefo: vi.fn(),
    sortirLotEntrepot: vi.fn(),
    getProduits: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import LotsEntrepot from './LotsEntrepot'

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
        <ThemeProvider><LotsEntrepot /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('LotsEntrepot (WIR109)', () => {
  it('liste les lots avec la péremption colorée', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Batterie 100Ah' }] })
    stockApi.getLotsEntrepot.mockResolvedValue({
      data: [
        {
          id: 5, numero_lot: 'LOT-005', produit_nom: 'Batterie 100Ah',
          date_peremption: '2020-01-01', est_perime: true,
          quantite_restante: 3, quantite_recue: 10, emplacement_nom: 'Dépôt A',
        },
      ],
    })

    renderPage()

    const grid = await screen.findByRole('grid', { name: 'Lots en entrepôt' })
    expect(within(grid).getByText('LOT-005')).toBeInTheDocument()
    expect(within(grid).getByText('Batterie 100Ah')).toBeInTheDocument()
  })

  it('sort une quantité d\'un lot', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [] })
    stockApi.getLotsEntrepot.mockResolvedValue({
      data: [
        {
          id: 5, numero_lot: 'LOT-005', produit_nom: 'Batterie 100Ah',
          date_peremption: null, est_perime: false,
          quantite_restante: 3, quantite_recue: 10, emplacement_nom: 'Dépôt A',
        },
      ],
    })
    stockApi.sortirLotEntrepot.mockResolvedValue({ data: {} })

    renderPage()
    const grid = await screen.findByRole('grid', { name: 'Lots en entrepôt' })
    await userEvent.click(within(grid).getByRole('button', { name: /Sortir/ }))

    const dialog = await screen.findByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Quantité'), '2')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Sortir' }))

    await waitFor(() => {
      expect(stockApi.sortirLotEntrepot).toHaveBeenCalledWith(
        5, expect.objectContaining({ quantite: 2 }))
    })
  })

  it('suggestion FEFO : affiche le plan renvoyé par le serveur', async () => {
    stockApi.getProduits.mockResolvedValue({ data: [{ id: 1, nom: 'Batterie 100Ah' }] })
    stockApi.getLotsEntrepot.mockResolvedValue({ data: [] })
    stockApi.getLotFefo.mockResolvedValue({
      data: [{ lot_id: 5, numero_lot: 'LOT-005', date_peremption: '2027-01-01', quantite: 2 }],
    })

    renderPage()
    await screen.findByRole('grid', { name: 'Lots en entrepôt' })

    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(await screen.findByRole('option', { name: 'Batterie 100Ah' }))
    await userEvent.click(screen.getByRole('button', { name: 'Suggérer' }))

    expect(await screen.findByText(/LOT-005/)).toBeInTheDocument()
    expect(stockApi.getLotFefo).toHaveBeenCalledWith('1', 1)
  })
})

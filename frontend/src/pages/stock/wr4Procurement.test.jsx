import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   WR4 — Achats & fournisseurs : scorecard performance (FG59), « facturer une
   réception » (FG56) et PDF facture fournisseur (FG55) câblés aux écrans.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getFournisseurs: vi.fn(),
    deleteFournisseur: vi.fn(),
    performanceFournisseur: vi.fn(),
    facturerReception: vi.fn(),
    factureFournisseurPdf: vi.fn(),
    confirmerReceptionFournisseur: vi.fn(),
    annulerReceptionFournisseur: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import FournisseursStock from './FournisseursStock.jsx'

function store(role = 'admin') {
  return configureStore({
    reducer: { auth: (s = { role, permissions: [] }) => s },
  })
}

function renderFournisseurs(role = 'admin') {
  return render(
    <Provider store={store(role)}>
      <MemoryRouter>
        <ThemeProvider><FournisseursStock /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  stockApi.getFournisseurs.mockResolvedValue({
    data: [{ id: 9, nom: 'JA Solar', nb_produits: 4, nb_bons_commande: 2 }],
  })
})

describe('WR4 — scorecard performance fournisseur', () => {
  it('ouvre la scorecard et affiche les indicateurs FG59 (admin)', async () => {
    stockApi.performanceFournisseur.mockResolvedValue({
      data: {
        fournisseur_id: 9, fournisseur_nom: 'JA Solar', nb_bons: 5,
        avg_lead_time_days: 12.5, fill_rate_pct: 94.2, nb_retours: 1,
        return_rate_pct: 20, total_achats_ht: '48000.00',
      },
    })
    renderFournisseurs('admin')
    expect((await screen.findAllByText('JA Solar')).length).toBeGreaterThan(0)
    fireEvent.click(screen.getAllByRole('button', { name: 'Voir la performance' })[0])
    await waitFor(() => {
      expect(stockApi.performanceFournisseur).toHaveBeenCalledWith(9)
    })
    expect(await screen.findByText('12.5 j')).toBeVisible()
    expect(screen.getByText('94.2 %')).toBeVisible()
    expect(screen.getByText(/48\s?000,00 MAD/)).toBeVisible()
  })

  it('ne montre pas le bouton performance pour un non-admin', async () => {
    renderFournisseurs('responsable')
    await screen.findAllByText('JA Solar')
    expect(screen.queryByRole('button', { name: 'Voir la performance' })).toBeNull()
  })
})

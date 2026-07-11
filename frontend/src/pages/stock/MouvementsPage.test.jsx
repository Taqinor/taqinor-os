import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZSTK7 — « Vue groupée / pivot » sur les mouvements de stock : bascule vers
   un tableau agrégé (entrées/sorties/net) par produit/type/mois/emplacement
   (mouvements/agregation/), avec son propre export Excel.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getTransferts: vi.fn(),
    mouvementsAgregation: vi.fn(),
    mouvementsAgregationXlsx: vi.fn(),
    exportMouvementsXlsx: vi.fn(),
  },
}))

vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchMouvements: () => ({ type: 'stock/fetchMouvements/noop' }),
  fetchProduits: () => ({ type: 'stock/fetchProduits/noop' }),
  createMouvement: (payload) => ({ type: 'stock/createMouvement/noop', payload }),
}))

import stockApi from '../../api/stockApi'
import MouvementsPage from './MouvementsPage.jsx'

function store({ role = 'admin', mouvements = [], produits = [], companyNom = 'TAQINOR' } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions: [], user: { company_nom: companyNom } }) => s,
      stock: (s = { mouvements, produits, loading: false, error: null }) => s,
    },
  })
}

function renderPage(opts) {
  return render(
    <Provider store={store(opts)}>
      <MemoryRouter>
        <ThemeProvider><MouvementsPage /></ThemeProvider>
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
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
})

describe('ZSTK7 — bascule Vue liste / Vue groupée', () => {
  it('la vue liste est affichée par défaut', () => {
    renderPage({ mouvements: [{ id: 1, produit: 1, produit_nom: 'Panneau', type_mouvement: 'entree', date: '2026-07-01T10:00:00Z', quantite_avant: 0, quantite_apres: 5 }] })
    expect(screen.getByRole('button', { name: /Vue groupée/ })).toBeInTheDocument()
    expect(screen.queryByText('Groupe')).toBeNull()
  })

  it('bascule vers la vue groupée et affiche les colonnes agrégées', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({
      data: [{ libelle: 'Panneau 550', entrees: 20, sorties: 5, net: 15 }],
    })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'produit' }))
    expect((await screen.findAllByText('Panneau 550'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('+20')[0]).toBeInTheDocument()
    expect(screen.getAllByText('-5')[0]).toBeInTheDocument()
    // Le bouton bascule en « Vue liste » une fois actif.
    expect(screen.getByRole('button', { name: /Vue liste/ })).toBeInTheDocument()
  })

  it('changer le regroupement recharge l\'agrégation avec le nouveau group_by', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({ data: [] })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'produit' }))
    await userEvent.click(screen.getByRole('combobox'))
    fireEvent.click(await screen.findByText('Par type'))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'type' }))
  })

  it('exporte l\'agrégation en Excel', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({ data: [] })
    stockApi.mouvementsAgregationXlsx.mockResolvedValue({ data: new Blob(['x']) })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregationXlsx).toHaveBeenCalledWith({ group_by: 'produit' }))
    clickSpy.mockRestore()
  })

  // VX81 — noms de fichiers horodatés (base_societe_AAAAMMJJ.xlsx) pour les
  // deux exports Excel de cet écran (pivot + liste) : jamais un nom nu.
  it('nomme les exports Excel avec la date + la société (VX81)', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({ data: [] })
    stockApi.mouvementsAgregationXlsx.mockResolvedValue({ data: new Blob(['x']) })
    stockApi.exportMouvementsXlsx.mockResolvedValue({ data: new Blob(['y']) })
    const anchor = document.createElement('a')
    const createSpy = vi.spyOn(document, 'createElement').mockReturnValue(anchor)
    const clickSpy = vi.spyOn(anchor, 'click').mockImplementation(() => {})
    renderPage()
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')

    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    await waitFor(() => expect(stockApi.exportMouvementsXlsx).toHaveBeenCalled())
    expect(anchor.download).toBe(`mouvements-stock_TAQINOR_${stamp}.xlsx`)

    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregationXlsx).toHaveBeenCalled())
    expect(anchor.download).toBe(`mouvements-agregation_TAQINOR_${stamp}.xlsx`)

    createSpy.mockRestore()
  })
})

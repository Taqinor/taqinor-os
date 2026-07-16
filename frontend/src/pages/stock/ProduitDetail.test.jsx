import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZPUR10 / ZSTK3 — Fiche produit : quantité « en commande » (BCF sources) +
   rapport prévisionnel (disponible + entrées/sorties attendues → solde
   projeté daté). Lecture seule, donnée interne.
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    produitPrevisionnel: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import { ProduitDetail } from './ProduitDetail.jsx'

const store = configureStore({
  reducer: { auth: (s = { role: 'Directeur', role_nom: 'Directeur', permissions: [] }) => s },
})
function wrapper({ children }) {
  // VX159 — RelationCounters rend un <Link> : un Router est requis dans le test.
  return <Provider store={store}><MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter></Provider>
}

const produit = {
  id: 7,
  nom: 'Panneau 550',
  sku: 'PAN-550',
  quantite_en_commande: 50,
  bcf_sources_en_commande: [
    { bon_commande_id: 12, reference: 'BCF-2026-0012', fournisseur_nom: 'JA Solar', quantite_restante: 50, date_livraison_prevue: '2026-08-01' },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('ZPUR10 — onglet « En commande »', () => {
  it('affiche la quantité en commande et ses BCF sources', () => {
    stockApi.produitPrevisionnel.mockResolvedValue({ data: null })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    expect(screen.getAllByText('50')[0]).toBeInTheDocument()
    expect(screen.getByText('BCF-2026-0012')).toBeInTheDocument()
    expect(screen.getByText('JA Solar')).toBeInTheDocument()
  })

  it('sans BCF ouvert : message honnête', () => {
    render(<ProduitDetail produit={{ ...produit, quantite_en_commande: 0, bcf_sources_en_commande: [] }} onClose={() => {}} />,
      { wrapper })
    expect(screen.getByText(/Aucun bon de commande ouvert/)).toBeInTheDocument()
  })
})

describe('ZSTK3 — onglet « Prévisionnel »', () => {
  it('affiche le solde projeté et la timeline', async () => {
    stockApi.produitPrevisionnel.mockResolvedValue({
      data: {
        disponible: 10, sorties_attendues: 3, solde_projete: 57,
        timeline: [
          { date: '2026-08-01', type: 'entree', quantite: 50, reference: 'BCF-2026-0012', fournisseur_nom: 'JA Solar', solde_projete: 60 },
          { date: null, type: 'sortie', quantite: -3, reference: null, fournisseur_nom: null, solde_projete: 57 },
        ],
      },
    })
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Prévisionnel' }))
    await waitFor(() => expect(stockApi.produitPrevisionnel).toHaveBeenCalledWith(7))
    expect((await screen.findAllByText('57'))[0]).toBeInTheDocument()
    expect(screen.getByText('+50')).toBeInTheDocument()
  })

  it('en cas d\'échec serveur : message indisponible honnête', async () => {
    stockApi.produitPrevisionnel.mockRejectedValue(new Error('boom'))
    render(<ProduitDetail produit={produit} onClose={() => {}} />, { wrapper })
    await userEvent.click(screen.getByRole('tab', { name: 'Prévisionnel' }))
    expect(await screen.findByText(/indisponible/)).toBeInTheDocument()
  })
})

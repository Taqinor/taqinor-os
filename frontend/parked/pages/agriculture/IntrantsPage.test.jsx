import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTAGR8 — catalogue d'intrants (dose/DAR) + ouverture du formulaire de
   traitement pour une campagne choisie. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { intrantsCreate } = vi.hoisted(() => ({
  intrantsCreate: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
}))

vi.mock('../../api/agricultureApi', () => ({
  default: {
    intrants: {
      list: () => Promise.resolve({
        data: [
          {
            id: 3, produit_nom: 'Bouillie bordelaise', categorie: 'phyto',
            categorie_display: 'Phytosanitaire', dose_reference_par_ha: '3.5',
            delai_avant_recolte_jours: 14, numero_amm: 'AMM-9988',
          },
        ],
      }),
      create: (...args) => intrantsCreate(...args),
    },
    campagnes: {
      list: () => Promise.resolve({
        data: [{ id: 7, culture: 'Vigne', date_recolte_prevue: '2026-06-01' }],
      }),
    },
    etapesCampagne: { create: vi.fn(() => Promise.resolve({ data: { id: 1 } })) },
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getProduits: () => Promise.resolve({
      data: [{ id: 55, nom: 'Cuivre 20WP' }],
    }),
  },
}))

import IntrantsPage from './IntrantsPage'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('IntrantsPage (NTAGR8)', () => {
  it('affiche le catalogue avec dose et DAR', async () => {
    withProviders(<IntrantsPage />)
    await waitFor(() => expect(screen.getAllByText('Bouillie bordelaise').length).toBeGreaterThan(0))
    expect(screen.getAllByText('14 j').length).toBeGreaterThan(0)
  })

  it('ouvre le formulaire de traitement une fois une campagne choisie', async () => {
    const user = userEvent.setup()
    withProviders(<IntrantsPage />)
    await waitFor(() => expect(screen.getAllByText('Bouillie bordelaise').length).toBeGreaterThan(0))

    expect(screen.getByRole('button', { name: /Ajouter un traitement/ })).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Campagne'), '7')
    await waitFor(() => expect(
      screen.getByRole('button', { name: /Ajouter un traitement/ }),
    ).toBeEnabled())

    await user.click(screen.getByRole('button', { name: /Ajouter un traitement/ }))
    expect(await screen.findByText('Nouvelle étape — Vigne')).toBeInTheDocument()
  })
})

// WIR141 — IntrantAgricole (catalogue agronomique) n'avait aucune UI de
// création : dialogue « Nouvel intrant » (produit stock + catégorie/dose/DAR).
describe('IntrantsPage — création d’un intrant (WIR141)', () => {
  it('crée un intrant à partir d’un produit du catalogue stock', async () => {
    const user = userEvent.setup()
    withProviders(<IntrantsPage />)
    await waitFor(() => expect(screen.getAllByText('Bouillie bordelaise').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: /Nouvel intrant/ }))
    await user.selectOptions(screen.getByLabelText('Produit (catalogue stock)'), '55')
    await user.selectOptions(screen.getByLabelText('Catégorie'), 'engrais')
    await user.click(screen.getByRole('button', { name: 'Créer l’intrant' }))

    await waitFor(() => expect(intrantsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ produit_id: '55', categorie: 'engrais' }),
    ))
  })
})

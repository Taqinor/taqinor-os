import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR111 — écran de consultation « Entrepôt » : 6 familles backend-only du
   module Magasin, un onglet par famille. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get } }))

import EntrepotConsultScreen from './EntrepotConsultScreen'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EntrepotConsultScreen (WIR111)', () => {
  it('rend les 6 onglets et charge les catégories par défaut', async () => {
    get.mockResolvedValue({ data: [] })
    get.mockImplementation((url) => {
      if (url === '/installations/categories-stockage/') {
        return Promise.resolve({ data: [{ id: 1, nom: 'Palettes', poids_max_kg: 500, qte_max: 10, melange_autorise: false }] })
      }
      return Promise.resolve({ data: [] })
    })
    render(<EntrepotConsultScreen />)
    expect(screen.getByRole('tab', { name: 'Catégories de stockage' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Matériels consignés' })).toBeInTheDocument()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/installations/categories-stockage/'))
    expect(await screen.findByText('Palettes')).toBeInTheDocument()
  })

  it('charge la famille séries quand on change d\'onglet', async () => {
    get.mockImplementation((url) => {
      if (url === '/installations/series-entrepot/') {
        return Promise.resolve({ data: [{ id: 9, numero_serie: 'SN-42', produit_nom: 'Onduleur', statut: 'en_stock', statut_display: 'En stock' }] })
      }
      return Promise.resolve({ data: [] })
    })
    const user = userEvent.setup()
    render(<EntrepotConsultScreen />)
    await user.click(screen.getByRole('tab', { name: 'Séries entrepôt' }))
    await waitFor(() => expect(get).toHaveBeenCalledWith('/installations/series-entrepot/'))
    expect(await screen.findByText('SN-42')).toBeInTheDocument()
  })
})

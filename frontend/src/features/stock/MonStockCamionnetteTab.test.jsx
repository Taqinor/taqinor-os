import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MonStockCamionnetteTab from './MonStockCamionnetteTab'

/* NTFSM20 — onglet « Mon stock camionnette » : le technicien voit UNIQUEMENT
   le stock de sa propre camionnette (résolue côté serveur, jamais un
   emplacement choisi côté client) ; sans camionnette affectée l'état reste
   propre (pas d'erreur). */

const api = vi.hoisted(() => ({
  getMonStockCamionnette: vi.fn(),
  signalerManquantVanStock: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/stockApi', () => ({ default: api }))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MonStockCamionnetteTab', () => {
  it("affiche un état vide propre sans camionnette affectée", async () => {
    api.getMonStockCamionnette.mockResolvedValueOnce({
      data: { emplacement: null, produits: [] },
    })
    render(<MonStockCamionnetteTab />)
    await waitFor(() => {
      expect(screen.getByText(/aucune camionnette affectée/i)).toBeInTheDocument()
    })
  })

  it('liste uniquement les produits de la camionnette du technicien', async () => {
    api.getMonStockCamionnette.mockResolvedValueOnce({
      data: {
        emplacement: { id: 7, nom: 'Camionnette Ahmed' },
        produits: [
          { produit_id: 1, nom: 'Onduleur Huawei 5kW', sku: 'OND-5K', quantite: 1, seuil_min: 2, seuil_max: 4 },
          { produit_id: 2, nom: 'Batterie 5kWh', sku: 'BAT-5', quantite: 6, seuil_min: 2, seuil_max: 8 },
        ],
      },
    })
    render(<MonStockCamionnetteTab />)
    await waitFor(() => {
      expect(screen.getByText('Camionnette Ahmed')).toBeInTheDocument()
    })
    expect(screen.getByText('Onduleur Huawei 5kW')).toBeInTheDocument()
    expect(screen.getByText('Batterie 5kWh')).toBeInTheDocument()
    // Produit sous son seuil_min (1 < 2) → badge « Sous seuil ».
    expect(screen.getByText('Sous seuil')).toBeInTheDocument()
  })

  it('le bouton « Signaler manquant » appelle la bonne action', async () => {
    api.getMonStockCamionnette.mockResolvedValueOnce({
      data: {
        emplacement: { id: 7, nom: 'Camionnette Ahmed' },
        produits: [
          { produit_id: 1, nom: 'Onduleur Huawei 5kW', sku: 'OND-5K', quantite: 1, seuil_min: 2, seuil_max: 4 },
        ],
      },
    })
    const user = userEvent.setup()
    render(<MonStockCamionnetteTab />)
    await waitFor(() => {
      expect(screen.getByText('Onduleur Huawei 5kW')).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /signaler manquant/i }))
    await waitFor(() => {
      expect(api.signalerManquantVanStock).toHaveBeenCalledWith(1)
    })
  })
})

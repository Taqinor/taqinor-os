import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT129 — Prix contractuels négociés par client (NTCPQ5) : un onglet sur
   la fiche client liste les prix négociés avec leurs dates de validité et
   permet d'en créer un. */

const { getPrixContractuels, createPrixContractuel } = vi.hoisted(() => ({
  getPrixContractuels: vi.fn(),
  createPrixContractuel: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
}))

vi.mock('../../api/cpqApi', () => ({
  default: {
    getPrixContractuels: (...args) => getPrixContractuels(...args),
    createPrixContractuel: (...args) => createPrixContractuel(...args),
  },
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getProduits: () => Promise.resolve({
      data: [{ id: 21, nom: 'Panneau 550W' }, { id: 22, nom: 'Onduleur 5kW' }],
    }),
  },
}))

import ClientPrixContractuelsTab from './ClientPrixContractuelsTab'

beforeEach(() => {
  vi.clearAllMocks()
  getPrixContractuels.mockResolvedValue({
    data: [
      { id: 1, client: 11, produit: 21, prix_ht: '1200.00', date_debut: '2026-01-01', date_fin: '2026-12-31', motif: 'Volume', est_actif: true },
      { id: 2, client: 99, produit: 22, prix_ht: '9000.00', date_debut: null, date_fin: null, motif: '', est_actif: false },
    ],
  })
})

describe('ClientPrixContractuelsTab (PACT129)', () => {
  it('ne montre que les prix négociés du client courant', async () => {
    render(<ClientPrixContractuelsTab clientId={11} />)
    expect(await screen.findByText('Panneau 550W')).toBeInTheDocument()
    expect(screen.queryByText('Onduleur 5kW')).not.toBeInTheDocument()
  })

  it('crée un prix négocié pour le client courant', async () => {
    const user = userEvent.setup()
    render(<ClientPrixContractuelsTab clientId={11} />)
    await screen.findByText('Panneau 550W')

    await user.selectOptions(screen.getByLabelText('Produit'), '22')
    await user.type(screen.getByLabelText('Prix HT négocié'), '8500')
    await user.click(screen.getByRole('button', { name: 'Créer le prix négocié' }))

    await waitFor(() => expect(createPrixContractuel).toHaveBeenCalledWith(expect.objectContaining({
      client: 11, produit: '22', prix_ht: '8500',
    })))
  })

  it('affiche le message serveur exact si la lecture est refusée (réservé aux profils élevés)', async () => {
    getPrixContractuels.mockRejectedValueOnce({
      response: { data: { detail: "Vous n'avez pas la permission d'effectuer cette action." } },
    })
    render(<ClientPrixContractuelsTab clientId={11} />)
    expect(await screen.findByText("Vous n'avez pas la permission d'effectuer cette action.")).toBeInTheDocument()
  })
})

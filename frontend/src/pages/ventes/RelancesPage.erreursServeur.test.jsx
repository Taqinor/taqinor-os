import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* AFAC61 — les refus serveur des gestes de relance s'AFFICHENT (raison réelle),
   la modale reste ouverte, le lot donne un bilan « n consignée(s), m refusée(s) ». */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ROWS = [
  { id: 1, reference: 'FAC-001', client_id: 42, client_nom: 'ACME SARL', montant_du: 1000, niveau: null },
  { id: 2, reference: 'FAC-002', client_id: 99, client_nom: 'Globex', montant_du: 2000, niveau: null },
]
const RAISON = 'Statut Payée : la relance ne concerne qu\'une facture ouverte et due.'
const refus = () => ({ response: { status: 400, data: { detail: RAISON } } })

vi.mock('../../api/ventesApi', () => ({
  default: {
    getRelances: vi.fn(() => Promise.resolve({ data: ROWS })),
    relancerFacture: vi.fn(),
  },
}))
vi.mock('../../api/axios', async () => (await import('../../test/mocksVentesEcrans.js')).axiosNu())
vi.mock('../../ui/confirm', async () => (await import('../../test/mocksVentesEcrans.js')).confirmAccepte())

import api from '../../api/axios'
import ventesApi from '../../api/ventesApi'
import RelancesPage from './RelancesPage'

beforeEach(() => {
  api.get.mockImplementation((url) => Promise.resolve({
    data: url === '/ventes/relances/' ? ROWS : [],
  }))
  ventesApi.getRelances.mockResolvedValue({ data: ROWS })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = () => render(<MemoryRouter><RelancesPage /></MemoryRouter>)

describe('RelancesPage — AFAC61 : refus serveur affichés', () => {
  it('« Consigner » refusée : la raison s\'affiche, la modale reste ouverte', async () => {
    const user = userEvent.setup()
    ventesApi.relancerFacture.mockRejectedValue(refus())
    renderPage()
    await screen.findByText('ACME SARL')
    await user.click(screen.getAllByRole('button', { name: 'Relancer' })[0])
    await screen.findByRole('checkbox', { name: /Envoyer l'email au client/ })
    await user.click(screen.getByRole('button', { name: 'Consigner' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(RAISON)
    // La modale est toujours là (son bouton « Consigner » aussi).
    expect(screen.getByRole('button', { name: 'Consigner' })).toBeInTheDocument()
  })

  it('promesse refusée : la raison serveur s\'affiche', async () => {
    const user = userEvent.setup()
    api.post.mockRejectedValue(refus())
    renderPage()
    await screen.findByText('ACME SARL')
    await user.click(screen.getByRole('button', { name: /Plus d'actions — FAC-001/ }))
    await user.click(await screen.findByRole('menuitem', { name: /Promesse de paiement/ }))
    await user.click(screen.getByRole('button', { name: 'Enregistrer la promesse' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(RAISON)
  })

  it('lot [ouverte, soldée] : bilan « 1 consignée, 1 refusée : raison », la sélection garde la refusée', async () => {
    const user = userEvent.setup()
    ventesApi.relancerFacture.mockImplementation((id) => (
      id === '2' || id === 2 ? Promise.reject(refus()) : Promise.resolve({ data: {} })))
    renderPage()
    await screen.findByText('ACME SARL')
    await user.click(screen.getByRole('checkbox', { name: 'Sélectionner FAC-001' }))
    await user.click(screen.getByRole('checkbox', { name: 'Sélectionner FAC-002' }))
    await user.click(screen.getByRole('button', { name: /Relancer la sélection/ }))
    await user.click(await screen.findByRole('menuitem', { name: 'Consigner uniquement' }))

    const bilan = await screen.findByRole('status')
    expect(bilan).toHaveTextContent('1 relance(s) consignée(s), 1 refusée(s)')
    expect(bilan).toHaveTextContent(RAISON)
    // La facture refusée reste sélectionnée, la réussie ne l'est plus.
    await waitFor(() => {
      expect(screen.getByRole('checkbox', { name: 'Sélectionner FAC-002' })).toBeChecked()
      expect(screen.getByRole('checkbox', { name: 'Sélectionner FAC-001' })).not.toBeChecked()
    })
    expect(within(bilan).queryByText(/undefined/)).toBeNull()
  })
})

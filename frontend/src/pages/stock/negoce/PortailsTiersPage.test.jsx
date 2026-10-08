import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   ASTK223 — liens 3PL : générer / lister / révoquer. Réponses = contrat
   committé `negoce_consignation_rfa.json` (ASTK164) ; seul axios est mocké.
   ========================================================================== */

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

import api from '../../../api/axios'
import PortailsTiersPage from './PortailsTiersPage'

const P = documentContrat('stock', 'negoce_consignation_rfa').routes.portails_tiers
const REVOQUE = { ...P.exemple_element, revoked: true, est_valide: false }

let etat
beforeEach(() => {
  vi.clearAllMocks()
  etat = P.exemple
  api.get.mockImplementation(() => Promise.resolve({ data: etat }))
})
afterEach(() => { cleanup() })

const monter = () => render(<MemoryRouter><PortailsTiersPage /></MemoryRouter>)

describe('ASTK223 — PortailsTiersPage', () => {
  it('liste les liens avec leur état actif / révoqué', async () => {
    monter()
    expect(await screen.findByText('Client Alpha')).toBeInTheDocument()
    expect(screen.getByText('Actif')).toBeInTheDocument()
    expect(screen.getByText(/\/depot-tiers\/tk_9f2c/)).toBeInTheDocument()
  })

  it('générer puis révoquer un lien', async () => {
    api.post.mockImplementation(() => Promise.resolve({ data: P.exemple_element }))
    api.patch.mockImplementation(() => {
      etat = { ...P.exemple, results: [REVOQUE] }
      return Promise.resolve({ data: REVOQUE })
    })
    monter()
    await screen.findByText('Client Alpha')
    fireEvent.change(screen.getByLabelText('Nom du dépositaire'), { target: { value: 'Client Alpha' } })
    fireEvent.click(screen.getByRole('button', { name: /Générer un lien/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/stock/portails-tiers/', { tiers_nom: 'Client Alpha' }))
    fireEvent.click(await screen.findByRole('button', { name: /Révoquer/i }))
    fireEvent.click(await screen.findByRole('button', { name: /Confirmer/i }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/stock/portails-tiers/2/', { revoked: true }))
    expect(await screen.findByText('Révoqué')).toBeInTheDocument()
  })

  it('une erreur serveur de génération est affichée telle quelle', async () => {
    api.post.mockRejectedValue({ response: { status: 400, data: { tiers_nom: ['Ce champ est obligatoire.'] } } })
    monter()
    await screen.findByText('Client Alpha')
    fireEvent.change(screen.getByLabelText('Nom du dépositaire'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: /Générer un lien/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce champ est obligatoire.')
  })
})

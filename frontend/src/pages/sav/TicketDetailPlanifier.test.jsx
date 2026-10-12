import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* WIR29 — bouton « Planifier une intervention en un clic » sur le détail du
   ticket SAV : POST tickets/{id}/planifier-intervention/ (installations
   services côté serveur), formulaire manuel conservé en option. savApi + api
   (axios direct) + installationsApi mockés — aucun réseau réel. */

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) =>
  (await import('./__tests__/ticketDetailTestKit')).ticketsSliceNoopMock(importOriginal))

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailTestKit')).savApiDetailMock({
  getTicket: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: { intervention_id: 77, ticket_statut: 'planifie' } })),
  },
}))

vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailTestKit')).installationsApiVideMock())

import { TicketDetail } from './TicketsPage'
import { renderTicketDetail } from './__tests__/ticketDetailTestKit'
import api from '../../api/axios'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderDetail = (ticket, opts) => renderTicketDetail(TicketDetail, ticket, opts)

const baseTicket = {
  id: 1, reference: 'SAV-1', statut: 'nouveau', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null,
  installation: 12, installation_reference: 'CH-2026-07-0001',
}

describe('TicketDetail — WIR29 planification en un clic', () => {
  it('affiche le bouton one-click à côté du formulaire manuel conservé', async () => {
    renderDetail(baseTicket)
    expect(await screen.findByRole('button', { name: /Planifier une intervention en un clic/ }))
      .toBeInTheDocument()
    // Le formulaire manuel reste disponible en option.
    expect(screen.getByRole('button', { name: /Ajouter une intervention/ })).toBeInTheDocument()
  })

  it('crée l\'intervention pré-remplie via POST planifier-intervention', async () => {
    renderDetail(baseTicket)
    const btn = await screen.findByRole('button', { name: /Planifier une intervention en un clic/ })
    fireEvent.click(btn)
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/sav/tickets/1/planifier-intervention/'))
  })
})

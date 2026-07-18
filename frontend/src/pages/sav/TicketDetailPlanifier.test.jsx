import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WIR29 — bouton « Planifier une intervention en un clic » sur le détail du
   ticket SAV : POST tickets/{id}/planifier-intervention/ (installations
   services côté serveur), formulaire manuel conservé en option. savApi + api
   (axios direct) + installationsApi mockés — aucun réseau réel. */

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    updateTicket: () => {
      const action = { type: 'sav/updateTicket/noop' }
      action.unwrap = () => Promise.resolve({})
      return action
    },
  }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicket: vi.fn(() => Promise.resolve({ data: {} })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
    post: vi.fn(() => Promise.resolve({ data: { intervention_id: 77, ticket_statut: 'planifie' } })),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'
import api from '../../api/axios'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: {
      tickets: (state = { items: [] }) => state,
      auth: (state = { role: 'admin', permissions: [] }) => state,
    },
  })
}

function renderDetail(ticket, opts = {}) {
  const store = makeStore()
  return render(
    <Provider store={store}>
      <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} {...opts} />
    </Provider>,
  )
}

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

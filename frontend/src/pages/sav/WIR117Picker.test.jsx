import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* WIR117/XSAV25 — picker de pièces du ticket : les pièces compatibles avec
   l'équipement lié sont proposées EN PREMIER (groupe dédié). */

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    updateTicket: () => { const a = { type: 'noop' }; a.unwrap = () => Promise.resolve({}); return a },
  }
})

vi.mock('../../api/savApi', () => ({
  default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getPiecesCompatibles: vi.fn(() => Promise.resolve({
      data: { results: [{ piece_id: 7, nom: 'Fusible 16A', sku: 'F16', note: '' }] },
    })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'
import savApi from '../../api/savApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({
    reducer: {
      tickets: (s = { items: [] }) => s,
      auth: (s = { role: 'admin', permissions: [] }) => s,
    },
  })
}

const ticket = {
  id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', installation: 5, equipement: 9,
}

describe('WIR117 — picker de pièces compatibles d\'abord', () => {
  it('charge les pièces compatibles et les propose sous un groupe dédié', async () => {
    const user = userEvent.setup()
    render(
      <Provider store={makeStore()}>
        <MemoryRouter>
          <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} />
        </MemoryRouter>
      </Provider>,
    )

    await waitFor(() => expect(savApi.getPiecesCompatibles).toHaveBeenCalledWith(1))

    const combos = screen.getAllByRole('combobox')
    const produitCombo = combos.find((c) => (c.textContent || '').includes('Produit'))
    expect(produitCombo).toBeTruthy()
    await user.click(produitCombo)

    expect(await screen.findByText("Compatibles avec l'équipement")).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Fusible 16A/ })).toBeInTheDocument()
  })
})

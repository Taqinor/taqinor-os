import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// ASAV3 — une seule porte de facturation sur la fiche ticket. Faux serveur en
// mémoire qui applique la décision d'ASAV2 (couvert → 0 MAD, récidive → 403
// sans override d'un responsable) ; aucune assertion sur les arguments d'appel.

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

const serveur = vi.hoisted(() => ({ factures: [] }))

vi.mock('../../api/savApi', () => {
  const facturer = (nonFacturable, override) => {
    if (nonFacturable && !override) {
      return Promise.reject({ response: { status: 403, data: {
        detail: 'Ticket récidive marqué non-facturable — override responsable requis.' } } })
    }
    const f = { facture_id: serveur.factures.length + 1, facture_reference: 'F-' + (serveur.factures.length + 1), couverture: nonFacturable ? 'facturable' : 'contrat', total: nonFacturable ? 5000 : 0 }
    serveur.factures.push(f)
    return Promise.resolve({ data: f })
  }
  return { default: {
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    facturerTicket: vi.fn((id, override) => facturer(id === 2, !!override)),
    rapportPdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  } }
})
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({ default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) } }))

import { TicketDetail } from './TicketsPage'

afterEach(() => { cleanup(); serveur.factures.length = 0 })

function renderDetail(ticket, role) {
  const store = configureStore({ reducer: {
    tickets: (state = { items: [] }) => state,
    auth: (state = { role, permissions: [] }) => state,
  } })
  return render(<Provider store={store}>
    <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} />
  </Provider>)
}
const base = (id) => ({ id, reference: 'SAV-' + id, statut: 'en_cours', type: 'correctif',
  priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
  couverture: 'a_determiner', devis_id_ext: null, facture_id_ext: null })

describe('TicketDetail — ASAV3 une seule porte de facture', () => {
  it('rend un seul bouton de facturation, jamais « Générer facture »', async () => {
    renderDetail(base(1), 'admin')
    await screen.findAllByRole('button', { name: /Facturer/ })
    expect(screen.getAllByRole('button', { name: /Facturer/ })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: /Générer facture/ })).toBeNull()
  })

  it('ticket couvert : une facture à 0 MAD, une seule', async () => {
    renderDetail(base(1), 'admin')
    fireEvent.click(await screen.findByRole('button', { name: /^Facturer$/ }))
    await waitFor(() => expect(serveur.factures).toHaveLength(1))
    expect(serveur.factures[0].total).toBe(0)
  })

  it('récidive, responsable : refus puis « Facturer quand même » crée la facture', async () => {
    renderDetail(base(2), 'admin')
    fireEvent.click(await screen.findByRole('button', { name: /^Facturer$/ }))
    expect(await screen.findByText(/override responsable requis/i)).toBeInTheDocument()
    expect(serveur.factures).toHaveLength(0)
    fireEvent.click(await screen.findByRole('button', { name: /Facturer quand même/ }))
    await waitFor(() => expect(serveur.factures).toHaveLength(1))
  })

  it('récidive, technicien : refus sans bouton d\'override', async () => {
    renderDetail(base(2), 'technicien')
    fireEvent.click(await screen.findByRole('button', { name: /^Facturer$/ }))
    expect(await screen.findByText(/override responsable requis/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Facturer quand même/ })).toBeNull()
    expect(serveur.factures).toHaveLength(0)
  })
})

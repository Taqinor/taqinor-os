import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'

// ASAV3 — une seule porte de facturation sur la fiche ticket. Faux serveur en
// mémoire qui applique la décision d'ASAV2 (couvert → 0 MAD, récidive → 403
// sans override d'un responsable) ; aucune assertion sur les arguments d'appel.

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io()))

const serveur = vi.hoisted(() => ({ factures: [] }))

vi.mock('../../api/savApi', async () => {
  const facturer = (nonFacturable, override) => {
    if (nonFacturable && !override) {
      return Promise.reject({ response: { status: 403, data: {
        detail: 'Ticket récidive marqué non-facturable — override responsable requis.' } } })
    }
    const f = { facture_id: serveur.factures.length + 1, facture_reference: 'F-' + (serveur.factures.length + 1), couverture: nonFacturable ? 'facturable' : 'contrat', total: nonFacturable ? 5000 : 0 }
    serveur.factures.push(f)
    return Promise.resolve({ data: f })
  }
  return (await import('./__tests__/ticketDetailMocks.js')).savApiMock({
    facturerTicket: vi.fn((id, override) => facturer(id === 2, !!override)),
    rapportPdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
  })
})
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore, TICKET_BASE } from './__tests__/ticketDetailMocks.js'

afterEach(() => { cleanup(); serveur.factures.length = 0 })

function renderDetail(ticket, role) {
  return render(<Provider store={ticketStore(role)}>
    <TicketDetail ticket={ticket} onClose={() => {}} onSaved={() => {}} />
  </Provider>)
}
const base = (id) => ({ ...TICKET_BASE, id, reference: 'SAV-' + id })

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

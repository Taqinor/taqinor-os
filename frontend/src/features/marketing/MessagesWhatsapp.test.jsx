import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PACT108 — journal LECTURE SEULE des messages WhatsApp entrants
   (MessageWhatsAppEntrantViewSet, /marketing/messages-whatsapp/,
   ReadOnlyModelViewSet côté serveur). Forme mockée = exactement
   MessageWhatsAppEntrantSerializer (id/wa_message_id/expediteur/nom_profil/
   texte/lead_id/traite/date_reception, tous read_only côté serveur). */

const mocks = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    messagesWhatsapp: { list: mocks.list },
  },
}))

import MessagesWhatsapp from './MessagesWhatsapp'

const renderScreen = () => render(<MemoryRouter><MessagesWhatsapp /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, wa_message_id: 'wamid.abc', expediteur: '+212612345678',
      nom_profil: 'Karim B.', texte: 'Bonjour, je veux un devis solaire',
      lead_id: 88, traite: true, date_reception: '2026-08-01T09:00:00Z' },
    { id: 2, wa_message_id: 'wamid.def', expediteur: '+212661112233',
      nom_profil: '', texte: 'Prix pompage agricole ?',
      lead_id: null, traite: false, date_reception: '2026-08-02T14:30:00Z' },
  ] })
})

describe('MessagesWhatsapp (PACT108)', () => {
  it('affiche le journal des messages WhatsApp entrants', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByText('+212612345678')).toBeInTheDocument()
    expect(screen.getByText('Karim B.')).toBeInTheDocument()
    expect(screen.getByText('Bonjour, je veux un devis solaire')).toBeInTheDocument()
    expect(screen.getByText('#88')).toBeInTheDocument()
    expect(screen.getAllByTestId('wa-message-row').length).toBe(2)
  })

  it('affiche « Traité » / « Non traité » tels que renvoyés par le serveur', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('wa-message-row')
    expect(rows[0]).toHaveTextContent('Traité')
    expect(rows[1]).toHaveTextContent('Non traité')
  })

  it('un message sans lead affiche un tiret, jamais un lead fictif', async () => {
    renderScreen()
    const rows = await screen.findAllByTestId('wa-message-row')
    expect(rows[1]).toHaveTextContent('Prix pompage agricole ?')
    expect(rows[1]).not.toHaveTextContent('#null')
  })

  it('reste purement en lecture : aucun bouton d\'action sur les lignes', async () => {
    renderScreen()
    await screen.findAllByTestId('wa-message-row')
    expect(screen.queryAllByRole('button').length).toBe(0)
  })

  it('affiche un état vide sans message', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByText('Aucun message WhatsApp reçu')).toBeInTheDocument()
  })
})

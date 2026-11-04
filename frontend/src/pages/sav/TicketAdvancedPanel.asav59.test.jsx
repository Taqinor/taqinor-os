import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

// ASAV59 — après « Fusionner un ticket doublon », la fiche du principal se
// recharge (pièces du doublon visibles) et la liste est prévenue (onSaved).
// Faux serveur qui applique la fusion : les pièces du doublon passent au
// principal, le doublon est annulé.

const serveur = vi.hoisted(() => ({
  pieces: [{ id: 1, produit_nom: 'Fusible 10A', quantite: '1' }],
  doublonAnnule: false,
  deplace: false, // ASAV126 — pièce jointe + item de checklist passés au principal
}))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io()))
vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock({
  getTicket: vi.fn(() => Promise.resolve({ data: { ...TICKET_BASE } })),
  fusionnerTicket: vi.fn(() => {
    serveur.pieces = [...serveur.pieces, { id: 2, produit_nom: 'Câble MC4 (du doublon)', quantite: '2' }]
    serveur.doublonAnnule = true
    serveur.deplace = true
    return Promise.resolve({ data: {} })
  }),
  getTicketPieces: vi.fn(() => Promise.resolve({ data: serveur.pieces.map((p) => ({ ...p })) })),
  getTicketChecklist: vi.fn(() => Promise.resolve({
    data: serveur.deplace ? [{ id: 9, libelle: 'Serrage MC4', fait: false }] : [] })),
}))
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock(
  (url) => Promise.resolve({
    data: url === '/records/attachments/' && serveur.deplace
      ? [{ id: 5, filename: 'photo-onduleur.jpg', url: '/x', mime_type: 'application/pdf' }]
      : [],
  })))
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore, TICKET_BASE } from './__tests__/ticketDetailMocks.js'

describe('TicketDetail — ASAV59 rechargement après fusion', () => {
  it('les pièces du doublon apparaissent et la liste est prévenue', async () => {
    const onSaved = vi.fn()
    render(<Provider store={ticketStore('responsable')}><MemoryRouter>
      <TicketDetail ticket={TICKET_BASE} onClose={() => {}} onSaved={onSaved} />
    </MemoryRouter></Provider>)
    expect(await screen.findByText(/Fusible 10A/)).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('ID du ticket doublon'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fusionner' }))
    expect(await screen.findByText(/Câble MC4 \(du doublon\)/)).toBeInTheDocument()
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(serveur.doublonAnnule).toBe(true)
  }, 60000)

  it('ASAV126 — pièce jointe et checklist du doublon visibles sans recharger la page', async () => {
    serveur.deplace = false
    render(<Provider store={ticketStore('responsable')}><MemoryRouter>
      <TicketDetail ticket={TICKET_BASE} onClose={() => {}} onSaved={() => {}} />
    </MemoryRouter></Provider>)
    expect(await screen.findByText(/Fusible 10A/)).toBeInTheDocument()
    expect(screen.queryByText(/photo-onduleur\.jpg/)).toBeNull()
    fireEvent.change(screen.getByPlaceholderText('ID du ticket doublon'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fusionner' }))
    expect(await screen.findByText(/photo-onduleur\.jpg/)).toBeInTheDocument()
    expect(await screen.findByText(/Serrage MC4/)).toBeInTheDocument()
  }, 60000)
})

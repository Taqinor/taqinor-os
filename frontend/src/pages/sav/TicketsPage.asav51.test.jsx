import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

// ASAV51 — le catalogue de 102 produits est servi paginé à 50 : le 102e doit
// se choisir dans « Retirer une pièce » de la fiche ticket.

const serveur = vi.hoisted(() => ({ corps: [], pagesLues: [] }))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__testutils__/ticketDetailMocks.js')).ticketsSliceMock(await io()))
vi.mock('../../api/savApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).savApiMock({
  retirerTicketPiece: vi.fn((id, body) => { serveur.corps.push(body); return Promise.resolve({ data: {} }) }),
}))
vi.mock('../../api/axios', async () => (await import('./__testutils__/ticketDetailMocks.js')).axiosMock((url, cfg) => {
  if (url !== '/stock/produits/') return Promise.resolve({ data: [] })
  const page = Number(cfg?.params?.page ?? 1)
  serveur.pagesLues.push(page)
  const results = []
  for (let i = (page - 1) * 50 + 1; i <= Math.min(102, page * 50); i += 1) {
    results.push({ id: i, nom: `Produit ${i}`, sku: `P${i}` })
  }
  return Promise.resolve({ data: { count: 102, next: null, results } })
}))
vi.mock('../../api/installationsApi', async () => (await import('./__testutils__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore, TICKET_BASE } from './__testutils__/ticketDetailMocks.js'

describe('TicketDetail — ASAV51 catalogue complet', () => {
  it('le 102e produit se choisit dans « Retirer une pièce »', async () => {
    const user = userEvent.setup()
    render(<Provider store={ticketStore('admin')}><MemoryRouter>
      <TicketDetail ticket={TICKET_BASE} onClose={() => {}} onSaved={() => {}} />
    </MemoryRouter></Provider>)
    await waitFor(() => expect(serveur.pagesLues).toEqual(expect.arrayContaining([1, 2, 3])))
    await user.click(screen.getByRole('combobox', { name: 'Produit à retirer' }))
    await user.click(await screen.findByText('Produit 102 (P102)'))
    await user.click(screen.getByRole('button', { name: /Retirer une pièce/ }))
    await waitFor(() => expect(serveur.corps).toHaveLength(1))
    expect(serveur.corps[0].produit).toBe('102')
  }, 60000)
})

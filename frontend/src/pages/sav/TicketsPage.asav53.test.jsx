import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

// ASAV53 — plus de garde locale « Stock insuffisant » : le serveur (ERR80)
// décide. Faux serveur qui applique ERR80 sur SON stock : pièce compatible
// 900 (stock 5, absente de la liste produits chargée) acceptée ; pièce 7
// (stock 0) refusée en 400 avec le message du serveur.

const serveur = vi.hoisted(() => ({ stock: { 900: 5, 7: 0 }, pieces: [], appels: 0 }))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io()))
vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock({
  getTicketPieces: vi.fn(() => Promise.resolve({ data: serveur.pieces })),
  getPiecesCompatibles: vi.fn(() => Promise.resolve({
    data: { results: [{ piece_id: 900, nom: 'Ventilateur', sku: 'VENT' }] } })),
  addTicketPiece: vi.fn((id, body) => {
    serveur.appels += 1
    const pid = Number(body.produit)
    const qte = Number(body.quantite)
    if (body.decrement && (serveur.stock[pid] ?? 0) < qte) {
      return Promise.reject({ response: { status: 400, data: {
        detail: `Stock insuffisant (ERR80) : ${serveur.stock[pid] ?? 0} disponible.` } } })
    }
    if (body.decrement) serveur.stock[pid] -= qte
    serveur.pieces.push({ id: serveur.pieces.length + 1, produit_nom: pid === 900 ? 'Ventilateur' : 'Autre', quantite: body.quantite })
    return Promise.resolve({ data: {}, status: 201 })
  }),
}))
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock((url) => Promise.resolve({
  // La liste produits chargée ne contient PAS la pièce 900 et donne 0 au 7.
  data: url === '/stock/produits/' ? [{ id: 7, nom: 'Autre', sku: 'AUT', quantite_stock: 0 }] : [] })))
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore, TICKET_BASE } from './__tests__/ticketDetailMocks.js'

function rendre() {
  return render(<Provider store={ticketStore('admin')}><MemoryRouter>
    <TicketDetail ticket={TICKET_BASE} onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV53 garde de stock côté serveur', () => {
  it('pièce compatible absente de la liste : appel serveur, acceptée ; pièce à 0 : message ERR80 du serveur', async () => {
    const user = userEvent.setup()
    rendre()
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Produit de la pièce' })).toBeInTheDocument())
    await user.click(screen.getByRole('checkbox'))

    await user.click(screen.getByRole('combobox', { name: 'Produit de la pièce' }))
    await user.click(await screen.findByText(/★ Ventilateur/))
    await user.click(screen.getByRole('button', { name: /Ajouter la pièce/ }))
    await waitFor(() => expect(serveur.pieces).toHaveLength(1))
    expect(serveur.stock[900]).toBe(4)

    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('combobox', { name: 'Produit de la pièce' }))
    await user.click(await screen.findByText('Autre (AUT)'))
    await user.click(screen.getByRole('button', { name: /Ajouter la pièce/ }))
    expect(await screen.findByText(/Stock insuffisant \(ERR80\)/)).toBeInTheDocument()
    expect(serveur.appels).toBe(2)
  }, 90000)
})

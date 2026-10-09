import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'

// ASAV41 — plus de champ « Coût (interne) » saisissable : le serveur (ASEC34)
// jette `cout` ; l'écran l'affiche en lecture seule aux seuls responsables.
// Faux serveur qui applique les `read_only_fields` réels (cout ignoré).

const serveur = vi.hoisted(() => ({
  ticket: { id: 1, reference: 'SAV-1', statut: 'en_cours', type: 'correctif',
    priorite: 'normale', sous_garantie: 'non', sous_garantie_effectif: 'non',
    couverture: 'a_determiner', description: 'avant', cout: '100.00',
    devis_id_ext: null, facture_id_ext: null, instructions: '' },
  patchs: [],
}))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io(), ({ data }) => {
  serveur.patchs.push(data)
  const { cout: _ignore, ...modifiable } = data // read_only_fields : cout jeté
  serveur.ticket = { ...serveur.ticket, ...modifiable }
  return serveur.ticket
}))

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock())
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore } from './__tests__/ticketDetailMocks.js'

afterEach(() => { cleanup(); serveur.patchs.length = 0 })

function renderDetail(role) {
  return render(<Provider store={ticketStore(role)}><MemoryRouter>
    <TicketDetail ticket={serveur.ticket} onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

describe('TicketDetail — ASAV41 coût interne en lecture seule', () => {
  it('administrateur : coût affiché en lecture seule, aucun champ éditable, PATCH sans cout', async () => {
    renderDetail('admin')
    expect(await screen.findByTestId('cout-interne')).toHaveTextContent('Coût interne : 100,00 MAD')
    expect(screen.queryByLabelText(/Coût \(interne\)/)).toBeNull()
    expect(screen.queryByText('Coût (interne)')).toBeNull()
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: 'après' } })
    fireEvent.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    await waitFor(() => expect(serveur.patchs).toHaveLength(1))
    expect('cout' in serveur.patchs[0]).toBe(false)
    expect(serveur.ticket.description).toBe('après')
    expect(serveur.ticket.cout).toBe('100.00')
  }, 60000)

  it('technicien : ne voit pas le coût interne', async () => {
    renderDetail('technicien')
    await screen.findByText('Ticket SAV — SAV-1', { exact: false })
    expect(screen.queryByTestId('cout-interne')).toBeNull()
  }, 60000)
})

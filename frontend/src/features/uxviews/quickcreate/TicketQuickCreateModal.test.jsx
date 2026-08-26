// WIR178 — Création rapide de ticket SAV (⌘K) : le payload sans client était
// un 400 GARANTI (Ticket.client est un FK non nullable côté serveur). Le
// sélecteur Client est désormais obligatoire ; on vérifie le CORPS RÉEL
// envoyé à savApi.createTicket (objectContaining({client})), pas seulement
// que l'appel a eu lieu.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { createTicket } = vi.hoisted(() => ({
  createTicket: vi.fn(() => Promise.resolve({ data: { id: 42, reference: 'SAV-0042' } })),
}))
vi.mock('../../../api/savApi', () => ({
  default: { createTicket: (...args) => createTicket(...args) },
}))

const { searchClients } = vi.hoisted(() => ({ searchClients: vi.fn() }))
vi.mock('../../../api/crmApi', () => ({
  default: { searchClients: (...args) => searchClients(...args) },
}))

import TicketQuickCreateModal from './TicketQuickCreateModal'

beforeEach(() => {
  vi.clearAllMocks()
  searchClients.mockResolvedValue({
    data: { results: [{ id: 7, nom: 'Client SAV Test', source: 'client' }] },
  })
})
afterEach(() => cleanup())

describe('TicketQuickCreateModal (WIR178)', () => {
  it('bloque la soumission tant qu\'aucun client n\'est sélectionné', async () => {
    const user = userEvent.setup()
    render(<TicketQuickCreateModal open onClose={() => {}} onCreated={() => {}} />)

    await user.type(screen.getByLabelText('Description'), 'Panne onduleur')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    expect(await screen.findByText('Le client est requis.')).toBeInTheDocument()
    expect(createTicket).not.toHaveBeenCalled()
  })

  it('crée le ticket avec le client sélectionné dans le corps réel (client obligatoire)', async () => {
    const user = userEvent.setup()
    const onCreated = vi.fn()
    render(<TicketQuickCreateModal open onClose={() => {}} onCreated={onCreated} />)

    await user.click(screen.getByRole('combobox', { name: 'Client' }))
    await user.type(screen.getByPlaceholderText('Nom ou ICE…'), 'Client SAV')
    await user.click(await screen.findByText('Client SAV Test'))

    await user.type(screen.getByLabelText('Description'), 'Panne onduleur')
    await user.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => expect(createTicket).toHaveBeenCalledWith(expect.objectContaining({
      client: 7, description: 'Panne onduleur',
    })))
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ id: 42, reference: 'SAV-0042' }))
  })
})

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/ticket_detail.json'

// ASAV42 — relecture B1 : le PATCH des champs d'abord, l'action de statut
// seulement s'il a réussi (un refus des champs ne change pas le statut) ;
// statuts proposés = `statuts_suivants` du serveur ; date de résolution posée
// par le serveur. Faux serveur bâti sur le contrat ticket_detail.json.

const serveur = vi.hoisted(() => ({ ticket: null, journal: [], refus: false, refusChamps: false, charges: [] }))

vi.mock('../../features/sav/store/ticketsSlice', async (io) => (await import('./__tests__/ticketDetailMocks.js')).ticketsSliceMock(await io(), ({ data }) => {
  serveur.journal.push('PATCH')
  serveur.charges.push(data)
  if (serveur.refusChamps) {
    return Promise.reject({ response: { status: 400, data: { description: ['Décrivez le problème signalé ou la demande du client pour ouvrir le ticket.'] } } })
  }
  serveur.ticket = { ...serveur.ticket, ...data }
  return serveur.ticket
}))

vi.mock('../../api/savApi', async () => (await import('./__tests__/ticketDetailMocks.js')).savApiMock({
  getTicket: vi.fn(() => Promise.resolve({ data: serveur.ticket })),
  resoudreTicket: vi.fn(() => {
    serveur.journal.push('POST resoudre')
    if (serveur.refus) {
      return Promise.reject({ response: { status: 400, data: { detail: 'Transition refusée par le serveur.' } } })
    }
    serveur.ticket = { ...serveur.ticket, statut: 'resolu', statuts_suivants: ['cloture'],
      date_resolution: '2026-10-09' }
    return Promise.resolve({ data: serveur.ticket })
  }),
}))
vi.mock('../../api/axios', async () => (await import('./__tests__/ticketDetailMocks.js')).axiosMock())
vi.mock('../../api/installationsApi', async () => (await import('./__tests__/ticketDetailMocks.js')).installationsApiMock())

import { TicketDetail } from './TicketsPage'
import { ticketStore } from './__tests__/ticketDetailMocks.js'

beforeEach(() => {
  serveur.ticket = { ...CONTRAT.exemple, type: 'correctif', description: 'avant',
    sous_garantie: 'non', couverture: 'a_determiner', devis_id_ext: null,
    facture_id_ext: null, instructions: '', cause: 1, remede: 7 }
  serveur.journal.length = 0
  serveur.charges.length = 0
  serveur.refus = false
  serveur.refusChamps = false
})
afterEach(() => { cleanup() })

function renderDetail() {
  return render(<Provider store={ticketStore('responsable')}><MemoryRouter>
    <TicketDetail ticket={serveur.ticket} onClose={() => {}} onSaved={() => {}} />
  </MemoryRouter></Provider>)
}

const statutBox = () => screen.getAllByRole('combobox').find((c) => c.textContent === 'En cours')

describe('TicketDetail — ASAV42 enregistrement ordonné', () => {
  it('« Nouveau » n\'est pas proposé ; « Résolu » l\'est ; aucun avertissement de saut', async () => {
    const user = userEvent.setup()
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    await user.click(statutBox())
    expect(await screen.findByRole('option', { name: 'Résolu' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Nouveau' })).toBeNull()
    expect(screen.queryByText(/Saut d.étape/)).toBeNull()
  }, 60000)

  it('Résolu : PATCH des champs puis POST resoudre, date posée par le serveur', async () => {
    const user = userEvent.setup()
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: 'edite' } })
    await user.click(statutBox())
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    await waitFor(() => expect(serveur.journal).toEqual(['PATCH', 'POST resoudre']))
    expect(serveur.ticket.description).toBe('edite')
    expect(serveur.ticket.date_resolution).toBe('2026-10-09')
  }, 60000)

  it('transition refusée : champs enregistrés, statut inchangé, l\'écran dit les deux', async () => {
    const user = userEvent.setup()
    serveur.refus = true
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: 'edite' } })
    await user.click(statutBox())
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    expect(await screen.findByText(/Vos modifications sont enregistrées, mais le statut n.a pas changé : Transition refusée par le serveur/)).toBeInTheDocument()
    expect(serveur.journal).toEqual(['PATCH', 'POST resoudre'])
    expect(serveur.ticket.description).toBe('edite')
    expect(serveur.ticket.statut).toBe('en_cours')
  }, 60000)

  // Relecture B1 — un refus des champs ne change PAS le statut.
  it('champs refusés : l\'action de statut n\'est pas lancée', async () => {
    const user = userEvent.setup()
    serveur.refusChamps = true
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: '' } })
    await user.click(statutBox())
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    expect(await screen.findByText(/Décrivez le problème/)).toBeInTheDocument()
    expect(serveur.journal).toEqual(['PATCH'])
    expect(serveur.ticket.statut).toBe('en_cours')
  }, 60000)

  // Relecture B1 — ancien ticket sans description : la charge du bouton ne
  // porte pas la clé (jamais null), le serveur l'accepte.
  it('description non touchée : la charge ne porte pas la clé', async () => {
    const user = userEvent.setup()
    serveur.ticket = { ...serveur.ticket, description: '' }
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    await waitFor(() => expect(serveur.charges).toHaveLength(1))
    expect(serveur.charges[0]).not.toHaveProperty('description')
  }, 60000)
})

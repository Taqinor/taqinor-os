import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import CONTRAT from '../../../../backend/django_core/apps/sav/contract_samples/ticket_detail.json'

// ASAV42 — l'action de statut d'abord, le PATCH seulement si elle réussit ;
// statuts proposés = `statuts_suivants` du serveur ; date de résolution posée
// par le serveur. Faux serveur bâti sur le contrat ticket_detail.json.

const serveur = vi.hoisted(() => ({ ticket: null, journal: [], refus: false }))

vi.mock('../../features/sav/store/ticketsSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, updateTicket: ({ data }) => {
    serveur.journal.push('PATCH')
    serveur.ticket = { ...serveur.ticket, ...data }
    const action = { type: 'sav/updateTicket/noop' }
    action.unwrap = () => Promise.resolve(serveur.ticket)
    return action
  } }
})

vi.mock('../../api/savApi', () => ({
  default: {
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
    getTicketHistorique: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketPieces: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipements: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketsSimilaires: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getTriageIa: vi.fn(() => Promise.resolve({ data: { disponible: false } })),
    getPretsEquipement: vi.fn(() => Promise.resolve({ data: [] })),
    getReponsesType: vi.fn(() => Promise.resolve({ data: [] })),
    getTicketChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    getChecklistTemplates: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: [] })) } }))
vi.mock('../../api/installationsApi', () => ({
  default: { getInterventions: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import { TicketDetail } from './TicketsPage'

beforeEach(() => {
  serveur.ticket = { ...CONTRAT.exemple, type: 'correctif', description: 'avant',
    sous_garantie: 'non', couverture: 'a_determiner', devis_id_ext: null,
    facture_id_ext: null, instructions: '', cause: 1, remede: 7 }
  serveur.journal.length = 0
  serveur.refus = false
})
afterEach(() => { cleanup() })

function renderDetail() {
  const store = configureStore({ reducer: {
    tickets: (state = { items: [] }) => state,
    auth: (state = { role: 'responsable', permissions: [] }) => state,
  } })
  return render(<Provider store={store}><MemoryRouter>
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

  it('Résolu : POST resoudre puis PATCH, date posée par le serveur', async () => {
    const user = userEvent.setup()
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: 'edite' } })
    await user.click(statutBox())
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    await waitFor(() => expect(serveur.journal).toEqual(['POST resoudre', 'PATCH']))
    expect(serveur.ticket.description).toBe('edite')
    expect(serveur.ticket.date_resolution).toBe('2026-10-09')
  }, 60000)

  it('transition refusée : rien n\'est écrit, message serveur, fiche rechargée', async () => {
    const user = userEvent.setup()
    serveur.refus = true
    renderDetail()
    await screen.findByText('Ticket SAV — SAV-2026-10-0042', { exact: false })
    fireEvent.change(screen.getByDisplayValue('avant'), { target: { value: 'edite' } })
    await user.click(statutBox())
    await user.click(await screen.findByRole('option', { name: 'Résolu' }))
    await user.click(screen.getByRole('button', { name: /Mettre à jour/ }))
    expect(await screen.findByText(/Transition refusée par le serveur/)).toBeInTheDocument()
    expect(serveur.journal).toEqual(['POST resoudre'])
    expect(serveur.ticket.description).toBe('avant')
    expect(serveur.ticket.statut).toBe('en_cours')
  }, 60000)
})
